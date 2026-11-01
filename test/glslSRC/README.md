# GLSL fixtures

Plan13 adds `vulkan-extensions.comp`: an independently written synthetic fixture
for control-flow attributes, cooperative/tensor types in fields and locals,
constructors and nearby comparisons. No llama.cpp source is copied here.
Run `test/test_glsl_preprocess.py` for protected strings/comments, malformed input,
false comparisons, byte offsets, CRLF/UTF-8 and idempotence. It also runs from test_glsl.py.

All fixtures are synthetic, written for the tests (no third-party or private shader code):
noise-field.fs — one-line functions, comment preamble, top-level #ifdef, and an #ifdef that
splits if/else in main (MISSING #endif); particles.fs — layout(location), struct, outputs;
quad.vs — vertex shader; preproc-split.fs — #ifdef branches split if/else inside a loop
(ERROR + MISSING inside main); declarations.glsl — names, structs/interfaces,
multi-declarators and comment preambles.
Expected ranges are hand-counted
in expected.py; golden output is reviewed separately.

Run with the interpreter containing the supplied capsule1 grammar:

    python -B test/check.py --fails
    python -B test/test_glsl.py
    python -B test/test_glsl_env.py

Full read-only PlanetWeather acceptance (needs that external source folder):

    python -B test/test_glsl.py --shaders Y:/AgentsWork/PlanetWeather/viewer_layered/export/shaders --baseline <baseline JSON> --out <outside the repo>

The baseline and run results embed shader source text, so they are kept outside this
repository (owner's machine: T:/AgentsWork/glsl-wheel-plan10/review-archive/).

Set TEMP/TMP on T: before testing on the owner's machine.
