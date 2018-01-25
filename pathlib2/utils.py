import ctypes
import os
import sys
from errno import EEXIST, ENOENT, EPERM, EACCES

import six


def _py2_fsencode(parts):
    # py2 => minimal unicode support
    assert six.PY2
    return [part.encode('ascii') if isinstance(part, six.text_type)
            else part for part in parts]


def _try_except_fileexistserror(try_func, except_func, else_func=None):
    if sys.version_info >= (3, 3):
        try:
            try_func()
        except FileExistsError as exc:
            except_func(exc)
        else:
            if else_func is not None:
                else_func()
    else:
        try:
            try_func()
        except EnvironmentError as exc:
            if exc.errno != EEXIST:
                raise
            else:
                except_func(exc)
        else:
            if else_func is not None:
                else_func()


def _try_except_filenotfounderror(try_func, except_func):
    if sys.version_info >= (3, 3):
        try:
            try_func()
        except FileNotFoundError as exc:
            except_func(exc)
    else:
        try:
            try_func()
        except EnvironmentError as exc:
            if exc.errno != ENOENT:
                raise
            else:
                except_func(exc)


def _try_except_permissionerror_iter(try_iter, except_iter):
    if sys.version_info >= (3, 3):
        try:
            for x in try_iter():
                yield x
        except PermissionError as exc:
            for x in except_iter(exc):
                yield x
    else:
        try:
            for x in try_iter():
                yield x
        except EnvironmentError as exc:
            if exc.errno not in (EPERM, EACCES):
                raise
            else:
                for x in except_iter(exc):
                    yield x


def _win32_get_unique_path_id(path):
    # get file information, needed for samefile on older Python versions
    # see http://timgolden.me.uk/python/win32_how_do_i/
    # see_if_two_files_are_the_same_file.html
    from ctypes import POINTER, Structure, WinError
    from ctypes.wintypes import DWORD, HANDLE, BOOL

    class FILETIME(Structure):
        _fields_ = [("datetime_lo", DWORD),
                    ("datetime_hi", DWORD),
                    ]

    class BY_HANDLE_FILE_INFORMATION(Structure):
        _fields_ = [("attributes", DWORD),
                    ("created_at", FILETIME),
                    ("accessed_at", FILETIME),
                    ("written_at", FILETIME),
                    ("volume", DWORD),
                    ("file_hi", DWORD),
                    ("file_lo", DWORD),
                    ("n_links", DWORD),
                    ("index_hi", DWORD),
                    ("index_lo", DWORD),
                    ]

    CreateFile = ctypes.windll.kernel32.CreateFileW
    CreateFile.argtypes = [ctypes.c_wchar_p, DWORD, DWORD, ctypes.c_void_p,
                           DWORD, DWORD, HANDLE]
    CreateFile.restype = HANDLE
    GetFileInformationByHandle = (
        ctypes.windll.kernel32.GetFileInformationByHandle)
    GetFileInformationByHandle.argtypes = [
        HANDLE, POINTER(BY_HANDLE_FILE_INFORMATION)]
    GetFileInformationByHandle.restype = BOOL
    CloseHandle = ctypes.windll.kernel32.CloseHandle
    CloseHandle.argtypes = [HANDLE]
    CloseHandle.restype = BOOL
    GENERIC_READ = 0x80000000
    FILE_SHARE_READ = 0x00000001
    FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
    OPEN_EXISTING = 3
    if os.path.isdir(path):
        flags = FILE_FLAG_BACKUP_SEMANTICS
    else:
        flags = 0
    hfile = CreateFile(path, GENERIC_READ, FILE_SHARE_READ,
                       None, OPEN_EXISTING, flags, None)
    if hfile == 0xffffffff:
        if sys.version_info >= (3, 3):
            raise FileNotFoundError(path)
        else:
            exc = OSError("file not found: path")
            exc.errno = ENOENT
            raise exc
    info = BY_HANDLE_FILE_INFORMATION()
    success = GetFileInformationByHandle(hfile, info)
    CloseHandle(hfile)
    if success == 0:
        raise WinError()
    return info.volume, info.index_hi, info.index_lo
