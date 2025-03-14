
.PHONY: all
all: README.md

README.md: build.py package-list.txt
	python3 build.py < package-list.txt > README.md

.PHONY: test
test:
	python3 -m doctest build.py
