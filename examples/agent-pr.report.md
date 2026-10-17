## Hearsay: claims about the outside world

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

- GHSA-r5fr-rjxr-66jc is not used: OSV lists CVE-2021-23337 among its merged aliases, but GitHub wrote it for a CVE published at NVD on 2026-03-31, and CVE-2021-23337 was published on 2021-02-15.
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

<details><summary>Evidence shown to the jury</summary>

[1] <https://requests.readthedocs.io/en/master/user/advanced> (Advanced Usage > Request and Response Objects)

> Whenever a call is made to `requests.get()` and friends, you are doing two major things. First, you are constructing a `Request` object which will be sent off to a server to request or query some resource. Second, a `Response` object is generated once Requests gets a response back from the server. The `Response` object contains all of the information returned by the server and also contains the `Request` object you created originally. Here is a simple request to get some very important information from Wikipedia’s servers:

[2] <https://requests.readthedocs.io/en/master/user/advanced> (Advanced Usage > Streaming Requests)

> ``` import json import requests r = requests. get('https://httpbin.org/stream/20', stream = True) for line in r. iter_lines():# filter out keep-alive new lines if line: decoded_line = line. decode('utf-8') print(json. loads(decoded_line)) ```

[3] <https://requests.readthedocs.io/en/master/user/advanced> (Advanced Usage > HTTP Verbs)

> ``` >>> import requests>>> r = requests. get('https://api.github.com/repos/psf/requests/git/commits/a050faf084662f3a352dd1a941f2c7c9f886d4ad') ```

[4] <https://requests.readthedocs.io/en/master/user/advanced> (Advanced Usage > Client Side Certificates)

> If you specify a wrong path or an invalid cert, you’ll get a SSLError: ``` >>> requests. get('https://kennethreitz.org', cert ='/wrong_path/client.pem')SSLError: [Errno 336265225] _ssl.c:347: error:140B0009:SSL routines:SSL_CTX_use_PrivateKey_file:PEM lib ```

[5] <https://requests.readthedocs.io/en/master/user/advanced> (Advanced Usage > Body Content Workflow)

> ``` with requests. get('https://httpbin.org/get', stream = True) as r:# Do things with the response here. ```

[6] <https://requests.readthedocs.io/en/master/user/advanced> (Advanced Usage > SSL Cert Verification)

> ``` >>> requests. get('https://requestb.in')requests.exceptions.SSLError: hostname 'requestb.in' doesn't match either of '*.herokuapp.com', 'herokuapp.com' ```

</details>

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

<details><summary>Evidence shown to the jury</summary>

[1] <https://docs.python.org/3/whatsnew/3.12.html> (What's New In Python 3.12 > Deprecated)

