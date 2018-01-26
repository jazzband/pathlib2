import os as std_os
import shutil
import sys
import tempfile

import pytest

import pathlib2 as pathlib

compat_os = pathlib.compat.os

compat_open = pathlib.compat.open
std_open = open

P = pathlib.Path

FILE_NAME = 'my.file'
DEEP_FILE_COMPONENTS = ('path', 'to', FILE_NAME)


@pytest.fixture
def tmp_dir(request):
    path = str(tempfile.mkdtemp(suffix='{}.{}'.format(request.module.__name__, request.function.__name__)))
    assert len(std_os.listdir(path)) == 0
    yield path
    shutil.rmtree(path, True)


@pytest.fixture
def tmp_file(tmp_dir):
    file_path = std_os.path.join(tmp_dir, FILE_NAME)
    with std_open(file_path, 'w') as f:
        f.write('file contents')
    return file_path


@pytest.mark.parametrize('std_mod,compat_mod', (
        (std_os, compat_os),
        (std_os.path, compat_os.path)
))
def test_module_replacement(std_mod, compat_mod):
    """Tests whether the shims are applied as appropriate (i.e. only in < py3.6)"""
    assert (std_mod != compat_mod) == (sys.version_info < (3, 6))


# OS FUNCTION TESTS

def test_listdir():
    path = '.'
    assert std_os.listdir(path) == compat_os.listdir(P(path))


# OS.PATH FUNCTION TESTS

def test_path_join():
    ref = std_os.path.join(*DEEP_FILE_COMPONENTS)
    test = compat_os.path.join(*[P(item) for item in DEEP_FILE_COMPONENTS])

    assert ref == test
