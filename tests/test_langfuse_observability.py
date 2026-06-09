import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from observability.langfuse_adapter import LangfuseObserver
from observability.tracer import TraceSession
from utils.llm_gateway import LLMGateway, llm_call_context


class FakeObservation:
    def __init__(self, bucket):
        self.bucket = bucket
        self.updates = []

    def update(self, **kwargs):
        self.updates.append(kwargs)
        self.bucket["updates"].append(kwargs)


class FakeLangfuseClient:
    def __init__(self):
        self.calls = []
        self.observations = []

    @contextmanager
    def start_as_current_observation(self, **kwargs):
        bucket = {"kwargs": kwargs, "updates": []}
        self.calls.append(kwargs)
        observation = FakeObservation(bucket)
        self.observations.append(observation)
        yield observation

    def create_trace_id(self, seed):
        return f"trace-{seed}"

    def get_trace_url(self, trace_id):
        return f"https://langfuse.local/{trace_id}"

    def flush(self):
        self.flushed = True


class FakeTracker:
    def is_available(self, _model):
        return True, "ok"

    def report_success(self, _model):
        pass

    def report_failure(self, _model, _error):
        pass


class FakeClient:
    def invoke(self, _prompt):
        return "answer"


class LangfuseObservabilityTests(unittest.TestCase):
    def test_adapter_records_trace_summary_without_raw_spans(self):
        client = FakeLangfuseClient()
        observer = LangfuseObserver(client=client)
        trace_data = {
            "trace_id": "abc123",
            "trace_type": "fusion_query",
            "question": "What was revenue?",
            "metadata": {"orchestrator": "production_harness"},
            "duration_s": 1.2,
            "spans": [{"name": "routing"}],
            "final": {"source_type": "sql_only", "from_cache": False},
        }

        with patch.dict(os.environ, {"NEXUSIQ_LANGFUSE_ENABLED": "1"}, clear=False):
            url = observer.record_trace_summary(trace_data)

        self.assertEqual(url, "https://langfuse.local/trace-abc123")
        self.assertEqual(client.calls[0]["as_type"], "agent")
        self.assertEqual(client.calls[0]["name"], "nexusiq.fusion_query")
        self.assertEqual(client.calls[0]["input"]["local_trace_id"], "abc123")
        self.assertEqual(client.observations[0].updates[0]["output"]["source_type"], "sql_only")

    def test_llm_gateway_mirrors_safe_generation_metadata(self):
        client = FakeLangfuseClient()
        observer = LangfuseObserver(client=client)

        def factory(_model_config, _temperature):
            return FakeClient()

        with tempfile.TemporaryDirectory() as tmp:
            gateway = LLMGateway(ledger_path=Path(tmp) / "ledger.jsonl", client_factory=factory)
            with patch("utils.llm_gateway.get_langfuse_observer", return_value=observer), \
                 patch.dict(os.environ, {"NEXUSIQ_LANGFUSE_ENABLED": "1"}, clear=False):
                result = gateway.invoke_with_fallback(
                    prompt="secret-ish prompt that must not be sent",
                    models=[{"name": "fake-model", "type": "fake", "description": "Fake"}],
                    tracker=FakeTracker(),
                    task="test.task",
                    metadata={"agent": "test"},
                )

        self.assertTrue(result["success"])
        generation_call = client.calls[0]
        self.assertEqual(generation_call["as_type"], "generation")
        self.assertEqual(generation_call["name"], "test.task")
        self.assertEqual(generation_call["model"], "fake-model")
        self.assertIn("prompt_hash", generation_call["input"])
        self.assertNotIn("secret-ish prompt", str(generation_call))
        self.assertEqual(client.observations[0].updates[0]["metadata"]["status"], "success")

    def test_llm_gateway_attaches_call_events_to_trace(self):
        class Response:
            content = "answer"
            usage_metadata = {
                "input_tokens": 7,
                "output_tokens": 2,
                "total_tokens": 9,
            }

        def factory(_model_config, _temperature):
            class Client:
                def invoke(self, _prompt):
                    return Response()

            return Client()

        with tempfile.TemporaryDirectory() as tmp:
            trace_index = Path(tmp) / "index.jsonl"
            with patch.dict(
                os.environ,
                {
                    "NEXUSIQ_TRACE_DIR": tmp,
                    "NEXUSIQ_TRACE_INDEX_PATH": str(trace_index),
                    "NEXUSIQ_LANGFUSE_ENABLED": "0",
                },
                clear=False,
            ):
                trace = TraceSession("What was revenue?")
                gateway = LLMGateway(ledger_path=Path(tmp) / "ledger.jsonl", client_factory=factory)
                with llm_call_context(
                    trace=trace,
                    trace_id=trace.trace_id,
                    harness_task_id="task-123",
                ):
                    gateway.invoke_with_fallback(
                        prompt="Question",
                        models=[{"name": "fake-model", "type": "fake", "description": "Fake"}],
                        tracker=FakeTracker(),
                        task="test.task",
                    )
                path = trace.finish({"source_type": "sql_only"})

            trace_data = json.loads(Path(path).read_text())
            llm_events = [span for span in trace_data["spans"] if span["name"] == "llm.call"]
            self.assertEqual(len(llm_events), 1)
            self.assertEqual(llm_events[0]["metadata"]["task"], "test.task")
            self.assertEqual(llm_events[0]["metadata"]["harness_task_id"], "task-123")
            self.assertEqual(llm_events[0]["metadata"]["total_tokens_actual"], 9)

    def test_trace_session_keeps_working_when_langfuse_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(
                os.environ,
                {
                    "NEXUSIQ_TRACE_DIR": tmp,
                    "NEXUSIQ_TRACE_INDEX_PATH": str(Path(tmp) / "index.jsonl"),
                    "NEXUSIQ_LANGFUSE_ENABLED": "0",
                },
                clear=False,
            ):
                trace = TraceSession("What was revenue?")
                trace.record_event("test.event", {"ok": True})
                path = trace.finish({"source_type": "sql_only"})
                self.assertIsNotNone(path)
                self.assertTrue(Path(path).exists())


if __name__ == "__main__":
    unittest.main()
