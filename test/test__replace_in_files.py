#!/usr/bin/env python3
"""Tests for replace_in_files.py utility. Generates fixtures, runs tool, verifies results."""

import os
import shutil
import subprocess
import sys


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  # test/ directory
UTILS_DIR = os.path.dirname(SCRIPT_DIR)                  # __HQ/tools/ (one level up from test/)
FIXTURES_DIR = os.path.join(SCRIPT_DIR, "test__replace_in_files", "fixtures")

UTIL_PATH = os.path.join(UTILS_DIR, "replace_in_files.py")


def run_tool(*args, expect_ok=True):
    """Run replace_in_files.py with given args and return (stdout, stderr, code)."""
    cmd = [sys.executable, UTIL_PATH] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if expect_ok and result.returncode != 0:
        print(f"FAIL: {cmd}")
        print(f"stdout:\n{result.stdout}")
        print(f"stderr:\n{result.stderr}")
        raise AssertionError("Tool exited with non-zero code")
    return result.stdout, result.stderr, result.returncode


def setup_fixtures():
    """Create or recreate test fixture files."""
    os.makedirs(FIXTURES_DIR, exist_ok=True)

    # Top-level file: README-style markdown with realistic content
    readme_content = (
        "# Project Documentation — Getting Started Guide\n"
        "\n"
        "This document provides an overview of the project architecture and setup instructions.\n"
        "\n"
        "## Dependencies\n"
        "\n"
        "- Python 3.10+ required for all tooling\n"
        "- Node.js 18+ for frontend components\n"
        "- Docker Desktop installed on your machine\n"
        "\n"
        "## Installation Steps\n"
        "\n"
        "Run the following commands in sequence:\n"
        "\n"
        '```bash\n'
        "git clone https://github.com/example/project.git\n"
        "cd project\n"
        "pip install -r requirements.txt\n"
        "npm install --prefix web/\n"
        "```\n"
        "\n"
        "## Configuration\n"
        "\n"
        'Edit `config.yaml` with your environment variables before first run.\n'
        "See `.env.example` for reference values and descriptions.\n"
        "\n"
        "## Running Tests\n"
        "\n"
        "Execute the test suite from the project root directory:\n"
        "\n"
        '    python -m pytest tests/ -v --tb=short\n'
        "\n"
        "For integration tests only, use the marker flag appropriately.\n"
        "\n"
        "---\n"
        "\n"
        "Last updated: 2024-03-15 by Engineering Team\n"
    )
    with open(os.path.join(FIXTURES_DIR, "README.md"), "w") as f:
        f.write(readme_content)

    # Python module with realistic code structure
    py_content = (
        '"""Configuration loader for application settings and environment variables."""\n'
        "\n"
        "import os\n"
        "from pathlib import Path\n"
        "\n"
        "\n"
        "def load_config(config_path=None):\n"
        '    """Load configuration from YAML file or environment defaults.\n'
        "    \n"
        "    Args:\n"
        "        config_path: Optional path to custom config file\n"
        "        \n"
        "    Returns:\n"
        "        dict with merged configuration values\n"
        '    """\n'
        "    if config_path is None:\n"
        '        config_path = os.environ.get("APP_CONFIG", "config.yaml")\n'
        "    \n"
        "    path = Path(config_path)\n"
        "    if not path.exists():\n"
        "        return get_default_config()\n"
        "    \n"
        '    with open(path, "r") as f:\n'
        "        user_config = f.read() or {}\n"
        "    \n"
        "    defaults = get_default_config()\n"
        "    merged = {**defaults, **user_config}\n"
        "    return merged\n"
        "\n"
        "\n"
        "def get_default_config():\n"
        '    """Return default configuration values for the application."""\n'
        "    return {\n"
        '        "database": {\n'
        '            "host": os.environ.get("DB_HOST", "localhost"),\n'
        '            "port": int(os.environ.get("DB_PORT", 5432)),\n'
        '            "name": os.environ.get("DB_NAME", "app_db")\n'
        "        },\n"
        '        "logging": {\n'
        '            "level": os.environ.get("LOG_LEVEL", "INFO"),\n'
        '            "format": "%(asctime)s [%(levelname)s] %(message)s"\n'
        "        },\n"
        '        "features": {\n'
        '            "enable_cache": True,\n'
        '            "max_connections": 100\n'
        "        }\n"
        "    }\n"
        "\n"
        "\n"
        "def validate_config(config):\n"
        '    """Validate that required configuration keys are present.\n'
        "    \n"
        "    Raises:\n"
        "        ValueError if mandatory settings are missing or invalid\n"
        '    """\n'
        '    required_keys = ["database", "logging"]\n'
        "    for key in required_keys:\n"
        "        if key not in config:\n"
        f'            raise ValueError(f"Missing required config section: {{key}}")\n'
        "\n"
        "\n"
        'if __name__ == "__main__":\n'
        "    cfg = load_config()\n"
        "    validate_config(cfg)\n"
        '    print("Configuration loaded successfully")\n'
    )
    with open(os.path.join(FIXTURES_DIR, "config_loader.py"), "w") as f:
        f.write(py_content)

    # Subdirectory file for --recurse tests (nested structure)
    subdir = os.path.join(FIXTURES_DIR, "src", "services")
    os.makedirs(subdir, exist_ok=True)

    db_content = (
        '"""Database service module — connection pooling and query execution."""\n'
        "\n"
        "import psycopg2\n"
        "from contextlib import contextmanager\n"
        "\n"
        "\n"
        "class DatabaseService:\n"
        '    """Manages database connections and provides query helpers.\n'
        "    \n"
        "    Handles connection pooling automatically for performance optimization.\n"
        '    """\n'
        "    \n"
        "    def __init__(self, config):\n"
        "        self.config = config\n"
        '        self.pool_size = config.get("max_connections", 10)\n'
        "        \n"
        "    @contextmanager\n"
        "    def get_connection(self):\n"
        '        """Context manager for acquiring and releasing database connections."""\n'
        "        conn = None\n"
        "        try:\n"
        "            conn = psycopg2.connect(\n"
        '                host=self.config["host"],\n'
        '                port=self.config["port"],\n'
        '                dbname=self.config["name"]\n'
        "            )\n"
        "            yield conn\n"
        "            conn.commit()\n"
        "        except Exception as e:\n"
        "            if conn:\n"
        "                conn.rollback()\n"
        f'            raise RuntimeError(f"Database operation failed: {{e}}")\n'
        "        finally:\n"
        "            if conn:\n"
        "                conn.close()\n"
        "                \n"
        "    def execute_query(self, query, params=None):\n"
        '        """Execute a SELECT query and return results as list of dicts."""\n'
        "        with self.get_connection() as conn:\n"
        "            cursor = conn.cursor()\n"
        "            cursor.execute(query, params or ())\n"
        "            columns = [desc[0] for desc in cursor.description]\n"
        "            return [dict(zip(columns, row)) for row in cursor.fetchall()]\n"
        "\n"
        "\n"
        "def create_service(config):\n"
        '    """Factory function to instantiate DatabaseService with given config."""\n'
        "    return DatabaseService(config)\n"
    )
    with open(os.path.join(subdir, "database.py"), "w") as f:
        f.write(db_content)

    # Another subdirectory file (deeper nesting)
    deep_dir = os.path.join(FIXTURES_DIR, "src", "services", "internal")
    os.makedirs(deep_dir, exist_ok=True)

    cache_content = (
        '"""In-memory caching layer for frequently accessed data."""\n'
        "\n"
        "import time\n"
        "\n"
        "\n"
        "class CacheService:\n"
        '    """Simple TTL-based cache implementation.\n'
        "    \n"
        "    Stores key-value pairs with optional expiration times.\n"
        "    Automatically removes expired entries on access.\n"
        '    """\n'
        "    \n"
        "    def __init__(self, default_ttl=300):\n"
        "        self.store = {}\n"
        "        self.default_ttl = default_ttl\n"
        "        \n"
        "    def get(self, key):\n"
        '        """Retrieve value from cache if not expired."""\n'
        "        entry = self.store.get(key)\n"
        "        if entry is None:\n"
        "            return None\n"
        "            \n"
        "        timestamp, value, ttl = entry\n"
        "        if time.time() - timestamp > ttl:\n"
        "            del self.store[key]\n"
        "            return None\n"
        "        return value\n"
        "        \n"
        "    def set(self, key, value, ttl=None):\n"
        '        """Store a value in cache with optional TTL override."""\n'
        "        actual_ttl = ttl or self.default_ttl\n"
        "        self.store[key] = (time.time(), value, actual_ttl)\n"
        "        \n"
        "    def delete(self, key):\n"
        '        """Remove an entry from the cache explicitly."""\n'
        "        self.store.pop(key, None)\n"
        "        \n"
        "    def clear_all(self):\n"
        '        """Reset the entire cache — removes all stored entries immediately."""\n'
        "        self.store.clear()\n"
        "\n"
        "\n"
        "# Global singleton instance for application-wide caching\n"
        "cache = CacheService(default_ttl=600)\n"
    )
    with open(os.path.join(deep_dir, "cache.py"), "w") as f:
        f.write(cache_content)

    # Create a .git directory to test skipping behavior
    git_dir = os.path.join(FIXTURES_DIR, ".git")
    os.makedirs(git_dir, exist_ok=True)

    with open(os.path.join(git_dir, "config"), "w") as f:
        f.write("[core]\n\trepositoryformatversion = 0\n")


