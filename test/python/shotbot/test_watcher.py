"""Validate that :class:`Watcher` behaves correctly."""
from threading import Event

from mock import patch
from pytest import fixture

from helpers import mock_submission
from shotbot.bots import Watcher
from shotbot.utils import base36_decode

SUBREDDIT = 'fakesub'


@fixture
def isolated_watcher(mocked_reddit, submissions_table, temporary_sqlite_uri):
    """Return a Watcher with mocked dependencies."""
    kill_switch = Event()
    watchbot = Watcher({}, temporary_sqlite_uri, SUBREDDIT, kill_switch)
    yield watchbot


def test_repr(isolated_watcher):
    '{!r}'.format(isolated_watcher)


def test_kill_switch(isolated_watcher):
    isolated_watcher._kill.set()
    with patch.object(isolated_watcher,
                      '_process_submission') as mocked_process:
        mocked_process.side_effect = NotImplementedError
        isolated_watcher.run()


def test_watcher_run(isolated_watcher):
    with patch.object(isolated_watcher, '_kill') as mock_kill:
        mock_kill.side_effect = [False, True, True]
        with patch.object(isolated_watcher,
                          '_process_submission'):
            isolated_watcher.run()


def test_process_submissions(isolated_watcher, submissions_table):
    """Watcher pulls submissions from subreddit into database."""
    subreddit = isolated_watcher.subreddit
    submissions = [mock_submission() for _ in range(100)]
    subreddit.stream.submissions.return_value = submissions

    isolated_watcher._process_submissions()

    for submission in submissions:
        assert submissions_table.find_one(id=base36_decode(submission.id))


def test_process_submissions_skips_duplicates(isolated_watcher,
                                              submissions_table):
    """Watcher inserts submissions into database only once."""
    subreddit = isolated_watcher.subreddit
    submissions = [mock_submission() for _ in range(10)]
    subreddit.stream.submissions.return_value = submissions * 10

    isolated_watcher._process_submissions()

    for submission in submissions:
        assert submissions_table.count(id=base36_decode(submission.id)) == 1
