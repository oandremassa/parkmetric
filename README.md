# ParkMetric

ParkMetric is a multi-site parking operations and analytics platform built with Django and PostgreSQL. It is designed as a complete portfolio-grade demonstration product: operators can register entries and checkouts, managers can manage capacity and tariff versions, administrators control users and site access, and historical reports are derived from persisted operations.

> **Demonstration software.** Payments are simulated. ParkMetric does not process real money, control gates, perform license-plate recognition, or integrate with third-party payment providers.

## Product scope

- Multi-parking-lot operation with per-site time zone and currency.
- Administrator, manager, and operator roles with server-side site scoping.
- Parking spot lifecycle: free, occupied, blocked, and inactive.
- Vehicle registry and active/completed stay history.
- Manual or automatic spot assignment with PostgreSQL row locking.
- Versioned tariffs with grace periods, billing intervals, and per-24-hour caps.
- Checkout quote acceptance, controlled simulated payment success/failure, and zero-charge waivers.
- Atomic close/payment/spot-release flow and request idempotency.
- Read-only audit trail for operational and administrative actions.
- Current occupancy plus historical daily, monthly, annual, hourly, and cross-site analytics.
- Filtered CSV exports protected against spreadsheet formula injection.
- Session-authenticated REST API with OpenAPI/Swagger documentation.
- Deterministic 90-day synthetic demo data and a compact 7-day demo option.
- Docker, production settings, PostgreSQL backup/restore guidance, and GitHub Actions CI.

## Technology

- Python 3.13
- Django 5.2.18 LTS
- Django REST Framework 3.17.2
- drf-spectacular 0.30.0
- PostgreSQL 17.11
- psycopg 3.3.6
- Gunicorn 23.0.0
- WhiteNoise 6.12.0
- django-axes 8.3.1

Dependencies are pinned in `requirements.txt` and `requirements-dev.txt`.


## Deploy to Railway

A Railway-specific package is included. The Docker image reads Railway's dynamic `PORT`, consumes the managed PostgreSQL `DATABASE_URL`, recognizes `RAILWAY_PUBLIC_DOMAIN` automatically, runs migrations on startup, and can seed an idempotent compact portfolio demo.

See [`RAILWAY.md`](RAILWAY.md) and [`.env.railway.example`](.env.railway.example) for the exact deployment steps and variables.

## Quick start with Docker

Requirements: Docker with Compose v2.

```bash
cp .env.example .env
```

Edit `.env` before starting. At minimum, replace `SECRET_KEY` and `POSTGRES_PASSWORD`. For local Docker execution use values such as:

```dotenv
DJANGO_SETTINGS_MODULE=config.settings.production
SECRET_KEY=replace-with-a-long-random-secret
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://localhost:8000
POSTGRES_DB=parkmetric
POSTGRES_USER=parkmetric
POSTGRES_PASSWORD=replace-with-a-strong-local-password
DEMO_MODE=true
ALLOW_DEMO_RESET=true
DEMO_PASSWORD=choose-a-demo-password
SECURE_SSL_REDIRECT=false
SESSION_COOKIE_SECURE=false
CSRF_COOKIE_SECURE=false
```

Then:

```bash
docker compose up --build -d
docker compose exec web python manage.py seed_demo --reference-date 2026-10-07
docker compose exec web python manage.py check
```

Open `http://localhost:8000`. The demo command creates `demo_admin`, `demo_manager`, and `demo_operator`; their password is the value you explicitly set in `DEMO_PASSWORD`.

The demo is **never** loaded on normal startup. `--reset` is additionally gated by `ALLOW_DEMO_RESET=true`.

## Local macOS / PyCharm without Docker

PostgreSQL is mandatory; SQLite is intentionally unsupported because concurrency behaviour is part of the product requirements.

1. Install Python 3.13 and PostgreSQL 17 using your preferred package manager.
2. Create a database and user, for example:

```sql
CREATE USER parkmetric WITH PASSWORD 'local-development-password';
CREATE DATABASE parkmetric OWNER parkmetric;
```

3. Create and activate a virtual environment:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
cp .env.example .env
```

4. Set `DATABASE_URL=postgresql://parkmetric:local-development-password@localhost:5432/parkmetric` and use `DJANGO_SETTINGS_MODULE=config.settings.development`.
5. Run:

```bash
python manage.py migrate
python manage.py seed_demo --small --reference-date 2026-10-07
python manage.py runserver
```

For PyCharm, select `.venv/bin/python` as the project interpreter. Create a Django run configuration with `manage.py`, `runserver`, and environment file `.env`. The same interpreter can run pytest from the built-in test runner.

## Demo data

Full deterministic dataset:

```bash
python manage.py seed_demo --seed 42 --reference-date 2026-10-07
```

Compact dataset:

```bash
python manage.py seed_demo --small --seed 42 --reference-date 2026-10-07
```

Explicit reset, only when both demo flags permit it:

```bash
python manage.py seed_demo --reset --seed 42 --reference-date 2026-10-07
```

The full dataset spans 90 days, creates three synthetic parking lots with different tariffs/capacities, demand variation, completed and active stays, failed simulated payments, successful simulated payments, and grace-period waivers. It never uses real customer data.

