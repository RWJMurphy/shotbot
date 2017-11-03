"""Renders screenshots."""
import datetime
import logging
import os
from tempfile import NamedTemporaryFile
from threading import Lock

import dataset
import imgurpython
import requests
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as expect
from selenium.webdriver.support.ui import WebDriverWait

from ..exceptions import RendererException

__all__ = ('REDDIT_HOME', 'MAX_SCREENSHOT_HEIGHT', 'Renderer')

log = logging.getLogger(__name__)

REDDIT_HOME = 'https://www.reddit.com'

MAX_SCREENSHOT_HEIGHT = 4000


class Renderer():
    """Renders screenshots of submitted webpages."""
    _lock = Lock()

    def __init__(self, imgur_auth, reddit_args, db_uri, kill_switch):
        """
        Create a new Renderer.

        :param imgur_auth: dict of arguments to pass to :class:`ImgurClient`
        :type imgur_auth: dict[str, str]
        :param reddit_args: dict of arguments to pass to :class:`Reddit`
        :type reddit_args: dict[str, str]
        :param str db_uri: SQLAlchemy-style DB URI
        :param Event kill_switch: when set, breaks the loop in :meth:`run`,
        and prevents :meth:`_process_submissions` from processing submissions
        """
        self._db_uri = db_uri
        self._imgur = imgurpython.ImgurClient(**imgur_auth)
        self._reddit_args = reddit_args
        self._kill = kill_switch
        self.driver = None

    def _authenticate_reddit(self, driver):
        username_field = driver.find_element_by_xpath(
            "//form[@id='login_login-main']/input[@name='user']")
        password_field = driver.find_element_by_xpath(
            "//form[@id='login_login-main']/input[@name='passwd']")
        remember = driver.find_element_by_id('rem-login-main')
        submit = driver.find_element_by_xpath(
            "//form[@id='login_login-main']/div/button[@type='submit']")

        username_field.send_keys(self._reddit_args['username'])
        password_field.send_keys(self._reddit_args['password'])
        remember.click()
        submit.click()

        logged_in = expect.presence_of_element_located((By.CLASS_NAME,
                                                        'userkarma'))
        try:
            WebDriverWait(driver, 10).until(logged_in)
        except TimeoutError:
            log.warning("Failed to login to reddit")
            with NamedTemporaryFile(suffix='.png', delete=False) as tmp_fh:
                tmp_fh.write(driver.get_screenshot_as_png())
            log.warning('Wrote screenshot to %s', tmp_fh.name)
            # for log_type in driver.log_types():
            #     log.warning("%s log:\n%s", log_type, driver.get_log(log_type))
            raise RendererException("Failed to login to reddit")

    @staticmethod
    def _accept_cookies(driver):
        try:
            driver.find_element_by_id('eu-cookie-policy').submit()
        except NoSuchElementException:
            pass

    UBLOCK_XPI_URL = ("https://addons.mozilla.org/firefox/downloads/latest"
                      "/ublock/type:attachment/addon-576580-latest.xpi")
    UBLOCK_XPI_PATH = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), '..', 'ublock.xpi')

    def _download_ublock(self):
        log.debug("downloading ublock origin")
        response = requests.get(self.UBLOCK_XPI_URL, stream=True)
        response.raise_for_status()
        with open(self.UBLOCK_XPI_PATH, 'wb') as ublock_file:
            ublock_file.write(response.raw.read())

    def _install_ublock(self, driver):
        with self._lock:
            if not os.path.exists(self.UBLOCK_XPI_PATH):
                self._download_ublock()
        log.debug("installing ublock origin")
        driver.install_addon(self.UBLOCK_XPI_PATH)

    def _create_driver(self):
        driver = webdriver.Firefox()
        try:
            self._install_ublock(driver)
            driver.get(REDDIT_HOME)
            self._accept_cookies(driver)
            self._authenticate_reddit(driver)
        except Exception:
            driver.quit()
            raise
        self.driver = driver

    def __del__(self):
        try:
            self.driver.quit()
        except AttributeError:
            pass

    def __repr__(self):
        return '<{cls}({db_uri}, Firefox, Imgur, {db_uri})>'.format(
            cls=self.__class__.__name__,
            db_uri=self._db_uri)

    def run(self):
        """Consume and render submissions until killed."""
        log.debug("%r running", self)
        self._create_driver()
        while True:
            self._process_next_submission()
            self._kill.wait(1)
            if self._kill.is_set():
                break

    LOCK_TIME = datetime.timedelta(minutes=5)

    def _process_next_submission(self):
        db = dataset.connect(self._db_uri)
        try:
            submissions_table = db['submissions']
            log.debug("checking for next submission that needs screenshot")
            for submission in submissions_table.find(bot_screenshot_at=None,
                                                     order_by='created'):
                now = datetime.datetime.utcnow()
                is_locked = (submission['bot_screenshot_lock'] and
                             now < submission['bot_screenshot_lock'])
                if is_locked:
                    log.debug("submission %d locked, continuing",
                              submission['id'])
                    continue
                submission['bot_screenshot_lock'] = now + self.LOCK_TIME
                submissions_table.update(submission, ['id'])
                db.commit()
                log.debug("submission %d screenshot lock acquired",
                          submission['id'])
                self._process_submission(submissions_table, submission)
                db.commit()
                log.info("submission %d screenshot generated",
                         submission['id'])
                return
        finally:
            if hasattr(db.local, 'conn'):
                db.local.conn.close()
            db.engine.dispose()

    def _process_submission(self, submissions_table, submission):
        log.debug("rendering submission %d", submission['id'])
        url, deletehash = self.capture(submission['url'])
        submission['bot_screenshot_url'] = url
        submission['bot_screenshot_deletehash'] = deletehash
        submission['bot_screenshot_at'] = datetime.datetime.utcnow()
        submissions_table.update(submission, ['id'])

    def render(self, url, max_height=MAX_SCREENSHOT_HEIGHT):
        """
        Render a screenshot of a webpage to a temporary file.

        :param str url: URL of webpage to render
        :param int max_height: maximum height in px
        :returns: path to PNG screenshot of webpage
        :rtype: str
        """
        log.debug("rendering %s", url)
        self.driver.get(url)
        screenshot_file = NamedTemporaryFile('wb', suffix='.png', delete=False)
        try:
            page = self.driver.find_element_by_xpath("/html/body")
            if max_height and page.size['height'] > max_height:
                log.debug("page height %d greater than %d; trimming",
                          page.size['height'], max_height)
                cap_element_js = """
                $('{selector}')[0].style.maxHeight = '{height}px';
                $('{selector}')[0].style.overflow = 'hidden';
                """

                script = cap_element_js.format(selector='body',
                                               height=max_height)
                self.driver.execute_script(script)
                log.debug("new page height %d", page.size['height'])

            screenshot = page.screenshot_as_png
            screenshot_file.write(screenshot)
            screenshot_file.flush()
        finally:
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
            image_url, deletehash = self.upload(temp_file_path)
        finally:
            if temp_file_path:
                os.unlink(temp_file_path)
        # return hosted URL
        log.info("captured %r to %r", url, image_url)
        return image_url, deletehash

    def upload(self, file_path):
        """
        Upload a file to Imgur.

        :param str file_path: path to file to upload
        :returns: URL of screenshot and image deletehash
        :rtype: tuple[str, str]
        """
        log.debug("uploading %s to imgur", file_path)
        response = self._imgur.upload_from_path(file_path)
        log.debug("upload respons: %r", response)
        return response['link'], response['deletehash']
