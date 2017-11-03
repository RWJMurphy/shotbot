"""Useful functions that don't have a better home."""
import copy
import itertools
import logging
import re
import string

import praw
import sqlalchemy.types

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


BLACKLISTED_FIELDS = set([
    # Complex values
    'media',
    'media_embed',
    'preview',
    'report_reasons',
    'secure_media',
    'secure_media_embed',
    # Don't care
    'approved',
    'approved_by',
    'approved_at_utc',
    'author_flair_css_class',
    'banned_at_utc',
    'brand_safe',
    'can_gild',
    'clicked',
    'comment_sort',
    'contest_mode',
    'distinguished',
    'hide_score',
    'is_reddit_media_domain',
    'is_video',
    'link_flair_css_class',
    'locked',
    'mod_reports',
    'name',
    'num_reports',
    'parent_whitelist_status',
    'quarantine',
    'removal_reason',
    'saved',
    'spoiler',
    'subreddit_id',
    'subreddit_name_prefixed',
    'subreddit_type',
    'suggested_sort',
    'thumbnail',
    'thumbnail_width',
    'thumbnail_height',
    'user_reports',
    'visited',
    'whitelist_status',
    # Legacy
    'downs',
    'likes',
    'ups',
    # Used in testing
    'comments',  # fake attr set for testing
    'method_calls',  # or the DB gets sad about MockSubmission
])
"""Submission fields we don't care to store in the DB."""


def remove_blacklisted_fields(submission):
    """
    Remove blacklisted fields from submission dict.

    :param submission: submission as a dict, likely from a DB
    :type submission: dict[str, Any]
    :returns: submission minus blacklisted fields
    :rtype: dict[str, Any]
    """
    submission = submission.copy()
    for field in set(submission.keys()) & BLACKLISTED_FIELDS:
        del submission[field]
    return submission


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
    'bot_commented_at': sqlalchemy.types.DateTime,
    'bot_screenshot_at': sqlalchemy.types.DateTime,
    'bot_screenshot_deletehash': sqlalchemy.types.String(length=16),
    'bot_screenshot_lock': sqlalchemy.types.DateTime,
    'bot_screenshot_url': sqlalchemy.types.String(length=256),
}


def ensure_schema(submissions_table):
    """
    Ensure the required columns exist in the submissions table.

    :param Table submissions_table:
    """
    if all(map(submissions_table.has_column, SUBMISSIONS_COLUMNS)):
        return
    log.debug("Adding screenshot columns to table")
    for column, _type in SUBMISSIONS_COLUMNS.items():
        submissions_table.create_column(column, _type)


def markdown_quote(text, quote='> '):
    """
    Blockquote a chunk of text.

    :param str text:
    :param str quote:
    :returns: text with markdown quotes
    :rtype: str
    """
    return ''.join(item
                   for pair in zip(
                       itertools.cycle([quote]), text.splitlines(True))
                   for item in pair)


MARKDOWN_ESCAPE_CHARS = re.compile(r'([\\`*_{}\[\]()#+.!-])')


def markdown_escape(text):
    """
    Escape Markdown characters in text.

    :param str text:
    :returns: text with Markdown escaped
    :rtype: str
    """
    return MARKDOWN_ESCAPE_CHARS.sub(r'\\\1', str(text))


COMMENT_URL_RE = re.compile(
    r'http(s)?://([^.]+\.)?reddit\.com'
    r'/r/[^/]+/comments/[0-9a-z]+/[^/]+/(?P<id>[0-9a-z]+)(/(\?.*)?)?'
)  # noqa


def is_comment_url(url):
    """
    :param str url:
    :returns: True if the given URL is a Reddit comment URL, False otherwise
    :rtype: bool
    """
    return bool(COMMENT_URL_RE.match(url))


def comment_id_from_url(url):
    """
    :param str url: a Reddit comment URL
    :returns: the comment ID from the URL
    :rtype: str
    """
    return COMMENT_URL_RE.match(url).group('id')
