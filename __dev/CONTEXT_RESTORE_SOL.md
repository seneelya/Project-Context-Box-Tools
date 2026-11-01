# CONTEXT_RESTORE_SOL — Plan11 completed, awaiting Claude review

Updated: 2026-11-01. Work is in **T:/AgentsWork/ProjectStarter/__HQ/tools**,
an independent nested Git repo. **Plan11 implementation is complete, uncommitted**.
Do not restart at step 0. Check git status, read the report, review the changes.
Last committed checkpoint: **f88fb17**; no new commit/push/deploy was made.

## Read first

1. **__dev/review/GLSL_INTEGRATION.md** — full steps 0–7, 22-file table,
   tests, ERROR recovery, exact delivery limitations and commands.
2. **__dev/plans/Plan11__glsl-in-get-codeblock.md** — approved D1–D9 and acceptance;
   implementation remains in working tree for Claude review/commit.
3. Tail __dev/TRACKER.md; __dev/DECISIONS.md; __dev/CONTEXT_RESTORE_TOOLS.md.
4. get_codeblock/reader/CONTRACT.md — invariants + new node_rules seam.
5. For build provenance only: wheels/README.md, wheels/build_manifest.json,
   __dev/review/GLSL_BUILD.md. Plan10 and its KICKBACK are now in plans/done.
   Plan11 KICKBACK is closed. Do not reopen accepted D1–D9.

## Runtime and restrictions

- **All new temp/cache/build data on T:. No temporary C: usage.**
- Reference Python: T:/AgentsWork/venv/Scripts/python.exe (3.12.10 Windows x64).
- **tree-sitter 0.26.0 unchanged**. Grammar already installed:
  **tree-sitter-glsl-spec 1.0.0+capsule1**.
- Installed _binding.pyd SHA256:
  53282c3421928a144513a02671534713d8c5b8558ed2c578e85ad72caf763e8b.
- Wheel wheels/tree_sitter_glsl_spec-1.0.0+capsule1-cp310-abi3-win_amd64.whl SHA256:
  6c18b83d121fa32da65c45e86c670d53e9ad4bf8793cbc59235d924c8193ba2a.
- Do not install into Hermes Python, touch Y:/Hermess, restart gateway/services,
  push/deploy or manually copy vendors. Plan11 says Claude reviews and commits.
- Original PlanetWeather shaders are READ-ONLY; fixtures are under test/glslSRC.
- No source map cards in this lightweight tools workshop (DECISIONS).
- Read source with get_codeblock --outline then selected --name/--line --query.
- Normal sandbox exec previously failed to start; scoped require_escalated worked.

Initialize EVERY fresh tool process:

```powershell
Set-Location 'T:/AgentsWork/ProjectStarter/__HQ/tools'
$py = 'T:/AgentsWork/venv/Scripts/python.exe'
$env:TEMP = 'T:/AgentsWork/glsl-wheel-plan10/tmp'
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = 'T:/AgentsWork/glsl-wheel-plan10/pip-cache'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONIOENCODING = 'utf-8'
Remove-Item Env:PYTHONPATH,Env:GLSL_PROBE_RUNTIME,Env:PYTHONHOME,Env:PYTHONPYCACHEPREFIX -ErrorAction SilentlyContinue
```

## Implementation

VERSION **0.10.0**. GLSL extensions .glsl .vert .frag .geom .comp .tesc .tese .vs .fs.
Profile: get_codeblock/reader/profiles/glsl.py, all registry wiring completed.
No GLSL branches in classify/render/address engines; shared handlers LangSpecs unchanged.
One optional profile-driven node_rules normalization in TSNode/TSBackend, same RNode
for map/addressing/names. Rules flatten wrappers, normalize interface/struct bodies,
field paths, directive end row and inline comments. Full-line comments remain preambles;
inline comments remain in owner source lines without a separate structural node.
This avoids earlier map/address disagreement and signature-line filler replacing function.
No preprocessor branch removed, no source preprocessing/masking.

Point guard in test/point_guard.py called by check.py; verified two temporary unsafe
reads are caught, injection removed. Never access Point.row/column on runtime 0.26.0.
Historical __dev diagnostics are intentionally excluded. No ctypes bridge.

D7 uses optional env_check dictionary data for artifact/platform/capsule_module;
old language lists keep old messages. requirements.txt has only wheel README comment.

