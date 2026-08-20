# conda E2E Test Automation

[![E2E tests](https://github.com/conda-incubator/conda-quality/actions/workflows/e2e-tests.yml/badge.svg)](https://github.com/conda-incubator/conda-quality/actions/workflows/e2e-tests.yml)
[![nightly](https://github.com/conda-incubator/conda-quality/actions/workflows/nightly.yml/badge.svg)](https://github.com/conda-incubator/conda-quality/actions/workflows/nightly.yml)

Black-box, end-to-end tests for the **conda CLI**. The suite runs a real `conda`
executable as a subprocess and asserts on its `stdout` / `stderr` / exit code and
the on-disk state it produces. The conda under test is whatever is on `PATH`, or
whatever `CONDA_E2E_CONDA` points to.

## Requirements

- [pixi](https://pixi.sh) — provisions the harness Python and dev tools from the project's pixi config/lock
- A `conda` executable on `PATH`, or `CONDA_E2E_CONDA` set to its full path

The harness that _runs_ the tests is separate from the conda it _drives_ — install
conda the normal way, not via `pip install conda`.

## Setup

1. Install pixi: https://pixi.sh/latest/installation/
2. Install project dependencies:

```bash
pixi install
```

3. Install the git pre-commit hooks (once per clone) to enable automatic check of all changes before commiting them:

```bash
pixi run prek install
```

The harness runs in a pixi environment resolved from conda-forge. We deliberately
never bootstrap it with the **conda under test** — a broken conda must not be able
to break the harness meant to catch it. Pixi uses `rattler`, not the conda
executable, so that guarantee holds. Just don't add `conda` to the harness env:
the suite finds the conda under test on `PATH`, and a `conda` in the harness env
would shadow it.

## Running the tests

```bash
# Run all tests
pixi run test

# Run only "env" test suite
pixi run pytest tests/e2e/env

# Run specific test module
pixi run pytest tests/e2e/env/test_env_crud.py::test_remove_missing_env_fails
```

Shell-integration tests (activate / hooks) run once per shell found on the current OS — bash, zsh, sh, and PowerShell on Unix; cmd and PowerShell on Windows. Shells that aren't
installed are skipped.

These commands run against whatever `conda` is on `PATH`. To point the suite at a
different conda, or update it to a specific version first, see
[Configuration](#configuration) — its flags combine with any of the above (e.g.
`pixi run pytest tests/e2e/env --conda-version=latest`).

## Test report

A local run writes an HTML report to `reports/report.html`, relative to where
you invoked pytest; CI names its own per job, below. Each test row lists the
conda commands it ran beside the usual traceback; click one to read its exit
code, stdout and stderr. The Environment table at the top names the OS, and the
conda version, channel and base Python under test.

From a CI run, open the workflow run's **Summary** page:

- The **E2E matrix results** table lists every matrix job with its outcome and a
  link to that job's report.
- Reports are also under **Artifacts**, one per matrix job, named
  `report-<os>-py<python-version>` — for example `report-macos-latest-py3.14`,
  containing `report-482-macos-latest-py3.14.html`. The run number and the job
  are in the filename, so a downloaded report still says where it came from.

Each report is a single self-contained file, so downloading and opening the HTML
is enough — there are no separate CSS or asset files to keep alongside it.

Note that a report embeds raw conda output, the channel under test and the path
to the conda executable. CI artifacts on a public repository are downloadable by
anyone, so don't point the suite at a channel whose URL carries a token.

## Configuration

Each knob is a CLI flag whose default is read from a `CONDA_E2E_*` env var, so
either form works (`pixi run pytest --conda-version=latest` or
`CONDA_E2E_CONDA_VERSION=latest pixi run pytest`):

| Flag              | Env var                   | Default                  | Purpose                                                              |
| ----------------- | ------------------------- | ------------------------ | -------------------------------------------------------------------- |
| `--conda`         | `CONDA_E2E_CONDA`         | `conda` on `PATH`        | The conda under test (name or path).                                 |
| `--conda-version` | `CONDA_E2E_CONDA_VERSION` | _(unset → no update)_    | Update base conda before tests: `latest` or a version like `26.5.2`. |
| `--conda-channel` | `CONDA_E2E_CONDA_CHANNEL` | `conda-canary/label/dev` | Channel/label to install conda from.                                 |

When `--conda-version` is set, the suite runs `conda install -n base
<channel>::conda[=<version>]` **once before the tests**. This mutates the real
`base` conda on the host (not the per-test sandbox), so use it on CI or
throwaway environments. If unset - nothing is installed and the existing conda is
used as-is.

```bash
# newest canary/dev build — the usual choice
pixi run test --conda-version=latest

# a specific build, if it is published on the channel
pixi run test --conda-version=26.5.2

# release candidate for the 26.5.x line (when available)
pixi run test --conda-version=latest --conda-channel=conda-canary/label/conda/conda/rc/26.5.x
```

Any channel/label works via `--conda-channel` as long as the `conda` package is
actually published there. Otherwise conda reports `PackagesNotFoundInChannelsError`.

Don't set the other `CONDA_*` variables (`CONDA_PKGS_DIRS`, `CONDARC`, …): the
sandbox fixtures set them **per test**, and several are themselves part of what's
under test.

## Writing tests

Three per-test, sandboxed fixtures drive the conda under test:

- `conda` — run conda directly without shell integration (auto-confirms prompts, accepts channel ToS).
- `conda_no_tos` — like `conda` but without ToS auto-accept, to test that gate.
- `conda_shell` — run conda through each available shell. Use
  `conda_shell.run_in_activated_env(env, *commands)` when you need to run conda commands against the activated environment.

Every call returns a `CommandResult` (with helpers like `.assert_ok()`, `.assert_error()`, etc).
Every call is also recorded automatically and attached to that test's row in the HTML report, so
tests need not print or log commands themselves.
Parse output into typed results with the `from_json` / `from_stdout` classmethods on a corresponding data object like `EnvList`, `PackageList`, etc.

```python
def test_create_env(conda):
    name = unique_env_name()
    conda("create", "-n", name).assert_ok()
    command_result = conda("env", "list", "--json").assert_ok()
    assert name in EnvList.from_json(command_result)
```

## Project layout

```text
root/
├── src/conda_e2e/             # Reusable, pytest-agnostic framework
│   ├── runner.py              # CliRunner — run conda as a subprocess, capture result
│   │                          #   (observe_results — subscribe to every result produced)
│   ├── update.py              # Update the base conda under test to a chosen version
│   ├── shells.py              # CondaShellRunner, Shell — drive conda through a shell
│   ├── result.py              # CommandResult — exit code + stdout/stderr, with assertions
│   ├── utils.py               # Service-agnostic helpers (unique_env_name, platform flags, …)
│   └── parsers/               # Turn stdout or --json into typed results
│
├── tests/
│   ├── conftest.py            # Per-test fixtures, plus the HTML report wiring
│   ├── harness/               # Tests of the harness itself (no conda needed)
│   ├── data/                  # Static test inputs (condarc files, fixtures read at runtime, etc.)
│   └── e2e/                   # The tests, one directory per command group
│       ├── env/
│       ├── activate/
│       └── ...
│
├── reports/                   # Generated HTML test report (git-ignored)
├── pyproject.toml             # ruff + pytest config
├── pixi.toml                  # harness environment + dev-tool tasks
├── pixi.lock                  # pinned harness dependencies
├── .pre-commit-config.yaml    # git hooks
├── README.md
└── LICENSE
```

## Linting & formatting

[ruff](https://docs.astral.sh/ruff/) handles linting and formatting, wired through
[prek](https://github.com/j178/prek). ruff runs
from the pixi env — the pre-commit hooks invoke `pixi run ruff`, so there's a single
ruff version everywhere.

Hook definitions live in `.pre-commit-config.yaml`.
[ruff](https://docs.astral.sh/ruff/)'s own rules live in `[tool.ruff]` in `pyproject.toml`.

```bash
# verify only, no writes (ruff check + ruff format --check)
pixi run check

# fix everything: ruff check --fix + ruff format + hygiene hooks
pixi run fix
```

CI runs `pixi run check` as a gate before the test matrix (the `lint` job in
`.github/workflows/e2e-tests.yml`). The installed git hook runs the full pre-commit
suite on commit.

## License

BSD-3-Clause (see the SPDX headers in the source files).
