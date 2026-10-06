# SPDX-License-Identifier: BSD-3-Clause
"""Generate COVERAGE.md: how much of the manual command inventory is automated.

This is *command* coverage, not code coverage — nothing here measures lines of
conda executed. The denominator is ``tests/inventory/commands.csv``, a hand-written
inventory of conda CLI cases. A case counts as covered when some test claims its
``id`` with ``@pytest.mark.covers(...)``.

Run via ``pixi run coverage``. Exits non-zero if a test claims an ``id`` that is
not in the inventory, so a typo'd or stale marker is loud rather than silently
inflating the numbers.

It also rewrites the inventory's ``automated`` column (``Yes``/``No``) to match.

Before reporting, unmarked tests are matched against the inventory and the
matching ``covers`` markers are written into the test files (see
``suggest_covers``).
"""

from __future__ import annotations

import ast
import csv
import inspect
import io
import re
import shutil
import subprocess
import sys
import textwrap
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent
E2E_ROOT = REPO_ROOT / "tests" / "e2e"
INVENTORY = REPO_ROOT / "tests" / "inventory" / "commands.csv"
#: Generated inventory column: ``Yes`` when some test claims the row.
AUTOMATED_COLUMN = "automated"
OUTPUT = REPO_ROOT / "COVERAGE.md"
CHART_DIR = REPO_ROOT / "docs"

# Worst-first, so the table reads as a priority queue rather than alphabetically.
PRIORITY_ORDER = ("Highest", "High", "Medium", "Low", "Lowest")

BAR_WIDTH = 20

# Chart geometry, in SVG user units.
LABEL_W = 78  # left gutter for priority names
PLOT_W = 440  # the plot area itself
VALUE_W = 140  # right gutter for "26/54  48%"
ROW_H = 30
BAR_H = 16
HEADER_H = 34  # legend strip
FOOTER_H = 22  # x-axis tick labels
CORNER_R = 4  # rounded data-end radius
SEGMENT_GAP = 2  # surface gap between the two stacked fills

# Slot-1 blue from the reference palette, re-stepped per mode rather than flipped.
# Both bar steps clear 3:1 against their own surface (validated for GitHub's
# #ffffff / #0d1117). The track is a same-ramp step that deliberately sits below
# 3:1 so it recedes; the relief rule is satisfied by the direct labels on every
# row plus the table view directly beneath the chart.
THEMES = {
    "light": {
        "bar": "#2a78d6",
        "track": "#cde2fb",
        "text": "#24292f",
        "muted": "#57606a",
        "grid": "#d0d7de",
    },
    "dark": {
        "bar": "#3987e5",
        "track": "#0d366b",
        "text": "#e6edf3",
        "muted": "#8b949e",
        "grid": "#30363d",
    },
}

FONT = "-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif"


@dataclass
class Case:
    """One row of the manual inventory."""

    id: int
    group: str
    command: str
    priority: str
    expected: str
    #: Test node IDs that claim this case; empty means not automated.
    covered_by: list[str] = field(default_factory=list)

    @property
    def covered(self) -> bool:
        """Whether at least one test claims this case."""
        return bool(self.covered_by)


class _CoversCollector:
    """Pytest plugin that records ``covers`` markers seen during collection."""

    def __init__(self) -> None:
        #: inventory id -> test node IDs claiming it
        self.claims: dict[int, list[str]] = defaultdict(list)
        #: tests carrying no ``covers`` marker at all
        self.unmarked: set[str] = set()
        #: unmarked node -> its collected items (one per parametrization)
        self.unmarked_items: dict[str, list[pytest.Item]] = defaultdict(list)

    def pytest_collection_modifyitems(self, items: list[pytest.Item]) -> None:
        """Read markers off every collected item."""
        for item in items:
            # Strip the [param] suffix: a parametrized test is one test for our
            # purposes, and its 4 shell variants shouldn't look like 4 claims.
            node = item.nodeid.partition("[")[0]
            ids = [i for marker in item.iter_markers("covers") for i in marker.args]
            if not ids:
                self.unmarked.add(node)
                self.unmarked_items[node].append(item)
                continue
            for case_id in ids:
                if node not in self.claims[case_id]:
                    self.claims[case_id].append(node)


