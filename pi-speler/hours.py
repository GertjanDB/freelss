# SPDX-License-Identifier: GPL-3.0-or-later
"""Nacht van 23:00 tot 08:00, klok van Brussel.

De Pi blijft aan. Knoppen die geluid maken zijn stil zodra 23:00 voorbijgaat
terwijl hij al loopt, en doen het weer om 08:00. Een start in die uren,
bijvoorbeeld na stroomherstel, blijft gewoon aan.

Echt uitzetten doet de Pi niet. Een uitgezet board start zichzelf om 08:00 niet.
Elke maandag om 08:00 herstart hij één keer, als hij dan al loopt.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

log = logging.getLogger("pi-speler")

QUIET_START_HOUR = 23
QUIET_END_HOUR = 8
BRUSSELS = ZoneInfo("Europe/Brussels")
MAX_GAP = timedelta(minutes=15)


def brussels(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(BRUSSELS)


def is_quiet_hour(moment: datetime) -> bool:
    hour = brussels(moment).hour
    return hour >= QUIET_START_HOUR or hour < QUIET_END_HOUR


class NightIdle:
    """Stil alleen als de lopende klok 23:00 passeert. Niet bij een sprong."""

    def __init__(self, now=None) -> None:
        self._now = now or (lambda: datetime.now(timezone.utc))
        self.silent = False
        self._last: datetime | None = None
        self._was_quiet = False

    def tick(self) -> str | None:
        moment = self._now()
        quiet = is_quiet_hour(moment)
        if self._last is None:
            self._last = moment
            self._was_quiet = quiet
            return None
        gap = moment - self._last
        self._last = moment
        if not quiet:
            self._was_quiet = False
            if self.silent:
                self.silent = False
                return "dag"
            return None
        entered = (not self._was_quiet) and timedelta(0) <= gap <= MAX_GAP
        self._was_quiet = True
        if entered and not self.silent:
            self.silent = True
            return "nacht"
        return None


class MorningReset:
    """Eén herstart als de lopende klok maandag 08:00 passeert."""

    def __init__(self, path: Path, now=None) -> None:
        self.path = Path(path)
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._last: datetime | None = None
        self._due: str | None = None

    def tick(self) -> bool:
        local = brussels(self._now())
        if self._last is None:
            self._last = local
            return False
        previous = self._last
        gap = local - previous
        self._last = local
        crossed = (
            timedelta(0) <= gap <= MAX_GAP
            and previous.date() == local.date()
            and previous.hour < QUIET_END_HOUR
            and local.hour >= QUIET_END_HOUR
            and local.weekday() == 0
        )
        if crossed:
            self._due = local.date().isoformat()
        if self._due is None or self._stamped(self._due):
            return False
        return True

    def commit(self) -> bool:
        if self._due is None:
            return False
        return self._stamp(self._due)

    def clear(self) -> None:
        try:
            self.path.unlink()
        except OSError:
            return

    def _stamped(self, day: str) -> bool:
        try:
            return self.path.read_text(encoding="utf-8").strip() == day
        except OSError:
            return False

    def _stamp(self, day: str) -> bool:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_name(self.path.name + ".tmp")
            temporary.write_text(day + "\n", encoding="utf-8")
            temporary.replace(self.path)
        except OSError as exc:
            log.warning("weekreset niet bewaard: %s", exc)
            return False
        return True
