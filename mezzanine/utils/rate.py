"""
When users tip or flag a submission (i.e. thread or comment)
"""
from drum.links.models import Profile
from drum.chambers.models import Chamber


def tip(request):
    """
    The user has tipped for a contribution. Credit the creator for the amount
    """
    tipper = None
    tipped = None
    amount = None
    tipper_entry = Profile.objects.get(tipper)
    if tipper_entry.balance < amount:
        #todo
        pass
    tipped_entry = Profile.objects.get(tipped)
    tipper_entry.balance -= amount
    tipped_entry.balance += amount
    tipped_entry.save()
    tipper_entry.save()


def flag(request):
    """
    The user has flagged a submission for moderation
    """
    flagger = None
    flagged = None
    chamber = Chamber.objects.get(chamber=request.chamber)
    stake = chamber.flag_stake
    if flagger.balance < stake:
        #todo
        pass
    flagger.balance -= stake
    flagger.save()
    # todo...
    # what to do about flagger balance. maybe profile attr like escrow
