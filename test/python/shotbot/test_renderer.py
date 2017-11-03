"""Validate that :class:`Renderer` behaves correctly."""
import copy
import os
from tempfile import NamedTemporaryFile

from mock import Mock, patch
from pytest import fixture, raises

from helpers import SCREENSHOT_PNG_CONTENT, mock_submission
from shotbot.bots import Renderer
from shotbot.exceptions import RendererException
from shotbot.utils import remove_blacklisted_fields, submission_as_dict

SUBREDDIT = 'fakesub'


@fixture
def isolated_renderer(mocked_driver, mocked_imgur, mocked_requests_get,
                      temporary_sqlite_uri):
    """Return a Renderer with mocked dependencies."""
    kill_switch = Mock()
    kill_switch.is_set.return_value = False
    imgur_auth = {'client_id': '', 'client_secret': ''}
    reddit_args = {'username': 'USERNAME', 'password': 'PASSWORD'}
    renderer = Renderer(imgur_auth, reddit_args, temporary_sqlite_uri,
                        kill_switch)
    renderer.driver = mocked_driver
    try:
        yield renderer
    finally:
        if os.path.exists(Renderer.UBLOCK_XPI_PATH):
            os.remove(Renderer.UBLOCK_XPI_PATH)


def test_render_url(isolated_renderer, mocked_driver):
    """:func:`render` behaves as expected."""
    some_url = "http://example.com"
    temp_file = isolated_renderer.render(some_url)
    assert os.path.exists(temp_file)
    with open(temp_file, 'rb') as temp_fh:
        assert temp_fh.read() == SCREENSHOT_PNG_CONTENT

    mocked_driver.get.assert_called_once_with(some_url)


def test_process_next_submission(isolated_renderer, db, submissions_table):
    """:func:`_process_submissions` behaves as expected."""
    mock_submissions = [
        remove_blacklisted_fields(submission_as_dict(mock_submission()))
        for _ in range(100)
    ]
    submissions_table.insert_many(mock_submissions)
    db.commit()

    with patch.object(isolated_renderer,
                      '_process_submission') as mocked_process:
        isolated_renderer._process_next_submission()
        mocked_process.assert_called_once()


def test_process_submission(isolated_renderer, mocked_driver, mocked_imgur, db,
                            submissions_table):
    """:func:`_process_submission` behaves as expected."""
    submission = remove_blacklisted_fields(
        submission_as_dict(mock_submission()))
    submissions_table.insert(submission)
    db.commit()

    isolated_renderer._process_submission(submissions_table,
                                          copy.copy(submission))

    updated_submission = submissions_table.find_one(id=submission['id'])
    assert updated_submission
    assert updated_submission != submission
    assert updated_submission['bot_screenshot_at']
    assert updated_submission['bot_screenshot_url']


def test_upload(isolated_renderer, mocked_imgur):
    """:func:`upload` behaves as expected."""
    path = "/some/path.png"
    isolated_renderer.upload(path)
    mocked_imgur.upload_from_path.assert_called_once_with(path)


def test_capture(isolated_renderer, mocked_driver):
    some_url = "http://example.com"

    with NamedTemporaryFile(delete=False) as temp_file:
        with patch.object(isolated_renderer, 'render') as mocked_render:
            mocked_render.return_value = temp_file.name
            with patch.object(isolated_renderer, 'upload') as mocked_upload:
                mocked_upload.return_value = 'https://imgur.com/404', 'deadbeef'

                assert os.path.exists(temp_file.name)
                isolated_renderer.capture(some_url)
                assert not os.path.exists(temp_file.name)


@patch('shotbot.bots.renderer.NamedTemporaryFile', autospec=True)
@patch('shotbot.bots.renderer.WebDriverWait', autospec=True)
def test_driver_quits_on_create_exception(mocked_wait, mocked_file,
                                          isolated_renderer, mocked_driver):
    mocked_wait.return_value.until.side_effect = TimeoutError
    with raises(RendererException):
        isolated_renderer._create_driver()

    mocked_driver.quit.assert_called_once()
    mocked_file_in_with = mocked_file.return_value.__enter__.return_value
    mocked_file_in_with.write.assert_called_once_with(SCREENSHOT_PNG_CONTENT)
