import os
import sys
import six
import tempfile
import errno

sys.path.insert(0, os.path.abspath('..'))

import pathlib2


if sys.version_info >= (3, 3):
    import collections.abc as collections_abc
else:
    import collections as collections_abc

if sys.version_info < (2, 7):
    try:
        import unittest2 as unittest
    except ImportError:
        raise ImportError("unittest2 is required for tests on pre-2.7")
else:
    import unittest

if sys.version_info < (3, 3):
    try:
        import mock
    except ImportError:
        raise ImportError("mock is required for tests on pre-3.3")
else:
    from unittest import mock

# assertRaisesRegex is missing prior to Python 3.2
if sys.version_info < (3, 2):
    unittest.TestCase.assertRaisesRegex = unittest.TestCase.assertRaisesRegexp

try:
    from test import support
except ImportError:
    from test import test_support as support

android_not_root = getattr(support, "android_not_root", False)

TESTFN = support.TESTFN

# work around broken support.rmtree on Python 3.3 on Windows
if (os.name == 'nt'
        and sys.version_info >= (3, 0) and sys.version_info < (3, 4)):
    import shutil
    support.rmtree = shutil.rmtree

try:
    import grp
    import pwd
except ImportError:
    grp = pwd = None

# support.can_symlink is missing prior to Python 3
if six.PY2:

    def support_can_symlink():
        return pathlib2.supports_symlinks

    support_skip_unless_symlink = unittest.skipIf(
        not pathlib2.supports_symlinks,
        "symlinks not supported on this platform")
else:
    support_can_symlink = support.can_symlink
    support_skip_unless_symlink = support.skip_unless_symlink


# Backported from 3.4
def fs_is_case_insensitive(directory):
    """Detects if the file system for the specified directory is
    case-insensitive.
    """
    base_fp, base_path = tempfile.mkstemp(dir=directory)
    case_path = base_path.upper()
    if case_path == base_path:
        case_path = base_path.lower()
    try:
        return os.path.samefile(base_path, case_path)
    except OSError as e:
        if e.errno != errno.ENOENT:
            raise
        return False
    finally:
        os.unlink(base_path)


support.fs_is_case_insensitive = fs_is_case_insensitive
