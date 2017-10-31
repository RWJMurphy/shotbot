import logging
import time

import dataset
import praw

__all__ = ('Commenter', )

log = logging.getLogger(__name__)


class Commenter():
    def __init__(self, reddit_args, db_uri, kill_switch):
        self._reddit = praw.Reddit(**reddit_args)
        self._db = dataset.connect(db_uri)
        self._kill = kill_switch

    def run(self):
        submissions = self._db['submissions']
        while True:
            for submission in submissions.find(bot_commented_at=None,
                                               order_by='created_at'):
                if self._kill.is_set():
                    break
                self.comment(submission)
                submission['bot_commented_at'] = time.time()
                submissions.update(submission, ['id'])
                self._db.commit()
            self._kill.wait(60)
            if self._kill.is_set():
                break

    def comment(self, submission):
        pass
