"""The main entry point for using Shotbot."""
import datetime
import logging
import os
import random
import time
from threading import Event, Thread

import dataset

from .bots import CommentContextRenderer, QuoteCommenter, Watcher
from .utils import ensure_schema
from .version import SHOTBOT_VERSION

USER_AGENT_TMPL = "{platform}:{name}:{version} (by /u/{owner})"

__all__ = ('Shotbot', )
log = logging.getLogger(__name__)


class Shotbot():
    """
    A "bot" that takes screenshots of submitted links.

    Actually orchestrates a swarm of `Watcher`, `CommentContextRenderer` and
    `QuoteCommenter` bots that handle the details of watching subreddits,
    rendering screenshots and posting comments, respectively.
    """

    def __init__(self,
                 reddit_auth,
                 imgur_auth,
                 owner,
                 watched_subreddits,
                 db_uri,
                 dry_run=False,
                 name=None,
                 version=SHOTBOT_VERSION):
        """
        Create a new Shotbot.

        :param reddit_auth:
        :type reddit_auth: dict[str, str]
        :param imgur_auth:
        :type imgur_auth: dict[str, str]
        :param str owner: bot instance's "owning" reddit user
        :param watched_subreddits: list of subreddit names to monitor
        :type watched_subreddits: list[str]
        :param bool dry_run: if True, won't post replies
        :param str db_uri: SQLAlchemy-style URI
        :param name: bot instance's name; defaults to `"Shotbot"`
        :type name: str or None
        :param Version version: bot instance's version; defaults to
        `SHOTBOT_VERSION`
        """
        self.name = name or self.__class__.__name__
        self.version = version
        user_agent = USER_AGENT_TMPL.format(platform=os.name,
                                            name=self.name,
                                            version=self.version,
                                            owner=owner)
        self._reddit_args = self._validate_reddit_auth(reddit_auth)
        self._reddit_args['user_agent'] = user_agent

        self._imgur_auth = self._validate_imgur_auth(imgur_auth)
        self.subreddits = watched_subreddits

        self.dry_run = dry_run
        self._db_uri = db_uri
        # self._db = dataset.connect(self._db_uri)

    @staticmethod
    def _validate_reddit_auth(reddit_auth):
        for key in ['client_id', 'client_secret', 'username', 'password']:
            if not reddit_auth.get(key, None):
                raise ValueError("Missing Reddit auth param {!r}".format(key))
        return reddit_auth.copy()

    @staticmethod
    def _validate_imgur_auth(imgur_auth):
        for key in ['client_id', 'client_secret']:
            if not imgur_auth.get(key, None):
                raise ValueError("Missing Imgur auth param {!r}".format(key))
        return imgur_auth.copy()

    def _spawn_watchers(self, kill_switch):
        watchers = []
        domains = None
        for subreddit, options in self.subreddits.items():
            filters = []
            if 'domains' in options:
                domains = set(options['domains'])

                def _filter_domain(submission):
                    if submission.domain in domains:
                        return True
                    log.debug("filtering submission: domain %r not in %r",
                              submission.domain, domains)
                    return False

                filters.append(_filter_domain)
            if 'newer_than' in options:

                def _filter_newer_than(delta):
                    def _filter(submission):
                        oldest = datetime.datetime.utcnow() - delta
                        then = datetime.datetime.utcfromtimestamp(
                            submission.created_utc)
                        if then >= oldest:
                            return True
                        log.debug("filtering submission: %s older than %r",
                                  submission.created_utc, delta)
                        return False

                    return _filter

                delta = datetime.timedelta(**options['newer_than'])
                filters.append(_filter_newer_than(delta))

            if filters:

                def _all_filters(filters):
                    def _all_filters(submission):
                        return all(_filter(submission) for _filter in filters)

                    return _all_filters

                _filter_fn = _all_filters(filters)
            else:
                _filter_fn = None

            watcher = Watcher(self._reddit_args, self._db_uri, subreddit,
                              kill_switch, _filter_fn)
            watchers.append(watcher)
        return watchers

    def _spawn_swarm(self, kill_switch):
        swarm = []
        # create a watcher per subreddit
        if log.isEnabledFor(logging.DEBUG):
            log.debug("spawning observers for %s", ', '.join(self.subreddits))

        watchers = self._spawn_watchers(kill_switch)
        swarm.extend(Thread(name='watch-{}'.format(bot.subreddit),
                            target=bot.run) for bot in watchers)
        # create screenshot worker
        renderer_count = max(os.cpu_count() - 1, 1)
        log.debug("spawning %d renderers", renderer_count)
        renderers = [
            CommentContextRenderer(self._imgur_auth, self._reddit_args,
                                   self._db_uri, kill_switch)
            for _ in range(renderer_count)
        ]
        swarm.extend(Thread(name='renderer-{}'.format(i),
                            target=bot.run) for i, bot in enumerate(renderers))
        # create a commenter
        log.debug("spawning commenter")
        commenter = QuoteCommenter(self._reddit_args, self._db_uri,
                                   kill_switch, self.dry_run)
        swarm.append(Thread(name='commenter', target=commenter.run))
        return swarm

    @staticmethod
    def _await_swarm(swarm, timeout=None):
        while True:
            for thread in swarm:
                if not thread.is_alive():
                    raise Exception("Thread {}, {} died".format(thread.ident,
                                                                thread.name))
            if timeout and time.time() >= timeout:
                log.debug("time ends")
                break
            time.sleep(1)

    def _ensure_db_schema(self):
        db = dataset.connect(self._db_uri)
        submissions = db.create_table('submissions', primary_id='id')
        ensure_schema(submissions)
        db.commit()
        db.engine.dispose()

    def run(self, timeout=None):  # pylint: disable=missing-raises-doc
        """
        Watch subreddits for submissions, render screenshots and make comments.

        :param timeout: if set, stops running after this many seconds
        :type timeout: int or None
        """
        log.info("%s v%s awakens", self.name, self.version)
        if self.dry_run:
            log.info("dry run, no comments will be posted")
        if timeout is not None:
            timeout = time.time() + timeout
        kill_switch = Event()

        self._ensure_db_schema()

        swarm = self._spawn_swarm(kill_switch)

        # orchestrate the whole thing or crash idk
        # heeeeere we go
        log.info("starting %d thread swarm", len(swarm))
        random.shuffle(swarm)
        for thread in swarm:
            thread.start()
            time.sleep(0.5 + random.random() * 0.5)

        log.debug("monitoring swarm")
        try:
            self._await_swarm(swarm, timeout)
        except Exception:
            log.exception("an exception occured")
            raise
        finally:
            log.info("throwing kill switch and reaping swarm")
            kill_switch.set()
            for thread in swarm:
                thread.join()

    def run_forever(self):
        """Run until something exceptional makes us stop."""
        return self.run(timeout=None)
