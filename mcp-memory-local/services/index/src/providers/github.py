"""GitHubProvider -- reads repos from GitHub via REST API."""

import base64
import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import AsyncIterator, Optional

import httpx
import yaml

import sys
sys.path.insert(0, "/app/shared/src")
from manifest import ManifestData

from .types import RepoDescriptor, DocumentDescriptor, DocumentContent

logger = logging.getLogger("index")


class GitHubProvider:
    """LocationProvider implementation for GitHub repos via REST API."""

    def __init__(self, pool=None):
        self._token = os.environ.get("GITHUB_TOKEN", "")
        if self._token == "":
            raise ValueError(
                "GITHUB_TOKEN is set but empty -- this is a misconfiguration. "
                "Either set a valid PAT or remove the variable entirely."
            )
        self._repos_raw = os.environ.get("GITHUB_REPOS", "")
        self._api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
        self._default_branch = os.environ.get("GITHUB_DEFAULT_BRANCH", "main")
        self._pool = pool
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
        )

    @property
    def name(self) -> str:
        return "github"

    def _repo_list(self) -> list[str]:
        """Parse GITHUB_REPOS into list of owner/repo strings."""
        if not self._repos_raw:
            return []
        return [r.strip() for r in self._repos_raw.split(",") if r.strip()]

    def _check_rate_limit(self, response: httpx.Response) -> None:
        """Log warning if rate limit is running low."""
        remaining = response.headers.get("X-RateLimit-Remaining")
        if remaining is None:
            return
        try:
            remaining_int = int(remaining)
        except ValueError:
            return
        if remaining_int < 100:
            limit = response.headers.get("X-RateLimit-Limit", "?")
            reset = response.headers.get("X-RateLimit-Reset", "?")
            reset_str = reset
            try:
                reset_str = datetime.fromtimestamp(int(reset), tz=timezone.utc).isoformat()
            except (ValueError, TypeError, OSError):
                pass
            logger.warning(
                f"GitHub API rate limit low: {remaining_int}/{limit} remaining, resets at {reset_str}"
            )

    def _handle_error(self, response: httpx.Response, repo: str, context: str = "") -> None:
        """Raise descriptive exceptions for HTTP error codes."""
        status = response.status_code
        ctx = f" ({context})" if context else ""

        if status == 401:
            raise RuntimeError("GitHub authentication failed -- check GITHUB_TOKEN")

        if status == 403:
            remaining = response.headers.get("X-RateLimit-Remaining")
            if remaining is not None and remaining == "0":
                reset = response.headers.get("X-RateLimit-Reset", "?")
                reset_str = reset
                try:
                    reset_str = datetime.fromtimestamp(int(reset), tz=timezone.utc).isoformat()
                except (ValueError, TypeError, OSError):
                    pass
                raise RuntimeError(
                    f"GitHub API rate limit exceeded -- resets at {reset_str}"
                )
            raise RuntimeError(
                f"GitHub access denied for {repo}{ctx} -- check PAT permissions"
            )

        if status >= 400:
            raise RuntimeError(
                f"GitHub API error {status} for {repo}{ctx}"
            )

    async def enumerate_repos(self) -> AsyncIterator[RepoDescriptor]:
        repos = self._repo_list()
        if not repos:
            return

        for owner_repo in repos:
            url = f"{self._api_url}/repos/{owner_repo}/contents/.ai/memory/manifest.yaml"
            resp = await self._client.get(url)
            self._check_rate_limit(resp)

            if resp.status_code == 404:
                logger.warning(f"No .ai/memory/manifest.yaml in {owner_repo} -- skipping")
                continue

            if resp.status_code == 401:
                self._handle_error(resp, owner_repo, "enumerate_repos")

            if resp.status_code != 200:
                self._handle_error(resp, owner_repo, "enumerate_repos")

            # Parse manifest content (base64 encoded from GitHub Contents API)
            data = resp.json()
            content_b64 = data.get("content", "")
            manifest_text = base64.b64decode(content_b64).decode("utf-8")
            raw = yaml.safe_load(manifest_text) or {}

            scope = raw.get("scope", {})
            embedding = raw.get("embedding", {})
            repo_name = owner_repo.split("/")[-1]

            manifest = ManifestData(
                pack_version=raw.get("pack_version", 1),
                scope_repo=scope.get("repo", ""),
                scope_namespace=scope.get("namespace", "default"),
                owners=raw.get("owners", []),
                classification=raw.get("classification", "internal"),
                embedding_model=embedding.get("model", "nomic-embed-text"),
                embedding_version=embedding.get("version", "locked"),
            )

            yield RepoDescriptor(
                namespace=manifest.scope_namespace,
                repo=repo_name,
                provider_name="github",
                external_id=owner_repo,
                metadata={
                    "pack_version": manifest.pack_version,
                    "owners": manifest.owners,
                    "classification": manifest.classification,
                    "embedding_model": manifest.embedding_model,
                    "embedding_version": manifest.embedding_version,
                },
            )

    async def enumerate_documents(
        self, repo: RepoDescriptor
    ) -> AsyncIterator[DocumentDescriptor]:
        owner_repo = repo.external_id
        branch = self._default_branch

        # Try cache first
        cached_shas = await self._get_cached_tree(owner_repo, branch)
        etag = None
        if cached_shas is not None:
            etag = cached_shas.get("_etag")

        url = f"{self._api_url}/repos/{owner_repo}/git/trees/{branch}:.ai"
        params = {"recursive": "1"}
        headers = {}
        if etag:
            headers["If-None-Match"] = etag

        resp = await self._client.get(url, params=params, headers=headers)
        self._check_rate_limit(resp)

        if resp.status_code == 404:
            # No .ai directory
            return

        if resp.status_code == 304 and cached_shas is not None:
            # Tree unchanged, yield from cache
            for path, sha in cached_shas.items():
                if path.startswith("_"):
                    continue
                yield DocumentDescriptor(
                    repo=repo,
                    path=f".ai/{path}",
                    anchor=None,
                    external_id=sha,
                )
            return

        if resp.status_code != 200:
            self._handle_error(resp, owner_repo, "enumerate_documents")

        tree_data = resp.json()
        new_etag = resp.headers.get("ETag")
        tree_sha = tree_data.get("sha")
        blob_shas: dict[str, str] = {}

        for entry in tree_data.get("tree", []):
            if entry.get("type") != "blob":
                continue
            path = entry["path"]
            # Filter: memory/**/*.md and memory/**/*.yaml, excluding manifest.yaml
            if not path.startswith("memory/"):
                continue
            if not (path.endswith(".md") or path.endswith(".yaml")):
                continue
            if path == "memory/manifest.yaml":
                continue

            sha = entry["sha"]
            blob_shas[path] = sha

            yield DocumentDescriptor(
                repo=repo,
                path=f".ai/{path}",
                anchor=None,
                external_id=sha,
            )

        # Update cache
        await self._set_cached_tree(owner_repo, branch, new_etag, tree_sha, blob_shas)

    async def fetch_content(
        self, doc: DocumentDescriptor
    ) -> DocumentContent:
        owner_repo = doc.repo.external_id
        blob_sha = doc.external_id

        # Try blob cache first
        cached_text = await self._get_cached_blob(blob_sha)
        if cached_text is not None:
            content_hash = hashlib.sha256(cached_text.encode("utf-8")).hexdigest()
            return DocumentContent(doc=doc, text=cached_text, content_hash=content_hash)

        url = f"{self._api_url}/repos/{owner_repo}/git/blobs/{blob_sha}"
        resp = await self._client.get(url)
        self._check_rate_limit(resp)

        if resp.status_code != 200:
            self._handle_error(resp, owner_repo, f"fetch blob {doc.path}")

        data = resp.json()
        text = base64.b64decode(data["content"]).decode("utf-8")
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

        # Cache the blob
        await self._set_cached_blob(blob_sha, text)

        return DocumentContent(doc=doc, text=text, content_hash=content_hash)

    # ---- Cache helpers (Phase 4) ----

    async def _get_cached_tree(self, owner_repo: str, branch: str) -> Optional[dict]:
        """Look up cached tree ETag and blob SHAs."""
        if self._pool is None:
            return None
        cache_key = f"{owner_repo}:{branch}"
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT etag, blob_shas FROM github_cache "
                    "WHERE cache_type = 'tree_etag' AND cache_key = $1",
                    cache_key,
                )
            if row is None:
                return None
            result = json.loads(row["blob_shas"]) if row["blob_shas"] else {}
            if row["etag"]:
                result["_etag"] = row["etag"]
            return result
        except Exception:
            logger.warning("Failed to read tree cache", exc_info=True)
            return None

    async def _set_cached_tree(
        self, owner_repo: str, branch: str,
        etag: Optional[str], tree_sha: Optional[str], blob_shas: dict[str, str]
    ) -> None:
        """Upsert cached tree data."""
        if self._pool is None:
            return
        cache_key = f"{owner_repo}:{branch}"
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO github_cache (cache_type, cache_key, etag, tree_sha, blob_shas)
                    VALUES ('tree_etag', $1, $2, $3, $4::jsonb)
                    ON CONFLICT (cache_type, cache_key) DO UPDATE SET
                        etag = EXCLUDED.etag,
                        tree_sha = EXCLUDED.tree_sha,
                        blob_shas = EXCLUDED.blob_shas,
                        updated_at = now()
                    """,
                    cache_key, etag, tree_sha, json.dumps(blob_shas),
                )
        except Exception:
            logger.warning("Failed to write tree cache", exc_info=True)

    async def _get_cached_blob(self, blob_sha: str) -> Optional[str]:
        """Look up cached blob content by SHA."""
        if self._pool is None:
            return None
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT content FROM github_cache "
                    "WHERE cache_type = 'blob' AND cache_key = $1",
                    blob_sha,
                )
            return row["content"] if row else None
        except Exception:
            logger.warning("Failed to read blob cache", exc_info=True)
            return None

    async def _set_cached_blob(self, blob_sha: str, text: str) -> None:
        """Cache decoded blob content."""
        if self._pool is None:
            return
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO github_cache (cache_type, cache_key, content)
                    VALUES ('blob', $1, $2)
                    ON CONFLICT (cache_type, cache_key) DO NOTHING
                    """,
                    blob_sha, text,
                )
        except Exception:
            logger.warning("Failed to write blob cache", exc_info=True)
