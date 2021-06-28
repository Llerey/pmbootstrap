# Copyright 2021 Alexey Minnekhanov
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import os
import time

_have_pyqt5 = False
_have_pygtk = False


def test_installed_gui_tooklits():
    global _have_pyqt5, _have_pygtk
    try:
        import PyQt5
        _have_pyqt5 = True
    except ImportError:
        pass

    try:
        import gi
        _have_pygtk = True
    except ImportError:
        pass


def raise_no_gui_toolkits():
    raise RuntimeError(
        "Can't run GUI: you need to install either PyQt5 or pygobject!\n"
        "You can do it using your distribution's package manager.")


def run_gui_qt5(args):
    import pmb.gui.qt5
    pmb.gui.qt5.start(args)


def run_gui_gtk(args):
    # TODO: implement
    pass


def run_gui_autoselect(args):
    global _have_pyqt5, _have_pygtk

    prefer_qt = False
    if os.environ["KDE_FULL_SESSION"] == "true" \
            or os.environ["XDG_CURRENT_DESKTOP"] == "KDE":
        prefer_qt = True
        logging.debug("KDE session detected")

    # TODO: add test for magic env vars for Gnome(-based) DEs

    # Be fair, true random
    if not prefer_qt and time.time() % 2 == 0:
        prefer_qt = True

    if prefer_qt and _have_pyqt5:
        run_gui_qt5(args)
        return

    # if no Qt preference, try gtk first
    if _have_pygtk:
        run_gui_gtk(args)
        return
    if _have_pyqt5:
        run_gui_qt5(args)
        return
    # give up
    raise_no_gui_toolkits()


def run_gui(args):
    test_installed_gui_tooklits()

    if not _have_pygtk and not _have_pyqt5:
        raise_no_gui_toolkits()
        return

    force_qt5 = False
    force_gtk = False
    if args.qt5:
        force_qt5 = args.qt5
    if args.gtk:
        force_gtk = args.gtk

    if force_gtk and force_qt5:
        raise RuntimeError("You must select only one of qt5, gtk options!")

    if force_gtk:
        if not _have_pygtk:
            raise RuntimeError("Cannot use gtk: pygobject is not installed!")
        run_gui_gtk(args)
    elif force_qt5:
        if not _have_pyqt5:
            raise RuntimeError("Cannot use Qt5: PyQt5 is not installed!")
        run_gui_qt5(args)
    else:
        run_gui_autoselect(args)
