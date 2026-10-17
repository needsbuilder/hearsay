"""Claims that a registry or advisory database answers. No model is involved.

Every result carries the URL it came from and, as its quote, the exact
field and value it relied on.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

from .http import Http
from .licenses import Match, compare_license
from .models import Claim, ClaimResult, ClaimType, DecisionPath, Verdict
from .registries import (
    REGISTRY_NAMES,
    PackageInfo,
    depsdev_version,
    entries_for_package,
    get_package,
    ids_of,
    match_version,
    npm_version_meta,
    osv_query_package,
    osv_record_url,
    osv_vuln,
    pypi_version_meta,
)
from .versions import (
    VersionError,
    affected_entry_covers,
    compare,
    normalize_ecosystem,
    parse_version,
    range_bounds,
)

SUPPORTED_ECOSYSTEMS = ("pypi", "npm")


def _result(
    claim: Claim,
    verdict: Verdict,
    path: DecisionPath,
    reason: str,
    *,
    url: str | None = None,
    quote: str | None = None,
    notes: list[str] | None = None,
) -> ClaimResult:
    return ClaimResult(
        claim=claim,
        verdict=verdict,
        path=path,
        source_url=url,
        quote=quote,
        reason=reason,
        notes=notes or [],
    )


def _unverifiable(claim: Claim, reason: str, notes: list[str] | None = None) -> ClaimResult:
    return _result(claim, Verdict.UNVERIFIABLE, DecisionPath.NONE, reason, notes=notes)


def apply_negation(result: ClaimResult) -> ClaimResult:
    """Deterministic checkers judge the positive form; flip it for negated claims."""
    if not result.claim.negated or result.verdict == Verdict.UNVERIFIABLE:
        return result
    flipped = Verdict.CONTRADICTED if result.verdict == Verdict.SUPPORTED else Verdict.SUPPORTED
    result.notes.append(
        f"The claim is negated, so the positive finding ({result.verdict.value}) becomes {flipped.value}."
    )
    result.verdict = flipped
    return result


# ------------------------------------------------------------ ecosystem


@dataclass
class Resolved:
    ecosystem: str | None
    info: PackageInfo | None
    infos: dict[str, PackageInfo]
    problem: str | None = None  # why no single package could be chosen
    note: str | None = None


def resolve_package(http: Http, claim: Claim) -> Resolved:
    """Find the package in the stated registry, or in PyPI and npm if none is stated."""
    assert claim.package
    eco = normalize_ecosystem(claim.ecosystem)
    if eco in SUPPORTED_ECOSYSTEMS:
        info = get_package(http, eco, claim.package)
        return Resolved(eco, info, {eco: info})
    if eco is not None:
        return Resolved(None, None, {}, problem=f"ecosystem {claim.ecosystem!r} is not supported yet (PyPI and npm only)")

    infos = {e: get_package(http, e, claim.package) for e in SUPPORTED_ECOSYSTEMS}
    existing = [e for e, i in infos.items() if i.exists]
    if claim.version and len(existing) > 1:
        with_version = [e for e in existing if match_version(infos[e], claim.version)]
        if len(with_version) == 1:
            existing = with_version
    if len(existing) == 1:
        e = existing[0]
        return Resolved(e, infos[e], infos, note=f"Ecosystem not stated; using {REGISTRY_NAMES[e]}, the only registry that matches.")
    if not existing:
        return Resolved(None, None, infos, problem="missing")
    return Resolved(
        None,
        None,
        infos,
        problem=f"ecosystem not stated and both PyPI and npm have a package named {claim.package!r}",
    )


def _not_found(claim: Claim, res: Resolved) -> ClaimResult:
    names = " or ".join(REGISTRY_NAMES[e] for e in res.infos)
    first = next(iter(res.infos.values()))
    quote = "; ".join(f"{REGISTRY_NAMES[e]}: HTTP {i.status} for {i.url}" for e, i in res.infos.items())
    return _result(
        claim,
        Verdict.CONTRADICTED,
        DecisionPath.REGISTRY,
        f"There is no package named {claim.package!r} on {names}.",
        url=first.url,
        quote=quote,
    )


# ------------------------------------------------------------ package / version


def check_package_exists(http: Http, claim: Claim) -> ClaimResult:
    res = resolve_package(http, claim)
    notes = [res.note] if res.note else []
    if res.problem == "missing" or (res.info is not None and not res.info.exists):
        return _not_found(claim, res)
    if res.info is None:
        # Ambiguous between registries still means the package exists.
        existing = [i for i in res.infos.values() if i.exists]
        if existing:
            i = existing[0]
            return _result(
                claim,
                Verdict.SUPPORTED,
                DecisionPath.REGISTRY,
                f"{claim.package!r} exists on " + " and ".join(REGISTRY_NAMES[x.ecosystem] for x in existing) + ".",
                url=i.url,
                quote=_name_quote(i),
                notes=notes,
            )
        return _unverifiable(claim, res.problem or "package lookup failed")
    info = res.info
    return _result(
        claim,
        Verdict.SUPPORTED,
        DecisionPath.REGISTRY,
        f"{info.name!r} exists on {REGISTRY_NAMES[info.ecosystem]} (latest version {info.latest}).",
        url=info.url,
        quote=_name_quote(info),
        notes=notes,
    )


def _name_quote(info: PackageInfo) -> str:
    if info.ecosystem == "pypi":
        return f'info.name: "{info.name}", info.version: "{info.latest}"'
    return f'name: "{info.name}", dist-tags.latest: "{info.latest}"'


def _versions_field(info: PackageInfo) -> str:
    return "releases" if info.ecosystem == "pypi" else "versions"


def _require_version(http: Http, claim: Claim) -> tuple[Resolved, list[str], ClaimResult | None]:
    """Resolve package and claimed version; return an early result if either is missing."""
    res = resolve_package(http, claim)
    notes = [res.note] if res.note else []
    if res.problem == "missing":
        return res, notes, _not_found(claim, res)
    if res.info is None:
        return res, notes, _unverifiable(claim, res.problem or "package lookup failed")
    info = res.info
    if not info.exists:
        return res, notes, _not_found(claim, res)
    assert claim.version
    try:
        parse_version(info.ecosystem, claim.version.strip().lstrip("vV="))
        valid = True
    except VersionError:
        valid = info.ecosystem == "npm" and claim.version.replace(".", "").isdigit()
    if not valid:
        return res, notes, _unverifiable(
            claim, f"{claim.version!r} is not a valid {REGISTRY_NAMES[info.ecosystem]} version string."
        )
    matches = match_version(info, claim.version)
    if not matches:
        field = _versions_field(info)
        return res, notes, _result(
            claim,
            Verdict.CONTRADICTED,
            DecisionPath.REGISTRY,
            f"{info.name} has no release {claim.version} on {REGISTRY_NAMES[info.ecosystem]} (latest is {info.latest}).",
            url=info.url,
            quote=f'{field} has no key "{claim.version}"; latest: "{info.latest}" ({len(info.versions)} releases listed)',
            notes=notes,
        )
    return res, notes, None


def check_version_exists(http: Http, claim: Claim) -> ClaimResult:
    res, notes, early = _require_version(http, claim)
    if early:
        return early
    info = res.info
    assert info and claim.version
    matches = match_version(info, claim.version)
    field = _versions_field(info)
    exact = matches[0] if len(matches) == 1 else None
    if exact and exact != claim.version:
        notes.append(f"{claim.version} and {exact} are the same version.")
    if not exact:
        notes.append(f"{claim.version} is a partial version; matching releases: {', '.join(matches[-5:])}.")
    for v in matches:
        if v in info.yanked:
            reason = info.yanked[v]
            notes.append(f"{v} is yanked on PyPI" + (f": {reason}" if reason else "."))
        if v in info.deprecated:
            notes.append(f"{v} is deprecated on npm: {info.deprecated[v]}")
    shown = matches[-1]
    return _result(
        claim,
        Verdict.SUPPORTED,
        DecisionPath.REGISTRY,
        f"{info.name} {shown} is published on {REGISTRY_NAMES[info.ecosystem]}.",
        url=info.url,
        quote=f'{field}["{shown}"] is present',
        notes=notes,
    )


# ------------------------------------------------------------ vulnerabilities


def _events_text(rng: dict) -> str:
    if "events" in rng:
        return json.dumps(rng["events"])
    return json.dumps(rng)


def _rank_records(records: list[dict], wanted: str) -> list[dict]:
    """Order records for citation: the record with the requested id, then GitHub's
    advisory, then ecosystem databases, earliest published first."""

    def rank(r: dict) -> tuple:
        rid = r.get("id", "")
        source = 0 if rid.startswith("GHSA-") else 1 if rid.startswith(("PYSEC-", "MAL-")) else 2
        return (0 if rid.upper() == wanted else 1, source, r.get("published") or "9999", rid)

    return sorted(records, key=rank)


# GitHub's records carry database_specific.nvd_published_at: when NVD published
# the CVE that GitHub attached to the advisory. A GHSA whose date is further
# than this from the claimed CVE's publication was written for another CVE.
NVD_DATE_TOLERANCE_DAYS = 7


def _day(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _other_cve(record: dict, wanted: str, cve_record: dict | None) -> str | None:
    """Why a record linked to `wanted` only by OSV's merged aliases is about another CVE."""
    rid = record.get("id", "")
    nvd = _day((record.get("database_specific") or {}).get("nvd_published_at"))
    cve_day = _day((cve_record or {}).get("published"))
    if not rid.startswith("GHSA-") or nvd is None or cve_day is None:
        return None
    if abs((nvd - cve_day).days) <= NVD_DATE_TOLERANCE_DAYS:
        return None
    return (
        f"{rid} is not used: OSV lists {wanted} among its merged aliases, but GitHub wrote it for a CVE "
        f"published at NVD on {nvd}, and {wanted} was published on {cve_day}."
    )


