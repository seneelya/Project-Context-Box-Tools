# CONTEXT_RESTORE_SOL — REQ-017, get_codeblock 0.10.1

Updated 2026-11-01. Independent repo: T:/AgentsWork/ProjectStarter/__HQ/tools.
Base HEAD **446411f** includes the owner's committed Plan12/13. Current task is
REQ-017, explicitly assigned after Plan13. Implementation and all-line old/new
comparison and final enhanced sweep are complete. Ready for Claude review/commit.
No commit/push/deploy/Hermes sync.

## Read first

1. __dev/review/REQ017_PREAMBLE.md — implementation, boundaries, tests and evidence.
2. __dev/Requests/REQ-017_blank-line-in-comment-preamble-addresses-file.md.
3. Tail __dev/TRACKER.md, DECISIONS.md and get_codeblock/reader/CONTRACT.md.
4. __dev/CONTEXT_RESTORE_TOOLS.md — architecture and traps.

Read source through get_codeblock --outline, then --name/--line --query, never whole
large source files. Tools workshop has no per-source cards. No subagents requested.

## Implementation

Brace addressing and blank focus use classify.blank_preamble_at: actual unfocused
map is authoritative, including leaf definitions. Preserve real ancestors; reject
false glue from the preceding statement's inline comment. Nonblank routes unchanged.
Python had the same bug: collect_preamble bounds now govern blanks before named
def/class/async-def, including decorator stacks; multiline strings stay protected.
No language branches in the shared engine, new grammar or dependency.

New synthetic test/Edge/preamble_gap.{cpp,ts,cs,glsl,py}, test/test_preamble.py,
15 manual ladder expectations, check.py integration. Sweep checks mapped blank
preambles as PREAMBLE HIGH. Sweep uses shared physical_lines.split_lines: lone CR
and Unicode separators are not line boundaries. Invalid-UTF8 diagnostic policy retained.
Version bumped once to 0.10.1.

## Evidence complete

- check169/0, cardstamp160/0, restamp21/0, golden16/16, cpp150/0, names55/0,
  views57/0, GLSL6 files/204 lines/22 functions +19 masks, env6PASS, preamble PASS.
  Logs: T:/AgentsWork/glsl-wheel-plan10/req017/regression-accepted/summary.json.
- Before archive446411f and comparison driver outside repo: req017/before/,
  compare.py, inputs.json, comparison-before.json, comparison-after.json.
  253 candidates:250 decodable files/185720 rows,3 identical invalid-UTF8 refusals.
  All500 full outline/dot outputs equal,185259 unchanged line outputs. Only461 blank
  rows changed across73 files:459 actual mapped preambles +2 false-owner exclusions
  before first actual comment. No changed nonblank output or source bytes.
- Vulkan185 files/25036 rows: original five Plan13 #6 cases now0. Strengthened sweep
  20973 probes:HIGH0/LOW0/SIBLING219. Exact query/map containment all rows PASS.
  Evidence: T:/AgentsWork/glsl-wheel-plan10/plan13/check-req017-final.json.
- PREAMBLE guard proven against archived old engine:3 synthetic failures caught.

## Final full sweep complete

--quiet --check-query:160 files/52603 probes,CONTAIN0/RANGE0/OPEN0/PREAMBLE0,
CRASH71,QUERY23,LOW5,SIBLING431,exit1. All QUERY23 are UnicodeDecodeError on the
old cp1252 README.md fixture; archived446411f reproduces the same23 QUERY there.
No new HIGH. Historical CRASH71/LOW5 remain. Evidence under req017/:
sweep-final-summary.json and query-diagnostics.json. No full sweep rerun needed.
Earlier regression-final sweep logs predate the final physical-line oracle and
are not the accepted final sweep. Do not reuse their old QUERY false positives.

Report/request/tracker/shared context finalized. Keep request filename until review.
No outstanding scope/approval question; no remaining implementation step.

## Environment and boundaries

Reference Windows Python T:/AgentsWork/venv/Scripts/python.exe,3.12.10,
tree-sitter0.26.0, glsl-spec1.0.0+capsule1. No installation/update needed.
Plan12 Linux wheel/WSL provenance: __dev/review/GLSL_LINUX.md; Plan13 masks and
accepted historical K1: __dev/review/GLSL_VULKAN.md. Do not reopen them.
Original shaders and Y:/SRC/llama.cpp_mix READ ONLY. No private sources/excerpts,
raw query output or JSON inside tools repo: evidence exclusively outside it on T:.
Never use C: for temp/cache/build data. No Hermes Python/gateway/service changes.

Each Windows shell:

```powershell
Set-Location 'T:/AgentsWork/ProjectStarter/__HQ/tools'
$py='T:/AgentsWork/venv/Scripts/python.exe'
$env:TEMP='T:/AgentsWork/glsl-wheel-plan10/tmp'
$env:TMP=$env:TEMP
$env:PIP_CACHE_DIR='T:/AgentsWork/glsl-wheel-plan10/pip-cache'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
```

Scoped require_escalated exec works (normal sandbox startup failed previously).
No new permission question needed for already authorized work on T:.
