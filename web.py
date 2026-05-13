#!/usr/bin/env python3
"""Web dashboard for kernel team package status.

Queries the Debian UDD public mirror and displays an interactive table
with version info, color-coded status, sorting/filtering, and links to
package trackers.

Requires: flask, psycopg2-binary
    pip install flask psycopg2-binary

Usage: python3 web.py [--port PORT] [--host HOST]
"""

import os
import re
import sys
from functools import lru_cache
from time import time

from flask import Flask, render_template_string

try:
    import psycopg2
except ImportError:
    print("Error: psycopg2 is required. Install with: pip install psycopg2-binary",
          file=sys.stderr)
    sys.exit(1)

app = Flask(__name__)

UDD_CONNSTR = "host=udd-mirror.debian.net port=5432 dbname=udd user=udd-mirror password=udd-mirror"

QUERY = """
SELECT
    p.pkg AS package,
    COALESCE(d.version::text, '-') AS debian_sid,
    COALESCE(u.version::text, '-') AS ubuntu_devel,
    COALESCE(up.upstream_version, '-') AS upstream,
    COALESCE(up.status, '') AS watch_status
FROM unnest(%(packages)s::text[]) AS p(pkg)
LEFT JOIN LATERAL (
    SELECT version
    FROM sources
    WHERE source = p.pkg AND release = 'sid'
    ORDER BY version DESC
    LIMIT 1
) d ON true
LEFT JOIN LATERAL (
    SELECT version
    FROM ubuntu_sources
    WHERE source = p.pkg
    ORDER BY version DESC
    LIMIT 1
) u ON true
LEFT JOIN LATERAL (
    SELECT upstream_version, status
    FROM upstream
    WHERE source = p.pkg AND release = 'sid'
    LIMIT 1
) up ON true
ORDER BY p.pkg;
"""

CACHE_TTL = 300  # 5 minutes
_cache = {"data": None, "time": 0}


def load_packages():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pkg_list = os.path.join(script_dir, "package-list.txt")
    packages = []
    with open(pkg_list) as f:
        for line in f:
            pkg = line.strip()
            if pkg:
                packages.append(pkg)
    return packages


def _order(c):
    """Debian version character ordering: ~ < empty < alphanumeric < everything else."""
    if c == '~':
        return -1
    if c == '':
        return 0
    if c.isalpha():
        return ord(c)
    return ord(c) + 256


def _deb_version_cmp_part(a, b):
    """Compare two version strings using Debian's algorithm."""
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


def deb_version_compare(a, b):
    """Compare two Debian version strings. Returns <0, 0, or >0."""
    if ':' in a:
        ea, a = a.split(':', 1)
    else:
        ea = '0'
    if ':' in b:
        eb, b = b.split(':', 1)
    else:
        eb = '0'
    if int(ea) != int(eb):
        return -1 if int(ea) < int(eb) else 1
    if '-' in a:
        ua, ra = a.rsplit('-', 1)
    else:
        ua, ra = a, '0'
    if '-' in b:
        ub, rb = b.rsplit('-', 1)
    else:
        ub, rb = b, '0'
    c = _deb_version_cmp_part(ua, ub)
    if c != 0:
        return c
    return _deb_version_cmp_part(ra, rb)


def classify_ubuntu(ubu_ver, deb_ver):
    """Return 'behind', 'same', or 'ahead'."""
    if ubu_ver == '-' or deb_ver == '-':
        return "unknown"
    ubu_base = re.sub(r'ubuntu\d*$', '', ubu_ver)
    if ubu_base == deb_ver:
        return "same"
    if deb_version_compare(ubu_base, deb_ver) < 0:
        return "behind"
    return "same"