## Verification already completed

- Installed wheel indexed acceptance WITHOUT PYTHONPATH: **480/480** (exit 0).
  __dev/review/glsl_probe_results_runtime26_installed_plan11.json.
- Full target: **22 files / 4464 physical lines / 348 raw functions PASS**;
  all names forced CLI equal forced signature-line query, source hashes baseline match,
  every rung contains target, map landmarks agree, query text exact including line ends.
  __dev/review/glsl_integration_results.json includes ERROR-zone per-line results.
- Local shader fixtures: **5 files / 855 lines / 50 functions PASS**.
- GLSL sweep --check-query: **4258 nonblank probes, HIGH=0**;
  LOW=2 on a one-line function and its if (cloud-layer:160, cloud-near:161), INFO SIBLING=6.
  Fixture folder sweep (including README): HIGH=0, LOW=0.
- D7 absent module / real upstream int / mocked unsupported platform: all PASS,
  separate -S subprocesses + T: dirs. Other language messages unchanged vs snapshot.
- check **150/0**, cardstamp **160/0**, restamp **21/0**, golden **16/16**,
  cpp **150/0**, name_resolver **55/0**, views **57/0**; no grammar skips.
- Full sweep **151 files / 52709 probes**: known old cp1252 **CRASH=71**, LOW=5;
  CONTAIN=RANGE=OPEN=QUERY=0. Exit 1 is expected legacy residual, not hidden as green.
- Old/new CLI **222 files / 666 comparisons / 0 differences**: 118 old test fixtures,
  104 files in configured STAMP_DIRS C/C++/CUDA zone Y:/SRC/llama.cpp_mix.
  __dev/review/glsl_other_languages_comparison.json.
- Source syntax and git diff --check passed; new GLSL golden files inspected.

Test commands (no need to repeat everything unless changes require it):

```powershell
& $py -B test/check.py --fails
& $py -B test/test_glsl.py
& $py -B test/test_glsl_env.py --upstream T:/AgentsWork/glsl-wheel-plan10/upstream-plan11 --before T:/AgentsWork/glsl-wheel-plan10/tools-before-plan11
& $py -B test/test_glsl.py --shaders Y:/AgentsWork/PlanetWeather/viewer_layered/export/shaders --out __dev/review/glsl_integration_results.json
& $py -B test/sweep_invariants.py Y:/AgentsWork/PlanetWeather/viewer_layered/export/shaders --quiet --check-query
```

Raw AST ranges are not public query ranges. Baseline text is a 220-char prefix.
Public --name --force equals --line signature --query --force (comment preambles,
legitimate one-line filler), not necessarily raw function_definition. Without force,
normal auto-escalation remains. Two one-line LOW-level ties are documented, not HIGH.

## Pending external actions — not performed

Claude reviews/commits Plan11, then normal vendor sync only if authorized.
Read-only vendor --check returned 1 with 12 tracked file differences; source_files
uses git ls-files + working-tree paths, so untracked glsl.py is not yet included.
Normal sync refuses dirty source. No files copied.
Hermes file_ops/read_file__get_codeblock_help.txt needs new extensions/wheel note when
GLSL is actually shipped. Sync does not copy wheels/, so artifact delivery/location
and installation into the owner-selected Python are separate from package sync.
These are recorded limitations of future distribution, not performed production work.
Plan11 remains active until final review; Plan10 is closed by D1.

## T: evidence / build folders

T:/AgentsWork/glsl-wheel-plan10 contains the prior source/build variants, dist wheels,
CLI 0.27.1, isolated runtime25 and acceptance workers, tmp/pip-cache/build-deps.
Main source commit 3a00d49a88cb53eec519b49d8e234e77d916f8ac (Caellian/tree-sitter-glsl).
No grammar/parser changes in capsule1; patch packaging only. Diagnostic wheel copies
remain in dist (deleted only from tools/wheels).
New: upstream-plan11 (real upstream 1.0.0 for D7), tools-before-plan11[.zip] (f88fb17),
compare-plan11/{inputs,result}.json, regression-plan11 logs, accept-installed-plan11.
Historical GLSL_BUILD/probes are evidence; do not rerun unsafe .row diagnostics or
overwrite old reports. No rebuild/download needed for continuation.
