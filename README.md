# Public Health Dashboard

This repository contains one Grafana dashboard backed by the HIS-QA
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

Run Grafana on a small VM or internal server that can reach the HIS-QA
PostgreSQL endpoint. Put it behind an HTTPS reverse proxy or private VPN for
production use.

1. Copy this repository to the deployment host.
2. Set the database connection values, database password, and a non-default
   Grafana admin password in the shell or in a secrets manager. Do not commit
   these values.

```bash
export HIS_QA_DB_HOST='<database-host>:<database-port>'
export HIS_QA_DB_USER='<database-user>'
export HIS_QA_DB_NAME='<database-name>'
export HIS_QA_DB_SSLMODE='disable'
export HIS_QA_DB_PASSWORD='<database-password>'
export GF_ADMIN_PASSWORD='<strong-grafana-admin-password>'
```

3. Start Grafana:

```bash
docker compose up -d
```

Grafana will be available on port `3000`. The dashboard and datasource are
provisioned automatically from the mounted `provisioning` directory.

The current HIS-QA endpoint accepts PostgreSQL `sslmode: disable`. For
production, use a private network or VPN and enable TLS on the database if the
server supports it.

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
export HIS_QA_DB_HOST='<database-host>:<database-port>'
export HIS_QA_DB_USER='<database-user>'
export HIS_QA_DB_NAME='<database-name>'
export HIS_QA_DB_SSLMODE='disable'
export HIS_QA_DB_PASSWORD='<the supplied HIS-QA password>'
./run.sh
```

The local URL is http://localhost:3000.
