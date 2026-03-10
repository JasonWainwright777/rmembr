"""FilesystemProvider -- reads repos from local filesystem under REPOS_ROOT."""

import hashlib
import os
from pathlib import Path
from typing import AsyncIterator, Optional

import sys
sys.path.insert(0, "/app/shared/src")
from manifest import parse_manifest

from .types import RepoDescriptor, DocumentDescriptor, DocumentContent


class FilesystemProvider:
    """LocationProvider implementation for local filesystem repos."""

    def __init__(self, repos_root: Optional[str] = None):
        self._repos_root = Path(repos_root or os.environ.get("REPOS_ROOT", "/repos"))

    @property
    def name(self) -> str:
        return "filesystem"

    async def enumerate_repos(self) -> AsyncIterator[RepoDescriptor]:
        if not self._repos_root.exists():
            return
        for repo_dir in sorted(self._repos_root.iterdir()):
            if not repo_dir.is_dir():
                continue
            ai_path = repo_dir / ".ai"
            if not ai_path.exists():
                continue
            manifest_path = ai_path / "memory" / "manifest.yaml"
            manifest = parse_manifest(manifest_path)
            yield RepoDescriptor(
                namespace=manifest.scope_namespace,
                repo=repo_dir.name,
                provider_name="filesystem",
                external_id=str(repo_dir),
                metadata={
                    "pack_version": manifest.pack_version,
                    "owners": manifest.owners,
                    "classification": manifest.classification,
                    "embedding_model": manifest.embedding_model,
                    "embedding_version": manifest.embedding_version,
                    "references_standards": manifest.references_standards,
                },
            )

    async def enumerate_documents(
        self, repo: RepoDescriptor
    ) -> AsyncIterator[DocumentDescriptor]:
        repo_path = Path(repo.external_id)
        ai_path = repo_path / ".ai"
        if not ai_path.exists():
            return
        md_files = list(ai_path.rglob("*.md")) + list(ai_path.rglob("*.yaml"))
        md_files = [f for f in md_files if f.name != "manifest.yaml"]
        for md_file in sorted(md_files):
            relative_path = str(md_file.relative_to(repo_path))
            yield DocumentDescriptor(
                repo=repo,
                path=relative_path,
                anchor=None,
                external_id=str(md_file),
            )

    async def fetch_content(
        self, doc: DocumentDescriptor
    ) -> DocumentContent:
        file_path = Path(doc.external_id)
        text = file_path.read_text(encoding="utf-8")
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return DocumentContent(
            doc=doc,
            text=text,
            content_hash=content_hash,
        )
