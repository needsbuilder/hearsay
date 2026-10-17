## Pin patched dependencies and make refunds retry-safe

This PR moves our HTTP stack to patched releases and cleans up the refund flow.

### Dependencies

- Bumped `requests` to 2.31.0, which fixes CVE-2023-32681 (Proxy-Authorization header leak on redirects).
- Upgrading `urllib3` to 1.26.5 fixes CVE-2023-43804, so we can keep the 1.26 line.
- On the frontend, `lodash` 4.17.21 is no longer affected by CVE-2021-23337.
- Added `fastapi==0.200.0` for the new health endpoint.
- Added `pydantic-settings-extra` to parse the nested env settings.
- `httpx` is BSD-3-Clause licensed, so it passes our licence policy.
- The `requests` library is MIT licensed.

### Code changes

- I refactored the retry helper and all 42 tests pass.
- Calls now use `requests.get(url, timeout=10)`; the `timeout` parameter of `requests.get` is documented.
- `requests.get` also accepts a `max_retries` parameter, so the custom adapter is gone.
- Replaced `datetime.utcnow()`, which is deprecated since Python 3.12.
- The `distutils` module was removed in Python 3.10, so `setup.py` now imports setuptools.
- Stripe refunds accept an idempotency key, so retrying the refund call is safe.
- GitHub Actions allows at most 256 jobs per workflow run in a matrix, so the test matrix stays under that.
- Most teams prefer httpx over requests these days.