def load_inventory() -> list[Case]:
    """Read the inventory CSV, newest-numbered last.

    Returns:
        Every inventory case, in ``id`` order.

    Raises:
        SystemExit: if the CSV is missing.
    """
    if not INVENTORY.is_file():
        sys.exit(f"inventory not found: {INVENTORY}")
    with INVENTORY.open(newline="") as fh:
        cases = [
            Case(
                id=int(row["id"]),
                group=row["group"],
                command=row["command"],
                priority=row["priority"],
                expected=row["expected"],
            )
            for row in csv.DictReader(fh)
        ]
    return sorted(cases, key=lambda c: c.id)


def write_automated_column(cases: list[Case]) -> bool:
    """Set the inventory's ``automated`` column from the claims, in place.

    The column is generated, like ``COVERAGE.md``: hand edits are overwritten.
    Row order and every other column are left exactly as they are.

    Returns:
        Whether the file changed.
    """
    covered = {c.id for c in cases if c.covered}
    with INVENTORY.open(newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    if AUTOMATED_COLUMN not in fieldnames:
        fieldnames.append(AUTOMATED_COLUMN)
    for row in rows:
        row[AUTOMATED_COLUMN] = "Yes" if int(row["id"]) in covered else "No"
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    text = out.getvalue()
    if INVENTORY.read_text() == text:
        return False
    INVENTORY.write_text(text)
    return True


def collect_claims() -> _CoversCollector:
    """Collect ``covers`` markers from the suite without running any tests.

    Returns:
        The populated collector.

    Raises:
        SystemExit: if pytest collection fails, since partial collection would
            undercount coverage and quietly report the wrong number.
    """
    collector = _CoversCollector()
    # `-o addopts=` drops the suite's default flags: they write an HTML report,
    # which would be a surprising side effect of computing coverage. --strict-markers
    # is re-added on its own so a misspelled marker name still fails here.
    args = [
        "--collect-only",
        "-q",
        "-o",
        "addopts=",
        "--strict-markers",
        "-p",
        "no:cacheprovider",
        "--no-header",
    ]
    status = pytest.main(args, plugins=[collector])
    if status not in (pytest.ExitCode.OK, pytest.ExitCode.NO_TESTS_COLLECTED):
        sys.exit(f"pytest collection failed (exit {status}); coverage numbers would be wrong")
    return collector


# --- automatic marker matching -------------------------------------------------
#
# A test is matched to an inventory row only when one of its own successful
# ``conda(...)`` calls has the row's subcommand and *exactly* the row's flag set.
# Exactness is what keeps this from inflating coverage: a ``--show channels``
# call must not also claim the bare ``--show`` row.

#: Any value: a ``<placeholder>`` in a row, or a non-literal argument in a test.
WILD = "\0wild"
#: ``expected`` prefixes marking a row whose command should fail
FAILURE_PREFIXES = ("Fails", "Invalid")
#: The suite runs non-interactively, so ``-y`` in a row is incidental.
NOISE_FLAGS = frozenset({"-y"})
#: Which env a call targets; only significant when the row names one itself.
TARGET_FLAGS = frozenset({"-n", "-p"})
#: Long spellings normalised to the short form the inventory mostly uses.
ALIASES = {
    "--name": "-n",
    "--prefix": "-p",
    "--channel": "-c",
    "--quiet": "-q",
    "--yes": "-y",
    "--verbose": "-v",
}
_WORD = re.compile(r"[a-z][a-z-]*")


@dataclass(frozen=True)
class _Invocation:
    """A conda command line reduced to its subcommand path and flags."""

    path: tuple[str, ...]
    #: (flag, value) pairs; value is a literal, ``WILD``, or ``None`` for none.
    flags: tuple[tuple[str, str | None], ...]
    #: positionals beyond the subcommand path (literals or ``WILD``)
    positionals: tuple[str, ...]


def _split(tokens: list[str]) -> _Invocation:
    """Reduce tokens (after ``conda``) to an invocation."""
    path: list[str] = []
    i = 0
    while i < len(tokens) and tokens[i] != WILD and _WORD.fullmatch(tokens[i]):
        path.append(tokens[i])
        i += 1
    flags: list[tuple[str, str | None]] = []
    positionals: list[str] = []
    while i < len(tokens):
        tok = tokens[i]
        if tok != WILD and tok.startswith("-"):
            flag, eq, inline = tok.partition("=")
            flag = ALIASES.get(flag, flag)
            if eq:
                flags.append((flag, inline))
            elif i + 1 < len(tokens) and not (
                tokens[i + 1] != WILD and tokens[i + 1].startswith("-")
            ):
                flags.append((flag, tokens[i + 1]))
                i += 1
            else:
                flags.append((flag, None))
        else:
            positionals.append(tok)
        i += 1
    return _Invocation(tuple(path), tuple(flags), tuple(positionals))


def parse_inventory_command(command: str) -> _Invocation | None:
    """Parse an inventory ``command`` cell, or ``None`` if it isn't a conda call."""
    normalised = re.sub(r"<[^>]*>", WILD, command)
    tokens = normalised.split()
    if not tokens or tokens[0].lower() != "conda":
        return None
    return _split(tokens[1:])


def _value_ok(want: str | None, have: str | None) -> bool:
    """Whether a call's flag value satisfies a row's.

    A literal in the row (``--file explicit.txt``, ``--show channels``) must appear
    literally in the test; a test variable is not proof it was that value.
    """
    if want == WILD:
        return True
    if want is None:
        # ``have`` may be WILD because a following package positional was read as
        # this flag's value; a literal value means a different invocation.
        return have is None or have == WILD
    return have == want


def matches(row: _Invocation, call: _Invocation, *, failure: bool = False) -> bool:
    """Whether a test's conda call exercises an inventory row."""
    row_flags = {f for f, _ in row.flags} - NOISE_FLAGS
    if failure:
        # A failure row is about one precise mistake, so the call must be the same
        # subcommand (``env <unknown subcommand>`` is not ``env remove``) with the
        # same targeting when the row names any (``list -n -p`` is not
        # ``list -n <nonexistent env>``).
        if call.path != row.path:
            return False
        # When a lone ``-n``/``-p`` is the only flag, the failure lies in its value
        # (a missing env), which a test's variables can't show.
        if len(row_flags) == 1 and row_flags <= TARGET_FLAGS:
            return False
        ignored = frozenset() if row_flags & TARGET_FLAGS else TARGET_FLAGS
    else:
        if call.path[: len(row.path)] != row.path:
            return False
        # Rows with nothing beyond targeting (``conda install -n <env> <pkg>``) look
        # identical to every test's setup calls, so they are only ever hand-marked.
        if not row_flags - TARGET_FLAGS:
            return False
        ignored = TARGET_FLAGS - row_flags
    call_flags = {f for f, _ in call.flags} - NOISE_FLAGS - ignored
    if row_flags != call_flags:
        return False
    for flag, want in row.flags:
        if flag in NOISE_FLAGS:
            continue
        if flag in TARGET_FLAGS:
            want = WILD  # example env names in the inventory are not significant
        if not any(_value_ok(want, have) for f, have in call.flags if f == flag):
            return False
    literal = [p for p in row.positionals if p != WILD]
    return all(p in call.positionals for p in literal)


def _resolve(arg: ast.expr, params: dict) -> list[str] | None:
    """Turn one call argument into tokens; ``None`` if it may hide unknown flags."""
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return [arg.value]
    if isinstance(arg, ast.Name) and arg.id in params:
        value = params[arg.id]
        return [value] if isinstance(value, str) else [WILD]
    if isinstance(arg, ast.Starred):
        inner = arg.value
        if isinstance(inner, (ast.Tuple, ast.List)):
            out: list[str] = []
            for elt in inner.elts:
                part = _resolve(elt, params)
                if part is None:
                    return None
                out += part
            return out
        if isinstance(inner, ast.Name) and inner.id in params:
            value = params[inner.id]
            if isinstance(value, (tuple, list)) and all(isinstance(v, str) for v in value):
                return list(value)
        return None
    return [WILD]


def _checked_calls(tree: ast.AST, check: str) -> list[ast.Call]:
    """``conda(...)`` calls whose result is checked with ``.<check>()``.

    Unchecked calls are skipped, and an ``assert_error`` call never counts as an
    ``assert_ok`` one, so a failure-path test never claims the success case it is
    the negative of (or the reverse).
    """
    ok: set[int] = set()
    bound: dict[str, ast.Call] = {}
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "conda":
                calls.append(node)
            elif isinstance(func, ast.Attribute) and func.attr == check:
                target = func.value
                if isinstance(target, ast.Call):
                    ok.add(id(target))
                elif isinstance(target, ast.Name) and target.id in bound:
                    ok.add(id(bound[target.id]))
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "conda"
        ):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    bound[target.id] = node.value
    # Bindings are recorded in walk order, so re-check names bound after use.
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == check
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in bound
        ):
            ok.add(id(bound[node.func.value.id]))
    return [c for c in calls if id(c) in ok]


