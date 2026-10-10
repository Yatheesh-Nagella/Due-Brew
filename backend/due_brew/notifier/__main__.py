"""Notifier worker.

python -m due_brew.notifier          # loop forever (the container's command)
python -m due_brew.notifier --once   # run a single tick and exit
"""

import argparse
import logging
import threading

from due_brew.notifier import install_signal_handlers, run_forever, tick


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m due_brew.notifier")
    parser.add_argument("--once", action="store_true", help="run a single tick and exit")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [notifier] %(message)s")
    if args.once:
        tick()
        return

    stop = threading.Event()
    install_signal_handlers(stop)
    run_forever(stop)


if __name__ == "__main__":
    main()
