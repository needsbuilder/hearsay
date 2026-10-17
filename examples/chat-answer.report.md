## Hearsay: claims about the outside world

**5 claims checked: 5 supported, 0 contradicted, 0 unverifiable.**

| # | Verdict | Claim | Decided by | Source |
|---|---|---|---|---|
| c1 | **SUPPORTED** | GitHub Actions allows at most 256 jobs per workflow run in a matrix. | jury | <https://docs.github.com/en/actions/reference/limits> |
| c2 | **SUPPORTED** | The `left-pad` package is deprecated on npm. | registry | <https://registry.npmjs.org/left-pad> |
| c3 | **SUPPORTED** | `Array.prototype.at()` accepts negative integers, which count back from the last element. | adjudicator | <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array/at> |
| c4 | **SUPPORTED** | `fs.rm` in Node.js supports a `recursive` option for deleting directories. | adjudicator | <https://nodejs.org/api/fs.html> |
| c5 | **SUPPORTED** | `express` 5.0.0 is MIT licensed. | registry | <https://api.deps.dev/v3/systems/npm/packages/express/versions/5.0.0> |

### c1. SUPPORTED: GitHub Actions allows at most 256 jobs per workflow run in a matrix.

Claim type `other_external`, decided by **jury**.

Said in the input:
> You can keep everything in one workflow: GitHub Actions allows at most 256 jobs per workflow run in a matrix.

All 2 judges agree. The excerpt from [1] states the limit is 256 jobs per workflow run and applies to both GitHub-hosted and self-hosted runners. The claim specifies at most 256 jobs per workflow run, which matches exactly with the information provided in the excerpt.

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

[2] <https://docs.github.com/actions/using-workflows/workflow-syntax-for-github-actions>

> ## `jobs.<job_id>.strategy` Use `jobs.<job_id>.strategy` to use a matrix strategy for your jobs. A matrix strategy lets you use variables in a single job definition to automatically create multiple job runs that are based on the combinations of the variables. For example, you can use a matrix strategy to test your code in multiple versions of a language or on multiple operating systems. For more information, see Running variations of jobs in a workflow. ## `jobs.<job_id>.strategy.matrix` Use `jobs.<job_id>.strategy.matrix` to define a matrix of different job configurations. For more information, see Running variations of jobs in a workflow. A matrix will generate a maximum of 256 jobs per workflow run. This limit applies to both GitHub-hosted and self-hosted runners.

[3] <https://docs.github.com/actions/using-workflows/workflow-syntax-for-github-actions>

> ### Example of `cache-mode` ```yaml cache-mode: read jobs: build: runs-on: ubuntu-latest steps: - uses: actions/checkout@v6 - uses: actions/cache@v4 with: path: ~/.npm key: npm-${{ hashFiles('/package-lock.json') }} ``` ## `jobs` A workflow run is made up of one or more `jobs`, which run in parallel by default. To run jobs sequentially, you can define dependencies on other jobs using the `jobs.<job_id>.needs` keyword. Each job runs in a runner environment specified by `runs-on`. You can run an unlimited number of jobs as long as you are within the workflow usage limits. For more information, see Billing and usage for GitHub-hosted runners and Actions limits for self-hosted runner usage limits.

[4] <https://docs.github.com/actions/reference/workflows-and-actions/contexts>

> | `jobs..defaults.run` | `github, needs, strategy, matrix, env, vars, inputs` | None | | `jobs..env` | `github, needs, strategy, matrix, vars, secrets, inputs` | None | | `jobs..environment` | `github, needs, strategy, matrix, vars, inputs` | None | | `jobs..environment.url` | `github, needs, strategy, matrix, job, runner, env, vars, steps, inputs` | None | | `jobs..if` | `github, needs, vars, inputs` | `always, cancelled, success, failure` | | `jobs..name` | `github, needs, strategy, matrix, vars, inputs` | None | | `jobs..outputs.` | `github, needs, strategy, matrix, job, runner, env, vars, secrets, steps, inputs` | None | | `jobs..runs-on` | `github, needs, strategy, matrix, vars, inputs` | None | | `jobs..secrets.` | `github, needs, strategy, matrix, secrets, inputs, vars` | None |

[5] <https://docs.github.com/actions/reference/workflows-and-actions/contexts>

