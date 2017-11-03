import datetime

import praw
from mock import MagicMock

from helpers import mock_submission


def test_basic_usage(isolated_shotbot, mocked_reddit, db):
    subreddit = MagicMock(spec=praw.models.Subreddit)
    mocked_submissions = {
        submission.id: submission
        for submission in (mock_submission(mocked_reddit) for _ in range(100))
    }
    for submission in mocked_submissions.values():
        submission.reply.return_value.created = datetime.datetime.utcnow()

    subreddit.stream.submissions.return_value = mocked_submissions.values()
    mocked_reddit.submission.side_effect = lambda id: mocked_submissions[id]
    mocked_reddit.subreddit.return_value = subreddit

    isolated_shotbot.run(1)

    subreddit.stream.submissions.assert_called()
