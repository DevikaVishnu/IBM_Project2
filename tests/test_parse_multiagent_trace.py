import unittest
from pathlib import Path

from parse_multiagent_trace import FIELDS, parse_multiagent_trace


class MultiAgentTraceParserTests(unittest.TestCase):
    def test_normalises_observed_input_output_messages_deliveries_and_retrieval(self):
        raw = {
            "executions": [{
                "execution_id": "X-001", "agent_id": "diagnostic", "kind": "analyze",
                "seq_start": 10, "seq_end": 20, "started_at": "2026-11-02T10:00:00Z",
                "completed_at": "2026-11-02T10:00:02Z", "status": "COMPLETED",
                "rendered_system": "Use evidence.", "rendered_input": "EV-001",
                "llm_calls": [{"response_excerpt": "short only"}], "output": {"finding": "Bearing Wear"},
            }],
            "messages": [{
                "seq": 21, "timestamp": "2026-11-02T10:00:03Z", "sender_agent_id": "diagnostic",
                "receiver_agent_ids": ["verification"], "message_type": "FINDING", "message_content": "Bearing Wear",
                "deliveries": [{"seq": 22, "timestamp": "2026-11-02T10:00:04Z", "receiver": "verification"}],
            }],
            "events": [{
                "seq": 3, "timestamp": "2026-11-02T09:59:00Z", "actor": "harness",
                "event_type": "EVIDENCE_RETRIEVED", "evidence_ids": ["EV-001"], "payload": {"count": 1},
            }],
        }

        events = parse_multiagent_trace(raw, Path("multiagent.json"))

        self.assertEqual([tuple(event) for event in events], [FIELDS] * 5)
        self.assertEqual([event["action"] for event in events], [
            "evidence_retrieved", "model_input", "model_output", "message_finding", "message_delivered",
        ])
        self.assertEqual(events[3]["target"], "verification")
        self.assertEqual(events[4]["target"], "verification")
        self.assertIn('"input": "EV-001"', events[1]["message"])
        self.assertIn('"response_excerpt": "short only"', events[2]["message"])
        self.assertTrue(events[0]["source_trace"].endswith("#/events/0"))


if __name__ == "__main__":
    unittest.main()
