# Contributing to the DevOps Error Library

Thank you for helping build the open-source encyclopedia of real DevOps, Cloud, Kubernetes, Docker, Terraform and OpenStack errors. Every accurate page you add saves another engineer a bad night. This guide explains the quality bar, how to add and update errors, the validation/CI rules, and the PR process.

> **TL;DR**
> ```bash
> errlib new "Terraform State Lock" --tech terraform --severity high
> # fill in every section with real logs + read-only diagnostics
> errlib validate        # must pass
> # commit, push, open a PR using the checklist below
> ```

---

## 🎯 The quality bar

This is a curated reference, not a link dump. Hold every contribution to **senior DevOps / SRE level**:

- **Accuracy over quantity.** One correct, complete page beats ten thin ones. We would rather merge slowly than merge wrong.
- **No fabricated logs.** Error messages must be **verbatim** strings you have actually seen, reproduced, or sourced from official docs/issues. Do not invent plausible-looking output. If you only have a paraphrase, say so or don't include it.
- **Read-only diagnostics only.** Everything in *Diagnostic Commands* must be safe to run on a live system: `describe`, `get`, `logs`, `status`, `journalctl`, `show`, `inspect`, `EXPLAIN`, etc. Never put a destructive or state-changing command in that section — those belong in *Resolution*, clearly flagged as risky.
- **Explain the mechanism.** The *Root Cause Analysis* must connect the log line to *why* the system produced it, not just restate the symptom.
- **Write for the reader at 3 a.m.** Precise, concrete, skimmable. Assume competence; don't pad.

No AI slop. Pages generated wholesale by an LLM without verification will be closed. Using AI to draft is fine — verifying every log line and command is mandatory.

---

## ➕ Adding a new error

### 1. Scaffold the page

```bash
errlib new "<Human Error Title>" --tech <technology> [--severity <level>] [--tags t1,t2] [--subdir <service>]
```

Examples:

```bash
errlib new "Kubernetes Evicted Pod" --tech kubernetes --severity high
errlib new "Nova No Valid Host" --tech openstack --subdir nova --severity high
```

- `--tech` picks the `errors/<technology>/` folder and is **required**.
- `--subdir` nests the file one level deeper — **use it for OpenStack services** (`nova`, `cinder`, `neutron`, `glance`, `keystone`, `heat`, `horizon`, `swift`, `placement`, `ironic`).
- `--severity` is one of `info | low | medium | high | critical` (defaults to `medium`).
- `--tags` is a comma-separated list.

The title becomes a **kebab-case slug**, and the **slug must equal the filename** (without `.md`). `errlib new` handles this for you — don't rename the file afterwards without updating the `slug:` field to match.

### 2. Fill in every section

Open the generated file and complete **all 14 sections** — none may be empty. Use [`ERROR_TEMPLATE.md`](./ERROR_TEMPLATE.md) as the canonical reference and [`errors/kubernetes/kubernetes-crashloopbackoff.md`](./errors/kubernetes/kubernetes-crashloopbackoff.md) as a worked example.

Section-by-section expectations:

| Section | What good looks like |
| --- | --- |
| **Error Message** | Verbatim string(s) in a fenced block. Include 1–2 realistic variants people paste into search. |
| **Description** | 1–2 paragraphs: what it means, which component emits it, when. |
| **Technologies** | The technology + the component/subsystem. |
| **Severity** | The level **and** the operational impact (degraded / partial / full outage / data-loss risk). |
| **Common Causes** | Ordered by real-world frequency, stated concretely. |
| **Root Cause Analysis** | The mechanism — how each cause produces this exact error. |
| **Diagnostic Commands** | Real, **read-only** commands with a comment on what each reveals. |
| **Expected Results** | What the output looks like when broken vs. healthy. |
| **Resolution** | Numbered, actionable steps. Flag any risky/destructive step. |
| **Validation** | The command + output that proves the error is resolved. |
| **Prevention** | Concrete guardrails / CI checks to stop recurrence. |
| **Related Errors** | Relative links to neighbouring pages. |
| **References** | Official docs first; deeper guides may link to https://devopsaitoolkit.com/blog. |
| **Tags** | The same tags as the front matter, as `` `code` `` separated by `·`. |

### 3. Get the front matter right

```yaml
---
title: "Kubernetes CrashLoopBackOff"   # human title, quoted
slug: kubernetes-crashloopbackoff      # MUST match the filename (kebab-case)
technologies: [kubernetes]             # one or more
severity: high                         # info | low | medium | high | critical
tags: [kubernetes, pod, scheduling, crashloopbackoff, production]
related: [kubernetes-imagepullbackoff, kubernetes-oomkilled]  # slugs of related pages
last_reviewed: 2026-06-27              # YYYY-MM-DD, the date you verified it
---
```

