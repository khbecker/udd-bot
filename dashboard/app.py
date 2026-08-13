#!/usr/bin/env python3
"""Web dashboard for kernel team package status.

Shows, for each package in package-list.txt, whether it is in sync with
Debian, needs a merge, can be synced back, or is stuck in -proposed.

Usage: python3 app.py [--host HOST] [--port PORT]
"""

import argparse
import importlib.util
import sys
from datetime import datetime
from pathlib import Path
from string import Template

from flask import Flask, abort, jsonify, render_template, request

import series
import udd
import versions

APP_DIR = Path(__file__).resolve().parent
REPO_DIR = APP_DIR.parent
DEFAULT_PACKAGE_LIST = REPO_DIR / "package-list.txt"
PROMPT_DIR = APP_DIR / "prompts"


def _load_gen_url():
    """Borrow gen_url from the repository's build.py.

    Loaded by path rather than by name: 'build' is also a package on PyPI, so
    a plain import could silently pick up the wrong module.
    """
    spec = importlib.util.spec_from_file_location("_udd_build", REPO_DIR / "build.py")
    if spec is None:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        return module.gen_url
    except (OSError, AttributeError):
        return None


_gen_udd_url = _load_gen_url()

app = Flask(__name__)
app.config["PACKAGE_LIST"] = DEFAULT_PACKAGE_LIST
app.config["DEVEL_SERIES"] = None
app.config["LTS_SERIES"] = None

cache = udd.Cache()


@app.template_filter("timestamp")
def _format_timestamp(value):
    if not value:
        return "never"
    return datetime.fromtimestamp(value).strftime("%H:%M:%S")


def udd_url(packages):
    """Link to the UDD page for these packages, matching the generated README."""
    if _gen_udd_url is None:
        return "https://udd.debian.org/dmd/"
    return _gen_udd_url(packages)


def load_packages(path=None):
    """Read the package list, ignoring blank lines and # comments."""
    path = Path(path or app.config["PACKAGE_LIST"])
    if not path.is_file():
        raise FileNotFoundError(
            f"package list not found: {path}\n"
            "Pass --package-list to point at the repository's package-list.txt."
        )
    packages = []
    with path.open() as handle:
        for line in handle:
            pkg = line.split("#", 1)[0].strip()
            if pkg:
                packages.append(pkg)
    if not packages:
        raise ValueError(f"package list is empty: {path}")
    return packages


# ---------------------------------------------------------------------------
# Row assembly
# ---------------------------------------------------------------------------


#: prompt kind -> (button label, tooltip). Also the whitelist of valid kinds.
PROMPT_LABELS = {
    "merge": ("Merge", "Generate a prompt to rebase the Ubuntu delta onto the newer Debian version"),
    "sync": ("Sync", "Generate a prompt to check whether the Ubuntu delta can be dropped and the package synced"),
    "new-upstream-debian": ("New upstream", "Generate a prompt to package the new upstream release in Debian"),
    "investigate-proposed": ("Investigate", "Generate a prompt to find why this is stuck in -proposed"),
}

#: versions.STATE_INFO tone -> Vanilla Framework status-label modifier. Keeps
#: CSS class names out of the classification logic.
TONE_CLASS = {
    "ok": "positive",
    "info": "information",
    "warn": "caution",
    "action": "negative",
}


def prompt_kinds(state, upstream_state, dif_passed):
    """Prompts valid for this state, most relevant first.

    Offering only valid actions stops the dashboard suggesting an upload for
    something already sitting in -proposed.
    """
    kinds = []
    if state == versions.IN_PROPOSED:
        kinds.append("investigate-proposed")
    elif state == versions.MERGE_NEEDED:
        kinds.append("merge")
    elif state == versions.SYNC_AVAILABLE:
        kinds.extend(["sync", "merge"])
    elif state == versions.AUTOSYNC_PENDING and dif_passed:
        kinds.append("sync")  # before DIF this syncs itself
    if upstream_state == versions.UPSTREAM_NEWER:
        kinds.append("new-upstream-debian")
    return kinds


