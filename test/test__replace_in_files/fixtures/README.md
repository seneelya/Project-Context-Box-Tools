# Project Documentation — Getting Started Guide

This document provides an overview of the project architecture and setup instructions.

## Dependencies

- Python 3.10+ required for all tooling
- Node.js 18+ for frontend components
- Docker Desktop installed on your machine

## Installation Steps

Run the following commands in sequence:

```bash
git clone https://github.com/example/project.git
cd project
pip install -r requirements.txt
npm install --prefix web/
```

## Configuration

Edit `config.yaml` with your environment variables before first run.
See `.env.example` for reference values and descriptions.

## Running Tests

Execute the test suite from the project root directory:

    python -m pytest tests/ -v --tb=short

For integration tests only, use the marker flag appropriately.

---

Last updated: 2024-03-15 by Engineering Team
