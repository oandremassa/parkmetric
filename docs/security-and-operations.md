# Security and operations

## Baseline controls

ParkMetric relies on Django's established security middleware and implements:

- CSRF protection for browser/session mutations;
- server-side authorization and site scoping;
- session-authenticated API;
- secure production cookies and HTTPS redirect;
- HSTS and clickjacking protection;
- login attempt lockout/rate limiting with django-axes;
- `DEBUG=False` in production settings;
- required production secret/host/origin/database configuration;
- no application secrets committed to the repository;
- health check with no exception/configuration disclosure;
- logs that avoid request bodies, passwords, tokens, and database credentials.

## Required production environment

`config.settings.production` requires `SECRET_KEY`, `DATABASE_URL`, `ALLOWED_HOSTS`, and `CSRF_TRUSTED_ORIGINS`. Missing values fail during startup instead of silently using demonstration defaults.

Use a reverse proxy/load balancer that terminates TLS. Only trust `X-Forwarded-Proto` from infrastructure you control.

## Logs

The default console format logs timestamp, severity, logger name, and message. It intentionally does not configure request-body logging. Infrastructure should collect stdout/stderr and apply retention/access controls appropriate to the deployment.

## Health

`GET /health/` performs `SELECT 1` against PostgreSQL. Success returns `200 ok`; database failure returns `503 unavailable`. No server version, environment value, or exception text is exposed.

## Backups

Create a custom-format PostgreSQL backup:

```bash
./scripts/backup_postgres.sh ./backups/parkmetric.dump
```

Restore only to an explicitly supplied verification database:

```bash
RESTORE_DATABASE_URL='postgresql://...' ./scripts/restore_postgres.sh ./backups/parkmetric.dump
```

A backup is not considered verified until it has been restored to a separate database and application-level checks have passed.

Suggested operational policy:

1. automated encrypted backups outside the application host;
2. retention appropriate to business/legal needs;
3. restricted access to backup storage;
4. periodic restore drills;
5. documented RPO/RTO owned by the eventual operator.

## Deployment boundary

The included Docker/Gunicorn configuration is a reproducible deployment baseline, not a claim that every commercial environment is production-ready. Before real deployment, validate infrastructure-specific TLS/proxy settings, secrets management, database sizing/HA, monitoring, alerting, vulnerability management, retention/privacy requirements, load characteristics, and disaster recovery.
