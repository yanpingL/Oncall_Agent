# Slow Response Alert Runbook

## Alert
- **Name**: `SlowResponse`
- **Severity**: Warning or Critical
- **Trigger**: Request latency exceeds the configured threshold.

## Impact
Slow responses degrade user experience, increase timeout rates, and can cause upstream retry storms.

## Investigation Steps
1. Check latency metrics by service, route, and instance.
2. Review application logs for slow requests, timeouts, and dependency errors.
3. Check CPU, memory, database, cache, and external dependency metrics.
4. Compare latency changes with deployments, traffic spikes, or infrastructure events.

## Common Causes
- Slow database queries or lock contention.
- External dependency latency.
- Thread pool or connection pool exhaustion.
- High CPU, memory pressure, or garbage collection pauses.

## Immediate Actions
1. Scale out if latency is load-related.
2. Roll back a bad release if latency started after deployment.
3. Increase or recover exhausted connection pools.
4. Degrade non-critical features if a dependency is slow.

## Validation
Latency percentiles should return to normal and timeout/error rates should drop.
