

from json import dumps
from string import punctuation

from django.apps import apps
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.messages import error
from django.urls import reverse
from django.db.models import ObjectDoesNotExist
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils.translation import ugettext_lazy as _

from drum.chambers.models import Chamber
from drum.links.models import Profile

from mezzanine.conf import settings
from mezzanine.generic.forms import ThreadedCommentForm, RatingForm
from mezzanine.generic.models import Keyword
from mezzanine.utils.cache import add_cache_bypass
from mezzanine.utils.deprecation import is_authenticated
from mezzanine.utils.views import set_cookie, is_spam
from mezzanine.utils.importing import import_dotted_path
from mezzanine.utils.automod import get_automod_scores, score_below_threshold
from mezzanine.utils.rate import tip, flag


@staff_member_required
def admin_keywords_submit(request):
    """
    Adds any new given keywords from the custom keywords field in the
    admin, and returns their IDs for use when saving a model with a
    keywords field.
    """
    keyword_ids, titles = [], []
    remove = punctuation.replace("-", "")  # Strip punctuation, allow dashes.
    for title in request.POST.get("text_keywords", "").split(","):
        title = "".join([c for c in title if c not in remove]).strip()
        if title:
            kw, created = Keyword.objects.get_or_create_iexact(title=title)
            keyword_id = str(kw.id)
            if keyword_id not in keyword_ids:
                keyword_ids.append(keyword_id)
                titles.append(title)
    return HttpResponse("%s|%s" % (",".join(keyword_ids), ", ".join(titles)),
        content_type='text/plain')


def initial_validation(request, prefix, score=None):
    """
    Returns the related model instance and post data to use in the
    comment/rating views below.

    Both comments and ratings have a ``prefix_ACCOUNT_REQUIRED``
    setting. If this is ``True`` and the user is unauthenticated, we
    store their post data in their session, and redirect to login with
    the view's url (also defined by the prefix arg) as the ``next``
    param. We can then check the session data once they log in,
    and complete the action authenticated.

    On successful post, we pass the related object and post data back,
    which may have come from the session, for each of the comments and
    ratings view functions to deal with as needed.
    """
    score = score or dict()
    post_data = request.POST
    login_required_setting_name = prefix.upper() + "S_ACCOUNT_REQUIRED"
    posted_session_key = "unauthenticated_" + prefix
    redirect_url = ""
    if getattr(settings, login_required_setting_name, False):
        if not is_authenticated(request.user):
            if request.method == "POST":
                request.session[posted_session_key] = request.POST
                error(request, _("You must be logged in. Please log in or "
                                 "sign up to complete this action."))
            redirect_url = "%s?next=%s" % (settings.LOGIN_URL, reverse(prefix))
        elif posted_session_key in request.session:
            post_data = request.session.pop(posted_session_key)
    if not redirect_url:
        model_data = post_data.get("content_type", "").split(".", 1)
        if len(model_data) != 2:
            return HttpResponseBadRequest()
        try:
            model = apps.get_model(*model_data)
            obj = model.objects.get(id=post_data.get("object_pk", None))
        except (TypeError, ObjectDoesNotExist, LookupError):
            redirect_url = "/"
    if redirect_url:
        if request.is_ajax():
            return HttpResponse(dumps({"location": redirect_url}))
        else:
            return redirect(redirect_url)
    return obj, post_data


def comment(request, template="generic/comments.html", extra_context=None):
    """
    Handle a ``ThreadedCommentForm`` submission and redirect back to its
    related object.
    """
    response = initial_validation(request, "comment")
    if isinstance(response, HttpResponse):
        return response
    obj, post_data = response
    form_class = import_dotted_path(settings.COMMENT_FORM_CLASS)
    form = form_class(request, obj, post_data)
    if form.is_valid():
        chamber = form.cleaned_data["chamber"]
        text = form.cleaned_data["comment"]
        url = obj.get_absolute_url()

        if is_spam(request, form, url):
            return redirect(url)

        # check if balance is too low
        user_balance = Profile.objects.get(user=request.user).balance
        min_comment_balance = Chamber.objects.get(chamber=chamber).min_comment_balance
        if user_balance < min_comment_balance:
            msg = "Balance ({}) too low to comment in '{}'. Minimum: {}"
            form = msg.format(user_balance, chamber, min_comment_balance)
            error(request, form)
            return redirect(chamber)

        scores, automods = get_automod_scores(request, chamber, text)
        fail_info = score_below_threshold(scores, automods)
        comment = form.save(request, failed_automod=fail_info)
        response = redirect(add_cache_bypass(comment.get_absolute_url()))
        # Store commenter's details in a cookie for 90 days.
        for field in ThreadedCommentForm.cookie_fields:
            cookie_name = ThreadedCommentForm.cookie_prefix + field
            cookie_value = post_data.get(field, "")
            set_cookie(response, cookie_name, cookie_value)
        return response
    elif request.is_ajax() and form.errors:
        return HttpResponse(dumps({"errors": form.errors}))
    # Show errors with stand-alone comment form.
    context = {"obj": obj, "posted_comment_form": form}
    context.update(extra_context or {})
    return TemplateResponse(request, template, context)


def rating(request):
    """
    Handle a ``RatingForm`` submission and redirect back to its
    related object.
    """
    response = initial_validation(request, "rating")
    if isinstance(response, HttpResponse):
        return response
    obj, post_data = response
    rating = post_data['value']
    url = add_cache_bypass(obj.get_absolute_url().split("#")[0])
    response = redirect(url + "#rating-%s" % obj.id)

    # this rating 2-3 thing is not good. right now the user can't click tip
    # and select amount, or click flag and choose to stake or not. do not
    # bother developing this stuff until we can get all the correct data
    # into this form. this means we need a dropdown or a modal in frontend,
    # which adds amount. for tip the amount should be customisable; for
    # flag, amount is either chamber.remove_stake_amount or 0.
    if rating in {2, 3}:
        if rating == 2:
            tip(request)
        elif rating == 3:
            flag(request)
        return response

    rating_form = RatingForm(request, obj, post_data)
    if rating_form.is_valid():
        rating_form.save()
        if request.is_ajax():
            # Reload the object and return the rating fields as json.
            obj = obj.__class__.objects.get(id=obj.id)
            rating_name = obj.get_ratingfield_name()
            json = {}
            for f in ("average", "count", "sum"):
                json["rating_" + f] = getattr(obj, "%s_%s" % (rating_name, f))
            response = HttpResponse(dumps(json))
        if rating_form.undoing:
            ratings = set(rating_form.previous) ^ set([rating_form.current])
        else:
            ratings = rating_form.previous + [rating_form.current]
        set_cookie(response, "mezzanine-rating", ",".join(ratings))
