"""
Module-level agent singletons for API/MCP entry points.

Fusion still owns the shared cross-source cache. Direct SQL/RAG/Web tools stay
lazy so a simple MCP database query does not cold-load the full Fusion stack.
"""

_sql_agent = None


def get_fusion_agent():
    from agents.fusion_agent import get_fusion_agent as _get_fusion

    return _get_fusion("live")


def get_sql_agent():
    global _sql_agent
    if _sql_agent is None:
        from agents.sql_agent import SQLAgent
        from config.data_contexts import LIVE_CONTEXT

        _sql_agent = SQLAgent(mode="development", data_context=LIVE_CONTEXT)
    return _sql_agent


def get_rag_agent():
    from agents.rag_agent import get_rag_agent as _get_rag

    return _get_rag("live")


def get_web_agent():
    from agents.web_agent import get_web_agent as _get_web

    return _get_web()
