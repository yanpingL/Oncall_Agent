"""Time tool for getting current time information"""

from datetime import datetime
from zoneinfo import ZoneInfo

from langchain_core.tools import tool
from loguru import logger


@tool
def get_current_time(timezone: str = "Asia/Shanghai") -> str:
    """Get current time
    
    Use this tool when the user asks time-related questions such as current time, weekday, or date.
    
    Args:
        timezone: Timezone, default Asia/Shanghai (Beijing time)
        
    Returns:
        str: Formatted current time information
    """
    try:
        # Get current time for the specified timezone
        tz = ZoneInfo(timezone)
        now = datetime.now(tz)
        
        # Return formatted date-time string
        return now.strftime('%Y-%m-%d %H:%M:%S')
        
    except Exception as e:
        logger.error(f"Time query tool call failed: {e}")
        return f"Failed to get time: {str(e)}"
