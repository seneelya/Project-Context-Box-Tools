"""Run existing, non-destructive review suites and retain their complete output."""
from pathlib import Path
import json
import os
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "validation"
SUITES = [
    ("check", ["test/check.py", "--fails"]),
    ("golden", ["test/golden_check.py"]),
    ("views", ["test/test_views.py"]),
    ("names", ["test/test_name_resolver.py"]),
    ("cpp", ["test/test_cpp.py", "--fails"]),
    ("cards", ["test/test_cardstamp.py"]),
    ("restamp", ["test/run_restamp_fixtures.py"]),
    ("split", ["-m", "pytest", "-q", "-p", "no:cacheprovider", "test/test_split_monster.py"]),
]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    results = []
    for name, args in SUITES:
        start = time.monotonic()
        run = subprocess.run([sys.executable, *args], cwd=ROOT, env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             timeout=600)
        (OUT / f"{name}.log").write_bytes(run.stdout)
        result = dict(name=name, args=args, exit_code=run.returncode,
                      seconds=round(time.monotonic() - start, 2))
        results.append(result)
        print(json.dumps(result), flush=True)
        print(run.stdout.decode("utf-8", errors="replace")[-1200:], flush=True)
        (OUT / "summary.json").write_text(
            json.dumps(dict(python=sys.executable, version=sys.version, results=results),
                       indent=2), encoding="utf-8")
    return int(any(r["exit_code"] for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
