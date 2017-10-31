import copy
import logging

import dataset
import praw

from ..utils import base36_decode

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
        self._db = dataset.connect(db_uri)
        self._seen = self._db.create_table('submissions', primary_id='id')
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
        for submission in self.subreddit.stream.submissions():
            if self._kill.is_set():
                return
            log.debug("[%s] %r", submission.id, submission)
            self._process_submission(submission)

    def _process_submission(self, submission):
        existing = self._seen.find_one(id=base36_decode(submission.id))
        if existing:
            log.debug("[%s] seen", submission.id)
            return
        self._seen.insert(_submission_as_dict(submission))
        self._db.commit()
        log.debug("[%s] inserted", submission.id)


def _submission_as_dict(submission):
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
