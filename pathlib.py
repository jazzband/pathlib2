import fnmatch
import functools
import io
import ntpath
import os
import posixpath
import re
import sys
import weakref
try:
    import threading
except ImportError:
    import dummy_threading as threading

from collections import Sequence, defaultdict
from contextlib import contextmanager
from errno import EINVAL, ENOENT, EEXIST
from itertools import chain, count
from operator import attrgetter
from stat import S_ISDIR, S_ISLNK, S_ISREG
try:
    from urllib import quote as urlquote, quote as urlquote_from_bytes
except ImportError:
    from urllib.parse import quote as urlquote, quote_from_bytes as urlquote_from_bytes


supports_symlinks = True
try:
    import nt
except ImportError:
    nt = None
else:
    if sys.getwindowsversion()[:2] >= (6, 0) and sys.version_info >= (3, 2):
        from nt import _getfinalpathname
    else:
        supports_symlinks = False
        _getfinalpathname = None


__all__ = [
    "PurePath", "PurePosixPath", "PureNTPath",
    "Path", "PosixPath", "NTPath",
    ]

#
# Internals
#

def _is_wildcard_pattern(pat):
    # Whether this pattern needs actual matching using fnmatch, or can
    # be looked up directly as a file.
    return "*" in pat or "?" in pat or "[" in pat


class _Flavour(object):
    """A flavour implements a particular (platform-specific) set of path
    semantics."""

    def __init__(self):
        self.join = self.sep.join

    def parse_parts(self, parts):
        parsed = []
        sep = self.sep
        altsep = self.altsep
        drv = root = ''
        it = reversed(parts)
        for part in it:
            if altsep:
                part = part.replace(altsep, sep)
            drv, root, rel = self.splitroot(part)
            rel = rel.rstrip(sep)
            parsed.extend(x for x in reversed(rel.split(sep)) if x and x != '.')
            if drv or root:
                if not drv:
                    # If no drive is present, try to find one in the previous
                    # parts. This makes the result of parsing e.g.
                    # ("C:", "/", "a") reasonably intuitive.
                    for part in it:
                        drv = self.splitroot(part)[0]
                        if drv:
                            break
                break
        if drv or root:
            parsed.append(drv + root)
        parsed.reverse()
        return drv, root, parsed


class _NTFlavour(_Flavour):
    # Reference for NT paths can be found at
    # http://msdn.microsoft.com/en-us/library/aa365247%28v=vs.85%29.aspx

    sep = '\\'
    altsep = '/'
    has_drv = True
    pathmod = ntpath

    is_supported = (nt is not None)

    drive_letters = (
        set(chr(x) for x in range(ord('a'), ord('z') + 1)) |
        set(chr(x) for x in range(ord('A'), ord('Z') + 1))
    )
    ext_namespace_prefix = '\\\\?\\'

    reserved_names = (
        {'CON', 'PRN', 'AUX', 'NUL'} |
        {'COM%d' % i for i in range(1, 10)} |
        {'LPT%d' % i for i in range(1, 10)}
        )

    # Interesting findings about extended paths:
    # - '\\?\c:\a', '//?/c:\a' and '//?/c:/a' are all supported
    #   but '\\?\c:/a' is not
    # - extended paths are always absolute; "relative" extended paths will
    #   fail.

    def splitroot(self, part, sep=sep):
        first = part[0:1]
        second = part[1:2]
        if (second == sep and first == sep):
            # XXX extended paths should also disable the collapsing of "."
            # components (according to MSDN docs).
            prefix, part = self._split_extended_path(part)
            first = part[0:1]
            second = part[1:2]
        else:
            prefix = ''
        third = part[2:3]
        if (second == sep and first == sep and third != sep):
            # is a UNC path:
            # vvvvvvvvvvvvvvvvvvvvv root
            # \\machine\mountpoint\directory\etc\...
            #            directory ^^^^^^^^^^^^^^
            index = part.find(sep, 2)
            if index != -1:
                index2 = part.find(sep, index + 1)
                # a UNC path can't have two slashes in a row
                # (after the initial two)
                if index2 != index + 1:
                    if index2 == -1:
                        index2 = len(part)
                    if prefix:
                        return prefix + part[1:index2], sep, part[index2+1:]
                    else:
                        return part[:index2], sep, part[index2+1:]
        drv = root = ''
        if second == ':' and first in self.drive_letters:
            drv = part[:2]
            part = part[2:]
            first = third
        if first == sep:
            root = first
            part = part.lstrip(sep)
        return prefix + drv, root, part

    def casefold(self, s):
        return s.lower()

    def casefold_parts(self, parts):
        return [p.lower() for p in parts]

    def resolve(self, path):
        s = str(path)
        if not s:
            return os.getcwd()
        if _getfinalpathname is not None:
            return self._ext_to_normal(_getfinalpathname(s))
        # Means fallback on absolute
        return None

    def _split_extended_path(self, s, ext_prefix=ext_namespace_prefix):
        prefix = ''
        if s.startswith(ext_prefix):
            prefix = s[:4]
            s = s[4:]
            if s.startswith('UNC\\'):
                prefix += s[:3]
                s = '\\' + s[3:]
        return prefix, s

    def _ext_to_normal(self, s):
        # Turn back an extended path into a normal DOS-like path
        return self._split_extended_path(s)[1]

    def is_reserved(self, parts):
        # NOTE: the rules for reserved names seem somewhat complicated
        # (e.g. r"..\NUL" is reserved but not r"foo\NUL").
        # We err on the side of caution and return True for paths which are
        # not considered reserved by Windows.
        if not parts:
            return False
        if parts[0].startswith('\\\\'):
            # UNC paths are never reserved
            return False
        return parts[-1].partition('.')[0].upper() in self.reserved_names

    def make_uri(self, path):
        # Under Windows, file URIs use the UTF-8 encoding.
        drive = path.drive
        if len(drive) == 2 and drive[1] == ':':
            # It's a path on a local drive => 'file:///c:/a/b'
            rest = path.as_posix()[2:].lstrip('/')
            return 'file:///%s/%s' % (
                drive, urlquote_from_bytes(rest.encode('utf-8')))
        else:
            # It's a path on a network drive => 'file://host/share/a/b'
            return 'file:' + urlquote_from_bytes(path.as_posix().encode('utf-8'))


