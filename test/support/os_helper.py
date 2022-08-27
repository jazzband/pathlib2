import collections.abc
import contextlib
import errno
import os
import re
import stat
import sys
import time
import unittest
import warnings


# Filename used for testing
if os.name == 'java':
    # Jython disallows @ in module names
    TESTFN_ASCII = '$test'
else:
    TESTFN_ASCII = '@test'

# Disambiguate TESTFN for parallel testing, while letting it remain a valid
# module name.
TESTFN_ASCII = "{}_{}_tmp".format(TESTFN_ASCII, os.getpid())

# TESTFN_UNICODE is a non-ascii filename
TESTFN_UNICODE = TESTFN_ASCII + "-\xe0\xf2\u0258\u0141\u011f"
if sys.platform == 'darwin':
    # In Mac OS X's VFS API file names are, by definition, canonically
    # decomposed Unicode, encoded using UTF-8. See QA1173:
    # http://developer.apple.com/mac/library/qa/qa2001/qa1173.html
    import unicodedata
    TESTFN_UNICODE = unicodedata.normalize('NFD', TESTFN_UNICODE)

# TESTFN_UNENCODABLE is a filename (str type) that should *not* be able to be
# encoded by the filesystem encoding (in strict mode). It can be None if we
# cannot generate such filename.
TESTFN_UNENCODABLE = None
if os.name == 'nt':
    # skip win32s (0) or Windows 9x/ME (1)
    if sys.getwindowsversion().platform >= 2:
        # Different kinds of characters from various languages to minimize the
        # probability that the whole name is encodable to MBCS (issue #9819)
        TESTFN_UNENCODABLE = TESTFN_ASCII + "-\u5171\u0141\u2661\u0363\uDC80"
        try:
            TESTFN_UNENCODABLE.encode(sys.getfilesystemencoding())
        except UnicodeEncodeError:
            pass
        else:
            print('WARNING: The filename %r CAN be encoded by the filesystem '
                  'encoding (%s). Unicode filename tests may not be effective'
                  % (TESTFN_UNENCODABLE, sys.getfilesystemencoding()))
            TESTFN_UNENCODABLE = None
# macOS and Emscripten deny unencodable filenames (invalid utf-8)
elif sys.platform not in {'darwin', 'emscripten', 'wasi'}:
    try:
        # ascii and utf-8 cannot encode the byte 0xff
        b'\xff'.decode(sys.getfilesystemencoding())
    except UnicodeDecodeError:
        # 0xff will be encoded using the surrogate character u+DCFF
        TESTFN_UNENCODABLE = TESTFN_ASCII \
            + b'-\xff'.decode(sys.getfilesystemencoding(), 'surrogateescape')
    else:
        # File system encoding (eg. ISO-8859-* encodings) can encode
        # the byte 0xff. Skip some unicode filename tests.
        pass

# FS_NONASCII: non-ASCII character encodable by os.fsencode(),
# or an empty string if there is no such character.
FS_NONASCII = ''
for character in (
    # First try printable and common characters to have a readable filename.
    # For each character, the encoding list are just example of encodings able
    # to encode the character (the list is not exhaustive).

    # U+00E6 (Latin Small Letter Ae): cp1252, iso-8859-1
    '\u00E6',
    # U+0130 (Latin Capital Letter I With Dot Above): cp1254, iso8859_3
    '\u0130',
    # U+0141 (Latin Capital Letter L With Stroke): cp1250, cp1257
    '\u0141',
    # U+03C6 (Greek Small Letter Phi): cp1253
    '\u03C6',
    # U+041A (Cyrillic Capital Letter Ka): cp1251
    '\u041A',
    # U+05D0 (Hebrew Letter Alef): Encodable to cp424
    '\u05D0',
    # U+060C (Arabic Comma): cp864, cp1006, iso8859_6, mac_arabic
    '\u060C',
    # U+062A (Arabic Letter Teh): cp720
    '\u062A',
    # U+0E01 (Thai Character Ko Kai): cp874
    '\u0E01',

    # Then try more "special" characters. "special" because they may be
    # interpreted or displayed differently depending on the exact locale
    # encoding and the font.

    # U+00A0 (No-Break Space)
    '\u00A0',
    # U+20AC (Euro Sign)
    '\u20AC',
):
    try:
        # If Python is set up to use the legacy 'mbcs' in Windows,
        # 'replace' error mode is used, and encode() returns b'?'
        # for characters missing in the ANSI codepage
        if os.fsdecode(os.fsencode(character)) != character:
            raise UnicodeError
    except UnicodeError:
        pass
    else:
        FS_NONASCII = character
        break

