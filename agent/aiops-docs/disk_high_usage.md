# High Disk Usage Alert Runbook

## Alert
- **Name**: `HighDiskUsage`
- **Severity**: Warning or Critical
- **Trigger**: Disk usage exceeds the configured threshold.

## Impact
High disk usage can prevent log writes, block database/storage operations, and cause service crashes.

## Investigation Steps
1. Identify the affected mount point and disk usage trend.
2. List large directories and files.
3. Check whether logs, temporary files, backups, or core dumps are growing abnormally.
4. Verify whether log rotation or cleanup jobs are working.

## Common Causes
- Log files growing too quickly.
- Temporary files not cleaned up.
- Backup or export files left on local disk.
- Application writing unexpected large artifacts.

## Immediate Actions
1. Remove safe temporary files and old rotated logs.
2. Compress or move backup/export files to object storage.
3. Increase disk size if growth is expected.
4. Fix log rotation or cleanup jobs.

## Validation
Disk usage should return below the warning threshold and continue trending safely after cleanup.
