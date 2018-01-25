import sys
import pathlib2.utils

if sys.version_info < (3, 6):
    import pathlib2.backport

    for item in dir(pathlib2.backport):
        locals()[item] = getattr(pathlib2.backport, item)
else:
    import pathlib
    for item in dir(pathlib):
        locals()[item] = getattr(pathlib, item)

import pathlib2.compat as compat
