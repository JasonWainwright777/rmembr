# Generate Architecture Report

Create an HTML architecture report for this repository. The report should be a single self-contained HTML file using Mermaid diagrams (loaded from CDN) with a dark theme.

## What to Include

Analyze the codebase and produce sections for:

1. **Service/Component Topology** — Mermaid graph showing all services, their roles, and how they communicate. Include external dependencies.
2. **User Flow** — Mermaid sequence diagram showing the primary user journey from setup through daily use.
3. **Core Data Flow** — Mermaid flowchart of the main processing pipeline (e.g., request → processing → response). Show decision points and caching.
4. **Data Model** — Mermaid ER diagram of database tables or key data structures and their relationships.
5. **API / Tool Catalog** — Table listing all endpoints, commands, or tools with categories and descriptions.
6. **Caching / Performance** — Diagram and description of caching layers, if any.
7. **Security Model** — List of security controls with descriptions (auth, validation, isolation, rate limiting).
8. **Configuration** — Key environment variables or config files and what they control.

For each section include:
- A Mermaid diagram where it adds clarity
- A brief text explanation (2-3 sentences max)
- Cards or tables for structured details

## Stats Bar

At the top, include a stats bar with 4-6 key numbers about the system (e.g., number of services, endpoints, tables, etc.).

## Style Requirements

Use this exact HTML/CSS structure for consistency across repos:

- Dark theme: `--bg: #0d1117`, `--surface: #161b22`, `--border: #30363d`, `--text: #e6edf3`
- Accent colors: blue `#58a6ff`, green `#3fb950`, orange `#d29922`, purple `#bc8cff`, cyan `#39d2e0`, red `#f85149`
- Gradient h1 title (blue → purple)
- `.card` class for content blocks (surface background, border, 8px radius)
- `.grid` class for responsive card layouts (auto-fit, minmax 340px)
- `.badge` class for inline labels (`.badge-blue`, `.badge-green`, `.badge-orange`, `.badge-purple`, `.badge-red`, `.badge-cyan`)
- `.stat` / `.stat-row` for the top stats bar
- Print-friendly `@media print` overrides (white background, dark text)
- Mermaid config: `theme: 'dark'`, node fills `#1a2332`, text `#e6edf3`, borders using accent colors

## Mermaid Setup

```html
<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
<script>
  mermaid.initialize({
    startOnLoad: true,
    theme: 'dark',
    themeVariables: {
      primaryColor: '#1a2332',
      primaryTextColor: '#e6edf3',
      primaryBorderColor: '#58a6ff',
      lineColor: '#8b949e',
      secondaryColor: '#161b22',
      tertiaryColor: '#161b22',
      fontSize: '14px',
    },
    flowchart: { curve: 'basis', padding: 15 },
    sequence: { mirrorActors: false, actorMargin: 50 },
    er: { fontSize: '12px' }
  });
</script>
```

## Output

Save the report as `docs/architecture-report.html` (or another path if the repo has a different docs convention). The file must be fully self-contained — no local CSS or JS dependencies beyond the Mermaid CDN.

## What NOT to Include

- No external persona/public-facing concepts unless the repo actually has them
- No speculative features — only document what exists in the code today
- No lengthy prose — keep descriptions to 2-3 sentences per section, let diagrams do the talking
- No emojis
