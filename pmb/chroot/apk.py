# Copyright 2022 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import logging
import shlex

import pmb.chroot
import pmb.config
import pmb.helpers.apk
import pmb.helpers.pmaports
import pmb.parse.apkindex
import pmb.parse.arch
import pmb.parse.depends
import pmb.parse.version


def update_repository_list(args, suffix="native", check=False):
    """
    Update /etc/apk/repositories, if it is outdated (when the user changed the
    --mirror-alpine or --mirror-pmOS parameters).

    :param check: This function calls it self after updating the
                  /etc/apk/repositories file, to check if it was successful.
                  Only for this purpose, the "check" parameter should be set to
                  True.
    """
    # Skip if we already did this
    if suffix in pmb.helpers.other.cache["apk_repository_list_updated"]:
        return

    # Read old entries or create folder structure
    path = f"{args.work}/chroot_{suffix}/etc/apk/repositories"
    lines_old = []
    if os.path.exists(path):
        # Read all old lines
        lines_old = []
        with open(path) as handle:
            for line in handle:
                lines_old.append(line[:-1])
    else:
        pmb.helpers.run.root(args, ["mkdir", "-p", os.path.dirname(path)])

    # Up to date: Save cache, return
    lines_new = pmb.helpers.repo.urls(args)
    if lines_old == lines_new:
        pmb.helpers.other.cache["apk_repository_list_updated"].append(suffix)
        return

    # Check phase: raise error when still outdated
    if check:
        raise RuntimeError(f"Failed to update: {path}")

    # Update the file
    logging.debug(f"({suffix}) update /etc/apk/repositories")
    if os.path.exists(path):
        pmb.helpers.run.root(args, ["rm", path])
    for line in lines_new:
        pmb.helpers.run.root(args, ["sh", "-c", "echo "
                                    f"{shlex.quote(line)} >> {path}"])
    update_repository_list(args, suffix, True)


def check_min_version(args, suffix="native"):
    """
    Check the minimum apk version, before running it the first time in the
    current session (lifetime of one pmbootstrap call).
    """

    # Skip if we already did this
    if suffix in pmb.helpers.other.cache["apk_min_version_checked"]:
        return

    # Skip if apk is not installed yet
    if not os.path.exists(f"{args.work}/chroot_{suffix}/sbin/apk"):
        logging.debug(f"NOTE: Skipped apk version check for chroot '{suffix}'"
                      ", because it is not installed yet!")
        return

    # Compare
    version_installed = installed(args, suffix)["apk-tools"]["version"]
    pmb.helpers.apk.check_outdated(
        args, version_installed,
        "Delete your http cache and zap all chroots, then try again:"
        " 'pmbootstrap zap -hc'")

    # Mark this suffix as checked
    pmb.helpers.other.cache["apk_min_version_checked"].append(suffix)


def install_is_necessary(args, build, arch, package, packages_installed):
    """
    This function optionally builds an out of date package, and checks if the
    version installed inside a chroot is up to date.
    :param build: Set to true to build the package, if the binary packages are
                  out of date, and it is in the aports folder.
    :param packages_installed: Return value from installed().
    :returns: True if the package needs to be installed/updated,
              False otherwise.
    """
    # For packages to be removed we can do the test immediately
    if package.startswith("!"):
        return package[1:] in packages_installed

    # User may have disabled buiding packages during "pmbootstrap install"
    build_disabled = False
    if args.action == "install" and not args.build_pkgs_on_install:
        build_disabled = True

    # Build package
    if build and not build_disabled:
        pmb.build.package(args, package, arch)

    # No further checks when not installed
    if package not in packages_installed:
        return True

    # Make sure that we really have a binary package
    data_repo = pmb.parse.apkindex.package(args, package, arch, False)
    if not data_repo:
        if build_disabled:
            raise RuntimeError(f"{package}: no binary package found for"
                               f" {arch}, and compiling packages during"
                               " 'pmbootstrap install' has been disabled."
                               " Consider changing this option in"
                               " 'pmbootstrap init'.")
        logging.warning("WARNING: Internal error in pmbootstrap,"
                        f" package '{package}' for {arch}"
                        " has not been built yet, but it should have"
                        " been. Rebuilding it with force. Please "
                        " report this, if there is no ticket about this"
                        " yet!")
        pmb.build.package(args, package, arch, True)
        return install_is_necessary(args, build, arch, package,
                                    packages_installed)

    # Compare the installed version vs. the version in the repos
    data_installed = packages_installed[package]
    compare = pmb.parse.version.compare(data_installed["version"],
                                        data_repo["version"])
    # a) Installed newer (should not happen normally)
    if compare == 1:
        logging.info(f"WARNING: {arch} package '{package}'"
                     f" installed version {data_installed['version']}"
                     " is newer, than the version in the repositories:"
                     f" {data_repo['version']}"
                     " See also: <https://postmarketos.org/warning-repo>")
        return False

    # b) Repo newer
    elif compare == -1:
        return True

    # c) Same version, look at last modified
    elif compare == 0:
        time_installed = float(data_installed["timestamp"])
        time_repo = float(data_repo["timestamp"])
        return time_repo > time_installed


