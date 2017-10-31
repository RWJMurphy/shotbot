import logging
from tempfile import NamedTemporaryFile
import time

import dataset
from selenium import webdriver

log = logging.getLogger(__name__)


class Renderer():
    def __init__(self, db_uri, kill_switch):
        self.driver = webdriver.Firefox()
        self._db = dataset.connect(db_uri)
        self._kill = kill_switch

    def run(self):
        submissions = self._db['submissions']
        while True:
            for submission in submissions.find(bot_screenshot_at=None,
                                               order_by='created_at'):
                if self._kill.is_set():
                    break
                submission['bot_screenshot_url'] = self.capture(submission.url)
                submission['bot_screenshot_at'] = time.time()
                submissions.update(submission, ['id'])
                self._db.commit()
            self._kill.wait(60)
            if self._kill.is_set():
                break

    def render(self, url):
        # renders given url to temporary file
        self.driver.get(url)
        with NamedTemporaryFile('wb', suffix='.png') as screenshot_file:
            screenshot_file.write(self.driver.get_screenshot_as_png())
            screenshot_file.flush()
            yield screenshot_file

    def capture(self, url):
        # render to temporary file
        with self.render(url) as temp_file:
            # upload to ?
            url = self.upload(temp_file)
        # return hosted URL
        return url

    def upload(self, temp_file):
        return "lolno"
