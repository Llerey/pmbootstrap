# Copyright 2022 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import shutil

import pmb.config
import pmb.chroot
import pmb.chroot.binfmt
import pmb.helpers.run
import pmb.helpers.run_core


def executables_absolute_path():
    """
    Get the absolute paths to the sh and chroot executables.
    """
    ret = {}
    for binary in ["sh", "chroot"]:
        path = shutil.which(binary, path=pmb.config.chroot_host_path)
        if not path:
            raise RuntimeError(f"Could not find the '{binary}'"
                               " executable. Make sure that it is in"
                               " your current user's PATH.")
        ret[binary] = path
    return ret


def root(args, cmd, suffix="native", working_dir="/", output="log",
         output_return=False, check=None, env={}, auto_init=True,
         disable_timeout=False):
    """
    Run a command inside a chroot as root.

    :param env: dict of environment variables to be passed to the command, e.g.
                {"JOBS": "5"}
    :param auto_init: automatically initialize the chroot

    See pmb.helpers.run_core.core() for a detailed description of all other
    arguments and the return value.
    """
    # Initialize chroot
    chroot = f"{args.work}/chroot_{suffix}"
    if not auto_init and not os.path.islink(f"{chroot}/bin/sh"):
        raise RuntimeError(f"Chroot does not exist: {chroot}")
    if auto_init:
        pmb.chroot.init(args, suffix)

    # Readable log message (without all the escaping)
    msg = f"({suffix}) % "
    for key, value in env.items():
        msg += f"{key}={value} "
    if working_dir != "/":
        msg += f"cd {working_dir}; "
    msg += " ".join(cmd)

    # Merge env with defaults into env_all
    env_all = {"CHARSET": "UTF-8",
               "LANG": "UTF-8",
               "HISTFILE": "~/.ash_history",
               "HOME": "/root",
               "PATH": pmb.config.chroot_path,
               "SHELL": "/bin/ash",
               "TERM": "xterm"}
    for key, value in env.items():
        env_all[key] = value

    # Build the command in steps and run it, e.g.:
    # cmd: ["echo", "test"]
    # cmd_chroot: ["/sbin/chroot", "/..._native", "/bin/sh", "-c", "echo test"]
    # cmd_sudo: ["sudo", "env", "-i", "sh", "-c", "PATH=... /sbin/chroot ..."]
    executables = executables_absolute_path()
    cmd_chroot = [executables["chroot"], chroot, "/bin/sh", "-c",
                  pmb.helpers.run.flat_cmd(cmd, working_dir)]

    if "sudo_askpass_program" in args:
        # sudo is required here, unfortunately, so it's hardcoded
        cmd_sudo = ["env", f"SUDO_ASKPASS={args.sudo_askpass_program}",
                    "sudo", "--askpass", "env", "-i", executables["sh"], "-c",
                    pmb.helpers.run.flat_cmd(cmd_chroot, env=env_all)]
    else:
        cmd_sudo = [pmb.config.sudo, "env", "-i", executables["sh"], "-c",
                    pmb.helpers.run.flat_cmd(cmd_chroot, env=env_all)]

    return pmb.helpers.run_core.core(args, msg, cmd_sudo, None, output,
                                     output_return, check, True,
                                     disable_timeout)