def teardown_fixtures():
    """Remove test fixture directory."""
    if os.path.exists(FIXTURES_DIR):
        shutil.rmtree(FIXTURES_DIR)


# ============================================================================
# Test cases — help and usage
# ============================================================================

def test_short_help_shows_on_no_args():
    """Running without args shows compact usage (<10 lines)."""
    out, err, code = run_tool()
    assert code == 0
    line_count = len([l for l in out.splitlines() if l.strip()])
    assert line_count < 10, f"Short help has {line_count} non-empty lines (expected <10)"


def test_full_help_shows_on_flag():
    """--help shows detailed documentation (>10 lines)."""
    out, err, code = run_tool("--help")
    assert code == 0
    line_count = len([l for l in out.splitlines() if l.strip()])
    assert line_count > 10, f"Full help has {line_count} non-empty lines (expected >10)"


# ============================================================================
# Test cases — basic replacement functionality
# ============================================================================

def test_simple_replace_dry_run_default():
    """Default mode is dry-run — no files modified."""
    setup_fixtures()

    # Read original content
    with open(os.path.join(FIXTURES_DIR, "README.md")) as f:
        orig = f.read()

    out, err, code = run_tool(
        FIXTURES_DIR, "*.md", "--find", "Python 3.10+", "--with", "Python 3.12+"
    )

    # Check dry-run output mentions DRY-RUN and replacements count
    assert "DRY-RUN" in out.upper() or "dry-run" in out.lower()
    assert "replacement(s)" in out.lower()

    # Verify file NOT modified
    with open(os.path.join(FIXTURES_DIR, "README.md")) as f:
        after = f.read()
    assert orig == after, "Dry-run should not modify files"


