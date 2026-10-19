# Plan: conda config `--set` and `--add` E2E tests (inventory IDs 93–95, 99–100, 114)

## Goal

Automate six `Highest`-priority, currently-unautomated inventory rows in
`tests/inventory/commands.csv` by extending `tests/e2e/config/test_config.py`:

| IDs | Row |
|-----|-----|
| 93–95 | `conda config --set channel_priority strict / flexible / disabled` |
| 99–100 | `conda config --set solver classic / libmamba` |
| 114 | `conda config --add channels conda-forge` |

## Context / decisions already made

- Write-side counterpart of the existing read-side pattern (`covers(57/58)`
  parametrized tests that write `condarc` directly). The new tests drive the
  change through the public CLI and read back with `ConfigShow` — that is the
  behavioral contrast: `--set`/`--add` must persist to `$CONDARC` (sandboxed via
  the `condarc` fixture) and be visible to a separate conda process.
- `--add` is an **alias for `--prepend`** (front of list, not append). Row 114's
  assertion must prove prepend semantics by ordering, not by a hardcoded list.
- Expected values derive from a second public-CLI observation, never from
  conda's implementation or a guessed default.
- `ConfigShow` (src/conda_e2e/parsers/config.py) lacks a `solver` accessor; add
  a typed `solver` property next to `channel_priority` instead of rereading raw
  JSON in tests.

## Tasks (ordered)

1. **Confirm real CLI behavior first (blocks everything else).**
   - Run `conda config --describe solver` and a sandboxed
     `conda config --set solver classic` / `libmamba`; fix the parametrized
     values from what the CLI actually accepts before writing assertions.
   - Run a sandboxed `conda config --show channels --json` on an empty
     `condarc` to see what the effective initial list looks like (no hardcoding
     in the test either way).

2. **Parser: add `solver` to `ConfigShow`** in `src/conda_e2e/parsers/config.py`:

   ```python
   @property
   def solver(self) -> str | None:
       """The configured ``solver``."""
       return self.values.get("solver")
   ```

   No other parser changes.

3. **Rows 93–95 — parametrized `--set channel_priority` round-trip** (Positive
   test cases, near the existing channel_priority tests):

   ```python
   @pytest.mark.covers(93, 94, 95)
   @pytest.mark.parametrize("priority", ["strict", "flexible", "disabled"])
   def test_config_set_channel_priority(conda, condarc, priority):
       """``conda config --set channel_priority <p>`` persists the value."""
       conda("config", "--set", "channel_priority", priority).assert_ok()
       result = conda("config", "--show", "channel_priority", "--json").assert_ok()
       assert ConfigShow.from_json(result).channel_priority == priority
   ```

4. **Rows 99–100 — parametrized `--set solver` round-trip** (same shape, values
   fixed by task 1):

   ```python
   @pytest.mark.covers(99, 100)
   @pytest.mark.parametrize("solver", ["classic", "libmamba"])  # confirm via --describe
   def test_config_set_solver(conda, condarc, solver):
       """``conda config --set solver <s>`` persists the solver choice."""
       conda("config", "--set", "solver", solver).assert_ok()
       result = conda("config", "--show", "solver", "--json").assert_ok()
       assert ConfigShow.from_json(result).solver == solver
   ```

5. **Row 114 — `--add channels` proves prepend semantics with derived initial
   list** (near the existing channels tests):

   ```python
   @pytest.mark.covers(114)
   def test_config_add_channels_prepends_conda_forge(conda, condarc):
       """``conda config --add channels conda-forge`` prepends to the channel list.

       ``--add`` is an alias for ``--prepend``: the added channel must land at the
       front, ahead of the initial effective list, whatever that list is.
       """
       initial = ConfigShow.from_json(
           conda("config", "--show", "channels", "--json").assert_ok()
       ).channels

       conda("config", "--add", "channels", "conda-forge").assert_ok()

       after = ConfigShow.from_json(
           conda("config", "--show", "channels", "--json").assert_ok()
       ).channels
       assert after == ["conda-forge", *initial], (
           f"--add must prepend; got {after}, initial was {initial}"
       )

       # Persistence: the change landed in the sandbox .condarc file itself.
       sources = ConfigSources.from_stdout(
           conda("config", "--show-sources").assert_ok()
       )
       assert sources.has_source(condarc)
       assert sources.channels(condarc) == ["conda-forge"]
   ```

   Note: the file-source assertion reads the *persisted* condarc content
   (conda-forge only — `--add` writes to `$CONDARC`, which starts empty), while
   the effective-list assertion proves prepend ordering. Do not conflate the two.

## Validation

1. Run the narrowest new test first, then the whole module:
   `pytest tests/e2e/config/test_config.py` (sandboxed; uses project pixi env —
   note the checkout's `.venv` is broken, use `pixi run pytest ...`).
2. `pixi run coverage` to regenerate `COVERAGE.md` / `docs/coverage-*.svg` and
   rewrite the inventory `automated` column — the six rows must flip to `Yes`
   and the `conda config` row must rise accordingly.
3. `pixi run check` (ruff check + format).
4. Pure additions to one module: no `--collect-only` reconciliation needed, but
   confirm collection counts grow by exactly the new cases (3 + 2 + 1).

## Risks / notes

- Mutation risk is limited to the sandboxed `$CONDARC` via the public CLI; no
  host config, cache, envs, and no `update_conda` exception.
- If `--set solver` rejects a value on the conda build under test, that is a
  real behavioral finding — record it and adjust the parametrization to accepted
  values only (rejected-value negative cases are a separate ledger row).
- Banner order in the module stays `Positive test cases` → `Edge cases` →
  `Negative test cases`; all new tests go inside the existing Positive section.
