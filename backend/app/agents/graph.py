from app.agents.state import AgentState
from app.agents.nodes import (
    input_guard_node,
    reject_node,
    router_node,
    retrieve_node,
    rerank_node,
    generate_node,
    output_guard_node,
)


def route_after_guard(state: dict) -> str:
    if state.get("guardrail_input_passed"):
        return "router"
    return "reject"


def build_graph():
    from langgraph.graph import StateGraph, END

    builder = StateGraph(AgentState)

    builder.add_node("input_guard", input_guard_node)
    builder.add_node("reject", reject_node)
    builder.add_node("router", router_node)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("rerank", rerank_node)
    builder.add_node("generate", generate_node)
    builder.add_node("output_guard", output_guard_node)

    builder.set_entry_point("input_guard")
    builder.add_conditional_edges("input_guard", route_after_guard, {"router": "router", "reject": "reject"})
    builder.add_edge("reject", END)
    builder.add_edge("router", "retrieve")
    builder.add_edge("retrieve", "rerank")
    builder.add_edge("rerank", "generate")
    builder.add_edge("generate", "output_guard")
    builder.add_edge("output_guard", END)

    return builder.compile()


_graph = None


class _LazyGraph:
    def __getattr__(self, name):
        global _graph
        if _graph is None:
            _graph = build_graph()
        return getattr(_graph, name)


agent_graph = _LazyGraph()
