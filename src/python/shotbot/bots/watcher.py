"""Watches a subreddit for submissions."""
import logging

import dataset
import praw

from ..utils import (base36_decode, remove_blacklisted_fields,
                     submission_as_dict)

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

    def __repr__(self):
        return '<{cls}(/r/{subreddit}, {db_uri})>'.format(
            cls=self.__class__.__name__,
            subreddit=self.subreddit.display_name,
            db_uri=self._db_uri, )

    def run(self):
        """Watch submission stream until the kill switch is flipped."""
        log.debug("%r running", self)
        while True:
            self._process_submissions()
            self._kill.wait(1)
            if self._kill.is_set():
                return

    def _process_submissions(self):
        db = dataset.connect(self._db_uri)
        try:
            seen = db.create_table('submissions', primary_id='id')
            for submission in self.subreddit.stream.submissions(pause_after=5):
                if self._kill.is_set() or submission is None:
                    return
                if self._process_submission(seen, submission):
                    db.commit()
                    log.info("new submission %d inserted",
                             base36_decode(submission.id))
        finally:
            if hasattr(db.local, 'conn'):
                db.local.conn.close()
            db.engine.dispose()

    @staticmethod
    def _process_submission(seen, submission):
        _id = base36_decode(submission.id)
        existing = seen.find_one(id=_id)
        if existing:
            log.debug("submission %d seen before", _id)
            return False
        seen.insert(remove_blacklisted_fields(submission_as_dict(submission)))
        return True