def invocations_of(item: pytest.Item, check: str = "assert_ok") -> list[_Invocation]:
    """Conda invocations a collected test checks with ``check``, params bound."""
    func = getattr(item, "function", None)
    if func is None:
        return []
    try:
        tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
    except (OSError, TypeError, SyntaxError):
        return []
    callspec = getattr(item, "callspec", None)
    params = callspec.params if callspec else {}
    out = []
    for call in _checked_calls(tree, check):
        tokens: list[str] = []
        for arg in call.args:
            part = _resolve(arg, params)
            if part is None:
                break
            tokens += part
        else:
            out.append(_split(tokens))
    return out


def _subject(item: pytest.Item) -> str | None:
    """Inventory group a test belongs to, from its ``tests/e2e/<sub>/`` directory."""
    try:
        rel = Path(item.path).resolve().relative_to(E2E_ROOT)
    except ValueError:
        return None
    return f"conda {rel.parts[0]}" if len(rel.parts) > 1 else None


def suggest_covers(cases: list[Case], items: list[pytest.Item]) -> list[int]:
    """Inventory ids an unmarked test exercises, across all its parametrizations."""
    rows = [(c, parse_inventory_command(c.command)) for c in cases]
    found: set[int] = set()
    for item in items:
        subject = _subject(item)
        ok_calls = invocations_of(item, "assert_ok")
        error_calls = invocations_of(item, "assert_error")
        for case, row in rows:
            if row is None or case.group.lower() != subject:
                continue
            # Rows expecting a failure are exercised by assert_error calls only.
            failure = case.expected.startswith(FAILURE_PREFIXES)
            calls = error_calls if failure else ok_calls
            if any(matches(row, call, failure=failure) for call in calls):
                found.add(case.id)
    return sorted(found)


