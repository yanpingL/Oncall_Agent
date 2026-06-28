
# Service Unavailable Alert Runbook

## Alert
- **Name**: `ServiceUnavailable`
- **Severity**: Critical
- **Trigger**: Service health checks fail or availability drops below threshold.

## Impact
Users may be unable to access the service. Upstream services may see errors, retries, and cascading failures.

## Investigation Steps
1. Check service health and instance status.
2. Review recent deployments, restarts, and scaling events.
3. Query application logs for startup failures, crashes, dependency errors, or configuration issues.
4. Check load balancer target health and dependency availability.

## Common Causes
- Bad deployment or incompatible configuration.
- Dependency outage, such as database, cache, or external API failure.
- Container crash loop or failed health check.
- Resource exhaustion.

## Immediate Actions
1. Roll back the latest deployment if it caused the outage.
2. Restart unhealthy instances if safe.
3. Scale out if capacity is insufficient.
4. Fail over or disable dependency-dependent features if a dependency is down.

## Validation
Health checks should pass, error rate should return to normal, and traffic should be served by healthy instances.
