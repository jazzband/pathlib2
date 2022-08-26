import sys

# wasm32-emscripten and -wasi are POSIX-like but do not
# have subprocess or fork support.
is_emscripten = sys.platform == "emscripten"
is_wasi = sys.platform == "wasi"
