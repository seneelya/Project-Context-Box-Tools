#!/bin/bash
set -euo pipefail
export TMPDIR=/work/tmp TEMP=/work/tmp TMP=/work/tmp PIP_CACHE_DIR=/work/pip-cache
export PYTHONDONTWRITEBYTECODE=1 HOME=/work/home XDG_CACHE_HOME=/work/cache
mkdir -p "$TMPDIR" "$HOME" /work/build-deps /work/dist /work/repaired
/opt/python/cp310-cp310/bin/python -m pip install --no-index --find-links /work/downloads --target /work/build-deps build setuptools wheel packaging pyproject-hooks
export PYTHONPATH=/work/build-deps
cd /work/source
/opt/python/cp310-cp310/bin/python -m build --wheel --no-isolation --outdir /work/dist
# auditwheel uses its own installed environment, not our build-deps.
unset PYTHONPATH
auditwheel show /work/dist/*.whl
auditwheel repair --plat manylinux_2_17_x86_64 --wheel-dir /work/repaired /work/dist/*.whl
auditwheel show /work/repaired/*.whl