# TESTFN_UNDECODABLE is a filename (bytes type) that should *not* be able to be
# decoded from the filesystem encoding (in strict mode). It can be None if we
# cannot generate such filename (ex: the latin1 encoding can decode any byte
# sequence). On UNIX, TESTFN_UNDECODABLE can be decoded by os.fsdecode() thanks
# to the surrogateescape error handler (PEP 383), but not from the filesystem
# encoding in strict mode.
TESTFN_UNDECODABLE = None
for name in (
    # b'\xff' is not decodable by os.fsdecode() with code page 932. Windows
    # accepts it to create a file or a directory, or don't accept to enter to
    # such directory (when the bytes name is used). So test b'\xe7' first:
    # it is not decodable from cp932.
    b'\xe7w\xf0',
    # undecodable from ASCII, UTF-8
    b'\xff',
    # undecodable from iso8859-3, iso8859-6, iso8859-7, cp424, iso8859-8, cp856
    # and cp857
    b'\xae\xd5'
    # undecodable from UTF-8 (UNIX and Mac OS X)
    b'\xed\xb2\x80', b'\xed\xb4\x80',
    # undecodable from shift_jis, cp869, cp874, cp932, cp1250, cp1251, cp1252,
    # cp1253, cp1254, cp1255, cp1257, cp1258
    b'\x81\x98',
):
    try:
        name.decode(sys.getfilesystemencoding())
    except UnicodeDecodeError:
        TESTFN_UNDECODABLE = os.fsencode(TESTFN_ASCII) + name
        break

if FS_NONASCII:
    TESTFN_NONASCII = TESTFN_ASCII + FS_NONASCII
else:
    TESTFN_NONASCII = None
TESTFN = TESTFN_NONASCII or TESTFN_ASCII


_can_symlink = None


def can_symlink():
    global _can_symlink
    if _can_symlink is not None:
        return _can_symlink
    # WASI / wasmtime prevents symlinks with absolute paths, see man
    # openat2(2) RESOLVE_BENEATH. Almost all symlink tests use absolute
    # paths. Skip symlink tests on WASI for now.
    src = os.path.abspath(TESTFN)
    symlink_path = src + "can_symlink"
    try:
        os.symlink(src, symlink_path)
        can = True
    except (OSError, NotImplementedError, AttributeError):
        can = False
    else:
        os.remove(symlink_path)
    _can_symlink = can
    return can


def skip_unless_symlink(test):
    """Skip decorator for tests that require functional symlink"""
    ok = can_symlink()
    msg = "Requires functional symlink implementation"
    return test if ok else unittest.skip(msg)(test)


_can_xattr = None


def can_xattr():
    import tempfile
    global _can_xattr
    if _can_xattr is not None:
        return _can_xattr
    if not hasattr(os, "setxattr"):
        can = False
    else:
        import platform
        tmp_dir = tempfile.mkdtemp()
        tmp_fp, tmp_name = tempfile.mkstemp(dir=tmp_dir)
        try:
            with open(TESTFN, "wb") as fp:
                try:
                    # TESTFN & tempfile may use different file systems with
                    # different capabilities
                    os.setxattr(tmp_fp, b"user.test", b"")
                    os.setxattr(tmp_name, b"trusted.foo", b"42")
                    os.setxattr(fp.fileno(), b"user.test", b"")
                    # Kernels < 2.6.39 don't respect setxattr flags.
                    kernel_version = platform.release()
                    m = re.match(r"2.6.(\d{1,2})", kernel_version)
                    can = m is None or int(m.group(1)) >= 39
                except OSError:
                    can = False
        finally:
            unlink(TESTFN)
            unlink(tmp_name)
            rmdir(tmp_dir)
    _can_xattr = can
    return can


