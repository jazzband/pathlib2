
pathlib
=======

.. module:: pathlib
   :synopsis: Object-oriented filesystem paths

.. moduleauthor:: Antoine Pitrou <solipsis@pitrou.net>

.. toctree::
   :maxdepth: 2


Manipulating filesystem paths as string objects can quickly become cumbersome:
multiple calls to :func:`os.path.join` or :func:`os.path.dirname`, etc.
This module offers a set of classes featuring all the common operations on
paths in an easy, object-oriented way.

This module requires Python 3.2 or later.  If using it with Python 3.3,
you also have access to optional ``openat``-based filesystem operations.


Download
--------

Releases are available on PyPI: http://pypi.python.org/pypi/pathlib/

The development repository and issue tracker can be found at BitBucket:
https://bitbucket.org/pitrou/pathlib/


Basic use
---------

   >>> from pathlib import *
   >>> p = Path('setup.py')
   >>> p
   PosixPath('setup.py')
   >>> p.is_absolute()
   False
   >>> p = p.resolve()
   >>> p
   PosixPath('/home/antoine/pathlib/setup.py')
   >>> p.parent()
   PosixPath('/home/antoine/pathlib')
   >>> p.open().readline()
   '#!/usr/bin/env python3\n'

   >>> import pprint
   >>> p = Path('.')
   >>> [x for x in p if x.ext == '.py']
   [PosixPath('test_pathlib.py'), PosixPath('setup.py'), PosixPath('pathlib.py')]
   >>> child = p['docs']
   >>> pprint.pprint(list(child))
   [PosixPath('docs/conf.py'),
    PosixPath('docs/_templates'),
    PosixPath('docs/make.bat'),
    PosixPath('docs/index.rst'),
    PosixPath('docs/_build'),
    PosixPath('docs/_static'),
    PosixPath('docs/Makefile')]


Pure paths
----------

Pure path objects provide path-handling operations which don't actually
access a filesystem.  There are three ways to access these classes, which
we also call *flavours*:


.. class:: PurePosixPath

   A subclass of :class:`PurePath`, this path flavour represents non-Windows
   filesystem paths::

      >>> PurePosixPath('/etc')
      PurePosixPath('/etc')

.. class:: PureNTPath

   A subclass of :class:`PurePath`, this path flavour represents Windows
   filesystem paths::

      >>> PureNTPath('c:/Program Files/')
      PureNTPath('c:\\Program Files')

.. class:: PurePath

   A generic class that represents the system's path flavour (instantiating
   it creates either a :class:`PurePosixPath` or a :class:`PureNTPath`)::

      >>> PurePath('setup.py')
      PurePosixPath('setup.py')


Regardless of the system you're running on, you can instantiate all of
these classes, since they don't provide any operation that does system calls.


Constructing paths
^^^^^^^^^^^^^^^^^^

Path constructors accept an arbitrary number of positional arguments.
When called without any argument, a path object points to the current
directory::

   >>> PurePath()
   PurePosixPath('.')

Any argument can be a string or bytes object representing an arbitrary number
of path segments, but it can also be another path object::

   >>> PurePath('foo', 'some/path', 'bar')
   PurePosixPath('foo/some/path/bar')
   >>> PurePath(Path('foo'), Path('bar'))
   PurePosixPath('foo/bar')

