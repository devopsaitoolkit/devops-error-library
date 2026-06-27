<div align="center">

# DevOps Error Library

**The open-source encyclopedia of real DevOps & cloud infrastructure errors — searchable, structured, and battle-tested.**

[![Errors](https://img.shields.io/badge/errors-167-blue)](./errors/README.md)
[![Technologies](https://img.shields.io/badge/technologies-14-success)](./errors/README.md)
[![License: CC BY 4.0](https://img.shields.io/badge/content-CC%20BY%204.0-lightgrey)](https://creativecommons.org/licenses/by/4.0/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)](./CONTRIBUTING.md)
[![CI](https://img.shields.io/github/actions/workflow/status/devopsaitoolkit/devops-error-library/ci.yml?label=CI)](https://github.com/devopsaitoolkit/devops-error-library/actions)

*A growing, community-maintained troubleshooting reference for Kubernetes, Docker, Terraform, OpenStack, Linux and more — one production error per page, with real logs, real diagnostic commands, and a working local search CLI.*

</div>

---

When something breaks at 3 a.m., you don't want a chatbot guessing — you want the exact error string, the cause, the read-only command that confirms it, and the fix an experienced SRE would actually run. **DevOps Error Library** is that reference: a curated, structured knowledge base where every error lives in its own Markdown page under [`errors/<technology>/`](./errors/), validated in CI and indexed for fast offline search.

It currently documents **~167 real errors across 14 technologies** — Kubernetes, Docker, Terraform, OpenStack, Linux, GitLab, Prometheus, Grafana, RabbitMQ, Redis, PostgreSQL, MySQL, Ceph and Linstor — and is architected to scale to **10,000+**. The count grows every week, and [contributions are welcome](./CONTRIBUTING.md).

> ![Search demo](assets/search-demo.png)
> *`errlib search` running locally — placeholder screenshot.*

---

## ✨ Why this exists / Features

Most error "solutions" on the web are scattered, stale, or auto-generated filler. This library is the opposite:

- **One error, one page.** Every entry is a single self-contained Markdown file — easy to read, link, diff, and review.
- **A fixed, predictable structure.** All 14 sections, every time. You always know where the *Resolution* and *Diagnostic Commands* are.
- **Real production logs.** Error messages are the verbatim strings engineers actually paste into a search box — including realistic variants.
- **Real, read-only diagnostic commands.** Every `kubectl`, `docker`, `terraform`, `openstack` or `journalctl` command is something a senior engineer would safely run to investigate.
- **A fast local search CLI.** `errlib search` works fully offline against a JSON index — no SaaS, no telemetry, no signup.
- **Zero-dependency-ish.** The `errlib` tool needs only Python ≥ 3.10 and PyYAML. The corpus itself is plain Markdown.
- **CI-validated.** Front matter, sections, slugs and the generated index are checked on every pull request — no malformed pages get merged.
- **SEO-friendly, human-readable titles & slugs.** Pages are named the way people search ("Kubernetes CrashLoopBackOff", "Terraform State Lock"), so they're findable from a browser too.

---

## 📁 Directory Overview

Every error is a Markdown file under `errors/<technology>/`. OpenStack is large enough that it is split further by service.

```text
errors/
├── README.md              # generated index — categories + counts
├── kubernetes/
│   ├── kubernetes-crashloopbackoff.md
│   ├── kubernetes-imagepullbackoff.md
│   └── ...
├── docker/
├── terraform/
├── linux/
├── gitlab/
├── prometheus/
├── grafana/
├── rabbitmq/
├── redis/
├── postgresql/
├── mysql/
├── ceph/
├── linstor/
└── openstack/             # split by service
    ├── nova/
    ├── cinder/
    ├── neutron/
    ├── glance/
    ├── keystone/
    ├── heat/
    ├── horizon/
    ├── swift/
    ├── placement/
    └── ironic/
```

See the live counts in [`errors/README.md`](./errors/README.md).

---

## 🔎 Search

The `errlib` CLI gives you offline full-text search, filtering, validation, indexing and stats.

### Install

```bash
git clone https://github.com/devopsaitoolkit/devops-error-library.git
cd devops-error-library
pip install -e .
```

That installs the `errlib` console script (Python ≥ 3.10, only PyYAML required).

### Search the library

```bash
# Free-text search across titles, messages, tags and bodies
errlib search "CrashLoopBackOff"

# Filter by technology and severity
errlib search --tech kubernetes --severity high

# Filter by tag
errlib search --tag scheduling

# Match only against the error message (great for pasting a log line)
errlib search --message "no valid host"

# Limit the number of results
errlib search "permission denied" --limit 5
```

Example output:

```text
[high    ] Kubernetes CrashLoopBackOff
           kubernetes/kubernetes-crashloopbackoff.md  (kubernetes)  score=42
[high    ] Kubernetes OOMKilled
           kubernetes/kubernetes-oomkilled.md  (kubernetes)  score=18

2 result(s).
```

### Other commands

```bash
errlib validate          # validate front matter + sections + slugs (what CI runs)
errlib index             # build the JSON search index
errlib stats             # per-technology document counts
errlib new "Kubernetes Evicted Pod" --tech kubernetes --severity high
```

`errlib new` also accepts `--tags tag1,tag2` and `--subdir <service>` (for the OpenStack services). Pass `--root <path>` to any command to point at a different `errors/` tree.

---

## 📄 The Error Page Format

Every page begins with YAML front matter and then follows the same 14 sections. The canonical template lives in [`ERROR_TEMPLATE.md`](./ERROR_TEMPLATE.md).

```yaml
---
title: "Kubernetes CrashLoopBackOff"
slug: kubernetes-crashloopbackoff
technologies: [kubernetes]
severity: high            # info | low | medium | high | critical
tags: [kubernetes, pod, scheduling, crashloopbackoff, production]
related: [kubernetes-imagepullbackoff, kubernetes-oomkilled]
last_reviewed: 2026-06-27
---
```

The fixed sections, in order:

1. **Error Message** — the verbatim log/CLI string (plus realistic variants)
2. **Description** — what it means and where it comes from
3. **Technologies** — component / subsystem
4. **Severity** — operational impact, for triage
5. **Common Causes** — ordered by how often they occur in production
6. **Root Cause Analysis** — the *mechanism*, not just the symptom
7. **Diagnostic Commands** — real, **read-only** commands
8. **Expected Results** — what healthy vs. broken output looks like
9. **Resolution** — numbered, actionable fix steps
10. **Validation** — how to confirm the fix worked
11. **Prevention** — guardrails so it doesn't recur
12. **Related Errors** — links to neighbouring pages
13. **References** — official docs + deeper guides
14. **Tags** — for search and navigation

A complete real example: [`errors/kubernetes/kubernetes-crashloopbackoff.md`](./errors/kubernetes/kubernetes-crashloopbackoff.md).

---

## 🧭 Browse

- 📚 **All categories & counts:** [`errors/README.md`](./errors/README.md)
- ☸️ **Kubernetes:** [`errors/kubernetes/`](./errors/kubernetes/)
- 🐳 **Docker:** [`errors/docker/`](./errors/docker/)
- 🌍 **Terraform:** [`errors/terraform/`](./errors/terraform/)
- ☁️ **OpenStack:** [`errors/openstack/`](./errors/openstack/)
- 🐧 **Linux:** [`errors/linux/`](./errors/linux/)

Each category folder has its own generated `README.md` listing every error with its severity and tags.

---

## 🤝 Contributing

Pull requests are very welcome — this is a community knowledge base and it only gets better as more engineers add the errors they've actually fought. Read the full guide in [`CONTRIBUTING.md`](./CONTRIBUTING.md).

The short version:

```bash
errlib new "Terraform State Lock" --tech terraform --severity high
# 1. Fill in every section with real logs and read-only diagnostics
# 2. errlib validate        # must pass
# 3. open a pull request
```

CI validates the front matter, sections, slugs, rebuilds the index, and runs the tests. Quality bar: **senior DevOps / SRE level — accuracy over quantity, no fabricated logs.**

---

## 🗺 Roadmap

The corpus is the foundation. Everything else reads the same Markdown tree and JSON index. See [`ROADMAP.md`](./ROADMAP.md) for the full plan. Highlights on the way:

- 🔍 **CLI search tool** — local fuzzy search *(partly done via `errlib`)*
- 🌐 **Static docs site** + **web search UI**
- 🔌 **REST API** over the JSON index
- ⚙️ **GitHub Action** that surfaces matching errors on CI failures
- 🤖 **AI troubleshooting suggestions** grounded in the corpus
- 🧠 **MCP server** so AI agents can query the library
- 🧩 **VS Code extension**
- 👍 **Community voting** + **error popularity rankings**

---

## ❓ FAQ

**Is this AI-generated slop?**
No. Every page is hand-structured, reviewed by a human, and validated in CI against a fixed schema (front matter + 14 sections + slug rules). The bar is *senior engineer* quality: real error strings, real read-only commands, no fabricated logs.

**How do I search offline?**
`pip install -e .`, then `errlib search "<query>"`. It runs entirely against a local JSON index — no network, no account, no telemetry. Filter with `--tech`, `--tag`, `--severity` and `--message`.

**How do I add an error?**
`errlib new "<Title>" --tech <tech>` to scaffold the page, fill in every section with real logs and read-only diagnostics, run `errlib validate`, and open a PR. Full guide in [`CONTRIBUTING.md`](./CONTRIBUTING.md).

**What's the quality bar?**
Accuracy over quantity. Verbatim error messages, read-only diagnostic commands only, correct front matter, kebab-case slug matching the filename, useful tags and related links. If `errlib validate` fails, CI fails.

**How big will it get?**
The structure is designed to scale to **10,000+** documented errors. We're at ~167 today and growing — see the per-technology targets in the [roadmap](./ROADMAP.md).

**What technologies are covered?**
Today: Kubernetes, Docker, Terraform, OpenStack (split by service), Linux, GitLab, Prometheus, Grafana, RabbitMQ, Redis, PostgreSQL, MySQL, Ceph and Linstor. More are added as contributors bring them.

**What's the license?**
Error content is **CC BY 4.0**; the `errlib` code and scripts are **MIT**. See [License](#-license).

---

## 🏛 Architecture

The library is intentionally boring and durable: a tree of plain Markdown files is the single source of truth. The `errlib` tool reads that tree, validates it, and compiles it into a JSON index. Everything downstream — the CLI today, and the planned web UI, REST API and MCP server tomorrow — reads that same index. No database, no lock-in, fully versioned in Git.

```text
errors/**/*.md            (the corpus — Markdown, one error per file)
        │
        ▼
   errlib index / validate   →   errlib/index.json   (the JSON search index)
        │
        ├──▶ errlib search        (local CLI — available today)
        ├──▶ static docs site / web search UI   (planned)
        ├──▶ REST API             (planned)
        └──▶ MCP server / AI agents             (planned)
```

---

## 📚 More troubleshooting

- 📝 In-depth guides on the [DevOps AI Toolkit blog](https://devopsaitoolkit.com/blog)
- 🚑 The [AI Incident Response Assistant](https://devopsaitoolkit.com/dashboard/incident-response) for live incident triage
- 📬 The [newsletter](https://devopsaitoolkit.com/newsletter) for new errors and DevOps tips

---

## 📄 License

- **Error content** (everything under `errors/`, plus `ERROR_TEMPLATE.md`): [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/) — use it anywhere, just attribute the DevOps Error Library.
- **Code** (`errlib/`, `scripts/`): [MIT](https://opensource.org/licenses/MIT).

If this library saved your incident, ⭐ the repo and [contribute the next error](./CONTRIBUTING.md).
