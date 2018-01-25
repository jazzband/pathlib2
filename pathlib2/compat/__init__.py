import sys
from pathlib2.compat import decorators

__all__ = ['os', 'open']

if sys.version_info < (3, 6):
    from pathlib2.compat import os

    open = decorators.path_compat(open)
else:
    import os

    open = open