_NO_FD = None

class _PosixFlavour(_Flavour):
    sep = '/'
    altsep = ''
    has_drv = False
    pathmod = posixpath

    is_supported = (os.name != 'nt')

    def splitroot(self, part, sep=sep):
        if part and part[0] == sep:
            stripped_part = part.lstrip(sep)
            # According to POSIX path resolution:
            # http://pubs.opengroup.org/onlinepubs/009695399/basedefs/xbd_chap04.html#tag_04_11
            # "A pathname that begins with two successive slashes may be
            # interpreted in an implementation-defined manner, although more
            # than two leading slashes shall be treated as a single slash".
            if len(part) - len(stripped_part) == 2:
                return '', sep * 2, stripped_part
            else:
                return '', sep, stripped_part
        else:
            return '', '', part

    def casefold(self, s):
        return s

    def casefold_parts(self, parts):
        return parts

    def resolve(self, path):
        sep = self.sep
        def split(p):
            return [x for x in p.split(sep) if x]
        def absparts(p):
            # Our own abspath(), since the posixpath one makes
            # the mistake of "normalizing" the path without resolving the
            # symlinks first.
            if not p.startswith(sep):
                return split(os.getcwd()) + split(p)
            else:
                return split(p)
        def close(fd):
            if fd != _NO_FD:
                os.close(fd)
        parts = absparts(str(path))[::-1]
        accessor = path._accessor
        resolved = cur = ""
        resolved_fd = _NO_FD
        symlinks = {}
        try:
            while parts:
                part = parts.pop()
                cur = resolved + sep + part
                if cur in symlinks and symlinks[cur] <= len(parts):
                    # We've already seen the symlink and there's not less
                    # work to do than the last time.
                    raise ValueError("Symlink loop from %r" % cur)
                try:
                    target = accessor.readlink(cur, part, dir_fd=resolved_fd)
                except OSError as e:
                    if e.errno != EINVAL:
                        raise
                    # Not a symlink
                    resolved_fd = accessor.walk_down(cur, part, dir_fd=resolved_fd)
                    resolved = cur
                else:
                    # Take note of remaining work from this symlink
                    symlinks[cur] = len(parts)
                    if target.startswith(sep):
                        # Symlink points to absolute path
                        resolved = ""
                        close(resolved_fd)
                        resolved_fd = _NO_FD
                    parts.extend(split(target)[::-1])
        finally:
            close(resolved_fd)
        return resolved or sep

    def is_reserved(self, parts):
        return False

    def make_uri(self, path):
        # We represent the path using the local filesystem encoding,
        # for portability to other applications.
        bpath = path.as_bytes()
        return 'file://' + urlquote_from_bytes(bpath)


_nt_flavour = _NTFlavour()
_posix_flavour = _PosixFlavour()


_fds_refs = defaultdict(int)
_fds_refs_lock = threading.Lock()

def _add_fd_ref(fd, lock=_fds_refs_lock):
    with lock:
        _fds_refs[fd] += 1

def _sub_fd_ref(fd, lock=_fds_refs_lock):
    with lock:
        nrefs = _fds_refs[fd] - 1
        if nrefs > 0:
            _fds_refs[fd] = nrefs
        else:
            del _fds_refs[fd]
            os.close(fd)


class _Accessor:
    """An accessor implements a particular (system-specific or not) way of
    accessing paths on the filesystem."""


if sys.version_info >= (3, 3):
    supports_openat = (os.listdir in os.supports_fd and
        os.supports_dir_fd >= { os.chmod, os.stat, os.mkdir, os.open,
                                os.readlink, os.rename, os.symlink, os.unlink, }
    )
else:
    supports_openat = False

