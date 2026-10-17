"""Find the official documentation for a claim.

Order: a curated map for well-known vendors and languages, then the Python
or Node.js standard library, then the package's own registry metadata
(PyPI project_urls, npm homepage). A package whose only link is a code host
(GitHub, GitLab) gets its repository page read directly instead of a search,
because restricting a search to github.com would let anyone's repository in.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from urllib.parse import urlparse

from .http import Http
from .models import Claim
from .registries import get_package, npm_version_meta
from .versions import normalize_ecosystem

# (names, domains). Names are matched against the claim's subject, package or
# the first word of its symbol, lowercased.
CURATED: list[tuple[tuple[str, ...], list[str]]] = [
    (("python", "cpython", "python standard library", "python stdlib"), ["docs.python.org"]),
    (("stripe", "stripe api"), ["docs.stripe.com", "stripe.com"]),
    (("github", "github actions", "github api", "github rest api", "github graphql api"), ["docs.github.com"]),
    (("mdn", "javascript", "web api", "web apis", "dom", "css", "html", "fetch api", "browser"), ["developer.mozilla.org"]),
    (("node", "node.js", "nodejs"), ["nodejs.org"]),
    (("typescript",), ["www.typescriptlang.org"]),
    (("react",), ["react.dev"]),
    (("django",), ["docs.djangoproject.com"]),
    (("go", "golang"), ["go.dev", "pkg.go.dev"]),
    (("rust",), ["doc.rust-lang.org"]),
    (("postgresql", "postgres"), ["www.postgresql.org"]),
    (("docker",), ["docs.docker.com"]),
    (("kubernetes", "k8s"), ["kubernetes.io"]),
    (("openai", "openai api"), ["platform.openai.com"]),
    (("tavily", "tavily api"), ["docs.tavily.com"]),
]

# Modules removed from CPython recently are not in sys.stdlib_module_names
# any more but are still documented (and still the subject of claims).
REMOVED_STDLIB = {
    "distutils", "imp", "asynchat", "asyncore", "smtpd", "aifc", "audioop", "cgi", "cgitb", "chunk",
    "crypt", "imghdr", "mailcap", "msilib", "nis", "nntplib", "ossaudiodev", "pipes", "sndhdr", "spwd",
    "sunau", "telnetlib", "uu", "xdrlib", "lib2to3",
}
PY_STDLIB = set(sys.stdlib_module_names) | REMOVED_STDLIB

NODE_BUILTINS = {
    "assert", "buffer", "child_process", "cluster", "crypto", "dgram", "dns", "events", "fs", "http", "http2",
    "https", "net", "os", "path", "perf_hooks", "process", "querystring", "readline", "stream", "string_decoder",
    "timers", "tls", "url", "util", "v8", "vm", "worker_threads", "zlib", "test",
}

CODE_HOSTS = {"github.com", "gitlab.com", "bitbucket.org", "www.github.com"}
NOT_DOCS = {"pypi.org", "www.npmjs.com", "npmjs.com", "registry.npmjs.org", "pythonhosted.org"}


@dataclass
class DocsTarget:
    domains: list[str] = field(default_factory=list)  # search scope for Tavily
    urls: list[str] = field(default_factory=list)  # pages to read directly (code host README)
    how: str = ""

    @property
    def found(self) -> bool:
        return bool(self.domains or self.urls)


def _norm(s: str | None) -> str:
    return " ".join((s or "").lower().replace("`", "").split())


def curated_domains(names: list[str | None]) -> tuple[list[str], str] | None:
    for raw in names:
        name = _norm(raw)
        if not name:
            continue
        for keys, domains in CURATED:
            for key in keys:
                if name == key or name.startswith(key + " "):
                    return domains, f"curated map: {key!r}"
    return None


def _top_module(symbol: str) -> str:
    s = symbol.strip().strip("`")
    if s.startswith("node:"):
        return "node:"
    return re.split(r"[.:(\[ ]", s)[0]


def stdlib_domains(claim: Claim) -> tuple[list[str], str] | None:
    if not claim.symbol:
        return None
    eco = normalize_ecosystem(claim.ecosystem)
    subject = _norm(claim.subject)
    top = _top_module(claim.symbol)
    if top == "node:" or (top in NODE_BUILTINS and (eco == "npm" or subject.startswith("node"))):
        return ["nodejs.org"], f"Node.js built-in module {top!r}"
    if top in PY_STDLIB and eco in (None, "pypi") and not (claim.package and _norm(claim.package) != top):
        return ["docs.python.org"], f"Python standard library module {top!r}"
    return None


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def _pick_url(candidates: list[tuple[str, str]]) -> tuple[str, str] | None:
    """(label, url) pairs -> best documentation URL. Docs links beat homepages."""
    docs = [(label, u) for label, u in candidates if re.search(r"doc", label, re.I)]
    home = [(label, u) for label, u in candidates if re.search(r"home|website", label, re.I)]
    for label, url in docs + home:
        url = url.strip()
        if url.startswith("git+"):
            url = url[4:]
        if url.startswith("http") and _host(url) not in NOT_DOCS:
            return label, url
    return None


def registry_target(http: Http, claim: Claim) -> DocsTarget | None:
    eco = normalize_ecosystem(claim.ecosystem)
    package = claim.package
    if not package and claim.symbol and eco in ("pypi", "npm"):
        package = _top_module(claim.symbol)
    if not package:
        return None
    ecosystems = [eco] if eco in ("pypi", "npm") else ["pypi", "npm"]
    for e in ecosystems:
        info = get_package(http, e, package)
        if not info.exists:
            continue
        candidates: list[tuple[str, str]] = []
        source_urls: list[str] = []
        if e == "pypi":
            pinfo = (info.raw or {}).get("info") or {}
            for label, url in (pinfo.get("project_urls") or {}).items():
                candidates.append((label, url))
                if re.search(r"source|code|repo", label, re.I):
                    source_urls.append(url)
            if pinfo.get("home_page"):
                candidates.append(("Homepage", pinfo["home_page"]))
            if pinfo.get("docs_url"):
                candidates.append(("Documentation", pinfo["docs_url"]))
        else:
            meta = npm_version_meta(http, info.name, info.latest or "latest")
            if meta.status == 200 and isinstance(meta.data, dict):
                if meta.data.get("homepage"):
                    candidates.append(("homepage", meta.data["homepage"]))
                repo = meta.data.get("repository")
                repo_url = repo.get("url") if isinstance(repo, dict) else repo
                if isinstance(repo_url, str):
                    source_urls.append(repo_url)
        picked = _pick_url(candidates)
        where = f"{'PyPI' if e == 'pypi' else 'npm'} metadata for {info.name}"
        if picked:
            label, url = picked
            host = _host(url)
            if host in CODE_HOSTS:
                return DocsTarget(urls=[_clean_repo_url(url)], how=f"{where}: {label} is a code host page, read directly")
            return DocsTarget(domains=[host.removeprefix("www.")], how=f"{where}: {label} {url}")
        for url in source_urls:
            clean = _clean_repo_url(url)
            if _host(clean) in CODE_HOSTS:
                return DocsTarget(urls=[clean], how=f"{where}: no docs link, reading the repository page")
        return DocsTarget(how=f"{where} has no documentation or homepage link")
    return None


def _clean_repo_url(url: str) -> str:
    url = url.strip()
    if url.startswith("git+"):
        url = url[4:]
    if url.startswith("git://"):
        url = "https://" + url[len("git://") :]
    url = url.split("#")[0]
    if url.endswith(".git"):
        url = url[:-4]
    return url


def resolve_docs(http: Http, claim: Claim) -> DocsTarget:
    """Standard library first, then curated names for the package or symbol,
    then registry metadata, then curated names for the free-text subject."""
    std = stdlib_domains(claim)
    if std:
        return DocsTarget(domains=std[0], how=std[1])
    symbol_head = re.split(r"[.:(/]", claim.symbol.strip("`"))[0] if claim.symbol else None
    curated = curated_domains([claim.package, symbol_head])
    if curated:
        return DocsTarget(domains=curated[0], how=curated[1])
    target = registry_target(http, claim)
    if target and target.found:
        return target
    curated = curated_domains([claim.subject])
    if curated:
        return DocsTarget(domains=curated[0], how=curated[1])
    return DocsTarget(how=(target.how if target else "no package, subject or symbol that maps to official documentation"))
