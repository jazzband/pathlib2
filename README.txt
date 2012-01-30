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

Python 3.2 or later is required.

Install
-------

``easy_install pathlib`` or ``pip install pathlib`` should do the trick.

Examples
--------

Importing the module classes::

    >>> from pathlib import *

Listing Python source files in a directory::

    >>> p = Path('.')
    >>> [x for x in p if x.ext == '.py']
    [PosixPath('test_pathlib.py'), PosixPath('setup.py'),
     PosixPath('pathlib.py')]

Listing subdirectories::

    >>> [x for x in p if x.is_dir()]
    [PosixPath('.hg'), PosixPath('docs'), PosixPath('dist'),
     PosixPath('__pycache__'), PosixPath('build')]

Navigating inside a directory tree::

    >>> p = Path('/etc')
    >>> q = p['init.d/reboot']
    >>> q
    PosixPath('/etc/init.d/reboot')
    >>> q.resolve()
    PosixPath('/etc/rc.d/init.d/halt')

Querying path properties::

    >>> q.exists()
    True
    >>> q.is_dir()
    False
    >>> q.st_mode
    33261

Opening a file::

    >>> with q.open() as f: f.readline()
    ...
    '#!/bin/bash\n'


Documentation
-------------

The full documentation can be read at `Read the Docs
<http://readthedocs.org/docs/pathlib/en/latest/>`_.

