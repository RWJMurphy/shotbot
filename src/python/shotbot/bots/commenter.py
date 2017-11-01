"""Comments on submissions."""
import logging
import time

import dataset
import praw

from ..utils import load_submission_for_dict

__all__ = ('Commenter', )

log = logging.getLogger(__name__)


class Commenter():
    """Comments on submissions with screenshot and quote."""

    def __init__(self, reddit_args, db_uri, kill_switch):
        """
        Create a new Commenter.

        :param reddit_args: dict of arguments to pass to :class:`Reddit`
        :type reddit_args: dict[str, str]
        :param str db_uri: SQLAlchemy-style DB URI
        :param Event kill_switch: when set, breaks the loop in :meth:`run`,
        and prevents :meth:`_process_submissions` from processing submissions
        """
        self._reddit = praw.Reddit(**reddit_args)
        self._db_uri = db_uri
        self._kill = kill_switch

    def run(self):
        """Consume and comment on submissions until killed."""
        while True:
            self._process_submissions()
            self._kill.wait(60)
            if self._kill.is_set():
                break

    def _process_submissions(self):
        db = dataset.connect(self._db_uri)
        submissions = db['submissions']
        for submission in submissions.find(bot_commented_at=None,
                                           order_by='created_at'):
            if self._kill.is_set():
                break
            self._process_submission(submissions, submission)
            db.commit()

    def _process_submission(self, submissions, submission):
        commented_at = self.comment(submission)
        submission['bot_commented_at'] = commented_at
        submissions.update(submission, ['id'])

    def _existing_comment(self, submission):
        submission = load_submission_for_dict(self._reddit, submission)
        for comment in submission.comments:
            if comment.author.name == self._reddit.config.username:
                return comment
        return None

    def comment(self, submission):
        """
        Post a comment, with screenshot and quote, on the submission.

        If we find we've already commented on the submission, we record the time
        of that comment in the DB and don't post another.

        :param submission: submission on which to comment
        :type submission: dict[str, Any]
        :returns: time comment posted
        :rtype: int
        """
        existing_comment = self._existing_comment(submission)
        if existing_comment:
            log.warning("[%s] already commented", submission['id'])
            return existing_comment.created_at

        # post comment to reddit
        commented_at = time.time()
        return commented_at
