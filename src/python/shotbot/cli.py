"""Command line interface to Shotbot."""
import logging
import os

import click
from ruamel import yaml

from .shotbot import SHOTBOT_VERSION, Shotbot

__all__ = ('DEFAULT_CONFIG_PATH', 'main')

DEFAULT_CONFIG_PATH = 'shotbot.yaml'


@click.command()
@click.help_option('--help', '-h')
@click.version_option(str(SHOTBOT_VERSION))
@click.option('--dry-run', '-n', is_flag=True, help="don't post replies")
@click.option('--config-file',
              '-c',
              type=str,
              default=None,
              help='shotbot config file',
              metavar='shotbot.yaml')
@click.option('--verbose', '-v', is_flag=True, help='enable verbose logging')
def main(config_file, dry_run, verbose):  # pylint:disable=W9015,W9016
    """Reddit bot that posts screenshots of submissions."""
    log_format = "%(asctime)s %(levelname)-5s %(name)s: %(message)s"
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
        raise click.exceptions.BadParameter(
            "Config file {config_file!r} does not exist. "
            "See shotbot-dist.yaml for an example config.".format(
                config_file=config_file))

    with open(config_file, mode='r', encoding='utf8') as config_fh:
        config = yaml.safe_load(config_fh)
    shotbot = Shotbot(dry_run=dry_run, **config)
    shotbot.run_forever()


if __name__ == '__main__':
    main()  # pylint:disable=no-value-for-parameter
