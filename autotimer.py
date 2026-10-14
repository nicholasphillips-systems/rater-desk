"""Auto timer: starts and stops work sessions from what window you're in. No UI imports.

Fed three things by activity.py: which window has focus (focus), that you touched
the mouse or changed tabs (activity), and screen lock (lock). tick() runs every few
seconds and decides.

  - A platform's site in focus for SETTLE seconds starts its timer, back-dated to
    when you opened it.
  - Leaving every platform window for AWAY seconds stops it, ended at when you left.
    A quick look at notes or Claude in between doesn't break the session.
  - Moving to another platform for SETTLE seconds switches the timer over.
  - No input for IDLE seconds, or locking the screen, stops it at your last input.
  - A manual timer always wins: auto mode stands aside while one runs, and won't
    restart on a platform you stopped by hand until you leave it and come back.
  - Sessions shorter than MIN_KEEP are thrown away as noise.

Times are timezone-aware UTC datetimes; the store gets ISO strings.
"""

import datetime

import catalog

SETTLE = 45
AWAY = 5 * 60
IDLE = 15 * 60
MIN_KEEP = 2 * 60


def _parse(iso):
    when = datetime.datetime.fromisoformat(iso)
    return when if when.tzinfo else when.replace(tzinfo=datetime.timezone.utc)


class AutoTimer:
    def __init__(self, store, on_change=None, settle=SETTLE, away=AWAY, idle=IDLE,
                 min_keep=MIN_KEEP):
        self.store = store
        self.on_change = on_change or (lambda *a: None)
        self.settle = settle
        self.away = away
        self.idle = idle
        self.min_keep = min_keep
        self.enabled = True
        self.candidate = None          # platform id now in focus, or None
        self.candidate_since = None    # when that focus began
        self.last_activity = None
        self.locked = False
        self.suppressed = None         # platform you stopped by hand while on it
        self.status = "Watching"
        self._saved_activity = None

    def recover(self):
        """End auto sessions left open by a crash or shutdown at the last input seen.

        Without this, a session open when the laptop died would run on until next
        launch and count the whole time in between.
        """
        last = self.store.get_setting("auto_last_activity")
        for s in self.store.recover_sessions():
            if s['source'] != 'auto':
                continue
            started = _parse(s['started_at'])
            end = _parse(last) if last else started
            self._stop(s, end, "recovered after restart")

    # -- inputs

    def focus(self, title, app_class, now):
        self.activity(now)
        plat = catalog.match_window(title, app_class, self.store.get_all_platforms())
        pid = plat['id'] if plat else None
        if pid != self.candidate or self.candidate_since is None:
            self.candidate = pid
            self.candidate_since = now
        if self.suppressed is not None and pid != self.suppressed:
            self.suppressed = None
        self.tick(now)

    def activity(self, now):
        # Coming back after going idle counts as opening the window fresh, so the
        # idle stretch never lands inside the next session.
        if self.last_activity is None or (now - self.last_activity).total_seconds() >= self.idle:
            self.candidate_since = now
        self.last_activity = now

    def lock(self, locked, now):
        self.locked = locked
        if not locked:
            self.activity(now)
            self.candidate_since = now
        self.tick(now)

    def stopped_by_hand(self, platform_id):
        """You pressed Stop on an auto session: don't restart it while you're still there."""
        self.suppressed = platform_id

    def set_enabled(self, enabled, now):
        self.enabled = enabled
        if not enabled:
            self.shutdown(now)
            self.status = "Off"
        else:
            self.candidate_since = now
            self.tick(now)

    def shutdown(self, now):
        """Stop a running auto session (app quitting or auto mode turned off)."""
        auto = self._open_auto()
        if auto:
            self._stop(auto, self.last_activity or now, "auto mode stopped")

    # -- decision

    def tick(self, now):
        if not self.enabled:
            self.status = "Off"
            return
        open_sessions = self.store.recover_sessions()
        if any(s['source'] != 'auto' for s in open_sessions):
            self.suppressed = self.candidate
            self.status = "Paused while your manual timer runs"
            return
        auto = open_sessions[-1] if open_sessions else None
        idle_for = (now - self.last_activity).total_seconds() if self.last_activity else None
        is_idle = idle_for is None or idle_for >= self.idle
        held = (now - self.candidate_since).total_seconds() if self.candidate_since else 0

        if auto:
            if self.locked:
                self._stop(auto, self.last_activity or now, "screen locked")
            elif is_idle:
                self._stop(auto, self.last_activity or now, "no input")
            elif self.candidate == auto['platform_id']:
                self.status = f"Timing {self._name(auto['platform_id'])} (auto)"
                self._save_activity()
            elif self.candidate is not None and self.candidate != self.suppressed and held >= self.settle:
                self._stop(auto, self.candidate_since, "switched platform")
                self._start(self.candidate, self.candidate_since)
            elif held >= self.away:
                self._stop(auto, self.candidate_since, "left the platform")
            else:
                self._save_activity()
                left = int(self.away - held)
                self.status = (f"Timing {self._name(auto['platform_id'])} (auto) - "
                               f"stops in {left // 60}:{left % 60:02d} unless you go back")
            return

        if self.candidate is None:
            self.status = "Watching - no platform open"
        elif self.candidate == self.suppressed:
            self.status = f"{self._name(self.candidate)} open - you stopped it by hand"
        elif self.locked or is_idle:
            self.status = "Watching - idle"
        elif held >= self.settle:
            self._start(self.candidate, self.candidate_since)
        else:
            self.status = f"{self._name(self.candidate)} open - timer starts in {int(self.settle - held)}s"

    # -- helpers

    def _save_activity(self):
        """Note the last input in the database, about once a minute, for recover()."""
        last = self.last_activity
        if last and (self._saved_activity is None
                     or (last - self._saved_activity).total_seconds() >= 60):
            self.store.set_setting("auto_last_activity", last.isoformat())
            self._saved_activity = last

    def _open_auto(self):
        for s in self.store.recover_sessions():
            if s['source'] == 'auto':
                return s
        return None

    def _name(self, platform_id):
        plat = self.store.get_platform(platform_id)
        return plat['name'] if plat else "?"

    def _start(self, platform_id, at):
        sid = self.store.start_session(platform_id, started_at=at.isoformat(), source='auto')
        self.status = f"Timing {self._name(platform_id)} (auto)"
        self.on_change("started", sid, platform_id, None)

    def _stop(self, session, at, reason):
        started = _parse(session['started_at'])
        at = max(at, started)
        if (at - started).total_seconds() < self.min_keep:
            self.store.delete_session(session['id'])
            reason += " (under 2 min, not kept)"
        else:
            self.store.stop_session(session['id'], ended_at=at.isoformat())
        self.status = f"Stopped {self._name(session['platform_id'])}: {reason}"
        self.on_change("stopped", session['id'], session['platform_id'], reason)
