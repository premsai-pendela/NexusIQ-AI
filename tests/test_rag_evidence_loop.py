"""Bounded RAG evidence loop contracts.

retrieve -> assess (deterministic, cross-encoder logits) -> if weak, one HyDE
retry -> re-assess -> answer / caveat / honest refusal. Proofs:

1. Strong initial retrieval never triggers the retry.
2. Weak initial retrieval triggers exactly one HyDE retry; better retry
   results (by rerank logit) are adopted.
3. Still-weak evidence answers with an explicit caveat, never as confident.
4. Insufficient evidence refuses honestly without calling the answer LLM.
5. Assessment falls back to hybrid score when the reranker is unavailable.
6. Sources/citations metadata intact on the strong path.
"""

import unittest
from datetime import datetime
from unittest.mock import MagicMock

from agents.rag_agent import RAGAgent


def chunk(filename, hybrid, rerank=None, text="Q4 revenue was $58.9M"):
    data = {"text": text, "filename": filename, "category": "financial",
            "page": 1, "chunk_id": 1, "similarity": hybrid,
            "bm25_score": 0.5, "vector_score": 0.5}
    if rerank is not None:
        data["rerank_score"] = rerank
    return data


STRONG = [chunk("01_Q4_Report.pdf", 0.84, rerank=9.3)]
MARGINAL = [chunk("11_Incident.pdf", 0.29, rerank=1.7)]
WEAK = [chunk("13_Annual.pdf", 0.74, rerank=-1.2)]
GARBAGE = [chunk("03_Policy.pdf", 0.45, rerank=-10.8)]
NO_RERANK_LOW = [chunk("x.pdf", 0.2)]
NO_RERANK_OK = [chunk("x.pdf", 0.6)]


class AssessEvidenceTest(unittest.TestCase):
    def test_thresholds(self):
        self.assertEqual(RAGAgent._assess_evidence([])["quality"], "insufficient")
        self.assertEqual(RAGAgent._assess_evidence(STRONG)["quality"], "sufficient")
        self.assertEqual(RAGAgent._assess_evidence(MARGINAL)["quality"], "sufficient")
        self.assertEqual(RAGAgent._assess_evidence(WEAK)["quality"], "weak")
        self.assertEqual(RAGAgent._assess_evidence(GARBAGE)["quality"], "insufficient")

    def test_hybrid_fallback_without_reranker(self):
        self.assertEqual(RAGAgent._assess_evidence(NO_RERANK_LOW)["quality"], "weak")
        self.assertEqual(RAGAgent._assess_evidence(NO_RERANK_OK)["quality"], "sufficient")

    def test_assessment_reports_signals(self):
        assessment = RAGAgent._assess_evidence(STRONG)
        self.assertEqual(assessment["top_rerank"], 9.3)
        self.assertEqual(assessment["unique_docs"], 1)

    def test_evidence_better_prefers_rerank_logit(self):
        self.assertTrue(RAGAgent._evidence_better(STRONG, WEAK))
        self.assertFalse(RAGAgent._evidence_better(WEAK, STRONG))
        # hybrid fallback when either side lacks rerank scores
        self.assertTrue(RAGAgent._evidence_better(NO_RERANK_OK, NO_RERANK_LOW))


def make_agent(initial_chunks, hyde_chunks=None):
    agent = RAGAgent.__new__(RAGAgent)
    agent._classify_query_complexity = lambda _q: "simple"
    agent._normalize_retrieval_query = lambda q: q
    agent.hybrid_search = MagicMock(return_value=initial_chunks)
    agent._hyde_search = MagicMock(return_value=hyde_chunks or [])
    agent._build_context = lambda chunks, model_name=None: "CTX"
    agent._create_prompt = lambda q, c: "PROMPT"
    agent._generate_answer_with_fallback = MagicMock(
        return_value=("The answer is $58.9M.", "stub-model", [])
    )
    agent._extract_sources = lambda answer, chunks: [
        {"filename": c["filename"], "page": c["page"]} for c in chunks
    ]
    return agent


def run(agent, question="What was Q4 revenue?"):
    return agent._handle_simple_query(question, n_results=5, return_sources=True,
                                      start_time=datetime.now())


class EvidenceLoopTest(unittest.TestCase):
    def test_strong_retrieval_never_retries(self):
        agent = make_agent(STRONG)
        result = run(agent)

        agent._hyde_search.assert_not_called()
        self.assertEqual(result["evidence_quality"], "sufficient")
        self.assertFalse(result["evidence"]["retried"])
        self.assertNotIn("Evidence caveat", result["answer"])
        self.assertEqual(result["sources"][0]["filename"], "01_Q4_Report.pdf")

    def test_weak_retrieval_retries_once_and_adopts_better_results(self):
        agent = make_agent(WEAK, hyde_chunks=STRONG)
        result = run(agent)

        agent._hyde_search.assert_called_once()
        self.assertTrue(result["evidence"]["retried"])
        self.assertEqual(result["evidence_quality"], "sufficient")
        self.assertNotIn("Evidence caveat", result["answer"])
        self.assertEqual(result["sources"][0]["filename"], "01_Q4_Report.pdf")

    def test_still_weak_after_retry_answers_with_caveat(self):
        agent = make_agent(WEAK, hyde_chunks=[])
        result = run(agent)

        agent._hyde_search.assert_called_once()
        self.assertEqual(result["evidence_quality"], "weak")
        self.assertIn("Evidence caveat", result["answer"])
        self.assertIn("retrieval confidence for this question was low", result["answer"])
        # still answers, still cites — weak is disclosed, not hidden
        self.assertTrue(result["sources"])

    def test_insufficient_evidence_refuses_without_answer_llm(self):
        agent = make_agent(GARBAGE, hyde_chunks=GARBAGE)
        result = run(agent, question="What is the quantum lunch policy?")

        agent._hyde_search.assert_called_once()
        agent._generate_answer_with_fallback.assert_not_called()
        self.assertEqual(result["evidence_quality"], "insufficient")
        self.assertIn("won't", result["answer"])
        self.assertIn("below the evidence threshold", result["answer"])
        self.assertEqual(result["sources"], [])
        self.assertEqual(result["chunks_retrieved"], 0)

    def test_retry_happens_at_most_once(self):
        agent = make_agent(WEAK, hyde_chunks=WEAK)
        run(agent)
        self.assertEqual(agent._hyde_search.call_count, 1)


if __name__ == "__main__":
    unittest.main()
