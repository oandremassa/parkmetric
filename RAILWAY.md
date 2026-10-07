# Railway deployment

ParkMetric is prepared for a **single Railway web service + Railway PostgreSQL** deployment.
The repository root contains a `Dockerfile`, so Railway can build it directly.

## What is already handled by the repository

- PostgreSQL-only configuration through `DATABASE_URL`.
- Railway's injected `PORT` is used by Gunicorn.
- Railway's `RAILWAY_PUBLIC_DOMAIN` is automatically accepted by Django and CSRF.
- WhiteNoise serves versioned static files collected during the Docker build.
- `/health/` checks database availability without exposing internals.
- Startup waits for PostgreSQL and applies Django migrations.
- Optional deterministic demo seeding is idempotent at startup.
- HTTPS redirect, secure cookies, HSTS, proxy SSL handling, login throttling and `DEBUG=False` are active in production.

## Deploy from GitHub

1. Push this repository to GitHub.
2. In Railway, create a new project and add a **PostgreSQL** database service.
3. Add a service from the GitHub repository. Railway detects the root `Dockerfile` automatically.
4. In the web service **Variables** tab, paste the values from `.env.railway.example`.
5. Ensure the database reference uses the actual service name, normally:

   `DATABASE_URL=${{Postgres.DATABASE_URL}}`

6. Replace `SECRET_KEY` and `DEMO_PASSWORD` with strong unique values.
7. Deploy the staged changes.
8. In the web service, open **Settings -> Networking -> Public Networking -> Generate Domain**.
9. In **Settings -> Deploy -> Healthcheck**, set the path to `/health/` if Railway has not detected it automatically.

No manual `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` or `PORT` value is needed for the generated Railway domain.

## First login for the portfolio demo

When all of these are set:

- `DEMO_MODE=true`
- `AUTO_SEED_DEMO=true`
- `DEMO_PASSWORD=<your password>`

startup creates the compact deterministic demo only when it does not already exist.
Use one of these usernames with the `DEMO_PASSWORD` value:

- `demo_admin`
- `demo_manager`
- `demo_operator`

The startup path never resets existing demo data. `ALLOW_DEMO_RESET=false` should remain false on Railway.

## Custom domain

If you add a custom domain, set:

`APP_PUBLIC_URL=https://your-domain.example`

The Railway-provided domain remains supported as well.

## Scaling note

The included startup script runs `migrate` before Gunicorn. This is appropriate for this portfolio deployment and one web replica. Before scaling to multiple replicas, move `python manage.py migrate --noinput` to Railway's **Pre-deploy Command** and remove it from `scripts/start_railway.sh` to make schema rollout a single deployment step.

## Useful verification after deployment

Open:

- `/health/` — should return `ok`.
- `/login/` — sign in with a demo account.
- `/api/docs/` — OpenAPI/Swagger documentation.

Then verify dashboard, entry, checkout/payment simulation, reports and CSV exports.
