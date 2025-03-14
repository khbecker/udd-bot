import urllib.parse

URL = "https://udd.debian.org/dmd/"

TEMPLATE = """
# kernel team udd link

[Click this link to access kernel-team UDD]({url}).

## Updating package list

1. Modify package-list.txt
2. Run `make`
3. Commit your changes
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
