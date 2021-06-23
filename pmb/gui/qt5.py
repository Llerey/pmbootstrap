# Copyright 2021 Alexey Minnekhanov
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import os
import sys

from PyQt5.QtCore import PYQT_VERSION, QObject, pyqtSignal, pyqtSlot,\
    pyqtProperty, QStringListModel
from PyQt5.QtGui import QIcon
from PyQt5.QtQml import QQmlApplicationEngine, QQmlListProperty,\
    qmlRegisterType
from PyQt5.QtQuick import QQuickWindow
from PyQt5.QtWidgets import QApplication

# since 5.11 PyQt uses internal sip module
if PYQT_VERSION >= 0x050B00:  # 5.11.0 == 0x5, 0xB, 0x00
    from PyQt5 import sip
else:
    import sip

import pmb.gui.pmb_api

_args = None


class PmbDevices(QObject):
    vendors_changed = pyqtSignal()
    channels_changed = pyqtSignal()
    current_channel_changed = pyqtSignal()
    devices_changed = pyqtSignal()
    uis_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._vendors = sorted(list(pmb.gui.pmb_api.list_vendors(_args)))
        self._channels = pmb.gui.pmb_api.get_channels_config(_args)
        self._channel_names = []
        for ch in self._channels:
            self._channel_names.append(ch)
        self._selected_vendor = None
        if len(self._vendors) > 0:
            self._selected_vendor = 0
        self._avail_codenames = []
        self._selected_codename = None

    @pyqtProperty(list, notify=vendors_changed)
    def vendors(self) -> list[str]:
        return self._vendors

    @pyqtProperty(list, notify=channels_changed)
    def channels(self) -> list[str]:
        ret = [ch + " " + self._channels[ch]['description'] for ch in self._channels.keys()]
        return ret

    @pyqtProperty(int, notify=current_channel_changed)
    def current_channel(self) -> int:
        cname = pmb.gui.pmb_api.get_current_channel(_args)
        if cname in self._channel_names:
            return self._channel_names.index(cname)
        return -1

    @pyqtSlot(int)
    def set_channel(self, idx: int) -> None:
        pmb.gui.pmb_api.switch_to_channel(_args, self._channel_names[idx])
        # reload vendors list
        self._vendors = sorted(list(pmb.gui.pmb_api.list_vendors(_args)))
        self.vendors_changed.emit()
        self._selected_vendor = 0
        self.devices_changed.emit()
        self._selected_codename = 0
        self.uis_changed.emit()

    @pyqtProperty(list, notify=devices_changed)
    def vendor_devices(self) -> list[str]:
        if self._selected_vendor is None:
            return list()
        self._avail_codenames = pmb.gui.pmb_api.list_vendor_codenames(
            _args, self._vendors[self._selected_vendor])
        return self._avail_codenames

    @pyqtSlot(int)
    def select_vendor(self, vidx: int) -> None:
        self._selected_vendor = vidx
        self.devices_changed.emit()
        self._selected_codename = None
        self.uis_changed.emit()

    @pyqtSlot(int)
    def select_device(self, idx: int) -> None:
        self._selected_codename = self._avail_codenames[idx]
        self.uis_changed.emit()

    @pyqtProperty(list, notify=uis_changed)
    def uis_list(self) -> list[str]:
        ret = []
        if self._selected_codename:
            uis = pmb.gui.pmb_api.list_uis(_args, self._selected_codename)
        else:
            uis = pmb.gui.pmb_api.list_uis(_args, "qemu-amd64")
        for tup in uis:
            ret.append(f"{tup[0]}  ({tup[1]})")
        return ret


def configure_sudo_askpass_program(args):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Launch our own GUI askpass handler by default
    askpass_program = f"{script_dir}/askpass.py"
    if "SSH_ASKPASS" in os.environ:
        askpass_program = os.environ["SSH_ASKPASS"]
        logging.debug(f"autodetected SSH_ASKPASS program: {askpass_program}")
    _args.sudo_askpass_program = askpass_program


def start(args):
    global _args
    _args = args

    configure_sudo_askpass_program(args)

    # We will need this, directory which contains this script
    script_dir = os.path.dirname(os.path.abspath(__file__))

    sip.setdestroyonexit(False)

    app = QApplication(sys.argv)
    engine = QQmlApplicationEngine()

    qmlRegisterType(PmbDevices, 'Pmb', 1, 0, 'Devices')

    engine.load(f"{script_dir}/qml/main.qml")
    if len(engine.rootObjects()) < 1:
        logging.error("Failed to load QML!")
        return 1

    root_objects = engine.rootObjects()  # type: list[QObject]
    # QML's ApplicationWindow instantiates QQuickWindow
    app_window = root_objects[0]  # type: QQuickWindow
    app_window.setIcon(QIcon(f"{script_dir}/img/pmos-logo.svg"))

    engine.quit.connect(app.quit)
    retval = app.exec_()
    logging.debug(f"Qt5: exiting with code {retval}")
    return retval
