<!-- hearsay-report -->
## Hearsay: claims about the outside world

Input: example-org/payments-service#42: Pin patched dependencies and make refunds retry-safe <https://github.com/example-org/payments-service/pull/42>

**11 claims checked: 4 supported, 5 contradicted, 2 unverifiable.**

| # | Verdict | Claim | Decided by | Source |
|---|---|---|---|---|
| c1 | **SUPPORTED** | requests 2.31.0 fixes CVE-2023-32681. | advisory | <https://api.osv.dev/v1/vulns/GHSA-j8r2-6x86-q33q> |
| c2 | **CONTRADICTED** | urllib3 1.26.5 fixes CVE-2023-43804. | advisory | <https://api.osv.dev/v1/vulns/GHSA-v845-jxx5-vc9f> |
| c3 | **SUPPORTED** | lodash 4.17.21 is no longer affected by CVE-2021-23337. | advisory | <https://api.osv.dev/v1/vulns/GHSA-35jh-r3h4-6jhm> |
| c4 | **CONTRADICTED** | fastapi 0.200.0 is added. | registry | <https://pypi.org/pypi/fastapi/json> |
| c5 | **CONTRADICTED** | pydantic-settings-extra is added. | registry | <https://pypi.org/pypi/pydantic-settings-extra/json> |
| c6 | **SUPPORTED** | httpx is BSD-3-Clause licensed. | registry | <https://api.deps.dev/v3/systems/pypi/packages/httpx/versions/0.28.1> |
| c7 | **CONTRADICTED** | requests is MIT licensed. | registry | <https://api.deps.dev/v3/systems/pypi/packages/requests/versions/2.34.2> |
| c8 | **UNVERIFIABLE** | requests.get accepts a max_retries parameter. | jury | - |
| c9 | **SUPPORTED** | datetime.utcnow() is deprecated since Python 3.12. | adjudicator | <https://docs.python.org/3/library/datetime.html> |
| c10 | **CONTRADICTED** | distutils was removed in Python 3.10. | adjudicator | <https://docs.python.org/3/library/distutils.html> |
| c11 | **UNVERIFIABLE** | Stripe refunds accept an idempotency key. | jury | - |

### c1. SUPPORTED: requests 2.31.0 fixes CVE-2023-32681.

Claim type `fixes_vulnerability`, decided by **advisory**.

Said in the input:
> - Bumped `requests` to 2.31.0, which fixes CVE-2023-32681 (Proxy-Authorization header leak on redirects).

CVE-2023-32681 is fixed in 2.31.0; requests 2.31.0 is not affected (this is the first fixed release).

Source: <https://api.osv.dev/v1/vulns/GHSA-j8r2-6x86-q33q>

> affected[requests].ranges.events: [{"introduced": "2.3.0"}, {"fixed": "2.31.0"}]

- Also consistent: PYSEC-2023-74.

### c2. CONTRADICTED: urllib3 1.26.5 fixes CVE-2023-43804.

Claim type `fixes_vulnerability`, decided by **advisory**.

Said in the input:
> - Upgrading `urllib3` to 1.26.5 fixes CVE-2023-43804, so we can keep the 1.26 line.

urllib3 1.26.5 is still affected by CVE-2023-43804 (GHSA-v845-jxx5-vc9f). The fix is in 1.26.17.

Source: <https://api.osv.dev/v1/vulns/GHSA-v845-jxx5-vc9f>

> affected[urllib3].ranges.events: [{"introduced": "0"}, {"fixed": "1.26.17"}]

- Also consistent: PYSEC-2023-192.

### c3. SUPPORTED: lodash 4.17.21 is no longer affected by CVE-2021-23337.

Claim type `affected_by_vulnerability`, decided by **advisory**.

Said in the input:
> - On the frontend, `lodash` 4.17.21 is no longer affected by CVE-2021-23337.

lodash 4.17.21 is outside every affected range of CVE-2021-23337.

Source: <https://api.osv.dev/v1/vulns/GHSA-35jh-r3h4-6jhm>

> affected[lodash].ranges.events: [{"introduced": "0"}, {"fixed": "4.17.21"}]

- OSV also links GHSA-r5fr-rjxr-66jc (published 2026-04-01, aliases CVE-2021-23337, CVE-2026-4800, GHSA-35jh-r3h4-6jhm) to CVE-2021-23337, and by that record lodash 4.17.21 is affected: [{"introduced": "4.0.0"}, {"fixed": "4.18.0"}]. Hearsay follows GHSA-35jh-r3h4-6jhm, the record for this id or the earliest one.
- The claim is negated, so the positive finding (contradicted) becomes supported.

### c4. CONTRADICTED: fastapi 0.200.0 is added.

Claim type `version_exists`, decided by **registry**.

Said in the input:
> - Added `fastapi==0.200.0` for the new health endpoint.

fastapi has no release 0.200.0 on PyPI (latest is 0.143.3).

Source: <https://pypi.org/pypi/fastapi/json>

> releases has no key "0.200.0"; latest: "0.143.3" (326 releases listed)

### c5. CONTRADICTED: pydantic-settings-extra is added.

Claim type `package_exists`, decided by **registry**.

Said in the input:
> - Added `pydantic-settings-extra` to parse the nested env settings.

There is no package named 'pydantic-settings-extra' on PyPI.

Source: <https://pypi.org/pypi/pydantic-settings-extra/json>

> PyPI: HTTP 404 for https://pypi.org/pypi/pydantic-settings-extra/json

### c6. SUPPORTED: httpx is BSD-3-Clause licensed.

