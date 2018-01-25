import os as std_os
import logging

from functools import wraps

from pathlib2.compat.decorators import path_compat, _path_to_string
from pathlib2.compat.constants import OS_PATH_FNS_TAKING_PATHS

logger = logging.getLogger(__name__)

for item in dir(std_os.path):
    if item in OS_PATH_FNS_TAKING_PATHS:
        try:
            locals()[item] = path_compat(getattr(std_os.path, item))
        except AttributeError:
            pass
    elif item == 'path':
        pass
    else:
        try:
            locals()[item] = getattr(std_os.path, item)
        except AttributeError:
            pass


@wraps(std_os.path.commonprefix)
def commonprefix(m):
    return std_os.path.commonprefix([_path_to_string(item) for item in m])
