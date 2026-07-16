"""
Visualize the LangGraph agent graph.
Usage:
    python -m scripts.visualize_graph          # prints ASCII + Mermaid
    python -m scripts.visualize_graph --png     # saves PNG (needs pygraphviz)
"""
import sys
from app.agents.graph import agent_graph


def main():
    graph = agent_graph.get_graph()

    print("=" * 60)
    print("ASCII Graph")
    print("=" * 60)
    print(graph.draw_ascii())

    print("\n" + "=" * 60)
    print("Mermaid")
    print("=" * 60)
    print(graph.draw_mermaid())

    if "--png" in sys.argv:
        graph.draw_mermaid_png("agent_graph.png")
        print("\nSaved agent_graph.png")


if __name__ == "__main__":
    main()
