# Cross-Tool AI Instructions Plan

## Goal

Support GitHub Copilot, Claude Code, and Kilo Code from one team-owned instruction source without
hand-maintained copies or platform-dependent symlinks.

Keep `.github/copilot-instructions.md` and `.github/instructions/` canonical. Generate any required
tool-specific adapters deterministically and validate them in CI.

## Phase 1: Canonical Source and Adapters

1. Treat `.github/copilot-instructions.md` as the only canonical repository-wide instruction body
   and `.github/instructions/*.instructions.md` as the only canonical scoped rule bodies.
2. Preserve both `applyTo` and `paths` metadata in each canonical scoped file so the same source
   describes Copilot and Claude Code scope.
3. Add an explicit applicability sentence near the start of each scoped rule body. Derive it from
   the file's description and path patterns so agents that ignore YAML path metadata can still decide
   whether the rule applies. Keep examples generic and explicitly illustrative.
4. Replace the `.claude/rules -> ../.github/instructions` directory symlink with generated regular
   files under `.claude/rules/`. Generate them byte-for-byte from `.github/instructions/` to preserve
   Claude Code's native `paths` behavior without requiring Windows Developer Mode or Git symlink
   support.
5. Keep `CLAUDE.md` as a thin Claude Code entry point that imports
   `@.github/copilot-instructions.md` and contains only genuinely Claude-specific additions.
6. Add a project `kilo.jsonc` that loads `.github/copilot-instructions.md`. Do not create a second
   hand-maintained `.kilo/rules/` tree. Verify Kilo's Claude compatibility behavior against the
   installed version before relying on `.claude/rules/`; otherwise list generated Kilo adapters
   explicitly in `kilo.jsonc`.

## Phase 2: Deterministic Synchronization

1. Add a Python 3.10-compatible utility at `tools/sync_ai_instructions.py` that recreates
   `.claude/rules/` from `.github/instructions/` in stable filename order.
2. Give the utility a read-only `--check` mode and make it reject unknown files in generated
   directories. Use exact copying or structured frontmatter handling, not ad hoc text replacement.
3. Expose sync and check commands through the repository's existing task convention in
   `pixi.toml` or `pyproject.toml`.
4. Add the check to CI and, if appropriate, `.pre-commit-config.yaml`. A pull request must fail when
   canonical rules change without regenerated adapters.
5. Document the ownership contract for contributors:
   - Edit only `.github/copilot-instructions.md` and `.github/instructions/`.
   - Run the synchronization task after changing scoped rules.
   - Never edit generated `.claude/rules/` files directly.
   - Keep credentials and personal Kilo or Claude settings outside tracked project configuration.

## Phase 3: Cross-Tool Workflow Assets

Audit prompts and skills separately from always-loaded instructions. If the same E2E testing workflow
must work in all three tools, make `.agents/skills/write-conda-e2e-tests/SKILL.md` canonical and add
only the discovery adapters each tool requires. Kilo loads `.agents/skills/` directly.

Do not place on-demand workflow content in always-loaded repository rules.

## Relevant Files

- `.github/copilot-instructions.md`: canonical repository-wide instructions.
- `.github/instructions/*.instructions.md`: canonical scoped rules with `applyTo` and `paths`.
- `CLAUDE.md`: thin Claude Code import wrapper.
- `.claude/rules/`: generated Claude Code compatibility output.
- `kilo.jsonc`: tracked Kilo project configuration without credentials.
- `tools/sync_ai_instructions.py`: proposed generation and drift-check utility.
- `pixi.toml` or `pyproject.toml`: proposed sync and check tasks.
- `.github/workflows/` and `.pre-commit-config.yaml`: synchronization enforcement.
- `.claude/skills/write-conda-e2e-tests/SKILL.md` and `.github/prompts/`: existing tool-specific
  workflow assets to evaluate during phase 3.

## Verification

1. Run the synchronization utility twice and confirm the second run produces no changes. Run
   `--check` and confirm it succeeds.
2. On macOS, Linux, and Windows CI, verify `.claude/rules/` contains regular generated files and does
   not require symlink support.
3. In Copilot, work with one parser file and one unrelated file. Confirm only matching
   `.github/instructions/` rules are applied.
4. In Claude Code, run `/context`. Confirm `CLAUDE.md`, its imported root instructions, and only
   path-matching `.claude/rules/` files load.
5. In Kilo, start a new session or run `/reload`, inspect loaded rules, and confirm each intended rule
   appears exactly once. Test one parser task and one unrelated task to confirm applicability wording
   prevents irrelevant rules from being followed.
6. Modify one generated Claude rule deliberately and verify the synchronization check fails. Restore
   it by regenerating and verify the check passes.
7. Run Markdown diagnostics and repository lint or formatting checks applicable to the new script and
   configuration.

## Decisions

- Canonical ownership remains under `.github/` because Copilot requires those native locations and
  the repository already uses them.
- Generated regular files replace directory symlinks for reliable Windows checkouts and reviewable
  diffs.
- Kilo uses project `kilo.jsonc`; do not add a legacy `.kilocode/rules/` tree or another manually
  maintained rule set.
- Do not add `AGENTS.md` initially because Copilot and Kilo may load it alongside native instructions,
  duplicating context. Reconsider it only when supporting another tool that requires the open
  standard.
- Keep tool permission and settings files tool-specific. Share behavioral instructions, not permission
  models.
- Treat skills and prompts as on-demand workflows, separate from always-loaded repository rules.