When several absolute paths are given, the last is taken as an anchor
(mimicking ``os.path.join``'s behaviour)::

   >>> PurePath('/etc', '/usr', 'lib64')
   PurePosixPath('/usr/lib64')
   >>> PureNTPath('c:/Windows', 'd:bar')
   PureNTPath('d:bar')

However, in a Windows path, changing the local root doesn't discard the
previous drive setting::

   >>> PureNTPath('c:/Windows', '/Program Files')
   PureNTPath('c:\\Program Files')

Spurious slashes and single dots are collapsed, but double dots (``'..'``)
are not, since this would change the meaning of a path in the face of
symbolic links::

   >>> PurePath('foo//bar')
   PurePosixPath('foo/bar')
   >>> PurePath('foo/./bar')
   PurePosixPath('foo/bar')
   >>> PurePath('foo/../bar')
   PurePosixPath('foo/../bar')

(a naïve approach would make ``PurePosixPath('foo/../bar')`` equivalent
to ``PurePosixPath('bar')``, which is wrong if ``foo`` is a symbolic link
to another directory)


General properties
^^^^^^^^^^^^^^^^^^

Paths are immutable and hashable.  Paths of a same flavour are comparable
and orderable.  These properties respect the flavour's case-folding
semantics::

   >>> PurePosixPath('foo') == PurePosixPath('FOO')
   False
   >>> PureNTPath('foo') == PureNTPath('FOO')
   True
   >>> PureNTPath('FOO') in { PureNTPath('foo') }
   True
   >>> PureNTPath('C:') < PureNTPath('d:')
   True

Paths of a different flavour compare unequal and cannot be ordered::

   >>> PureNTPath('foo') == PurePosixPath('foo')
   False
   >>> PureNTPath('foo') < PurePosixPath('foo')
   Traceback (most recent call last):
     File "<stdin>", line 1, in <module>
   TypeError: unorderable types: PureNTPath() < PurePosixPath()


Operators
^^^^^^^^^

Indexing a path helps create child paths, similarly to ``os.path.join``::

   >>> p = PurePath('/etc')
   >>> p
   PurePosixPath('/etc')
   >>> p['passwd']
   PurePosixPath('/etc/passwd')
   >>> p['init.d/apache2']
   PurePosixPath('/etc/init.d/apache2')

The string representation of a path is the raw filesystem path itself, which
you can pass to any function taking a file path as a string::

   >>> p = PurePath('/etc')
   >>> str(p)
   '/etc'

Similarly, calling ``bytes`` on a path gives the raw filesystem path as a
bytes object::

   >>> bytes(p)
   b'/etc'


Accessing individual parts
^^^^^^^^^^^^^^^^^^^^^^^^^^

To access the individual "parts" (components) of a path, use the following
property:

.. data:: PurePath.parts

   An immutable sequence-like object giving access to the path's various
   components.  Indexing this object returns individual strings, while
   slicing this object returns other path objects of the same flavour::

      >>> p = PurePath('/usr/bin/python3')
      >>> p.parts
      <PurePosixPath.parts: ['/', 'usr', 'bin', 'python3']>
      >>> p.parts[0]
      '/'
      >>> p.parts[-1]
      'python3'
      >>> p.parts[1:]
      PurePosixPath('usr/bin/python3')
      >>> p.parts[:-1]
      PurePosixPath('/usr/bin')

      >>> p = PureNTPath('c:/Program Files/PSF')
      >>> p.parts[0]
      'c:\\'
      >>> p.parts[1:]
      PureNTPath('Program Files\\PSF')

   (note how the drive and local root are regrouped in a single part)


Methods and properties
^^^^^^^^^^^^^^^^^^^^^^

Pure paths provide the following methods an properties:

.. data:: PurePath.drive

   A string representing the drive letter or name, if any::

      >>> PureNTPath('c:/Program Files/').drive
      'c:'
      >>> PureNTPath('/Program Files/').drive
      ''
      >>> PurePosixPath('/etc').drive
      ''

   UNC shares are also considered drives::

      >>> PureNTPath('//some/share/foo.txt').drive
      '\\\\some\\share'

.. data:: PurePath.root

   A string representing the (local or global) root, if any::

      >>> PureNTPath('c:/Program Files/').root
      '\\'
      >>> PureNTPath('c:Program Files/').root
      ''
      >>> PurePosixPath('/etc').root
      '/'

   UNC shares always have a root::

      >>> PureNTPath('//some/share').root
      '\\'


.. data:: PurePath.ext

   A string representing the file extension of the final component, if any::

      >>> PurePosixPath('my/library/setup.py').ext
      '.py'
      >>> PurePosixPath('my/library.tar.gz').ext
      '.tar.gz'
      >>> PurePosixPath('my/library').ext
      ''

   UNC drive names are not considered::

      >>> PureNTPath('//some/share/setup.py').ext
      '.py'
      >>> PureNTPath('//some.txt/share.py').ext
      ''


.. method:: PurePath.as_bytes()

   Equivalent to calling ``bytes()`` on the path object::

      >>> PurePosixPath('/etc').as_bytes()
      b'/etc'


.. method:: PurePath.as_posix()

   Return a string representation of the path with forward slashes (``/``)::

      >>> p = PureNTPath('c:\\windows')
      >>> str(p)
      'c:\\windows'
      >>> p.as_posix()
      'c:/windows'


.. method:: PurePath.is_absolute()

   Return whether the path is absolute or not.  A path is considered absolute
   if it has both a root and (if the flavour allows) a drive::

      >>> PurePosixPath('/a/b').is_absolute()
      True
      >>> PurePosixPath('a/b').is_absolute()
      False

      >>> PureNTPath('c:/a/b').is_absolute()
      True
      >>> PureNTPath('/a/b').is_absolute()
      False
      >>> PureNTPath('c:').is_absolute()
      False
      >>> PureNTPath('//some/share').is_absolute()
      True


.. method:: PurePath.is_reserved()

   With :class:`PureNTPath`, return True if the path is considered reserved
   under Windows, False otherwise.  With :class:`PurePosixPath`, False is
   always returned.

      >>> PureNTPath('nul').is_reserved()
      True
      >>> PurePosixPath('nul').is_reserved()
      False

   File system calls on reserved paths can fail mysteriously or have
   unintended effects.


.. method:: PurePath.join(*other)

   Calling this method is equivalent to indexing the path with each of
   the *other* arguments in turn::

      >>> PurePosixPath('/etc').join('passwd')
      PurePosixPath('/etc/passwd')
      >>> PurePosixPath('/etc').join(PurePosixPath('passwd'))
      PurePosixPath('/etc/passwd')
      >>> PurePosixPath('/etc').join('init.d', 'apache2')
      PurePosixPath('/etc/init.d/apache2')
      >>> PureNTPath('c:').join('/Program Files')
      PureNTPath('c:\\Program Files')


.. method:: PurePath.normcase()

   Return a case-folded version of the path.  Calling this method is *not*
   needed before comparing path objects.


.. method:: PurePath.relative()

   Return the path object stripped of its drive and root, if any::

      >>> PurePosixPath('/etc/passwd').relative()
      PurePosixPath('etc/passwd')
      >>> PurePosixPath('lib/setup.py').relative()
      PurePosixPath('lib/setup.py')

      >>> PureNTPath('//some/share/setup.py').relative()
      PureNTPath('setup.py')
      >>> PureNTPath('//some/share/lib/setup.py').relative()
      PureNTPath('lib\\setup.py')


.. method:: PurePath.relative_to(*other)

   Compute a version of this path relative to the path represented by
   *other*.  If it's impossible, ValueError is raised::

      >>> p = PurePosixPath('/etc/passwd')
      >>> p.relative_to('/')
      PurePosixPath('etc/passwd')
      >>> p.relative_to('/etc')
      PurePosixPath('passwd')
      >>> p.relative_to('/usr')
      Traceback (most recent call last):
        File "<stdin>", line 1, in <module>
        File "pathlib.py", line 694, in relative_to
          .format(str(self), str(formatted)))
      ValueError: '/etc/passwd' does not start with '/usr'