Claim type `license_is`, decided by **registry**.

Said in the input:
> - `httpx` is BSD-3-Clause licensed, so it passes our licence policy.

httpx 0.28.1 is licensed BSD-3-Clause.

Source: <https://api.deps.dev/v3/systems/pypi/packages/httpx/versions/0.28.1>

> licenses: "BSD-3-Clause"

- No version in the claim; checked the latest release, 0.28.1.

### c7. CONTRADICTED: requests is MIT licensed.

Claim type `license_is`, decided by **registry**.

Said in the input:
> - The `requests` library is MIT licensed.

requests 2.34.2 declares Apache-2.0, not MIT.

Source: <https://api.deps.dev/v3/systems/pypi/packages/requests/versions/2.34.2>

> licenses: "Apache-2.0"

- No version in the claim; checked the latest release, 2.34.2.

### c8. UNVERIFIABLE: requests.get accepts a max_retries parameter.

Claim type `parameter_exists`, decided by **jury**.

Said in the input:
> - `requests.get` also accepts a `max_retries` parameter, so the custom adapter is gone.

1 of 2 judges answered contradicted but their quotes were not in the evidence, so the verdict is unverifiable.

| Judge | Model | Verdict | Stated | Quote found | Anchored |
|---|---|---|---|---|---|
| judge 1 | `qwen2.5:3b` | unverifiable | unverifiable | no | - |
| judge 2 | `qwen2.5:7b` | unverifiable | contradicted | no | - |

- judge 2: no quote; the contradicted verdict was discarded

Documentation searched: requests.readthedocs.io.

- Documentation source: PyPI metadata for requests: Documentation https://requests.readthedocs.io.
- Extract failed for https://requests.readthedocs.io/_/downloads/en/stable/pdf; used the search snippet.
- Extract failed for https://requests.readthedocs.io/en/latest/api; used the search snippet.
- Anchoring: a quote counts only from a passage about requests.get.

### c9. SUPPORTED: datetime.utcnow() is deprecated since Python 3.12.

Claim type `deprecated`, decided by **adjudicator**.

Said in the input:
> - Replaced `datetime.utcnow()`, which is deprecated since Python 3.12.

Judges disagreed (qwen2.5:3b: supported, qwen2.5:7b: unverifiable); the adjudicator decided supported. Excerpt [3] explicitly states that `datetime.utcnow()` is deprecated since version 3.12, matching the claim's details of being deprecated since Python 3.12 and specifying the function name.

Source: <https://docs.python.org/3/library/datetime.html>

> Deprecated since version 3.12: Use `datetime.now()` with `UTC` instead.

| Judge | Model | Verdict | Stated | Quote found | Anchored |
|---|---|---|---|---|---|
| judge 1 | `qwen2.5:3b` | supported | supported | yes | yes |
| judge 2 | `qwen2.5:7b` | unverifiable | supported | no | - |
| adjudicator | `qwen2.5:7b` | supported | supported | yes | yes |

- judge 2: quote does not appear in the evidence; the supported verdict was discarded

Documentation searched: docs.python.org.

- Documentation source: Python standard library module 'datetime'.
- Anchoring: a quote counts only from a passage about datetime.utcnow.

### c10. CONTRADICTED: distutils was removed in Python 3.10.

Claim type `deprecated`, decided by **adjudicator**.

Said in the input:
> - The `distutils` module was removed in Python 3.10, so `setup.py` now imports setuptools.

Judges disagreed (qwen2.5:3b: supported, qwen2.5:7b: contradicted); the adjudicator decided contradicted. The claim states that distutils was removed in Python 3.10, but the excerpts show it was actually deprecated in Python 3.10 and removed in Python 3.12. This contradicts the claim.

Source: <https://docs.python.org/3/library/distutils.html>

> Deprecated since version 3.10, removed in version 3.12.

| Judge | Model | Verdict | Stated | Quote found | Anchored |
|---|---|---|---|---|---|
| judge 1 | `qwen2.5:3b` | supported | supported | yes | yes |
| judge 2 | `qwen2.5:7b` | contradicted | contradicted | yes | yes |
| adjudicator | `qwen2.5:7b` | contradicted | contradicted | yes | yes |

Documentation searched: docs.python.org.

- Documentation source: Python standard library module 'distutils'.
- Anchoring: a quote counts only from a passage about distutils.

### c11. UNVERIFIABLE: Stripe refunds accept an idempotency key.

Claim type `parameter_exists`, decided by **jury**.

Said in the input:
> - Stripe refunds accept an idempotency key, so retrying the refund call is safe.

1 of 2 judges answered supported but their quotes were not in the evidence, so the verdict is unverifiable.

| Judge | Model | Verdict | Stated | Quote found | Anchored |
|---|---|---|---|---|---|
| judge 1 | `qwen2.5:3b` | unverifiable | unverifiable | no | - |
| judge 2 | `qwen2.5:7b` | unverifiable | supported | no | - |

- judge 2: quote is shorter than 15 characters; the supported verdict was discarded

Documentation searched: docs.stripe.com, stripe.com.

- Documentation source: curated map: 'stripe'.
- Anchoring: a quote counts only from a passage about Stripe.refunds.

---
Claims extracted by `qwen2.5:7b` from 19 sentences.
Jury: `qwen2.5:3b`, `qwen2.5:7b`; adjudicator `qwen2.5:7b`.
Calls this run: 0 HTTP (15 cached), 0 Tavily (8 cached), 2 model (14 cached).

Checked the pull request description.

[Workflow run](https://github.com/example-org/payments-service/actions/runs/123)
