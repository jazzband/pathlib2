import os as std_os
import logging

from pathlib2.compat.os import path
from pathlib2.compat.decorators import path_compat
from pathlib2.compat.constants import OS_FNS_TAKING_PATHS

logger = logging.getLogger(__name__)

for item in dir(std_os):
    if item in OS_FNS_TAKING_PATHS:
        try:
            locals()[item] = path_compat(getattr(std_os, item))
        except AttributeError:
            pass
    elif item == 'path':
        pass
    else:
        try:
            locals()[item] = getattr(std_os, item)
        except AttributeError:
            pass
