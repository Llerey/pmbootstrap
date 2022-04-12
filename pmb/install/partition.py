# Copyright 2022 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import os
import time
import pmb.chroot
import pmb.config
import pmb.install.losetup


def partitions_mount(args, layout, sdcard):
    """
    Mount blockdevices of partitions inside native chroot
    :param layout: partition layout from get_partition_layout()
    :param sdcard: path to sdcard device (e.g. /dev/mmcblk0) or None
    """
    prefix = sdcard
    if not sdcard:
        img_path = "/home/pmos/rootfs/" + args.device + ".img"
        prefix = pmb.install.losetup.device_by_back_file(args, img_path)

    tries = 20

    # Devices ending with a number have a 'p' before the partition number:
    # /dev/sda1 has no "p", but /dev/mmcblk0p1 has
    partition_prefix = prefix
    if str.isdigit(prefix[-1:]):
        partition_prefix = f"{prefix}p"

    found = False
    for i in range(tries):
        if os.path.exists(f"{partition_prefix}1"):
            found = True
            break
        logging.debug(f"NOTE: ({i + 1}/{tries}) failed to find the install "
                      "partition. Retrying...")
        time.sleep(0.1)

    if not found:
        raise RuntimeError(f"Unable to find the first partition of {prefix}, "
                           f"expected it to be at {partition_prefix}1!")

    partitions = [layout["boot"], layout["root"]]

    if layout["kernel"]:
        partitions += [layout["kernel"]]

    for i in partitions:
        source = f"{partition_prefix}{i}"
        target = args.work + "/chroot_native/dev/installp" + str(i)
        pmb.helpers.mount.bind_file(args, source, target)


def partition(args, layout, size_boot, size_reserve):
    """
    Partition /dev/install and create /dev/install{p1,p2,p3}:
    * /dev/installp1: boot
    * /dev/installp2: root (or reserved space)
    * /dev/installp3: (root, if reserved space > 0)

    When adjusting this function, make sure to also adjust
    ondev-prepare-internal-storage.sh in postmarketos-ondev.git!

    :param layout: partition layout from get_partition_layout()
    :param size_boot: size of the boot partition in MiB
    :param size_reserve: empty partition between root and boot in MiB (pma#463)
    """
    # Convert to MB and print info
    mb_boot = f"{round(size_boot)}M"
    mb_reserved = f"{round(size_reserve)}M"
    mb_root_start = f"{round(size_boot) + round(size_reserve)}M"
    logging.info(f"(native) partition /dev/install (boot: {mb_boot},"
                 f" reserved: {mb_reserved}, root: the rest)")

    filesystem = args.deviceinfo["boot_filesystem"] or "ext2"

    # Actual partitioning with 'parted'. Using check=False, because parted
    # sometimes "fails to inform the kernel". In case it really failed with
    # partitioning, the follow-up mounting/formatting will not work, so it
    # will stop there (see #463).
    boot_part_start = args.deviceinfo["boot_part_start"] or "2048"

    partition_type = args.deviceinfo["partition_type"] or "msdos"

    commands = [
        ["mktable", partition_type],
        ["mkpart", "primary", filesystem, boot_part_start + 's', mb_boot],
    ]

    if size_reserve:
        mb_reserved_end = f"{round(size_reserve + size_boot)}M"
        commands += [["mkpart", "primary", mb_boot, mb_reserved_end]]

    commands += [
        ["mkpart", "primary", mb_root_start, "100%"],
        ["set", str(layout["boot"]), "boot", "on"]
    ]

    for command in commands:
        pmb.chroot.root(args, ["parted", "-s", "/dev/install"] +
                        command, check=False)


def partition_cgpt(args, layout, size_boot, size_reserve):
    """
    This function does similar functionality to partition(), but this
    one is for ChromeOS devices which use special GPT.

    :param layout: partition layout from get_partition_layout()
    :param size_boot: size of the boot partition in MiB
    :param size_reserve: empty partition between root and boot in MiB (pma#463)
    """

    pmb.chroot.root(args, ["apk", "add", "cgpt"])

    cgpt = {
        'kpart_start': args.deviceinfo["cgpt_kpart_start"],
        'kpart_size': args.deviceinfo["cgpt_kpart_size"],
    }

    # Convert to MB and print info
    mb_boot = f"{round(size_boot)}M"
    mb_reserved = f"{round(size_reserve)}M"
    logging.info(f"(native) partition /dev/install (boot: {mb_boot},"
                 f" reserved: {mb_reserved}, root: the rest)")

    boot_part_start = str(int(cgpt['kpart_start']) + int(cgpt['kpart_size']))

    # Convert to sectors
    s_boot = str(int(size_boot * 1024 * 1024 / 512))
    s_root_start = str(int(
        int(boot_part_start) + int(s_boot) + size_reserve * 1024 * 1024 / 512
    ))

    commands = [
        ["parted", "-s", "/dev/install", "mktable", "gpt"],
        ["cgpt", "create", "/dev/install"],
        [
            "cgpt", "add",
            # pmOS_boot is second partition, the first will be ChromeOS kernel
            # partition
            "-i", str(layout["boot"]),  # Partition number
            "-t", "data",
            "-b", boot_part_start,
            "-s", s_boot,
            "-l", "pmOS_boot",
            "/dev/install"
        ],
        # Mark this partition as bootable for u-boot
        [
            "parted",
            "-s", "/dev/install",
            "set", str(layout["boot"]),
            "boot", "on"
        ],
        # For some reason cgpt switches all flags to 0 after marking
        # any partition as bootable, so create ChromeOS kernel partition
        # only after pmOS_boot is created and marked as bootable
        [
            "cgpt", "add",
            "-i", str(layout["kernel"]),
            "-t", "kernel",
            "-b", cgpt['kpart_start'],
            "-s", cgpt['kpart_size'],
            "-l", "Kernel",
            "-S", "1",  # Successful flag
            "-T", "5",  # Tries flag
            "-P", "10",  # Priority flag
            "/dev/install"
        ],
    ]

    dev_size = pmb.chroot.root(
        args, ["blockdev", "--getsz", "/dev/install"], output_return=True)
    root_size = str(int(dev_size) - int(s_root_start) - 1024)

    commands += [
        [
            "cgpt", "add",
            "-i", str(layout["root"]),
            "-t", "data",
            "-b", s_root_start,
            "-s", root_size,
            "-l", "pmOS_root",
            "/dev/install"
        ],
        ["partx", "-a", "/dev/install"]
    ]

    for command in commands:
        pmb.chroot.root(args, command, check=False)
