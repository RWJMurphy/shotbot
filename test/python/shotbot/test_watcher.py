"""Validate that :class:`Watcher` behaves correctly."""
from mock import Mock
from pytest import fixture

from helpers import SQLITE_IN_MEM, mock_submission
from shotbot.bots import Watcher
from shotbot.utils import base36_decode

SUBREDDIT = 'fakesub'


@fixture
def isolated_watcher(mocked_reddit):
    """Return a Watcher with mocked dependencies."""
    kill_switch = Mock()
    kill_switch.is_set.return_value = False
    watchbot = Watcher({}, SQLITE_IN_MEM, SUBREDDIT, kill_switch)
    yield watchbot


def test_process_submissions(isolated_watcher):
    """Watcher pulls submissions from subreddit into database."""
    subreddit = isolated_watcher.subreddit
    submissions = [mock_submission() for _ in range(100)]
    subreddit.stream.submissions.return_value = submissions

    isolated_watcher._process_submissions()
    table = isolated_watcher._db['submissions']

    for submission in submissions:
        assert table.find_one(id=base36_decode(submission.id))


def test_process_submissions_skips_duplicates(isolated_watcher):
    """Watcher inserts submissions into database only once."""
    subreddit = isolated_watcher.subreddit
    submissions = [mock_submission() for _ in range(10)]
    subreddit.stream.submissions.return_value = submissions * 10

    isolated_watcher._process_submissions()
    table = isolated_watcher._db['submissions']

    for submission in submissions:
        assert table.count(id=base36_decode(submission.id)) == 1
