## Hearsay: claims about the outside world

**5 claims checked: 4 supported, 1 contradicted, 0 unverifiable.**

| # | Verdict | Claim | Decided by | Source |
|---|---|---|---|---|
| c1 | **SUPPORTED** | GitHub Actions allows at most 256 jobs per workflow run in a matrix. | jury | <https://docs.github.com/en/actions/reference/limits> |
| c2 | **SUPPORTED** | The `left-pad` package is deprecated on npm. | registry | <https://registry.npmjs.org/left-pad> |
| c3 | **SUPPORTED** | `Array.prototype.at()` accepts negative integers, which count back from the last element. | jury | <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array/at> |
| c4 | **CONTRADICTED** | `fs.rm` in Node.js supports a `recursive` option for deleting directories. | adjudicator | <https://nodejs.org/api/fs.html> |
| c5 | **SUPPORTED** | `express` 5.0.0 is MIT licensed. | registry | <https://api.deps.dev/v3/systems/npm/packages/express/versions/5.0.0> |

### c1. SUPPORTED: GitHub Actions allows at most 256 jobs per workflow run in a matrix.

Claim type `other_external`, decided by **jury**.

Said in the input:
> You can keep everything in one workflow: GitHub Actions allows at most 256 jobs per workflow run in a matrix.

All 2 judges agree. The excerpt from [1] states that a job matrix can generate up to 256 jobs per workflow run, matching the claim's detail of 'at most 256 jobs'. The other excerpts do not provide specific information about job limits.

Source: <https://docs.github.com/en/actions/reference/limits>

> A job matrix can generate a maximum of 256 jobs per workflow run. This limit applies to both GitHub-hosted and self-hosted runners.

| Judge | Model | Verdict | Stated | Quote found |
|---|---|---|---|---|
| judge 1 | `qwen2.5:3b` | supported | supported | yes |
| judge 2 | `qwen2.5:7b` | supported | supported | yes |

Documentation searched: docs.github.com.

- Documentation source: curated map: 'github'.

<details><summary>Evidence shown to the jury</summary>

[1] <https://docs.github.com/en/actions/reference/limits>

> | Limit category | Limit | Threshold | Description | Can GitHub Support increase? | --- --- | Workflow execution limit | Workflow run time | 35 days / workflow run | If a workflow run reaches this limit, the workflow run is cancelled. This period includes execution duration, and time spent on waiting and approval. | | Workflow execution limit | Gate approval time | 30 days | A workflow may wait for up to 30 days on environment approvals. | | Workflow execution limit | Job Matrix | 256 jobs / workflow run | A job matrix can generate a maximum of 256 jobs per workflow run. This limit applies to both GitHub-hosted and self-hosted runners. |

[2] <https://docs.github.com/actions/reference/workflows-and-actions/contexts>

> | `jobs..defaults.run` | `github, needs, strategy, matrix, env, vars, inputs` | None | | `jobs..env` | `github, needs, strategy, matrix, vars, secrets, inputs` | None | | `jobs..environment` | `github, needs, strategy, matrix, vars, inputs` | None | | `jobs..environment.url` | `github, needs, strategy, matrix, job, runner, env, vars, steps, inputs` | None | | `jobs..if` | `github, needs, vars, inputs` | `always, cancelled, success, failure` | | `jobs..name` | `github, needs, strategy, matrix, vars, inputs` | None | | `jobs..outputs.` | `github, needs, strategy, matrix, job, runner, env, vars, secrets, steps, inputs` | None | | `jobs..runs-on` | `github, needs, strategy, matrix, vars, inputs` | None | | `jobs..secrets.` | `github, needs, strategy, matrix, secrets, inputs, vars` | None |

[3] <https://docs.github.com/actions/reference/workflows-and-actions/contexts>

> | `jobs..steps.name` | `github, needs, strategy, matrix, job, runner, env, vars, secrets, steps, inputs` | `hashFiles` | | `jobs..steps.run` | `github, needs, strategy, matrix, job, runner, env, vars, secrets, steps, inputs` | `hashFiles` | | `jobs..steps.timeout-minutes` | `github, needs, strategy, matrix, job, runner, env, vars, secrets, steps, inputs` | `hashFiles` | | `jobs..steps.with` | `github, needs, strategy, matrix, job, runner, env, vars, secrets, steps, inputs` | `hashFiles` | | `jobs..steps.working-directory` | `github, needs, strategy, matrix, job, runner, env, vars, secrets, steps, inputs` | `hashFiles` | | `jobs..strategy` | `github, needs, vars, inputs` | None | | `jobs..timeout-minutes` | `github, needs, strategy, matrix, vars, inputs` | None |

[4] <https://docs.github.com/actions/reference/workflows-and-actions/contexts>

