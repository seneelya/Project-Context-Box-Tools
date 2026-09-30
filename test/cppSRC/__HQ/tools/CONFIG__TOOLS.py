"""CONFIG__TOOLS for the cppSRC fixture (Plan08). Read by card tools via `load_config_at(test/cppSRC)`
(REQ-007: a foreign --project-root R -> R/__HQ/tools/CONFIG__TOOLS.py). Keys the C/C++ stamp uses."""

CONFIG_SCHEMA_VERSION = 2
LANGUAGE = "cpp"
TEST_DIRS = []

# `#include "x.h"` resolution after the including file's own folder, in this order
# (root-relative). llama.cpp's CMake adds these; ggml-cuda.cu includes "ggml-cuda/cumsum.cuh"
# from ggml/src/ggml-cuda/ — resolves only via "ggml/src", not via its own folder.
CPP_INCLUDE_DIRS = ["ggml/include", "ggml/src"]

# Export/attribute macros that sit in front of declarations and confuse the parser —
# cut out before parsing (NOT GGML_UNUSED: a statement inside bodies).
CPP_STRIP_MACROS = ["GGML_API", "GGML_BACKEND_API", "GGML_RESTRICT", "GGML_NORETURN"]

# Function-like macros that WRAP a whole declaration: `GGML_DEPRECATED(GGML_API void f(), "hint")`
# -> `void f()`. Without it tree-sitter loses ~1100 lines of ggml.h (reported as opaque).
CPP_WRAPPER_MACROS = ["GGML_DEPRECATED"]

# Header <-> implementation pairs the same-stem rule can't find (root-relative). Same stem pairs
# itself (ggml-cuda.h <-> ggml-cuda/ggml-cuda.cu); nothing disputed in this fixture yet.
CPP_PAIRS = {}
