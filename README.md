
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

