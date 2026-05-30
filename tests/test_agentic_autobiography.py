import json
import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import agentic_autobiography as engine


class AgenticAutobiographyTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.workspace.name)
        self.old_data_dir = engine.DATA_DIR
        self.old_journal_dir = engine.JOURNAL_DIR
        self.old_index_path = engine.INDEX_PATH
        self.old_dashboard_path = engine.DASHBOARD_PATH
        engine.DATA_DIR = self.temp_root / "data"
        engine.JOURNAL_DIR = engine.DATA_DIR / "journals"
        engine.INDEX_PATH = engine.DATA_DIR / "index.json"
        engine.DASHBOARD_PATH = self.temp_root / "dashboard" / "index.html"

    def tearDown(self):
        engine.DATA_DIR = self.old_data_dir
        engine.JOURNAL_DIR = self.old_journal_dir
        engine.INDEX_PATH = self.old_index_path
        engine.DASHBOARD_PATH = self.old_dashboard_path
        self.workspace.cleanup()

    def test_index_search_and_summary_are_source_grounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "note.md"
            doc.write_text(
                "# Test Project\n\nDecision: use local-first indexing.\n\nAction: write dashboard tests.",
                encoding="utf-8",
            )
            payload = engine.build_index([Path(tmp)])

        self.assertEqual(payload["files_indexed"], 1)
        results = engine.search("local-first dashboard", limit=3)
        self.assertTrue(results)
        self.assertTrue(results[0]["source"].endswith("note.md"))

        summary = engine.summarize("local-first dashboard")
        self.assertIn("sources", summary)
        self.assertTrue(summary["decisions"])
        self.assertTrue(summary["next_actions"])

    def test_journal_and_dashboard_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "journal.md"
            doc.write_text(
                "# Daily Work\n\nDecision: keep the memory layer dependency-free.\n\nAction: render dashboard.",
                encoding="utf-8",
            )
            journal = engine.generate_journal(hours=24, docs=[Path(tmp)])

        self.assertIn("summary", journal)
        self.assertTrue(engine.DASHBOARD_PATH.exists())
        html = engine.DASHBOARD_PATH.read_text(encoding="utf-8")
        self.assertIn("Agentic Autobiography", html)

    def test_mcp_server_lists_tools(self):
        import contextos_mcp

        response = contextos_mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertIsNotNone(response)
        tools = response["result"]["tools"]
        names = {tool["name"] for tool in tools}
        self.assertIn("memory.search", names)
        self.assertIn("journal.generate", names)


if __name__ == "__main__":
    unittest.main()