def _ensure_pytest_import(lines: list[str]) -> None:
    """Add ``import pytest`` to a module's lines if it isn't imported."""
    tree = ast.parse("\n".join(lines))
    for node in tree.body:
        if isinstance(node, ast.Import) and any(a.name == "pytest" for a in node.names):
            return
    anchor = 0
    for node in tree.body:
        is_docstring = (
            node is tree.body[0]
            and isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        )
        if is_docstring or (isinstance(node, ast.ImportFrom) and node.module == "__future__"):
            anchor = node.end_lineno or anchor
    lines[anchor:anchor] = ["", "import pytest"]


def apply_markers(additions: dict[Path, list[tuple[int, list[int]]]]) -> None:
    """Write ``covers`` markers above test definitions, then ruff the files.

    Args:
        additions: file -> ``(first line of the def incl. decorators, ids)``.
    """
    for path, edits in additions.items():
        lines = path.read_text().split("\n")
        # Bottom-up so earlier insertions don't shift later line numbers.
        for lineno, ids in sorted(edits, reverse=True):
            indent = re.match(r"\s*", lines[lineno - 1]).group()
            lines.insert(lineno - 1, f"{indent}@pytest.mark.covers({', '.join(map(str, ids))})")
        _ensure_pytest_import(lines)
        path.write_text("\n".join(lines))
    # The pre-commit ruff hooks run before this one, so tidy our own edits.
    ruff = shutil.which("ruff")
    if ruff and additions:
        files = [str(p) for p in additions]
        subprocess.run([ruff, "check", "--fix", "--quiet", *files], check=False)
        subprocess.run([ruff, "format", "--quiet", *files], check=False)