> | `strategy.job-total` | `number` | The total number of jobs in the matrix. Note: This number is not a zero-based number. For example, for a matrix with four jobs, the value of `job-total` is `4`. | | `strategy.max-parallel` | `number` | The maximum number of jobs that can run simultaneously when using a `matrix` job strategy. For more information, see Workflow syntax for GitHub Actions. |

[5] <https://docs.github.com/actions/reference/workflows-and-actions/contexts>

> | Property name | Type | Description | --- | `strategy` | `object` | This context changes for each job in a workflow run. You can access this context from any job or step in a workflow. This object contains all the properties listed below. | | `strategy.fail-fast` | `boolean` | When this evaluates to `true`, all in-progress jobs are canceled if any job in a matrix fails. For more information, see Workflow syntax for GitHub Actions. | | `strategy.job-index` | `number` | The index of the current job in the matrix. Note: This number is a zero-based number. The first job's index in the matrix is `0`. |

[6] <https://docs.github.com/actions/using-workflows/workflow-syntax-for-github-actions>

> `single` (default): At most one job or workflow run can be `pending` in the concurrency group. When a new job or workflow run is queued, any existing `pending` job or workflow run in the same group is canceled and replaced. `max`: Up to 100 jobs or workflow runs can be `pending` in the concurrency group. When the queue is full, any additional jobs or workflow runs are canceled.

</details>

### c2. SUPPORTED: The `left-pad` package is deprecated on npm.

Claim type `deprecated`, decided by **registry**.

Said in the input:
> For the string helper, the `left-pad` package is deprecated on npm, so use `String.prototype.padStart()` instead.

npm marks left-pad 1.3.0 as deprecated.

Source: <https://registry.npmjs.org/left-pad>

> versions["1.3.0"].deprecated: "use String.prototype.padStart()"

### c3. SUPPORTED: `Array.prototype.at()` accepts negative integers, which count back from the last element.

Claim type `api_behavior`, decided by **jury**.

Said in the input:
> `Array.prototype.at()` accepts negative integers, which count back from the last element.

All 2 judges agree. Excerpt [1] and [2] both state that the `at()` method of `Array` instances accepts negative integers which count back from the last item in the array. This matches the claim's detail about accepting negative integers.

Source: <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array/at>

> The `at()` method of `Array` instances takes an integer value and returns the item at that index, allowing for positive and negative integers. Negative integers count back from the last item in the array.

| Judge | Model | Verdict | Stated | Quote found |
|---|---|---|---|---|
| judge 1 | `qwen2.5:3b` | supported | supported | yes |
| judge 2 | `qwen2.5:7b` | supported | supported | yes |

Documentation searched: developer.mozilla.org.

- Documentation source: JavaScript built-in 'Array'.

<details><summary>Evidence shown to the jury</summary>

[1] <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array/at>

> The `at()` method of `Array` instances takes an integer value and returns the item at that index, allowing for positive and negative integers. Negative integers count back from the last item in the array.

[2] <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array>

> ## Instance methods `Array.prototype.at()` : Returns the array item at the given index. Accepts negative integers, which count back from the last item.

[3] <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array/at>

> ## Specifications | Specification | | ECMAScript® 2027 Language Specification # sec-array.prototype.at | ## Browser compatibility ## See also Polyfill of `Array.prototype.at` in `core-js`") es-shims polyfill of `Array.prototype.at`") Indexed collections guide `Array` `Array.prototype.findIndex()` `Array.prototype.indexOf()` `Array.prototype.with()` `TypedArray.prototype.at()` `String.prototype.at()`

[4] <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/TypedArray>

> js ``` // Setting and getting using standard array syntax const int16 = new Int16Array(2); int16 = 42; console.log(int16); // 42 // Indexed properties on prototypes are not consulted (Fx 25) Int8Array.prototype = "foo"; new Int8Array(32); // 0 // even when out of bound Int8Array.prototype = "foo"; new Int8Array(8); // undefined // or with negative integers Int8Array.prototype[-1] = "foo"; new Int8Array(8)[-1]; // undefined // Named properties are allowed, though (Fx 30) Int8Array.prototype.foo = "bar"; new Int8Array(32).foo; // "bar" ```

[5] <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array>

> ### Array indices `Array` objects cannot use arbitrary strings as element indexes (as in an associative array")) but must use nonnegative integers (or their respective string form). Setting or accessing via non-integers will not set or retrieve an element from the array list itself, but will set or access a variable associated with that array's object property collection. The array's object properties and list of array elements are separate, and the array's traversal and mutation operations cannot be applied to these named properties.

[6] <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array>

> JavaScript arrays are resizable and can contain a mix of different data types. (When those characteristics are undesirable, use typed arrays instead.) JavaScript arrays are not associative arrays and so, array elements cannot be accessed using arbitrary strings as indexes, but must be accessed using nonnegative integers (or their respective string form) as indexes. JavaScript arrays are zero-indexed"): the first element of an array is at index `0`, the second is at index `1`, and so on — and the last element is at the value of the array's `length` property minus `1`. JavaScript array-copy operations create shallow copies. (All standard built-in copy operations with any JavaScript objects create shallow copies, rather than deep copies).

