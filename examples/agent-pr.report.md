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
| c8 | **UNVERIFIABLE** | requests.get accepts a max_retries parameter. | adjudicator | - |
| c9 | **SUPPORTED** | datetime.utcnow() is deprecated since Python 3.12. | jury | <https://docs.python.org/3/library/datetime.html> |
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

Claim type `parameter_exists`, decided by **adjudicator**.

Said in the input:
> - `requests.get` also accepts a `max_retries` parameter, so the custom adapter is gone.

Judges disagreed (qwen2.5:3b: unverifiable, qwen2.5:7b: contradicted); the adjudicator decided unverifiable. The claim states that `requests.get` accepts a `max_retries` parameter, but none of the excerpts mention such a parameter directly for `requests.get`. However, excerpt [5] mentions `max_retries`, which is relevant to the `get` method context.

| Judge | Model | Verdict | Stated | Quote found |
|---|---|---|---|---|
| judge 1 | `qwen2.5:3b` | unverifiable | unverifiable | no |
| judge 2 | `qwen2.5:7b` | contradicted | contradicted | yes |
| adjudicator | `qwen2.5:7b` | unverifiable | unverifiable | yes |

Documentation searched: requests.readthedocs.io.

- Documentation source: PyPI metadata for requests: Documentation https://requests.readthedocs.io.
- Extract failed for https://requests.readthedocs.io/_/downloads/en/stable/pdf; used the search snippet.
- Extract failed for https://requests.readthedocs.io/en/latest/api; used the search snippet.

<details><summary>Evidence shown to the jury</summary>

[1] <https://requests.readthedocs.io/en/master/user/advanced>

> We will begin with the verb most commonly used: GET. HTTP GET is an idempotent method that returns a resource from a given URL. As a result, it is the verb you ought to use when attempting to retrieve data from a web location. An example usage would be attempting to get information about a specific commit from GitHub. Suppose we wanted commit `a050faf` on Requests. We would get it like so: ``` >>> import requests>>> r = requests. get(' ``` We should confirm that GitHub responded correctly. If it has, we want to work out what type of content it is. Do this like so: ``` >>> if r. status_code == requests. codes. ok:... print(r. headers['content-type'])...application/json; charset=utf-8 ```

[2] <https://requests.readthedocs.io/en/master/user/advanced>

> All values that are contained within a session are directly available to you. See the Session API Docs to learn more. ## Request and Response Objects¶ Whenever a call is made to `requests.get()` and friends, you are doing two major things. First, you are constructing a `Request` object which will be sent off to a server to request or query some resource. Second, a `Response` object is generated once Requests gets a response back from the server. The `Response` object contains all of the information returned by the server and also contains the `Request` object you created originally. Here is a simple request to get some very important information from Wikipedia’s servers: ``` >>> r = requests. get(' ``` If we want to access the headers the server sent back to us, we do this:

[3] <https://requests.readthedocs.io/en/master/user/advanced>

> ``` r = requests. get(' timeout =(3.05, 27)) ``` If the remote server is very slow, you can tell Requests to wait forever for a response, by passing None as a timeout value and then retrieving a cup of coffee. ``` r = requests. get(' timeout = None) ``` Note The connect timeout applies to each connection attempt to an IP address. If multiple addresses exist for a domain name, the underlying `urllib3` will try each address sequentially until one successfully connects. This may lead to an effective total connection timeout multiple times longer than the specified time, e.g. an unresponsive server having both IPv4 and IPv6 addresses will have its perceived timeout doubled, so take that into account when setting the connection timeout. Note

[4] <https://requests.readthedocs.io/en/master/user/advanced>

> ``` from urllib3.util import Retry from requests import Session from requests.adapters import HTTPAdapter s = Session() retries = Retry(total = 3, backoff_factor =0.1, status_forcelist =[502, 503, 504], allowed_methods ={'POST'},) s. mount(' HTTPAdapter(max_retries = retries)) ``` ## Blocking Or Non-Blocking?¶ With the default Transport Adapter in place, Requests does not provide any kind of non-blocking IO. The `Response.content` property will block until the entire response has been downloaded. If you require more granularity, the streaming features of the library (see Streaming Requests) allow you to retrieve smaller quantities of the response at a time. However, these calls will still block.