def fetch_data():
    now = time()
    if _cache["data"] and (now - _cache["time"]) < CACHE_TTL:
        return _cache["data"]

    packages = load_packages()
    conn = psycopg2.connect(UDD_CONNSTR)
    cur = conn.cursor()
    cur.execute(QUERY, {"packages": packages})
    rows = cur.fetchall()
    conn.close()

    result = []
    for row in rows:
        pkg, deb_ver, ubu_ver, upstream, status = row
        ubu_status = classify_ubuntu(ubu_ver, deb_ver)
        ubu_base = re.sub(r'ubuntu\d*$', '', ubu_ver) if ubu_ver != '-' else '-'
        debian_is_newer = (deb_ver != '-' and ubu_base != '-'
                           and deb_version_compare(ubu_base, deb_ver) < 0)
        result.append({
            "package": pkg,
            "debian_sid": deb_ver,
            "ubuntu_devel": ubu_ver,
            "upstream": upstream,
            "watch_status": status,
            "ubuntu_status": ubu_status,
            "debian_is_newer": debian_is_newer,
        })

    _cache["data"] = result
    _cache["time"] = now
    return result


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kernel Team Package Status</title>
<style>
  :root {
    --bg: #1a1a2e;
    --surface: #16213e;
    --text: #e0e0e0;
    --muted: #888;
    --border: #2a2a4a;
    --green: #4caf50;
    --yellow: #ff9800;
    --red: #f44336;
    --link: #64b5f6;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, monospace;
    background: var(--bg);
    color: var(--text);
    padding: 2rem;
    line-height: 1.6;
  }
  h1 { margin-bottom: 0.5rem; font-size: 1.5rem; }
  .subtitle { color: var(--muted); margin-bottom: 1.5rem; font-size: 0.9rem; }
  .filter-bar {
    margin-bottom: 1rem;
    display: flex;
    gap: 1rem;
    align-items: center;
    flex-wrap: wrap;
  }
  .filter-bar input {
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 0.4rem 0.8rem;
    border-radius: 4px;
    font-size: 0.9rem;
    width: 250px;
  }
  .filter-bar select {
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 0.4rem 0.8rem;
    border-radius: 4px;
    font-size: 0.9rem;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    background: var(--surface);
    border-radius: 8px;
    overflow: hidden;
  }
  th, td {
    padding: 0.6rem 1rem;
    text-align: left;
    border-bottom: 1px solid var(--border);
  }
  th {
    background: var(--border);
    white-space: nowrap;
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  tr:hover { background: rgba(255,255,255,0.03); }
  .status-same { color: var(--green); }
  .status-behind { color: var(--yellow); }
  .status-newer { color: var(--red); }
  .status-unknown { color: var(--muted); }
  a { color: var(--link); text-decoration: none; }
  a:hover { text-decoration: underline; }
  .links { font-size: 0.8rem; white-space: nowrap; }
  .links a { margin-right: 0.5rem; }
  .links button {
    background: var(--border);
    border: 1px solid var(--muted);
    color: var(--text);
    padding: 0.2rem 0.5rem;
    border-radius: 3px;
    font-size: 0.75rem;
    cursor: pointer;
    margin-right: 0.3rem;
  }
  .links button:hover { background: #3a3a5a; }
  .modal-overlay {
    display: none;
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.7);
    z-index: 1000;
    align-items: center;
    justify-content: center;
  }
  .modal-overlay.active { display: flex; }
  .modal {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1.5rem;
    max-width: 700px;
    width: 90%;
    max-height: 80vh;
    overflow-y: auto;
  }
  .modal h2 { margin-bottom: 1rem; font-size: 1.1rem; }
  .modal pre {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 1rem;
    white-space: pre-wrap;
    font-size: 0.85rem;
    line-height: 1.5;
  }
  .modal .btn-row {
    margin-top: 1rem;
    display: flex;
    gap: 0.5rem;
  }
  .modal button {
    background: var(--border);
    border: 1px solid var(--muted);
    color: var(--text);
    padding: 0.4rem 1rem;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.85rem;
  }
  .modal button:hover { background: #3a3a5a; }
  .modal button.primary { background: var(--link); color: #000; border-color: var(--link); }
  .modal button.primary:hover { opacity: 0.8; }
  .legend {
    margin-top: 1.5rem;
    font-size: 0.85rem;
    color: var(--muted);
  }
  .legend span { margin-right: 1.5rem; }
  .dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 4px; vertical-align: middle; }
  .dot-green { background: var(--green); }
  .dot-yellow { background: var(--yellow); }
  .dot-red { background: var(--red); }
</style>
</head>
<body>
<h1>Kernel Team Package Status</h1>
<p class="subtitle">Data from UDD public mirror &middot; cached for 5 minutes &middot; {{ packages|length }} packages</p>

<div class="filter-bar">
  <input type="text" id="filter" placeholder="Filter packages..." oninput="filterTable()">
  <select id="statusFilter" onchange="filterTable()">
    <option value="">All statuses</option>
    <option value="behind">Ubuntu behind Debian</option>
    <option value="newer">Newer upstream available</option>
    <option value="ok">Up to date</option>
  </select>
</div>

<table id="pkgTable">
<thead>
<tr>
  <th>Package</th>
  <th>Debian (sid)</th>
  <th>Ubuntu (devel)</th>
  <th>Upstream</th>
  <th>Status</th>
  <th>Links</th>
</tr>
</thead>
<tbody>
{% for p in packages %}
<tr data-pkg="{{ p.package }}" data-ubuntu-status="{{ p.ubuntu_status }}" data-watch-status="{{ p.watch_status }}">
  <td><strong>{{ p.package }}</strong></td>
  <td>{{ p.debian_sid }}</td>
  <td class="{% if p.ubuntu_status == 'behind' %}status-behind{% elif p.ubuntu_status == 'same' %}status-same{% endif %}">
    {{ p.ubuntu_devel }}
  </td>
  <td class="{% if p.watch_status == 'newer package available' %}status-newer{% elif p.watch_status == 'up to date' %}status-same{% endif %}">
    {{ p.upstream }}
  </td>
  <td class="{% if p.watch_status == 'newer package available' %}status-newer{% elif p.ubuntu_status == 'behind' %}status-behind{% else %}status-same{% endif %}">
    {% if p.watch_status == 'newer package available' %}Upstream newer
    {% elif p.ubuntu_status == 'behind' %}Ubuntu behind
    {% elif p.watch_status == 'up to date' and p.ubuntu_status == 'same' %}Up to date
    {% else %}—{% endif %}
  </td>
  <td class="links">
    <a href="https://tracker.debian.org/pkg/{{ p.package }}" target="_blank">Debian</a>
    <a href="https://launchpad.net/ubuntu/+source/{{ p.package }}" target="_blank">Ubuntu</a>
    {% if p.watch_status == 'newer package available' %}
    <button onclick="showPrompt('debian', '{{ p.package }}', '{{ p.debian_sid }}', '{{ p.upstream }}')">🤖 Debian</button>
    {% endif %}
    {% if p.ubuntu_status == 'behind' or p.watch_status == 'newer package available' %}
    <button onclick="showPrompt('ubuntu', '{{ p.package }}', '{{ p.ubuntu_devel }}', '{{ p.debian_sid }}', '{{ p.upstream }}', {{ p.debian_is_newer | tojson }})">🤖 Ubuntu</button>
    {% endif %}
  </td>
</tr>
{% endfor %}
</tbody>
</table>

<div class="legend">
  <span><span class="dot dot-green"></span> Up to date</span>
  <span><span class="dot dot-yellow"></span> Ubuntu behind Debian</span>
  <span><span class="dot dot-red"></span> Newer upstream available</span>
</div>

<div class="modal-overlay" id="promptModal" onclick="closeModal(event)">
  <div class="modal">
    <h2 id="modalTitle">AI Prompt</h2>
    <pre id="modalPrompt"></pre>
    <div class="btn-row">
      <button class="primary" onclick="copyPrompt()">📋 Copy to clipboard</button>
      <button onclick="document.getElementById('promptModal').classList.remove('active')">Close</button>
    </div>
  </div>
</div>

<script>
function filterTable() {
  const text = document.getElementById('filter').value.toLowerCase();
  const status = document.getElementById('statusFilter').value;
  const rows = document.querySelectorAll('#pkgTable tbody tr');
  rows.forEach(row => {
    const pkg = row.dataset.pkg;
    const uStatus = row.dataset.ubuntuStatus;
    const wStatus = row.dataset.watchStatus;
    let show = pkg.includes(text);
    if (show && status === 'behind') show = uStatus === 'behind';
    else if (show && status === 'newer') show = wStatus === 'newer package available';
    else if (show && status === 'ok') show = uStatus !== 'behind' && wStatus !== 'newer package available';
    row.style.display = show ? '' : 'none';
  });
}

function showPrompt(type, pkg, currentVer, ...args) {
  let prompt;
  if (type === 'debian') {
    const upstream = args[0];
    prompt = `Update the Debian package "${pkg}" from version ${currentVer} to new upstream version ${upstream}.

Steps:
1. Clone the Debian packaging repo from salsa.debian.org for ${pkg}
2. Import the new upstream tarball (version ${upstream}) using gbp import-orig or uscan
3. Update debian/changelog with a new entry for the upstream release
4. Check debian/patches — refresh or drop patches that are no longer needed
5. Build the package with sbuild or dpkg-buildpackage and fix any FTBFS issues
6. Run autopkgtest if the package has tests
7. Verify the package installs and runs correctly (lintian clean)

Reference: https://tracker.debian.org/pkg/${pkg}`;
  } else {
    const debVer = args[0];
    const upstream = args[1];
    const debIsNewer = args[2];
    const targetVer = (upstream && upstream !== '-') ? upstream : debVer;
    const mergeStep = debIsNewer
      ? `3. Merge or sync with the latest Debian version (${debVer}) from sid
4. Resolve any conflicts in debian/ (especially patches and changelog)
5. `
      : `3. `;
    prompt = `Update the Ubuntu package "${pkg}" from version ${currentVer} to upstream version ${targetVer}.

Steps:
1. Pull the current Ubuntu packaging from Launchpad: pull-lp-source ${pkg}
2. Import the new upstream tarball (version ${targetVer}) using uscan or gbp import-orig
${debIsNewer ? `3. Merge or sync with the latest Debian version (${debVer}) from sid
4. Resolve any conflicts in debian/ (especially patches and changelog)
5. Update debian/changelog using dch with the appropriate ubuntu suffix
6. Check debian/patches — refresh or drop patches that no longer apply
7. Build in a clean chroot with sbuild targeting the current devel series
8. Run autopkgtest and verify installability
9. Upload to the appropriate PPA or propose via git-ubuntu` : `3. Update debian/changelog using dch with the appropriate ubuntu suffix
4. Check debian/patches — refresh or drop patches that no longer apply
5. Build in a clean chroot with sbuild targeting the current devel series
6. Run autopkgtest and verify installability
7. Upload to the appropriate PPA or propose via git-ubuntu`}

Reference:
- Debian: https://tracker.debian.org/pkg/${pkg}
- Ubuntu: https://launchpad.net/ubuntu/+source/${pkg}`;
  }

  document.getElementById('modalTitle').textContent = `AI Prompt: Update ${pkg} (${type})`;
  document.getElementById('modalPrompt').textContent = prompt;
  document.getElementById('promptModal').classList.add('active');
}

function closeModal(event) {
  if (event.target === document.getElementById('promptModal')) {
    document.getElementById('promptModal').classList.remove('active');
  }
}

function copyPrompt() {
  const text = document.getElementById('modalPrompt').textContent;
  navigator.clipboard.writeText(text).then(() => {
    const btn = document.querySelector('.modal .primary');
    btn.textContent = '✓ Copied!';
    setTimeout(() => { btn.textContent = '📋 Copy to clipboard'; }, 2000);
  });
}
</script>
</body>
</html>
"""


@app.route("/")
def index():
    try:
        packages = fetch_data()
    except Exception as e:
        return f"<h1>Error</h1><pre>{e}</pre>", 500
    return render_template_string(HTML_TEMPLATE, packages=packages)


@app.route("/api/packages")
def api_packages():
    from flask import jsonify
    try:
        packages = fetch_data()
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify(packages)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Kernel team package status dashboard")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=5000, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    print(f"Starting dashboard on http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)