def matching_records(http: Http, linked: list[dict], wanted: str) -> tuple[list[dict], list[str]]:
    """The records that describe the claimed vulnerability, and notes on the ones left out.

    OSV merges aliases transitively, so a record can list ids it was never
    about (lodash's 2021 advisory lists the 2026 CVE of a later incomplete
    fix). Matching means:

    1. a record whose own id is the claimed id is the claimed advisory, and
       only such records are used;
    2. for a claimed CVE, every record that lists it, except a GitHub advisory
       whose nvd_published_at (the publication of the CVE GitHub attached)
       is more than NVD_DATE_TOLERANCE_DAYS from the claimed CVE's own
       publication date in OSV;
    3. records without that evidence (PYSEC and others) are kept, so a
       merged record of that kind can still cause a disagreement, which
       makes the verdict unverifiable rather than wrong.
    """
    own = [r for r in linked if r.get("id", "").upper() == wanted]
    if own:
        others = sorted(r["id"] for r in linked if r not in own)
        return own, ([f"Records that list {wanted} only as an alias were not used: {', '.join(others)}."] if others else [])
    if not wanted.startswith("CVE-"):
        return linked, []
    cve_record = osv_vuln(http, wanted)
    keep, notes = [], []
    for r in linked:
        why = _other_cve(r, wanted, cve_record)
        if why:
            notes.append(why)
        else:
            keep.append(r)
    return (keep or linked), notes