- **`slug` must equal the filename.** This is checked in CI.
- **`severity`** must be one of the five allowed values.
- **`related`** lists *slugs* (not paths); the body's *Related Errors* section links to them with relative paths.
- **`tags`** should include the technology, the area, the symptom, and `production` where relevant — they power `errlib search --tag`.
- **`last_reviewed`** is the date a human verified the content.

### 4. Validate locally

```bash
errlib validate          # front matter + sections + slugs; exits non-zero on any issue
errlib index             # rebuild the JSON index (optional locally; CI does it)
errlib search "<a phrase from your page>"   # sanity-check it's findable
```

`errlib validate` must print `OK — N error document(s) valid.` before you open a PR.

---

## ✏️ Updating or verifying existing errors

- Found something inaccurate or outdated? Fix it and bump `last_reviewed` to today's date.
- Re-running the diagnostic commands on a current version of the technology and confirming the output still matches counts as a real, valuable contribution — bump `last_reviewed`.
- If a tool's output format changed across versions, note the affected versions in *Description* or *Expected Results* rather than overwriting; keep the page useful for people on older releases.
- Keep edits scoped: one logical change per PR makes review fast.

---

## ✅ Validation & CI rules

Every pull request runs CI, which:

1. Runs **`errlib validate`** — fails on missing/empty sections, malformed or missing front-matter keys, an invalid `severity`, or a `slug` that doesn't match the filename.
2. Rebuilds the **JSON search index** (`errlib index`) to confirm the corpus compiles.
3. Regenerates the category indexes (`scripts/gen_indexes.py`) — these are navigation aids and are excluded from validation and the search index, so you don't have to hand-edit them.
4. Runs the **test suite** (`pytest`).

If `errlib validate` fails locally, it will fail in CI — fix it before pushing.

---

## 🔀 Pull request process

1. Fork the repo and create a branch: `git checkout -b add/<tech>-<slug>`.
2. Add or edit error pages; run `errlib validate` until it passes.
3. Commit with a clear message, e.g. `Add: Terraform State Lock error`.
4. Open a PR against `main` and fill in the checklist below.
5. A maintainer reviews for accuracy and the quality bar; address feedback; we merge.

### PR checklist

- [ ] Created the page with `errlib new` (correct `--tech` / `--subdir`).
- [ ] All **14 sections** filled in — none empty.
- [ ] Error Message is **verbatim**; no fabricated logs.
- [ ] Diagnostic Commands are **read-only** and safe to run live.
- [ ] Front matter complete: valid `severity`, `slug` == filename, useful `tags`, `related` slugs, `last_reviewed` set.
- [ ] `errlib validate` passes locally (`OK — N error document(s) valid.`).
- [ ] Related links and references resolve.
- [ ] One logical change per PR.

---

## 📦 Claiming & coordinating large batches

Adding 20+ errors for a technology? Help us avoid duplicate work:

1. Open a tracking issue titled e.g. `Batch: 30 PostgreSQL errors` listing the titles/slugs you plan to add.
2. A maintainer will confirm there's no overlap and effectively "assign" the batch to you.
3. Submit in **reviewable chunks** (roughly 5–10 errors per PR) rather than one giant PR — it's faster to review and less likely to bit-rot.
4. Check the per-technology targets in [`ROADMAP.md`](./ROADMAP.md) so your batch moves a real goal forward.

---

## 🎨 Style & structure conventions

- **One error per file.** Never combine multiple distinct errors in a page.
- **Folder = technology.** `errors/<technology>/`. OpenStack is split by **service** subfolder.
- **Filename = slug**, kebab-case, prefixed with the technology where natural (`kubernetes-crashloopbackoff.md`, `nova-no-valid-host.md`).
- **Severity scale:** `info` (informational) → `low` → `medium` → `high` → `critical` (data loss / full outage). Choose by operational impact, not by how scary the message looks.
- **Voice:** senior engineer, concrete, no filler. Prefer imperative steps in *Resolution*.
- **Code blocks:** use ```text for logs/output, ```bash for commands, ```yaml for manifests.
- **Links:** relative paths between error pages; absolute URLs for external references.

---

## 📄 Licensing of contributions

By contributing, you agree that:

- **Error content** (anything under `errors/`) is licensed **CC BY 4.0**.
- **Code** (`errlib/`, `scripts/`) is licensed **MIT**.

Only submit content you have the right to share. Thanks for making DevOps troubleshooting better for everyone. 🙌
