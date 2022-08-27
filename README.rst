pathlib2
========

|jazzband| |github| |codecov|

Fork of pathlib aiming to support the full stdlib Python API.

The `old pathlib <https://web.archive.org/web/20181106215056/https://bitbucket.org/pitrou/pathlib/>`_
module on bitbucket is no longer maintained.
The goal of pathlib2 is to provide a backport of
`standard pathlib <http://docs.python.org/dev/library/pathlib.html>`_
module which tracks the standard library module,
so all the newest features of the standard pathlib can be
used also on older Python versions.

Download
--------

Standalone releases are available on PyPI:
http://pypi.python.org/pypi/pathlib2/

Development
-----------

The main development takes place in the Python standard library: see
the `Python developer's guide <http://docs.python.org/devguide/>`_.
In particular, new features should be submitted to the
`Python bug tracker <http://bugs.python.org/>`_.

Issues that occur in this backport, but that do not occur not in the
standard Python pathlib module can be submitted on
the `pathlib2 bug tracker <https://github.com/jazzband/pathlib2/issues>`_.

Syncing with the Python standard library
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

As of `Python 3.11.0rc1`, the following files need to be copied from the CPython reference implementation to `pathlib2`:

* `Doc/library/pathlib.rst` -> `docs/pathlib2.rst`
* `Lib/pathlib.py` -> `pathlib2/__init__.py`
* `Lib/test/test_pathlib.py` -> `test/test_pathlib2.py`
* `Lib/test/support/os_helper.py` -> `test/support/os_helper.py`

To facilitate the backporting process, we store a set of patch files in the `dev` directory:

* changes made to `pathlib2/__init__.py` to make it work on older versions of Python
* changes made to `test/test_pathlib2.py` to adjust the tests to run on older versions of Python and use backported support functions.
* changes made to `test/support/os_helper.py` to conditionally import `contextlib2`.

Documentation
-------------

Refer to the
`standard pathlib <http://docs.python.org/dev/library/pathlib.html>`_
documentation.

.. |github| image:: https://github.com/jazzband/pathlib2/actions/workflows/python-package.yml/badge.svg
   :target: https://github.com/jazzband/pathlib2/actions/workflows/python-package.yml
   :alt: github

.. |codecov| image:: https://codecov.io/gh/jazzband/pathlib2/branch/develop/graph/badge.svg
    :target: https://codecov.io/gh/jazzband/pathlib2
    :alt: codecov

.. |jazzband| image:: https://jazzband.co/static/img/badge.svg
   :alt: Jazzband
   :target: https://jazzband.co/
