import json
import pytest
from pathlib import Path
from mac_care.dashboard.app import MacCareDashboard
from textual.widgets import DataTable, Markdown

@pytest.fixture
def mock_report(tmp_path):
    report_data = {
        "generated_at": "2026-05-03 12:00:00",
        "findings": [
            {
                "category": "user_logs",
                "path": "/Users/test/Library/Logs",
                "size_bytes": 1024 * 1024,
                "risk": "review",
                "reason": "Old logs",
                "source": "native"
            },
            {
                "category": "trash",
                "path": "/Users/test/.Trash",
                "size_bytes": 5 * 1024 * 1024,
                "risk": "auto_safe",
                "reason": "Trash files",
                "source": "native"
            }
        ]
    }
    report_path = tmp_path / "mac-care-20260503.json"
    report_path.write_text(json.dumps(report_data))
    return report_path

@pytest.mark.asyncio
async def test_dashboard_loading(mock_report):
    app = MacCareDashboard(mock_report)
    async with app.run_test() as pilot:
        table = app.query_one(DataTable)
        assert table.row_count == 2
        
        # Verify first row content
        # Column indices: 0:Risk, 1:Category, 2:Size, 3:Source
        row0 = table.get_row_at(0)
        assert row0[0] == "REVIEW"
        assert row0[1] == "user_logs"
        assert row0[2] == "1.0 MB"

@pytest.mark.asyncio
async def test_dashboard_detail_update(mock_report):
    app = MacCareDashboard(mock_report)
    async with app.run_test() as pilot:
        detail = app.query_one(Markdown)
        # Initially shows first finding
        assert "User Logs" in str(detail.source)
        
        # Select second row
        table = app.query_one(DataTable)
        table.move_cursor(row=1)
        # Wait for the detail update to trigger
        await pilot.pause()
        
        assert "Trash" in str(detail.source)
        assert "/Users/test/.Trash" in str(detail.source)

@pytest.mark.asyncio
async def test_dashboard_filter(mock_report):
    app = MacCareDashboard(mock_report)
    async with app.run_test() as pilot:
        table = app.query_one(DataTable)
        assert table.row_count == 2
        
        # Type into filter
        await pilot.press("f")
        for char in "trash":
            await pilot.press(char)
        
        assert table.row_count == 1
        assert table.get_row_at(0)[1] == "trash"

@pytest.mark.asyncio
async def test_dashboard_sort(mock_report):
    app = MacCareDashboard(mock_report)
    async with app.run_test() as pilot:
        table = app.query_one(DataTable)
        # Initially user_logs (1MB), then trash (5MB)
        assert table.get_row_at(0)[1] == "user_logs"
        
        # Sort by size
        await pilot.press("s")
        
        # Now trash (5MB) should be first
        assert table.get_row_at(0)[1] == "trash"
