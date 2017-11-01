"""Renders screenshots."""
import logging
import os
import time
from tempfile import NamedTemporaryFile

import dataset
import imgurpython
from selenium import webdriver

log = logging.getLogger(__name__)


class Renderer():
    """Renders screenshots of submitted webpages."""

    def __init__(self, imgur_auth, db_uri, kill_switch):
        """
        Create a new Renderer.

        :param imgur_auth: dict of arguments to pass to :class:`ImgurClient`
        :type imgur_auth: dict[str, str]
        :param str db_uri: SQLAlchemy-style DB URI
        :param Event kill_switch: when set, breaks the loop in :meth:`run`,
        and prevents :meth:`_process_submissions` from processing submissions
        """
        self.driver = webdriver.Firefox()
        self._db_uri = db_uri
        self._imgur = imgurpython.ImgurClient(**imgur_auth)
        self._kill = kill_switch

    def run(self):
        """Consume and render submissions until killed."""
        while True:
            self._process_submissions()
            self._kill.wait(60)
            if self._kill.is_set():
                break

    def _process_submissions(self):
        db = dataset.connect(self._db_uri)
        submissions_table = db['submissions']
        for submission in submissions_table.find(bot_screenshot_at=None,
                                                 order_by='created_at'):
            if self._kill.is_set():
                break
            self._process_submission(submissions_table, submission)
            db.commit()

    def _process_submission(self, submissions_table, submission):
        log.debug("[%s] consuming", submission['id'])
        url, deletehash = self.capture(submission['url'])
        submission['bot_screenshot_url'] = url
        submission['bot_screenshot_deletehash'] = deletehash
        submission['bot_screenshot_at'] = time.time()
        submissions_table.update(submission, ['id'])

    def render(self, url):
        """
        Render a screenshot of a webpage to a temporary file.

        :param str url: URL of webpage to render
        :returns: path to PNG screenshot of webpage
        :rtype: str
        """
        self.driver.get(url)
        screenshot_file = NamedTemporaryFile('wb', suffix='.png', delete=False)
        screenshot_file.write(self.driver.get_screenshot_as_png())
        screenshot_file.flush()
        screenshot_file.close()
        return screenshot_file.name

    def capture(self, url):
        """
        Render a screenshot of a webpage and upload it to Imgur.

        :param str url: URL of webpage to render
        :returns: URL of screenshot and image deletehash
        :rtype: tuple[str, str]
        """
        temp_file_path = None
        try:
            # render to temporary file
            temp_file_path = self.render(url)
            # upload to ?
            url, deletehash = self.upload(temp_file_path)
        finally:
            if temp_file_path:
                os.unlink(temp_file_path)
        # return hosted URL
        return url, deletehash

    def upload(self, file_path):
        """
        Upload a file to Imgur.

        :param str file_path: path to file to upload
        :returns: URL of screenshot and image deletehash
        :rtype: tuple[str, str]
        """
        response = self._imgur.upload_from_path(file_path)
        return response['link'], response['deletehash']
