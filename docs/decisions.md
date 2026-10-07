# Technical decisions

## 1. Modular monolith rather than microservices

The core workflows require strong transactions across stays, spots, payments, idempotency, and audit. A Django monolith with PostgreSQL provides a clearer and safer boundary for this product size than introducing services/queues.

## 2. PostgreSQL from development onward

Capacity allocation and idempotency rely on row locks, partial unique constraints, and real transaction semantics. SQLite is intentionally unsupported instead of providing misleading concurrency tests.

## 3. Shared service layer for HTML and API

Entry/checkout/tariff rules live in service functions. This avoids separate business logic for templates and DRF.

## 4. Immutable history via version/snapshot strategy

Tariff versions are never retroactively edited into stays. Stays preserve codes/plate/currency values needed to explain a historical transaction. Completed stays reject financial/operational edits.

## 5. Quote revalidation rather than silent price drift

Time can cross a billing boundary between preview and confirmation. The server recalculates; a changed amount requires explicit acceptance rather than silently charging a different value.

## 6. Simulated payments isolated from pricing

The simulator controls only the payment outcome. Pricing remains deterministic and testable independently. Every receipt/reference is clearly marked `SIM-`.

## 7. Site-local calendar reporting, UTC duration

UTC is correct for elapsed time. Site-local dates are correct for operational reporting. ParkMetric intentionally uses both for their respective purposes.

## 8. Server-side permissions first

Navigation hiding improves usability but is not authorization. Querysets, object retrieval, services, API, and exports all enforce access.
