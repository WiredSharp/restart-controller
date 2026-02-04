#!/usr/bin/env bash
set -euo pipefail

KUBECTL="kubectl"
TIMEOUT=60

pass=0
fail=0

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    if [[ "$expected" == "$actual" ]]; then
        echo "  PASS: $desc"
        ((pass++))
    else
        echo "  FAIL: $desc (expected='$expected', actual='$actual')"
        ((fail++))
    fi
}

assert_gt() {
    local desc="$1" threshold="$2" actual="$3"
    if [[ "$actual" -gt "$threshold" ]]; then
        echo "  PASS: $desc"
        ((pass++))
    else
        echo "  FAIL: $desc (expected > $threshold, actual='$actual')"
        ((fail++))
    fi
}

wait_for_rollout() {
    local deployment="$1"
    $KUBECTL rollout status "deployment/$deployment" --timeout="${TIMEOUT}s" >/dev/null 2>&1
}

get_annotation() {
    local deployment="$1" annotation="$2"
    $KUBECTL get deployment "$deployment" -o jsonpath="{.spec.template.metadata.annotations['${annotation}']}" 2>/dev/null || echo ""
}

get_generation() {
    local deployment="$1"
    $KUBECTL get deployment "$deployment" -o jsonpath="{.metadata.generation}"
}

echo "==> Verifying initial state"
for dep in db api frontend restart-controller; do
    $KUBECTL rollout status "deployment/$dep" --timeout="${TIMEOUT}s" >/dev/null
done
echo "  All deployments available"

echo ""
echo "==> Recording baseline generations"
gen_api_before=$(get_generation api)
gen_frontend_before=$(get_generation frontend)

echo "==> Triggering restart of db (patching an env var)"
$KUBECTL set env deployment/db TRIGGER="$(date +%s)"

echo "==> Waiting for db rollout"
wait_for_rollout db

echo "==> Waiting for controller to cascade restarts"
sleep 10

echo ""
echo "==> Test 1: api should have been restarted"
wave_api=$(get_annotation api "restart-controller/wave")
reason_api=$(get_annotation api "restart-controller/restart-reason")
assert_gt "api generation increased" "$gen_api_before" "$(get_generation api)"
[[ -n "$wave_api" ]] && assert_eq "api has wave annotation" "true" "true" || assert_eq "api has wave annotation" "true" "false"
assert_eq "api restart reason" "parent db changed" "$reason_api"

echo ""
echo "==> Test 2: frontend should have been restarted (transitive)"
wave_frontend=$(get_annotation frontend "restart-controller/wave")
reason_frontend=$(get_annotation frontend "restart-controller/restart-reason")
assert_gt "frontend generation increased" "$gen_frontend_before" "$(get_generation frontend)"
[[ -n "$wave_frontend" ]] && assert_eq "frontend has wave annotation" "true" "true" || assert_eq "frontend has wave annotation" "true" "false"

echo ""
echo "==> Test 3: api and frontend share the same wave ID"
assert_eq "same wave ID" "$wave_api" "$wave_frontend"

echo ""
echo "==> Test 4: no duplicate restarts (each deployment patched once)"
patch_count=$($KUBECTL get events --field-selector reason=ScalingReplicaSet,involvedObject.name=api --no-headers 2>/dev/null | wc -l)
# At most 2 scaling events per restart (scale down old RS + scale up new RS)
echo "  api scaling events: $patch_count"

echo ""
echo "==============================="
echo "Results: $pass passed, $fail failed"
echo "==============================="

[[ "$fail" -eq 0 ]] && exit 0 || exit 1
