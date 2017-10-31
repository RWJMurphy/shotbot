import logging
from mock import patch, MagicMock, Mock
from pytest import fixture

import praw

from shotbot import Shotbot


@fixture(autouse=True)
def no_network_access():
    def _no(*args, **kwargs):
        raise NotImplementedError("No networking D:<")
    with patch('socket.socket', _no):
        yield


@fixture
def mocked_driver():
    with patch('selenium.webdriver.Firefox', autospec=True) as driver:
        yield driver.return_value


@fixture
def mocked_reddit():
    with patch('praw.reddit.Reddit', autospec=True) as reddit:
        with patch('shotbot.bots.watcher.praw.Reddit', reddit):
            with patch('shotbot.bots.commenter.praw.Reddit', reddit):
                reddit = reddit.return_value
                reddit.subreddit = subreddit_fn = Mock()
                subreddit_fn.return_value = subreddit = MagicMock(
                    spec=praw.models.Subreddit)
                subreddit.__str__.return_value = "fakesub"
                yield reddit


@fixture
def isolated_shotbot(mocked_reddit, mocked_driver):
    return Shotbot(client_id='client_id',
                   client_secret='client_secret',
                   username='username',
                   password='p4ssw0rd',
                   db_path='',
                   owner='owner',
                   watched_subreddits=['fakesub'])


@fixture
def debug_logging(caplog):
    caplog.set_level(logging.DEBUG)
