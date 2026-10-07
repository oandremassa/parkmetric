# API

The REST API is rooted at `/api/v1/`. OpenAPI is served at `/api/schema/` and Swagger UI at `/api/docs/`.

## Authentication

The API uses Django session authentication and therefore CSRF protection for unsafe methods. Object querysets are scoped to the authenticated user's parking-lot permissions before lookup.

## Resources

- `GET /api/v1/parking-lots/`
- `GET /api/v1/spots/?parking_lot=<id>&status=<status>`
- `GET /api/v1/vehicles/?q=<plate>`
- `POST /api/v1/vehicles/`
- `GET /api/v1/stays/?parking_lot=<id>&status=<status>`
- `GET /api/v1/stays/{id}/quote/`
- `POST /api/v1/stays/{id}/checkout/`
- `GET /api/v1/tariffs/`
- `GET /api/v1/payments/`
- `POST /api/v1/operations/entry/`
- `GET /api/v1/reports/summary/?parking_lot=<id>&start=YYYY-MM-DD&end=YYYY-MM-DD`

## Entry

`POST /api/v1/operations/entry/`

Header:

```text
Idempotency-Key: <caller-generated-key>
```

Body:

```json
{
  "parking_lot": 1,
  "vehicle": 12,
  "spot": null
}
```

`spot=null` requests automatic allocation. A specific spot must belong to the selected accessible parking lot and be operational.

## Quote and checkout

Read the current estimate:

```text
GET /api/v1/stays/42/quote/
```

Then confirm using a new idempotency key:

```json
{
  "accepted_amount": "8.40",
  "simulator_outcome": "success"
}
```

`simulator_outcome` may be `success` or `failure`. A controlled failure records a failed simulated payment and returns HTTP 402 while keeping the stay open.

If the amount has changed since the quote, checkout returns HTTP 409. The client must request a fresh quote and explicitly accept the new value.

## Idempotency semantics

The key is bound to operation scope, authenticated actor, parking lot, and canonical request content. Equivalent retries receive the previously persisted response. Reusing a key with different content returns HTTP 409. Concurrent same-key requests are serialized by PostgreSQL constraints/locking.

## Reports

The summary endpoint requires administrator or manager access. `start`/`end` use the same validation and local-calendar interpretation as the HTML reports and CSV exports.
