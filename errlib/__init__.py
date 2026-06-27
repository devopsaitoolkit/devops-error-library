"""errlib — index, search and validate the DevOps Error Library.

A dependency-light toolkit (only PyYAML) that scans the ``errors/`` tree of
Markdown error documents, builds a search index, and powers a local CLI search
tool. Designed to stay fast across tens of thousands of documents.
"""

from __future__ import annotations

__version__ = "0.1.0"

REQUIRED_FRONTMATTER = ("title", "slug", "technologies", "severity", "tags")
SEVERITIES = ("info", "low", "medium", "high", "critical")
REQUIRED_SECTIONS = (
    "Error Message",
    "Description",
    "Technologies",
    "Severity",
    "Common Causes",
    "Root Cause Analysis",
    "Diagnostic Commands",
    "Expected Results",
    "Resolution",
    "Validation",
    "Prevention",
    "Related Errors",
    "References",
    "Tags",
)
