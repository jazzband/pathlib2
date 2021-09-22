# some extra tests for coverage

import pytest
import os
from pathlib2 import os_path_realpath


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


def test_realpath_bytes():
    assert os_path_realpath(b'abc.xyz').endswith(b'abc.xyz')
