Package the new upstream release of `$package` **in Debian**, version
`$upstream`.

## Current state

- Debian (sid): `$debian`
- Debian (experimental): `$debian_experimental`
- Upstream: `$upstream`
- Ubuntu ($devel_series): `$devel`
- Component: `$component`

## Why Debian and not Ubuntu

New upstream versions should land in Debian first and reach Ubuntu by sync or
merge. Importing a new upstream release directly into Ubuntu creates a
permanent delta that somebody has to carry at every subsequent merge, and it
diverges the two archives for no benefit. Only package a new upstream version
directly in Ubuntu when there is a specific, time-critical reason, and record
that reason in the changelog.

If the kernel team maintains this package in Debian, do the work there. If it
is maintained by someone else, file a bug or contact the maintainer rather
than NMU-ing without warning.

## Steps

1. Clone the packaging repository from salsa.debian.org and import the new
   upstream release:

       gbp import-orig --uscan --pristine-tar

2. Update `debian/changelog` for the new upstream version.

3. Refresh `debian/patches`. Drop anything applied upstream and update DEP-3
   headers on what remains.

4. Check for packaging changes the new release requires: soname changes,
   new or removed binaries, `debian/control` build-dependency updates, and
   `debian/*.symbols` updates.

5. Build and test:

       sbuild -d unstable
       autopkgtest ../${package}_*.dsc -- schroot unstable-amd64
       lintian -i ../${package}_*.changes

6. Close any Debian bugs the new release fixes in the changelog.

## Afterwards

Once the new version is in sid, Ubuntu picks it up by autosync if the package
has no Ubuntu delta. If Ubuntu carries a delta, follow up with a merge.
Current Ubuntu version is `$devel`.

## Please produce

- The `debian/changelog` entry.
- The list of patches to drop or refresh.
- Any `debian/control` changes the new upstream release requires.

## Reference

- Debian: https://tracker.debian.org/pkg/$package
- Upstream scan: https://qa.debian.org/cgi-bin/watch?pkg=$package
