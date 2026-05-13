
# kernel team udd link

[Click this link to access kernel-team UDD](https://udd.debian.org/dmd/?email1=&email2=&email3=&packages=bpftrace+crash+dkms+dwarves+ethtool+firmware-sof+iproute2+kdump-tools+kexec-tools+kmod+kpatch+libbpf+linux-base+makedumpfile+rt-tests+strace+wireless-regdb&ignpackages=&format=html#todo).

## Updating package list

1. Modify package-list.txt
2. Run `make`
3. Commit your changes

## Rationale

The goal of this repository and the big UDD URL above is to track userland
packages that the kernel team need and do/should maintain. The generated UDD
page shows which packages need updating, if they have RC bugs in Debian, etc.

The Ubuntu Desktop team has [a package
tracker](https://people.canonical.com/~platform/desktop/versions/versions.html),
but it is less advanced than the UDD tracker, so better just use UDD in the
first place.

## Web dashboard

A local web dashboard is available that shows package versions with
color-coded status, sorting/filtering, links to package trackers, and
AI-generated prompts for updating packages.

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Running

```bash
python3 web.py
```

Then open http://127.0.0.1:5000 in your browser.

Options:
- `--port PORT` — bind to a different port (default: 5000)
- `--host HOST` — bind to a different address (default: 127.0.0.1)
- `--debug` — enable Flask debug/reload mode

