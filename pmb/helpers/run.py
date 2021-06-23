# Copyright 2022 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import shlex
import pmb.helpers.run_core


def flat_cmd(cmd, working_dir=None, env={}):
    """
    Convert a shell command passed as list into a flat shell string with
    proper escaping.

    :param cmd: command as list, e.g. ["echo", "string with spaces"]
    :param working_dir: when set, prepend "cd ...;" to execute the command
                        in the given working directory
    :param env: dict of environment variables to be passed to the command, e.g.
                {"JOBS": "5"}
    :returns: the flat string, e.g.
              echo 'string with spaces'
              cd /home/pmos;echo 'string with spaces'
    """
    # Merge env and cmd into escaped list
    escaped = []
    for key, value in env.items():
        escaped.append(key + "=" + shlex.quote(value))
    for i in range(len(cmd)):
        escaped.append(shlex.quote(cmd[i]))

    # Prepend working dir
    ret = " ".join(escaped)
    if working_dir:
        ret = "cd " + shlex.quote(working_dir) + ";" + ret

    return ret


def user(args, cmd, working_dir=None, output="log", output_return=False,
         check=None, env={}, sudo=False):
    """
    Run a command on the host system as user.

    :param env: dict of environment variables to be passed to the command, e.g.
                {"JOBS": "5"}

    See pmb.helpers.run_core.core() for a detailed description of all other
    arguments and the return value.
    """
    # Readable log message (without all the escaping)
    msg = "% "
    for key, value in env.items():
        msg += key + "=" + value + " "
    if working_dir:
        msg += "cd " + working_dir + "; "
    msg += " ".join(cmd)

    # Add environment variables and run
    if env:
        cmd = ["sh", "-c", flat_cmd(cmd, env=env)]
    return pmb.helpers.run_core.core(args, msg, cmd, working_dir, output,
                                     output_return, check, sudo)


def root(args, cmd, working_dir=None, output="log", output_return=False,
         check=None, env={}):
    """
    Run a command on the host system as root, with sudo or doas.

    :param env: dict of environment variables to be passed to the command, e.g.
                {"JOBS": "5"}

    See pmb.helpers.run_core.core() for a detailed description of all other
    arguments and the return value.
    """
    if env:
        cmd = ["sh", "-c", flat_cmd(cmd, env=env)]

    # fom `man sudo`:
    # If the -A (askpass) option
    #  is specified, a (possibly graphical) helper program is executed to
    #  read the user's password and output the password to the standard output.
    #  If the SUDO_ASKPASS environment variable is set, it specifies the path
    #  to the helper program.
    if "sudo_askpass_program" in args:
        # sudo is required here, unfortunately, so it's hardcoded
        cmd = ["env", f"SUDO_ASKPASS={args.sudo_askpass_program}",
               "sudo", "--askpass"] + cmd
    else:
        cmd = [pmb.config.sudo] + cmd

    return user(args, cmd, working_dir, output, output_return, check, env,
                True)
