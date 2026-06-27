# Roadmap

The DevOps Error Library is built on one durable foundation: a tree of plain Markdown files under [`errors/`](./errors/), compiled by [`errlib`](./errlib/) into a JSON search index. **Every item on this roadmap reads that same corpus and index** — no rewrites, no lock-in. We grow the content, and tooling layers on top.

We're at **~167 documented errors across 14 technologies** today, architected to scale to **10,000+**. Here's how we get there.

> Want to help? See [`CONTRIBUTING.md`](./CONTRIBUTING.md). The single highest-leverage thing you can do is add accurate error pages.

---

## 🟢 Near-term — grow & harden the corpus

The priority is breadth and depth of high-quality, verified errors, plus the tooling that keeps the corpus trustworthy.

### Per-technology targets

Stretch goals for the most-requested technologies (current counts in [`errors/README.md`](./errors/README.md)):

| Technology | Now | Target |
| --- | ---: | ---: |
| Kubernetes | 16 | **200** |
| Docker | 12 | **150** |
| Terraform | 16 | **200** |
| OpenStack (all services) | 21 | **250** |
| Linux | 12 | 150 |
| GitLab | 12 | 100 |
| Prometheus / Grafana | 22 | 150 |
| RabbitMQ / Redis | 20 | 120 |
| PostgreSQL / MySQL | 20 | 150 |
| Ceph / Linstor | 16 | 120 |

These are directional, not gates — accuracy still beats quantity. Batches are coordinated via tracking issues (see [`CONTRIBUTING.md`](./CONTRIBUTING.md#-claiming--coordinating-large-batches)).

### Corpus quality

- **Category indexes** — keep `scripts/gen_indexes.py` output fresh on every merge (per-category `README.md` + the root index).
- **Link checking** — CI step that verifies every relative *Related Errors* link and external *References* URL resolves.
- **Freshness tracking** — surface pages with a stale `last_reviewed` date so they get re-verified.
- **Front-matter & schema tightening** — broaden `errlib validate` checks (tag hygiene, `related` slugs that actually exist, severity sanity).
- **New technologies** — add the next wave of folders as contributors bring verified errors (CI/CD runners, Helm, ArgoCD, Nginx, HAProxy, etcd, cloud-provider APIs, …).

---

## 🟡 Mid-term — make the corpus searchable everywhere

Once the index is rich, expose it through more surfaces — all reading `errlib`'s JSON index.

- **CLI search tool packaging** — publish `errlib` to PyPI (`pip install devops-error-library`) and ship prebuilt binaries so the local fuzzy search is a one-line install. *(The CLI itself already exists via `errlib search`.)*
- **Static docs site** — generate a browsable, SEO-friendly site directly from the Markdown corpus (one URL per error), so pages rank for "Kubernetes / Terraform / Docker / OpenStack troubleshooting" searches.
- **Web search UI** — a hosted search front-end over the JSON index: paste a log line, get matching pages, filter by technology/severity/tag.
- **REST API** — a thin HTTP service over the JSON index (`/search`, `/errors/<slug>`, `/stats`) so other tools and dashboards can query the library programmatically.
- **GitHub Action** — drop-in Action that, on a failed CI job, searches the library for the failure's error string and comments the matching error pages on the run — troubleshooting where the failure happens.

---

## 🔵 Long-term — intelligence & ecosystem

With a large, structured, verified corpus and an API, build the smart layer on top.

- **AI troubleshooting suggestions** — grounded, retrieval-based suggestions that cite specific library pages (never ungrounded guesses), bringing the structured corpus to the [AI Incident Response Assistant](https://devopsaitoolkit.com/dashboard/incident-response).
- **MCP server** — a [Model Context Protocol](https://modelcontextprotocol.io) server so AI agents and IDE assistants can query the library as a first-class tool (`search_errors`, `get_error`), with citations back to the corpus.
- **VS Code extension** — search and read errors without leaving the editor; surface matching pages from terminal output and log files.
- **Community voting** — let readers mark whether a page resolved their issue, feeding a quality signal back to maintainers.
- **Error popularity rankings** — aggregate search and voting data into "most-hit errors per technology" and trending pages, guiding where to deepen coverage next.

---

## 🧭 Guiding principles

1. **Markdown is the source of truth.** Every feature reads `errors/**/*.md` and the generated JSON index. If a feature needs a separate database of content, we've taken a wrong turn.
2. **Accuracy over quantity.** Growth never lowers the bar — verified logs, read-only diagnostics, real fixes.
3. **Offline-first.** Core value (the corpus + `errlib search`) always works with no network and no account.
4. **Open by default.** Content stays CC BY 4.0; tooling stays MIT.

Have an idea or want to own a roadmap item? Open an issue or read [`CONTRIBUTING.md`](./CONTRIBUTING.md). 🚀
