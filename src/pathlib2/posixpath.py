import os
import stat
from os.path import abspath, split, join


def realpath(filename, *, strict=False):
    """Return the canonical path of the specified filename, eliminating any
symbolic links encountered in the path."""
    filename = os.fspath(filename)
    path, ok = _joinrealpath(filename[:0], filename, strict, {})
    return abspath(path)


# Join two paths, normalizing and eliminating any symbolic links
# encountered in the second path.
def _joinrealpath(path, rest, strict, seen):
    if isinstance(path, bytes):
        sep = b'/'
        curdir = b'.'
        pardir = b'..'
    else:
        sep = '/'
        curdir = '.'
        pardir = '..'

    if isabs(rest):
        rest = rest[1:]
        path = sep

    while rest:
        name, _, rest = rest.partition(sep)
        if not name or name == curdir:
            # current dir
            continue
        if name == pardir:
            # parent dir
            if path:
                path, name = split(path)
                if name == pardir:
                    path = join(path, pardir, pardir)
            else:
                path = pardir
            continue
        newpath = join(path, name)
        try:
            st = os.lstat(newpath)
        except OSError:
            if strict:
                raise
            is_link = False
        else:
            is_link = stat.S_ISLNK(st.st_mode)
        if not is_link:
            path = newpath
            continue
        # Resolve the symbolic link
        if newpath in seen:
            # Already seen this path
            path = seen[newpath]
            if path is not None:
                # use cached value
                continue
            # The symlink is not resolved, so we must have a symlink loop.
            if strict:
                # Raise OSError(errno.ELOOP)
                os.stat(newpath)
            else:
                # Return already resolved part + rest of the path unchanged.
                return join(newpath, rest), False
        seen[newpath] = None # not resolved symlink
        path, ok = _joinrealpath(path, os.readlink(newpath), strict, seen)
        if not ok:
            return join(path, rest), False
        seen[newpath] = path # resolved symlink

    return path, True
