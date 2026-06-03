"""Unified Word table grid parsing and cell location — the single source of truth
for OOXML grid-aware cell access."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from docx.oxml.ns import qn
from docx.table import _Cell


# ── GridCell ────────────────────────────────────────────────────────────

@dataclass
class GridCell:
    """One real cell in a Word table's OOXML grid."""
    row: int
    physical_col: int       # index within python-docx row.cells
    grid_col: int           # true OOXML grid column
    grid_span: int          # w:gridSpan (default 1)
    text: str               # cell text trimmed
    normalized_text: str    # text with punctuation / whitespace stripped
    cell: Any               # python-docx Cell proxy for write-back


# ── parse_table_grid ────────────────────────────────────────────────────

def parse_table_grid(table) -> list[list[GridCell]]:
    """Parse a Word table into a true grid[row][grid_col].

    Reads w:tblGrid for total column count, then iterates w:tr / w:tc,
    computing grid_col from w:gridSpan.  Handles vertical merges (w:vMerge)
    by carrying cells into subsequent rows.

    Returns:
        grid[row][grid_col] = GridCell (or None for untouched spots).
    """
    tbl = table._tbl

    # 1. Total columns from w:tblGrid
    tbl_grid = tbl.find(qn('w:tblGrid'))
    num_cols = 0
    if tbl_grid is not None:
        num_cols = sum(1 for _ in tbl_grid.findall(qn('w:gridCol')))

    # Fallback: scan first row w:tc gridSpan totals
    if num_cols <= 0:
        for tr in tbl.findall(qn('w:tr')):
            total = 0
            for tc in tr.findall(qn('w:tc')):
                tc_pr = tc.find(qn('w:tcPr'))
                gs = 1
                if tc_pr is not None:
                    gs_el = tc_pr.find(qn('w:gridSpan'))
                    if gs_el is not None and gs_el.get(qn('w:val')):
                        gs = int(gs_el.get(qn('w:val')))
                total += gs
            if total > num_cols:
                num_cols = total

    if num_cols <= 0:
        num_cols = max((len(row.cells) for row in table.rows), default=2)

    # 2. Build grid row-by-row
    grid: list[list[GridCell | None]] = []
    vmerge_carry: dict[int, GridCell] = {}   # grid_col → carried cell

    for row_index, row in enumerate(table.rows):
        row_grid: list[GridCell | None] = [None] * num_cols
        tc_elements = row._tr.findall(qn('w:tc'))
        physical_idx = 0
        grid_col = 0

        for tc in tc_elements:
            # Advance past columns already filled by vMerge carry
            while grid_col < num_cols and row_grid[grid_col] is not None:
                grid_col += 1
            if grid_col >= num_cols:
                break

            tc_pr = tc.find(qn('w:tcPr'))
            grid_span = 1
            is_vmerge_continue = False
            is_vmerge_restart = False

            if tc_pr is not None:
                gs_el = tc_pr.find(qn('w:gridSpan'))
                if gs_el is not None and gs_el.get(qn('w:val')):
                    grid_span = int(gs_el.get(qn('w:val')))

                vm_el = tc_pr.find(qn('w:vMerge'))
                if vm_el is not None:
                    val = vm_el.get(qn('w:val'))
                    if val == 'restart':
                        is_vmerge_restart = True
                    else:
                        is_vmerge_continue = True

            # Get text
            cell_proxy = _Cell(tc, table)
            text = ""
            normalized = ""
            if cell_proxy is not None:
                text = "\n".join(p.text for p in cell_proxy.paragraphs).strip()
                normalized = re.sub(r"[\s:：；;、，,。.·\-—–（）()\[\]【】<>《》]+", "", text)

            gcell = GridCell(
                row=row_index,
                physical_col=physical_idx,
                grid_col=grid_col,
                grid_span=grid_span,
                text=text,
                normalized_text=normalized,
                cell=cell_proxy,
            )

            # Place in row grid (one ref per grid column)
            for g in range(grid_span):
                pos = grid_col + g
                if pos < num_cols:
                    row_grid[pos] = gcell

            # vMerge bookkeeping
            if is_vmerge_restart or is_vmerge_continue:
                base = gcell
                if is_vmerge_continue:
                    base = vmerge_carry.get(grid_col, gcell)
                for g in range(grid_span):
                    vmerge_carry[grid_col + g] = base
            else:
                for g in range(grid_span):
                    vmerge_carry.pop(grid_col + g, None)

            grid_col += grid_span
            physical_idx += 1

        # Fill vMerge carries for this row
        for gcol, carry_cell in list(vmerge_carry.items()):
            if row_grid[gcol] is None:
                row_grid[gcol] = carry_cell

        grid.append(row_grid)

    return grid


# ── find_cell_by_grid ───────────────────────────────────────────────────

def find_cell_by_grid(table, row: int, grid_col: int, physical_col: int | None = None):
    """Return the python-docx Cell at (row, grid_col).

    Uses parse_table_grid to locate the cell, falling back to
    physical_col if the grid lookup fails.
    """
    grid = parse_table_grid(table)

    # 1. Try precise grid lookup
    if 0 <= row < len(grid):
        row_grid = grid[row]
        for gc in range(grid_col, min(grid_col + 10, len(row_grid))):
            gcell = row_grid[gc]
            if gcell is None:
                continue
            if gcell.grid_col <= grid_col < gcell.grid_col + gcell.grid_span:
                return gcell.cell

    # 2. Fallback to physical col
    if physical_col is not None:
        if row < len(table.rows) and physical_col < len(table.rows[row].cells):
            return table.rows[row].cells[physical_col]

    return None
