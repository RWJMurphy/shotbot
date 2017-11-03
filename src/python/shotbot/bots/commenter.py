"""Comments on submissions."""
import datetime
import logging
import re

import dataset
import praw
from jinja2 import Environment, PackageLoader

from ..exceptions import CommenterException
from ..utils import (base36_decode, load_submission_for_dict, markdown_escape,
                     markdown_quote)

__all__ = ('Commenter', )

log = logging.getLogger(__name__)


class Commenter():
    """Comments on submissions with screenshot and quote."""

    def __init__(self, reddit_args, db_uri, kill_switch, dry_run=True):
        """
        Create a new Commenter.

        :param reddit_args: dict of arguments to pass to :class:`Reddit`
        :type reddit_args: dict[str, str]
        :param str db_uri: SQLAlchemy-style DB URI
        :param Event kill_switch: when set, breaks the loop in :meth:`run`,
        and prevents :meth:`_process_submissions` from processing submissions
        :param bool dry_run: if True, doesn't post comments, just logs them
        """
        self._reddit = praw.Reddit(**reddit_args)
        self._db_uri = db_uri
        self._kill = kill_switch
        self._jinja = self._create_jinja_env()
        self.dry_run = dry_run

    @staticmethod
    def _create_jinja_env():
        env = Environment(loader=PackageLoader('shotbot'))
        env.filters['markdown_escape'] = markdown_escape
        env.filters['markdown_quote'] = markdown_quote
        env.filters['parse_utc_epoch'] = datetime.datetime.utcfromtimestamp
        return env

    def __repr__(self):
        return '<{cls}({db_uri}, /u/{reddit_user})>'.format(
            cls=self.__class__.__name__,
            db_uri=self._db_uri,
            reddit_user=self._reddit.config.username)

    def run(self):
        """Consume and comment on submissions until killed."""
        log.debug("%r running", self)
        while True:
            self._process_submissions()
            self._kill.wait(1)
            if self._kill.is_set():
                break

    def _process_submissions(self):
        db = dataset.connect(self._db_uri)
        try:
            submissions = db['submissions']
            for submission in submissions.find(
                    submissions.table.columns.bot_screenshot_url != None,  # noqa (SQLAlchemy won't let us do "is not None")
                    bot_commented_at=None,
                    order_by='created'):
                if self._kill.is_set():
                    break
                self._process_submission(submissions, submission)
                db.commit()
        finally:
            if hasattr(db.local, 'conn'):
                db.local.conn.close()
            db.engine.dispose()

    def _process_submission(self, submissions, submission):
        commented_at = self.comment(submission)
        submission['bot_commented_at'] = commented_at
        submissions.update(submission, ['id'])

    def _existing_comment(self, submission):
        for comment in submission.comments:
            try:
                if comment.author.name == self._reddit.config.username:
                    return comment
            except AttributeError:
                continue
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
        submission_obj = load_submission_for_dict(self._reddit, submission)
        existing_comment = self._existing_comment(submission_obj)
        if existing_comment:
            log.warning("[%s] already commented: %s", submission['id'],
                        existing_comment.permalink)
            return existing_comment.created

        # post comment to reddit
        try:
            commented_at = self._post_comment(submission_obj,
                                              submission['bot_screenshot_url'])
            log.info("submission %s commented", submission['id'])
        except CommenterException:
            log.exception("Failed to generate comment for submission %s",
                          submission['id'])
            commented_at = 0
        return commented_at

    def _post_comment(self, submission, screenshot):
        comment_body = self._generate_comment(submission, screenshot)
        if self.dry_run:
            log.info("Dry run; would have commented following on %s:\n%s",
                     submission.permalink, comment_body)
            return None
        log.debug("Comment for submission %s\n%s",
                  base36_decode(submission.id), comment_body)
        reply = submission.reply(comment_body)
        log.debug("Posted reply: %r", reply)
        return reply.created

    def _generate_comment(self, submission, screenshot):
        template = self._jinja.get_template('comment.md.j2')
        comment_body = template.render(submission=submission,
                                       screenshot=screenshot)
        return comment_body


class QuoteCommenter(Commenter):
    """If a submission links to a Reddit comment, quotes the linked comment."""
    COMMENT_URL_RE = re.compile(
        r'http(s)?://([^.]+\.)?reddit\.com/r/[^/]+/comments/[0-9a-z]+/[^/]+/(?P<id>[0-9a-z]+)(/(\?.*)?)?')  # noqa

    REMOVED_COMMENT = '[removed]'
    DELETED_COMMENT = '[deleted]'

    @classmethod
    def _is_comment_url(cls, url):
        return bool(cls.COMMENT_URL_RE.match(url))

    @classmethod
    def _comment_id_from_url(cls, url):
        return cls.COMMENT_URL_RE.match(url).group('id')

    @classmethod
    def _is_comment_submission(cls, submission):
        return (not submission.is_self and
                submission.domain == 'reddit.com' and
                cls._is_comment_url(submission.url))

    def _get_linked_comment(self, submission):
        return self._reddit.comment(
            id=self._comment_id_from_url(submission.url))

    def _generate_comment(self, submission, screenshot):
        if not self._is_comment_submission(submission):
            log.warning(
                "non comment submission %r, url: %s, is_self: %s, domain: %s",
                submission, submission.url, submission.is_self,
                submission.domain)
            return super()._generate_comment(submission, screenshot)
        comment = self._get_linked_comment(submission)
        if comment.body in (self.REMOVED_COMMENT, self.DELETED_COMMENT):
            raise CommenterException("comment {} deleted".format(comment))

        template = self._jinja.get_template('quote_comment.md.j2')
        comment_body = template.render(submission=submission,
                                       comment=comment,
                                       screenshot=screenshot)
        return comment_body
