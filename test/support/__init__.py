import os
import stat
import sys

# wasm32-emscripten and -wasi are POSIX-like but do not
# have subprocess or fork support.
is_emscripten = sys.platform == "emscripten"
is_wasi = sys.platform == "wasi"

verbose = 1              # Flag set to 0 by regrtest.py

def _force_run(path, func, *args):
    try:
        return func(*args)
    except FileNotFoundError as err:
        # chmod() won't fix a missing file.
        if verbose >= 2:
            print('%s: %s' % (err.__class__.__name__, err))
        raise
    except OSError as err:
        if verbose >= 2:
            print('%s: %s' % (err.__class__.__name__, err))
            print('re-run %s%r' % (func.__name__, args))
        os.chmod(path, stat.S_IRWXU)
        return func(*args)