def auto_mark(cases: list[Case], collector: _CoversCollector) -> list[str]:
    """Add markers for unmarked tests that match the inventory; update ``collector``.

    Returns:
        One human-readable line per test that was marked.
    """
    additions: dict[Path, list[tuple[int, list[int]]]] = defaultdict(list)
    report = []
    for node, items in sorted(collector.unmarked_items.items()):
        ids = suggest_covers(cases, items)
        if not ids:
            continue
        func = items[0].function
        _, start = inspect.getsourcelines(func)
        additions[Path(inspect.getsourcefile(func))].append((start, ids))
        collector.unmarked.discard(node)
        for case_id in ids:
            collector.claims[case_id].append(node)
        report.append(f"marked {node} -> covers({', '.join(map(str, ids))})")
    apply_markers(additions)
    return report


def bar(covered: int, total: int) -> str:
    """Render a fixed-width text progress bar."""
    if total == 0:
        return "░" * BAR_WIDTH
    filled = round(BAR_WIDTH * covered / total)
    return "█" * filled + "░" * (BAR_WIDTH - filled)


def pct(covered: int, total: int) -> str:
    """Format a coverage percentage, or ``—`` when there is nothing to cover."""
    return "—" if total == 0 else f"{100 * covered / total:.1f}%"


def _hbar(x: float, y: float, w: float, h: float, round_right: bool) -> str:
    """Return an SVG path for a horizontal bar with a square, baseline-anchored left end.

    The right end is the data end, so only it gets rounded — and only when the bar
    is wide enough that a corner radius would not distort it.
    """
    if not round_right or w <= CORNER_R:
        return f"M{x:.1f},{y:.1f}h{w:.1f}v{h:.1f}h{-w:.1f}z"
    r, right = CORNER_R, x + w
    return (
        f"M{x:.1f},{y:.1f}H{right - r:.1f}A{r},{r} 0 0 1 {right:.1f},{y + r:.1f}"
        f"V{y + h - r:.1f}A{r},{r} 0 0 1 {right - r:.1f},{y + h:.1f}H{x:.1f}z"
    )


