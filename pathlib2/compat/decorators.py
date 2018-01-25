import sys
from functools import wraps

import six

if sys.version_info < (3, 6):
    from pathlib2 import PurePath
else:
    from pathlib import PurePath


def _path_to_string(arg):
    if isinstance(arg, PurePath):
        return str(arg)
    else:
        return arg


def path_compat(fn):
    """
    Decorate the given function `fn`, returning a function which parses its arguments to convert any instances of
    PurePath into strings before passing them to the wrapped function.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        stringified_args = tuple(_path_to_string(arg) for arg in args)
        stringified_kwargs = {key: _path_to_string(value) for key, value in six.iteritems(kwargs)}

        return fn(*stringified_args, **stringified_kwargs)

    return wrapper