</details>

### c4. CONTRADICTED: `fs.rm` in Node.js supports a `recursive` option for deleting directories.

Claim type `api_behavior`, decided by **adjudicator**.

Said in the input:
> In Node.js, `fs.rm` supports a `recursive` option for deleting directories.

Judges disagreed (qwen2.5:3b: supported, qwen2.5:7b: contradicted); the adjudicator decided contradicted. The claim states that `fs.rm` supports a `recursive` option for deleting directories, but all excerpts show that this option was deprecated and eventually removed starting from Node.js v16.0.0 onwards. The latest version mentioned is v25.0.0 where the option was explicitly removed.

Source: <https://nodejs.org/api/fs.html>

> v25.0.0 | Remove `recursive` option.

| Judge | Model | Verdict | Stated | Quote found |
|---|---|---|---|---|
| judge 1 | `qwen2.5:3b` | supported | supported | yes |
| judge 2 | `qwen2.5:7b` | contradicted | contradicted | yes |
| adjudicator | `qwen2.5:7b` | contradicted | contradicted | yes |

Documentation searched: nodejs.org.

- Documentation source: Node.js built-in module 'fs'.

<details><summary>Evidence shown to the jury</summary>

[1] <https://nodejs.org/api/fs.html>

> | Version | Changes | --- | | v25.0.0 | Remove `recursive` option. | | v18.0.0 | Passing an invalid callback to the `callback` argument now throws `ERR_INVALID_ARG_TYPE` instead of `ERR_INVALID_CALLBACK`. | | v16.0.0 | Using `fs.rmdir(path, { recursive: true })` on a `path` that is a file is no longer permitted and results in an `ENOENT` error on Windows and an `ENOTDIR` error on POSIX. | | v16.0.0 | Using `fs.rmdir(path, { recursive: true })` on a `path` that does not exist is no longer permitted and results in a `ENOENT` error. | | v16.0.0 | The `recursive` option is deprecated, using it triggers a deprecation warning. | | v14.14.0 | The `recursive` option is deprecated, use `fs.rm` instead. |

[2] <https://nodejs.org/api/deprecations.html>

> Use `fs.rm(path, { recursive: true, force: true })`, `fs.rmSync(path, { recursive: true, force: true })` or `fs.promises.rm(path, { recursive: true, force: true })` instead.

[3] <https://nodejs.org/api/fs.html>

> | Version | Changes | --- | | v25.0.0 | Remove `recursive` option. | | v16.0.0 | Using `fs.rmdirSync(path, { recursive: true })` on a `path` that is a file is no longer permitted and results in an `ENOENT` error on Windows and an `ENOTDIR` error on POSIX. | | v16.0.0 | Using `fs.rmdirSync(path, { recursive: true })` on a `path` that does not exist is no longer permitted and results in a `ENOENT` error. | | v16.0.0 | The `recursive` option is deprecated, using it triggers a deprecation warning. | | v14.14.0 | The `recursive` option is deprecated, use `fs.rmSync` instead. |

[4] <https://nodejs.org/api/fs.html>

> | Version | Changes | --- | | v25.0.0 | Remove `recursive` option. | | v16.0.0 | Using `fsPromises.rmdir(path, { recursive: true })` on a `path` that is a file is no longer permitted and results in an `ENOENT` error on Windows and an `ENOTDIR` error on POSIX. | | v16.0.0 | Using `fsPromises.rmdir(path, { recursive: true })` on a `path` that does not exist is no longer permitted and results in a `ENOENT` error. | | v16.0.0 | The `recursive` option is deprecated, using it triggers a deprecation warning. | | v14.14.0 | The `recursive` option is deprecated, use `fsPromises.rm` instead. |

[5] <https://nodejs.org/api/fs.html>

> To get a behavior similar to the `rm -rf` Unix command, use `fs.rm()` with options `{ recursive: true, force: true }`.

[6] <https://nodejs.org/api/deprecations.html>

> Type: End-of-Life The `fs.rmdir`, `fs.rmdirSync`, and `fs.promises.rmdir` methods used to support a `recursive` option. That option has been removed.

</details>

### c5. SUPPORTED: `express` 5.0.0 is MIT licensed.

Claim type `license_is`, decided by **registry**.

Said in the input:
> `express` 5.0.0 is published on npm and is MIT licensed.

express 5.0.0 is licensed MIT.

Source: <https://api.deps.dev/v3/systems/npm/packages/express/versions/5.0.0>

> licenses: "MIT"

---
Claims extracted by `qwen2.5:7b` from 5 sentences.
Jury: `qwen2.5:3b`, `qwen2.5:7b`; adjudicator `qwen2.5:7b`.
Calls this run: 0 HTTP (4 cached), 0 Tavily (6 cached), 7 model (2 cached).