.. method:: PurePath.parent(level=1)

   Return the path's parent at the *level*'th level.  If *level* is not given,
   return the path's immediate parent::

      >>> p = PurePosixPath('/a/b/c/d')
      >>> p.parent()
      PurePosixPath('/a/b/c')
      >>> p.parent(2)
      PurePosixPath('/a/b')
      >>> p.parent(3)
      PurePosixPath('/a')
      >>> p.parent(4)
      PurePosixPath('/')


.. method:: PurePath.parents()

   Iterate over the path's parents from the most to the least specific::

      >>> for p in PureNTPath('c:/foo/bar/setup.py').parents(): p
      ...
      PureNTPath('c:\\foo\\bar')
      PureNTPath('c:\\foo')
      PureNTPath('c:\\')


Concrete paths
--------------

Concrete paths are subclasses of the pure path classes.  In addition to
operations provided by the latter, they also provide methods to do system
calls on path objects.  There are three ways to instantiate concrete paths:


.. class:: PosixPath

   A subclass of :class:`Path` and :class:`PurePosixPath`, this class
   represents concrete non-Windows filesystem paths::

      >>> PosixPath('/etc')
      PosixPath('/etc')

.. class:: NTPath

   A subclass of :class:`Path` and :class:`PureNTPath`, this class represents
   concrete Windows filesystem paths::

      >>> NTPath('c:/Program Files/')
      NTPath('c:\\Program Files')

.. class:: Path

   A subclass of :class:`PurePath`, this class represents concrete paths of
   the system's path flavour (instantiating it creates either a
   :class:`PosixPath` or a :class:`NTPath`)::

      >>> Path('setup.py')
      PosixPath('setup.py')


You can only instantiate the class flavour that corresponds to your system
(allowing system calls on non-compatible path flavours could lead to
bugs or failures in your application)::

   >>> import os
   >>> os.name
   'posix'
   >>> Path('setup.py')
   PosixPath('setup.py')
   >>> PosixPath('setup.py')
   PosixPath('setup.py')
   >>> NTPath('setup.py')
   Traceback (most recent call last):
     File "<stdin>", line 1, in <module>
     File "pathlib.py", line 798, in __new__
       % (cls.__name__,))
   NotImplementedError: cannot instantiate 'NTPath' on your system


Operations
^^^^^^^^^^

When a concrete path points to a directory, iterating over it yields path
objects of the directory contents::

   >>> p = Path('docs')
   >>> for child in p: child
   ...
   PosixPath('docs/conf.py')
   PosixPath('docs/_templates')
   PosixPath('docs/make.bat')
   PosixPath('docs/index.rst')
   PosixPath('docs/_build')
   PosixPath('docs/_static')
   PosixPath('docs/Makefile')