def test_simple_replace_with_apply():
    """--apply actually modifies files on disk."""
    setup_fixtures()

    run_tool(
        FIXTURES_DIR, "*.py", "--find", "get_default_config", 
        "--with", "build_default_config", "--apply"
    )

    # Check config_loader.py: function name changed everywhere
    with open(os.path.join(FIXTURES_DIR, "config_loader.py")) as f:
        content = f.read()

    assert "def build_default_config()" in content
    assert "get_default_config()" not in content


def test_recurse_flag():
    """--recurse processes files in subdirectories."""
    setup_fixtures()

    run_tool(
        FIXTURES_DIR, "*.py", "--find", "CacheService", 
        "--with", "TTLCacheService",
        "--apply", "--recurse"
    )

    # cache.py in deep subdir should be modified
    with open(os.path.join(FIXTURES_DIR, "src", "services", "internal", "cache.py")) as f:
        content = f.read()
    assert "TTLCacheService" in content


def test_no_recurse_skips_subdirs():
    """Without --recurse, subdirectory files are NOT processed."""
    setup_fixtures()

    run_tool(
        FIXTURES_DIR, "*.py", "--find", "DatabaseService", 
        "--with", "PostgresService",
        "--apply"  # no --recurse flag
    )

    # database.py in subdir should be unchanged
    with open(os.path.join(FIXTURES_DIR, "src", "services", "database.py")) as f:
        content = f.read()
    assert "DatabaseService" in content


