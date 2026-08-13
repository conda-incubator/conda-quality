# TODO

## Simplify `conda info` Assertions

**Status:** Completed after [PR #27](https://github.com/conda-incubator/conda-quality/pull/27)
was merged.

**Source:** [Review comment](https://github.com/conda-incubator/conda-quality/pull/27#discussion_r3725459710)

Review the assertions in `tests/e2e/info/info_asserts.py` and the tests that compose them. Split
assertions that cover multiple independent contracts into smaller, clearly named checks where that
improves readability and failure diagnosis. Complete this work in a separate PR, as requested by the
reviewer.

### Scope

1. Inventory each assertion helper and all call sites in the `conda info` tests.
2. Identify overloaded, duplicate, transitive, weaker, or conflicting assertions.
3. Split only helpers that combine genuinely independent contracts; keep cohesive relationships
   together.
4. Preserve observable coverage and avoid changing public behavior under test.
5. Run the focused `conda info` suite and repository lint and formatting checks.

### Completion Criteria

- PR #27 and its follow-up changes are merged before implementation begins.
- Each helper has one clear contract and useful pytest failure diagnostics.
- No assertion coverage is lost or duplicated through helper composition.
- The complete `conda info` test suite and `pixi run check` pass.

## Verify `conda info` Root Writability

**Status:** Semantics unverified. The existing JSON test asserts only that the field is boolean.
No portable, public, non-mutating setup can independently establish the expected writability state.

**Source:** [Review comment](https://github.com/conda-incubator/conda-quality/pull/27#discussion_r3716407052)

Analyze how to validate the public `root_writable` field independently. PR #27 intentionally checks
only that the field is boolean because a host-side permission probe does not necessarily match
conda's writability semantics. Add the semantic coverage as a separate test and PR after determining
a reliable, portable setup and oracle.

### Scope

1. Confirm the documented meaning and observed behavior of `root_writable` through the public conda
   CLI across supported platforms.
2. Find a disposable setup that creates an observable writable/non-writable contrast without
   changing permissions or state in the user's real conda installation or base environment.
3. Derive the expected result independently rather than reproducing conda's implementation in the
   test.
4. Add a focused test for every safely controllable state and retain the boolean type assertion for
   uncontrolled installations.
5. If a portable independent check is not feasible, document the field's semantics as unverified
   and the exact platform or fixture support needed to close the gap.

### Validation Note

#### Observed Semantics

Conda's current implementation treats `root_writable` as true only when
`<root_prefix>/conda-meta/history` exists and can be opened for append. This was confirmed with a
real conda executable pointed at disposable directories: a writable history file reported `true`,
a read-only history file reported `false`, and a missing history file reported `false`.

This knowledge explains why a general host-side directory-permission probe would be a weaker and
potentially misleading oracle. It is implementation knowledge rather than a documented `conda info`
contract, so the suite must not copy this condition into an expectation.

#### Rejected Setup

The `root_prefix`/`root_dir` configuration can redirect conda to throwaway paths and make the three
states above easy to reproduce. However, conda classifies this setting as hidden and undocumented:
it is absent from `conda config --describe`, has no public compatibility guarantee, and is not an
acceptable black-box test interface. Using it would couple this suite to a private configuration
path and to the implementation-derived oracle described above.

#### Required Future Fixture

A valid public test would need a complete working conda installation at a disposable location,
invoked through that installation's own public executable. The fixture would need to create both
writable and non-writable installation states without modifying the selected conda installation,
its base environment, or its package cache. Relocating or copying a full installation is presently
impractical and fragile across platforms because of installation size, relocatability, and embedded
paths; this repository has no established fixture for it.

Until a portable, non-mutating fixture exists, the boolean assertion in `test_conda_info_json`
remains the appropriate coverage. Writability semantics are explicitly unverified on every platform.

#### Archived Experiment (Do Not Restore As Coverage)

The following removed test draft is retained as a record of the explored setup. It created a
disposable environment containing conda, invoked that environment's `python -m conda info --json`,
and removed write bits from every path in the environment. It passed locally on macOS, but its
expected values come from controlled filesystem permissions rather than a documented public
`root_writable` contract. Do not restore it unless a public, independent oracle and portable fixture
are established.

```python
import stat


def test_conda_info_reports_disposable_writable_root(conda, tmp_path):
   """``root_writable`` is true for a newly created disposable conda installation."""
   root_prefix = tmp_path / "disposable-conda"
   conda("create", "--prefix", root_prefix, "conda").assert_ok()

   info = CondaInfo.from_json(
      conda(
         "run", "--prefix", root_prefix, "python", "-m", "conda", "info", "--json"
      ).assert_ok()
   )

   assert is_same_path(info.root_prefix, root_prefix)
   assert info.root_writable


@pytest.mark.skipif(
   IS_WINDOWS,
   reason="Windows does not provide a portable, deterministic read-only conda installation setup",
)
def test_conda_info_reports_read_only_disposable_root(conda, tmp_path):
   """``root_writable`` is false when every file in a disposable root is read-only."""
   root_prefix = tmp_path / "read-only-conda"
   conda("create", "--prefix", root_prefix, "conda").assert_ok()

   original_modes = {
      path: stat.S_IMODE(path.stat().st_mode) for path in (root_prefix, *root_prefix.rglob("*"))
   }
   for path, mode in original_modes.items():
      path.chmod(mode & ~0o222)

   try:
      info = CondaInfo.from_json(
         conda(
            "run", "--prefix", root_prefix, "python", "-m", "conda", "info", "--json"
         ).assert_ok()
      )
   finally:
      for path, mode in original_modes.items():
         path.chmod(mode)

   assert is_same_path(info.root_prefix, root_prefix)
   assert not info.root_writable
```

### Completion Criteria

- PR #27 and its follow-up changes are merged before implementation begins.
- The test fails when conda reports the wrong writability state for the controlled setup.
- The test never mutates the selected conda installation, package cache, or base environment.
- Platform-specific permission behavior is covered by CI or reported explicitly as unverified.
- The focused `conda info` test and `pixi run check` pass.
