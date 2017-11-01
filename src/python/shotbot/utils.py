"""Useful functions that don't have a better home."""
import copy
import logging
import string

import praw

log = logging.getLogger(__name__)


def seq_encode(number, symbols):
    """
    Encode a number using a sequence of symbols.

    :param int number: number to encode
    :param symbols: sequence key
    :type symbols: str or list[char]
    :returns: encoded value
    :rtype: str
    """
    d, m = divmod(number, len(symbols))
    if d > 0:
        return seq_encode(d, symbols) + symbols[m]
    return symbols[m]


def seq_decode(_string, symbols):
    """
    Decode a number from a using encoded by a sequence of symbols.

    :param str _string: string to decode
    :param symbols: sequence key
    :type symbols: str or list[char]
    :returns: decoded value
    :rtype: int
    """
    value = 0
    base = len(symbols)
    for i, c in enumerate(reversed(_string)):
        value += symbols.index(c) * i**base
    return value


BASE36_CHARS = string.digits + string.ascii_lowercase
"""Symbols used for base36 encoding"""


def base36_encode(number):
    """
    Encode a number in base36.

    :param int number:
    :returns: base36 encoded value
    :rtype: str
    """
    return seq_encode(number, BASE36_CHARS)


def base36_decode(_string):
    """
    Decode a number from a base36 encoded string.

    :param str _string: base36 encoded value
    :returns: decoded value
    :rtype: int
    """
    return int(_string, base=36)


def submission_as_dict(submission):
    """
    Convert a :class:`Submission` to a flat `dict`.

    Also decodes the base36 encoded `id` field to a plain integer.

    :param Submission submission:
    :returns: a `dict` suitable for storing
    :rtype: dict[str, Any]
    """
    data = {}
    for k, v in submission.__dict__.items():
        if k.startswith('_'):
            continue
        if isinstance(v, praw.models.Redditor):
            v = v.name
        elif isinstance(v, praw.models.Subreddit):
            v = v.display_name
        data[k] = copy.copy(v)
    data['id'] = base36_decode(data['id'])
    return data


def load_submission_for_dict(reddit, submission):
    """
    Load the :class:`Submission` for a submission dict.

    :param Reddit reddit: Reddit client with which to fetch submission
    :param submission: submission as a dict, likely from a DB
    :type submission: dict[str, Any]
    :return: a reddit submission
    :rtype: Submission
    """
    return reddit.submission(id=base36_encode(submission['id']))


SUBMISSIONS_COLUMNS = {
    'bot_screenshot_at': 0,
    'bot_screenshot_url': 'http://example.com',
    'bot_screenshot_deletehash': 'deadbeef',
    'bot_commented_at': 0,
}


def ensure_schema(submissions_table):
    """
    Ensure the required columns exist in the submissions table.

    :param Table submissions_table:
    """
    if all(map(submissions_table.has_column, SUBMISSIONS_COLUMNS)):
        return
    log.debug("Adding screenshot columns to table")
    for column, example in SUBMISSIONS_COLUMNS.items():
        submissions_table.create_column_by_example(column, example)