> See [**PEP 688**](https://peps.python.org/pep-0688/#current-options) for more details. (Contributed by Shantanu Jain in [gh-91896](https://github.com/python/cpython/issues/91896).) * [`datetime`](../library/datetime.html#module-datetime "datetime: Basic date and time types."): [`datetime.datetime`](../library/datetime.html#datetime.datetime "datetime.datetime")’s [`utcnow()`](../library/datetime.html#datetime.datetime.utcnow "datetime.datetime.utcnow") and [`utcfromtimestamp()`](../library/datetime.html#datetime.datetime.utcfromtimestamp "datetime.datetime.utcfromtimestamp") are deprecated and will be removed in a future version.

[2] <https://docs.python.org/3/whatsnew/3.12.html> (What's New In Python 3.12 > Deprecated > Pending removal in future versions)

> + [`utcnow()`](../library/datetime.html#datetime.datetime.utcnow "datetime.datetime.utcnow"): use `datetime.datetime.now(tz=datetime.UTC)`. + [`utcfromtimestamp()`](../library/datetime.html#datetime.datetime.utcfromtimestamp "datetime.datetime.utcfromtimestamp"): use `datetime.datetime.fromtimestamp(timestamp,tz=datetime.UTC)`. * [`gettext`](../library/gettext.html#module-gettext "gettext: Multilingual internationalization services."): Plural value must be an integer. * [`importlib`](../library/importlib.html#module-importlib "importlib: The implementation of the import machinery."):

[3] <https://docs.python.org/3/library/datetime.html> (datetime - Basic date and time types > datetime objects > classmethod datetime.utcnow() [datetime.datetime.utcnow])

> Deprecated since version 3.12: Use [`datetime.now()`](#datetime.datetime.now "datetime.datetime.now") with [`UTC`](#datetime.UTC "datetime.UTC") instead.

[4] <https://docs.python.org/3/deprecations/index.html> (Deprecations > Pending removal in future versions)

> + [`utcnow()`](../library/datetime.html#datetime.datetime.utcnow "datetime.datetime.utcnow"): use `datetime.datetime.now(tz=datetime.UTC)`. + [`utcfromtimestamp()`](../library/datetime.html#datetime.datetime.utcfromtimestamp "datetime.datetime.utcfromtimestamp"): use `datetime.datetime.fromtimestamp(timestamp,tz=datetime.UTC)`. * [`gettext`](../library/gettext.html#module-gettext "gettext: Multilingual internationalization services."): Plural value must be an integer. * [`importlib`](../library/importlib.html#module-importlib "importlib: The implementation of the import machinery."):

[5] <https://docs.python.org/3/library/datetime.html> (datetime - Basic date and time types > datetime objects > classmethod datetime.utcnow() [datetime.datetime.utcnow])

> This is like [`now()`](#datetime.datetime.now "datetime.datetime.now"), but returns the current UTC date and time, as a naive [`datetime`](#datetime.datetime "datetime.datetime") object. An aware current UTC datetime can be obtained by calling `datetime.now(timezone.utc)`. See also `now()`.

[6] <https://docs.python.org/3/library/datetime.html> (datetime - Basic date and time types > datetime objects > classmethod datetime.utcnow() [datetime.datetime.utcnow])

> : Return the current UTC date and time, with [`tzinfo`](#datetime.datetime.tzinfo "datetime.datetime.tzinfo") `None`.

</details>

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

<details><summary>Evidence shown to the jury</summary>

[1] <https://docs.python.org/3/whatsnew/3.12.html> (What's New In Python 3.12 > Removed > distutils)

> * Remove the `distutils` package. It was deprecated in Python 3.10 by [**PEP 632**](https://peps.python.org/pep-0632/) “Deprecate distutils module”. For projects still using `distutils` and cannot be updated to something else, the `setuptools` project can be installed: it still provides `distutils`. (Contributed by Victor Stinner in [gh-92584](https://github.com/python/cpython/issues/92584).)

[2] <https://docs.python.org/3/library/distutils.html> (distutils - Building and installing Python modules)

> Deprecated since version 3.10, removed in version 3.12. This module is no longer part of the Python standard library. It was [removed in Python 3.12](../whatsnew/3.12.html#whatsnew312-removed-distutils) after being deprecated in Python 3.10. The removal was decided in [**PEP 632**](https://peps.python.org/pep-0632/), which has [migration advice](https://peps.python.org/pep-0632/#migration-advice).

[3] <https://docs.python.org/3/whatsnew/3.12.html> (What's New In Python 3.12 > C API Changes > Table of Contents)

> - [Pending removal in future versions](#pending-removal-in-future-versions) + [Removed](#removed) - [asynchat and asyncore](#asynchat-and-asyncore) - [configparser](#configparser) - [distutils](#distutils) - [ensurepip](#ensurepip) - [enum](#enum) - [ftplib](#ftplib) - [gzip](#gzip) - [hashlib](#hashlib) - [importlib](#importlib) - [imp](#imp) - [io](#io) - [locale](#locale) - [smtpd](#smtpd) - [sqlite3](#id2) - [ssl](#ssl) - [unittest](#id3) - [webbrowser](#webbrowser) - [xml.etree.ElementTree](#xml-etree-elementtree) - [zipimport](#zipimport) - [Others](#others) + [Porting to Python 3.12](#porting-to-python-3-12) - [Changes in the Python API](#changes-in-the-python-api) + [Build Changes](#build-changes) + [C API Changes](#c-api-changes) - [New Features](#id4)

[4] <https://docs.python.org/3/whatsnew/3.12.html> (What's New In Python 3.12 > Summary - Release highlights)

> Important deprecations, removals or restrictions: * [**PEP 623**](https://peps.python.org/pep-0623/): Remove `wstr` from Unicode objects in Python’s C API, reducing the size of every [`str`](../builtins/stdtypes.html#str "str") object by at least 8 bytes. * [**PEP 632**](https://peps.python.org/pep-0632/): Remove the `distutils` package. See [**the migration guide**](https://peps.python.org/pep-0632/#migration-advice) for advice replacing the APIs it provided. The third-party [Setuptools](https://setuptools.pypa.io/en/latest/deprecated/distutils-legacy.html) package continues to provide `distutils`, if you still require it in Python 3.12 and beyond. * [gh-95299](https://github.com/python/cpython/issues/95299): Do not pre-install `setuptools` in virtual environments created with [`venv`](../library/venv.html#module-venv "venv: Creation of virtual environments.").

[5] <https://docs.python.org/3/library/distutils.html> (distutils - Building and installing Python modules > Navigation)

> * [index](../genindex.html "General Index") * [modules](../py-modindex.html "Python Module Index") | * [next](imghdr.html "imghdr — Determine the type of an image") | * [previous](crypt.html "crypt — Function to check Unix passwords") | * [Python](https://www.python.org/) » * [3.15.0 Documentation](../index.html) » * [The Python standard library](index.html) » * [Removed Modules](removed.html) » * `distutils` — Building and installing Python modules * | * |

[6] <https://docs.python.org/3/library/distutils.html> (distutils - Building and installing Python modules)

> The last version of Python that provided the `distutils` module was [Python 3.11](https://docs.python.org/3.11/library/distutils.html).

</details>

### c11. UNVERIFIABLE: Stripe refunds accept an idempotency key.

Claim type `parameter_exists`, decided by **jury**.

Said in the input:
> - Stripe refunds accept an idempotency key, so retrying the refund call is safe.

2 of 2 judges answered supported but their quotes were not in the evidence or not about the claim's symbol, so the verdict is unverifiable.

| Judge | Model | Verdict | Stated | Quote found | Anchored |
|---|---|---|---|---|---|
| judge 1 | `qwen2.5:3b` | unverifiable | supported | no | - |
| judge 2 | `qwen2.5:7b` | unverifiable | supported | yes | no |

- judge 1: quote does not appear in the evidence; the supported verdict was discarded
- judge 2: anchoring: the quoted passage does not name Stripe.refunds; the supported verdict was discarded

Documentation searched: docs.stripe.com, stripe.com.

- Documentation source: curated map: 'stripe'.
- Anchoring: a quote counts only from a passage about Stripe.refunds.

<details><summary>Evidence shown to the jury</summary>

[1] <https://docs.stripe.com/changelog/2017-05-25/events-specify-request-id-idempotency-key> (The request field of the Events object now specifies both the request ID and idempotency keyBreaking changes > Impact)

> Expanding the request property on the `Event` object to include both the request ID and idempotency key lets you access more detailed information about the API request that triggered the event, particularly the idempotency key.

[2] <https://docs.stripe.com/idempotency> (Idempotent requests)

> A client generates an idempotency key, which is a unique key that the server uses to recognize subsequent retries of the same request. How you create unique keys is up to you, but we suggest using V4 UUIDs, or another random string with enough entropy to avoid collisions. Idempotency keys are up to 255 characters long. Avoid using sensitive data (for example, email addresses or personal identifiers) as idempotency keys.

[3] <https://docs.stripe.com/idempotency> (Idempotent requests)

> For API v1, Stripe saves the status code and body of the first request made with a given idempotency key after endpoint execution begins. Retries with the same key return the saved response, including `500` errors. With [API v2](/api-v2-overview#idempotency), retries don’t repeat successful operations. Stripe retries failed or partially failed work to completion when possible and returns an updated response. If a retry can’t succeed, Stripe returns an error explaining why.

[4] <https://docs.stripe.com/idempotency>

> [Payouts](https://docs.stripe.com/api/payouts) [Refunds](https://docs.stripe.com/api/refunds) [Confirmation Tokens](https://docs.stripe.com/api/confirmation_tokens) [Tokens](https://docs.stripe.com/api/tokens) [Ephemeral Keys](https://docs.stripe.com/api/ephemeral_keys) Payment Methods [Payment Methods](https://docs.stripe.com/api/payment_methods) [Payment Method Configurations](https://docs.stripe.com/api/payment_method_configurations)

[5] <https://docs.stripe.com/changelog/2017-05-25/events-specify-request-id-idempotency-key> (The request field of the Events object now specifies both the request ID and idempotency keyBreaking changes > What's new)

> Updates the `request` property on the `Event` object to be a hash containing the request ID and the idempotency key. Previously, `request` was just the ID.

[6] <https://docs.stripe.com/idempotency> (Idempotent requests)

> For API v1, all `POST` requests accept idempotency keys. Don’t send idempotency keys in `GET` and `DELETE` requests because it has no effect. These requests are idempotent by definition.

</details>

---
Claims extracted by `qwen2.5:7b` from 19 sentences.
Jury: `qwen2.5:3b`, `qwen2.5:7b`; adjudicator `qwen2.5:7b`.
Calls this run: 0 HTTP (18 cached), 1 Tavily (7 cached), 2 model (14 cached).
