# Copyright 2022 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
# PYTHON_ARGCOMPLETE_OK
import sys
import logging
import os
import traceback

from . import config
from . import parse
from .config import init as config_init
from .helpers import frontend
from .helpers import logging as pmb_logging
from .helpers import mount
from .helpers import other


def main():
    # Wrap everything to display nice error messages
    args = None
    try:
        # Parse arguments, set up logging
        args = parse.arguments()
        os.umask(0o22)

        # Sanity checks
        other.check_grsec()
        if not args.as_root and os.geteuid() == 0:
            raise RuntimeError("Do not run pmbootstrap as root!")

        # Initialize or require config
        if args.action == "init":
            return config_init.frontend(args)
        elif args.action == "gui":
            # "pmbootstrap gui" also does not require initialized config
            return frontend.gui(args)
        elif not os.path.exists(args.config):
            raise RuntimeError("Please specify a config file, or run"
                               " 'pmbootstrap init' to generate one.")
        elif not os.path.exists(args.work):
            raise RuntimeError("Work path not found, please run 'pmbootstrap"
                               " init' to create it.")

        other.check_old_devices(args)

        # Migrate work folder if necessary
        if args.action not in ["shutdown", "zap", "log"]:
            other.migrate_work_folder(args)

        # Run the function with the action's name (in pmb/helpers/frontend.py)
        if args.action:
            getattr(frontend, args.action)(args)
        else:
            logging.info("Run pmbootstrap -h for usage information.")

        # Still active notice
        if mount.ismount(args.work + "/chroot_native/dev"):
            logging.info("NOTE: chroot is still active (use 'pmbootstrap"
                         " shutdown' as necessary)")
        logging.info("DONE!")

    except Exception as e:
        # Dump log to stdout when args (and therefore logging) init failed
        if not args:
            logging.getLogger().setLevel(logging.DEBUG)

        logging.info("ERROR: " + str(e))
        logging.info("See also: <https://postmarketos.org/troubleshooting>")
        logging.debug(traceback.format_exc())

        # Hints about the log file (print to stdout only)
        log_hint = "Run 'pmbootstrap log' for details."
        if not args or not os.path.exists(args.log):
            log_hint += (" Alternatively you can use '--details-to-stdout' to"
                         " get more output, e.g. 'pmbootstrap"
                         " --details-to-stdout init'.")
        print(log_hint)
        return 1


if __name__ == "__main__":
    sys.exit(main())
