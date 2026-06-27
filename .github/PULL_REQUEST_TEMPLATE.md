<!-- Thanks for contributing to the DevOps Error Library! -->

## What does this PR do?

<!-- New error(s)? Correction? Tooling? Briefly describe. -->

## Checklist

- [ ] Each error is one Markdown file under `errors/<technology>/` (OpenStack under its service subfolder).
- [ ] Front matter has `title`, `slug`, `technologies`, `severity` (info/low/medium/high/critical) and `tags`.
- [ ] `slug` is kebab-case and **exactly matches the filename** (minus `.md`).
- [ ] All 14 sections are present, in order (Error Message → Tags).
- [ ] The **Error Message** section contains a realistic, real-world log/CLI snippet (no fabricated logs).
- [ ] **Diagnostic Commands** are READ-ONLY (no mutating/destructive commands).
- [ ] `errlib validate` passes locally.
- [ ] Information is accurate, at a senior-engineer level, and cites a reference.

## Related issues

<!-- e.g. Closes #123 -->
