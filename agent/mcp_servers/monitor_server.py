"""Intelligent operations monitoring MCP Server

Local monitoring MCP server that provides:
- Monitoring data queries (CPU, memory, disk, network, etc.)
- Process information queries
- Historical ticket queries
- Service information queries

Supports troubleshooting scenarios for the operations agent.
"""

import logging
import functools
import json
import random
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from fastmcp import FastMCP
from app.core.prometheus_alerts import get_prometheus_alerts_summary

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("Monitor_MCP_Server")

mcp = FastMCP("Monitor")


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


# ============================================================
# Helper functions
# ============================================================

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
    # Return the default time (current time plus offset)
    return datetime.now() + timedelta(hours=default_offset_hours)


def generate_time_series(base_time: datetime, minutes_offset: int, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Generate a time-series string.

    Args:
        base_time: Reference time
        minutes_offset: Minute offset
        format_str: Time format string

    Returns:
        str: Formatted time string
    """
    result_time = base_time + timedelta(minutes=minutes_offset)
    return result_time.strftime(format_str)





# ============================================================
# Monitoring data query tools
# ============================================================

@mcp.tool()
@log_tool_call
def query_prometheus_alerts() -> Dict[str, Any]:
    """Query current active alerts from the configured Prometheus or AMP workspace.

    Returns:
        Dict: Simplified Prometheus alert data, including alert list, state counts, total count,
        and error information when the query fails.
    """
    return get_prometheus_alerts_summary()


@mcp.tool()
@log_tool_call
def query_cpu_metrics(
    service_name: str,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    interval: str = "1m"
) -> Dict[str, Any]:
    """Query CPU usage metrics for a service.

    Args:
        service_name: service name(required)
            Example: "data-sync-service"
        
        start_time: start time(optional,string type)
            Format: "YYYY-MM-DD HH:MM:SS"
            Example: "2026-02-14 10:00:00"
            Default: defaults to one hour before the current time if omitted
            Note: must be a string, not a timestamp
        
        end_time: end time(optional,string type)
            Format: "YYYY-MM-DD HH:MM:SS"
            Example: "2026-02-14 11:00:00"
            Default: defaults to the current time if omitted
            Note: must be a string, not a timestamp
        
        interval: data aggregation interval(optional)
            Allowed values: "1m" (1minutes), "5m" (5minutes), "1h" (1hours)
            Default: "1m"
            Description: controls the time interval between data points

    Returns:
        Dict: CPU monitoring data
            - service_name: service name
            - metric_name: metric name (cpu_usage_percent)
            - interval: data aggregation interval
            - data_points: data point list,each point contains:
                * timestamp: timestamp(Format: HH:MM)
                * value: CPU usage percentage
            - statistics: statistics
                * average: average
                * max: maximum
                * min: minimum
            - alert: alert informationif present
                * triggered: whether the alert was triggered
                * threshold: alert threshold
                * message: alert message
    
    Usage examples:
        # Example1: Use the default time(the last hour)
        query_cpu_metrics(service_name="data-sync-service")
        
        # Example2: Specify a time range
        query_cpu_metrics(
            service_name="data-sync-service",
            start_time="2026-02-14 10:00:00",
            end_time="2026-02-14 11:00:00",
            interval="5m"
        )
        
        # Example3: Specify only the start time; end time defaults to the current time
        query_cpu_metrics(
            service_name="data-sync-service",
            start_time="2026-02-14 10:00:00"
        )
    """
    # Parse time arguments
    start_dt = parse_time_or_default(start_time, default_offset_hours=-1)
    end_dt = parse_time_or_default(end_time, default_offset_hours=0)
    
    # Parse interval duration(interval: 1m, 5m, 1h etc.)
    interval_minutes = 1  # default: 1 minute
    if interval.endswith('m'):
        interval_minutes = int(interval[:-1])
    elif interval.endswith('h'):
        interval_minutes = int(interval[:-1]) * 60

    # Dynamically generate CPU usage data that gradually increases from low to high
    data_points = []
    current_time = start_dt
    time_index = 0

    # Initial CPU usage (10%)
    base_cpu = 10.0

    while current_time <= end_dt:
        # Algorithm for gradually increasing CPU usage:
        # - The first few data points stay around 10%
        # - Then the value starts rising quickly
        # - Eventually reaches around 95%

        if time_index < 3:
            # Initial phase: fluctuates around 10%
            cpu_value = base_cpu + (time_index * 0.5)
        else:
            # Growth phase: use an exponential growth model
            growth_factor = (time_index - 2) * 8.5
            cpu_value = min(base_cpu + growth_factor, 96.0)

        # Add small random fluctuation (+/-2%)
        cpu_value = round(cpu_value + random.uniform(-2, 2), 1)
        cpu_value = max(0, min(100, cpu_value))  # Clamp to the 0-100 range

        data_point = {
            "timestamp": current_time.strftime("%H:%M"),
            "value": cpu_value,
            "process_id": "pid-12345"
        }

        data_points.append(data_point)

        # Next timestamp
        current_time += timedelta(minutes=interval_minutes)
        time_index += 1

    # Calculate statistics
    if data_points:
        values = [d["value"] for d in data_points]
        avg_value = round(sum(values) / len(values), 2)
        max_value = max(values)
        min_value = min(values)

        # Detect whether there is a CPU spike above 80%
        spike_detected = max_value > 80.0

        return {
            "service_name": service_name,
            "metric_name": "cpu_usage_percent",
            "interval": interval,
            "data_points": data_points,
            "statistics": {
                "avg": avg_value,
                "max": max_value,
                "min": min_value,
                "p95": round(sorted(values)[int(len(values) * 0.95)] if len(values) > 1 else max_value, 2),
                "spike_detected": spike_detected
            },
            "alert_info": {
                "triggered": spike_detected,
                "threshold": 80.0,
                "message": "CPU usage continuously exceeds the 80% threshold" if spike_detected else "CPU usage is normal"
            }
        }
    else:
        return {
            "service_name": service_name,
            "metric_name": "cpu_usage_percent",
            "interval": interval,
            "data_points": [],
            "statistics": {},
        }


@mcp.tool()
@log_tool_call
def query_memory_metrics(
    service_name: str,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    interval: str = "1m"
) -> Dict[str, Any]:
    """Query memory usage metrics for a service.

    Args:
        service_name: service name(required)
            Example: "data-sync-service"
        
        start_time: start time(optional,string type)
            Format: "YYYY-MM-DD HH:MM:SS"
            Example: "2026-02-14 10:00:00"
            Default: defaults to one hour before the current time if omitted
            Note: must be a string, not a timestamp
        
        end_time: end time(optional,string type)
            Format: "YYYY-MM-DD HH:MM:SS"
            Example: "2026-02-14 11:00:00"
            Default: defaults to the current time if omitted
            Note: must be a string, not a timestamp
        
        interval: data aggregation interval(optional)
            Allowed values: "1m" (1minutes), "5m" (5minutes), "1h" (1hours)
            Default: "1m"

    Returns:
        Dict: Memory monitoring data
            - service_name: service name
            - metric_name: metric name (memory_usage_percent)
            - interval: data aggregation interval
            - data_points: data point list,each point contains:
                * timestamp: timestamp(Format: HH:MM)
                * value: Memory usage percentage
                * used_gb: Used memory (GB)
                * total_gb: Total memory (GB)
            - statistics: statistics
                * average: average
                * max: maximum
                * min: minimum
            - alert: alert informationif present
                * triggered: whether the alert was triggered
                * threshold: alert threshold
                * message: alert message
    
    Usage examples:
        # Example1: Use the default time(the last hour)
        query_memory_metrics(service_name="data-sync-service")
        
        # Example2: Specify a time range
        query_memory_metrics(
            service_name="data-sync-service",
            start_time="2026-02-14 10:00:00",
            end_time="2026-02-14 11:00:00",
            interval="5m"
        )
    """
    # Parse time arguments
    start_dt = parse_time_or_default(start_time, default_offset_hours=-1)
    end_dt = parse_time_or_default(end_time, default_offset_hours=0)
    
    # Parse interval duration(interval: 1m, 5m, 1h etc.)
    interval_minutes = 1  # default: 1 minute
    if interval.endswith('m'):
        interval_minutes = int(interval[:-1])
    elif interval.endswith('h'):
        interval_minutes = int(interval[:-1]) * 60
    
    # Dynamically generate memory usage data that gradually increases from low to high
    data_points = []
    current_time = start_dt
    time_index = 0
    
    # Initial memory usage (30%)
    base_memory = 30.0
    total_gb = 8.0  # Total memory: 8 GB
    
    while current_time <= end_dt:
        # Algorithm for gradually increasing memory usage:
        # - The first few data points stay around 30%
        # - Then the value starts rising gradually
        # - Eventually reaches around 85%
        
        if time_index < 3:
            # Initial phase: fluctuates around 30%
            memory_value = base_memory + (time_index * 1.0)
        else:
            # Growth phase: use a linear growth model (memory grows more slowly than CPU)
            growth_factor = (time_index - 2) * 5.5
            memory_value = min(base_memory + growth_factor, 85.0)
        
        # Add small random fluctuation (+/-1%)
        memory_value = round(memory_value + random.uniform(-1, 1), 1)
        memory_value = max(0, min(100, memory_value))  # Clamp to the 0-100 range
        
        # Calculate used memory (GB)
        used_gb = round((memory_value / 100.0) * total_gb, 2)
        
        data_point = {
            "timestamp": current_time.strftime("%H:%M"),
            "value": memory_value,
            "used_gb": used_gb,
            "total_gb": total_gb
        }
        
        data_points.append(data_point)
        
        # Next timestamp
        current_time += timedelta(minutes=interval_minutes)
        time_index += 1
    
    # Calculate statistics
    if data_points:
        values = [d["value"] for d in data_points]
        avg_value = round(sum(values) / len(values), 2)
        max_value = max(values)
        min_value = min(values)
        
        # Detect memory pressure above 70%
        memory_pressure = max_value > 70.0
        
        return {
            "service_name": service_name,
            "metric_name": "memory_usage_percent",
            "interval": interval,
            "data_points": data_points,
            "statistics": {
                "avg": avg_value,
                "max": max_value,
                "min": min_value,
                "p95": round(sorted(values)[int(len(values) * 0.95)] if len(values) > 1 else max_value, 2),
                "memory_pressure": memory_pressure
            },
            "alert_info": {
                "triggered": memory_pressure,
                "threshold": 70.0,
                "message": "Memory usage exceeds the 70% threshold; memory pressure exists" if memory_pressure else "Memory usage is normal"
            }
        }
    else:
        return {
            "service_name": service_name,
            "metric_name": "memory_usage_percent",
            "interval": interval,
            "data_points": [],
            "statistics": {},
            "error": "Invalid time range or no data points were generated"
        }




if __name__ == "__main__":
    # Run in streamable-http mode on port 8004
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8004, path="/mcp")