> | `jobs..steps.name` | `github, needs, strategy, matrix, job, runner, env, vars, secrets, steps, inputs` | `hashFiles` | | `jobs..steps.run` | `github, needs, strategy, matrix, job, runner, env, vars, secrets, steps, inputs` | `hashFiles` | | `jobs..steps.timeout-minutes` | `github, needs, strategy, matrix, job, runner, env, vars, secrets, steps, inputs` | `hashFiles` | | `jobs..steps.with` | `github, needs, strategy, matrix, job, runner, env, vars, secrets, steps, inputs` | `hashFiles` | | `jobs..steps.working-directory` | `github, needs, strategy, matrix, job, runner, env, vars, secrets, steps, inputs` | `hashFiles` | | `jobs..strategy` | `github, needs, vars, inputs` | None | | `jobs..timeout-minutes` | `github, needs, strategy, matrix, vars, inputs` | None |

[6] <https://docs.github.com/actions/reference/workflows-and-actions/contexts>

> | `strategy.job-total` | `number` | The total number of jobs in the matrix. Note: This number is not a zero-based number. For example, for a matrix with four jobs, the value of `job-total` is `4`. | | `strategy.max-parallel` | `number` | The maximum number of jobs that can run simultaneously when using a `matrix` job strategy. For more information, see Workflow syntax for GitHub Actions. |

</details>

### c2. SUPPORTED: The `left-pad` package is deprecated on npm.

Claim type `deprecated`, decided by **registry**.

Said in the input:
> For the string helper, the `left-pad` package is deprecated on npm, so use `String.prototype.padStart()` instead.

npm marks left-pad 1.3.0 as deprecated.

Source: <https://registry.npmjs.org/left-pad>

> versions["1.3.0"].deprecated: "use String.prototype.padStart()"

### c3. SUPPORTED: `Array.prototype.at()` accepts negative integers, which count back from the last element.

Claim type `api_behavior`, decided by **adjudicator**.

Said in the input:
> `Array.prototype.at()` accepts negative integers, which count back from the last element.

Judges disagreed (qwen2.5:3b: unverifiable, qwen2.5:7b: supported); the adjudicator decided supported. Both excerpt [1] and excerpt [6] confirm that Array.prototype.at() accepts negative integers to count back from the last element of an array, which matches the claim.

Source: <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array/at>

> The `at()` method of `Array` instances takes an integer value and returns the item at that index, allowing for positive and negative integers. Negative integers count back from the last item in the array.

| Judge | Model | Verdict | Stated | Quote found |
|---|---|---|---|---|
| judge 1 | `qwen2.5:3b` | unverifiable | supported | no |
| judge 2 | `qwen2.5:7b` | supported | supported | yes |
| adjudicator | `qwen2.5:7b` | supported | supported | yes |

Documentation searched: developer.mozilla.org.

- Documentation source: JavaScript built-in 'Array'.

<details><summary>Evidence shown to the jury</summary>

[1] <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array>

> ## Instance methods `Array.prototype.at()` : Returns the array item at the given index. Accepts negative integers, which count back from the last item. `Array.prototype.concat()` : Returns a new array that is the calling array joined with other array(s) and/or value(s). `Array.prototype.copyWithin()` : Copies a sequence of array elements within an array. `Array.prototype.entries()` : Returns a new array iterator object that contains the key/value pairs for each index in an array. `Array.prototype.every()` : Returns `false` if it finds an element in the array that does not satisfy the provided testing function. Otherwise, it returns `true`. `Array.prototype.fill()` : Fills all the elements of an array from a start index to an end index with a static value.

[2] <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/TypedArray>

> `TypedArray.prototype.BYTES_PER_ELEMENT` : Returns a number value of the element size for the different `TypedArray` objects. ## Instance methods These methods are defined on the `TypedArray` prototype object and are thus shared by all `TypedArray` subclass instances. `TypedArray.prototype.at()` : Takes an integer value and returns the item at that index. This method allows for negative integers, which count back from the last item. `TypedArray.prototype.copyWithin()` : Copies a sequence of array elements within the array. See also `Array.prototype.copyWithin()`. `TypedArray.prototype.entries()` : Returns a new array iterator object that contains the key/value pairs for each index in the array. See also `Array.prototype.entries()`.

[3] <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array/at>