## Roles and authorization

| Capability | Administrator | Manager | Operator |
|---|---:|---:|---:|
| All parking lots | Yes | Assigned only | Assigned only |
| Manage users and site access | Yes | No | No |
| Create/edit parking lots | Yes | No | No |
| Manage spots | Yes | Assigned only | No |
| Manage tariff versions | Yes | Assigned only | No |
| Register entry/checkout | Yes | Assigned only | Assigned only |
| View operational lists | Yes | Assigned only | Assigned only |
| View historical analytics | Yes | Assigned only | No revenue/report analytics |
| View audit trail | Yes | Assigned only | No |
| Export reports | Yes | Assigned only | No |

Authorization is applied in views, service functions, API querysets, selectors, and exports. UI visibility is not treated as a security boundary.

## Tariff model

A stay stores the tariff version that was valid at entry. A new tariff closes the previous version and creates a new immutable version.

For an elapsed duration `D`:

- If `D <= grace`, charge is `0.00`.
- Once the grace threshold is exceeded, the **entire elapsed time** is chargeable.
- Each started billing interval rounds upward.
- Elapsed time is split into successive 24-hour windows.
- Each full or partial 24-hour window is capped independently by the tariff's daily cap.
- Money uses `Decimal`, never binary floating-point arithmetic.
- Elapsed duration is measured from UTC instants; display is converted to the parking lot's IANA time zone.

The browser first receives a quote. At confirmation, the server recalculates it. If the amount has changed, checkout is rejected and the user must explicitly accept the new amount.

See `docs/pricing.md` for worked examples.

## API

Interactive documentation is available at `/api/docs/`; the OpenAPI schema is served at `/api/schema/`.

Main endpoints:

```text
GET  /api/v1/parking-lots/
GET  /api/v1/spots/
GET  /api/v1/vehicles/
POST /api/v1/vehicles/
GET  /api/v1/stays/
GET  /api/v1/stays/{id}/quote/
POST /api/v1/stays/{id}/checkout/
GET  /api/v1/tariffs/
GET  /api/v1/payments/
POST /api/v1/operations/entry/
GET  /api/v1/reports/summary/
```

Entry and checkout mutation endpoints require an `Idempotency-Key` header. API authentication uses the logged-in Django session and CSRF protection.

See `docs/api.md`.

## Tests

With PostgreSQL running:

```bash
pytest
```

Useful focused runs:

```bash
pytest billing/tests/test_pricing.py
pytest parking/tests/test_operations.py
pytest parking/tests/test_idempotency.py
pytest parking/tests/test_concurrency.py
pytest parking/tests/test_permissions.py
pytest analyticsapp/tests
```

Quality and deployment checks:

```bash
ruff check .
python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py check --deploy --settings=config.settings.production
python manage.py spectacular --file /tmp/openapi.yml --validate
```

Concurrency tests are `TransactionTestCase` tests intended for real PostgreSQL. The project does not provide a SQLite fallback.

## Production configuration

Production settings require explicit values for:

- `SECRET_KEY`
- `DATABASE_URL`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`

Secure cookies, HTTPS redirect, HSTS, proxy SSL headers, and `DEBUG=False` are enabled by the production profile. If TLS terminates at a reverse proxy, forward `X-Forwarded-Proto: https` only from a trusted proxy.

`/health/` executes a minimal database check and returns only `ok` or `unavailable`; it does not disclose configuration or exception details.

Login throttling/lockout is provided by django-axes. Do not disable it in production.

## PostgreSQL backup and restore

Examples are included in `scripts/backup_postgres.sh` and `scripts/restore_postgres.sh`.

Basic pattern:

```bash
pg_dump --format=custom --no-owner --file=parkmetric.dump "$DATABASE_URL"
pg_restore --clean --if-exists --no-owner --dbname="$RESTORE_DATABASE_URL" parkmetric.dump
```

Always restore into a separate verification database first and run application checks before treating a backup as usable.

## Documentation

- `docs/architecture.md` — modules, data model, states, transactions, and boundaries.
- `docs/permissions.md` — role matrix and authorization strategy.
- `docs/pricing.md` — billing policy and examples.
- `docs/analytics.md` — indicator definitions and date semantics.
- `docs/api.md` — API behaviour and idempotency.
- `docs/security-and-operations.md` — deployment, logs, health, backup/restore.
- `docs/decisions.md` — concise architecture decision record.
- `docs/acceptance-matrix.md` — requirement-to-implementation/test mapping.
- `docs/validation-report.md` — commands actually executed and current verification limits.
- `docs/demo-script.md` — approximately three-minute demonstration script.
- `docs/interview-guide-pt.md` — Portuguese study/interview guide.

## Known boundaries

This repository is intended to be installable and demonstrable within its documented scope. It does **not** claim unattended commercial production readiness for arbitrary infrastructure. Real payment processing, physical gates, plate recognition, external integrations, fiscal documents, penetration testing, production observability/SLOs, disaster-recovery exercises, and infrastructure-specific load testing are outside the implemented scope.

No public license is included. Choose a license deliberately before public distribution.
