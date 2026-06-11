# High Memory Usage Alert Runbook

## Alert
- **Name**: `HighMemoryUsage`
- **Severity**: Critical
- **Trigger**: Memory usage stays above 85% for 5 minutes.

## Impact
High memory usage can cause garbage collection pressure, OOM kills, container restarts, request latency, and service instability.

## Investigation Steps
1. Query memory metrics for the affected service and instance.
2. Check process memory usage and identify the largest consumers.
3. Review application logs for OOM, allocation failures, or repeated retries.
4. Compare recent deployments or traffic changes with the alert time.

## Common Causes
- Memory leak after a new release.
- Cache growth without eviction.
- Large batch job or oversized payload processing.
- Traffic spike increasing concurrent memory use.

## Immediate Actions
1. Restart affected instances if memory is not being released.
2. Scale out instances if load-related.
3. Reduce batch size or disable risky jobs temporarily.
4. Roll back recent release if leak symptoms started after deployment.

## Validation
Memory should stabilize below the alert threshold, no OOM events should recur, and service latency should return to normal.
