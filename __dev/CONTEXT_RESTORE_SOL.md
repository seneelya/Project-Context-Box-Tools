# CONTEXT_RESTORE_SOL — Plan12 and Plan13 complete, awaiting Claude review

Updated2026-11-01. Repo **T:/AgentsWork/ProjectStarter/__HQ/tools**, its own Git.
User explicitly authorized: **do Plan12, then Plan13**. Worked in that order.
HEAD **c6293db**; underlying GLSL0.10.0 commit1976d7b (user cleaned/recommitted
Plan11). **Do not restore deleted private fixtures/JSON!** No commit/push/deploy
made during Plan12/13; all working changes remain for Claude review/commit.

## Read now

1. __dev/review/GLSL_LINUX.md — Plan12 completed, provenance/commands/test evidence.
2. __dev/review/GLSL_VULKAN.md — Plan13 completed masks and full corpus metrics, K1 CLOSED.
3. __dev/plans/Plan13__KICKBACK.md — **CLOSED, owner chose option 1**.
4. __dev/plans/Plan12__glsl-wheel-linux.md and Plan13__glsl-vulkan-extensions.md.
5. Tail __dev/TRACKER.md, DECISIONS, CONTEXT_RESTORE_TOOLS and reader/CONTRACT.md.
Read source through get_codeblock --outline then selected --line/--name, not whole.
No per-source map cards in this tools workshop. No subagents requested.

## Accepted scope — K1 CLOSED

Owner explicitly chose **option 1**: accept Plan13 with **no NEW #6 mismatches**,
compare complete before/after lists and retain the five original cases in the report.
Lists are exactly identical; the accepted criterion is met. #7/query/HIGH also pass.
General blank-preamble addressing is **REQ-017**, a separate task after Plan13:
__dev/Requests/REQ-017_blank-line-in-comment-preamble-addresses-file.md.
**Do not change that general mechanism as part of Plan13.** No pending answer or
acceptance decision remains. Reports, Plan13 criteria, KICKBACK, tracker and decisions
have been updated; code was not changed in response to this decision.

Five identical cases: flash_attn_dequant.glsl:14, flash_attn_mmq_funcs.glsl:4,
mul_mat_vec_iq4_xs.comp:13, mul_mmq_cm1_funcs.glsl:510, soft_max_back.comp:12.
Complete map/address ranges in report; JSON lists compare exactly equal.

## Environment — mandatory

All new temp/cache/build data on **T:**. No new temporary C: usage. Docker image
storage itself is explicitly allowed by Plan12; bind mounts/build/venv/cache on T:.
Windows reference **T:/AgentsWork/venv/Scripts/python.exe**,3.12.10, tree-sitter0.26.0,
glsl-spec1.0.0+capsule1 — unchanged, no pip install/update there.
Do not touch Hermes Python/Y:/Hermess/gateway/services. Original shaders read-only.
No external shader copies, excerpts or JSON/log text inside the public tools repo;
only synthetic fixtures. Store raw data under T:/AgentsWork/glsl-wheel-plan10.

Every Windows tool process:

```powershell
Set-Location 'T:/AgentsWork/ProjectStarter/__HQ/tools'
$py='T:/AgentsWork/venv/Scripts/python.exe'
$env:TEMP='T:/AgentsWork/glsl-wheel-plan10/tmp'
$env:TMP=$env:TEMP
$env:PIP_CACHE_DIR='T:/AgentsWork/glsl-wheel-plan10/pip-cache'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
Remove-Item Env:PYTHONPATH,Env:PYTHONHOME,Env:GLSL_PROBE_RUNTIME,Env:PYTHONPYCACHEPREFIX -ErrorAction SilentlyContinue
```

Scoped exec require_escalated works; normal sandbox failed startup earlier. No need
to request repeat permission for already authorized build/test actions on T:.

## Plan12 complete

Wheel in tools/wheels:
tree_sitter_glsl_spec-1.0.0+capsule1-cp310-abi3-manylinux1_x86_64.manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_5_x86_64.whl
SHA25655e402505beb13b1f9e91af4d83cc3540d0e71b677d4bc02ca227b57b199cc2b.
Binding.so SHA256f07cdb7b394461eda738422b9ddb9ef50a8caa0e19012da49bba41255fca0ebc.
Source3a00d49a88cb53eec519b49d8e234e77d916f8ac + unchanged capsule1.patch;
parser.c/grammar.js exact Windows hashes. Source binding only CRLF differs after
Windows git apply; LF-normalized equals Windows binding, documented in manifest.

Official manylinux2014 image digest dc58399aca4cfb0de257f92e2de71b4f8421e60cce8542fcd5e28df0c0760942,
1,704,774,662bytes. build-linux.sh in wheels and plan12/. Offline build dependencies
in plan12/downloads; auditwheel: GLIBC_2.2.5, no external shared libraries, requested
manylinux_2_17/manylinux2014 tags retained plus older-compatible tags.

