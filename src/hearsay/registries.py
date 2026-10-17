"""PyPI, npm, deps.dev and OSV lookups. No models here, only registry data."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

from packaging.version import InvalidVersion, Version

from .http import Http, HttpResult
from .versions import SemVer, VersionError

PYPI = "https://pypi.org/pypi"
NPM = "https://registry.npmjs.org"
NPM_ABBREVIATED = {"Accept": "application/vnd.npm.install-v1+json"}
DEPSDEV = "https://api.deps.dev/v3"
OSV = "https://api.osv.dev/v1"

REGISTRY_NAMES = {"pypi": "PyPI", "npm": "npm"}
OSV_ECOSYSTEMS = {"pypi": "PyPI", "npm": "npm"}


def pypi_normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def npm_path(name: str) -> str:
    # scoped packages keep the @ but encode the slash
    return quote(name, safe="@")


@dataclass
class PackageInfo:
    ecosystem: str
    name: str
    exists: bool
    url: str
    status: int
    versions: list[str] = field(default_factory=list)
    latest: str | None = None
    yanked: dict[str, str | None] = field(default_factory=dict)
    deprecated: dict[str, str] = field(default_factory=dict)
    raw: Any = None


def pypi_package(http: Http, name: str) -> PackageInfo:
    url = f"{PYPI}/{quote(name)}/json"
    res = http.get(url)
    if res.status != 200 or not isinstance(res.data, dict):
        return PackageInfo("pypi", name, False, url, res.status)
    data = res.data
    releases = data.get("releases") or {}
    yanked: dict[str, str | None] = {}
    for ver, files in releases.items():
        if files and all(f.get("yanked") for f in files):
            yanked[ver] = files[0].get("yanked_reason")
    return PackageInfo(
        "pypi",
        data["info"]["name"],
        True,
        url,
        res.status,
        versions=list(releases.keys()),
        latest=data["info"].get("version"),
        yanked=yanked,
        raw=data,
    )


def npm_package(http: Http, name: str) -> PackageInfo:
    url = f"{NPM}/{npm_path(name)}"
    res = http.get(url, headers=NPM_ABBREVIATED)
    if res.status != 200 or not isinstance(res.data, dict) or "versions" not in res.data:
        return PackageInfo("npm", name, False, url, res.status)
    data = res.data
    versions = data.get("versions") or {}
    deprecated = {v: meta["deprecated"] for v, meta in versions.items() if meta.get("deprecated")}
    return PackageInfo(
        "npm",
        data.get("name", name),
        True,
        url,
        res.status,
        versions=list(versions.keys()),
        latest=(data.get("dist-tags") or {}).get("latest"),
        deprecated=deprecated,
        raw=data,
    )


def get_package(http: Http, ecosystem: str, name: str) -> PackageInfo:
    if ecosystem == "pypi":
        return pypi_package(http, name)
    if ecosystem == "npm":
        return npm_package(http, name)
    raise ValueError(f"unsupported ecosystem {ecosystem}")


def match_version(info: PackageInfo, version: str) -> list[str]:
    """Published versions matching a claimed version.

    PyPI: PEP 440 equality, so "2.31" matches "2.31.0".
    npm: exact SemVer equality; a partial version such as "4.17" matches
    every 4.17.x release (that is what npm itself resolves it to).
    """
    wanted = version.strip().lstrip("vV=")
    if info.ecosystem == "pypi":
        try:
            target = Version(wanted)
        except InvalidVersion:
            return [v for v in info.versions if v == wanted]
        out = []
        for v in info.versions:
            try:
                if Version(v) == target:
                    out.append(v)
            except InvalidVersion:
                continue
        return out
    if info.ecosystem == "npm":
        if re.fullmatch(r"\d+(\.\d+)?", wanted):
            prefix = wanted + "."
            return [v for v in info.versions if v.startswith(prefix) and "-" not in v]
        try:
            target_sv = SemVer.parse(wanted)
        except VersionError:
            return [v for v in info.versions if v == wanted]
        out = []
        for v in info.versions:
            try:
                if SemVer.parse(v) == target_sv:
                    out.append(v)
            except VersionError:
                continue
        return out
    return []


def pypi_version_meta(http: Http, name: str, version: str) -> HttpResult:
    return http.get(f"{PYPI}/{quote(name)}/{quote(version)}/json")


def npm_version_meta(http: Http, name: str, version: str) -> HttpResult:
    return http.get(f"{NPM}/{npm_path(name)}/{quote(version)}")


def depsdev_version(http: Http, ecosystem: str, name: str, version: str) -> HttpResult:
    system = {"pypi": "pypi", "npm": "npm"}[ecosystem]
    url = f"{DEPSDEV}/systems/{system}/packages/{quote(name, safe='')}/versions/{quote(version, safe='')}"
    return http.get(url)


# ---------------------------------------------------------------- OSV


def osv_query_package(http: Http, ecosystem: str, name: str, version: str | None = None) -> tuple[str, list[dict]]:
    """All OSV records for a package (or for one version of it). Follows pagination."""
    url = f"{OSV}/query"
    body: dict[str, Any] = {"package": {"name": name, "ecosystem": OSV_ECOSYSTEMS[ecosystem]}}
    if version:
        body["version"] = version
    vulns: list[dict] = []
    for _ in range(10):
        res = http.post(url, body)
        if res.status != 200 or not isinstance(res.data, dict):
            break
        vulns.extend(res.data.get("vulns") or [])
        token = res.data.get("next_page_token")
        if not token:
            break
        body = {**body, "page_token": token}
    return url, vulns


def osv_record_url(record_id: str) -> str:
    return f"{OSV}/vulns/{record_id}"


def ids_of(record: dict) -> set[str]:
    return {record.get("id", "").upper(), *(a.upper() for a in record.get("aliases") or [])}


def osv_vuln(http: Http, vuln_id: str) -> dict | None:
    res = http.get(osv_record_url(vuln_id))
    return res.data if res.status == 200 and isinstance(res.data, dict) else None


def same_package(ecosystem: str, a: str, b: str) -> bool:
    if ecosystem == "pypi":
        return pypi_normalize(a) == pypi_normalize(b)
    return a == b


def entries_for_package(record: dict, ecosystem: str, name: str) -> list[dict]:
    osv_eco = OSV_ECOSYSTEMS[ecosystem]
    out = []
    for entry in record.get("affected") or []:
        pkg = entry.get("package") or {}
        if pkg.get("ecosystem") == osv_eco and same_package(ecosystem, pkg.get("name", ""), name):
            out.append(entry)
    return out
