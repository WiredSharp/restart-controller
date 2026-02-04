#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="restart-controller"

echo "==> Deleting k3d cluster '$CLUSTER_NAME'"
if k3d cluster list | grep -q "$CLUSTER_NAME"; then
    k3d cluster delete "$CLUSTER_NAME"
    echo "==> Cluster deleted"
else
    echo "==> Cluster '$CLUSTER_NAME' does not exist"
fi
