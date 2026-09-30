"""Per-file scan cache — derived data of the tools, kept next to them (Vision10 §5, Plan09 step 1).

Where:  <tools>/_cache/<root name>-<short hash of the root path>/<kind>.json
        (TOOLS_CACHE_DIR overrides <tools>/_cache; TOOLS_NO_CACHE=1 turns the cache off).
What:   {rel path: [fingerprint, data]} + a header (producer version, config fingerprint).
Fresh:  fingerprint = git blob id for a tracked, clean file (`git ls-files -s`, one call for the
        whole root); a file git reports as changed/untracked, or any file without git ->
        mtime+size. Same fingerprint -> the stored data is valid; otherwise the caller rescans
        ONLY that file and puts the new result.
Reset:  another producer version (hash of the producer's source file) or another config ->
        the whole cache is dropped. Files not touched during a run (deleted) are dropped on save.

The cache is never a source of truth: delete it and the tool silently rebuilds it. Language-
neutral: the producer decides what `data` is (must be JSON-serialisable).
"""
import hashlib
import json
import os
import subprocess
from typing import Dict, Optional

_TOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def cache_dir_for(project_root: str) -> str:
    root = os.path.abspath(project_root)
    base = os.environ.get("TOOLS_CACHE_DIR") or os.path.join(_TOOLS_DIR, "_cache")
    h = hashlib.sha1(os.path.normcase(root).encode("utf-8")).hexdigest()[:8]
    name = os.path.basename(root.rstrip("\\/")) or "root"
    return os.path.join(base, f"{name}-{h}")


def source_version(path: str) -> str:
    """Producer version = hash of its source file: any code change invalidates the cache."""
    try:
        with open(path, "rb") as fh:
            return hashlib.sha1(fh.read()).hexdigest()[:12]
    except OSError:
        return "?"


def _git(root: str, *args: str) -> Optional[bytes]:
    try:
        r = subprocess.run(["git", "-C", root, *args], capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def git_fingerprints(project_root: str) -> Dict[str, str]:
    """{normcased abs path: blob id} for tracked files under the root that git sees as clean.
    Empty without git — every file then falls back to mtime+size."""
    root = os.path.abspath(project_root)
    out = _git(root, "ls-files", "-s", "-z")
    if out is None:
        return {}
    fps: Dict[str, str] = {}
    for rec in out.decode("utf-8", "replace").split("\0"):
        if not rec or "\t" not in rec:
            continue
        meta, rel = rec.split("\t", 1)
        parts = meta.split()
        if len(parts) >= 2:
            fps[os.path.normcase(os.path.join(root, rel))] = parts[1]
    # changed / untracked files: their blob id is stale -> stat fallback
    prefix = (_git(root, "rev-parse", "--show-prefix") or b"").decode("utf-8", "replace").strip()
    top = root
    for _ in [p for p in prefix.replace("\\", "/").split("/") if p]:
        top = os.path.dirname(top)
    st = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=no", ".")
    if st:
        recs = st.decode("utf-8", "replace").split("\0")
        i = 0
        while i < len(recs):
            rec = recs[i]
            i += 1
            if len(rec) < 4:
                continue
            fps.pop(os.path.normcase(os.path.join(top, rec[3:])), None)
            if rec[0] in "RC":
                i += 1   # rename/copy: the next record is the old path
    return fps


class ScanCache:
    def __init__(self, project_root: str, kind: str, version: str, config=None):
        self.root = os.path.abspath(project_root)
        self.enabled = os.environ.get("TOOLS_NO_CACHE", "") not in ("1", "true", "yes")
        self.path = os.path.join(cache_dir_for(self.root), f"{kind}.json")
        self.version = version
        self.config = json.dumps(config, sort_keys=True, default=str)
        self.entries: Dict[str, list] = {}
        self.touched: Dict[str, list] = {}
        self.hits = self.misses = 0
        self._fps: Optional[Dict[str, str]] = None
        self._dirty = False
        if self.enabled:
            self._load()

    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as fh:
                doc = json.load(fh)
        except (OSError, ValueError):
            return
        if doc.get("version") == self.version and doc.get("config") == self.config:
            self.entries = doc.get("entries") or {}
        else:
            self._dirty = True   # stale producer/config -> rewrite from scratch

    def _rel(self, abs_path: str) -> str:
        return os.path.relpath(abs_path, self.root).replace(os.sep, "/")

    def fingerprint(self, abs_path: str) -> Optional[str]:
        if self._fps is None:
            self._fps = git_fingerprints(self.root) if self.enabled else {}
        fp = self._fps.get(os.path.normcase(os.path.abspath(abs_path)))
        if fp:
            return fp
        try:
            s = os.stat(abs_path)
        except OSError:
            return None
        return f"m{s.st_mtime_ns}:{s.st_size}"

    def get(self, abs_path: str):
        """Stored data if the file's fingerprint still matches, else None (caller rescans)."""
        if not self.enabled:
            return None
        rel = self._rel(abs_path)
        e = self.entries.get(rel)
        if e is not None and e[0] == self.fingerprint(abs_path):
            self.touched[rel] = e
            self.hits += 1
            return e[1]
        self.misses += 1
        return None

    def put(self, abs_path: str, data):
        if not self.enabled:
            return
        fp = self.fingerprint(abs_path)
        if fp is None:
            return
        rel = self._rel(abs_path)
        self.touched[rel] = [fp, data]
        self._dirty = True

    def save(self):
        """Write touched entries only (untouched = deleted/out of scope -> dropped)."""
        if not self.enabled:
            return
        if not self._dirty and set(self.touched) == set(self.entries):
            return
        doc = {"version": self.version, "config": self.config, "root": self.root,
               "entries": self.touched}
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + f".{os.getpid()}.tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(doc, fh, separators=(",", ":"))
            os.replace(tmp, self.path)
            self.entries = dict(self.touched)
            self._dirty = False
        except OSError:
            pass   # read-only tools dir etc.: the cache is an optimisation, never an error