> Skip to search Toggle sidebar 1. Web 2. JavaScript 3. Reference 4. Standard built-in objects 5. Array 6. at() Remember language Learn more Deutsch English (US) Español Français 日本語 한국어 Português (do Brasil) Русский 中文 (简体) # Array.prototype.at() Baseline Widely available This feature is well established and works across many devices and browser versions. It’s been available across browsers since March 2022. See full compatibility Learn more The `at()` method of `Array` instances takes an integer value and returns the item at that index, allowing for positive and negative integers. Negative integers count back from the last item in the array. ## Try it

[4] <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array>

> `Array.prototype.indexOf()` : Returns the first (least) index at which a given element can be found in the calling array. `Array.prototype.join()` : Returns a new string that is the concatenation of all elements in this array, separated by commas or a specified separator string. `Array.prototype.keys()` : Returns a new array iterator that contains the keys for each index in the calling array. `Array.prototype.lastIndexOf()` : Returns the last (greatest) index at which a given element can be found in the calling array, or `-1` if none is found. `Array.prototype.map()` : Returns a new array containing the results of invoking a function on every element in the calling array. `Array.prototype.pop()` : Removes the last element from an array and returns that element.

[5] <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/TypedArray>

> `TypedArray.prototype.findIndex()` : Returns the first index value in the array that has an element that satisfies a provided testing function, or `-1` if no appropriate element was found. See also `Array.prototype.findIndex()`. `TypedArray.prototype.findLast()` : Returns the value of the last element in the array that satisfies a provided testing function, or `undefined` if no appropriate element is found. See also `Array.prototype.findLast()`. `TypedArray.prototype.findLastIndex()` : Returns the index of the last element in the array that satisfies a provided testing function, or `-1` if no appropriate element was found. See also `Array.prototype.findLastIndex()`.

[6] <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array/at>

> js ``` const arrayLike = { length: 2, 0: "a", 1: "b", 2: "c", // ignored by at() since length is 2 }; console.log(Array.prototype.at.call(arrayLike, 0)); // "a" console.log(Array.prototype.at.call(arrayLike, 2)); // undefined ``` ## Specifications | Specification | | ECMAScript® 2027 Language Specification # sec-array.prototype.at | ## Browser compatibility ## See also Polyfill of `Array.prototype.at` in `core-js`") es-shims polyfill of `Array.prototype.at`") Indexed collections guide `Array` `Array.prototype.findIndex()` `Array.prototype.indexOf()` `Array.prototype.with()` `TypedArray.prototype.at()` `String.prototype.at()` ## Help improve MDN Learn how to contribute This page was last modified on by MDN contributors.

</details>

### c4. SUPPORTED: `fs.rm` in Node.js supports a `recursive` option for deleting directories.

Claim type `api_behavior`, decided by **adjudicator**.

Said in the input:
> In Node.js, `fs.rm` supports a `recursive` option for deleting directories.

Judges disagreed (qwen2.5:3b: contradicted, qwen2.5:7b: supported); the adjudicator decided supported. The claim is supported by excerpt [3] and [6], which state that the `fs.rm(path[, options], callback)` method supports a `recursive: true` option. This contradicts Judge 1's reasoning, as it clearly indicates that `fs.rmdir` does not support this option, but `fs.rm` does.

Source: <https://nodejs.org/api/fs.html>

> `path` | | `options` There are currently no options exposed. There used to be options for `recursive`, `maxBusyTries`, and `emfileWait` but they were deprecated and removed.

| Judge | Model | Verdict | Stated | Quote found |
|---|---|---|---|---|
| judge 1 | `qwen2.5:3b` | contradicted | contradicted | yes |
| judge 2 | `qwen2.5:7b` | supported | supported | yes |
| adjudicator | `qwen2.5:7b` | supported | supported | yes |

Documentation searched: nodejs.org.

- Documentation source: Node.js built-in module 'fs'.

<details><summary>Evidence shown to the jury</summary>

[1] <https://nodejs.org/api/deprecations.html>

