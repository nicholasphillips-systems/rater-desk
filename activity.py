"""Which window you're in and whether you're at the keyboard, for the auto timer.

KDE Plasma (Wayland or X11): a small KWin script calls back into the app over D-Bus
whenever the focused window or its title changes, and (at most every 20 s) when
the mouse moves. Wayland gives apps no other way to see other windows. Screen lock
comes from org.freedesktop.ScreenSaver's ActiveChanged signal.

Windows: polls the foreground window title, its .exe name and GetLastInputInfo
every few seconds.

Anything else: auto timer unavailable; why_unavailable says so.
"""

import datetime
import os
import tempfile

from PyQt6.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot

import paths

SERVICE = "org.raterdesk.Activity"
OBJECT_PATH = "/Activity"
INTERFACE = "org.raterdesk.Activity"
KWIN_SCRIPT_NAME = "raterdesk-activity"

KWIN_SCRIPT = """
// Rater Desk auto timer: report the focused window and mouse movement.
var lastInput = 0;
function send(w) {
    if (!w) return;
    callDBus("%(service)s", "%(path)s", "%(iface)s", "focus",
             String(w.caption || ""), String(w.resourceClass || ""));
}
function watch(w) {
    if (!w) return;
    w.captionChanged.connect(function () { if (workspace.activeWindow === w) send(w); });
}
workspace.windowList().forEach(watch);
workspace.windowAdded.connect(watch);
workspace.windowActivated.connect(send);
workspace.cursorPosChanged.connect(function () {
    var now = Date.now();
    if (now - lastInput > 20000) {
        lastInput = now;
        callDBus("%(service)s", "%(path)s", "%(iface)s", "input");
    }
});
send(workspace.activeWindow);
""" % {"service": SERVICE, "path": OBJECT_PATH, "iface": INTERFACE}


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


class ActivitySource(QObject):
    focus_changed = pyqtSignal(str, str, object)   # title, app class, when
    input_seen = pyqtSignal(object)                 # when
    lock_changed = pyqtSignal(bool, object)         # locked, when

    def __init__(self, parent=None):
        super().__init__(parent)
        self.why_unavailable = None
        self._impl = None

    def start(self):
        """Begin watching. Returns False (and sets why_unavailable) if it can't here."""
        if paths.IS_WINDOWS:
            self._impl = _WindowsPoller(self)
        elif paths.IS_LINUX and _is_kde():
            self._impl = _KWinWatcher(self)
        else:
            self.why_unavailable = "needs KDE Plasma or Windows"
            return False
        ok = self._impl.start()
        if not ok:
            self.why_unavailable = self._impl.error
            self._impl = None
        return ok

    def stop(self):
        if self._impl:
            self._impl.stop()
            self._impl = None


def _is_kde():
    desktop = (os.environ.get("XDG_CURRENT_DESKTOP", "") + os.environ.get("DESKTOP_SESSION", "")).lower()
    return "kde" in desktop or "plasma" in desktop


class _KWinWatcher(QObject):
    def __init__(self, source):
        super().__init__(source)
        self.source = source
        self.error = None
        self.script_path = None

    @pyqtSlot(str, str)
    def focus(self, caption, resource_class):
        self.source.focus_changed.emit(caption, resource_class, utc_now())

    @pyqtSlot()
    def input(self):
        self.source.input_seen.emit(utc_now())

    @pyqtSlot(bool)
    def screen_lock(self, active):
        self.source.lock_changed.emit(bool(active), utc_now())

    def start(self):
        from PyQt6.QtDBus import QDBusConnection, QDBusInterface

        bus = QDBusConnection.sessionBus()
        if not bus.isConnected():
            self.error = "no D-Bus session"
            return False
        if not bus.registerService(SERVICE):
            self.error = "another Rater Desk is already watching windows"
            return False
        bus.registerObject(OBJECT_PATH, INTERFACE, self,
                           QDBusConnection.RegisterOption.ExportAllSlots)
        for path in ("/org/freedesktop/ScreenSaver", "/ScreenSaver"):
            bus.connect("org.freedesktop.ScreenSaver", path, "org.freedesktop.ScreenSaver",
                        "ActiveChanged", self.screen_lock)

        if os.environ.get("RATER_DESK_NO_KWIN_SCRIPT"):
            # Testing: events arrive only from whoever calls focus/input on D-Bus,
            # not from the real desktop.
            return True

        fd, self.script_path = tempfile.mkstemp(prefix="raterdesk-kwin-", suffix=".js")
        with os.fdopen(fd, "w") as f:
            f.write(KWIN_SCRIPT)
        scripting = QDBusInterface("org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting", bus)
        if not scripting.isValid():
            self.error = "KWin scripting not reachable"
            return False
        # A copy left behind by a crash would report to nobody; replace it.
        scripting.call("unloadScript", KWIN_SCRIPT_NAME)
        reply = scripting.call("loadScript", self.script_path, KWIN_SCRIPT_NAME)
        args = reply.arguments()
        if not args or int(args[0]) < 0:
            self.error = "KWin refused the window-watch script"
            return False
        script = QDBusInterface("org.kde.KWin", f"/Scripting/Script{int(args[0])}",
                                "org.kde.kwin.Script", bus)
        script.call("run")
        return True

    def stop(self):
        from PyQt6.QtDBus import QDBusConnection, QDBusInterface

        bus = QDBusConnection.sessionBus()
        QDBusInterface("org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting", bus) \
            .call("unloadScript", KWIN_SCRIPT_NAME)
        bus.unregisterObject(OBJECT_PATH)
        bus.unregisterService(SERVICE)
        if self.script_path and os.path.exists(self.script_path):
            os.unlink(self.script_path)


class _WindowsPoller(QObject):
    POLL_MS = 3000

    def __init__(self, source):
        super().__init__(source)
        self.source = source
        self.error = None
        self._last = None
        self._last_input_tick = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)

    def start(self):
        try:
            self._api = _win32_api()
        except (OSError, AttributeError) as e:
            self.error = f"Windows API unavailable ({e})"
            return False
        self._timer.start(self.POLL_MS)
        self._poll()
        return True

    def stop(self):
        self._timer.stop()

    def _poll(self):
        now = utc_now()
        title, exe = self._api.foreground()
        if (title, exe) != self._last:
            self._last = (title, exe)
            self.source.focus_changed.emit(title, exe, now)
        tick, idle_ms = self._api.last_input()
        if tick != self._last_input_tick:
            self._last_input_tick = tick
            self.source.input_seen.emit(now - datetime.timedelta(milliseconds=idle_ms))


def _win32_api():
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

    class Api:
        def foreground(self):
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return "", ""
            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            exe = ""
            handle = kernel32.OpenProcess(0x1000, False, pid.value)  # QUERY_LIMITED_INFORMATION
            if handle:
                size = wintypes.DWORD(1024)
                path = ctypes.create_unicode_buffer(1024)
                if kernel32.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size)):
                    exe = os.path.basename(path.value).lower()
                kernel32.CloseHandle(handle)
            return buf.value, exe

        def last_input(self):
            info = LASTINPUTINFO()
            info.cbSize = ctypes.sizeof(info)
            user32.GetLastInputInfo(ctypes.byref(info))
            idle = (kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF
            return info.dwTime, idle

    return Api()
