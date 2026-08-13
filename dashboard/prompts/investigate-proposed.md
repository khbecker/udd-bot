Investigate why `$package` is stuck in `$devel_series-proposed` instead of
migrating to the release pocket.

## Current state

- Ubuntu ($devel_series, release pocket): `$devel`
- Ubuntu ($devel_series-proposed): `$proposed`
- Debian (sid): `$debian`
- Component: `$component`
- Last Ubuntu upload: `$last_upload_version` by $last_uploader on $last_upload_date

The upload already exists; nobody needs to prepare another one. The work is to
find and clear the migration blocker.

## Steps

1. Read the excuse for this package on the update-excuses page and identify
   the specific blocker:

       https://ubuntu-archive-team.ubuntu.com/proposed-migration/update_excuses.html#$package

2. Classify the blocker. The usual causes are:
   - **Failing autopkgtest**, either its own or a reverse dependency's.
     Check whether the regression is real or a flaky test.
   - **Uninstallable binaries** on one or more architectures.
   - **Missing builds**, including a build still running or failed on an
     architecture.
   - **Blocked by a britney hint** or a block-proposed tag.
   - **Waiting on another package** that must migrate at the same time.

3. For autopkgtest regressions, determine whether the failure is caused by
   this package or by the test environment. Retry flaky tests via the
   autopkgtest request page; fix genuine regressions with a new upload.

4. For uninstallability, check whether a dependency is also stuck in
   -proposed, in which case the two need to migrate together.

## Please produce

- The specific reason this package is not migrating.
- Whether the fix is a retry, a new upload, a hint request to the archive
  admins, or waiting on another package.
- If a new upload is needed, the changelog entry describing the fix.

## Reference

- Update excuses: https://ubuntu-archive-team.ubuntu.com/proposed-migration/update_excuses.html#$package
- Ubuntu: https://launchpad.net/ubuntu/+source/$package
- Publishing history: https://launchpad.net/ubuntu/+source/$package/+publishinghistory
