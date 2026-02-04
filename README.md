# Kubernetes Pod Restart Controller

A Kubernetes controller that enforces pod restart synchronization when pods have dependencies between each other.

## Overview

When a parent deployment's pod restarts (due to crash, manual deletion, or rollout), all its child deployments are automatically restarted. This ensures dependent services reconnect to fresh parent instances.

### Features

- **Cascading restarts**: When a pod restarts, all descendant deployments restart transitively
- **Deduplication**: If multiple ancestors restart, a descendant only restarts once
- **Cooldown protection**: 60-second cooldown per deployment prevents restart loops
- **Simple configuration**: Dependencies declared via annotations

## Quick Start

### Prerequisites

- Docker
- k3d (or any Kubernetes cluster)
- kubectl

### Setup

```bash
# Create k3d cluster and deploy controller
./scripts/setup-k3d.sh

# View example deployments (db -> api -> frontend)
kubectl get deployments
```

### Define Dependencies

Add the `restart-controller/parent` annotation to child deployments:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  annotations:
    restart-controller/parent: db  # api depends on db
spec:
  # ...
```

### Test Cascading Restart

```bash
# Delete db pod - api and frontend will automatically restart
kubectl delete pod -l app=db

# Watch the cascade
kubectl get pods -w
```

### Cleanup

```bash
./scripts/cleanup-k3d.sh
```

## Development

```bash
make install-dev   # Create venv and install dependencies
make test          # Run tests
make lint          # Run linter
make format        # Auto-format code
```

## Architecture

- **PodWatcher**: Monitors pod deletions and container restarts, resolves owning deployment
- **RestartManager**: Patches deployment annotations to trigger rollouts, enforces 60s cooldown
- **Controller**: Builds dependency tree from annotations, computes restart sets, coordinates restarts
- **DependencyTree**: Pure logic for parent-child relationships and transitive descendant computation

## Annotations

| Annotation | Description |
|------------|-------------|
| `restart-controller/parent` | Name of parent deployment (on child deployment metadata) |
| `restart-controller/last-restart` | ISO timestamp of last controller-triggered restart (on pod template) |
| `restart-controller/restart-reason` | Human-readable reason for restart (on pod template) |
