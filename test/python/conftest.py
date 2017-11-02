import logging
from tempfile import NamedTemporaryFile

import dataset
import praw
import requests
from mock import MagicMock, Mock, patch
from pytest import fixture

from shotbot import Shotbot
from shotbot.utils import ensure_schema

SCREENSHOT_PNG_CONTENT = b'deadbeef'


@fixture
def temporary_sqlite_uri():
    with NamedTemporaryFile(suffix='.db') as sqlite_file:
        yield 'sqlite:///' + sqlite_file.name


@fixture
def db(temporary_sqlite_uri):
    yield dataset.connect(temporary_sqlite_uri)


@fixture
def submissions_table(db):
    table = db.create_table('submissions', primary_id='id')
    ensure_schema(table)
    yield table


@fixture(autouse=True)
def no_network_access():
    """Causes any socket creation attempts to fail."""

    def _no(*args, **kwargs):
        raise NotImplementedError("No networking D:<")
    with patch('socket.socket', _no):
        yield


@fixture
def mocked_requests_get():
    """Mocked requests get call."""
    with patch('requests.get', autospec=True) as get:
        with patch('shotbot.bots.renderer.requests.get', get):
            response = Mock(name='MockResponse', spec=requests.models.Response)
            raw_response = Mock(name='MockRawResponse')
            raw_response.read.return_value = b'beefcafe'
            response.raw = raw_response
            get.return_value = response
            yield get


@fixture
def mocked_driver():
    """A mocked Firefox webdriver."""
    with patch('selenium.webdriver.Firefox', autospec=True) as driver:
        with patch('shotbot.bots.renderer.webdriver.Firefox', driver):
            driver = driver.return_value
            driver.get_screenshot_as_png.return_value = SCREENSHOT_PNG_CONTENT
            find_result = driver.find_element_by_xpath.return_value
            find_result.screenshot_as_png = SCREENSHOT_PNG_CONTENT
            find_result.size = {'height': 1000, 'widht': 1000}
            yield driver


@fixture
def mocked_reddit():
    """A mocked Reddit client."""
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
def mocked_imgur():
    """A mocked Imgur client."""
    with patch('imgurpython.ImgurClient', autospec=True) as imgur:
        with patch('shotbot.bots.renderer.imgurpython.ImgurClient', imgur):
            imgur = imgur.return_value
            imgur.upload_from_path.return_value = {
                'link': 'https://i.imgur.com/404',
                'deletehash': 'none',
            }
            yield imgur


@fixture
def isolated_shotbot(mocked_reddit, mocked_driver, mocked_imgur,
                     mocked_requests_get, temporary_sqlite_uri):
    """A Shotbot instance with all its dependencies mocked."""
    reddit_auth = {
        'client_id': 'reddit_client_id',
        'client_secret': 'reddit_client_secret',
        'username': 'username',
        'password': 'p4ssw0rd',
    }
    imgur_auth = {
        'client_id': 'imgur_client_id',
        'client_secret': 'imgur_client_secret',
    }
    yield Shotbot(reddit_auth=reddit_auth,
                  imgur_auth=imgur_auth,
                  db_uri=temporary_sqlite_uri,
                  owner='owner',
                  watched_subreddits=['fakesub'])


@fixture
def debug_logging(caplog):
    """Sets the log level to DEBUG."""
    caplog.set_level(logging.DEBUG)
