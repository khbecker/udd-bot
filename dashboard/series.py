"""Current Ubuntu development and LTS series, and freeze dates.

The UDD queries need concrete release names, and the UI should never say
"devel" without naming the series.
"""

import os
import subprocess
from datetime import date, datetime

#: Used when distro-info is unavailable. The UI flags these as guesses.
FALLBACK_DEVEL = "questing"
FALLBACK_LTS = "noble"


def _distro_info(*args):
    try:
        out = subprocess.run(
            ["ubuntu-distro-info", *args],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = out.stdout.strip().splitlines()
    return value[-1].strip() if value else None


def devel_series(override=None):
    """Name of the current development series."""
    return override or os.environ.get("UDD_DEVEL_SERIES") or _distro_info("--devel") or FALLBACK_DEVEL


def lts_series(override=None):
    """Name of the most recent LTS series."""
    return override or os.environ.get("UDD_LTS_SERIES") or _distro_info("--lts") or FALLBACK_LTS


def resolved_by_distro_info():
    """True when distro-info answered, rather than us falling back."""
    return _distro_info("--devel") is not None


# ---------------------------------------------------------------------------
# Debian Import Freeze
# ---------------------------------------------------------------------------
#
# Before DIF, packages with no Ubuntu delta sync from Debian automatically.
# After DIF they need a manual sync, which inverts the advice for most rows.

#: From the published release schedules. Only add a series once its date has
#: been checked; an unknown series must report unknown rather than be guessed.
#: stonking (26.10): https://documentation.ubuntu.com/release-notes/26.10/schedule/
KNOWN_DIF_DATES = {
    "stonking": date(2026, 8, 20),  # same day as Feature Freeze
}


def dif_date(series=None, override=None):
    """DIF date for ``series``, or None if unknown.

    An override or UDD_DIF_DATE wins over the table, so a new cycle needs no
    code change.
    """
    raw = override or os.environ.get("UDD_DIF_DATE")
    if raw:
        try:
            return datetime.strptime(raw.strip(), "%Y-%m-%d").date()
        except ValueError:
            return None
    return KNOWN_DIF_DATES.get(series)


def freeze_state(series=None, override=None, today=None):
    """Return (passed, date, days_until) for Debian Import Freeze.

    passed is None when the date is unknown, so the UI can say so rather than
    imply autosync is still running. days_until goes negative after DIF.
    """
    when = dif_date(series, override)
    if when is None:
        return None, None, None
    now = today or date.today()
    return now >= when, when, (when - now).days
