import unittest
from pathlib import Path

from build_multiagent_trace_draft import build


class MultiAgentDraftTests(unittest.TestCase):
    def test_keeps_only_checked_observable_annotations(self):
        raw = {
            "trace": {"trace_id": "TR-1", "status": "COMPLETED"},
            "agents": {"a": {"name": "Agent A", "role": "test"}},
            "messages": [{"message_id": "M-1", "sender_agent_id": "a", "message_content": "Bearing Wear is likely.", "evidence_ids": ["EV-1"]}],
            "disagreements": [{"message_id": "M-2", "outcome": "open"}],
        }
        annotations = {
            "trace_id": "TR-1",
            "claims": [{"id": "c1", "message_id": "M-1", "agent": "a", "quote": "Bearing Wear", "evidence_ids": ["EV-1"]}],
            "disagreements": [{"id": "d1", "message_id": "M-2"}],
        }
        draft = build(raw, [], annotations, Path("trace.json"))
        self.assertEqual(draft["schema"], "ida.agenttrace-draft/0.1")
        self.assertEqual(draft["claims"][0]["source_trace"], "ida.agenttrace:trace.json#/messages/0")
        self.assertEqual(draft["disagreements"][0]["recorded"]["outcome"], "open")


if __name__ == "__main__":
    unittest.main()
