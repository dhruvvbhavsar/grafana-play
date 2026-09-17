# Scheduled dashboard refresh

AWS region: `ap-south-1`. Function and daily schedule name:
`aarogyahub-health-dashboard-refresh`.

EventBridge Scheduler invokes `handler.lambda_handler` daily using
`cron(0 4 * * ? *)`, time zone **Asia/Kolkata**, flexible window OFF.
AWS schedules have minute-level precision (04:00:00–04:00:59), not exact-second guarantees.

The handler executes only `CALL public.refresh_health_dashboard()`.
The existing procedure inserts missing diagnosis IDs and ANALYZEs the table;
it does not update already-inserted diagnoses. Its SQL definition is owned by
the database and is not modified by this project.

## Runtime and security

- Python 3.12, x86_64, 128 MB, 840-second Lambda timeout.
- Database statement timeout: 780 seconds.
- Reserved concurrency: 1; transaction advisory lock also prevents concurrent workers.
- DB credential read from Secrets Manager `grafana/aarogyahub/health-refresh`.
- `DB_SECRET_ARN` contains only the secret reference, not the credential.
- Secret JSON fields: `host`, `port`, `dbname`, `user`, `password`.
- `DB_TLS_MODE=verify-full` is the code default. The live deployment explicitly
  uses `require`: transport encryption without server certificate validation.
  For verified TLS, configure a trusted server certificate and matching DNS name.
- No VPC configuration: Lambda currently reaches the existing public database
  endpoint. No firewall rules were broadened for deployment. If the endpoint
  is later restricted, use VPC routing/NAT with an approved fixed egress IP.
- Dedicated IAM roles can access only this secret, function log group, and failure queue.
- CloudWatch log group `/aws/lambda/aarogyahub-health-dashboard-refresh`, retention 30 days.
- SQS failure queue `aarogyahub-health-dashboard-refresh-failures`, encrypted,
  retention 14 days. Both scheduler delivery failures and exhausted Lambda
  async failures are captured. No email/SMS notification subscription is configured.
- Lambda async retries: 1, maximum event age 3600s; scheduler delivery retries:
  2, maximum event age 3600s. Scheduling is at-least-once, not exactly-once.
- Only status/duration are logged. DB exception messages are deliberately suppressed.

Use separate least-privilege database roles for Grafana reads and procedure
execution when those roles are available. The deployment currently uses the
supplied database account for both.

## Tests

```bash
python3 -m venv /tmp/health-refresh-venv
/tmp/health-refresh-venv/bin/pip install -r aws/health_refresh/requirements.txt
/tmp/health-refresh-venv/bin/python -m unittest discover -s aws/health_refresh -v
```

Tests mock external AWS/database clients. A live AWS invocation and an actual
one-time scheduler trigger must additionally pass before deployment is accepted.
Verify all Grafana panel and variable queries after changing the database.

## Updating the existing Lambda

Package `handler.py` and pg8000 dependencies at the ZIP root. boto3 is provided
by the Lambda Python runtime. Use a clean build directory, exclude tests and
`__pycache__`, and do not include any `.env` file. Then:

```bash
aws lambda update-function-code --region ap-south-1 \
  --function-name aarogyahub-health-dashboard-refresh \
  --zip-file fileb:///absolute/path/health-refresh.zip
aws lambda wait function-updated-v2 --region ap-south-1 \
  --function-name aarogyahub-health-dashboard-refresh
aws lambda invoke --region ap-south-1 \
  --function-name aarogyahub-health-dashboard-refresh \
  --cli-read-timeout 900 /tmp/refresh-result.json
aws scheduler get-schedule --region ap-south-1 \
  --name aarogyahub-health-dashboard-refresh
```

A successful invocation returns `{"status":"refreshed"}` without `FunctionError`.
`skipped` means another transaction holds the refresh advisory lock.
Read the exact function config and schedule back after any changes.

## Grafana database migration

Grafana environment variables are `HIS_AAROGYAHUB_DB1_*`; HOST and PORT are
separate in the protected host `.env`, combined by Compose for provisioning.
The datasource UID `his-qa-postgres` is deliberately preserved to keep existing
panel references working. Its displayed name is HIS-AAROGYAHUB PostgreSQL.
The `deleteDatasources` migration entry removes only the legacy HIS-QA datasource
configuration; it does not delete database tables or dashboard data.

On the deployment host, `.env.pre-aarogyahub` retains a mode-600 rollback backup.
A rollback requires BOTH the earlier Git configuration and the matching old
`.env`; do not change just one of them. Never commit either secret file.
