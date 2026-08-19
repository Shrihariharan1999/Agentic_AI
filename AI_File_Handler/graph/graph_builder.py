from langgraph.graph import START, END, StateGraph

from graph.state import AgentState
from graph.nodes import chatbot_node

builder = StateGraph(AgentState)

builder.add_node("chatbot", chatbot_node)

builder.add_edge(START, "chatbot")
builder.add_edge("chatbot", END)

graph = builder.compile()