if supports_openat:

    def _fdnamepair(pathobj):
        """Get a (parent fd, name) pair from a path object, suitable for use
        with the various *at functions."""
        parent_fd = pathobj._parent_fd
        if parent_fd is not None:
            return parent_fd, pathobj._parts[-1]
        else:
            return _NO_FD, str(pathobj)


    class _OpenatAccessor(_Accessor):

        def _wrap_atfunc(atfunc):
            @functools.wraps(atfunc)
            def wrapped(pathobj, *args, **kwargs):
                parent_fd, name = _fdnamepair(pathobj)
                return atfunc(name, *args, dir_fd=parent_fd, **kwargs)
            return staticmethod(wrapped)

        def _wrap_binary_atfunc(atfunc):
            @functools.wraps(atfunc)
            def wrapped(pathobjA, pathobjB, *args, **kwargs):
                parent_fd_A, nameA = _fdnamepair(pathobjA)
                # We allow pathobjB to be a plain str, for convenience
                if isinstance(pathobjB, Path):
                    parent_fd_B, nameB = _fdnamepair(pathobjB)
                else:
                    # If it's a str then at best it's cwd-relative
                    parent_fd_B, nameB = _NO_FD, str(pathobjB)
                return atfunc(nameA, nameB, *args,
                              src_dir_fd=parent_fd_A, dst_dir_fd=parent_fd_B,
                              **kwargs)
            return staticmethod(wrapped)

        stat = _wrap_atfunc(os.stat)

        lstat = _wrap_atfunc(os.lstat)

        open = _wrap_atfunc(os.open)

        chmod = _wrap_atfunc(os.chmod)

        def lchmod(self, pathobj, mode):
            return self.chmod(pathobj, mode, follow_symlinks=False)

        mkdir = _wrap_atfunc(os.mkdir)

        unlink = _wrap_atfunc(os.unlink)

        rmdir = _wrap_atfunc(os.rmdir)

        def listdir(self, pathobj):
            fd = self._make_fd(pathobj, tolerant=False)
            return os.listdir(fd)

        rename = _wrap_binary_atfunc(os.rename)

        if sys.version_info >= (3, 3):
            replace = _wrap_binary_atfunc(os.replace)

        def symlink(self, target, pathobj, target_is_directory):
            parent_fd, name = _fdnamepair(pathobj)
            os.symlink(str(target), name, dir_fd=parent_fd)

        def _make_fd(self, pathobj, tolerant=True):
            fd = pathobj._cached_fd
            if fd is not None:
                return fd
            try:
                fd = self.open(pathobj, os.O_RDONLY)
            except (PermissionError, FileNotFoundError):
                if tolerant:
                    # If the path doesn't exist or is forbidden, just let us
                    # gracefully fallback on fd-less code.
                    return None
                raise
            # This ensures the stat information is consistent with the fd.
            try:
                st = pathobj._cached_stat = os.fstat(fd)
            except:
                os.close(fd)
                raise
            if tolerant and not S_ISDIR(st.st_mode):
                # Not a directory => no point in keeping the fd
                os.close(fd)
                return None
            else:
                pathobj._cached_fd = fd
                pathobj._add_managed_fd(fd)
                return fd

        def init_path(self, pathobj):
            self._make_fd(pathobj)

        def make_child(self, pathobj, args):
            drv, root, parts = pathobj._flavour.parse_parts(args)
            if drv or root:
                # Anchored path => we can't do any better
                return None
            # NOTE: In the code below, we want to expose errors instead of
            # risking race conditions when e.g. a non-existing directory gets
            # later created.  This means we want e.g. non-existing path
            # components or insufficient permissions to raise an OSError.
            pathfd = self._make_fd(pathobj, tolerant=False)
            if not parts:
                # This is the same path
                newpath = pathobj._from_parsed_parts(
                    pathobj._drv, pathobj._root, pathobj._parts, init=False)
                newpath._init(template=pathobj, fd=pathfd)
                return newpath
            parent_fd = pathfd
            for part in parts[:-1]:
                fd = os.open(part, os.O_RDONLY, dir_fd=parent_fd)
                if parent_fd != pathfd:
                    # Forget intermediate fds
                    os.close(parent_fd)
                parent_fd = fd
            # The last component may or may not exist, it doesn't matter: we
            # have the fd of its parent
            newpath = pathobj._from_parsed_parts(
                pathobj._drv, pathobj._root, pathobj._parts + parts, init=False)
            newpath._init(template=pathobj, parent_fd=parent_fd)
            return newpath

        # Helpers for resolve()
        def walk_down(self, path, name, dir_fd):
            if dir_fd != _NO_FD:
                try:
                    return os.open(name, os.O_RDONLY, dir_fd=dir_fd)
                finally:
                    os.close(dir_fd)
            else:
                return os.open(path, os.O_RDONLY)

        def readlink(self, path, name, dir_fd):
            if dir_fd != _NO_FD:
                return os.readlink(name, dir_fd=dir_fd)
            else:
                return os.readlink(path)

    _openat_accessor = _OpenatAccessor()