def build_rows(raw_rows, dif_passed):
    """Turn query rows into template rows: state, delta, prompts, formatting."""
    rows = []
    for raw in raw_rows:
        info = versions.classify(
            devel=raw["ubuntu_devel"],
            proposed=raw["ubuntu_proposed"],
            debian=raw["debian_sid"],
        )
        label, tone, explanation = versions.STATE_INFO[info["state"]]
        upstream_state = versions.classify_upstream(raw["watch_status"])
        row = dict(raw)
        row.update(
            state=info["state"],
            state_label=label,
            state_class=TONE_CLASS[tone],
            state_explanation=explanation,
            delta=info["delta"],
            in_proposed=info["in_proposed"],
            native=info["native"],
            upstream_state=upstream_state,
            actionable=info["state"] in versions.ACTIONABLE,
            prompts=[
                {"kind": k, "label": PROMPT_LABELS[k][0], "title": PROMPT_LABELS[k][1]}
                for k in prompt_kinds(info["state"], upstream_state, dif_passed)
            ],
            last_upload_date=(
                raw["last_upload_date"].strftime("%Y-%m-%d")
                if raw["last_upload_date"]
                else None
            ),
        )
        rows.append(row)
    return rows


def get_context(force=False):
    devel = series.devel_series(app.config["DEVEL_SERIES"])
    lts = series.lts_series(app.config["LTS_SERIES"])
    dif_passed, dif_when, dif_days = series.freeze_state(devel)

    def loader():
        return udd.fetch_rows(load_packages(), devel, lts)

    raw_rows, fetched_at, stale_error = cache.get(loader, force=force)
    rows = build_rows(raw_rows, dif_passed)
    return {
        "packages": rows,
        "devel_series": devel,
        "lts_series": lts,
        "series_resolved": series.resolved_by_distro_info(),
        "dif_passed": dif_passed,
        "dif_date": dif_when.isoformat() if dif_when else None,
        "dif_days": dif_days,
        "fetched_at": fetched_at,
        "stale_error": stale_error,
        "action_count": sum(1 for r in rows if r["actionable"]),
        "udd_url": udd_url([r["package"] for r in rows]),
    }


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------


def render_prompt(kind, row, devel, lts):
    """Fill a prompts/*.md template with this package's current state."""
    if kind not in PROMPT_LABELS:
        abort(404, f"unknown prompt kind: {kind}")
    path = PROMPT_DIR / f"{kind}.md"
    if not path.is_file():
        abort(404, f"missing prompt template: {kind}")
    context = {
        "package": row["package"],
        "initial": row["package"][0],  # merges.ubuntu.com path component
        "devel": row["ubuntu_devel"] or "(not in devel)",
        "proposed": row["ubuntu_proposed"] or "(nothing in proposed)",
        "debian": row["debian_sid"] or "(not in Debian)",
        "debian_experimental": row["debian_experimental"] or "(none)",
        "lts": row["ubuntu_lts"] or "(not in LTS)",
        "upstream": row["upstream"] or "(unknown)",
        "component": row["component"] or "(unknown)",
        "delta": row["delta"] or "(none)",
        "last_upload_version": row["last_upload_version"] or "(unknown)",
        "last_uploader": row["last_uploader"] or "(unknown)",
        "last_upload_date": row["last_upload_date"] or "(unknown)",
        "devel_series": devel,
        "lts_series": lts,
    }
    # safe_substitute leaves unknown $placeholders alone rather than raising,
    # so a typo in a template degrades to visible text instead of a 500.
    return Template(path.read_text()).safe_substitute(context)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    try:
        context = get_context(force=request.args.get("refresh") == "1")
    except Exception as exc:
        return render_template("error.html", error=str(exc)), 500
    return render_template("index.html", **context)


@app.route("/api/packages")
def api_packages():
    try:
        context = get_context()
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify(context)


@app.route("/api/prompt/<package>")
def api_prompt(package):
    kind = request.args.get("kind", "merge")
    try:
        context = get_context()
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    for row in context["packages"]:
        if row["package"] == package:
            text = render_prompt(
                kind, row, context["devel_series"], context["lts_series"]
            )
            return jsonify({"package": package, "kind": kind, "prompt": text})
    return jsonify({"error": f"unknown package: {package}"}), 404


def main():
    parser = argparse.ArgumentParser(
        description="Kernel team package status dashboard"
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=5000, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument(
        "--package-list",
        default=DEFAULT_PACKAGE_LIST,
        help="Path to package-list.txt (default: ../package-list.txt)",
    )
    parser.add_argument("--series", help="Override the devel series name")
    parser.add_argument("--lts", help="Override the LTS series name")
    args = parser.parse_args()

    app.config["PACKAGE_LIST"] = Path(args.package_list)
    app.config["DEVEL_SERIES"] = args.series
    app.config["LTS_SERIES"] = args.lts

    try:
        load_packages()
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Starting dashboard on http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


if __name__ == "__main__":
    sys.exit(main())