> Type: End-of-Life The `fs.rmdir`, `fs.rmdirSync`, and `fs.promises.rmdir` methods used to support a `recursive` option. That option has been removed. Use `fs.rm(path, { recursive: true, force: true })`, `fs.rmSync(path, { recursive: true, force: true })` or `fs.promises.rm(path, { recursive: true, force: true })` instead. An automated migration is available (source): ``` npx codemod@latest @nodejs/rmdir npx codemod@latest @nodejs/rmdir bash ``` #### DEP0148: Folder mappings in `"exports"` (trailing `"/"`)# History | Version | Changes | --- | | v17.0.0 | End-of-Life. | | v16.0.0 | Runtime deprecation. | | v15.1.0 | Runtime deprecation for self-referencing imports. | | v14.13.0 | Documentation-only deprecation. | Type: End-of-Life

[2] <https://nodejs.org/api/fs.html>

> | Version | Changes | --- | | v25.0.0 | Remove `recursive` option. | | v18.0.0 | Passing an invalid callback to the `callback` argument now throws `ERR_INVALID_ARG_TYPE` instead of `ERR_INVALID_CALLBACK`. | | v16.0.0 | Using `fs.rmdir(path, { recursive: true })` on a `path` that is a file is no longer permitted and results in an `ENOENT` error on Windows and an `ENOTDIR` error on POSIX. | | v16.0.0 | Using `fs.rmdir(path, { recursive: true })` on a `path` that does not exist is no longer permitted and results in a `ENOENT` error. | | v16.0.0 | The `recursive` option is deprecated, using it triggers a deprecation warning. | | v14.14.0 | The `recursive` option is deprecated, use `fs.rm` instead. |

[3] <https://nodejs.org/api/fs.html>

> `path` | | `options` There are currently no options exposed. There used to be options for `recursive`, `maxBusyTries`, and `emfileWait` but they were deprecated and removed. The `options` argument is still accepted for backwards compatibility but it is not used. `callback` + `err` Asynchronous `rmdir(2)`. No arguments other than a possible exception are given to the completion callback. Using `fs.rmdir()` on a file (not a directory) results in an `ENOENT` error on Windows and an `ENOTDIR` error on POSIX. To get a behavior similar to the `rm -rf` Unix command, use `fs.rm()` with options `{ recursive: true, force: true }`. #### `fs.rm(path[, options], callback)`# Added in: v14.14.0History

[4] <https://nodejs.org/api/fs.html>

> | Version | Changes | --- | | v25.0.0 | Remove `recursive` option. | | v16.0.0 | Using `fs.rmdirSync(path, { recursive: true })` on a `path` that is a file is no longer permitted and results in an `ENOENT` error on Windows and an `ENOTDIR` error on POSIX. | | v16.0.0 | Using `fs.rmdirSync(path, { recursive: true })` on a `path` that does not exist is no longer permitted and results in a `ENOENT` error. | | v16.0.0 | The `recursive` option is deprecated, using it triggers a deprecation warning. | | v14.14.0 | The `recursive` option is deprecated, use `fs.rmSync` instead. |

[5] <https://nodejs.org/api/fs.html>

> | Version | Changes | --- | | v25.0.0 | Remove `recursive` option. | | v16.0.0 | Using `fsPromises.rmdir(path, { recursive: true })` on a `path` that is a file is no longer permitted and results in an `ENOENT` error on Windows and an `ENOTDIR` error on POSIX. | | v16.0.0 | Using `fsPromises.rmdir(path, { recursive: true })` on a `path` that does not exist is no longer permitted and results in a `ENOENT` error. | | v16.0.0 | The `recursive` option is deprecated, using it triggers a deprecation warning. | | v14.14.0 | The `recursive` option is deprecated, use `fsPromises.rm` instead. |

[6] <https://nodejs.org/api/fs.html>

> `path` | | `options` There are currently no options exposed. There used to be options for `recursive`, `maxBusyTries`, and `emfileWait` but they were deprecated and removed. The `options` argument is still accepted for backwards compatibility but it is not used. Returns: Fulfills with `undefined` upon success. Removes the directory identified by `path`. Using `fsPromises.rmdir()` on a file (not a directory) results in the promise being rejected with an `ENOENT` error on Windows and an `ENOTDIR` error on POSIX. To get a behavior similar to the `rm -rf` Unix command, use `fsPromises.rm()` with options `{ recursive: true, force: true }`. #### `fsPromises.rm(path[, options])`# Added in: v14.14.0

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
Calls this run: 0 HTTP (4 cached), 0 Tavily (6 cached), 0 model (10 cached).
