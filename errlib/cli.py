"""The ``errlib`` command line interface: search, validate, index, stats, new.

Dependency-light (argparse + PyYAML) so engineers can run it anywhere::

    errlib search "CrashLoopBackOff"
    errlib search --tech kubernetes --severity high
    errlib validate
    errlib index
    errlib stats
    errlib new "Kubernetes Evicted Pod" --tech kubernetes --severity high
"""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .index import DEFAULT_ROOT, INDEX_FILE, build_index, stats, write_index
from .new_error import create_error
from .search import search
from .validate import validate_tree


def _cmd_search(args: argparse.Namespace) -> int:
    docs = build_index(args.root)
    results = search(
        docs,
        args.query,
        technology=args.tech,
        tag=args.tag,
        severity=args.severity,
        message=args.message,
        limit=args.limit,
    )
    if not results:
        print("No matching errors found.")
        return 1
    for res in results:
        d = res.doc
        techs = ",".join(d.technologies)
        print(f"[{d.severity:<8}] {d.title}")
        print(f"           {d.path}  ({techs})  score={res.score}")
    print(f"\n{len(results)} result(s).")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    issues = validate_tree(args.root)
    if not issues:
        count = len(build_index(args.root))
        print(f"OK — {count} error document(s) valid.")
        return 0
    for issue in issues:
        print(f"{issue.path}: {issue.message}")
    print(f"\n{len(issues)} issue(s) found.", file=sys.stderr)
    return 1


def _cmd_index(args: argparse.Namespace) -> int:
    docs = build_index(args.root)
    out = write_index(docs, args.out)
    print(f"Wrote {out} ({len(docs)} documents).")
    return 0


def _cmd_stats(args: argparse.Namespace) -> int:
    for tech, count in stats(build_index(args.root)).items():
        print(f"{tech:<16} {count}")
    return 0


def _cmd_new(args: argparse.Namespace) -> int:
    path = create_error(
        args.title,
        args.tech,
        severity=args.severity,
        tags=args.tags.split(",") if args.tags else None,
        root=args.root,
        subdir=args.subdir,
    )
    print(f"Created {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Construct the argparse CLI."""
    parser = argparse.ArgumentParser(prog="errlib", description="Search the DevOps Error Library.")
    parser.add_argument("--version", action="version", version=f"errlib {__version__}")
    parser.add_argument("--root", default=DEFAULT_ROOT, help="Path to the errors/ tree.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_search = sub.add_parser("search", help="Search errors by text and filters.")
    p_search.add_argument("query", nargs="?", default=None, help="Free-text query.")
    p_search.add_argument("--tech", help="Filter by technology.")
    p_search.add_argument("--tag", help="Filter by tag.")
    p_search.add_argument("--severity", help="Filter by severity.")
    p_search.add_argument("--message", help="Match against the error message only.")
    p_search.add_argument("--limit", type=int, default=20)
    p_search.set_defaults(func=_cmd_search)

    p_validate = sub.add_parser("validate", help="Validate every error document.")
    p_validate.set_defaults(func=_cmd_validate)

    p_index = sub.add_parser("index", help="Build the JSON search index.")
    p_index.add_argument("--out", default=INDEX_FILE)
    p_index.set_defaults(func=_cmd_index)

    p_stats = sub.add_parser("stats", help="Show per-technology document counts.")
    p_stats.set_defaults(func=_cmd_stats)

    p_new = sub.add_parser("new", help="Scaffold a new error document.")
    p_new.add_argument("title", help="Human error title, e.g. 'Kubernetes Evicted Pod'.")
    p_new.add_argument("--tech", required=True, help="Technology, e.g. kubernetes.")
    p_new.add_argument("--severity", default="medium")
    p_new.add_argument("--tags", help="Comma-separated tags.")
    p_new.add_argument("--subdir", help="Optional nested dir (e.g. an OpenStack service).")
    p_new.set_defaults(func=_cmd_new)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``errlib`` console script."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
