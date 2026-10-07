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
@pytest.mark.covers(487, 488)
def test_package_name_target_creates_archive(conda, make_env, tmp_path):
    env_name, _ = make_env()
    conda("package", "-n", env_name, "--pkg-name", "demo", "--pkg-version", "1.0").assert_ok()
```

A simplified version of the real test in `tests/e2e/package/test_package.py`: it claims
487 (`--pkg-name`/`--pkg-version`) and 488 (`-n <env name>`) because it exercises both.

Mapping is many-to-many: one test may cover several cases, and one case may need
several tests.

The bar for claiming a case is that the test **exercises** the behaviour. A `--help`
test that asserts `--json` appears in the help output covers the `--help` case only —
being documented is not being tested. Claiming it anyway inflates the coverage number,
which is the one thing that makes the whole report worthless.

A test with no matching inventory row should stay unmarked; `COVERAGE.md` lists those
separately so they can be linked or turned into new rows later. Don't invent an `id` to
silence the list.

A test marked `@pytest.mark.skip` never runs, so it doesn't count: its `covers` IDs
are ignored and it isn't listed as unmarked either. Tests skipped only on some platforms
with `@pytest.mark.skipif` still count, because they run on the others.

## Regenerating

The `coverage-report` pre-commit hook does this for you: committing a change under
`tests/` (or to the generator) regenerates `COVERAGE.md`. If the numbers moved or the `automated`
column changed, the hook rewrites the files and stops the commit. Review and stage the
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
chart that `COVERAGE.md` and the top-level `README.md` embed. Both are generated and
must be committed alongside the report; two files exist because GitHub strips media queries inside an SVG, so a
`<picture>` element with `prefers-color-scheme` is the only reliable way to theme it.
That keys off the *OS* setting, so a reader whose GitHub theme differs from their OS
theme sees the other variant — legible either way, just not matched.

The `lint` CI job backs the hook up: it runs `pixi run coverage` and fails if any
generated file differs from what was committed, so a stale report that slipped past
`git commit --no-verify`, or a clone without `pixi run prek install`, still fails the PR.
