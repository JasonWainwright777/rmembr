# rMEMbr Architect Showcase — Demo Script

Prompts to demonstrate rMEMbr's value to the architecture team. Each section builds on the previous one, showing how AI assistants get governed context automatically.

---

## 1. The Problem: "What standards apply to my task?"

Start here — show that rMEMbr knows what 9 enterprise standards exist and can surface them on demand.

> "List all enterprise standards available in rMEMbr"

**What to highlight:** Standards are served live from the `enterprise-standards` GitHub repo. When the architecture team updates a standard on GitHub, every AI assistant picks it up automatically — no deployments, no copy-paste.

---

## 2. Task-Aware Standard Selection

This is the headline feature. Show how different tasks pull different standards — no more "dump everything into the prompt."

### Bicep task (should pull Bicep + CUBI patterns)

> "Get a context bundle for writing a Bicep module for a new storage account in sample-repo-a"

**What to highlight:** Only the Bicep standard (with full CUBI content — naming functions, private endpoint patterns, module layout) is selected. ADO, Docker, Terraform, .NET standards are excluded. The AI gets 20KB of directly relevant governance instead of 5 random standards.

### .NET API task (should pull API + .NET standards)

> "Get a context bundle for adding a new REST API endpoint to sample-repo-a"

**What to highlight:** Pulls REST API Design and .NET Application Standards. The AI will know our URL conventions, HTTP method rules, and .NET patterns — not our Bicep or Terraform rules.

### Docker + observability task (should pull Docker + Logging standards)

> "Get a context bundle for containerizing a service with proper logging in sample-repo-a"

**What to highlight:** Pulls Docker Container Standards and Logging & Monitoring Standard. Observability scores higher because "logging" matches directly. The AI knows our base image policy, health check requirements, and structured logging format.

### Generic task (should pull zero standards)

> "Get a context bundle for understanding the project structure of sample-repo-a"

**What to highlight:** Zero standards selected — no token budget wasted. The bundle still includes repo-specific context (architecture, branching, local dev setup).

---

## 3. Manifest Pinning — Repo-Level Governance

Show how a repo can declare "always include these standards regardless of task."

> "Get a context bundle for refactoring database queries in sample-repo-b"

**What to highlight:** sample-repo-b pins `enterprise/bicep/infrastructure-as-code` in its manifest. Even though the task says "database queries" (no keyword match), the Bicep standard is included because the repo owner mandated it. This is how platform teams enforce governance without relying on AI keyword matching.

---

## 4. Explainability — "Why did the AI get this context?"

After any bundle call above, use the bundle ID to explain the selection.

> "Explain how that last context bundle was assembled"

**What to highlight:** Shows exactly which standards were included, why (pinned vs keyword match), what the match scores were, and which standards were available but not selected. Full audit trail — architects can verify the AI got the right governance.

---

## 5. Live Standards from GitHub

Show that standards content is live, not stale.

> "Show me the Bicep infrastructure-as-code standard"

**What to highlight:** The response shows the full CUBI-specific Bicep standard (v2, ~20KB) with `coreParams`, `constructResourceName`, private endpoint patterns, multi-region architecture, pipeline hierarchy — all pulled live from `JasonWainwright777/enterprise-standards` on GitHub. Point out the path says `github:JasonWainwright777/enterprise-standards/...`.

---

## 6. Cross-Repo Context (if rmembr repo is indexed)

Show that the same system works for rMEMbr's own repo.

> "Get a context bundle for adding a new retrieval ranking boost to the rmembr repo"

**What to highlight:** The AI gets rMEMbr's own architecture docs, ranking pipeline details, and relevant standards — same system, different repo. One MCP server serves context for every repo in the organization.

---

## Key Talking Points for Architects

1. **Governance at the point of generation** — Standards are injected into AI context automatically, not via training or hope
2. **Task-aware selection** — Only relevant standards consume the token budget (5 of 9 standards, not all 9)
3. **Two-layer control** — Manifest pinning (repo owners enforce) + keyword matching (AI discovers)
4. **Live from GitHub** — Update a standard, every AI assistant gets it immediately
5. **Explainable** — Full audit trail of what context was provided and why
6. **Federated** — Repo teams own their memory packs, architecture team owns the standards, rMEMbr orchestrates
7. **Zero-friction adoption** — Add a `CLAUDE.md` one-liner and context loads automatically, developers never have to ask
8. **No vendor lock-in** — Works with any MCP-compatible AI client (Claude Code, VS Code Copilot, etc.)
