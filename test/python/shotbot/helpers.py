"""Useful code shared between tests."""
import random
import time

from praw.models import Submission

from shotbot.utils import base36_encode

SQLITE_IN_MEM = 'sqlite:///'


def _score():
    return random.randint(-10, 100)


def _author():
    return "AUTHOR"


def _created():
    return time.time() - random.randrange(3600)


def _url():
    return "example.com", "https://example.com/"


def _subreddit():
    return "FAKE_SUBREDDIT"


def _title():
    return "SUBMISSION TITLE"


__submission_id = 0


def _submission_id():
    global __submission_id
    __submission_id += 1
    return base36_encode(__submission_id)


def _selftext():
    return """HI REDDIT

THIS IS AN EXAMPLE SELF POST WHIHC IS WHY IM YELLING AT you

* list
* of
* htings

oh no!"""


def mock_submission():
    """
    Create a fake :class:`Submission`.

    :returns: a semi-random faked :class:`Submission`
    :rtype: Submission
    """
    created = _created()
    submission_id = _submission_id()
    selfpost = random.random() <= .3
    subreddit = _subreddit()
    title = _title()

    permalink = '/r/{subreddit}/comments/{id}/{slug}'.format(
        subreddit=subreddit,
        id=submission_id,
        slug=title.lower(), )

    data = {
        "author": _author(),
        "created": created,
        "created_utc": created,
        "id": submission_id,
        "permalink": permalink,
        "score": _score(),
        "subreddit": subreddit,
        "title": title,
    }

    if selfpost:
        data.update({
            'is_self': True,
            "selftext": _selftext(),
            "domain": "self.{}".format(subreddit),
            "url": "https://www.reddit.com{permalink}/".format(
                permalink=permalink),
        })

    else:
        domain, url = _url()
        data.update({
            'is_self': False,
            "selftext": "",
            "url": url,
            "domain": domain,
        })

    return Submission(None, _data=data)
