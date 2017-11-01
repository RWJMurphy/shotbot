"""Watches a subreddit for submissions."""
import logging

import dataset
import praw

from ..utils import base36_decode, submission_as_dict

__all__ = ('Watcher', )

log = logging.getLogger(__name__)


class Watcher():
    """Watches a subreddit and inserts submissions into a database."""

    def __init__(self, reddit_args, db_uri, subreddit, kill_switch):
        """
        Create a new Watcher.

        :param reddit_args: dict of arguments to pass to :class:`Reddit`
        :type reddit_args: dict[str, str]
        :param str db_uri: SQLAlchemy-style DB URI
        :param str subreddit: name of the subreddit to watch
        :param Event kill_switch: when set, breaks the loop in :meth:`run`,
        and prevents :meth:`_process_submissions` from processing submissions
        """
        self._reddit = praw.Reddit(**reddit_args)
        self._reddit.read_only = True
        self._db_uri = db_uri
        self.subreddit = self._reddit.subreddit(subreddit)
        self._kill = kill_switch

    def run(self):
        """Watch submission stream until the kill switch is flipped."""
        while True:
            self._process_submissions()
            self._kill.wait(60)
            if self._kill.is_set():
                return

    def _process_submissions(self):
        db = dataset.connect(self._db_uri)
        seen = db.create_table('submissions', primary_id='id')
        for submission in self.subreddit.stream.submissions():
            if self._kill.is_set():
                return
            log.debug("[%s] %r", submission.id, submission)
            self._process_submission(seen, submission)
            db.commit()
            log.debug("[%s] inserted", submission.id)

    @staticmethod
    def _process_submission(seen, submission):
        _id = base36_decode(submission.id)
        existing = seen.find_one(id=_id)
        if existing:
            log.debug("[%s] seen", submission.id)
            return
        seen.insert(submission_as_dict(submission))
