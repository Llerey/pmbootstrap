# Copyright 2019 Martijn Braam
# Copyright 2021 Alexey Minnekhanov
# SPDX-License-Identifier: GPL-3.0-or-later

# This file serves as some layer of abstraction on top of raw pmbootstrap API.
# Every GUI layer interaction with pmbootstrap should go through this file.

import logging

# typing is available since python 3.5
from typing import List, Optional, Set

import pmb.chroot
import pmb.config
import pmb.config.pmaports
import pmb.helpers.devices
import pmb.helpers.git
import pmb.helpers.ui
import pmb.parse._apkbuild


class DeviceInfo:
    def __init__(self):
        # copy deviceinfo_attributes from pmb
        for attr_name in pmb.config.deviceinfo_attributes:
            setattr(self, attr_name, None)

        # properties taken from pmb/config/__init__.py
        # general
        self.name = None
        self.manufacturer = None
        self.codename = None
        self.year = None
        self.dtb = None
        self.modules_initfs = []
        self.arch = None

        # device
        self.chassis = None
        self.keyboard = False
        self.external_storage = False
        self.screen_width = None
        self.screen_height = None
        self.dev_touchscreen = None
        self.dev_touchscreen_calibration = None
        self.append_dtb = None

        # bootloader
        self.flash_method = "none"
        self.boot_filesystem = None

        # flash
        self.flash_heimdall_partition_kernel = None
        self.flash_heimdall_partition_initfs = None
        self.flash_heimdall_partition_system = None
        self.flash_heimdall_partition_vbmeta = None
        self.flash_fastboot_partition_kernel = None
        self.flash_fastboot_partition_system = None
        self.flash_fastboot_partition_vbmeta = None
        self.generate_legacy_uboot_initfs = None
        self.kernel_cmdline = None
        self.generate_bootimg = None
        self.bootimg_qcdt = False
        self.bootimg_mtk_mkimage = False
        self.bootimg_dtb_second = False
        self.flash_offset_base = None
        self.flash_offset_kernel = None
        self.flash_offset_ramdisk = None
        self.flash_offset_second = None
        self.flash_offset_tags = None
        self.flash_pagesize = None
        self.flash_fastboot_max_size = None
        self.flash_sparse = False
        self.rootfs_image_sector_size = None
        self.sd_embed_firmware = None
        self.sd_embed_firmware_step_size = None
        self.partition_blacklist = []
        self.boot_part_start = None
        self.root_filesystem = None
        self.flash_kernel_on_update = None

        # weston (some legacy?)
        self.weston_pixman_type = None

        # Keymaps
        self.keymaps = []

        # extra properties that are used by some devices
        self.getty = None
        self.no_framebuffer = False
        self.framebuffer_landscape = False
        self.usb_rndis_function = None
        self.usb_idVendor = None
        self.usb_idProduct = None
        self.mesa_driver = None
        self.dev_internal_storage = None
        self.dev_internal_storage_repartition = None
        self.bootimg_blobpack = None
        self.bootimg_pxa = None
        self.bootimg_append_seandroidenforce = None
        self.disable_dhcpd = False
        self.swap_size_recommended = None
        self.initfs_compression = None

    def __repr__(self):
        return f'<DeviceInfo {self.codename}>'

    def fill_from_pmb_deviceinfo(self, dev: dict) -> None:
        for key in dev:
            if not hasattr(self, key):
                logging.debug(f"{dev['codename']}: unknown deviceinfo key: "
                              f"{key}")
            setattr(self, key, dev[key])

        # split some strings into lists
        self.modules_initfs = self.modules_initfs.split() \
            if type(self.modules_initfs) == str else []


def list_vendors(args) -> Set[str]:
    return pmb.helpers.devices.list_vendors(args)


def list_vendor_codenames(args, vendor: str,
                          unmaintained: Optional[bool] = None) -> List[str]:
    return pmb.helpers.devices.list_codenames(args, vendor, unmaintained)


def list_device_kernels(args, codename: str) -> dict:
    """
    Get device kernel subpackages
    :param args: global program state
    :param codename: device codename (for example qemu-amd64)
    :return: dict('kernel_subpkgname' => 'description', ...)
    """
    return pmb.parse._apkbuild.kernels(args, codename)


def list_deviceinfos(args) -> List[DeviceInfo]:
    """ Get a list of all devices with the information contained in the
    deviceinfo

    :returns: list of DeviceInfo objects for all known devices
    :rtype: List[DeviceInfo]
    """
    raw = pmb.helpers.devices.list_deviceinfos(args)
    result = []
    for device in raw:
        row = DeviceInfo()
        row.fill_from_pmb_deviceinfo(raw[device])
        result.append(row)
    return list(sorted(result, key=lambda k: k.codename))


def get_channels_config(args) -> dict:
    channels_cfg = pmb.helpers.git.parse_channels_cfg(args)
    return channels_cfg["channels"]


def switch_to_channel(args, channel: str) -> None:
    # always switch to safe device before switching branch
    cfg = pmb.config.load(args)
    cfg['pmbootstrap']['device'] = 'qemu-amd64'
    pmb.config.save(args, cfg)
    # zap!
    pmb.chroot.zap(args, confirm=False)
    # do the switch
    pmb.config.pmaports.switch_to_channel_branch(args, channel)


def get_current_channel(args) -> str:
    repo_path = pmb.helpers.git.get_path(args, "pmaports")
    # Get branch name (if on branch) or current commit
    ref = pmb.helpers.git.rev_parse(args, repo_path,
                                    extra_args=["--abbrev-ref"])
    if ref == "HEAD":
        ref = pmb.helpers.git.rev_parse(args, repo_path)[0:8]
    if ref == "master":
        return "edge"
    return ref


def list_uis(args, codename: str) -> list[tuple[str, str]]:
    info = pmb.parse.deviceinfo(args, codename)
    ui_list = pmb.helpers.ui.list(args, info["arch"])
    return ui_list
