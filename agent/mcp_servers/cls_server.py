"""Tencent Cloud CLS (Cloud Log Service) MCP Server

Local CLS log service MCP server that provides log query, retrieval, and analysis features.
"""

import logging
import functools
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from fastmcp import FastMCP

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("CLS_MCP_Server")

mcp = FastMCP("CLS")


def log_tool_call(func):
    """Decorator: log tool calls, including method name, arguments, and return status"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        method_name = func.__name__

        # Log call information
        logger.info(f"=" * 80)
        logger.info(f"Method called: {method_name}")

        # Log arguments (excluding self, etc.)
        if kwargs:
            # Format arguments with json.dumps and handle possible serialization errors
            try:
                params_str = json.dumps(kwargs, ensure_ascii=False, indent=2)
            except (TypeError, ValueError):
                params_str = str(kwargs)
            logger.info(f"Arguments:\n{params_str}")
        else:
            logger.info("Arguments: none")

        # Execute method
        try:
            result = func(*args, **kwargs)

            # Log return status
            logger.info(f"Return status: SUCCESS")

            # Log a result summary to avoid overly long logs
            if isinstance(result, dict):
                summary = {k: v if not isinstance(v, (list, dict)) else f"<{type(v).__name__} with {len(v)} items>"
                          for k, v in list(result.items())[:5]}
                logger.info(f"Result summary: {json.dumps(summary, ensure_ascii=False)}")
            else:
                logger.info(f"Result: {result}")

            logger.info(f"=" * 80)
            return result

        except Exception as e:
            # Log error status
            logger.error(f"Return status: ERROR")
            logger.error(f"Error message: {str(e)}")
            logger.error(f"=" * 80)
            raise

    return wrapper


def parse_time_or_default(time_str: Optional[str], default_offset_hours: int = 0) -> datetime:
    """Parse a time string or return the default time.

    Args:
        time_str: Time string (format: YYYY-MM-DD HH:MM:SS)
        default_offset_hours: Default time offset in hours

    Returns:
        datetime: Parsed datetime object
    """
    if time_str:
        try:
            return datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    return datetime.now() + timedelta(hours=default_offset_hours)


def generate_time_series(base_time: datetime, minutes_offset: int) -> str:
    """Generate a time string based on the reference time.

    Args:
        base_time: Reference time
        minutes_offset: Minute offset

    Returns:
        str: Formatted time string
    """
    result_time = base_time + timedelta(minutes=minutes_offset)
    return result_time.strftime("%Y-%m-%d %H:%M:%S")


@mcp.tool()
@log_tool_call
def get_current_timestamp() -> int:
    """Get the current timestamp in milliseconds.
    
    This tool returns a standard millisecond timestamp and can be used to:
    1. Use as the search_log end_time argument to query up to now
    2. Calculate a historical timestamp for the start_time argument
    
    Returns:
        int: current timestamp in milliseconds, for example: 1708012345000
    
    Usage examples:
        # Get the current time
        current = get_current_timestamp()
        
        # Calculate the time 15 minutes ago
        fifteen_min_ago = current - (15 * 60 * 1000)
        
        # Calculate the time 1 hour ago
        one_hour_ago = current - (60 * 60 * 1000)
        
        # Use it to search logs from the last 15 minutes
        search_log(
            topic_id="topic-001",
            start_time=fifteen_min_ago,
            end_time=current
        )
    """
    return int(datetime.now().timestamp() * 1000)


@mcp.tool()
@log_tool_call
def get_region_code_by_name(region_name: str) -> Dict[str, Any]:
    """Find the region parameters for a region name.

    Args:
        region_name: Region name, such as Beijing, Shanghai, or Guangzhou

    Returns:
        Dict: Dictionary containing the region code and related information
            - region_code: region code
            - region_name: region name
            - available: whether it is available
    """
    # Mock region mapping table; in production this should come from configuration or a database
    region_mapping = {
        "Beijing": {"region_code": "ap-beijing", "region_name": "Beijing", "available": True},
        "Shanghai": {"region_code": "ap-shanghai", "region_name": "Shanghai", "available": True},
        "Guangzhou": {"region_code": "ap-guangzhou", "region_name": "Guangzhou", "available": True},
    }

    result = region_mapping.get(region_name)
    if result:
        return result
    else:
        return {
            "region_code": None,
            "region_name": region_name,
            "available": False,
            "error": f"Region not found: {region_name}"
        }


@mcp.tool()
@log_tool_call
def get_topic_info_by_name(topic_name: str, region_code: Optional[str] = None) -> Dict[str, Any]:
    """Search topic information by topic name.

    Args:
        topic_name: topic name
        region_code: region code (optional)

    Returns:
        Dict: Dictionary containing topic information
            - topic_id: topic ID
            - topic_name: topic name
            - region_code: region
            - create_time: creation time
            - log_count: log count
    """
    mock_topics = [
        {
            "topic_id": "topic-001",
            "topic_name": "Data sync service logs",
            "service_name": "data-sync-service",
            "region_code": "ap-beijing",
            "create_time": "2024-01-01 10:00:00",
            "log_count": 0,
            "description": "Service application logs"
        }
    ]

    # Filter by name and region
    for topic in mock_topics:
        if topic["topic_name"] == topic_name:
            if region_code is None or topic["region_code"] == region_code:
                return topic

    return {
        "topic_id": None,
        "topic_name": topic_name,
        "region_code": region_code,
        "error": f"Topic not found: {topic_name}"
    }


@mcp.tool()
@log_tool_call
def search_topic_by_service_name(
    service_name: str,
    region_code: Optional[str] = None,
    fuzzy: bool = True
) -> Dict[str, Any]:
    """Search related log topic information by service name with fuzzy matching support.
    
    This tool finds the corresponding log topic for a service name so later log queries can use it.
    
    Args:
        service_name: service name (required)
            Example: "data-sync-service", "sync", "data-sync"
            Description: When fuzzy=True, partial matching is supported
        
        region_code: region code (optional)
            Example: "ap-beijing", "ap-shanghai"
            Description: If specified, only topics in that region are returned
        
        fuzzy: whether fuzzy search is enabled (optional, default: True)
            True: partial match, for example "sync" can match "data-sync-service"
            False: exact match, must match exactly
    
    Returns:
        Dict: search result
            - total: number of matched topics
            - topics: topic list; each topic contains:
                * topic_id: topic ID used for later log queries
                * topic_name: topic name
                * service_name: service name
                * region_code: region
                * create_time: creation time
                * log_count: log count
                * description: topic description
            - query: query criteria
    
    Usage examples:
        # Example1: Fuzzy search (recommended)
        search_topic_by_service_name(service_name="data-sync")
        # can match: "data-sync-service", "data-sync-worker" etc.
        
        # Example2: Exact search
        search_topic_by_service_name(
            service_name="data-sync-service",
            fuzzy=False
        )
        
        # Example3: Search in a specified region
        search_topic_by_service_name(
            service_name="sync",
            region_code="ap-beijing"
        )
        
        # Example4: Full workflow for finding a topic and then searching logs
        # Step1: Find a topic by service name
        result = search_topic_by_service_name(service_name="data-sync-service")
        
        # Step2: Get the topic_id
        topic_id = result["topics"][0]["topic_id"]  # "topic-001"
        
        # Step3: Query logs with the topic_id
        current_ts = get_current_timestamp()
        start_ts = current_ts - (15 * 60 * 1000)
        search_log(
            topic_id=topic_id,
            start_time=start_ts,
            end_time=current_ts
        )
    """
    # Mock topic data; in production this should come from configuration or a database
    mock_topics = [
        {
            "topic_id": "topic-001",
            "topic_name": "Data sync service logs",
            "service_name": "data-sync-service",
            "region_code": "ap-beijing",
            "create_time": "2024-01-01 10:00:00",
            "log_count": 0,
            "description": "Application logs for the data sync service, including sync task execution details"
        },
        {
            "topic_id": "topic-002",
            "topic_name": "Data sync service error logs",
            "service_name": "data-sync-service",
            "region_code": "ap-beijing",
            "create_time": "2024-01-01 10:00:00",
            "log_count": 0,
            "description": "Error logs for the data sync service"
        },
        {
            "topic_id": "topic-003",
            "topic_name": "API gateway service logs",
            "service_name": "api-gateway-service",
            "region_code": "ap-shanghai",
            "create_time": "2024-01-01 10:00:00",
            "log_count": 0,
            "description": "API gateway service logs"
        }
    ]
    
    matched_topics = []
    
    # Search logic
    for topic in mock_topics:
        # Region filter
        if region_code and topic["region_code"] != region_code:
            continue
        
        # Service name matching
        topic_service_name = topic.get("service_name", "")
        
        if fuzzy:
            # Fuzzy matching: service name contains the query string, or the query string contains the service name
            if (service_name.lower() in topic_service_name.lower() or 
                topic_service_name.lower() in service_name.lower()):
                matched_topics.append(topic)
        else:
            # exact match
            if topic_service_name == service_name:
                matched_topics.append(topic)
    
    return {
        "total": len(matched_topics),
        "topics": matched_topics,
        "query": {
            "service_name": service_name,
            "region_code": region_code,
            "fuzzy": fuzzy
        },
        "message": f"Found {len(matched_topics)} matching log topics" if matched_topics else f"No log topic found for service '{service_name}'"
    }


@mcp.tool()
@log_tool_call
def search_log(
    topic_id: str,
    start_time: int,
    end_time: int,
    query: Optional[str] = None,
    limit: int = 100
) -> Dict[str, Any]:
    """Search logs using the provided query parameters.

    Args:
        topic_id: topic ID (required)
            Example: "topic-001"
        
        start_time: start timestamp in milliseconds (required, int)
            Important: must be an integer millisecond timestamp
            How to obtain it: 
            1. Use get_current_timestamp() to get the current timestamp
            2. Calculate historical time: current_timestamp - (number of minutes * 60 * 1000)
            Example: 
            - current time: 1708012345000
            - 15 minutes ago: 1708012345000 - (15 * 60 * 1000) = 1708011445000
            - 1 hour ago: 1708012345000 - (60 * 60 * 1000) = 1708008745000
        
        end_time: end timestamp in milliseconds (required, int)
            Important: must be an integer millisecond timestamp
            Usually use get_current_timestamp() to get the current time as the end time
            Example: 1708012345000
        
        query: query expression (optional, CLS query syntax)
            Example: "level:ERROR" or "message:exception"
        
        limit: result limit (default: 100, optional)

    Returns:
        Dict: search result
            - topic_id: topic ID
            - start_time: start timestamp
            - end_time: end timestamp
            - query: query expression
            - limit: result limit
            - total: actual number of returned log entries
            - logs: log list; each log entry contains:
                * timestamp: log time (format: YYYY-MM-DD HH:MM:SS)
                * level: log level
                * message: log message
            - took_ms: query latency (milliseconds)
            - message: query status message
    
    Usage examples:
        # Step1: Get the current timestamp
        current_ts = get_current_timestamp()  # returns: 1708012345000
        
        # Step2: Calculate the start time (15 minutes ago)
        start_ts = current_ts - (15 * 60 * 1000)  # 1708011445000
        
        # Step3: Search logs
        search_log(
            topic_id="topic-001",
            start_time=start_ts,     # int type: 1708011445000
            end_time=current_ts,     # int type: 1708012345000
            limit=100
        )
    """
    # Return different results based on topic_id
    if topic_id == "topic-001":
        # topic-001: application logs with dynamically generated INFO entries
        logs = []
        current_time_ms = start_time
        count = 0

        # Calculate the maximum number of logs that can be generated based on the time range
        max_logs_by_time = int((end_time - start_time) / (60 * 1000)) + 1

        # Use the smaller value of limit and the maximum log count within the time range
        actual_limit = min(limit, max_logs_by_time)

        while current_time_ms <= end_time and count < actual_limit:
            # Convert the millisecond timestamp to a readable format
            log_time = datetime.fromtimestamp(current_time_ms / 1000)
            time_str = log_time.strftime("%Y-%m-%d %H:%M:%S")

            log_entry = {
                "timestamp": time_str,
                "level": "INFO",
                "message": "Synchronizing metadata..."
            }

            logs.append(log_entry)
            count += 1

            # Increase the next log timestamp by 1 minute (60 seconds * 1000 milliseconds)
            current_time_ms += 60 * 1000

        return {
            "topic_id": topic_id,
            "start_time": start_time,
            "end_time": end_time,
            "query": query,
            "limit": limit,
            "total": len(logs),
            "logs": logs,
            "took_ms": 50,
            "message": f"Successfully queried {len(logs)} application log entries"
        }
    else:
        # Other topic_id values return an error indicating the topic does not exist
        return {
            "topic_id": topic_id,
            "start_time": start_time,
            "end_time": end_time,
            "query": query,
            "limit": limit,
            "total": 0,
            "logs": [],
            "took_ms": 0,
            "error": f"Topic does not exist: {topic_id}",
            "message": f"Error: Topic not found {topic_id}; please check whether the topic_id is correct"
        }



if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="127.0.0.1", port=8003, path="/mcp")
