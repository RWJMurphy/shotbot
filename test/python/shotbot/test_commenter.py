"""Validate that :class:`Renderer` behaves correctly."""
import copy
import os

from mock import Mock, patch
from pytest import fixture

from helpers import mock_submission
from shotbot.bots import Commenter
from shotbot.utils import submission_as_dict

SUBREDDIT = 'fakesub'


@fixture
def isolated_commenter(mocked_reddit, temporary_sqlite_uri):
    """Return a Commenter with mocked dependencies."""
    kill_switch = Mock()
    kill_switch.is_set.return_value = False
    commenter = Commenter({}, temporary_sqlite_uri, kill_switch)
    yield commenter


def test_process_submissions(isolated_commenter, db, submissions_table):
    """:func:`_process_submissions` behaves as expected."""
    mock_submissions = [
        submission_as_dict(mock_submission()) for _ in range(100)
    ]
    submissions_table.insert_many(mock_submissions)
    db.commit()

    with patch.object(isolated_commenter,
                      '_process_submission') as mocked_process:
        isolated_commenter._process_submissions()
        assert len(mocked_process.mock_calls) == len(mock_submissions)

def test_process_submission(isolated_commenter, mocked_reddit, db, submissions_table):
    """:func:`_process_submission` behaves as expected."""
    submission = submission_as_dict(mock_submission())
    submissions_table.insert(submission)
    db.commit()

    isolated_commenter._process_submission(submissions_table, copy.copy(submission))

    updated_submission = submissions_table.find_one(id=submission['id'])
    assert updated_submission
    assert updated_submission != submission
    assert updated_submission['bot_commented_at']