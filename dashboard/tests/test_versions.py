"""Tests for version comparison and package state classification.

Deliberately small: this covers the cases that were previously wrong, not
every possible input. Comparison is checked against dpkg, since dpkg is the
authority.
"""

import shutil
import subprocess

import pytest

import versions
from versions import (
    AUTOSYNC_PENDING,
    DELTA_CURRENT,
    IN_PROPOSED,
    MERGE_NEEDED,
    NOT_IN_DEVEL,
    SYNC_AVAILABLE,
    SYNCED,
)

HAVE_DPKG = shutil.which("dpkg") is not None


def dpkg_sign(a, b):
    if subprocess.run(["dpkg", "--compare-versions", a, "lt", b]).returncode == 0:
        return -1
    if subprocess.run(["dpkg", "--compare-versions", a, "eq", b]).returncode == 0:
        return 0
    return 1


# Pairs that exercise epochs, tildes, +ds, Ubuntu revisions and native forms.
COMPARE_PAIRS = [
    ("1.0", "1.0a"),
    ("1.0~rc1", "1.0"),
    ("2:1.0", "1:9.9"),
    ("1.2-3", "1.2-4"),
    ("1.2-3ubuntu1", "1.2-4"),
    ("1.2-3ubuntu0.1", "1.2-3"),
    ("4.15ubuntu5", "4.15"),
    ("1:1.10.7ubuntu3", "1:1.10.7"),
    ("6.19+ds-0ubuntu5", "7.0+ds-1"),
    ("2026.05.30-0ubuntu1", "2026.05.30-1"),
    ("0.9.11-1", "0.9.11-1.1"),
    ("9.0.2+~16.3-1", "9.0.2+~16.3-1"),
]


@pytest.mark.skipif(not HAVE_DPKG, reason="dpkg not available")
@pytest.mark.parametrize("a,b", COMPARE_PAIRS)
def test_version_compare_matches_dpkg(a, b):
    result = versions.version_compare(a, b)
    assert ((result > 0) - (result < 0)) == dpkg_sign(a, b)


@pytest.mark.parametrize(
    "version,expected",
    [
        ("1.2-3ubuntu0.1", "ubuntu0.1"),  # missed by a trailing-ubuntuN regex
        ("4.15ubuntu5", "ubuntu5"),  # native
        ("6.19+ds-0ubuntu5", "ubuntu5"),
        ("1.2-3", None),
    ],
)
def test_ubuntu_delta(version, expected):
    assert versions.ubuntu_delta(version) == expected


# Pinned to real archive data for the tracked packages.
@pytest.mark.parametrize(
    "devel,proposed,debian,expected",
    [
        # crash: no delta, identical to Debian.
        ("9.0.2+~16.3-1", None, "9.0.2+~16.3-1", SYNCED),
        # strace: delta carried, Debian moved to a new upstream.
        ("6.19+ds-0ubuntu5", None, "7.0+ds-1", MERGE_NEEDED),
        # wireless-regdb: Ubuntu packaged upstream first, Debian caught up.
        ("2026.05.30-0ubuntu1", None, "2026.05.30-1", SYNC_AVAILABLE),
        # ethtool: release pocket behind, but the upload is already pending.
        ("1:7.0-1", "1:7.1-1", "1:7.1-1", IN_PROPOSED),
        # ...and the same package without that pending upload.
        ("1:7.0-1", None, "1:7.1-1", AUTOSYNC_PENDING),
        # linux-base: native, must not be compared as if it had a revision.
        ("4.15ubuntu5", None, "4.15", DELTA_CURRENT),
        # Absent from devel.
        (None, None, "1.0-1", NOT_IN_DEVEL),
    ],
)
def test_classify(devel, proposed, debian, expected):
    assert versions.classify(devel=devel, proposed=proposed, debian=debian)["state"] == expected


@pytest.mark.parametrize(
    "status,expected",
    [
        ("up to date", versions.UPSTREAM_OK),
        ("newer package available", versions.UPSTREAM_NEWER),
        # makedumpfile reports this; it must not render as healthy.
        ("only older package available", versions.UPSTREAM_UNKNOWN),
        (None, versions.UPSTREAM_UNKNOWN),
    ],
)
def test_classify_upstream(status, expected):
    assert versions.classify_upstream(status) == expected


def test_every_state_has_display_info():
    """Guard against adding a state the UI cannot render."""
    assert versions.ACTIONABLE <= set(versions.STATE_INFO)
