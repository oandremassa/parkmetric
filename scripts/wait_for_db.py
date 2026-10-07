"""Wait for PostgreSQL before deployment startup without leaking credentials."""

import os
import sys
import time

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

import django  # noqa: E402
from django.db import connection  # noqa: E402


def main() -> int:
    django.setup()
    timeout = int(os.getenv("DATABASE_WAIT_TIMEOUT", "60"))
    deadline = time.monotonic() + timeout
    last_error = None

    while time.monotonic() < deadline:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            print("PostgreSQL is available.")
            return 0
        except Exception as exc:  # pragma: no cover - deployment helper
            last_error = exc.__class__.__name__
            connection.close()
            time.sleep(2)

    print(f"PostgreSQL was not available within {timeout}s ({last_error or 'unknown error'}).", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