def _evaluate_record(eco: str, version: str, record: dict, package: str):
    """(affected, decisive range) for one record, or None if it has no usable ranges."""
    seen_any = False
    not_affected: list[dict] = []
    for entry in entries_for_package(record, eco, package):
        check = affected_entry_covers(eco, version, entry)
        if check is None:
            continue
        seen_any = True
        if check.affected:
            return True, check.used
        not_affected.extend(check.used)
    if not seen_any:
        return None
    return False, not_affected


def check_vulnerability(http: Http, claim: Claim) -> ClaimResult:
    res, notes, early = _require_version(http, claim)
    if early:
        return early
    info = res.info
    assert info and claim.version
    eco = info.ecosystem
    versions = match_version(info, claim.version)
    if len(versions) != 1:
        return _unverifiable(
            claim, f"{claim.version} matches several releases ({', '.join(versions[-5:])}); name one exact version.", notes
        )
    version = versions[0]

    if not claim.vulnerability_id:
        if claim.type != ClaimType.AFFECTED_BY_VULNERABILITY:
            return _unverifiable(claim, "No vulnerability id given.", notes)
        url, vulns = osv_query_package(http, eco, info.name, version)
        ids = sorted(v.get("id", "") for v in vulns)
        if ids:
            return _result(
                claim,
                Verdict.SUPPORTED,
                DecisionPath.ADVISORY,
                f"OSV lists {len(ids)} advisories affecting {info.name} {version}.",
                url=url,
                quote=f"vulns[].id: {', '.join(ids[:10])}" + (" ..." if len(ids) > 10 else ""),
                notes=notes,
            )
        return _result(
            claim,
            Verdict.CONTRADICTED,
            DecisionPath.ADVISORY,
            f"OSV lists no advisories affecting {info.name} {version}.",
            url=url,
            quote="vulns: [] (no OSV records for this package version)",
            notes=notes + ["Absence from OSV means no published advisory, not proof that no flaw exists."],
        )

    wanted = claim.vulnerability_id.strip().upper()
    query_url, records = osv_query_package(http, eco, info.name)
    matched = [r for r in records if wanted in ids_of(r)]
    if not matched:
        record = osv_vuln(http, wanted)
        if record is None:
            return _unverifiable(claim, f"OSV has no record {wanted}.", notes)
        listed = sorted(
            {
                f"{(e.get('package') or {}).get('ecosystem')}/{(e.get('package') or {}).get('name')}"
                for e in record.get("affected") or []
                if e.get("package")
            }
        )
        where = f" It lists: {', '.join(listed)}." if listed else ""
        return _unverifiable(
            claim,
            f"OSV record {wanted} is not linked to {REGISTRY_NAMES[eco]} package {info.name}.{where}",
            notes,
        )

    matching, excluded = matching_records(http, matched, wanted)
    notes.extend(excluded)
    ranked = _rank_records(matching, wanted)
    evaluated = []
    try:
        for record in ranked:
            outcome = _evaluate_record(eco, version, record, info.name)
            if outcome is not None:
                evaluated.append((record, outcome))
    except VersionError as exc:
        return _unverifiable(claim, f"Could not compare versions: {exc}", notes)
    if not evaluated:
        return _unverifiable(claim, f"OSV record {ranked[0]['id']} has no version ranges for {info.name}.", notes)

    if len({affected for _, (affected, _) in evaluated}) > 1:
        # Records that describe this vulnerability disagree: do not pick one.
        said = [
            f"{r['id']} says {'affected' if a else 'not affected'} "
            f"({'; '.join(_events_text(x) for x in ranges)})"
            for r, (a, ranges) in evaluated
        ]
        return _result(
            claim, Verdict.UNVERIFIABLE, DecisionPath.ADVISORY,
            f"The OSV records for {wanted} disagree about {info.name} {version}: {'; '.join(said)}.",
            url=osv_record_url(evaluated[0][0]["id"]),
            quote="; ".join(f"{r['id']}: " + "; ".join(_events_text(x) for x in ranges) for r, (_, ranges) in evaluated),
            notes=notes,
        )

    primary, (primary_affected, primary_ranges) = evaluated[0]
    agreeing = [r["id"] for r, _ in evaluated[1:]]
    if agreeing:
        notes.append(f"Also consistent: {', '.join(agreeing)}.")

    affected_hit = (primary, primary_ranges[0]) if primary_affected else None
    not_affected: list[dict] = [] if primary_affected else primary_ranges

    if affected_hit:
        record, rng = affected_hit
        url = osv_record_url(record["id"])
        quote = f"affected[{info.name}].ranges.events: {_events_text(rng)}"
        if claim.type == ClaimType.AFFECTED_BY_VULNERABILITY:
            return _result(
                claim, Verdict.SUPPORTED, DecisionPath.ADVISORY,
                f"{info.name} {version} is inside the affected range of {record['id']}.",
                url=url, quote=quote, notes=notes,
            )
        fixed = range_bounds(eco, rng)["fixed"] if "events" in rng else []
        hint = f" The fix is in {', '.join(fixed)}." if fixed else ""
        return _result(
            claim, Verdict.CONTRADICTED, DecisionPath.ADVISORY,
            f"{info.name} {version} is still affected by {wanted} ({record['id']}).{hint}",
            url=url, quote=quote, notes=notes,
        )

    # Not affected.
    url = osv_record_url(primary["id"])
    ranges_with_events = [r for r in not_affected if "events" in r]
    quote = f"affected[{info.name}].ranges.events: " + "; ".join(_events_text(r) for r in ranges_with_events or not_affected)
    if claim.type == ClaimType.AFFECTED_BY_VULNERABILITY:
        return _result(
            claim, Verdict.CONTRADICTED, DecisionPath.ADVISORY,
            f"{info.name} {version} is outside every affected range of {wanted}.",
            url=url, quote=quote, notes=notes,
        )

    # "version fixes vuln": the version must be at or after a fix, not merely
    # older than the bug.
    fixed_at_or_below = []
    last_affected_below = []
    introduced = []
    for rng in ranges_with_events:
        bounds = range_bounds(eco, rng)
        introduced += [v for v in bounds["introduced"] if v != "0"]
        try:
            fixed_at_or_below += [f for f in bounds["fixed"] if compare(eco, f, version) <= 0]
            last_affected_below += [la for la in bounds["last_affected"] if compare(eco, la, version) < 0]
        except VersionError as exc:
            return _unverifiable(claim, f"Could not compare versions: {exc}", notes)
    if fixed_at_or_below:
        first_fix = max(fixed_at_or_below, key=lambda f: parse_version(eco, f))
        exact = " (this is the first fixed release)" if compare(eco, first_fix, version) == 0 else ""
        return _result(
            claim, Verdict.SUPPORTED, DecisionPath.ADVISORY,
            f"{wanted} is fixed in {first_fix}; {info.name} {version} is not affected{exact}.",
            url=url, quote=quote, notes=notes,
        )
    if last_affected_below:
        return _result(
            claim, Verdict.SUPPORTED, DecisionPath.ADVISORY,
            f"The last affected release is {max(last_affected_below, key=lambda v: parse_version(eco, v))}; "
            f"{info.name} {version} is after it.",
            url=url, quote=quote, notes=notes,
        )
    if introduced:
        return _result(
            claim, Verdict.CONTRADICTED, DecisionPath.ADVISORY,
            f"{info.name} {version} predates {wanted} (introduced in {min(introduced, key=lambda v: parse_version(eco, v))}), "
            "so it was never affected and does not contain the fix.",
            url=url, quote=quote, notes=notes,
        )
    return _unverifiable(claim, f"OSV ranges for {wanted} do not say where it was fixed.", notes)


