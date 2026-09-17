# Public Health Dashboard

This repository contains one Grafana dashboard backed by the HIS-AAROGYAHUB
PostgreSQL database. It does not include the old demo Prometheus stack or the
synthetic Python telemetry service.

## Dashboard

- **Public Health Dashboard** - district disease tracker, weekly patient
  visits, summary stats, and disease-category charts.
- Source relation: `public.diagnosis_dashboard_data`
- Dashboard file: `provisioning/dashboards/public-health-dashboard.json`

The dashboard is aggregate-only. It does not select patient names, UHIDs, or
health numbers.

## Recommended deployment: Docker Compose

Run Grafana on a small VM or internal server that can reach the HIS-AAROGYAHUB
PostgreSQL endpoint. Put it behind an HTTPS reverse proxy or private VPN for
production use.

1. Copy this repository to the deployment host.
2. Set the database connection values, database password, and a non-default
   Grafana admin password in the shell or in a secrets manager. Do not commit
   these values.

```bash
export HIS_AAROGYAHUB_DB1_HOST='<database-host>'
export HIS_AAROGYAHUB_DB1_PORT='<database-port>'
export HIS_AAROGYAHUB_DB1_USER='<database-user>'
export HIS_AAROGYAHUB_DB1_NAME='<database-name>'
export HIS_AAROGYAHUB_DB1_SSLMODE='require'
export HIS_AAROGYAHUB_DB1_PASSWORD='<database-password>'
export GF_ADMIN_PASSWORD='<strong-grafana-admin-password>'
```

3. Start Grafana:

```bash
docker compose up -d
```

Grafana will be available on port `3000`. The dashboard and datasource are
provisioned automatically from the mounted `provisioning` directory.

The deployment requires encrypted PostgreSQL connections (`sslmode: require`).
This encrypts transport but does not verify server identity. Use `verify-full`
with a trusted CA and matching DNS name when available. Prefer a dedicated
read-only Grafana database account; the refresh worker needs procedure execution.

Useful operations:

```bash
docker compose logs -f grafana
docker compose ps
docker compose down
```

## Local Homebrew run

If Grafana is already installed locally, the included launcher starts only
Grafana:

```bash
export HIS_AAROGYAHUB_DB1_HOST='<database-host>'
export HIS_AAROGYAHUB_DB1_PORT='<database-port>'
export HIS_AAROGYAHUB_DB1_USER='<database-user>'
export HIS_AAROGYAHUB_DB1_NAME='<database-name>'
export HIS_AAROGYAHUB_DB1_SSLMODE='require'
export HIS_AAROGYAHUB_DB1_PASSWORD='<the supplied HIS-AAROGYAHUB password>'
./run.sh
```

The local URL is http://localhost:3000.
