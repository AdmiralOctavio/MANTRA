"""
Sounds of the LCARS theme: the chirps of the consoles when a button is pressed, a field is clicked or a value entered, and the alarms
when the app warns or fails. Only the LCARS theme plays them, and the View menu turns them off.

One filter on the app hears the clicks and keys of every widget, so the tabs need no code of their own; the message boxes are heard
when they are shown, by their icon: a question (unsaved changes, quit during a run) gives the console warning, a warning (a run
failed) the damage alarm, a critical error the red alert.
"""

import os
import random
import time

from PySide6.QtCore import QEvent, QObject, Qt, QUrl
from PySide6.QtWidgets import (QAbstractButton, QAbstractItemView, QAbstractSpinBox, QApplication, QCheckBox, QComboBox, QLineEdit,
                               QMenu, QMenuBar, QMessageBox, QRadioButton, QTabBar)

FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sounds")

# what plays when: a list is played in a random order, so the same buttons do not always chirp the same
SOUNDS = {
    "button": ["computerbeep_3", "computerbeep_26", "computerbeep_44"],    # any other button
    "primary": ["computerbeep_73"],                                         # Solve nozzle, Run thermal simulation, Run throttle analysis
    "tab": ["computerbeep_42"],                                             # the column of the frame and the tab bars
    "view": ["deskviewerbeep"],                                             # the tabs of the plots on the Results tab
    "complete": ["voy_hail"],                                               # the nozzle solved, a thermal run or throttle analysis done
    "menu": ["computerbeep_43"],                                            # a command of a menu
    "open": ["computerbeep_15"],                                            # a menu of the menu bar, a field or drop-down clicked
    "enter": ["computerbeep_4"],                                            # Enter in a field, a choice of a drop-down
    "toggle": ["computerbeep_5"],                                           # check boxes
    "done": ["computerbeep_74"],                                            # an information box (STEP model written)
    "about": ["computerbeep_75"],
    "invalid": ["consolewarning"],                                          # a value that can not be read
    "question": ["consolewarning"],                                         # unsaved changes, quit during a run
    "warning": ["damagealarm"],                                             # a run failed
    "critical": ["critical"],                                               # a file can not be opened or written
}
ALERTS = {"invalid", "question", "warning", "critical"}
# loudness of the files, so that they all sound about as loud
VOLUME = {"damagealarm": 0.35, "computerbeep_15": 0.9, "critical": 0.7}
LOUDNESS = 0.6