Methods
^^^^^^^

Concrete paths provide the following methods in addition to pure paths
methods.  Many of these methods can raise an :exc:`OSError` if a system
call fails (for example because the path doesn't exist):

.. classmethod:: Path.cwd()

   Return a new path object representing the current directory (as returned
   by :func:`os.getcwd`)::

      >>> Path.cwd()
      PosixPath('/home/antoine/pathlib')


.. method:: Path.stat()

   Return information about this path (similarly to :func:`os.stat`).
   The result is cached accross calls.

      >>> p = Path('setup.py')
      >>> p.stat().st_size
      956
      >>> p.stat().st_mtime
      1327883547.852554

   This information can also be accessed through :ref:`helper attributes <st_attrs>`.


.. method:: Path.restat()

   Like :meth:`Path.stat`, but ignores the cached value and always invokes
   the underlying system call.


.. method:: Path.chmod(mode)

   Change the file mode and permissions, like :func:`os.chmod`::

      >>> p = Path('setup.py')
      >>> p.stat().st_mode
      33277
      >>> p.chmod(0o444)
      >>> p.restat().st_mode
      33060


.. method:: Path.exists()

   Whether the path points to an existing file or directory::

      >>> from pathlib import *
      >>> Path('.').exists()
      True
      >>> Path('setup.py').exists()
      True
      >>> Path('/etc').exists()
      True
      >>> Path('nonexistentfile').exists()
      False


.. method:: Path.is_dir()

   Return True if the path points to a directory, False if it points to
   another kind of file::

      >>> Path('.').is_dir()
      True
      >>> Path('setup.py').is_dir()
      False


.. method:: Path.lchmod(mode)

   Like :meth:`Path.chmod` but, if the path points to a symbolic link, the
   symbolic link's mode is changed rather than its target's.


.. method:: Path.lstat()

   Like :meth:`Path.stat` but, if the path points to a symbolic link, return
   the symbolic link's information rather than its target's.


.. method:: Path.open(mode='r', buffering=-1, encoding=None, errors=None, newline=None)

   Open the file pointed to by the path, like the built-in :func:`open`
   function does::

      >>> p = Path('setup.py')
      >>> with p.open() as f:
      ...     f.readline()
      ...
      '#!/usr/bin/env python3\n'


.. method:: Path.raw_open(flags, mode=0o777)

   Open the file pointed to by the path and return a numeric file descriptor,
   as :func:`os.open` does::

      >>> p = Path('setup.py')
      >>> fd = p.raw_open(os.O_RDONLY)
      >>> os.read(fd, 10)
      b'#!/usr/bin'
      >>> os.close(fd)


.. method:: Path.rename(target)

   Rename this file or directory to the given *target*.  *target* can be
   either a string or another path object::

      >>> p = Path('foo')
      >>> p.open('w').write('some text')
      9
      >>> target = Path('bar')
      >>> p.rename(target)
      >>> target.open().read()
      'some text'


.. method:: Path.resolve()

   Make the path absolute, resolving any symlinks.  A new path object is
   returned::

      >>> p = Path()
      >>> p
      PosixPath('.')
      >>> p.resolve()
      PosixPath('/home/antoine/pathlib')

   If the path doesn't exist, an :exc:`OSError` is raised.


.. method:: Path.rmdir()

   Remove this directory.  The directory must be empty.


.. method:: Path.symlink_to(target)

   Make this path a symbolic link to *target*.

      >>> p = Path('mylink')
      >>> p.symlink_to('setup.py')
      >>> p.resolve()
      PosixPath('/home/antoine/pathlib/setup.py')
      >>> p.stat().st_size
      956
      >>> p.lstat().st_size
      8

   .. note::
      The order of arguments (link, target) is the reverse
      of :func:`os.symlink`'s.


.. method:: Path.unlink()

   Remove this file or symbolic link.  If the path points to a directory,
   use :func:`Path.rmdir` instead.


.. _st_attrs:

Attributes
^^^^^^^^^^

Concrete paths provide the following attributes:

.. data::
      Path.st_mode
      Path.st_ino
      Path.st_dev
      Path.st_nlink
      Path.st_uid
      Path.st_gid
      Path.st_size
      Path.st_atime
      Path.st_mtime
      Path.st_ctime
      ...

   Helper attributes returning the corresponding fields on :meth:`Path.stat`'s
   result::

      >>> p = Path('setup.py')
      >>> p.st_size
      956
      >>> p.st_mtime
      1327939910.2178059
