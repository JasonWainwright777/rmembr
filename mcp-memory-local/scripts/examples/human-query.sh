#!/usr/bin/env bash
# Example: Human developer querying for terraform module versioning guidance.
# Returns markdown output suitable for reading.

set -euo pipefail
CLI="python $(dirname "$0")/../mcp-cli.py"

echo "=== Step 1: Check system health ==="
$CLI health
echo

echo "=== Step 2: Index the sample repo (idempotent) ==="
$CLI index-repo sample-repo-a
echo

echo "=== Step 3: Get context bundle as markdown ==="
$CLI get-bundle sample-repo-a "How do we version terraform modules?" \
  --persona human \
  --format markdown
echo

echo "=== Step 4: Search for related content ==="
$CLI search sample-repo-a "module pinning rules" --k 3
echo

echo "=== Step 5: Get a specific standard ==="
$CLI get-standard enterprise/terraform/module-versioning --format markdown