[5] <https://requests.readthedocs.io/_/downloads/en/stable/pdf>

> GetKwargs]) → Response. Sends a GET request. Parameters. • url – URL ... max_retries – The maximum number of retries each connection should

[6] <https://requests.readthedocs.io/en/master/user/advanced>

> ``` import ssl from urllib3.poolmanager import PoolManager from requests.adapters import HTTPAdapter class Ssl3HttpAdapter(HTTPAdapter): """"Transport adapter" that allows us to use SSLv3.""" def init_poolmanager(self, connections, maxsize, block = False): self. poolmanager = PoolManager(num_pools = connections, maxsize = maxsize, block = block, ssl_version = ssl. PROTOCOL_SSLv3) ``` ### Example: Automatic Retries¶ By default, Requests does not retry failed connections. However, it is possible to implement automatic retries with a powerful array of features, including backoff, within a Requests `Session` using the urllib3.util.Retry class:

</details>

### c9. SUPPORTED: datetime.utcnow() is deprecated since Python 3.12.

Claim type `deprecated`, decided by **jury**.

Said in the input:
> - Replaced `datetime.utcnow()`, which is deprecated since Python 3.12.

All 2 judges agree. The claim states that `datetime.utcnow()` is deprecated since Python 3.12, which matches the excerpt from [4] and [5], where it says 'Deprecated since version 3.12: Use `datetime.now()` with `UTC` instead.'

Source: <https://docs.python.org/3/library/datetime.html>

> Deprecated since version 3.12: Use `datetime.now()` with `UTC` instead.

| Judge | Model | Verdict | Stated | Quote found |
|---|---|---|---|---|
| judge 1 | `qwen2.5:3b` | supported | supported | yes |
| judge 2 | `qwen2.5:7b` | supported | supported | yes |

Documentation searched: docs.python.org.

- Documentation source: Python standard library module 'datetime'.

<details><summary>Evidence shown to the jury</summary>

[1] <https://docs.python.org/3/whatsnew/3.12.html>

> See PEP 688 for more details. (Contributed by Shantanu Jain in gh-91896.) `datetime`: `datetime.datetime`’s `utcnow()` and `utcfromtimestamp()` are deprecated and will be removed in a future version. Instead, use timezone-aware objects to represent datetimes in UTC: respectively, call `now()` and `fromtimestamp()` with the tz parameter set to `datetime.UTC`. (Contributed by Paul Ganssle in gh-103857.) `email`: Deprecate the isdst parameter in `email.utils.localtime()`. (Contributed by Alan Williams in gh-72346.) `importlib.abc`: Deprecated the following classes, scheduled for removal in Python 3.14: + `importlib.abc.ResourceReader` + `importlib.abc.Traversable` + `importlib.abc.TraversableResources` Use `importlib.resources.abc` classes instead:

[2] <https://docs.python.org/3/library/datetime.html>

> classmethod datetime.now(tz=None)¶ : Return the current local date and time. If optional argument tz is `None` or not specified, this is like `today()`, but, if possible, supplies more precision than can be gotten from going through a `time.time()` timestamp (for example, this may be possible on platforms supplying the C `gettimeofday()` function). If tz is not `None`, it must be an instance of a `tzinfo` subclass, and the current date and time are converted to tz’s time zone. This function is preferred over `today()` and `utcnow()`. Note Subsequent calls to `datetime.now()` may return the same instant depending on the precision of the underlying clock. classmethod datetime.utcnow()¶ : Return the current UTC date and time, with `tzinfo` `None`.

[3] <https://docs.python.org/3/whatsnew/3.12.html>

> + `utcnow()`: use `datetime.datetime.now(tz=datetime.UTC)`. + `utcfromtimestamp()`: use `datetime.datetime.fromtimestamp(timestamp,tz=datetime.UTC)`. `gettext`: Plural value must be an integer. `importlib`: + `cache_from_source()` debug\_override parameter is deprecated: use the optimization parameter instead. `importlib.metadata`:

