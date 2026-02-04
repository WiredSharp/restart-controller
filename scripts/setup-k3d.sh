#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
IMAGE_NAME="restart-controller:latest"
CLUSTER_NAME="restart-controller"

echo "==> Checking k3d installation"
if ! command -v k3d &>/dev/null; then
    echo "Installing k3d..."
    curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash
fi

echo "==> Creating k3d cluster"
if k3d cluster list | grep -q "$CLUSTER_NAME"; then
    echo "Cluster '$CLUSTER_NAME' already exists"
else
    k3d cluster create "$CLUSTER_NAME" --no-lb --k3s-arg "--disable=traefik@server:0"
fi

echo "==> Waiting for node to be ready"
kubectl wait --for=condition=Ready node --all --timeout=60s

echo "==> Building controller image"
docker build -t "$IMAGE_NAME" "$PROJECT_DIR"

echo "==> Importing image into k3d cluster"
k3d image import "$IMAGE_NAME" -c "$CLUSTER_NAME"

echo "==> Applying RBAC"
kubectl apply -f "$PROJECT_DIR/deploy/rbac.yaml"

echo "==> Deploying controller"
kubectl apply -f "$PROJECT_DIR/deploy/deployment.yaml"

echo "==> Deploying example chain (db -> api -> frontend)"
kubectl apply -f "$PROJECT_DIR/deploy/examples/chain.yaml"

echo "==> Waiting for all deployments to be available"
kubectl wait deployment --all --for=condition=Available --timeout=120s

echo "==> Setup complete"
kubectl get deployments