class _NormalAccessor(_Accessor):

    def _wrap_strfunc(strfunc):
        @functools.wraps(strfunc)
        def wrapped(pathobj, *args):
            return strfunc(str(pathobj), *args)
        return staticmethod(wrapped)

    def _wrap_binary_strfunc(strfunc):
        @functools.wraps(strfunc)
        def wrapped(pathobjA, pathobjB, *args):
            return strfunc(str(pathobjA), str(pathobjB), *args)
        return staticmethod(wrapped)

    stat = _wrap_strfunc(os.stat)

    lstat = _wrap_strfunc(os.lstat)

    open = _wrap_strfunc(os.open)

    listdir = _wrap_strfunc(os.listdir)

    chmod = _wrap_strfunc(os.chmod)

    if hasattr(os, "lchmod"):
        lchmod = _wrap_strfunc(os.lchmod)
    else:
        def lchmod(self, pathobj, mode):
            raise NotImplementedError("lchmod() not available on this system")

    mkdir = _wrap_strfunc(os.mkdir)

    unlink = _wrap_strfunc(os.unlink)

    rmdir = _wrap_strfunc(os.rmdir)

    rename = _wrap_binary_strfunc(os.rename)

    if sys.version_info >= (3, 3):
        replace = _wrap_binary_strfunc(os.replace)

    if nt:
        if supports_symlinks:
            symlink = _wrap_binary_strfunc(os.symlink)
        else:
            def symlink(a, b, target_is_directory):
                raise NotImplementedError("symlink() not available on this system")
    else:
        # Under POSIX, os.symlink() takes two args
        @staticmethod
        def symlink(a, b, target_is_directory):
            return os.symlink(str(a), str(b))

    def init_path(self, pathobj):
        pass

    def make_child(self, pathobj, args):
        return None

    # Helpers for resolve()
    def walk_down(self, path, name, dir_fd):
        assert dir_fd == _NO_FD
        return _NO_FD

    def readlink(self, path, name, dir_fd):
        assert dir_fd == _NO_FD
        return os.readlink(path)

_normal_accessor = _NormalAccessor()


#
# Globbing helpers
#

@contextmanager
def _cached(func):
    try:
        func.__cached__
        yield func
    except AttributeError:
        cache = {}
        def wrapper(*args):
            if args in cache:
                return cache[args]
            value = cache[args] = func(*args)
            return value
        wrapper.__cached__ = True
        try:
            yield wrapper
        finally:
            cache.clear()

def _make_selector(pattern_parts):
    pat = pattern_parts[0]
    child_parts = pattern_parts[1:]
    if pat == '**':
        cls = _RecursiveWildcardSelector
    elif '**' in pat:
        raise ValueError("Invalid pattern: '**' can only be an entire path component")
    elif _is_wildcard_pattern(pat):
        cls = _WildcardSelector
    else:
        cls = _PreciseSelector
    return cls(pat, child_parts)

if hasattr(functools, "lru_cache"):
    _make_selector = functools.lru_cache()(_make_selector)


class _Selector:
    """A selector matches a specific glob pattern part against the children
    of a given path."""

    def __init__(self, child_parts):
        self.child_parts = child_parts
        if child_parts:
            self.successor = _make_selector(child_parts)
        else:
            self.successor = _TerminatingSelector()

    def select_from(self, parent_path):
        """Iterate over all child paths of `parent_path` matched by this
        selector.  This can contain parent_path itself."""
        path_cls = type(parent_path)
        is_dir = path_cls.is_dir
        exists = path_cls.exists
        listdir = parent_path._accessor.listdir
        return self._select_from(parent_path, is_dir, exists, listdir)


class _TerminatingSelector:

    def _select_from(self, parent_path, is_dir, exists, listdir):
        yield parent_path


class _PreciseSelector(_Selector):

    def __init__(self, name, child_parts):
        self.name = name
        _Selector.__init__(self, child_parts)

    def _select_from(self, parent_path, is_dir, exists, listdir):
        if not is_dir(parent_path):
            return
        path = parent_path._make_child_relpath(self.name)
        if exists(path):
            for p in self.successor._select_from(path, is_dir, exists, listdir):
                yield p


class _WildcardSelector(_Selector):

    def __init__(self, pat, child_parts):
        self.pat = re.compile(fnmatch.translate(pat))
        _Selector.__init__(self, child_parts)

    def _select_from(self, parent_path, is_dir, exists, listdir):
        if not is_dir(parent_path):
            return
        cf = parent_path._flavour.casefold
        for name in listdir(parent_path):
            casefolded = cf(name)
            if self.pat.match(casefolded):
                path = parent_path._make_child_relpath(name)
                for p in self.successor._select_from(path, is_dir, exists, listdir):
                    yield p


class _RecursiveWildcardSelector(_Selector):

    def __init__(self, pat, child_parts):
        _Selector.__init__(self, child_parts)

    def _iterate_directories(self, parent_path, is_dir, listdir):
        yield parent_path
        for name in listdir(parent_path):
            path = parent_path._make_child_relpath(name)
            if is_dir(path):
                for p in self._iterate_directories(path, is_dir, listdir):
                    yield p

    def _select_from(self, parent_path, is_dir, exists, listdir):
        if not is_dir(parent_path):
            return
        with _cached(listdir) as listdir:
            yielded = set()
            try:
                successor_select = self.successor._select_from
                for starting_point in self._iterate_directories(parent_path, is_dir, listdir):
                    for p in successor_select(starting_point, is_dir, exists, listdir):
                        if p not in yielded:
                            yield p
                            yielded.add(p)
            finally:
                yielded.clear()


#
# Public API
#

class _PathParts(Sequence):
    """This object provides sequence-like access to the parts of a path.
    Don't try to construct it yourself."""
    __slots__ = ('_pathcls', '_parts')

    def __init__(self, path):
        # We don't store the instance to avoid reference cycles
        self._pathcls = type(path)
        self._parts = path._parts

    def __len__(self):
        return len(self._parts)

    def __getitem__(self, idx):
        if isinstance(idx, slice):
            return self._pathcls(*self._parts[idx])
        return self._parts[idx]

    def __repr__(self):
        return "<{}.parts: {!r}>".format(self._pathcls.__name__, self._parts)