def test_match_guard():
    """--match applies replace only on lines where expression is true."""
    setup_fixtures()

    run_tool(
        FIXTURES_DIR, "*.md",
        "--find", "-", "--with", "*",
        "--match", 'line.startswith("-")',
        "--apply"
    )

    with open(os.path.join(FIXTURES_DIR, "README.md")) as f:
        content = f.read()

    # Lines starting with "-" should now start with "*"
    assert "* Python 3.10+" in content or "* Node.js" in content


# ============================================================================
# Test cases — safety and edge cases
# ============================================================================

def test_wildcard_mask_forces_dry_run():
    """Mask '*' or '*.*' forces dry-run even with --apply."""
    setup_fixtures()

    run_tool(
        FIXTURES_DIR, "*", "--find", "Python 3.10+", 
        "--with", "Python 4.0+", "--apply"
    )

    # README.md should be unchanged (forced dry-run)
    with open(os.path.join(FIXTURES_DIR, "README.md")) as f:
        content = f.read()
    assert "Python 3.10+" in content


def test_dry_run_applies_over_apply():
    """When both --dry-run and --apply are given, dry-run wins."""
    setup_fixtures()

    run_tool(
        FIXTURES_DIR, "*.py", "--find", "load_config", 
        "--with", "parse_config",
        "--apply", "--dry-run"  # both flags present
    )

    with open(os.path.join(FIXTURES_DIR, "config_loader.py")) as f:
        content = f.read()
    assert "def load_config(config_path=None):" in content


def test_skip_git_dir():
    """Files under .git/ directory should be skipped."""
    setup_fixtures()

    # The fixture already has a .git/config file created

    run_tool(
        FIXTURES_DIR, "*", "--find", "repositoryformatversion", 
        "--with", "CHANGED_VERSION",
        "--apply", "--recurse"
    )

    # File in .git should be unchanged
    with open(os.path.join(FIXTURES_DIR, ".git", "config")) as f:
        content = f.read()
    assert "repositoryformatversion" in content


# ============================================================================
# Test cases — argument validation and errors
# ============================================================================

def test_missing_find_flag_error():
    """Missing --find flag produces clear error message."""
    setup_fixtures()

    out, err, code = run_tool(
        FIXTURES_DIR, "*.py", "--with", "replacement", expect_ok=False
    )

    assert code != 0
    combined = (out + err).lower()
    assert "missing" in combined and "find" in combined


def test_missing_with_flag_error():
    """Missing --with flag produces clear error message."""
    setup_fixtures()

    out, err, code = run_tool(
        FIXTURES_DIR, "*.py", "--find", "target", expect_ok=False
    )

    assert code != 0
    combined = (out + err).lower()
    assert "missing" in combined and "with" in combined


def test_multiple_find_flags_error():
    """Multiple --find flags are rejected with clear error."""
    setup_fixtures()

    out, err, code = run_tool(
        FIXTURES_DIR, "*.py", 
        "--find", "first", "--find", "second", 
        "--with", "replacement", expect_ok=False
    )

    assert code != 0
    combined = (out + err).lower()
    assert "multiple" in combined and "one" in combined


def test_unrecognized_argument_error():
    """Unknown flags produce clear error with usage hint."""
    out, err, code = run_tool("--unknown-flag", expect_ok=False)

    assert code != 0
    combined = (out + err).lower()
    # Either argparse reports missing args or unrecognized — either way, shows usage hint
    assert "usage:" in combined and ("error" in combined or "required" in combined)


# ============================================================================
# Test cases — new output format features
# ============================================================================

def test_output_shows_scanning_header_with_full_path():
    """Output begins with 'Scanning <full-path>/<mask>:' header."""
    setup_fixtures()

    out, err, code = run_tool(
        FIXTURES_DIR, "*.py", "--find", "def load_config", "--with", "def parse_config"
    )

    assert code == 0
    # Header should contain the absolute path to fixtures directory
    full_path = os.path.abspath(FIXTURES_DIR)
    assert f"Scanning {full_path}/" in out


