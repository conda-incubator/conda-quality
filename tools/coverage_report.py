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
"""

from __future__ import annotations

import csv
import io
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent
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

# Chart colours per GitHub theme (background #ffffff light, #0d1117 dark).
# "bar" (automated) has at least 3:1 contrast with the background in both modes.
# "track" (remaining) is deliberately faint; each row's printed numbers and the
# table below the chart carry the same data.
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


def write_file(path: Path, text: str) -> None:
    """Write a generated file as UTF-8 with LF line endings on every platform.

    The platform default (cp1252 on Windows) can't encode the report's bar
    characters, and would leave the file truncated; it would also make the
    output differ by OS, so the pre-commit hook would see spurious changes.
    """
    path.write_text(text, encoding="utf-8", newline="\n")


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

    def pytest_collection_modifyitems(self, items: list[pytest.Item]) -> None:
        """Read markers off every collected item."""
        for item in items:
            # Strip the [param] suffix: a parametrized test is one test for our
            # purposes, and its 4 shell variants shouldn't look like 4 claims.
            node = item.nodeid.partition("[")[0]
            # An unconditional skip never runs anywhere, so its markers prove nothing.
            # skipif is still counted: its condition is platform-dependent, and the
            # test runs elsewhere; dropping it would make the numbers differ by OS.
            if item.get_closest_marker("skip"):
                continue
            ids = [i for marker in item.iter_markers("covers") for i in marker.args]
            if not ids:
                self.unmarked.add(node)
                continue
            for case_id in ids:
                if node not in self.claims[case_id]:
                    self.claims[case_id].append(node)


def load_inventory() -> list[Case]:
    """Read the inventory CSV, newest-numbered last.

    Returns:
        Every inventory case, in ``id`` order.

    Raises:
        SystemExit: if the CSV is missing, or two rows share an ``id``: markers
            find their case by ``id``, so a test would count for only one of them.
    """
    if not INVENTORY.is_file():
        sys.exit(f"inventory not found: {INVENTORY}")
    with INVENTORY.open(encoding="utf-8", newline="") as fh:
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
    duplicates = sorted(i for i, n in Counter(c.id for c in cases).items() if n > 1)
    if duplicates:
        sys.exit(f"duplicate id(s) in {INVENTORY.name}: {duplicates}; give each row its own id")
    return sorted(cases, key=lambda c: c.id)


def write_automated_column(cases: list[Case]) -> bool:
    """Set the inventory's ``automated`` column from the claims, in place.

    The column is generated, like ``COVERAGE.md``: hand edits are overwritten.
    Row order and every other column are left exactly as they are.

    Returns:
        Whether the file changed.
    """
    covered = {c.id for c in cases if c.covered}
    with INVENTORY.open(encoding="utf-8", newline="") as fh:
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
    # Compare bytes, so a CRLF checkout counts as a change and gets normalised.
    if INVENTORY.read_bytes() == text.encode("utf-8"):
        return False
    write_file(INVENTORY, text)
    return True


def collect_claims() -> _CoversCollector:
    """Collect ``covers`` markers from the suite without running any tests.

    Returns:
        The populated collector.

    Raises:
        SystemExit: if pytest collection fails or finds no tests, since either
            would undercount coverage and quietly report the wrong number.
    """
    collector = _CoversCollector()
    # The explicit tests path makes collection independent of the working
    # directory (e.g. an IDE running this from tools/), and pytest still finds the
    # repo's pyproject.toml from it. `-o addopts=` drops the suite's default flags:
    # they write an HTML report, which would be a surprising side effect of
    # computing coverage. --strict-markers is re-added on its own so a misspelled
    # marker name still fails here.
    args = [
        str(REPO_ROOT / "tests"),
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
    # NO_TESTS_COLLECTED is a failure too: 0 tests would report 0% and overwrite
    # the generated files with it.
    if status != pytest.ExitCode.OK:
        sys.exit(f"pytest collection failed (exit {status}); coverage numbers would be wrong")
    return collector


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
        write_file(CHART_DIR / f"coverage-{mode}.svg", render_chart(rows, mode))


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

    for case_id, nodes in collector.claims.items():
        by_id[case_id].covered_by = nodes

    write_file(OUTPUT, build_report(cases, collector.unmarked))
    if write_automated_column(cases):
        print(f"updated the {AUTOMATED_COLUMN} column in {INVENTORY.name}")
    covered = sum(c.covered for c in cases)
    print(f"\n{OUTPUT.name}: {covered}/{len(cases)} cases automated ({pct(covered, len(cases))})")
    # Not an error: a test may have no inventory row yet. Listed so whoever runs
    # this can check none of them is just missing its marker.
    if collector.unmarked:
        print(f"\nwarning: {len(collector.unmarked)} test(s) have no covers marker:")
        for node in sorted(collector.unmarked):
            print(f"  {node}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
