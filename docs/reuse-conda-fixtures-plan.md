# Plan: Reusing conda/conda Fixtures in conda-quality

Source under consideration: https://github.com/conda/conda/tree/main/conda/testing
(specifically `conda/testing/fixtures.py`).

## Guiding decision

**Do not import `conda.testing.*`.** Doing so would:

- Violate this repo's black-box charter ("Test only public CLI behavior… do not
  import conda's Python internals").
- Add conda as a build/test dependency of the harness.
- Run conda **in-process** (via `main_subshell`/`context`) rather than as the real
  CLI, which is the entire point of this suite.

Instead: **port the internals-free patterns verbatim, and re-implement the useful
internals-bound fixtures as black-box (subprocess) equivalents in our harness.**

Licensing is not a blocker — both repos are BSD-3-Clause. Attribution in ported
code is the only obligation.

## Triage of conda's `fixtures.py`

### Reject — in-process / context-bound (incompatible with a subprocess suite)
`conda_cli`, `session_conda_cli`, `pip_cli`, `solver_classic`, `solver_libmamba`,
`solver_rattler`, `parametrized_solver_fixture`, `context_testdata`,
`reset_conda_context`, `context_aware_monkeypatch`, `PYTHONPATH`,
`clear_subdir_cache`, `clear_plugin_manager_cache`, `suppress_resource_warning`,
`suppress_pytest_bencher_deprecation_warning`.

Solver selection is already covered here via the `--solver` flag / env vars.

### Already covered by our harness
- `tmp_pkgs_dir`, `tmp_envs_dir` → `isolated_env_vars` sets `CONDA_PKGS_DIRS` /
  `CONDA_ENVS_DIRS`.
- `empty_env` → exists in `tests/conftest.py`.

### Port — no internals
- `path_factory` (`PathFactoryFixture`): unique, non-existent paths.
- `http_test_server`: stdlib `http.server`-based.

### Re-implement as black-box
- `tmp_env` / `empty_env` factory: shell out to `conda create`.
- `tmp_channel`: build a local channel via `conda index`.

## Mapping table

| conda fixture | Verdict | Our equivalent |
|---|---|---|
| `conda_cli` (in-process) | Reject — violates black-box charter | Existing `CliRunner` / `conda` fixture (subprocess) |
| `tmp_env` / `empty_env` | Re-implement black-box | Generalize `empty_env` into a `tmp_env(*packages)` factory |
| `path_factory` | Port ~verbatim (no internals) | New `path_factory` fixture → unique non-existent paths under `tmp_path` |
| `tmp_channel` | Re-implement black-box | Local channel via `conda index` subprocess |
| `tmp_pkgs_dir` / `tmp_envs_dir` | Already covered | `isolated_env_vars` sets `CONDA_PKGS_DIRS` / `CONDA_ENVS_DIRS` |
| `http_test_server` | Port (stdlib, no internals) | New fixture when a test needs a served channel |
| `solver_*`, `context_*`, `reset_context`, `PYTHONPATH` | Reject — in-process context manipulation | Set via env vars / `--solver` per call |
| `suppress_*_warning` | N/A — subprocess output isn't Python warnings | — |

## Phases

### Phase 0 — Confirm the boundary (no code)
- Read the real `PathFactoryFixture` and `http_test_server` source in
  `conda/testing/` so the black-box re-impl is faithful.
- Check `conda index --help` locally for the local-channel build signature.

### Phase 1 — Port `path_factory`
Add a pure-`pathlib` fixture to `tests/conftest.py` returning unique, non-existent
paths rooted at `tmp_path` (prefix / suffix / name params). No conda imports. This
is a genuine gap today (we only have `env_prefix` / `unique_env_name`).

### Phase 2 — Black-box `tmp_env` factory
Generalize `empty_env` into a `tmp_env(*packages)` fixture that shells out
(`conda create -n <unique> <packages...>` via the `conda` runner) and yields
`(name, prefix)`. Mirrors conda's `TmpEnvFixture` ergonomics with no imports.
Lives in `tests/conftest.py` (global).

### Phase 3 (defer until a test needs it) — Local channel `tmp_channel`
Create a package dir layout, run `conda index <dir>` as a subprocess, yield a
`file://` URL. Unblocks deterministic offline install tests and removes reliance
on mutable remote channels (which the instructions warn against).

### Phase 4 (defer) — `http_test_server`
Stdlib-based port; only if a test needs a channel served over HTTP rather than
`file://`.

Per the "don't add a fixture nothing exercises yet" rule, Phases 3–4 remain
deferred until a concrete test requires them.

## Explicitly NOT doing
- Importing `conda.testing.*`.
- Adding conda as a harness dependency.
- Adopting any `context` / `reset_context` / in-process fixture.
