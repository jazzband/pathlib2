#!/usr/bin/python3
"""Test pathlib's handling of Unicode strings."""

import errno
import shutil
import sys
import tempfile

import pathlib2 as pathlib

from test_pathlib2 import support_skip_unless_symlink

if sys.version_info < (2, 7):
    try:
        import unittest2 as unittest
    except ImportError:
        # pylint: disable=raise-missing-from
        raise ImportError("unittest2 is required for tests on pre-2.7")
else:
    import unittest


class TestUnicode(unittest.TestCase):
    """Test the Unicode strings handling of various pathlib2 methods."""

    # pylint: disable=too-many-public-methods

    def examine_path(self, path, name):
        # type: (TestUnicode, pathlib.Path, str) -> None
        """Examine an already-built path."""
        msg = "examining {path!r}: {parts!r}, expect name {name!r}".format(
            path=path,
            parts=path.parts,
            name=name,
        )
        self.assertEqual(path.name, name, msg)
        self.assertIsInstance(path.name, str, msg)
        self.assertTrue(all(isinstance(part, str) for part in path.parts), msg)

    def setUp(self):
        # type: (TestUnicode) -> None
        """Create a temporary directory and a single file in it."""
        self.tempd = tempfile.mkdtemp(prefix="pathlib-test.")
        tempd_etc_b = str(self.tempd).encode("UTF-8") + b"/etc"
        self.base = pathlib.Path(tempd_etc_b.decode("UTF-8"))
        self.base.mkdir(0o755)
        (self.base / "a.file").write_bytes(b"")

    def tearDown(self):
        # type: (TestUnicode) -> None
        """Remove the temporary directory."""
        shutil.rmtree(self.tempd)

    def get_child(self):
        # type: (TestUnicode) -> pathlib.Path
        """Get a <tempd>/etc/passwd path with a Unicode last component."""
        return self.base / b"passwd".decode("UTF-8")

    def test_init(self):
        # type: (TestUnicode) -> None
        """Test that self.base was constructed properly."""
        self.examine_path(self.base, "etc")

    def test_absolute(self):
        # type: (TestUnicode) -> None
        """Test that pathlib.Path.absolute() returns str objects only."""
        self.examine_path(self.base.absolute(), "etc")

    def test_anchor(self):
        # type: (TestUnicode) -> None
        """Test that pathlib.Path.anchor() returns a str object."""
        self.assertIsInstance(self.base.anchor, str)

    def test_glob(self):
        # type: (TestUnicode) -> None
        """Test that pathlib.Path.glob() accepts a Unicode pattern."""
        first_child = next(self.base.glob(b"*".decode("us-ascii")))
        self.examine_path(first_child, "a.file")

    def test_div(self):
        # type: (TestUnicode) -> None
        """Test that div/truediv/rtruediv accepts a Unicode argument."""
        child = self.get_child()
        self.examine_path(child, "passwd")

    def test_joinpath(self):
        # type: (TestUnicode) -> None
        """Test that pathlib.Path.joinpath() accepts a Unicode path."""
        child = self.get_child()
        self.examine_path(child, "passwd")

    def test_match(self):
        # type: (TestUnicode) -> None
        """Test that pathlib.Path.match() accepts a Unicode pattern."""
        self.assertTrue(self.base.match(b"*etc".decode("us-ascii")))

    def test_parent(self):
        # type: (TestUnicode) -> None
        """Test that pathlib.Path.parent() returns str objects."""
        child = self.get_child()
        self.examine_path(child.parent, "etc")

    def test_parents(self):
        # type: (TestUnicode) -> None
        """Test that pathlib.Path.parent() returns str objects."""
        child = self.get_child()
        for parent in child.parents:
            if str(parent) != "/":
                self.examine_path(parent, parent.name)

    def test_relative_to(self):
        # type: (TestUnicode) -> None
        """Test that pathlib.Path.relative_to() accepts a Unicode path."""
        child = self.get_child()
        rel = child.relative_to(
            str(child.parent).encode("UTF-8").decode("UTF-8")
        )
        self.examine_path(rel, "passwd")

    def test_rename(self):
        # type: (TestUnicode) -> None
        """Test that pathlib.Path.rename() accepts a Unicode path."""
        first_child = next(self.base.glob(b"*".decode("us-ascii")))
        try:
            first_child.rename(b"/nonexistent/nah".decode("us-ascii"))
        except OSError as err:
            if err.errno not in (errno.ENOENT, errno.ENOTDIR):
                raise

    def test_replace(self):
        # type: (TestUnicode) -> None
        """Test that pathlib.Path.replace() accepts a Unicode path."""
        first_child = next(self.base.glob(b"*".decode("us-ascii")))
        if sys.version_info >= (3, 3):
            try:
                first_child.replace(b"/nonexistent/nah".decode("us-ascii"))
            except OSError as err:
                if err.errno not in (errno.ENOENT, errno.ENOTDIR):
                    raise

    def test_rglob(self):
        # type: (TestUnicode) -> None
        """Test that pathlib.Path.rglob() accepts a Unicode pattern."""
        first_child = next(self.base.rglob(b"*".decode("us-ascii")))
        self.examine_path(first_child, "a.file")

    def test_root(self):
        # type: (TestUnicode) -> None
        """Test that pathlib.Path.root returns a str object."""
        child = self.get_child()
        self.assertIsInstance(child.root, str)

    def test_samefile(self):
        # type: (TestUnicode) -> None
        """Test that pathlib.Path.samefile() accepts a Unicode path."""
        first_child = next(self.base.rglob(b"*".decode("us-ascii")))
        self.assertFalse(
            first_child.samefile(str(__file__).encode("UTF-8").decode("UTF-8"))
        )

    def test_stem(self):
        # type: (TestUnicode) -> None
        """Test that pathlib.Path.stem returns a str object."""
        child = self.get_child()
        self.assertIsInstance(child.stem, str)

    def test_suffix(self):
        # type: (TestUnicode) -> None
        """Test that pathlib.Path.suffix returns a str object."""
        child = self.get_child()
        self.assertIsInstance(child.suffix, str)

    def test_suffixes(self):
        # type: (TestUnicode) -> None
        """Test that pathlib.Path.suffixes returns str objects."""
        child = self.get_child()
        self.assertTrue(
            all(isinstance(suffix, str) for suffix in child.suffixes)
        )

    @support_skip_unless_symlink
    def test_symlink_to(self):
        # type: (TestUnicode) -> None
        """Test that pathlib.Path.symlink_to() accepts a Unicode path."""
        child = self.get_child()
        first_child = next(self.base.rglob(b"*".decode("us-ascii")))
        self.assertFalse(child.exists(), repr(child.parts))
        child.symlink_to(b"a.file".decode("us-ascii"))
        self.assertTrue(
            child.samefile(first_child),
            repr((child.parts, first_child.parts)),
        )

    def test_with_name(self):
        # type: (TestUnicode) -> None
        """Test that pathlib.Path.with_name() accepts a Unicode name."""
        child = self.get_child()
        child = child.with_name(b"hosts".decode("us-ascii"))
        self.examine_path(child, "hosts")

    def test_with_suffix(self):
        # type: (TestUnicode) -> None
        """Test that pathlib.Path.with_suffix() accepts a Unicode suffix."""
        child = self.get_child()
        child = child.with_suffix(b".txt".decode("us-ascii"))
        self.examine_path(child, "passwd.txt")


def main():
    # type: () -> None
    """Run the tests."""
    unittest.main(__name__)


if __name__ == "__main__":
    main()