def _ticks(upper: int) -> list[int]:
    """Return gridline positions from 0 to at least ``upper``, at a round interval.

    Picks the round step whose top tick overshoots ``upper`` least, so the bars use
    the full plot width instead of trailing off into dead space, while keeping the
    gridline count readable.
    """
    upper = max(upper, 1)
    best = None
    for step in (1, 2, 5, 10, 20, 25, 50, 100, 200, 500):
        top = -(-upper // step) * step  # ceil to the next multiple
        if 3 <= top // step + 1 <= 10 and (best is None or top < best[0]):
            best = (top, step)
    if best is None:
        # Too few cases for any round step to give a sensible axis.
        return [0, upper]
    top, step = best
    return list(range(0, top + step, step))


def render_chart(rows: list[tuple[str, int, int]], mode: str) -> str:
    """Render the by-priority stacked bar chart as a standalone SVG.

    Bars are scaled to absolute case counts, not normalised to 100%, so the chart
    carries magnitude as well as ratio — ``Low`` having 205 cases is a large part
    of why its coverage is low, and a normalised chart would hide that.

    Args:
        rows: ``(priority, covered, total)`` in display order.
        mode: ``light`` or ``dark``; selects the colour set.

    Returns:
        A complete SVG document.
    """
    c = THEMES[mode]
    scale_max = _ticks(max(total for _, _, total in rows))[-1]
    width = LABEL_W + PLOT_W + VALUE_W
    height = HEADER_H + ROW_H * len(rows) + FOOTER_H
    x_of = lambda n: LABEL_W + PLOT_W * n / scale_max  # noqa: E731

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="Automated versus remaining conda CLI test cases, by priority">',
        "<title>Command coverage by priority</title>",
        f'<g font-family="{FONT}" font-size="12">',
    ]

    # Legend: two series, so identity is never carried by colour alone.
    lx = LABEL_W
    for name, fill in (("Automated", c["bar"]), ("Remaining", c["track"])):
        out.append(f'<rect x="{lx}" y="12" width="10" height="10" rx="2" fill="{fill}"/>')
        out.append(f'<text x="{lx + 15}" y="21" fill="{c["muted"]}">{name}</text>')
        lx += 20 + 7 * len(name)

    # Recessive gridlines, behind the bars.
    plot_top, plot_bottom = HEADER_H, HEADER_H + ROW_H * len(rows)
    for tick in _ticks(scale_max):
        tx = x_of(tick)
        out.append(
            f'<line x1="{tx:.1f}" y1="{plot_top}" x2="{tx:.1f}" y2="{plot_bottom}" '
            f'stroke="{c["grid"]}" stroke-width="1"/>'
        )
        out.append(
            f'<text x="{tx:.1f}" y="{plot_bottom + 15}" fill="{c["muted"]}" '
            f'font-size="11" text-anchor="middle">{tick}</text>'
        )

    for i, (name, covered, total) in enumerate(rows):
        y = HEADER_H + i * ROW_H + (ROW_H - BAR_H) / 2
        done_w = PLOT_W * covered / scale_max
        rest_w = PLOT_W * (total - covered) / scale_max
        mid = y + BAR_H / 2 + 4

        out.append(
            f'<text x="{LABEL_W - 10}" y="{mid:.1f}" fill="{c["text"]}" '
            f'text-anchor="end">{name}</text>'
        )
        if done_w > 0:
            # Rounded only when nothing follows it in the stack.
            out.append(
                f'<path d="{_hbar(LABEL_W, y, done_w, BAR_H, rest_w <= 0)}" fill="{c["bar"]}"/>'
            )
        if rest_w > 0:
            gap = SEGMENT_GAP if done_w > 0 else 0
            out.append(
                f'<path d="{_hbar(LABEL_W + done_w + gap, y, max(rest_w - gap, 0.5), BAR_H, True)}"'
                f' fill="{c["track"]}"/>'
            )
        out.append(
            f'<text x="{LABEL_W + PLOT_W + 12}" y="{mid:.1f}" fill="{c["muted"]}" '
            f'font-size="11">{covered}/{total}</text>'
        )
        out.append(
            f'<text x="{width - 8}" y="{mid:.1f}" fill="{c["text"]}" font-size="11" '
            f'text-anchor="end">{pct(covered, total)}</text>'
        )

    out += ["</g>", "</svg>", ""]
    return "\n".join(out)


def write_charts(rows: list[tuple[str, int, int]]) -> None:
    """Write the light and dark chart SVGs, creating ``docs/`` if needed."""
    CHART_DIR.mkdir(exist_ok=True)
    for mode in THEMES:
        (CHART_DIR / f"coverage-{mode}.svg").write_text(render_chart(rows, mode))


def _table(rows: list[tuple[str, int, int]], label: str, show_bar: bool = True) -> Iterator[str]:
    """Yield a markdown table of ``(name, covered, total)`` rows.

    ``Remaining`` is shown because the subcommand table is sorted by it; without
    the column the row order looks arbitrary. ``show_bar`` is off for the priority
    table, where the SVG chart above it already carries the same shape.
    """
    tail = " |" if show_bar else ""
    yield f"| {label} | Cases | Automated | Remaining | Coverage |{tail}"
    yield f"| --- | --: | --: | --: | --: |{' :-- |' if show_bar else ''}"
    for name, covered, total in rows:
        cells = f"{total} | {covered} | {total - covered} | {pct(covered, total)}"
        graphic = f" `{bar(covered, total)}` |" if show_bar else ""
        yield f"| {name} | {cells} |{graphic}"


