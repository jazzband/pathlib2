UNICODE_TEST_FILE=tests/test_pathlib2_unicode.py

.PHONY: test
test: install-dev
	pytest;

.PHONY: unicode-test
unicode-test: unicode-testfile
	@make test;

.PHONY: unicode-testfile
unicode-testfile:
	@echo "from __future__ import unicode_literals" > $(UNICODE_TEST_FILE); \
	cat tests/test_pathlib2.py >> $(UNICODE_TEST_FILE);

.PHONY: install
install:
	pip install .

.PHONY: install-dev
install-dev:
	pip install -e .

.PHONY: clean
clean: rm-unicode-testfile
	rm -rf .cache .tox pathlib2.egg-info

.PHONY: rm-unicode-testfile
rm-unicode-testfile:
	rm -f $(UNICODE_TEST_FILE)
