#!/usr/bin/env bash
# Example: External persona — classification filtering demo.
# Shows that external persona only sees public chunks (no internal/confidential).

set -euo pipefail
CLI="python $(dirname "$0")/../mcp-cli.py"

echo "=== External persona (only public content) ==="
$CLI get-bundle sample-repo-a "What does this repo do?" \
  --persona external \
  --format json
echo

echo "=== Human persona (public + internal content) ==="
$CLI get-bundle sample-repo-a "What does this repo do?" \
  --persona human \
  --format json
