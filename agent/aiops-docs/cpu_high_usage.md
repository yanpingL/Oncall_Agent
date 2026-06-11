# High CPU Usage Alert Runbook

## Alert
- **Name**: `HighCPUUsage`
- **Severity**: Critical
- **Trigger**: CPU usage stays above 80% for 5 minutes.

## Impact
Sustained high CPU can slow application responses, increase request timeouts, raise system load, and trigger cascading failures.

## Investigation Steps
1. Get the current time with `get_current_time` to define the investigation window.
2. Query system logs for the last 30 minutes with conditions such as `level:ERROR OR cpu_usage:>80`.
3. Identify CPU-heavy processes, including process name, PID, CPU percentage, start time, and owning service.
4. Query application logs around the alert time with `level:ERROR OR level:WARN`.

## Common Causes
- Infinite loop or recursion: one process is near 100% CPU and logs show repeated stack traces.
- Traffic spike: multiple processes rise together and request volume increases.
- Overlapping scheduled jobs: CPU rises periodically at fixed times.
- Slow database queries: application CPU is high while business logic is simple, often with slow SQL logs.

## Immediate Actions
1. Scale out service instances if traffic is the cause.
2. Enable rate limiting if malicious traffic is suspected.
3. Restart a single bad instance if only one instance is affected.

## Follow-up Actions
1. Analyze logs to identify the root cause.
2. Roll back if the issue is code-related.
3. Adjust configuration if configuration caused the incident.
4. Continue monitoring CPU recovery.

## Validation
Confirm CPU returns below 60%, response time recovers, no new error logs appear, and the issue does not recur for 30 minutes.