[4] <https://docs.python.org/3/library/datetime.html>

> This is like `now()`, but returns the current UTC date and time, as a naive `datetime` object. An aware current UTC datetime can be obtained by calling `datetime.now(timezone.utc)`. See also `now()`. Warning Because naive `datetime` objects are treated by many `datetime` methods as local times, it is preferred to use aware datetimes to represent times in UTC. As such, the recommended way to create an object representing the current time in UTC is by calling `datetime.now(timezone.utc)`. Deprecated since version 3.12: Use `datetime.now()` with `UTC` instead.

[5] <https://docs.python.org/3/library/datetime.html>

> Warning Because naive `datetime` objects are treated by many `datetime` methods as local times, it is preferred to use aware datetimes to represent times in UTC. As such, the recommended way to create an object representing a specific timestamp in UTC is by calling `datetime.fromtimestamp(timestamp, tz=timezone.utc)`. Changed in version 3.3: Raise `OverflowError` instead of `ValueError` if the timestamp is out of the range of values supported by the platform C `gmtime()` function. Raise `OSError` instead of `ValueError` on `gmtime()` failure. Changed in version 3.15: Accepts any real number as timestamp, not only integer or float. Deprecated since version 3.12: Use `datetime.fromtimestamp()` with `UTC` instead.

[6] <https://docs.python.org/3/whatsnew/3.12.html>

> + The `_enablelegacywindowsfsencoding()` function has been deprecated since Python 3.13. Use the `PYTHONLEGACYWINDOWSFSENCODING` environment variable instead. `sysconfig`: + The `sysconfig.expand_makefile_vars()` function has been deprecated since Python 3.14. Use the `vars` argument of `sysconfig.get_paths()` instead. `tarfile`: + The undocumented and unused `TarFile.tarfile` attribute has been deprecated since Python 3.13. ### Pending removal in Python 3.17¶ `datetime`: + `strptime()` calls using a format string containing `%e` (day of month) without a year. This has been deprecated since Python 3.15. (Contributed by Stan Ulbrych in gh-70647.) `collections.abc`: + `collections.abc.ByteString` is scheduled for removal in Python 3.17.

</details>

### c10. CONTRADICTED: distutils was removed in Python 3.10.

Claim type `deprecated`, decided by **adjudicator**.

Said in the input:
> - The `distutils` module was removed in Python 3.10, so `setup.py` now imports setuptools.

Judges disagreed (qwen2.5:3b: unverifiable, qwen2.5:7b: contradicted); the adjudicator decided contradicted. The claim states that `distutils` was removed in Python 3.10, but the excerpts indicate it was deprecated and will be removed in Python 3.12.

Source: <https://docs.python.org/3/library/distutils.html>

> Deprecated since version 3.10, removed in version 3.12.

| Judge | Model | Verdict | Stated | Quote found |
|---|---|---|---|---|
| judge 1 | `qwen2.5:3b` | unverifiable | contradicted | no |
| judge 2 | `qwen2.5:7b` | contradicted | contradicted | yes |
| adjudicator | `qwen2.5:7b` | contradicted | contradicted | yes |

Documentation searched: docs.python.org.

- Documentation source: Python standard library module 'distutils'.

<details><summary>Evidence shown to the jury</summary>

[1] <https://docs.python.org/3/library/distutils.html>

