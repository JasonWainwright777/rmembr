#!/usr/bin/env bash
# Example: AI agent workflow — JSON output for programmatic consumption.
# Simulates an agent reviewing a PR that changes terraform files.

set -euo pipefail
CLI="python $(dirname "$0")/../mcp-cli.py"

echo "=== Step 1: Index all repos ==="
$CLI index-all
echo

echo "=== Step 2: Get context bundle as JSON (agent persona, with changed files) ==="
$CLI get-bundle sample-repo-a "Review infrastructure changes" \
  --persona agent \
  --changed-files "infra/modules/network/main.tf,infra/environments/prod/main.tf" \
  --format json
echo

echo "=== Step 3: Search for pipeline configuration context ==="
$CLI search sample-repo-a "CI/CD pipeline templates" --k 5
echo

echo "=== Step 4: List available standards (latest version) ==="
$CLI list-standards --version v4
echo

echo "=== Step 5: Validate memory pack ==="
$CLI validate-pack sample-repo-a
