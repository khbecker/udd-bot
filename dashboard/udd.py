"""UDD queries and caching for the dashboard."""

import threading
from time import time

import psycopg2

UDD_CONNSTR = (
    "host=udd-mirror.debian.net port=5432 dbname=udd "
    "user=udd-mirror password=udd-mirror connect_timeout=15"
)

CACHE_TTL = 300  # seconds

# One lateral per suite, so a version in -proposed or in an older stable
# release can never be mistaken for the devel release pocket.
QUERY = """
SELECT
    p.pkg                          AS package,
    d.version::text                AS debian_sid,
    dx.version::text               AS debian_experimental,
    ud.version::text               AS ubuntu_devel,
    ud.component                   AS component,
    upp.version::text              AS ubuntu_proposed,
    ul.version::text               AS ubuntu_lts,
    us.upstream_version            AS upstream,
    us.status                      AS watch_status,
    uh.version::text               AS last_upload_version,
    uh.date                        AS last_upload_date,
    uh.signed_by_name              AS last_uploader
FROM unnest(%(packages)s::text[]) AS p(pkg)
LEFT JOIN LATERAL (
    SELECT version FROM sources
    WHERE source = p.pkg AND release = 'sid' AND distribution = 'debian'
    ORDER BY version DESC LIMIT 1
) d ON true
LEFT JOIN LATERAL (
    SELECT version FROM sources
    WHERE source = p.pkg AND release = 'experimental' AND distribution = 'debian'
    ORDER BY version DESC LIMIT 1
) dx ON true
LEFT JOIN LATERAL (
    SELECT version, component FROM ubuntu_sources
    WHERE source = p.pkg AND release = %(devel)s
    ORDER BY version DESC LIMIT 1
) ud ON true
LEFT JOIN LATERAL (
    SELECT version FROM ubuntu_sources
    WHERE source = p.pkg AND release = %(devel_proposed)s
    ORDER BY version DESC LIMIT 1
) upp ON true
LEFT JOIN LATERAL (
    SELECT version FROM ubuntu_sources
    WHERE source = p.pkg AND release = %(lts)s
    ORDER BY version DESC LIMIT 1
) ul ON true
LEFT JOIN LATERAL (
    SELECT upstream_version, status FROM upstream
    WHERE source = p.pkg AND release = 'sid' AND distribution = 'debian'
    ORDER BY upstream_version DESC LIMIT 1
) us ON true
LEFT JOIN LATERAL (
    SELECT version, date, signed_by_name FROM ubuntu_upload_history
    WHERE source = p.pkg AND version = ud.version
    ORDER BY date DESC LIMIT 1
) uh ON true
ORDER BY p.pkg;
"""

class Cache:
    """Time-based cache that keeps serving stale data if UDD goes away.

    Returning HTTP 500 when the mirror hiccups is worse than showing slightly
    old data with a visible timestamp.
    """

    def __init__(self, ttl=CACHE_TTL):
        self.ttl = ttl
        self._lock = threading.Lock()
        self._data = None
        self._fetched_at = 0
        self._error = None

    def get(self, loader, force=False):
        """Return (data, fetched_at, error). error is set only on stale data."""
        # The lock is deliberately held across loader(): concurrent requests
        # then wait for one query instead of each opening its own connection.
        with self._lock:
            fresh = self._data is not None and (time() - self._fetched_at) < self.ttl
            if fresh and not force:
                return self._data, self._fetched_at, None
            try:
                data = loader()
            except Exception as exc:
                self._error = str(exc)
                if self._data is None:
                    raise  # nothing to fall back on
                return self._data, self._fetched_at, self._error
            self._data = data
            self._fetched_at = time()
            self._error = None
            return self._data, self._fetched_at, None


def fetch_rows(packages, devel, lts, connstr=UDD_CONNSTR):
    """Run the dashboard query and return one dict per package."""
    params = {
        "packages": list(packages),
        "devel": devel,
        "devel_proposed": f"{devel}-proposed",
        "lts": lts,
    }
    conn = psycopg2.connect(connstr)
    try:
        with conn.cursor() as cur:
            cur.execute(QUERY, params)
            # Column names come from the cursor so they cannot drift out of
            # step with the SELECT list.
            columns = [d.name for d in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]
    finally:
        conn.close()
