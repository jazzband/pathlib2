# some extra tests for coverage

import pytest
import os
from pathlib2 import os_path_realpath, _make_selector, Path


@pytest.mark.skipif(os.name != "nt", reason="Windows only test")
def test_realpath_nt_nul():
    assert os_path_realpath(b'nul') == b'\\\\.\\NUL'
    assert os_path_realpath('nul') == '\\\\.\\NUL'


@pytest.mark.skipif(os.name != "nt", reason="Windows only test")
def test_realpath_nt_unc():
    assert os_path_realpath('\\\\?\\UNC\\localhost\\C$') == '\\\\?\\UNC\\localhost\\C$'


@pytest.mark.skipif(os.name != "nt", reason="Windows only test")
def test_realpath_nt_badpath():
    with pytest.raises(FileNotFoundError):
        os_path_realpath('\\\\invalid\\server')
    with pytest.raises(FileNotFoundError):
        os_path_realpath('does/not/exist', strict=True)


def test_realpath_bytes():
    assert os_path_realpath(b'abc.xyz').endswith(b'abc.xyz')


def test_make_selector():
    with pytest.raises(ValueError, match="Invalid pattern"):
        _make_selector(("x**x",), None)


def test_parents_repr():
    p = Path("/some/path/here")
    assert repr(p.parents).endswith(".parents>")


def test_bad_glob():
    p = Path("some/path")
    files = p.glob("/test/**")
    with pytest.raises(NotImplementedError,
                       match="Non-relative patterns are unsupported"):
        next(files)


@pytest.mark.skipif(os.name != "nt", reason="only for windows")
def test_is_mount_windows():
    p = Path("some/path")
    with pytest.raises(NotImplementedError):
        p.is_mount()
