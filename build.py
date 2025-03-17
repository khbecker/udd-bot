import urllib.parse

URL = "https://udd.debian.org/dmd/"

TEMPLATE = """
# kernel team udd link

[Click this link to access kernel-team UDD]({url}).

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
"""


def gen_url(packages: list[str]) -> str:
    """Generate an URL for a list of packages.

    >>> gen_url(["foo", "bar"])
    'https://udd.debian.org/dmd/?email1=&email2=&email3=&packages=foo+bar&ignpackages=&format=html#todo'

    """
    params = {
        "email1": "",
        "email2": "",
        "email3": "",
        "packages": " ".join(packages),
        "ignpackages": "",
        "format": "html",
    }
    params = urllib.parse.urlencode(params)

    return f"{URL}?{params}#todo"


def main():
    import fileinput

    packages = [l.strip() for l in fileinput.input()]
    url = gen_url(packages)

    print(TEMPLATE.format(url=url))


if __name__ == "__main__":
    main()
