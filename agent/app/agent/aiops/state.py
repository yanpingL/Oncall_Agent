
"""
Generic Plan-Execute-Replan state definition
Implemented based on the official LangGraph tutorial
"""

from typing import List, TypedDict, Annotated
import operator


class PlanExecuteState(TypedDict):
    """Plan-Execute-Replan Status"""
    
    # User input(task description)
    input: str
    
    # Execution plan (step list)
    plan: List[str]
    
    # Executed step history
    # Use operator.add for append-style updates instead of overwrite
    past_steps: Annotated[List[tuple], operator.add]
    
    # Final response/report
    response: str
