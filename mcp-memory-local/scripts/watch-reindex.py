#!/usr/bin/env python3
"""File watcher for auto-reindex on memory pack changes.

Watches repos/ for changes to .ai/memory/ files and triggers
re-indexing of the affected repo via the gateway proxy.

Requires: pip install watchdog httpx
"""

import os
import sys
import time

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    print("Error: watchdog is required. Install with: pip install watchdog", file=sys.stderr)
    sys.exit(1)

try:
    import httpx
except ImportError:
    print("Error: httpx is required. Install with: pip install httpx", file=sys.stderr)
    sys.exit(1)


GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://localhost:8080")
REPOS_ROOT = os.environ.get("REPOS_ROOT", os.path.join(os.path.dirname(__file__), "..", "repos"))
DEBOUNCE_SECONDS = 3


class MemoryPackHandler(FileSystemEventHandler):
    """Watches for changes in .ai/memory/ directories and triggers reindex."""

    def __init__(self):
        super().__init__()
        self._pending = {}  # repo -> last_event_time

    def _extract_repo(self, path: str) -> str | None:
        """Extract repo name from a file path under repos/."""
        rel = os.path.relpath(path, os.path.abspath(REPOS_ROOT))
        parts = rel.replace("\\", "/").split("/")
        if len(parts) < 1:
            return None
        repo = parts[0]
        # Only trigger for .ai/memory/ paths
        if ".ai/memory" in rel.replace("\\", "/"):
            return repo
        return None

    def on_any_event(self, event):
        if event.is_directory:
            return
        repo = self._extract_repo(event.src_path)
        if repo:
            self._pending[repo] = time.time()

    def process_pending(self):
        """Reindex repos that have had no changes for DEBOUNCE_SECONDS."""
        now = time.time()
        to_reindex = [r for r, t in self._pending.items() if now - t >= DEBOUNCE_SECONDS]
        for repo in to_reindex:
            del self._pending[repo]
            self._reindex(repo)

    def _reindex(self, repo: str):
        print(f"[watch] Reindexing {repo}...")
        try:
            resp = httpx.post(
                f"{GATEWAY_URL}/proxy/index/index_repo",
                json={"repo": repo, "ref": "local"},
                timeout=120.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                print(f"[watch] {repo}: {data.get('chunks_new', 0)} new, "
                      f"{data.get('chunks_updated', 0)} updated, "
                      f"{data.get('skipped_unchanged', 0)} unchanged")
            else:
                print(f"[watch] {repo}: Error {resp.status_code}: {resp.text}", file=sys.stderr)
        except Exception as e:
            print(f"[watch] {repo}: Failed to reindex: {e}", file=sys.stderr)


def main():
    repos_path = os.path.abspath(REPOS_ROOT)
    print(f"[watch] Watching {repos_path} for .ai/memory/ changes...")
    print(f"[watch] Gateway: {GATEWAY_URL}")
    print(f"[watch] Debounce: {DEBOUNCE_SECONDS}s")
    print("[watch] Press Ctrl+C to stop")

    handler = MemoryPackHandler()
    observer = Observer()
    observer.schedule(handler, repos_path, recursive=True)
    observer.start()

    try:
        while True:
            handler.process_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[watch] Stopping...")
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
