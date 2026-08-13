"""Tests for series resolution and Debian Import Freeze dates."""

from datetime import date

import series


def test_known_dif_date():
    """From the published 26.10 release schedule."""
    assert series.dif_date("stonking") == date(2026, 8, 20)


def test_unknown_series_reports_unknown():
    """Guessing a DIF date would invert the advice for every no-delta package."""
    assert series.freeze_state("nonexistent") == (None, None, None)


def test_freeze_state_before_and_after():
    assert series.freeze_state("stonking", today=date(2026, 8, 13))[:1] == (False,)
    assert series.freeze_state("stonking", today=date(2026, 8, 13))[2] == 7
    assert series.freeze_state("stonking", today=date(2026, 8, 20))[0] is True


def test_override_beats_table():
    assert series.dif_date("stonking", override="2026-01-01") == date(2026, 1, 1)