def build_report(cases: list[Case], unmarked: set[str]) -> str:
    """Render the full COVERAGE.md body.

    Args:
        cases: Inventory cases, with ``covered_by`` already populated.
        unmarked: Node IDs of tests carrying no ``covers`` marker.

    Returns:
        The markdown document.
    """
    total = len(cases)
    covered = sum(c.covered for c in cases)
    lines = [
        "<!-- Generated by `pixi run coverage`; do not edit by hand. -->",
        "",
        "# Command coverage",
        "",
        "How much of the manual conda CLI test inventory has an automated E2E test.",
        "",
        "This is **not** code coverage — it measures nothing about which lines of conda",
        "run. The denominator is [`tests/inventory/commands.csv`](tests/inventory/commands.csv),",
        f"a hand-written inventory of {total} CLI cases. A case counts as automated when a",
        "test claims its `id` with `@pytest.mark.covers(...)`.",
        "",
        f"**{covered} of {total} cases automated — {pct(covered, total)}**",
        "",
        f"`{bar(covered, total)}`",
        "",
        "## By priority",
        "",
        "Where the gap actually matters. `Highest` and `High` are the rows to read first.",
        "",
    ]

    by_priority = [
        (p, sum(c.covered for c in group), len(group))
        for p in PRIORITY_ORDER
        if (group := [c for c in cases if c.priority == p])
    ]
    write_charts(by_priority)
    lines += [
        # Two SVGs rather than one: GitHub strips media queries inside an SVG, so
        # <picture> is the only reliable way to theme a chart here.
        "<picture>",
        '  <source media="(prefers-color-scheme: dark)" srcset="docs/coverage-dark.svg">',
        '  <img alt="Automated versus remaining cases by priority" src="docs/coverage-light.svg">',
        "</picture>",
        "",
    ]
    lines += _table(by_priority, "Priority", show_bar=False)

    # Any priority string not in PRIORITY_ORDER would silently vanish from the
    # table above; surface it rather than lose the rows.
    unknown = sorted({c.priority for c in cases} - set(PRIORITY_ORDER))
    if unknown:
        lines += ["", f"> Unrecognised priority values in the inventory: {unknown}"]

    lines += [
        "",
        "## By subcommand",
        "",
        "Sorted by number of cases still to automate — the top of this table is the",
        "work queue.",
        "",
    ]

    groups: dict[str, list[Case]] = defaultdict(list)
    for case in cases:
        groups[case.group].append(case)
    by_group = sorted(
        ((g, sum(c.covered for c in cs), len(cs)) for g, cs in groups.items()),
        key=lambda row: (-(row[2] - row[1]), row[0]),
    )
    lines += _table(by_group, "Subcommand")

    if unmarked:
        lines += [
            "",
            "## Tests with no inventory link",
            "",
            f"{len(unmarked)} test(s) carry no `covers` marker, so they do not count",
            "toward the numbers above. Either link them to an inventory case or add the",
            "case they exercise.",
            "",
        ]
        lines += [f"- `{node}`" for node in sorted(unmarked)]

    return "\n".join(lines) + "\n"


def main() -> int:
    """Generate COVERAGE.md and the inventory's ``automated`` column.

    Returns:
        Process exit status; non-zero when a marker cites an unknown case ID.
    """
    cases = load_inventory()
    by_id = {c.id: c for c in cases}
    collector = collect_claims()

    unknown = sorted(set(collector.claims) - set(by_id))
    if unknown:
        for case_id in unknown:
            claimed = ", ".join(collector.claims[case_id])
            print(f"error: covers({case_id}) is not an inventory id — claimed by {claimed}")
        print(f"\n{len(unknown)} unknown case id(s); refusing to write {OUTPUT.name}")
        return 1

    for line in auto_mark(cases, collector):
        print(line)

    for case_id, nodes in collector.claims.items():
        by_id[case_id].covered_by = nodes

    OUTPUT.write_text(build_report(cases, collector.unmarked))
    if write_automated_column(cases):
        print(f"updated the {AUTOMATED_COLUMN} column in {INVENTORY.name}")
    covered = sum(c.covered for c in cases)
    print(f"\n{OUTPUT.name}: {covered}/{len(cases)} cases automated ({pct(covered, len(cases))})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
