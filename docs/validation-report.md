# Validation report

Generated on 2026-10-07.

This report intentionally separates **executed evidence** from checks that are only implemented/configured. No result below is marked as passed unless the command actually ran in the generation environment.

## Environment inspection

Observed:

```text
Python 3.13.5
git version 2.47.3
docker: NOT AVAILABLE
psql: NOT AVAILABLE
postgres: NOT AVAILABLE
django: NOT INSTALLED (ModuleNotFoundError)
drf: NOT INSTALLED (ModuleNotFoundError)
```

A dependency installation attempt with `pip install -r requirements-dev.txt` was also made, but the runtime could not reach the Python package index because of DNS/network resolution failure. Therefore a Django runtime was not created here.

## Executed: Python syntax compilation

Command:

```bash
python3 -m compileall -q .
```

Result:

```text
PASS
```

This validates Python parsing/bytecode compilation only. It does not validate Django model loading or migrations.

## Executed: dependency-free pricing verification

Command:

```bash
python3 scripts/verify_pricing_core.py
```

Result:

```text
pricing-core: PASS (grace, rounding, cap, multi-window, DST, negative duration)
```

Verified cases include:

- exact grace boundary;
- first charge immediately after grace;
- upward interval rounding;
- daily cap;
- a 25-hour stay split across two elapsed 24-hour windows;
- Europe/Berlin spring DST transition using real elapsed UTC time;
- Europe/Berlin autumn DST transition using real elapsed UTC time;
- negative duration rejection.

## Static source checks performed during construction

- Python sources repeatedly recompiled after changes.
- A simple AST import-use check was used to remove detected unused imports before packaging.
- Source review confirmed no SQLite fallback in settings/tests.
- Source review confirmed no public license file.
- Source review confirmed synthetic-only demo naming/data.
- Source review confirmed application pages rather than Django Admin as the primary workflows.

These are source-level checks, not runtime substitutes.


## Executed: Railway packaging checks

After the Railway deployment adaptation, the following source/package checks were executed:

```text
PASS: shell syntax for scripts/start_railway.sh
PASS: Python AST parsing for project source files
PASS: dependency-free pricing verification
PASS: package scan found no .env, local database, .pyc or secret-bearing runtime files
```

The Railway startup path now waits for PostgreSQL, runs migrations, optionally seeds demo data idempotently, and starts Gunicorn on the platform-provided `PORT`. These are source-level checks because Docker and a live Railway runtime are not available in this generation environment.

## Implemented but NOT executed here

The repository contains 53 Django test functions covering pricing, tariff versioning, operations, PostgreSQL concurrency, idempotency, permissions, API, metrics, periods, CSV export, demo loading, and user administration.

The following commands could not be truthfully executed in this runtime because Django/DRF/psycopg were unavailable and no PostgreSQL/Docker executable was exposed:

```bash
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py check
python manage.py check --deploy --settings=config.settings.production
python manage.py spectacular --file /tmp/openapi.yml --validate
ruff check .
pytest
docker compose build
docker compose up
```

Consequently, the following acceptance evidence remains pending:

1. Django model/migration graph validation.
2. Real PostgreSQL concurrency execution.
3. All Django/DRF integration tests.
4. Runtime OpenAPI schema generation/validation.
5. Docker image build/start.
6. Browser verification on desktop and narrow/mobile viewport.
7. Real application screenshots.
8. Clean installation in a separate directory.
9. PostgreSQL backup + restore drill to a separate test database.
10. GitHub Actions result after publication (publication was explicitly not performed).

## Required next verification on a PostgreSQL-capable machine

Run, in order:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
# configure PostgreSQL + .env
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py check
ruff check .
python manage.py spectacular --file /tmp/openapi.yml --validate
pytest
python manage.py seed_demo --small --reference-date 2026-10-07
python manage.py runserver
```

Then execute the browser walkthrough in `docs/demo-script.md`, check responsive behaviour, capture real screenshots, and perform a backup/restore drill with the scripts in `scripts/`.

## Readiness statement

The package contains the requested implementation and verification assets, but because the mandatory PostgreSQL/Django runtime checks could not be executed in this environment, this report does **not** label the build “fully verified” or “commercial-production ready.” It is a substantial implementation package awaiting the explicitly listed runtime validation steps.