_can_chmod = None

def can_chmod():
    global _can_chmod
    if _can_chmod is not None:
        return _can_chmod
    if not hasattr(os, "chown"):
        _can_chmod = False
        return _can_chmod
    try:
        with open(TESTFN, "wb") as f:
            try:
                os.chmod(TESTFN, 0o777)
                mode1 = os.stat(TESTFN).st_mode
                os.chmod(TESTFN, 0o666)
                mode2 = os.stat(TESTFN).st_mode
            except OSError as e:
                can = False
            else:
                can = stat.S_IMODE(mode1) != stat.S_IMODE(mode2)
    finally:
        unlink(TESTFN)
    _can_chmod = can
    return can


def skip_unless_working_chmod(test):
    """Skip tests that require working os.chmod()

    WASI SDK 15.0 cannot change file mode bits.
    """
    ok = can_chmod()
    msg = "requires working os.chmod()"
    return test if ok else unittest.skip(msg)(test)


# Check whether the current effective user has the capability to override
# DAC (discretionary access control). Typically user root is able to
# bypass file read, write, and execute permission checks. The capability
# is independent of the effective user. See capabilities(7).
_can_dac_override = None

def can_dac_override():
    global _can_dac_override

    if not can_chmod():
        _can_dac_override = False
    if _can_dac_override is not None:
        return _can_dac_override

    try:
        with open(TESTFN, "wb") as f:
            os.chmod(TESTFN, 0o400)
            try:
                with open(TESTFN, "wb"):
                    pass
            except OSError:
                _can_dac_override = False
            else:
                _can_dac_override = True
    finally:
        unlink(TESTFN)

    return _can_dac_override


def skip_if_dac_override(test):
    ok = not can_dac_override()
    msg = "incompatible with CAP_DAC_OVERRIDE"
    return test if ok else unittest.skip(msg)(test)


def skip_unless_dac_override(test):
    ok = can_dac_override()
    msg = "requires CAP_DAC_OVERRIDE"
    return test if ok else unittest.skip(msg)(test)


def unlink(filename):
    try:
        _unlink(filename)
    except (FileNotFoundError, NotADirectoryError):
        pass


if sys.platform.startswith("win"):
    def _waitfor(func, pathname, waitall=False):
        # Perform the operation
        func(pathname)
        # Now setup the wait loop
        if waitall:
            dirname = pathname
        else:
            dirname, name = os.path.split(pathname)
            dirname = dirname or '.'
        # Check for `pathname` to be removed from the filesystem.
        # The exponential backoff of the timeout amounts to a total
        # of ~1 second after which the deletion is probably an error
        # anyway.
        # Testing on an i7@4.3GHz shows that usually only 1 iteration is
        # required when contention occurs.
        timeout = 0.001
        while timeout < 1.0:
            # Note we are only testing for the existence of the file(s) in
            # the contents of the directory regardless of any security or
            # access rights.  If we have made it this far, we have sufficient
            # permissions to do that much using Python's equivalent of the
            # Windows API FindFirstFile.
            # Other Windows APIs can fail or give incorrect results when
            # dealing with files that are pending deletion.
            L = os.listdir(dirname)
            if not (L if waitall else name in L):
                return
            # Increase the timeout and try again
            time.sleep(timeout)
            timeout *= 2
        warnings.warn('tests may fail, delete still pending for ' + pathname,
                      RuntimeWarning, stacklevel=4)

    def _unlink(filename):
        _waitfor(os.unlink, filename)

    def _rmdir(dirname):
        _waitfor(os.rmdir, dirname)

    def _rmtree(path):
        from test.support import _force_run

        def _rmtree_inner(path):
            for name in _force_run(path, os.listdir, path):
                fullname = os.path.join(path, name)
                try:
                    mode = os.lstat(fullname).st_mode
                except OSError as exc:
                    print("support.rmtree(): os.lstat(%r) failed with %s"
                          % (fullname, exc),
                          file=sys.__stderr__)
                    mode = 0
                if stat.S_ISDIR(mode):
                    _waitfor(_rmtree_inner, fullname, waitall=True)
                    _force_run(fullname, os.rmdir, fullname)
                else:
                    _force_run(fullname, os.unlink, fullname)
        _waitfor(_rmtree_inner, path, waitall=True)
        _waitfor(lambda p: _force_run(p, os.rmdir, p), path)

    def _longpath(path):
        try:
            import ctypes
        except ImportError:
            # No ctypes means we can't expands paths.
            pass
        else:
            buffer = ctypes.create_unicode_buffer(len(path) * 2)
            length = ctypes.windll.kernel32.GetLongPathNameW(path, buffer,
                                                             len(buffer))
            if length:
                return buffer[:length]
        return path
