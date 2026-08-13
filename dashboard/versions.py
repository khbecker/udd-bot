"""Debian/Ubuntu version comparison and package state classification.

Imports neither Flask nor psycopg2, so it is unit testable without a web
stack or a database.
"""

import re

# ---------------------------------------------------------------------------
# Version comparison
# ---------------------------------------------------------------------------

try:  # pragma: no cover - depends on whether python3-apt is available
    import apt_pkg

    apt_pkg.init_system()
    _HAVE_APT_PKG = True
except Exception:  # pragma: no cover
    _HAVE_APT_PKG = False


def _order(c):
    """Sort key for one non-digit character: ~ sorts before letters before the rest."""
    if c == "~":
        return -1
    if c.isalpha():
        return ord(c)
    return ord(c) + 256


def _cmp_part(a, b):
    """Compare one version component using Debian's algorithm."""
    i, j = 0, 0
    while i < len(a) or j < len(b):
        while (i < len(a) and not a[i].isdigit()) or (j < len(b) and not b[j].isdigit()):
            ac = _order(a[i]) if i < len(a) and not a[i].isdigit() else 0
            bc = _order(b[j]) if j < len(b) and not b[j].isdigit() else 0
            if ac != bc:
                return -1 if ac < bc else 1
            if i < len(a) and not a[i].isdigit():
                i += 1
            if j < len(b) and not b[j].isdigit():
                j += 1
            if (i >= len(a) or a[i].isdigit()) and (j >= len(b) or b[j].isdigit()):
                break
        num_a, num_b = 0, 0
        while i < len(a) and a[i].isdigit():
            num_a = num_a * 10 + int(a[i])
            i += 1
        while j < len(b) and b[j].isdigit():
            num_b = num_b * 10 + int(b[j])
            j += 1
        if num_a != num_b:
            return -1 if num_a < num_b else 1
    return 0


def split_version(version):
    """Split a version into (epoch, upstream, revision).

    >>> split_version("1:2.0-3ubuntu1")
    (1, '2.0', '3ubuntu1')
    >>> split_version("4.15ubuntu5")
    (0, '4.15ubuntu5', '')
    """
    epoch = 0
    rest = version
    if ":" in rest:
        head, tail = rest.split(":", 1)
        if head.isdigit():
            epoch = int(head)
            rest = tail
    if "-" in rest:
        upstream, revision = rest.rsplit("-", 1)
    else:
        upstream, revision = rest, ""
    return epoch, upstream, revision


def _fallback_compare(a, b):
    ea, ua, ra = split_version(a)
    eb, ub, rb = split_version(b)
    if ea != eb:
        return -1 if ea < eb else 1
    c = _cmp_part(ua, ub)
    if c != 0:
        return c
    return _cmp_part(ra or "0", rb or "0")


def version_compare(a, b):
    """Compare two Debian version strings. Returns <0, 0 or >0.

    Uses apt_pkg when available (authoritative), otherwise falls back to a
    pure-Python implementation of the same algorithm.

    >>> version_compare("1.0", "1.0a") < 0
    True
    >>> version_compare("1.2-3ubuntu0.1", "1.2-3") > 0
    True
    >>> version_compare("2:1.0", "1:9.9") > 0
    True
    """
    if _HAVE_APT_PKG:  # pragma: no cover
        return apt_pkg.version_compare(a, b)
    return _fallback_compare(a, b)


# ---------------------------------------------------------------------------
# Ubuntu delta detection
# ---------------------------------------------------------------------------

# Matches an Ubuntu revision marker anywhere in the version, covering
# -3ubuntu1, -0ubuntu5, -1ubuntu0.2 and native forms such as 4.15ubuntu5.
_UBUNTU_RE = re.compile(r"ubuntu(\d+(?:\.\d+)*)")


def is_native(version):
    """True if the version has no Debian revision (native source format).

    >>> is_native("4.15ubuntu5")
    True
    >>> is_native("1.2-3")
    False
    """
    _, _, revision = split_version(version)
    return revision == ""


def ubuntu_delta(version):
    """Return the Ubuntu revision marker, or None if the version has no delta.

    >>> ubuntu_delta("1.2-3ubuntu1")
    'ubuntu1'
    >>> ubuntu_delta("1.2-3ubuntu0.1")
    'ubuntu0.1'
    >>> ubuntu_delta("4.15ubuntu5")
    'ubuntu5'
    >>> ubuntu_delta("1.2-3") is None
    True
    """
    if version is None:
        return None
    match = _UBUNTU_RE.search(version)
    return match.group(0) if match else None


def upstream_version(version):
    """The upstream portion of a version, with any Ubuntu marker stripped.

    >>> upstream_version("6.19+ds-0ubuntu5")
    '6.19+ds'
    >>> upstream_version("4.15ubuntu5")
    '4.15'
    """
    _, upstream, _ = split_version(version)
    return _UBUNTU_RE.sub("", upstream).rstrip("-.~+")


# ---------------------------------------------------------------------------
# Package states
# ---------------------------------------------------------------------------

