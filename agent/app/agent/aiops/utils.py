
"""
Common utility functions for AIOps Agent
"""

from typing import List


def format_tools_description(tools: List) -> str:
    """Format tool list as description text"""
    tool_descriptions = []
    for tool in tools:
        if hasattr(tool, 'name') and hasattr(tool, 'description'):
            tool_descriptions.append(f"- {tool.name}: {tool.description}")
    return "\n".join(tool_descriptions)