> This module is no longer part of the Python standard library. It was [removed in Python 3.12](../whatsnew/3.12.html#whatsnew312-removed-distutils) after being deprecated in Python 3.10. The removal was decided in [**PEP 632**](https://peps.python.org/pep-0632/), which has [migration advice](https://peps.python.org/pep-0632/#migration-advice). The last version of Python that provided the `distutils` module was [Python 3.11](https://docs.python.org/3.11/library/distutils.html). #### Previous topic [`crypt` — Function to check Unix passwords](crypt.html "previous chapter") #### Next topic [`imghdr` — Determine the type of an image](imghdr.html "next chapter") ### This page * [Report a bug](../bugs.html) * [Improve this page](../improve-page-nojs.html) * [Show source](https://github.com/python/cpython/blob/3.15/Doc/library/distutils.rst?plain=1) ### Navigation

[2] <https://docs.python.org/3/library/distutils.html>

> ### Navigation * [index](../genindex.html "General Index") * [modules](../py-modindex.html "Python Module Index") | * [next](imghdr.html "imghdr — Determine the type of an image") | * [previous](crypt.html "crypt — Function to check Unix passwords") | * [Python](https://www.python.org/) » * [3.15.0 Documentation](../index.html) » * [The Python standard library](index.html) » * [Removed Modules](removed.html) » * `distutils` — Building and installing Python modules * | * | # `distutils` — Building and installing Python modules[¶](#module-distutils "Link to this heading") Deprecated since version 3.10, removed in version 3.12.

[3] <https://docs.python.org/3/whatsnew/3.12.html>

> ### configparser¶ Several names deprecated in the `configparser` way back in 3.2 have been removed per gh-89336: + `configparser.ParsingError` no longer has a `filename` attribute or argument. Use the `source` attribute and argument instead. + `configparser` no longer has a `SafeConfigParser` class. Use the shorter `ConfigParser` name instead. + `configparser.ConfigParser` no longer has a `readfp` method. Use `read_file()` instead. ### distutils¶ Remove the `distutils` package. It was deprecated in Python 3.10 by PEP 632 “Deprecate distutils module”. For projects still using `distutils` and cannot be updated to something else, the `setuptools` project can be installed: it still provides `distutils`. (Contributed by Victor Stinner in gh-92584.) ### ensurepip¶

[4] <https://docs.python.org/3/whatsnew/3.10.html>

> ### distutils¶ The entire `distutils` package is deprecated, to be removed in Python 3.12. Its functionality for specifying package builds has already been completely replaced by third-party packages `setuptools` and `packaging`, and most other commonly used APIs are available elsewhere in the standard library (such as `platform`, `shutil`, `subprocess` or `sysconfig`). There are no plans to migrate any other functionality from `distutils`, and applications that are using other functions should plan to make private copies of the code. Refer to PEP 632 for discussion. The `bdist_wininst` command deprecated in Python 3.8 has been removed. The `bdist_wheel` command is now recommended to distribute binary packages on Windows. (Contributed by Victor Stinner in bpo-42802.) ### doctest¶

[5] <https://docs.python.org/3/whatsnew/3.10.html>

> - os.path - pathlib - platform - pprint - py\_compile - pyclbr - shelve - statistics - site - socket - ssl - sqlite3 - sys - \_thread - threading - traceback - types - typing - unittest - urllib.parse - xml - zipimport + Optimizations + Deprecated + Removed + Porting to Python 3.10 - Changes in the Python syntax - Changes in the Python API - Changes in the C API + CPython bytecode changes + Build Changes + C API Changes - PEP 652: Maintaining the Stable ABI - New Features - Porting to Python 3.10 - Deprecated - Removed + Notable security feature in 3.10.7 + Notable security feature in 3.10.8 + Notable changes in 3.10.12 - tarfile

[6] <https://docs.python.org/3/whatsnew/3.12.html>

> ### hashlib¶ Remove the pure Python implementation of `hashlib`’s `hashlib.pbkdf2_hmac()`, deprecated in Python 3.10. Python 3.10 and newer requires OpenSSL 1.1.1 (PEP 644): this OpenSSL version provides a C implementation of `pbkdf2_hmac()` which is faster. (Contributed by Victor Stinner in gh-94199.) ### importlib¶ Many previously deprecated cleanups in `importlib` have now been completed:

</details>

### c11. UNVERIFIABLE: Stripe refunds accept an idempotency key.

Claim type `parameter_exists`, decided by **jury**.

Said in the input:
> - Stripe refunds accept an idempotency key, so retrying the refund call is safe.

1 of 2 judges answered supported but their quotes were not in the evidence, so the verdict is unverifiable.

| Judge | Model | Verdict | Stated | Quote found |
|---|---|---|---|---|
| judge 1 | `qwen2.5:3b` | unverifiable | supported | no |
| judge 2 | `qwen2.5:7b` | unverifiable | unverifiable | no |

Documentation searched: docs.stripe.com, stripe.com.

- Documentation source: curated map: 'stripe'.

<details><summary>Evidence shown to the jury</summary>

[1] <https://docs.stripe.com/idempotency>

> `500` A client generates an idempotency key, which is a unique key that the server uses to recognize subsequent retries of the same request. How you create unique keys is up to you, but we suggest using V4 UUIDs, or another random string with enough entropy to avoid collisions. Idempotency keys are up to 255 characters long. Avoid using sensitive data (for example, email addresses or personal identifiers) as idempotency keys. For API v1, you can remove keys from the system automatically after they’re at least 24 hours old. We generate a new request if a key is reused after the original is pruned. The idempotency layer compares incoming parameters to those of the original request and errors if they’re not the same to prevent accidental misuse.

[2] <https://docs.stripe.com/api/idempotent_requests?__=>

> A client generates an idempotency key, which is a unique key that the server uses to recognize subsequent retries of the same request. How you create unique keys is up to you, but we suggest using V4 UUIDs, or another random string with enough entropy to avoid collisions. Idempotency keys are up to 255 characters long. Avoid using sensitive data (for example, email addresses or personal identifiers) as idempotency keys. For API v1, you can remove keys from the system automatically after they’re at least 24 hours old. We generate a new request if a key is reused after the original is pruned. The idempotency layer compares incoming parameters to those of the original request and errors if they’re not the same to prevent accidental misuse.

[3] <https://docs.stripe.com/idempotency>

> `IdempotencyKey` For API v1, Stripe saves the status code and body of the first request made with a given idempotency key after endpoint execution begins. Retries with the same key return the saved response, including `500` errors. With API v2, retries don’t repeat successful operations. Stripe retries failed or partially failed work to completion when possible and returns an updated response. If a retry can’t succeed, Stripe returns an error explaining why. `500`

[4] <https://docs.stripe.com/api/idempotent_requests?__=>

> For API v1, Stripe saves the status code and body of the first request made with a given idempotency key after endpoint execution begins. Retries with the same key return the saved response, including `500` errors. With API v2, retries don’t repeat successful operations. Stripe retries failed or partially failed work to completion when possible and returns an updated response. If a retry can’t succeed, Stripe returns an error explaining why.

[5] <https://docs.stripe.com/idempotency>

> For API v1, we save results only after the execution of an endpoint begins. If incoming parameters fail validation, or the request conflicts with another request that’s executing concurrently, we don’t save the idempotent result because no API endpoint initiates the execution. You can retry these requests. Learn more about when you can retry idempotent requests. For API v1, all `POST` requests accept idempotency keys. Don’t send idempotency keys in `GET` and `DELETE` requests because it has no effect. These requests are idempotent by definition. `POST` `GET` `DELETE` `curl \ -u sk_test_...sk_test_...: \ -H "Idempotency-Key: KG5LxwFBepaKHyUD" \ -d description="My First Test Customer (created for API docs at # Include-dependent response values (API v2)

[6] <https://docs.stripe.com/idempotency>

> # Idempotent requests The API supports idempotency for safely retrying requests without accidentally performing the same operation twice. When creating or updating an object, use an idempotency key. Then, if a connection error occurs, you can safely repeat the request without risk of creating a second object or performing the update twice. To perform an idempotent request, provide an additional `IdempotencyKey` element to the request options. `IdempotencyKey`

</details>

---
Claims extracted by `qwen2.5:7b` from 19 sentences.
Jury: `qwen2.5:3b`, `qwen2.5:7b`; adjudicator `qwen2.5:7b`.
Calls this run: 0 HTTP (15 cached), 0 Tavily (8 cached), 0 model (15 cached).