WSL Ubuntu Python3.12.3, platform **linux-x86_64**. Separate venv:
/mnt/t/AgentsWork/glsl-wheel-plan10/plan12/venv/bin/python.
Ubuntu lacked ensurepip; WSL DNS cannot reach pypi.org. No apt/system changes:
get-pip and Linux dependency wheels downloaded via Windows to T:, installed offline
into this venv. Runtime0.26.0, cpp0.23.4, exact capsule1 wheel.

Strict WSL acceptance **480/480** =22×20 full +20 minimal +20 CPP, paths/versions/
binary hashes/capsule/baseline enforced. test_glsl fixture5/178/21 and real22/4464/348
PASS. Cross Windows/Linux outline and name output equal after mount-prefix/CRLF
normalization. Real WSL D7 and Windows D7 **6PASS**. Point.row Linux delta[0,-1]
confirms runtime bug; index[+1,0]. Never use Point.row/column outside historical probes.

Production Plan12 change only Linux artifacts entry. Tests choose native artifact,
check Windows+Linux hints, unsupported aarch64, vendored-no-wheel. Runner generalized
OS roots/.so/platlib; default output moved OUTSIDE repo. Docs/manifest updated.
Windows wheel6c18b83d… and installed pyd53282c34… exact hashes confirmed unchanged.

Plan12 regression: check150/card160/restamp21/golden16/cpp150/names55/views57 all0fail;
GLSL fixturesPASS/env6PASS. Full sweep152files/52083probes retains known cp1252
CRASH71/LOW5, other HIGH0. Logs plan12/regression; Linux evidence plan12/accept-linux.*,
accept-workers, integration-linux.json, cross-output. No need rebuild/retest unchanged work.

## Plan13 implemented

get_codeblock/glsl_source.py masks [[attributes]] and parameter lists of ONLY the
profile data types coopmat5,tensorLayoutNV1–2,tensorViewNV3–7. LangSpec.preprocess;
no grammar rebuild, no GLSL branches in engines, no shared handlers edits.
Protected comments/strings (including malformed endings/continued //), byte lengths
and exact CR/LF positions preserved. Conservative argument arity/context/balancing;
unknown/ambiguous constructs stay raw. Original query/API bytes retained. Outline
labels may omit type parameters. No macro/include expansion, all #if branches kept.

185 top-level Vulkan shaders:155.comp+30.glsl. Exact stats before/attrs/final:
error files118/16/13; ERROR+MISSING1164/481/124; totalnodes336049/331480/329556.
Root direct functions368 throughout; all raw functions634 throughout (#if branches).
All676 attrs (668unroll+8dont_unroll) and148 type lists (134+11+3) masked;
all errors on these supported constructs gone,124 remaining are reported honestly.
Report has mutually exclusive first-error-line category table and residual13files.

Full exact185-file verification: **25036 physical lines**,20968 nonblank sweep probes,
HIGH0/LOW0, SIBLING210before/219after. Every line including blanks contains/query exact.
Additional #6 test recorded the five identical existing mismatches (not swept away).
Before folder sweep also ran193files including8ancillary; do not confuse with185.

PlanetWeather V4:22files/4464lines/348functions PASS vs external baseline; all88
full CLI outputs before/after byte-identical; preprocess(source)==source on22/22.
No personal shader text in repo. Baseline is external review-archive/*.json.

Synthetic new fixture test/glslSRC/vulkan-extensions.comp26lines. Expected ladders
at17,21,19;19 is honest merged adjacent-for filler16–22. test_glsl now includes.comp
and calls test_glsl_preprocess. **19 adversarial unchanged cases** + positive
CRLF/UTF8/offset/idempotence tests. Windows and WSL fixture **6/204/22 PASS**.

Final Plan13 regression: check153/0,card160/0,restamp21/0,golden16/16,cpp150/0,
names55/0,views57/0,GLSL6/204/22,env6PASS. Full sweep154files/52171probes:
known CRASH71/LOW5, CONTAIN/RANGE/OPEN/QUERY0; exit1 reported honestly. No skips.
Source mask was then hardened only for unterminated protected strings; unit checks,
check153/0 and corpus error metrics rechecked, outputs unchanged. Full logs plan13/regression.

## Next actions

1. Claude reviews/commits completed Plan12+Plan13; no remaining implementation work.
2. REQ-017 is separate; do not start it under Plan13 or reopen the accepted criterion.
3. No push/deploy/Hermes action. Both plans remain active pending review/commit;
   do not stage/commit on your own.

Raw evidence and scripts: T:/AgentsWork/glsl-wheel-plan10/plan13/{before,attributes,types}.json,
check-before.json/check-after.json (identical map_mismatches), check-corpus.py,
probe.py, planet-output.py, planet-before/after (private text), planet-integration.json,
regression/. Windows build root/source/dist/runtime25 and historical review-archive remain.
