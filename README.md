# conda E2E Test Automation

Black-box, end-to-end tests for the **conda CLI**. The suite runs a real `conda`
executable as a subprocess and asserts on its `stdout` / `stderr` / exit code and
the on-disk state it produces. The conda under test is whatever is on `PATH`, or
whatever `CONDA_E2E_CONDA` points to.

## Requirements

- Python **3.10+**
- A `conda` executable on `PATH`, or `CONDA_E2E_CONDA` set to its full path

The harness that *runs* the tests is separate from the conda it *drives* — install
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

## Configuration

`CONDA_E2E_CONDA` is optional. The suite uses `conda` from `PATH` by default. Set
this variable to a full path only when the conda you want to exercise isn't on
`PATH` (or to pick a specific build over the one on `PATH`).

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
