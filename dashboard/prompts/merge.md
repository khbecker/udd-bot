Prepare an Ubuntu merge of the source package `$package` for the $devel_series
development series.

## Current state

- Ubuntu ($devel_series): `$devel`
- Debian (sid): `$debian`
- Ubuntu delta marker: `$delta`
- Component: `$component`
- Last Ubuntu upload: `$last_upload_version` by $last_uploader on $last_upload_date

Ubuntu carries a delta on this package and Debian is newer, so this needs a
merge, not a sync. The goal is to rebase the Ubuntu delta onto the new Debian
version and drop anything that Debian has since absorbed.

## Steps

1. Clone and start the merge:

       git ubuntu clone $package
       cd $package
       git ubuntu merge start --force ubuntu/devel

2. Review the existing delta before touching anything:

       git ubuntu merge --help
       debdiff <old-debian.dsc> <old-ubuntu.dsc>

   For each change, decide explicitly: keep it, drop it because Debian now
   does the same thing, or drop it because it is no longer relevant. Do not
   carry changes forward without justifying them.

3. Resolve conflicts in `debian/`, paying particular attention to
   `debian/patches/`. Refresh patches that still apply with fuzz, and drop
   patches that Debian has applied upstream or backported.

4. Write the changelog with `git ubuntu merge finish`. The entry must contain
   an accurate "Remaining changes" block listing every delta still carried,
   and a "Dropped changes" block explaining what went away and why. Use
   `dch` conventions and the `$devel_series` distribution.

5. Ensure every remaining patch has a DEP-3 header with `Origin`, `Forwarded`
   and `Bug-Ubuntu`/`Bug-Debian` fields where applicable. Anything Ubuntu
   carries indefinitely should be forwarded to Debian.

6. Build in a clean chroot for the devel series:

       sbuild -d $devel_series

7. Test before uploading:

       autopkgtest --shell-fail ../${package}_*.dsc -- schroot $devel_series-amd64
   Upload to a PPA first and confirm it builds on all architectures.

8. Upload with `dput ubuntu ../${package}_*_source.changes`. If you do not
   have upload rights for `$component`, prepare the merge and request
   sponsorship instead.

## Please produce

- The complete `debian/changelog` entry, including the "Remaining changes"
  and "Dropped changes" blocks.
- A per-change table of the existing delta with a keep/drop recommendation
  and a one-line justification for each.
- The list of patches that need refreshing or dropping.

## Reference

- Debian: https://tracker.debian.org/pkg/$package
- Ubuntu: https://launchpad.net/ubuntu/+source/$package
- Merge report: https://merges.ubuntu.com/$initial/$package/
