"""
LangGraph Workflow Compiler
===========================
Defines the structure, edges, conditional pathways, and checkpoint memory for the workflow.

WHY DO WE NEED WORKFLOW COMPILATION?
A workflow is a directed graph. In this file:
1. Nodes are registered (from nodes.py).
2. Directed transitions (edges) are established.
3. Conditional transitions (deciders) are configured. For example:
   - If input validation fails → Skip discovery and jump directly to summary.
4. A Checkpointer (MemorySaver) is attached to the compiled graph.
   - This checkpointer is CRITICAL for Human-In-The-Loop. It saves the graph's memory 
     state to RAM, allowing it to pause execution during `human_review` and resume
     exactly where it left off when the user issues an approval.
"""

from langgraph.graph import END, START, StateGraph      # Graph structures
from langgraph.checkpoint.memory import MemorySaver    # RAM checkpointer for interrupts

from app.graph.state import TestRunState                 # State dictionary schema
from app.graph.nodes import (                            # Node functions
    discovery_node,
    execution_node,
    failure_analysis_node,
    human_review_node,
    planning_node,
    self_healing_node,
    summary_node,
    test_generation_node,
    validate_target_node,
)


def route_after_validation(state: TestRunState) -> str:
    """
    Decides whether to proceed to element discovery or abort due to validation failures.

    Args:
        state: Current TestRunState.

    Returns:
        Name of the next node to transition to.
    """
    # If the validate_target node flagged the status as failed, route directly to summary
    if state.get("status") == "failed":
        print("[Router: route_after_validation] Target URL validation failed. Routing to summary.")
        return "summary"
    
    # Otherwise, proceed normally
    print("[Router: route_after_validation] Target URL valid. Routing to discovery.")
    return "discovery"


def build_test_workflow():
    """
    Constructs, connects, and compiles the directed workflow graph.
    """
    # Initialize the graph with our state definition
    builder = StateGraph(TestRunState)

    # 1. Register all nodes
    builder.add_node("validate_target", validate_target_node)
    builder.add_node("discovery", discovery_node)
    builder.add_node("planning", planning_node)
    builder.add_node("test_generation", test_generation_node)
    builder.add_node("human_review", human_review_node)
    builder.add_node("execution", execution_node)
    builder.add_node("failure_analysis", failure_analysis_node)
    builder.add_node("self_healing", self_healing_node)
    builder.add_node("summary", summary_node)

    # 2. Add static connections (edges)
    builder.add_edge(START, "validate_target")
    builder.add_edge("discovery", "planning")
    builder.add_edge("planning", "test_generation")
    builder.add_edge("test_generation", "human_review")
    builder.add_edge("human_review", "execution")
    builder.add_edge("execution", "summary")
    builder.add_edge("summary", END)

    # 3. Add conditional connection from validation node
    # Depending on route_after_validation return, goes to "discovery" or "summary"
    builder.add_conditional_edges(
        "validate_target",
        route_after_validation,
        {
            "discovery": "discovery",
            "summary": "summary"
        }
    )

    # 4. Compile graph with RAM checkpointer enabled
    # This checkpointer gives the graph 'session memory' to handle interruptions.
    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)