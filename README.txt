pathlib offers a set of classes to handle filesystem paths.  It offers the
following advantages over using string objects:

* No more cumbersome use of os and os.path functions.  Everything can be
  done easily through operators, attribute accesses, and method calls.

* Embodies the semantics of different path types.  For example, comparing
  Windows paths ignores casing.

* Well-defined semantics, eliminating any warts or ambiguities (forward vs.
  backward slashes, etc.).

Requirements
------------

Python 3.2 or later is recommended, but pathlib is also usable with Python 2.7.

Install
-------

In Python 3.4, pathlib is now part of the standard library.  For Python 3.3
and earlier, ``easy_install pathlib`` or ``pip install pathlib`` should do
the trick.

Examples
--------

Importing the module classes::

   >>> from pathlib import *

Listing Python source files in a directory:

   >>> list(p.glob('*.py'))
   [PosixPath('test_pathlib.py'), PosixPath('setup.py'),
    PosixPath('pathlib.py')]

Navigating inside a directory tree::

   >>> p = Path('/etc')
   >>> q = p / 'init.d' / 'reboot'
   >>> q
   PosixPath('/etc/init.d/reboot')
   >>> q.resolve()
   PosixPath('/etc/rc.d/init.d/halt')

Querying path properties::

   >>> q.exists()
   True
   >>> q.is_dir()
   False

Opening a file::

   >>> with q.open() as f: f.readline()
   ...
   '#!/bin/bash\n'


Documentation
-------------

The full documentation can be read at `Read the Docs
<https://pathlib.readthedocs.org/>`_.


Contributing
------------

The issue tracker and repository are hosted by `BitBucket
<https://bitbucket.org/pitrou/pathlib/>`_.


History
-------

Version 0.97
^^^^^^^^^^^^

- Reintegrate all changes made for :pep:`428`; they are too long to list
  here.

.. warning::
   The API in this version is changed from pathlib 0.8 and earlier.

Version 0.8
^^^^^^^^^^^

- Add PurePath.name and PurePath.anchor.
- Add Path.owner and Path.group.
- Add Path.replace().
- Add Path.as_uri().
- Issue #10: when creating a file with Path.open(), don't set the executable
  bit.
- Issue #11: fix comparisons with non-Path objects.

Version 0.7
^^^^^^^^^^^

- Add '**' (recursive) patterns to Path.glob().
- Fix openat() support after the API refactoring in Python 3.3 beta1.
- Add a *target_is_directory* argument to Path.symlink_to()

Version 0.6
^^^^^^^^^^^

- Add Path.is_file() and Path.is_symlink()
- Add Path.glob() and Path.rglob()
- Add PurePath.match()

Version 0.5
^^^^^^^^^^^

- Add Path.mkdir().
- Add Python 2.7 compatibility by Michele Lacchia.
- Make parent() raise ValueError when the level is greater than the path
  length.
