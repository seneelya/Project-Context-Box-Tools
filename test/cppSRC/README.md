# cppSRC — C/C++ fixture (Plan08 / Vision09)

Files of **ggml-org/llama.cpp** at upstream commit `7fee1784646b6196bdff9c144326217720099a3c`,
copied WHOLE (byte-exact `git show`, never trimmed) with the real folder layout — include
resolution through `CPP_INCLUDE_DIRS` can't be tested otherwise. License: `LICENSE` (MIT).
Config for this root: `__HQ/tools/CONFIG__TOOLS.py`.

| file | lines | what it exercises |
|---|---|---|
| `ggml/include/ggml.h` | 3022 | big public API behind `GGML_API`; `GGML_DEPRECATED(...)` |
| `ggml/include/ggml-backend.h` | 437 | backend API, `GGML_BACKEND_API` |
| `ggml/include/ggml-cuda.h`, `ggml-vulkan.h` | 47 / 29 | small backend headers (pair with the impls below) |
| `ggml/src/ggml-backend-impl.h` | 291 | structs of function pointers (vtables) |
| `ggml/src/ggml-backend-reg.cpp` | 605 | `#ifdef GGML_USE_*` → `register_backend(...)`: the conditional hub |
| `ggml/src/ggml-backend-dl.{h,cpp}` | 45 / 48 | `dlopen` / `LoadLibrary` |
| `ggml/src/ggml-cuda/ggml-cuda.cu` | 5879 | `.cu` impl, vtable fill-in, includes `ggml-cuda/*.cuh` via `ggml/src` |
| `ggml/src/ggml-vulkan/ggml-vulkan.cpp` | 16553 | monster impl, vtable fill-in |
| `ggml/src/ggml-vulkan/ggml-vulkan-{common,push-constants,types}.h` | 309 / 1140 / 1454 | the ONLY path from `ggml-vulkan.cpp` to `ggml-vulkan.h` (transitive chain); `#if`-guarded `<spirv…>`, build-generated `ggml-vulkan-shaders.hpp` |

## Known links (hand-checked, quoted `#include "..."` only)

- `ggml-backend-reg.cpp` → `ggml-backend-impl.h`, `ggml-backend.h`, `ggml-backend-dl.h`,
  `ggml-impl.h` (NOT in the fixture → pending edge); then 16 `#include "ggml-<backend>.h"`
  (L30–90), EACH under its own `#ifdef GGML_USE_<BACKEND>` — `ggml-cuda.h` (L34) and
  `ggml-vulkan.h` (L46) resolve, the other 14 are outside the fixture (the "edge leaves the zone" case).
- `ggml-backend-dl.cpp` → `ggml-backend-dl.h` (which has only `<filesystem>`).
- `ggml-backend-impl.h` → `ggml-backend.h`; `ggml-backend.h` → `ggml.h`, `ggml-alloc.h` (outside);
  `ggml-cuda.h` / `ggml-vulkan.h` → `ggml.h`, `ggml-backend.h`.
- `ggml-cuda.cu` → `ggml-cuda.h`, `ggml-impl.h`, `ggml-backend-impl.h`, `ggml.h` (L73) + 68
  `ggml-cuda/*.cuh` (outside; they resolve only via `CPP_INCLUDE_DIRS` "ggml/src", not the file's folder).
- `ggml-vulkan.cpp` has ONE include: `ggml-vulkan-common.h` → `ggml-vulkan-push-constants.h` →
  `ggml-vulkan-types.h` → `ggml-vulkan.h`, `ggml-cpu.h` (outside), `ggml-impl.h` (outside),
  `ggml-backend-impl.h`, `ggml-vulkan-shaders.hpp` (generated at build time — exists nowhere in the tree).
  Own-folder resolution; the impl reaches its public header only transitively.
- Same-stem pairs: `ggml-cuda.h` ↔ `ggml-cuda/ggml-cuda.cu`, `ggml-vulkan.h` ↔
  `ggml-vulkan/ggml-vulkan.cpp`, `ggml-backend-dl.h` ↔ `ggml-backend-dl.cpp`.

Exact counts get pinned by the tests of each Plan08 step, not here.
