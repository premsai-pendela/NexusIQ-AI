"""
Module-level agent singletons — FastAPI and Streamlit share the same
quota tracker and TTL cache state. All agents are keyed to 'live' context.
"""
from agents.fusion_agent import get_fusion_agent as _get_fusion


def get_fusion_agent():
    return _get_fusion("live")


def get_sql_agent():
    return get_fusion_agent().sql_agent


def get_rag_agent():
    return get_fusion_agent().rag_agent


def get_web_agent():
    return get_fusion_agent().web_agent