class PurePath(object):
    """PurePath represents a filesystem path and offers operations which
    don't imply any actual filesystem I/O.  Depending on your system,
    instantiating a PurePath will return either a PurePosixPath or a
    PureNTPath object.  You can also instantiate either of these classes
    directly, regardless of your system.
    """
    __slots__ = (
        '_drv', '_root', '_parts',
        '_str', '_hash', '_pparts', '_cached_cparts',
    )

    def __new__(cls, *args):
        """Construct a PurePath from one or several strings and or existing
        PurePath objects.  The strings and path objects are combined so as
        to yield a canonicalized path, which is incorporated into the
        new PurePath object.
        """
        if cls is PurePath:
            cls = PureNTPath if os.name == 'nt' else PurePosixPath
        return cls._from_parts(args)

    @classmethod
    def _parse_args(cls, args):
        # This is useful when you don't want to create an instance, just
        # canonicalize some constructor arguments.
        parts = []
        for a in args:
            if isinstance(a, PurePath):
                parts += a._parts
            elif isinstance(a, str):
                # Assuming a str
                parts.append(a)
            else:
                raise TypeError(
                    "argument should be a path or str object, not %r"
                    % type(a))
        return cls._flavour.parse_parts(parts)

    @classmethod
    def _from_parts(cls, args, init=True):
        # We need to call _parse_args on the instance, so as to get the
        # right flavour.
        self = object.__new__(cls)
        drv, root, parts = self._parse_args(args)
        self._drv = drv
        self._root = root
        self._parts = parts
        if init:
            self._init()
        return self

    @classmethod
    def _from_parsed_parts(cls, drv, root, parts, init=True):
        self = object.__new__(cls)
        self._drv = drv
        self._root = root
        self._parts = parts
        if init:
            self._init()
        return self

    @classmethod
    def _format_parsed_parts(cls, drv, root, parts):
        if drv or root:
            return drv + root + cls._flavour.join(parts[1:])
        else:
            return cls._flavour.join(parts)

    def _init(self):
        # Overriden in concrete Path
        pass

    def _make_child(self, args):
        # Overriden in concrete Path
        parts = self._parts[:]
        parts.extend(args)
        return self._from_parts(parts)

    def __str__(self):
        """Return the string representation of the path, suitable for
        passing to system calls."""
        try:
            return self._str
        except AttributeError:
            self._str = self._format_parsed_parts(self._drv, self._root,
                                                  self._parts) or '.'
            return self._str

    def as_posix(self):
        """Return the string representation of the path with forward (/)
        slashes."""
        f = self._flavour
        return str(self).replace(f.sep, '/')

    def as_bytes(self):
        """Return the bytes representation of the path.  This is only
        recommended to use under Unix."""
        if sys.version_info < (3, 2):
            raise NotImplementedError("needs Python 3.2 or later")
        return os.fsencode(str(self))

    __bytes__ = as_bytes

    def __repr__(self):
        return "{}({!r})".format(self.__class__.__name__, str(self))

    def as_uri(self):
        """Return the path as a 'file' URI."""
        if not self.is_absolute():
            raise ValueError("relative path can't be expressed as a file URI")
        return self._flavour.make_uri(self)

    @property
    def _cparts(self):
        # Cached casefolded parts, for hashing and comparison
        try:
            return self._cached_cparts
        except AttributeError:
            self._cached_cparts = self._flavour.casefold_parts(self._parts)
            return self._cached_cparts

    def __eq__(self, other):
        if not isinstance(other, PurePath):
            return NotImplemented
        return self._cparts == other._cparts and self._flavour is other._flavour

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        try:
            return self._hash
        except AttributeError:
            self._hash = hash(tuple(self._cparts))
            return self._hash

    def __lt__(self, other):
        if not isinstance(other, PurePath) or self._flavour is not other._flavour:
            return NotImplemented
        return self._cparts < other._cparts

    def __le__(self, other):
        if not isinstance(other, PurePath) or self._flavour is not other._flavour:
            return NotImplemented
        return self._cparts <= other._cparts

    def __gt__(self, other):
        if not isinstance(other, PurePath) or self._flavour is not other._flavour:
            return NotImplemented
        return self._cparts > other._cparts

    def __ge__(self, other):
        if not isinstance(other, PurePath) or self._flavour is not other._flavour:
            return NotImplemented
        return self._cparts >= other._cparts

    drive = property(attrgetter('_drv'),
                     doc="""The drive prefix (letter or UNC path), if any""")

    root = property(attrgetter('_root'),
                    doc="""The root of the path, if any""")

    @property
    def anchor(self):
        """The concatenation of the drive and root, or ''."""
        anchor = self._drv + self._root
        return anchor

    @property
    def name(self):
        """The final path component, if any."""
        parts = self._parts
        if len(parts) == (1 if (self._drv or self._root) else 0):
            return ''
        return parts[-1]

    @property
    def ext(self):
        """The final component's extension, if any."""
        basename = self.name
        if basename == '' or basename == '.':
            return ''
        i = basename.find('.')
        if i == -1:
            return ''
        return basename[i:]

    def relative(self):
        """Return a new path without any drive and root.
        """
        if self._drv or self._root:
            return self._from_parsed_parts('', '', self._parts[1:])
        else:
            return self._from_parsed_parts('', '', self._parts)

    def relative_to(self, *other):
        """Return the relative path to another path identified by the passed
        arguments.  If the operation is not possible (because this is not
        a subpath of the other path), raise ValueError.
        """
        # For the purpose of this method, drive and root are considered
        # separate parts, i.e.:
        #   Path('c:/').relative('c:')  gives Path('/')
        #   Path('c:/').relative('/')   raise ValueError
        if not other:
            raise TypeError("need at least one argument")
        parts = self._parts
        drv = self._drv
        root = self._root
        if drv or root:
            if root:
                abs_parts = [drv, root] + parts[1:]
            else:
                abs_parts = [drv] + parts[1:]
        else:
            abs_parts = parts
        to_drv, to_root, to_parts = self._parse_args(other)
        if to_drv or to_root:
            if to_root:
                to_abs_parts = [to_drv, to_root] + to_parts[1:]
            else:
                to_abs_parts = [to_drv] + to_parts[1:]
        else:
            to_abs_parts = to_parts
        n = len(to_abs_parts)
        if n == 0 and (drv or root) or abs_parts[:n] != to_abs_parts:
            formatted = self._format_parsed_parts(to_drv, to_root, to_parts)
            raise ValueError("{!r} does not start with {!r}"
                             .format(str(self), str(formatted)))
        return self._from_parsed_parts('', '', abs_parts[n:])

    @property
    def parts(self):
        """An object providing sequence-like access to the
        components in the filesystem path."""
        try:
            return self._pparts
        except AttributeError:
            self._pparts = _PathParts(self)
            return self._pparts

    def join(self, *args):
        """Combine this path with one or several arguments, and return a
        new path representing either a subpath (if all arguments are relative
        paths) or a totally different path (if one of the arguments is
        anchored).
        """
        return self._make_child(args)

    def __getitem__(self, key):
        if isinstance(key, tuple):
            return self._make_child(key)
        else:
            return self._make_child((key,))

    def parent(self, level=1):
        """A parent or ancestor (if `level` is specified) of this path."""
        if level < 1:
            raise ValueError("`level` must be a non-zero positive integer")
        drv = self._drv
        root = self._root
        parts = self._parts[:-level]
        if not parts:
            if level > len(self._parts) - bool(drv or root):
                raise ValueError("level greater than path length")
        return self._from_parsed_parts(drv, root, parts)

    def parents(self):
        """Iterate over this path's parents, in ascending order."""
        drv = self._drv
        root = self._root
        parts = self._parts
        n = len(parts)
        end = 0 if (drv or root) else -1
        for i in range(n - 1, end, -1):
            yield self._from_parsed_parts(drv, root, parts[:i])

    def is_absolute(self):
        """True if the path is absolute (has both a root and, if applicable,
        a drive)."""
        if not self._root:
            return False
        return not self._flavour.has_drv or bool(self._drv)

    def normcase(self):
        """Return this path, possibly lowercased if the path flavour has
        case-insensitive path semantics.
        Calling this method is not needed before comparing Path instances."""
        fix = self._flavour.casefold_parts
        drv, = fix((self._drv,))
        root = self._root
        parts = fix(self._parts)
        return self._from_parsed_parts(drv, root, parts)

    def is_reserved(self):
        """Return True if the path contains one of the special names reserved
        by the system, if any."""
        return self._flavour.is_reserved(self._parts)

    def match(self, path_pattern):
        """
        Return True if this path matches the given pattern.
        """
        cf = self._flavour.casefold
        path_pattern = cf(path_pattern)
        drv, root, pat_parts = self._flavour.parse_parts((path_pattern,))
        if not pat_parts:
            raise ValueError("empty pattern")
        if drv and drv != cf(self._drv):
            return False
        if root and root != cf(self._root):
            return False
        parts = self._cparts
        if drv or root:
            if len(pat_parts) != len(parts):
                return False
            pat_parts = pat_parts[1:]
        elif len(pat_parts) > len(parts):
            return False
        for part, pat in zip(reversed(parts), reversed(pat_parts)):
            if not fnmatch.fnmatchcase(part, pat):
                return False
        return True


