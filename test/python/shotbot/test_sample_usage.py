import praw
from mock import MagicMock

from helpers import mock_submission


def test_basic_usage(isolated_shotbot, mocked_reddit, db):
    subreddit = MagicMock(spec=praw.models.Subreddit)
    subreddit.stream.submissions.return_value = [
        mock_submission() for _ in range(100)
    ]
    mocked_reddit.subreddit.return_value = subreddit

    isolated_shotbot.run(1)

    subreddit.stream.submissions.assert_called()
