"""Command line interface to Shotbot."""
import logging
import os

import click
from ruamel import yaml

from .shotbot import SHOTBOT_VERSION, Shotbot

__all__ = ('DEFAULT_CONFIG', 'DEFAULT_CONFIG_PATH', 'main')

DEFAULT_CONFIG_PATH = 'shotbot.yaml'
DEFAULT_CONFIG = {
    'reddit_auth': {
        'client_id': 'REDDIT_CLIENT_ID',
        'client_secret': 'REDDIT_CLIENT_SECRET',
        'username': 'REDDIT_USERNAME',
        'password': 'REDDIT_PASSWORD',
    },
    'imgur_auth': {
        'client_id': 'REDDIT_CLIENT_ID',
        'client_secret': 'REDDIT_CLIENT_SECRET',
    },
    'owner': 'YOUR_USERNAME',
    'watched_subreddits': [
        'subreddit',
        'truesubreddit',
        'subredditsucks',
        'shitsubredditsays',
    ],
    'db_uri': 'sqlite:///shotbot.db',
}


def _populate_config(config_file):
    with open(config_file, 'w') as config_fh:
        yaml.dump(DEFAULT_CONFIG, config_fh, default_flow_style=False)


@click.command()
@click.help_option('--help', '-h')
@click.version_option(str(SHOTBOT_VERSION))
@click.option('--config-file',
              '-c',
              type=str,
              default=None,
              help='shotbot config file',
              metavar='shotbot.yaml')
@click.option('--verbose', '-v', is_flag=True, help='enable verbose logging')
def main(config_file, verbose):  # pylint:disable=W9015,W9016
    """Reddit bot that posts screenshots of submissions."""
    log_format = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
    debug_log_format = (
        "%(asctime)s %(levelname)s [%(thread)d %(threadName)s] [%(name)s] "
        "%(message)s (%(filename)s:%(lineno)s:%(funcName)s)")
    if verbose:
        logging.basicConfig(level=logging.DEBUG, format=debug_log_format)
        logging.getLogger(
            'selenium.webdriver.remote.remote_connection').setLevel(
                logging.INFO)
    else:
        logging.basicConfig(level=logging.INFO, format=log_format)

    if not config_file:
        config_file = DEFAULT_CONFIG_PATH
    if not os.path.exists(config_file):
        _populate_config(config_file)
        raise click.exceptions.BadParameter(
            "Config file {config_file!r} did not exist. "
            "An example config has been written to {config_file!r}, "
            "please fill it in then rerun.".format(config_file=config_file))

    with open(config_file, mode='r', encoding='utf8') as config_fh:
        config = yaml.safe_load(config_fh)
    shotbot = Shotbot(**config)
    shotbot.run_forever()


if __name__ == '__main__':
    main()  # pylint:disable=no-value-for-parameter