class PurePosixPath(PurePath):
    _flavour = _posix_flavour
    __slots__ = ()


class PureNTPath(PurePath):
    _flavour = _nt_flavour
    __slots__ = ()


# Filesystem-accessing classes


class Path(PurePath):
    __slots__ = (
        '_accessor',
        '_cached_stat',
        '_closed',
        # Used by _OpenatAccessor
        '_cached_fd',
        '_parent_fd',
        '_managed_fds',
        '__weakref__',
    )

    _wrs = {}
    _wr_id = count()

    def __new__(cls, *args, **kwargs):
        use_openat = kwargs.get('use_openat', False)
        if cls is Path:
            cls = NTPath if os.name == 'nt' else PosixPath
        self = cls._from_parts(args, init=False)
        if not self._flavour.is_supported:
            raise NotImplementedError("cannot instantiate %r on your system"
                                      % (cls.__name__,))
        self._init(use_openat)
        return self

    def _init(self, use_openat=False,
              # Private non-constructor arguments
              template=None, parent_fd=None, fd=None,
              ):
        self._closed = False
        self._managed_fds = None
        self._parent_fd = parent_fd
        self._cached_fd = fd
        if parent_fd is not None:
            self._add_managed_fd(parent_fd)
        if fd is not None:
            self._add_managed_fd(fd)
        if template is not None:
            self._accessor = template._accessor
        elif use_openat:
            if not supports_openat:
                raise NotImplementedError("your system doesn't support openat()")
            self._accessor = _openat_accessor
        else:
            self._accessor = _normal_accessor
        self._accessor.init_path(self)

    def _make_child(self, args):
        child = self._accessor.make_child(self, args)
        if child is not None:
            return child
        parts = self._parts[:]
        parts.extend(args)
        return self._from_parts(parts)

    def _make_child_relpath(self, part):
        # This is an optimization used for dir walking.  `part` must be
        # a single part relative to this path.
        child = self._accessor.make_child(self, (part,))
        if child is not None:
            return child
        parts = self._parts + [part]
        return self._from_parsed_parts(self._drv, self._root, parts)

    @property
    def _stat(self):
        try:
            return self._cached_stat
        except AttributeError:
            pass
        st = self._accessor.stat(self)
        self._cached_stat = st
        return st

    @classmethod
    def _cleanup(cls, fds, wr_id=None):
        if wr_id is not None:
            del cls._wrs[wr_id]
        while fds:
            _sub_fd_ref(fds.pop())

    def _add_managed_fd(self, fd):
        """Add a file descriptor managed by this object."""
        if fd is None:
            return
        fds = self._managed_fds
        if fds is None:
            # This setup is done lazily so that most path objects avoid it
            fds = self._managed_fds = []
            cleanup = type(self)._cleanup
            # We can't hash the weakref directly since distinct Path objects
            # can compare equal.
            wr_id = next(self._wr_id)
            wr = weakref.ref(self, lambda wr: cleanup(fds, wr_id))
            self._wrs[wr_id] = wr
        _add_fd_ref(fd)
        fds.append(fd)

    def _sub_managed_fd(self, fd):
        """Remove a file descriptor managed by this object."""
        self._managed_fds.remove(fd)
        _sub_fd_ref(fd)

    def __enter__(self):
        if self._closed:
            self._raise_closed()
        return self

    def __exit__(self, t, v, tb):
        self._closed = True
        fds = self._managed_fds
        if fds is not None:
            self._managed_fds = None
            self._cached_fd = None
            self._parent_fd = None
            self._cleanup(fds)

    def _raise_closed(self):
        raise ValueError("I/O operation on closed path")

    def _opener(self, name, flags, mode=0o666):
        # A stub for the opener argument to built-in open()
        return self._accessor.open(self, flags, mode)

    # Public API

    @classmethod
    def cwd(cls, use_openat=False):
        """Return a new path pointing to the current working directory
        (as returned by os.getcwd()).
        """
        return cls(os.getcwd(), use_openat=use_openat)

    def __iter__(self):
        """Iterate over the files in this directory.  Does not yield any
        result for the special paths '.' and '..'.
        """
        if self._closed:
            self._raise_closed()
        for name in self._accessor.listdir(self):
            if name in {'.', '..'}:
                # Yielding a path object for these makes little sense
                continue
            yield self._make_child_relpath(name)
            if self._closed:
                self._raise_closed()

    def __getattr__(self, name):
        if name.startswith('st_'):
            return getattr(self._stat, name)
        return self.__getattribute__(name)

    def glob(self, pattern):
        """Iterate over this subtree and yield all existing files (of any
        kind, including directories) matching the given pattern.
        """
        pattern = self._flavour.casefold(pattern)
        drv, root, pattern_parts = self._flavour.parse_parts((pattern,))
        if drv or root:
            raise NotImplementedError("Non-relative patterns are unsupported")
        selector = _make_selector(tuple(pattern_parts))
        for p in selector.select_from(self):
            yield p

    def rglob(self, pattern):
        """Recursively yield all existing files (of any kind, including
        directories) matching the given pattern, anywhere in this subtree.
        """
        pattern = self._flavour.casefold(pattern)
        drv, root, pattern_parts = self._flavour.parse_parts((pattern,))
        if drv or root:
            raise NotImplementedError("Non-relative patterns are unsupported")
        selector = _make_selector(("**",) + tuple(pattern_parts))
        for p in selector.select_from(self):
            yield p

    def absolute(self):
        """Return an absolute version of this path.  This function works
        even if the path doesn't point to anything.

        No normalization is done, i.e. all '.' and '..' will be kept along.
        Use resolve() to get the canonical path to a file.
        """
        # XXX untested yet!
        if self._closed:
            self._raise_closed()
        if self.is_absolute():
            return self
        # FIXME this must defer to the specific flavour (and, under Windows,
        # use nt._getfullpathname())
        obj = self._from_parts([os.getcwd()] + self._parts, init=False)
        obj._init(template=self, parent_fd=self._parent_fd, fd=self._cached_fd)
        return obj

    def resolve(self):
        """
        Make the path absolute, resolving all symlinks on the way and also
        normalizing it (for example turning slashes into backslashes under
        Windows).
        """
        if self._closed:
            self._raise_closed()
        s = self._flavour.resolve(self)
        if s is None:
            # No symlink resolution => for consistency, raise an error if
            # the path doesn't exist or is forbidden
            self._stat
            s = str(self.absolute())
        # Now we have no symlinks in the path, it's safe to normalize it.
        normed = self._flavour.pathmod.normpath(s)
        obj = self._from_parts((normed,), init=False)
        obj._init(template=self, parent_fd=self._parent_fd, fd=self._cached_fd)
        return obj

    def stat(self):
        """
        Return the result of the stat() system call on this path, like
        os.stat() does.
        """
        return self._stat

    def restat(self):
        """
        Same as stat(), but resets the internal cache to force a fresh value.
        """
        try:
            del self._cached_stat
        except AttributeError:
            pass
        return self._stat

    @property
    def owner(self):
        """
        Return the login name of the file owner.
        """
        import pwd
        return pwd.getpwuid(self._stat.st_uid).pw_name

    @property
    def group(self):
        """
        Return the group name of the file gid.
        """
        import grp
        return grp.getgrgid(self._stat.st_gid).gr_name

    def raw_open(self, flags, mode=0o777):
        """
        Open the file pointed by this path and return a file descriptor,
        as os.open() does.
        """
        if self._closed:
            self._raise_closed()
        return self._accessor.open(self, flags, mode)

    def open(self, mode='r', buffering=-1, encoding=None,
             errors=None, newline=None):
        """
        Open the file pointed by this path and return a file object, as
        the built-in open() function does.
        """
        if self._closed:
            self._raise_closed()
        if sys.version_info >= (3, 3):
            return io.open(str(self), mode, buffering, encoding, errors, newline,
                           opener=self._opener)
        else:
            return io.open(str(self), mode, buffering, encoding, errors, newline)

    def touch(self, mode=0o666, exist_ok=True):
        """
        Create this file with the given access mode, if it doesn't exist.
        """
        if self._closed:
            self._raise_closed()
        flags = os.O_CREAT
        if not exist_ok:
            flags |= os.O_EXCL
        fd = self.raw_open(flags, mode)
        os.close(fd)

    def mkdir(self, mode=0o777, parents=False):
        if self._closed:
            self._raise_closed()
        if not parents:
            self._accessor.mkdir(self, mode)
        else:
            try:
                self._accessor.mkdir(self, mode)
            except OSError as e:
                if e.errno != ENOENT:
                    raise
                self.parent().mkdir(mode, True)
                self._accessor.mkdir(self, mode)

    def chmod(self, mode):
        """
        Change the permissions of the path, like os.chmod().
        """
        if self._closed:
            self._raise_closed()
        self._accessor.chmod(self, mode)

    def lchmod(self, mode):
        """
        Like chmod(), except if the path points to a symlink, the symlink's
        permissions are changed, rather than its target's.
        """
        if self._closed:
            self._raise_closed()
        self._accessor.lchmod(self, mode)

    def unlink(self):
        """
        Remove this file or link.
        If the path is a directory, use rmdir() instead.
        """
        if self._closed:
            self._raise_closed()
        self._accessor.unlink(self)

    def rmdir(self):
        """
        Remove this directory.  The directory must be empty.
        """
        if self._closed:
            self._raise_closed()
        self._accessor.rmdir(self)

    def lstat(self):
        """
        Like stat(), except if the path points to a symlink, the symlink's
        status information is returned, rather than its target's.
        """
        if self._closed:
            self._raise_closed()
        return self._accessor.lstat(self)

    def rename(self, target):
        """
        Rename this path to the given path.
        """
        if self._closed:
            self._raise_closed()
        self._accessor.rename(self, target)

    def replace(self, target):
        """
        Rename this path to the given path, clobbering the existing
        destination if it exists.
        """
        if sys.version_info < (3, 3):
            raise NotImplementedError("replace() is only available "
                                      "with Python 3.3 and later")
        if self._closed:
            self._raise_closed()
        self._accessor.replace(self, target)

    def symlink_to(self, target, target_is_directory=False):
        """
        Make this path a symlink pointing to the given path.
        Note the order of arguments (self, target) is the reverse of os.symlink's.
        """
        if self._closed:
            self._raise_closed()
        self._accessor.symlink(target, self, target_is_directory)

    # Convenience functions for querying the stat results

    def exists(self):
        """
        Whether this path exists.
        """
        try:
            self.restat()
        except OSError as e:
            if e.errno != ENOENT:
                raise
            return False
        return True

    def is_dir(self):
        """
        Whether this path is a directory.
        """
        return S_ISDIR(self._stat.st_mode)

    def is_file(self):
        """
        Whether this path is a regular file (also True for symlinks pointing
        to regular files).
        """
        return S_ISREG(self._stat.st_mode)

    def is_symlink(self):
        """
        Whether this path is a symbolic link.
        """
        st = self.lstat()
        return S_ISLNK(st.st_mode)


class PosixPath(Path, PurePosixPath):
    __slots__ = ()

class NTPath(Path, PureNTPath):
    __slots__ = ()