def replace_aports_packages_with_path(args, packages, suffix, arch):
    """
    apk will only re-install packages with the same pkgname,
    pkgver and pkgrel, when you give it the absolute path to the package.
    This function replaces all packages that were built locally,
    with the absolute path to the package.
    """
    ret = []
    for package in packages:
        aport = pmb.helpers.pmaports.find(args, package, False)
        if aport:
            data_repo = pmb.parse.apkindex.package(args, package, arch, False)
            if not data_repo:
                raise RuntimeError(f"{package}: could not find binary"
                                   " package, although it should exist for"
                                   " sure at this point in the code."
                                   " Probably an APKBUILD subpackage parsing"
                                   " bug. Related: https://gitlab.com/"
                                   "postmarketOS/build.postmarketos.org/"
                                   "issues/61")
            apk_path = (f"/mnt/pmbootstrap-packages/{arch}/"
                        f"{package}-{data_repo['version']}.apk")
            if os.path.exists(f"{args.work}/chroot_{suffix}{apk_path}"):
                package = apk_path
        ret.append(package)
    return ret


def install(args, packages, suffix="native", build=True):
    """
    :param build: automatically build the package, when it does not exist yet
                  or needs to be updated, and it is inside the pm-aports
                  folder. Checking this is expensive - if you know that all
                  packages are provides by upstream repos, set this to False!
    """
    # Initialize chroot
    check_min_version(args, suffix)
    pmb.chroot.init(args, suffix)

    # Add depends to packages
    arch = pmb.parse.arch.from_chroot_suffix(args, suffix)
    packages_with_depends = pmb.parse.depends.recurse(args, packages, suffix)

    # Filter outdated packages (build them if required)
    packages_installed = installed(args, suffix)
    packages_toadd = []
    packages_todel = []
    for package in packages_with_depends:
        if not install_is_necessary(
                args, build, arch, package, packages_installed):
            continue
        if package.startswith("!"):
            packages_todel.append(package.lstrip("!"))
        else:
            packages_toadd.append(package)
    if not len(packages_toadd) and not len(packages_todel):
        return

    # Sanitize packages: don't allow '--allow-untrusted' and other options
    # to be passed to apk!
    for package in packages_toadd + packages_todel:
        if package.startswith("-"):
            raise ValueError(f"Invalid package name: {package}")

    # Readable install message without dependencies
    message = f"({suffix}) install"
    for pkgname in packages:
        if pkgname not in packages_installed:
            message += f" {pkgname}"
    logging.info(message)

    # Local packages: Using the path instead of pkgname makes apk update
    # packages of the same version if the build date is different
    packages_toadd = replace_aports_packages_with_path(args, packages_toadd,
                                                       suffix, arch)

    # Split off conflicts
    packages_without_conflicts = list(
        filter(lambda p: not p.startswith("!"), packages))

    # Use a virtual package to mark only the explicitly requested packages as
    # explicitly installed, not their dependencies or specific paths (#1212)
    commands = [["add"] + packages_without_conflicts]
    if len(packages_toadd) and packages_without_conflicts != packages_toadd:
        commands = [["add", "-u", "--virtual", ".pmbootstrap"] +
                    packages_toadd,
                    ["add"] + packages_without_conflicts,
                    ["del", ".pmbootstrap"]]
    if len(packages_todel):
        commands.append(["del"] + packages_todel)
    for (i, command) in enumerate(commands):
        if args.offline:
            command = ["--no-network"] + command
        if i == 0:
            pmb.helpers.apk.apk_with_progress(args, ["apk"] + command,
                                              chroot=True, suffix=suffix)
        else:
            # Virtual package related commands don't actually install or remove
            # packages, but only mark the right ones as explicitly installed.
            # They finish up almost instantly, so don't display a progress bar.
            pmb.chroot.root(args, ["apk", "--no-progress"] + command,
                            suffix=suffix)


def installed(args, suffix="native"):
    """
    Read the list of installed packages (which has almost the same format, as
    an APKINDEX, but with more keys).

    :returns: a dictionary with the following structure:
              { "postmarketos-mkinitfs":
                {
                  "pkgname": "postmarketos-mkinitfs"
                  "version": "0.0.4-r10",
                  "depends": ["busybox-extras", "lddtree", ...],
                  "provides": ["mkinitfs=0.0.1"]
                }, ...
              }
    """
    path = f"{args.work}/chroot_{suffix}/lib/apk/db/installed"
    return pmb.parse.apkindex.parse(path, False)
