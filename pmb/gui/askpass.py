#!/usr/bin/env python3
# Copyright 2021 Alexey Minnekhanov
# SPDX-License-Identifier: GPL-3.0-or-later

# man sudo.conf: askpass:
# The fully qualified path to a helper program used to read the user's
# password when no terminal is available.  This may be the case when sudo
# is executed from a graphical (as opposed to text-based) application.
# The program specified by askpass should display the argument passed to
# it as the prompt and write the user's password to the standard output.

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


PROMPT = ""
PASSWORD = ""


class Askpass(QObject):
    """
    This class is instantiated in QML like:

        import Pmb 1.0 as Pmb

        Pmb.Askpass {
            id: askpass
        }

    Then prompt property is used inother QML components like

        text: asskpass.prompt
        askpass.set_pass('...')

    """
    prompt_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

    @pyqtProperty(str, notify=prompt_changed)
    def prompt(self) -> str:
        global PROMPT
        return PROMPT

    @pyqtSlot(str)
    def set_pass(self, p: str) -> None:
        global PASSWORD
        PASSWORD = p


def sudo_askpass(prompt: str):
    global PROMPT, PASSWORD
    PROMPT = prompt

    script_dir = os.path.dirname(os.path.abspath(__file__))

    sip.setdestroyonexit(False)

    app = QApplication(sys.argv)

    engine = QQmlApplicationEngine()

    qmlRegisterType(Askpass, 'Pmb', 1, 0, 'Askpass')

    engine.load(f"{script_dir}/qml/askpass.qml")
    if len(engine.rootObjects()) < 1:
        print("Failed to load QML!", file=sys.stderr)
        return 1

    # set window icon
    root_objects = engine.rootObjects()  # type: list[QObject]
    # QML's ApplicationWindow instantiates QQuickWindow
    app_window = root_objects[0]  # type: QQuickWindow
    app_window.setIcon(QIcon(f"{script_dir}/img/pmos-logo.svg"))

    engine.quit.connect(app.quit)
    app.exec_()

    # print('<put-your-password-here>')  # for debugging purposes only
    if len(PASSWORD) < 1:
        sys.exit(1)

    print(PASSWORD)
    sys.stdout.flush()
    sys.exit(0)


def usage(pname: str):
    print(f"Usage: {pname} <prompt>")
    sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        sudo_askpass(sys.argv[1])
    else:
        usage(sys.argv[0])
