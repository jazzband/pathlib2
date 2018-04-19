#!/bin/sh

echo "from __future__ import unicode_literals" > tests/test_unicode_literals.py
cat tests/test_pathlib2.py >> tests/test_unicode_literals.py
