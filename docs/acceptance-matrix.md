# Acceptance matrix

Status meanings:

- **Implemented**: code/documentation exists in this package.
- **Executed**: validation was actually run in the generation environment.
- **CI pending**: test/check is implemented but requires the PostgreSQL/dependency-capable environment described in `docs/validation-report.md`.

| Requirement | Implementation | Validation evidence | Status |
|---|---|---|---|
| Multi-site parking model | `ParkingLot`, `ParkingAccess`, site-scoped views/API | permission tests | Implemented; CI pending |
| Authentication/logout/password change | Django auth views/templates | Django integration suite | Implemented; CI pending |
| User administration | `accounts` pages/forms | `accounts/tests.py` | Implemented; CI pending |
| Admin/manager/operator matrix | `User.Role`, decorators, access helpers | `test_permissions.py`, `accounts/tests.py` | Implemented; CI pending |
| Server-side site permissions | scoped querysets, services, API, exports | direct URL/API/export tests | Implemented; CI pending |
| Disabled accounts stop operating | inactive-user middleware + helpers | disabled-session test | Implemented; CI pending |
| Parking lot CRUD | product pages/forms, not only admin | integration paths | Implemented; CI pending |
| Spot CRUD/block/deactivate | product pages/forms/model validation | operations tests | Implemented; CI pending |
| Occupied spot cannot be blocked/deactivated | model validation | `test_occupied_spot...` | Implemented; CI pending |
| Occupied state not manually forged | model validation | integrity test | Implemented; CI pending |
| Vehicle registry/history | product pages + scoped API | API/permission tests | Implemented; CI pending |
| Manual/automatic entry | `enter_vehicle()` + UI/API | operations/API tests | Implemented; CI pending |
| Max one active stay per spot | PostgreSQL partial unique constraint | concurrency test | Implemented; CI pending |
| Max one active vehicle stay/site | PostgreSQL partial unique constraint | operations + concurrency test | Implemented; CI pending |
| Last-space race protection | `SELECT FOR UPDATE SKIP LOCKED` | real PostgreSQL thread test | Implemented; CI pending |
| Valid operational spot/tariff required | entry service checks | operations tests | Implemented; CI pending |
| Exit before entry rejected | pricing + DB check constraint | pricing/model tests | Implemented; core executed |
| Versioned tariffs | `TariffVersion`, atomic version service | tariff tests | Implemented; CI pending |
| One active tariff/site | PostgreSQL partial unique constraint | migration/model checks | Implemented; CI pending |
| Stay preserves tariff version | FK selected at entry | operations + tariff tests | Implemented; CI pending |
| Grace boundary | pricing engine | pricing test + standalone verifier | Implemented; Executed |
| Full-time charging after grace | pricing engine | pricing test + standalone verifier | Implemented; Executed |
| Interval rounding upward | pricing engine | pricing test + standalone verifier | Implemented; Executed |
| 24-hour window cap | pricing engine | pricing test + standalone verifier | Implemented; Executed |
| Final incomplete window cap | pricing engine | pricing test | Implemented; CI pending |
| Decimal money | `Decimal` throughout pricing/models | pricing assertions | Implemented; Executed |
| UTC elapsed time/DST | UTC normalization + ZoneInfo display/reporting | spring/fall verifier + tests | Implemented; Executed |
| Quote revalidation | checkout recalculation/409 conflict | operations/API tests | Implemented; CI pending |
| Simulated payment success | `Payment.SUCCEEDED` flow | operations/API tests | Implemented; CI pending |
| Simulated payment failure keeps stay open | `Payment.FAILED` branch | operations/idempotency tests | Implemented; CI pending |
| Zero-charge waiver | `Payment.WAIVED` branch | operation test | Implemented; CI pending |
| Atomic success close/payment/release | transaction + row locks | operations/concurrency tests | Implemented; CI pending |
| Completed stay immutability | model protection + read-only admin | immutable-history test | Implemented; CI pending |
| Historical identifiers preserved | stay snapshots | operations/export code/tests | Implemented; CI pending |
| Idempotent equivalent retry | `IdempotencyRecord` + response persistence | sequential/concurrent tests | Implemented; CI pending |
| Idempotency content mismatch rejected | canonical payload hash | idempotency test | Implemented; CI pending |
| Concurrent same-key handling | DB uniqueness + row lock | PostgreSQL thread test | Implemented; CI pending |
| Audit within operations | `AuditEvent` in service transactions | operation checks | Implemented; CI pending |
| Audit read-only for normal profiles | manager/admin read page; no mutation route | permission tests | Implemented; CI pending |
| Current occupancy | persisted spot states | metrics tests | Implemented; CI pending |
| Entry/exit period metrics | timestamp-specific queries | metrics tests | Implemented; CI pending |
| Simulated revenue | succeeded-payment timestamp | metrics tests | Implemented; CI pending |
| Average ticket + denominator | eligible succeeded >0 payments | metrics tests | Implemented; CI pending |
| Average stay + denominator | closed stays by exit period | metrics tests | Implemented; CI pending |
| Daily/monthly/annual trends | Django DB aggregations | metrics + template coverage | Implemented; CI pending |
| Hourly demand/peak | site-local hour aggregation | metrics tests | Implemented; CI pending |
| Site comparison/currency isolation | per-site rows, no cross-currency sum | metrics code/tests | Implemented; CI pending |
| Unified period filters | shared `parse_period` + site local bounds | period/API/export tests | Implemented; CI pending |
| Pagination/search | product list views | page integration suite | Implemented; CI pending |
| Filtered full-result CSV | streaming queryset beyond page | export tests | Implemented; CI pending |
| CSV formula injection protection | leading formula characters escaped | export unit test | Implemented; CI pending |
| Deterministic 90-day demo | `seed_demo` command | demo tests | Implemented; CI pending |
| >=3 sites/varied demand/tariffs | demo generator | demo assertions | Implemented; CI pending |
| Demo failed/waived/open cases | demo generator | demo assertions | Implemented; CI pending |
| Explicit demo/reset guards | settings + command guards | demo tests | Implemented; CI pending |
| Responsive product UI | Django templates/CSS/JS | source inspection; browser blocked | Implemented; browser validation pending |
| Keyboard focus/labels/feedback | CSS focus, semantic forms/messages | source inspection; browser blocked | Implemented; browser validation pending |
| Repeated-click UI protection | submit disabling JS + server idempotency | source + idempotency tests | Implemented; server CI pending |
| DRF API | viewsets + operational endpoints | API tests | Implemented; CI pending |
| OpenAPI | drf-spectacular schema/docs | CI `spectacular --validate` | Implemented; CI pending |
| CSRF and session API auth | Django/DRF settings | Django deployment/integration checks | Implemented; CI pending |
| Excessive login attempts | django-axes backend/middleware | configuration + integration environment | Implemented; CI pending |
| Required production variables | production settings fail explicitly | `check --deploy` in CI | Implemented; CI pending |
| Secure production cookies/HTTPS/HSTS | production settings | `check --deploy` in CI | Implemented; CI pending |
| Health check without detail leakage | DB `SELECT 1`, plain responses | integration environment | Implemented; CI pending |
| Logs without secrets/body logging | console logging config | configuration review | Implemented |
| PostgreSQL backup/restore guidance | docs + scripts | executable tools unavailable here | Implemented; restore drill pending |
| Docker/Gunicorn | Dockerfile/Compose | Docker unavailable here | Implemented; build pending |
| macOS/PyCharm path | README | documentation review | Implemented |
| CI with PostgreSQL | GitHub Actions workflow | not published/run by request | Implemented; GitHub run pending |
| Migration drift check | CI `makemigrations --check` | Django unavailable here | Implemented; CI pending |
| Clean install verification | documented command path | blocked by dependency/DB environment | Pending execution |
| Browser desktop/mobile verification | responsive implementation exists | runtime/browser unavailable | Pending execution |
| Real screenshots | placeholder explains why none fabricated | runtime unavailable | Pending execution |
| 3-minute demo script | `docs/demo-script.md` | documentation review | Implemented |
| Portuguese interview guide | `docs/interview-guide-pt.md` | documentation review | Implemented |
