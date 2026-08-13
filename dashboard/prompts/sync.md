Evaluate whether the source package `$package` can be synced from Debian for
the $devel_series development series, dropping the current Ubuntu delta.

## Current state

- Ubuntu ($devel_series): `$devel`
- Debian (sid): `$debian`
- Ubuntu delta marker: `$delta`
- Component: `$component`
- Last Ubuntu upload: `$last_upload_version` by $last_uploader on $last_upload_date

Ubuntu packaged this upstream release ahead of Debian using a `-0ubuntuN`
revision, and Debian has now packaged the same upstream version. In this
situation the Ubuntu packaging is usually redundant and the package can go
back to being a straight sync.

## Do this first

Confirm the Ubuntu delta is genuinely obsolete before dropping it. Syncing
discards every Ubuntu change in one step, so this decision needs evidence,
not assumption:

1. Diff the two packages and enumerate the Ubuntu changes:

       pull-lp-source $package $devel_series
       pull-debian-source $package
       debdiff <debian.dsc> <ubuntu.dsc>

2. For each Ubuntu change, confirm Debian's packaging covers it. Look
   specifically for Ubuntu-specific integration that Debian would not carry:
   apparmor profiles, systemd unit differences, `debian/control` dependency
   changes for Ubuntu-only packages, and any patch referencing a Launchpad
   bug.

3. Check the Ubuntu changelog for changes never forwarded to Debian. Anything
   still needed must be re-applied, which makes this a merge rather than a
   sync.

## If the delta is obsolete

    syncpackage --no-lp -d unstable -s <your-sponsor> $package

If the delta is still needed, treat this as a merge instead and rebase the
remaining changes onto `$debian`.

## Please produce

- A verdict: sync or merge, with the reasoning.
- The enumerated Ubuntu delta with, for each item, evidence that Debian does
  or does not cover it.
- If sync: the exact syncpackage command and the changelog text.
- If merge: the list of changes that must be carried forward.

## Reference

- Debian: https://tracker.debian.org/pkg/$package
- Ubuntu: https://launchpad.net/ubuntu/+source/$package
- Publishing history: https://launchpad.net/ubuntu/+source/$package/+publishinghistory
