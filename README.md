# conda E2E Test Automation

[![E2E tests](https://github.com/conda-incubator/conda-quality/actions/workflows/e2e-tests.yml/badge.svg)](https://github.com/conda-incubator/conda-quality/actions/workflows/e2e-tests.yml)
[![nightly](https://github.com/conda-incubator/conda-quality/actions/workflows/nightly.yml/badge.svg)](https://github.com/conda-incubator/conda-quality/actions/workflows/nightly.yml)

Black-box, end-to-end tests for the **conda CLI**. The suite runs a real `conda`
executable as a subprocess and asserts on its `stdout` / `stderr` / exit code and
the on-disk state it produces. The conda under test is whatever is on `PATH`, or
whatever `CONDA_E2E_CONDA` points to.

## Requirements

- Python **3.10+**
- A `conda` executable on `PATH`, or `CONDA_E2E_CONDA` set to its full path

The harness that _runs_ the tests is separate from the conda it _drives_ — install
conda the normal way, not via `pip install conda`.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

We deliberately use Python's own `venv` and `pip` rather than conda to set up the
harness, since conda is the thing under test. Keeping the harness off conda means
its environment can't interfere with (or be broken by) the conda it drives.

## Running the tests

```bash
# Run all tests
pytest
# Run only "env" test suite
pytest tests/e2e/env
# Run specific test module
pytest tests/e2e/env/test_env_crud.py::test_remove_missing_env_fails
```

Shell-integration tests (activate / hooks) run once per shell found on the current OS — bash, zsh, sh, and PowerShell on Unix; cmd and PowerShell on Windows. Shells that aren't
installed are skipped.

These commands run against whatever `conda` is on `PATH`. To point the suite at a
different conda, or update it to a specific version first, see
[Configuration](#configuration) — its flags combine with any of the above (e.g.
`pytest tests/e2e/env --conda-version=latest`).

## Configuration

Each knob is a CLI flag whose default is read from a `CONDA_E2E_*` env var, so
either form works (`pytest --conda-version=latest` or
`CONDA_E2E_CONDA_VERSION=latest pytest`):

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
pytest --conda-version=latest
# a specific build, if it is published on the channel
pytest --conda-version=26.5.2
# release candidate for the 26.5.x line (when available)
pytest --conda-version=latest --conda-channel=conda-canary/label/conda/conda/rc/26.5.x
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
│   ├── update.py              # Update the base conda under test to a chosen version
│   ├── shells.py              # CondaShellRunner, Shell — drive conda through a shell
│   ├── result.py              # CommandResult — exit code + stdout/stderr, with assertions
│   ├── utils.py               # Service-agnostic helpers (unique_env_name, platform flags, …)
│   └── parsers/               # Turn stdout or --json into typed results
│
├── tests/
│   ├── conftest.py            # Per-test fixtures
│   ├── data/                  # Static test inputs (condarc files, fixtures read at runtime, etc.)
│   └── e2e/                   # The tests, one directory per command group
│       ├── env/
│       ├── activate/
│       └── ...
│
├── pyproject.toml
├── requirements.txt
├── .pre-commit-config.yaml
├── README.md
└── LICENSE
```

## Linting & formatting

[ruff](https://docs.astral.sh/ruff/) handles linting and formatting, wired through
[prek](https://github.com/j178/prek) (a drop-in `pre-commit` replacement):

```bash
ruff check .          # lint
ruff format .         # format
prek install          # install git hooks
prek run --all-files  # run all hooks
```

## License

BSD-3-Clause (see the SPDX headers in the source files).