# ------------------------------------------------------------ licence


def check_license(http: Http, claim: Claim) -> ClaimResult:
    assert claim.license
    res = resolve_package(http, claim)
    notes = [res.note] if res.note else []
    if res.problem == "missing":
        return _not_found(claim, res)
    if res.info is None:
        return _unverifiable(claim, res.problem or "package lookup failed")
    info = res.info
    if not info.exists:
        return _not_found(claim, res)
    if claim.version:
        matches = match_version(info, claim.version)
        if not matches:
            return _result(
                claim, Verdict.CONTRADICTED, DecisionPath.REGISTRY,
                f"{info.name} has no release {claim.version}.",
                url=info.url, quote=f'{_versions_field(info)} has no key "{claim.version}"', notes=notes,
            )
        version = matches[-1]
    else:
        version = info.latest or ""
        notes.append(f"No version in the claim; checked the latest release, {version}.")

    # (url, field description, value) in order of preference
    candidates: list[tuple[str, str, str]] = []
    dd = depsdev_version(http, info.ecosystem, info.name, version)
    if dd.status == 200 and isinstance(dd.data, dict):
        for lic in dd.data.get("licenses") or []:
            if lic and lic.lower() != "non-standard":
                candidates.append((dd.url, "licenses", lic))
    if info.ecosystem == "pypi":
        meta = pypi_version_meta(http, info.name, version)
        if meta.status == 200 and isinstance(meta.data, dict):
            pinfo = meta.data.get("info") or {}
            if pinfo.get("license_expression"):
                candidates.append((meta.url, "info.license_expression", pinfo["license_expression"]))
            if pinfo.get("license") and pinfo["license"].strip().upper() not in ("UNKNOWN", ""):
                candidates.append((meta.url, "info.license", pinfo["license"]))
            for c in pinfo.get("classifiers") or []:
                if c.startswith("License ::"):
                    candidates.append((meta.url, "info.classifiers", c))
    else:
        meta = npm_version_meta(http, info.name, version)
        if meta.status == 200 and isinstance(meta.data, dict):
            lic = meta.data.get("license")
            if isinstance(lic, dict):
                lic = lic.get("type")
            if isinstance(lic, str) and lic:
                candidates.append((meta.url, "license", lic))
            for item in meta.data.get("licenses") or []:
                if isinstance(item, dict) and item.get("type"):
                    candidates.append((meta.url, "licenses[].type", item["type"]))

    if not candidates:
        return _unverifiable(claim, f"{info.name} {version} has no licence metadata on {REGISTRY_NAMES[info.ecosystem]} or deps.dev.", notes)

    seen_unknown = []
    for url, field, value in candidates:
        m = compare_license(claim.license, value)
        shown = value if len(value) <= 160 else value[:157] + "..."
        quote = f'{field}: "{shown}"'
        if m == Match.MATCH:
            return _result(
                claim, Verdict.SUPPORTED, DecisionPath.REGISTRY,
                f"{info.name} {version} is licensed {value if len(value) <= 60 else claim.license}.",
                url=url, quote=quote, notes=notes,
            )
        if m == Match.MISMATCH:
            return _result(
                claim, Verdict.CONTRADICTED, DecisionPath.REGISTRY,
                f"{info.name} {version} declares {shown}, not {claim.license}.",
                url=url, quote=quote, notes=notes,
            )
        if m == Match.PARTIAL:
            return _result(
                claim, Verdict.UNVERIFIABLE, DecisionPath.REGISTRY,
                f"The licence is {value}; {claim.license} is only one part of it.",
                url=url, quote=quote, notes=notes,
            )
        seen_unknown.append(quote)
    return _unverifiable(
        claim,
        f"Licence metadata for {info.name} {version} is too vague to compare with {claim.license}: {'; '.join(seen_unknown[:3])}.",
        notes,
    )


# ------------------------------------------------------------ npm deprecation


def check_npm_deprecated(http: Http, claim: Claim) -> ClaimResult | None:
    """Package-level deprecation on npm. None means the registry does not settle it."""
    assert claim.package
    info = get_package(http, "npm", claim.package)
    if not info.exists:
        return _not_found(claim, Resolved("npm", info, {"npm": info}))
    version = info.latest
    if claim.version:
        matches = match_version(info, claim.version)
        if matches:
            version = matches[-1]
    if version and version in info.deprecated:
        return _result(
            claim, Verdict.SUPPORTED, DecisionPath.REGISTRY,
            f"npm marks {info.name} {version} as deprecated.",
            url=info.url, quote=f'versions["{version}"].deprecated: "{info.deprecated[version]}"',
        )
    return None
