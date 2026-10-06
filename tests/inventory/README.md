# Command inventory

`commands.csv` is the hand-written inventory of conda CLI cases this suite aims to
automate. It is the **denominator** for [`COVERAGE.md`](../../COVERAGE.md): a case
counts as automated when some test claims its `id`.

| Column | Meaning |
| --- | --- |
| `id` | Permanent identifier. See the rule below. |
| `group` | Subcommand the case belongs to, e.g. `conda install`. |
| `command` | The invocation the case describes. |
| `priority` | `Highest` / `High` / `Medium` / `Low` / `Lowest`. |
| `expected` | What the command is expected to do. |
| `automated` | **Generated.** `Yes` when some test claims the row, else `No`. |

## `id` values are permanent

**Never renumber, never reuse, never reorder-and-renumber.** IDs are referenced from
`@pytest.mark.covers(...)` across the suite; changing one silently re-points every
marker that cites it at a different command. Nothing catches that — the tests still
pass and the coverage number still looks plausible, it just attributes the wrong test
to the wrong case.

This is not hypothetical. The inventory was imported from a spreadsheet whose `Sl. No.`
column was a row *position*: new cases had been inserted mid-sheet and everything below
them renumbered. That is exactly the failure this rule exists to prevent, which is why
the CSV — not the spreadsheet — is now the source of truth.

So:

- **Adding a case?** Append the next unused integer. It does not need to sit next to its
  group in the file; `id` order and `group` order are independent.
- **Case no longer meaningful?** Delete the row and leave the number retired. Gaps are
  fine and expected.
- **Fixing a typo** in `command`, `priority` or `expected` is always safe.

## Linking a test to a case

```python
@pytest.mark.covers(492, 495)
def test_package_metadata_flags_set_archive_name(conda, make_env):
    conda("package", "--pkg-name", "demo", "--pkg-version", "1.0").assert_ok()
```

Mapping is many-to-many: one test may cover several cases, and one case may need
several tests.

The bar for claiming a case is that the test **exercises** the behaviour. A `--help`
test that asserts `--json` appears in the help output covers the `--help` case only —
being documented is not being tested. Claiming it anyway inflates the coverage number,
which is the one thing that makes the whole report worthless.

### Automatic markers

`pixi run coverage` (and so the pre-commit hook) also **writes** markers. For each
test with no `covers` marker, it reads the test's own `conda(...)` calls and claims
an inventory row only when a call:

- lives under `tests/e2e/<sub>/` matching the row's group, and has the row's
  subcommand;
- is checked with `.assert_ok()`, or with `.assert_error()` when the row's
  `expected` starts with `Fails` or `Invalid` (so a test only ever claims cases
  with the same outcome);
- has **exactly** the row's flags, ignoring `-y`, and ignoring `-n`/`-p` unless the
  row names them;
- uses any value the row spells out literally (`--file explicit.txt`,
  `--show channels`), and any package the row names.

Success rows with no flags beyond `-n`/`-p`/`-y` (e.g. `conda install -n <env> <pkg>`)
are never auto-claimed, since every test's setup calls look like them. Failure rows
are stricter instead: the subcommand must match exactly (`conda env <unknown
subcommand>` is not `conda env remove`), and a row whose only flag is a lone `-n` or
`-p` (e.g. `conda list -n <nonexistent env>`) is never claimed, because the failure
lies in the value. Calls built from non-parametrized variables (`conda(*args)`) are
skipped, and so are tests that don't call the `conda` fixture (e.g. `conda_shell`
activation tests).

Tests that already carry a marker are left alone, so a hand-written marker always
wins. The matcher favours misses over false claims, so most tests still need marking
by hand. Review what it prints (`marked <test> -> covers(...)`) before committing,
and if a claim is wrong, add the correct marker by hand: a test that already has a
marker is never matched again.

A test with no matching inventory row should stay unmarked; `COVERAGE.md` lists those
separately so they can be linked or turned into new rows later. Don't invent an `id` to
silence the list.

## Regenerating

The `coverage-report` pre-commit hook does this for you: committing a change under
`tests/` (or to the generator) regenerates `COVERAGE.md`. If the numbers moved, or it added markers
to test files or changed the `automated` column, the hook rewrites them and stops the commit. Review and stage the
changes, then commit again.

To run it by hand:

```bash
pixi run coverage
```

Either way it **fails** if a marker cites an `id` that is not in this file, and only
collects tests — it never runs them, so no conda under test is needed.

It also rewrites the `automated` column of `commands.csv` to match the markers, so
don't edit that column by hand (or in the spreadsheet you copy it into): the next run
overwrites it. Every other column, and the row order, are left untouched.

It also rewrites `docs/coverage-light.svg` and `docs/coverage-dark.svg`, the by-priority
chart `COVERAGE.md` embeds. Both are generated and must be committed alongside the
report; two files exist because GitHub strips media queries inside an SVG, so a
`<picture>` element with `prefers-color-scheme` is the only reliable way to theme it.
That keys off the *OS* setting, so a reader whose GitHub theme differs from their OS
theme sees the other variant — legible either way, just not matched.

Note the hook is the only thing keeping `COVERAGE.md` current; there is no CI check.
`git commit --no-verify`, or a clone without `pixi run prek install`, will let a stale
report through.
