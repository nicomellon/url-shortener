"""One-off admin tasks, run in the same environment as the app.

See https://12factor.net/admin-processes. Usage:

    my-project-admin init-db
"""

import argparse
import logging

from sqlalchemy import create_engine

from my_project import bootstrap, config

logger = logging.getLogger(__name__)


def init_db():
    logger.info("Creating database tables")
    engine = create_engine(config.get_settings().database_url)
    bootstrap.create_tables(engine)


COMMANDS = {
    "init-db": init_db,
}


def main():
    parser = argparse.ArgumentParser(prog="my-project-admin")
    parser.add_argument("command", choices=COMMANDS)
    args = parser.parse_args()
    config.configure_logging()
    COMMANDS[args.command]()
