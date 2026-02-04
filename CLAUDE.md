# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Kubernetes controller that enforces pod restart synchronization when pods have dependencies. Restarts are managed at the **deployment** level, not the pod level.

### Core Domain Rules

- Each pod may have **at most one parent** and **zero or more children** (tree structure).
- When a pod restarts, **all its children must be restarted** as well (transitively).
- **Duplicate restarts must be prevented**: if multiple ancestors restart, a descendant should only restart once.
- Init containers already exist externally to enforce child pods waiting for their parents at startup.
- **Kubernetes annotations** on deployments are used to track last triggered restart timestamps.
- The solution will be limited to no more than 10 pods and relationships graph remain simple.

### Implementation

This solution will be developped in Python. Code will be located in the src folder and deployment related files in a 'deploy' folder.

We can identify the following components:

- A kubernetes resource watcher to read various events and notify when an event match the provided filter
- A Restart manager that handle pod restart. Restart loop must be prevented. Deployment annotations must indicate when and why restart is triggered.
- A coordinator to require the restart manager to restart a pod by updating its deployment when resource watcher send a notification.

Code should be organized in order to be able to test most of the code without requiring a specific infrastructure.

Avoid module level variables

### Tests

helper script to setup a local k3s test cluster must be available.

linter should be run to enforce clean code even for a small project.

### Logging

logs will follow  a standard format with an iso8601 timestamp, a logger and a message. logs will be redirected to stderr and to a file for local execution.

console will only display logs with verbosity info or higher and local file will store all logs.

## Development Commands

```bash
make install-dev   # Create venv and install dependencies
make test          # Run tests (pytest -v)
make lint          # Run linter (ruff)
make format        # Auto-format code (ruff format + fix)
```

A `.venv` virtualenv is used. All Makefile targets use it automatically.

## Architecture

- `src/tree.py` — Pure dependency tree logic: builds parent→children map, computes transitive restart sets with deduplication. No K8s dependency.
- `src/logging_config.py` — Logging setup: ISO 8601 formatter, stderr (INFO+), rotating file (DEBUG+).
- `src/watcher.py` — Kubernetes event watch loops for deployments and pods (planned).
- `src/restart_manager.py` — Patches deployment annotations to trigger restarts (planned).
- `src/main.py` — Entry point and coordinator (planned).

Dependencies are declared via annotations: `restart-controller/parent: <parent-deployment-name>` on each child deployment.
