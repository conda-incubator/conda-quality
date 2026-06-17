# conda E2E Test Automation

Black-box, end-to-end tests for the **conda CLI**. The suite runs a real `conda`
executable as a subprocess and asserts on its `stdout` / `stderr` / exit code
plus the on-disk state. The conda under test is whatever is on `PATH`, or whatever
`CONDA_E2E_CONDA` points to.

## Requirements

- Python **3.10+** (3.13 recommended for local development)
- A `conda` executable on `PATH`, or `CONDA_E2E_CONDA` set to its full path

The harness that *runs* the tests is intentionally separate from the conda it
*drives*. Install conda the normal way rather than `pip install conda`.

## Installation

The framework is run, not installed — there is no `pip install -e .`. Create a
virtual environment and install the harness dependencies; pytest adds `src/` to
the import path automatically (`pythonpath = ["src"]` in `pyproject.toml`).

```bash
python3.13 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Running the tests

```bash
# Run all tests
pytest -v
# Run only "env" test suite
pytest tests/e2e/env -v
# Run specific test module
pytest tests/e2e/env/test_env_crud.py::test_remove_missing_env_fails -v
```

A bare `pytest` runs everything, including tests that download packages from a
real channel. Shell-integration tests (`activate` / `init` / hooks) fan out
across the shells available on the current OS (bash/zsh on Unix, cmd/PowerShell
on Windows) and skip the rest.

## Configuration

Set `CONDA_E2E_CONDA` to the full path of the conda build you want to exercise;
it defaults to `conda` on `PATH`. The other `CONDA_*` variables conda reads
(`CONDA_PKGS_DIRS`, `CONDARC`, …) are set **per test** by the sandbox fixtures —
don't set them globally, since several are themselves part of what's under test.

## Project structure

`src/conda_e2e/` is the reusable, pytest-agnostic framework: the subprocess
runner (`CliRunner`/`ShellRunner`), the `CommandResult` type, output parsers
(`parsers/`, which turn a command's stdout into typed results), and small shared
helpers (`utils`). Per-test sandboxing of conda's state lives in the fixtures
(`tests/conftest.py`). The conda tests live under `tests/e2e/`, one directory per
command group (e.g. `env/`, `activate/`).

## Linting & formatting

[ruff](https://docs.astral.sh/ruff/) handles linting and formatting, wired
through [prek](https://github.com/j178/prek) (a drop-in `pre-commit` replacement
that reads the same config).

```bash
ruff check .          # lint
ruff format .         # format
prek install          # install git hooks
prek run --all-files  # run all hooks
```

## License

BSD-3-Clause (see the SPDX headers in the source files).
