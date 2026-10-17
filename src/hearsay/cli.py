"""Command line: hearsay check <file> | hearsay check --github-pr OWNER/REPO#N | hearsay claim "<sentence>"
| hearsay web | hearsay mcp."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ._version import __version__
from .config import Settings, load_env_file
from .github import fetch_pull_request
from .pipeline import ConfigError, Context, check, stderr_progress
from .report import to_json, to_markdown


def _common(p: argparse.ArgumentParser) -> None:
    fmt = p.add_mutually_exclusive_group()
    fmt.add_argument("--json", action="store_true", help="print the JSON report")
    fmt.add_argument("--markdown", action="store_true", help="print the Markdown report (default)")
    p.add_argument("--no-llm", action="store_true", help="no model calls: pattern extraction and registry/advisory checks only")
    p.add_argument("--env-file", action="append", default=[], metavar="PATH", help="load KEY=VALUE settings (repeatable)")
    p.add_argument("--json-out", metavar="PATH", help="also write the JSON report to PATH")
    p.add_argument("--md-out", metavar="PATH", help="also write the Markdown report to PATH")
    p.add_argument("--evidence", action="store_true", help="include the jury's evidence passages in Markdown")
    p.add_argument("--refresh", action="store_true", help="ignore cached answers (they are rewritten)")
    p.add_argument("--fail-on-contradicted", action="store_true", help="exit with status 2 if any claim is contradicted")
    p.add_argument("-q", "--quiet", action="store_true", help="no progress messages on stderr")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hearsay",
        description="Check claims coding agents make about the outside world against primary sources.",
    )
    parser.add_argument("--version", action="version", version=f"hearsay {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    c = sub.add_parser("check", help="check every claim in a file, stdin or a GitHub pull request description")
    c.add_argument("file", nargs="?", help="input file; '-' or omitted reads stdin")
    c.add_argument("--github-pr", metavar="OWNER/REPO#N", help="read the description of a public pull request")
    _common(c)

    one = sub.add_parser("claim", help="check a single sentence")
    one.add_argument("sentence")
    _common(one)

    web = sub.add_parser("web", help="run the web demo (FastAPI) on http://HOST:PORT")
    web.add_argument("--host", default="127.0.0.1", help="address to listen on (default 127.0.0.1)")
    web.add_argument("--port", type=int, default=8000, help="port (default 8000)")
    web.add_argument("--env-file", action="append", default=[], metavar="PATH", help="load KEY=VALUE settings (repeatable)")

    mcp = sub.add_parser("mcp", help="run the MCP server on stdio, for coding agents")
    mcp.add_argument("--env-file", action="append", default=[], metavar="PATH", help="load KEY=VALUE settings (repeatable)")
    return parser


def _load_env_files(paths: list[str]) -> bool:
    for path in paths:
        try:
            load_env_file(path)
        except OSError as exc:
            print(f"hearsay: cannot read env file {path}: {exc.strerror}", file=sys.stderr)
            return False
    return True


def _serve(args: argparse.Namespace) -> int:
    """`hearsay web` and `hearsay mcp` read settings from the environment and
    --env-file only; a .env in the working directory is not loaded for them."""
    if not _load_env_files(args.env_file):
        return 1
    if args.command == "web":
        import uvicorn

        uvicorn.run("hearsay.web.app:app", host=args.host, port=args.port, proxy_headers=False)
        return 0
    from .mcp_server import main as mcp_main

    mcp_main()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command in ("web", "mcp"):
        return _serve(args)

    default_env = Path(".env")
    if default_env.is_file():
        load_env_file(default_env)
    if not _load_env_files(args.env_file):
        return 1

    settings = Settings.from_env()
    settings.refresh_cache = args.refresh
    progress = None if args.quiet else stderr_progress
    try:
        ctx = Context.create(settings, use_llm=not args.no_llm, progress=progress)
    except ConfigError as exc:
        print(f"hearsay: {exc}", file=sys.stderr)
        return 1

    title = url = None
    if args.command == "claim":
        text = args.sentence
    elif args.github_pr:
        try:
            pr = fetch_pull_request(ctx.http, args.github_pr)
        except ValueError as exc:
            print(f"hearsay: {exc}", file=sys.stderr)
            return 1
        text = f"{pr.title}\n\n{pr.body}"
        title, url = f"{pr.owner}/{pr.repo}#{pr.number}: {pr.title}", pr.url
    elif args.file and args.file != "-":
        text = Path(args.file).read_text(encoding="utf-8")
    else:
        if sys.stdin.isatty():
            print("hearsay: give a file, '-', or pipe text on stdin", file=sys.stderr)
            return 1
        text = sys.stdin.read()

    report = check(text, context=ctx)
    report.input_title, report.input_url = title, url

    json_text = to_json(report)
    md_text = to_markdown(report, include_evidence=args.evidence)
    if args.json_out:
        Path(args.json_out).write_text(json_text + "\n", encoding="utf-8")
    if args.md_out:
        Path(args.md_out).write_text(md_text, encoding="utf-8")
    print(json_text if args.json else md_text)

    if args.fail_on_contradicted and report.totals.contradicted:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