else:
    _unlink = os.unlink
    _rmdir = os.rmdir

    def _rmtree(path):
        import shutil
        try:
            shutil.rmtree(path)
            return
        except OSError:
            pass

        def _rmtree_inner(path):
            from test.support import _force_run
            for name in _force_run(path, os.listdir, path):
                fullname = os.path.join(path, name)
                try:
                    mode = os.lstat(fullname).st_mode
                except OSError:
                    mode = 0
                if stat.S_ISDIR(mode):
                    _rmtree_inner(fullname)
                    _force_run(path, os.rmdir, fullname)
                else:
                    _force_run(path, os.unlink, fullname)
        _rmtree_inner(path)
        os.rmdir(path)

    def _longpath(path):
        return path


def rmdir(dirname):
    try:
        _rmdir(dirname)
    except FileNotFoundError:
        pass


def rmtree(path):
    try:
        _rmtree(path)
    except FileNotFoundError:
        pass


def fs_is_case_insensitive(directory):
    """Detects if the file system for the specified directory
    is case-insensitive."""
    import tempfile
    with tempfile.NamedTemporaryFile(dir=directory) as base:
        base_path = base.name
        case_path = base_path.upper()
        if case_path == base_path:
            case_path = base_path.lower()
        try:
            return os.path.samefile(base_path, case_path)
        except FileNotFoundError:
            return False


class FakePath:
    """Simple implementing of the path protocol.
    """
    def __init__(self, path):
        self.path = path

    def __repr__(self):
        return f'<FakePath {self.path!r}>'

    def __fspath__(self):
        if (isinstance(self.path, BaseException) or
            isinstance(self.path, type) and
                issubclass(self.path, BaseException)):
            raise self.path
        else:
            return self.path


class EnvironmentVarGuard(collections.abc.MutableMapping):

    """Class to help protect the environment variable properly.  Can be used as
    a context manager."""

    def __init__(self):
        self._environ = os.environ
        self._changed = {}

    def __getitem__(self, envvar):
        return self._environ[envvar]

    def __setitem__(self, envvar, value):
        # Remember the initial value on the first access
        if envvar not in self._changed:
            self._changed[envvar] = self._environ.get(envvar)
        self._environ[envvar] = value

    def __delitem__(self, envvar):
        # Remember the initial value on the first access
        if envvar not in self._changed:
            self._changed[envvar] = self._environ.get(envvar)
        if envvar in self._environ:
            del self._environ[envvar]

    def keys(self):
        return self._environ.keys()

    def __iter__(self):
        return iter(self._environ)

    def __len__(self):
        return len(self._environ)

    def set(self, envvar, value):
        self[envvar] = value

    def unset(self, envvar):
        del self[envvar]

    def copy(self):
        # We do what os.environ.copy() does.
        return dict(self)

    def __enter__(self):
        return self

    def __exit__(self, *ignore_exc):
        for (k, v) in self._changed.items():
            if v is None:
                if k in self._environ:
                    del self._environ[k]
            else:
                self._environ[k] = v
        os.environ = self._environ
