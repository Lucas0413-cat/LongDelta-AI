from langchain_core.messages import HumanMessage

from src.graph.workflow import build_graph


def main():
    app = build_graph()
    question = input("你想分析什么？> ").strip()
    state = {"messages": [HumanMessage(content=question)]}
    out = app.invoke(state)
    print("\n=== Agent Output ===\n")
    print(out["messages"][-1].content)

if __name__ == "__main__":
    main()
