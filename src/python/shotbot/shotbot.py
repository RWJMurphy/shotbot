import logging
import os
from threading import Thread, Event
import time

import dataset

from .version import SHOTBOT_VERSION
from .bots import Watcher, Commenter, Renderer

USER_AGENT_TMPL = "{platform}:{name}:{version} (by /u/{owner})"

log = logging.getLogger(__name__)


def _determine_platform():
    return os.name


class Shotbot():
    def __init__(self,
                 client_id,
                 client_secret,
                 username,
                 password,
                 owner,
                 watched_subreddits,
                 db_path,
                 name=None,
                 version=SHOTBOT_VERSION):
        self.name = name or self.__class__.__name__
        self.version = version
        user_agent = USER_AGENT_TMPL.format(platform=_determine_platform(),
                                            name=self.name,
                                            version=self.version,
                                            owner=owner)
        self._reddit_args = {
            'client_id': client_id,
            'client_secret': client_secret,
            'username': username,
            'password': password,
            'user_agent': user_agent,
        }
        self.subreddits = watched_subreddits
        self._db_uri = 'sqlite:///{}'.format(db_path)
        self._db = dataset.connect(self._db_uri)

    def run_forever(self):
        return self.run(timeout=None)

    def _spawn_swarm(self, kill_switch):
        swarm = []
        # create a watcher per subreddit
        if log.isEnabledFor(logging.DEBUG):
            log.debug("spawning observers for %s", ', '.join(self.subreddits))
        watchers = [
            Watcher(self._reddit_args, self._db_uri, subreddit, kill_switch)
            for subreddit in self.subreddits
        ]
        swarm.extend(Thread(name='watch-{}'.format(bot.subreddit),
                            target=bot.run) for bot in watchers)
        # create N screenshot workers
        shotter_count = os.cpu_count()
        log.debug("spawning %d renderers", shotter_count)
        renderers = [
            Renderer(self._db_uri, kill_switch) for _ in range(shotter_count)
        ]
        swarm.extend(Thread(name='renderer-{:d}'.format(i),
                            target=bot.run) for i, bot in enumerate(renderers))
        # create a commenter
        log.debug("spawning commenter")
        commenter = Commenter(self._reddit_args, self._db_uri, kill_switch)
        swarm.append(Thread(name='commenter', target=commenter.run))
        return swarm

    def _await_swarm(self, swarm, timeout=None):
        while True:
            for thread in swarm:
                if not thread.is_alive():
                    raise Exception("{} died".format(thread.name))
            if timeout and time.time() >= timeout:
                log.debug("time ends")
                break
            time.sleep(1)

    def run(self, timeout=None):
        log.info("%s v%s awakens", self.name, self.version)
        if timeout is not None:
            timeout = time.time() + timeout
        kill_switch = Event()
        swarm = self._spawn_swarm(kill_switch)

        # orchestrate the whole thing or crash idk
        # heeeeere we go
        log.debug("starting %d thread swarm", len(swarm))
        for thread in swarm:
            thread.start()

        log.debug("monitoring")
        try:
            self._await_swarm(swarm, timeout)
        except Exception as ex:
            log.exception("an exception occured")
            raise
        finally:
            log.debug("throwing kill switch and reaping swarm")
            kill_switch.set()
            for thread in swarm:
                thread.join()
