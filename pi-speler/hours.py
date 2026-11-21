# SPDX-License-Identifier: GPL-3.0-or-later
"""Nacht van 23:00 tot 08:00, klok van Brussel.

De Pi blijft aan. Knoppen die geluid maken zijn stil zodra 23:00 voorbijgaat
terwijl hij al loopt, en doen het weer om 08:00. Een start in die uren,
bijvoorbeeld na stroomherstel, blijft gewoon aan.

Echt uitzetten doet de Pi niet. Een uitgezet board start zichzelf om 08:00 niet.
Hij herstart niet op een klok. Stopt de speler met een fout, dan start de service hem opnieuw.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

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
