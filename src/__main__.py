import argparse
import logging
import os

from src.config import Config
from src.daemon import RecorderDaemon


def main():
    parser = argparse.ArgumentParser(description="Rekordbox Auto-Recorder")
    parser.add_argument(
        "-c", "--config",
        default=os.path.expanduser("~/.config/rb-recorder/config.toml"),
        help="Path to config file",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    if os.path.exists(args.config):
        config = Config.from_file(args.config)
    else:
        config = Config()

    daemon = RecorderDaemon(config)
    daemon.run()


if __name__ == "__main__":
    main()
