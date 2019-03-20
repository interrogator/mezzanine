import requests
from drum.chambers.models import Chamber
from django.urls import reverse
from mezzanine.conf import settings


def get_automod_scores(request, chamber_name, text):
    """
    Return a dict of {mod: score} and a dict of {mod: severity}
    """
    lang_url = request.build_absolute_uri(reverse('evaluate'))
    chamber = Chamber.objects.get(chamber=chamber_name)
    automods = chamber._automod_config()
    post_data = dict(text=text, config={}, automods=automods)
    scores = requests.post(lang_url, json=post_data)
    return scores.json(), automods


def score_below_threshold(scores, automods):
    """
    Return a formatted string when the score is too low
    """
    temp = '* "{}" automod needed {} points or more. You got {}.'
    out = list()
    for name, score in scores.items():
        threshold = automods[name]
        if score < threshold:
            msg = temp.format(settings.EVALUATORS[name], threshold, score)
            out.append(msg)
    # keep this for now, useful debug sometimes
    print('scores_below_threshold, scores:', scores, 'automods', automods, out)
    return "<br>".join(out)
