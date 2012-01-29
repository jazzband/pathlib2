
pathlib
=======

.. module:: pathlib
   :synopsis: Object-oriented filesystem paths

.. moduleauthor:: Antoine Pitrou <solipsis@pitrou.net>


Manipulating filesystem paths as string objects can quickly become cumbersome:
multiple calls to ``os.path.join`` or ``os.path.dirname``, etc.  This module
offers a set of path objects featuring all the common operations on path in
an easy, object-oriented way.

This module requires Python 3.2 or later.  If using it with Python 3.3,
you also have access to optional ``openat``-based filesystem operations.


Pure paths
----------

Pure path objects provide path-handling operations which don't actually
access a filesystem.  There are three ways to access these classes, which
we also call *flavours*:


.. class:: PurePosixPath

   A subclass of :class:`PurePath`, this path flavour represents POSIX
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

   >>> Path()
   PosixPath('.')

Any argument can be a string or bytes object representing an arbitrary number
of path segments, but it can also be another path object::

   >>> Path('foo', 'some/path', 'bar')
   PosixPath('foo/some/path/bar')
   >>> Path(Path('foo'), Path('bar'))
   PosixPath('foo/bar')

When several absolute paths are given, the last is taken as an anchor
(mimicking ``os.path.join``'s behaviour)::

   >>> Path('/etc', '/usr', 'lib64')
   PosixPath('/usr/lib64')
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

Indexing a path helps create children paths, similarly to ``os.path.join``::

   >>> p = PurePath('/etc')
   >>> p
   PurePosixPath('/etc')
   >>> p['passwd']
   PurePosixPath('/etc/passwd')
   >>> p['init.d/apache2']
   PurePosixPath('/etc/init.d/apache2')

The string representation of a path is the raw filesystem path itself, which
you can path to any function taking a file path as a string::

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

.. toctree::
   :maxdepth: 2


Methods and properties
^^^^^^^^^^^^^^^^^^^^^^

:class:



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

