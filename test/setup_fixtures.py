"""Fixture generator for replace_in_files tests."""

import os


# Test fixtures directory path (same as original test file)
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "test__replace_in_files", "fixtures")


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
    import shutil
    if os.path.exists(FIXTURES_DIR):
        shutil.rmtree(FIXTURES_DIR)
