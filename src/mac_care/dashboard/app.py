from __future__ import annotations

import json
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, Markdown, Static, Input
from textual.binding import Binding

from ..model import format_bytes
from ..explain import _explain_category


class FindingDetail(Markdown):
    """A widget to display details of a finding."""
    def update_finding(self, finding: dict) -> None:
        category = finding.get("category", "unknown")
        risk = finding.get("risk", "review")
        path = finding.get("path", "unknown")
        size = format_bytes(finding.get("size_bytes", 0))
        reason = finding.get("reason", "No reason provided")
        
        # Get detailed explanation
        meta = _explain_category(category, risk=risk)
        
        md = f"""
# {meta.title}
**Category:** `{category}`  
**Risk:** `{risk.upper()}`  
**Size:** `{size}`  

### Finding
> {reason}

### Path
`{path}`

---

### Description
{meta.description}

### Rationale
{meta.risk_rationale}

### Safety Tip
{meta.safety_tip}
"""
        self.update(md)


class MacCareDashboard(App):
    """A Textual app for browsing mac-care findings."""
    
    CSS = """
    Screen {
        background: $surface;
    }

    #main-container {
        height: 1fr;
    }

    DataTable {
        height: 1fr;
        width: 60%;
        border-right: solid $primary;
    }

    FindingDetail {
        width: 40%;
        padding: 1;
        overflow-y: scroll;
    }

    #filter-container {
        height: 3;
        dock: top;
        background: $surface;
        padding: 0 1;
    }

    Input {
        width: 100%;
        border: none;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("s", "sort", "Sort by Size", show=True),
        Binding("f", "focus_filter", "Filter", show=True),
        Binding("escape", "clear_filter", "Clear Filter", show=False),
    ]

    def __init__(self, report_path: Path):
        super().__init__()
        self.report_path = report_path
        self.findings: list[dict] = []
        self.all_findings: list[dict] = []

    def on_mount(self) -> None:
        self.load_report()
        table = self.query_one(DataTable)
        table.add_columns("Risk", "Category", "Size", "Source")
        self.populate_table()
        table.focus()

    def load_report(self) -> None:
        if not self.report_path.exists():
            return
        try:
            data = json.loads(self.report_path.read_text(encoding="utf-8"))
            self.all_findings = data.get("findings", [])
            self.findings = self.all_findings
        except (json.JSONDecodeError, OSError):
            self.all_findings = []
            self.findings = []

    def populate_table(self, filter_text: str = "") -> None:
        table = self.query_one(DataTable)
        table.clear()
        
        filtered = []
        for f in self.all_findings:
            if filter_text.lower() in f["category"].lower() or filter_text.lower() in f["path"].lower():
                filtered.append(f)
        
        self.findings = filtered
        for i, f in enumerate(self.findings):
            table.add_row(
                f["risk"].upper(),
                f["category"],
                format_bytes(f["size_bytes"]),
                f.get("source", "native"),
                key=str(i)
            )
        
        if self.findings:
            table.move_cursor(row=0)
            self.update_detail(0)

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Vertical(
                Horizontal(
                    DataTable(cursor_type="row"),
                    FindingDetail(),
                ),
                id="main-container"
            ),
            Horizontal(
                Input(placeholder="Filter by category or path... (Esc to clear)"),
                id="filter-container"
            )
        )
        yield Footer()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key and event.row_key.value:
            idx = int(event.row_key.value)
            self.update_detail(idx)

    def update_detail(self, idx: int) -> None:
        if 0 <= idx < len(self.findings):
            detail = self.query_one(FindingDetail)
            detail.update_finding(self.findings[idx])

    def on_input_changed(self, event: Input.Changed) -> None:
        self.populate_table(event.value)

    def action_focus_filter(self) -> None:
        self.query_one(Input).focus()

    def action_clear_filter(self) -> None:
        input_widget = self.query_one(Input)
        input_widget.value = ""
        self.query_one(DataTable).focus()

    def action_sort(self) -> None:
        # Toggle sort by size_bytes
        self.all_findings.sort(key=lambda x: x["size_bytes"], reverse=True)
        self.populate_table(self.query_one(Input).value)