NOT_IN_DEVEL = "not-in-devel"
UBUNTU_ONLY = "ubuntu-only"
IN_PROPOSED = "in-proposed"
SYNCED = "synced"
AUTOSYNC_PENDING = "autosync-pending"
SYNC_AVAILABLE = "sync-available"
MERGE_NEEDED = "merge-needed"
DELTA_CURRENT = "delta-current"
UBUNTU_AHEAD = "ubuntu-ahead"

#: state -> (label, tone, tooltip). Tone is semantic; app.py maps it to CSS.
STATE_INFO = {
    NOT_IN_DEVEL: ("Not in devel", "warn", "Absent from the devel series; check if it was removed."),
    UBUNTU_ONLY: ("Ubuntu only", "info", "No Debian counterpart; maintained directly in Ubuntu."),
    IN_PROPOSED: ("In proposed", "warn", "A newer version is waiting in -proposed; check proposed-migration."),
    SYNCED: ("Synced", "ok", "Identical to Debian, no Ubuntu delta."),
    AUTOSYNC_PENDING: ("Autosync pending", "info", "No delta and Debian is newer; autosync handles this before DIF."),
    SYNC_AVAILABLE: ("Sync available", "action", "Debian has packaged this upstream release; the Ubuntu delta can probably be dropped."),
    MERGE_NEEDED: ("Merge needed", "action", "Debian is newer and Ubuntu carries a delta."),
    DELTA_CURRENT: ("Delta current", "ok", "Ubuntu carries a delta but Debian is not ahead."),
    UBUNTU_AHEAD: ("Ubuntu ahead", "ok", "Ubuntu is ahead of Debian without an Ubuntu revision marker."),
}

#: States that need a human to do something.
ACTIONABLE = {NOT_IN_DEVEL, IN_PROPOSED, SYNC_AVAILABLE, MERGE_NEEDED}

# Upstream watch axis, kept separate from the Debian/Ubuntu axis.
UPSTREAM_OK = "up-to-date"
UPSTREAM_NEWER = "newer"
UPSTREAM_UNKNOWN = "unknown"


def classify_upstream(watch_status):
    """Map a UDD watch status onto an upstream state.

    Anything not explicitly good or explicitly newer is unknown, not healthy.

    >>> classify_upstream("newer package available")
    'newer'
    >>> classify_upstream("up to date")
    'up-to-date'
    >>> classify_upstream("only older package available")
    'unknown'
    >>> classify_upstream(None)
    'unknown'
    """
    if not watch_status:
        return UPSTREAM_UNKNOWN
    status = watch_status.strip().lower()
    if status == "up to date":
        return UPSTREAM_OK
    if status == "newer package available":
        return UPSTREAM_NEWER
    return UPSTREAM_UNKNOWN


def _is_sync_candidate(devel, debian):
    """True when the Ubuntu delta looks droppable in favour of a plain sync.

    The narrow case where Ubuntu packaged an upstream release ahead of Debian
    as ``-0ubuntuN`` and Debian has since packaged the same upstream version.
    Anything else is a merge, where a human must judge whether the delta
    still applies.

    >>> _is_sync_candidate("2026.05.30-0ubuntu1", "2026.05.30-1")
    True
    >>> _is_sync_candidate("6.19+ds-0ubuntu5", "7.0+ds-1")
    False
    >>> _is_sync_candidate("1.2-3ubuntu1", "1.2-4")
    False
    """
    _, _, revision = split_version(devel)
    if not revision.startswith("0ubuntu"):
        return False
    return version_compare(upstream_version(devel), upstream_version(debian)) == 0


def _state(devel, proposed, debian, has_delta, in_proposed):
    """Work out the state. See STATE_INFO for what each one means."""
    if not devel and not proposed:
        return NOT_IN_DEVEL
    if not devel:
        return IN_PROPOSED  # only ever been in -proposed
    if not debian:
        return UBUNTU_ONLY

    cmp_devel = version_compare(devel, debian)
    if cmp_devel < 0:
        if not has_delta:
            state = AUTOSYNC_PENDING
        elif _is_sync_candidate(devel, debian):
            state = SYNC_AVAILABLE
        else:
            state = MERGE_NEEDED
    elif cmp_devel == 0:
        state = SYNCED
    else:
        state = DELTA_CURRENT if has_delta else UBUNTU_AHEAD

    # The release pocket is behind Debian, but a pending upload already covers
    # it: chase proposed-migration rather than prepare another upload. Applies
    # whichever state it would otherwise have been.
    if in_proposed and cmp_devel < 0 and version_compare(proposed, debian) >= 0:
        state = IN_PROPOSED
    return state


def classify(devel=None, proposed=None, debian=None):
    """Classify a package from its devel, -proposed and sid versions.

    Pass None for a suite the package is absent from. Returns the state, the
    Ubuntu delta marker, whether an upload is pending in -proposed, and
    whether the source format is native.
    """
    # Fall back to -proposed only when the package is not in the release
    # pocket at all, so the delta always describes the version shown.
    current = devel or proposed
    in_proposed = bool(
        proposed and (not devel or version_compare(proposed, devel) > 0)
    )
    delta = ubuntu_delta(current)
    return {
        "state": _state(devel, proposed, debian, delta is not None, in_proposed),
        "delta": delta,
        "in_proposed": in_proposed,
        "native": bool(current) and is_native(current),
    }