class Sounds(QObject):
    def __init__(self):
        super().__init__()
        self.effects = {}          # file name: QSoundEffect, made when the LCARS theme is first chosen
        self.theme = False         # the LCARS theme is on
        self.enabled = True        # the View menu has the sounds on
        self.last = None           # name of the last sound, for the tests
        self._played = (None, 0.0)
        self._pressed = None       # widget of the last mouse press

    @property
    def active(self):
        return self.theme and self.enabled

    def set_theme(self, app, lcars):
        if lcars == self.theme:
            return
        self.theme = lcars
        if lcars:
            self._load()
            app.installEventFilter(self)
        else:
            app.removeEventFilter(self)
            self.stop()

    def set_enabled(self, on):
        self.enabled = bool(on)
        if not on:
            self.stop()

    def _load(self):
        if self.effects:
            return
        try:
            from PySide6.QtMultimedia import QSoundEffect
        except ImportError:            # Qt without its multimedia module: the theme stays silent
            return
        for names in SOUNDS.values():
            for name in names:
                if name not in self.effects:
                    effect = QSoundEffect(self)
                    effect.setSource(QUrl.fromLocalFile(os.path.join(FOLDER, name + ".wav")))
                    effect.setVolume(LOUDNESS * VOLUME.get(name, 1.0))
                    self.effects[name] = effect

    def play(self, kind):
        """Plays a sound of the kind (a key of SOUNDS), if the LCARS theme and its sounds are on"""
        if not self.active or kind not in SOUNDS:
            return
        # a key or click passes through the field and its parents: one sound for it
        now = time.monotonic()
        if self._played[0] == kind and now - self._played[1] < 0.08:
            return
        self._played = (kind, now)
        if kind in ALERTS or kind == "complete":
            self.stop()                # the alarm or the hail, not the chirp of the button that led to it
        self.last = kind
        self._start(random.choice(SOUNDS[kind]))

    def _start(self, name):
        effect = self.effects.get(name)
        if effect is not None:
            effect.play()

    def stop(self):
        for effect in self.effects.values():
            effect.stop()

    # ── what the widgets do ──────────────────────────────────────────────
    def eventFilter(self, obj, event):
        if self.active:
            try:
                kind = self._kind(obj, event)
                if kind is not None:
                    self.play(kind)
            except Exception:          # a sound must never break the app
                pass
        return False

    def _kind(self, obj, event):
        t = event.type()
        if t == QEvent.Type.MouseButtonRelease:
            if event.button() != Qt.MouseButton.LeftButton or not getattr(obj, "isEnabled", lambda: False)():
                return None
            pos = event.position().toPoint()
            if isinstance(obj, QAbstractButton):
                if not obj.rect().contains(pos):
                    return None
                from .lcars import ColumnButton
                if isinstance(obj, ColumnButton):
                    return None if obj.isChecked() else "tab"
                if isinstance(obj, (QCheckBox, QRadioButton)):
                    return "toggle"
                return "primary" if obj.objectName() == "primary" else "button"
            if isinstance(obj, QMenu):
                action = obj.actionAt(pos)
                return "menu" if action is not None and action.isEnabled() and action.menu() is None and not action.isSeparator() else None
            # a choice in the list of a drop-down; not the release of the click that opened it, which lands on the list as well
            view = obj.parent()
            if isinstance(view, QAbstractItemView) and view.window().metaObject().className() == "QComboBoxPrivateContainer":
                return "enter" if self._pressed is obj else None
            return None
        if t == QEvent.Type.MouseButtonPress:
            self._pressed = obj
            if event.button() != Qt.MouseButton.LeftButton or not getattr(obj, "isEnabled", lambda: False)():
                return None
            pos = event.position().toPoint()
            if isinstance(obj, QTabBar):
                index = obj.tabAt(pos)
                # a tab bar can ask for a sound of its own (the plots on the Results tab)
                return (obj.property("sound") or "tab") if index >= 0 and index != obj.currentIndex() else None
            if isinstance(obj, QMenuBar):
                return "open" if obj.actionAt(pos) is not None else None
            if isinstance(obj, (QAbstractSpinBox, QComboBox, QLineEdit)):
                return "open"
            return None
        if t == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and isinstance(obj, (QLineEdit, QAbstractSpinBox, QComboBox)):
                return "enter"
            return None
        if t == QEvent.Type.Show and isinstance(obj, QMessageBox):
            icon = obj.icon()
            # Windows plays its own sound for a box with a standard icon (Qt picks it from the icon): the same picture without the
            # standard icon keeps the box silent, so only the alarm of the theme is heard
            if icon != QMessageBox.Icon.NoIcon:
                obj.setIconPixmap(obj.iconPixmap())
            return {QMessageBox.Icon.Question: "question", QMessageBox.Icon.Warning: "warning", QMessageBox.Icon.Critical: "critical",
                    QMessageBox.Icon.Information: "done"}.get(icon, "about")
        return None


player = Sounds()


def play(kind):
    player.play(kind)


def set_theme(lcars):
    app = QApplication.instance()
    if app is not None:
        player.set_theme(app, lcars)

def check(seconds=5.0):
    """For the self test of the packaged app: the multimedia module of Qt and the sound files are there. Returns (ok, text). How
    many sounds Qt could read is told, but does not fail the test: a build machine may have no sound device."""
    try:
        from PySide6.QtMultimedia import QSoundEffect
    except ImportError as e:
        return False, "LCARS sounds: no Qt multimedia module (%s)" % e
    names = sorted({name for names in SOUNDS.values() for name in names})
    missing = [name for name in names if not os.path.exists(os.path.join(FOLDER, name + ".wav"))]
    if missing:
        return False, "LCARS sounds: missing " + ", ".join(missing)
    app = QApplication.instance() or QApplication([])
    sounds = Sounds()
    sounds._load()
    end = time.monotonic() + seconds
    while time.monotonic() < end and any(e.status() in (QSoundEffect.Status.Null, QSoundEffect.Status.Loading)
                                         for e in sounds.effects.values()):
        app.processEvents()
        time.sleep(0.02)
    ready = sum(e.status() == QSoundEffect.Status.Ready for e in sounds.effects.values())
    return True, "LCARS sounds: %d of %d read" % (ready, len(names))