def test_output_uses_relative_paths_from_scanning_root():
    """File paths in output are relative to scanning root, not absolute."""
    setup_fixtures()

    # Run with --recurse so we get files from subdirectories
    out, err, code = run_tool(
        FIXTURES_DIR, "*.py", "--find", "def load_config", 
        "--with", "def parse_config", "--recurse"
    )

    assert code == 0

    # Should see relative path like "src/services/database.py" not absolute
    lines = out.splitlines()
    # Skip header line (Scanning ...) and summary line — only check file listing lines
    file_lines = [l for l in lines if ".py:" in l or ".py\n" in l]
    file_lines = [l for l in file_lines if not l.startswith("Scanning")]

    for line in file_lines:
        # Relative paths should NOT start with / or drive letter
        stripped = line.strip().split()[-1]  # last token is the path
        assert not stripped.startswith("/"), f"Expected relative path, got absolute: {stripped}"


def test_verbose_shows_changed_lines_with_line_numbers():
    """--verbose output shows each changed line with 'Line N:' format."""
    setup_fixtures()

    out, err, code = run_tool(
        FIXTURES_DIR, "*.py", "--find", "def load_config", 
        "--with", "def parse_config", "--verbose"
    )

    assert code == 0

    # Verbose output should contain "Line N:" entries for each changed line
    lines = out.splitlines()
    verbose_lines = [l for l in lines if "Line " in l and ":" in l]

    assert len(verbose_lines) > 0, "Expected 'Line N:' format in verbose output"

    # Check format: should be indented with "Line <number>:"
    sample = verbose_lines[0]
    assert "Line " in sample and ": " in sample


def test_verbose_applied_shows_new_content():
    """--verbose with --apply shows the new content after replacement."""
    setup_fixtures()

    out, err, code = run_tool(
        FIXTURES_DIR, "*.py", "--find", "load_config", 
        "--with", "parse_config", "--verbose", "--apply"
    )

    assert code == 0

    # Verbose output should show new content containing the replacement text
    lines = out.splitlines()
    verbose_lines = [l for l in lines if "Line " in l]

    found_new_content = any("parse_config" in line for line in verbose_lines)
    assert found_new_content, "Verbose with --apply should show new content after replacement"


def test_at_alias_resolves_to_project_root():
    """@ as PATH argument resolves to PROJECT_ROOT from CONFIG__TOOLS."""
    # This tests that @ is recognized and doesn't produce a 'no files matched' error
    # when used with appropriate mask

    out, err, code = run_tool(
        "@", "*.py", "--find", "#!/usr/bin/env python3", 
        "--with", "#!/usr/bin/env python3.12"
    )

    # Should succeed (exit 0) and show scanning header with project root path
    assert code == 0

    combined = out + err
    # Either it found files or the PROJECT_ROOT exists — either way @ was resolved
    assert "Scanning" in combined, "@ alias should resolve to a valid directory path"


# ============================================================================
# Main runner
# ============================================================================

def main():
    tests = [
        test_short_help_shows_on_no_args,
        test_full_help_shows_on_flag,
        test_simple_replace_dry_run_default,
        test_simple_replace_with_apply,
        test_recurse_flag,
        test_no_recurse_skips_subdirs,
        test_match_guard,
        test_wildcard_mask_forces_dry_run,
        test_dry_run_applies_over_apply,
        test_skip_git_dir,
        # New tests — argument validation
        test_missing_find_flag_error,
        test_missing_with_flag_error,
        test_multiple_find_flags_error,
        test_unrecognized_argument_error,
        # New tests — output format
        test_output_shows_scanning_header_with_full_path,
        test_output_uses_relative_paths_from_scanning_root,
        test_verbose_shows_changed_lines_with_line_numbers,
        test_verbose_applied_shows_new_content,
        test_at_alias_resolves_to_project_root,
    ]

    passed = 0
    failed = []

    for test in tests:
        name = test.__name__
        try:
            setup_fixtures()
            test()
            passed += 1
        except Exception as e:
            print(f"FAIL: {name} — {e}")
            failed.append((name, str(e)))
        finally:
            teardown_fixtures()

    print(f"\nResults: {passed}/{len(tests)} tests passed")
    if failed:
        for name, err in failed:
            print(f"  - {name}: {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
