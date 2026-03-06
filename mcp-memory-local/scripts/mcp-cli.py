#!/usr/bin/env python3
"""CLI for calling MCP Memory Gateway tools.

Requires: pip install httpx

Usage:
    python scripts/mcp-cli.py health
    python scripts/mcp-cli.py index-repo sample-repo-a
    python scripts/mcp-cli.py index-all
    python scripts/mcp-cli.py search sample-repo-a "terraform modules" --k 5
    python scripts/mcp-cli.py get-bundle sample-repo-a "How do we version terraform modules?"
    python scripts/mcp-cli.py get-bundle sample-repo-a "task" --persona agent --format markdown
    python scripts/mcp-cli.py explain-bundle <bundle-id>
    python scripts/mcp-cli.py list-standards --version v3 --domain enterprise/terraform
    python scripts/mcp-cli.py get-standard enterprise/terraform/module-versioning --version v4
    python scripts/mcp-cli.py validate-pack sample-repo-a
"""

import argparse
import json
import sys
import os

try:
    import httpx
except ImportError:
    print("Error: httpx is required. Install with: pip install httpx", file=sys.stderr)
    sys.exit(1)

GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://localhost:8080")
TIMEOUT = 120.0


def _post(path: str, body: dict) -> dict:
    resp = httpx.post(f"{GATEWAY_URL}{path}", json=body, timeout=TIMEOUT)
    if resp.status_code >= 400:
        print(f"Error {resp.status_code}: {resp.text}", file=sys.stderr)
        sys.exit(1)
    return resp.json()


def _get(path: str) -> dict:
    resp = httpx.get(f"{GATEWAY_URL}{path}", timeout=TIMEOUT)
    return resp.json()


def _print_json(data):
    print(json.dumps(data, indent=2))


def cmd_health(_args):
    _print_json(_get("/health"))


def cmd_index_repo(args):
    _print_json(_post("/proxy/index/index_repo", {"repo": args.repo, "ref": args.ref, "provider": args.provider}))


def cmd_index_all(args):
    _print_json(_post("/proxy/index/index_all", {"ref": args.ref}))


def cmd_search(args):
    _print_json(_post("/proxy/index/search_repo_memory", {
        "repo": args.repo,
        "query": args.query,
        "k": args.k,
        "ref": args.ref,
        "namespace": args.namespace,
    }))


def cmd_get_bundle(args):
    body = {
        "repo": args.repo,
        "task": args.task,
        "persona": args.persona,
        "k": args.k,
        "ref": args.ref,
        "namespace": args.namespace,
        "standards_version": args.standards_version,
    }
    if args.changed_files:
        body["changed_files"] = args.changed_files.split(",")

    data = _post("/tools/get_context_bundle", body)

    if args.format == "markdown":
        print(data.get("markdown", ""))
    else:
        _print_json(data)


def cmd_explain_bundle(args):
    _print_json(_post("/tools/explain_context_bundle", {"bundle_id": args.bundle_id}))


def cmd_list_standards(args):
    body = {"version": args.version}
    if args.domain:
        body["domain"] = args.domain
    _print_json(_post("/proxy/standards/list_standards", body))


def cmd_get_standard(args):
    data = _post("/proxy/standards/get_standard", {"id": args.standard_id, "version": args.version})
    if args.format == "markdown":
        print(data.get("content", ""))
    else:
        _print_json(data)


def cmd_validate_pack(args):
    _print_json(_post("/tools/validate_pack", {"repo": args.repo, "ref": args.ref}))


def main():
    parser = argparse.ArgumentParser(
        description="MCP Memory CLI — interact with the Gateway, Index, and Standards services",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("health", help="Check gateway and dependency health")

    p = sub.add_parser("index-repo", help="Index a single repo's memory pack")
    p.add_argument("repo", help="Repo name (e.g., sample-repo-a)")
    p.add_argument("--ref", default="local")
    p.add_argument("--provider", default="filesystem", help="Provider name (filesystem or github)")

    p = sub.add_parser("index-all", help="Index all repos under REPOS_ROOT")
    p.add_argument("--ref", default="local")

    p = sub.add_parser("search", help="Semantic search in a repo's memory")
    p.add_argument("repo")
    p.add_argument("query")
    p.add_argument("--k", type=int, default=8)
    p.add_argument("--ref", default="local")
    p.add_argument("--namespace", default="default")

    p = sub.add_parser("get-bundle", help="Get a context bundle from the gateway")
    p.add_argument("repo")
    p.add_argument("task", help="Task description or question")
    p.add_argument("--persona", default="human", choices=["human", "agent", "external"])
    p.add_argument("--k", type=int, default=12)
    p.add_argument("--ref", default="local")
    p.add_argument("--namespace", default="default")
    p.add_argument("--standards-version", default="local")
    p.add_argument("--changed-files", default=None, help="Comma-separated changed file paths")
    p.add_argument("--format", default="json", choices=["json", "markdown"])

    p = sub.add_parser("explain-bundle", help="Explain a previously generated bundle")
    p.add_argument("bundle_id")

    p = sub.add_parser("list-standards", help="List available enterprise standards")
    p.add_argument("--version", default="local")
    p.add_argument("--domain", default=None, help="Filter by domain prefix")

    p = sub.add_parser("get-standard", help="Get a specific standard's content")
    p.add_argument("standard_id", help="Standard ID (e.g., enterprise/terraform/module-versioning)")
    p.add_argument("--version", default="local")
    p.add_argument("--format", default="json", choices=["json", "markdown"])

    p = sub.add_parser("validate-pack", help="Validate a repo's memory pack")
    p.add_argument("repo")
    p.add_argument("--ref", default="local")

    args = parser.parse_args()

    commands = {
        "health": cmd_health,
        "index-repo": cmd_index_repo,
        "index-all": cmd_index_all,
        "search": cmd_search,
        "get-bundle": cmd_get_bundle,
        "explain-bundle": cmd_explain_bundle,
        "list-standards": cmd_list_standards,
        "get-standard": cmd_get_standard,
        "validate-pack": cmd_validate_pack,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
