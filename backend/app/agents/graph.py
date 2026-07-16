from langgraph.graph import StateGraph, END

from app.agents.state import AgentState
from app.agents.nodes import (
    input_guard_node,
    router_node,
    retrieve_node,
    rerank_node,
    generate_node,
    output_guard_node,
)


def build_graph() -> StateGraph:
    builder = StateGraph(AgentState)

    builder.add_node("input_guard", input_guard_node)
    builder.add_node("router", router_node)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("rerank", rerank_node)
    builder.add_node("generate", generate_node)
    builder.add_node("output_guard", output_guard_node)

    builder.set_entry_point("input_guard")
    builder.add_edge("input_guard", "router")
    builder.add_edge("router", "retrieve")
    builder.add_edge("retrieve", "rerank")
    builder.add_edge("rerank", "generate")
    builder.add_edge("generate", "output_guard")
    builder.add_edge("output_guard", END)

    return builder.compile()


agent_graph = build_graph()
