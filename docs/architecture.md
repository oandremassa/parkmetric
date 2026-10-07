# Architecture

## Shape

ParkMetric is a modular Django monolith. This keeps business transactions inside a single PostgreSQL boundary and avoids unnecessary distributed-system complexity.

```text
Browser / REST client
        |
 Django views + DRF
        |
 service layer
        |
 domain models + constraints
        |
    PostgreSQL
```

The HTML interface and REST API call the same operational services for entry, checkout, tariff selection, pricing, idempotency, and audit events. Pricing logic is not duplicated.

## Modules

- `accounts`: custom user roles, parking-lot access grants, user administration, inactive-session enforcement.
- `parking`: parking lots, spots, vehicles, stays, operational services, pages, API.
- `billing`: tariff versions, pricing engine, simulated payments.
- `auditlog`: append-only application audit events and idempotency records.
- `analyticsapp`: report period parsing, metrics, aggregation, and safe CSV streaming.
- `config`: environment-specific Django settings, URL routing, WSGI/ASGI.

## Core data model

```text
User 1---* ParkingAccess *---1 ParkingLot
ParkingLot 1---* ParkingSpot
ParkingLot 1---* TariffVersion
Vehicle 1---* Stay *---1 ParkingLot
ParkingSpot 1---* Stay
TariffVersion 1---* Stay
Stay 1---* Payment
Stay/Payment/Tariff/... ---* AuditEvent
User + ParkingLot + Scope + Key --- IdempotencyRecord
```

### Historical snapshots

A stay stores:

- `vehicle_plate_snapshot`
- `spot_code_snapshot`
- `parking_lot_code_snapshot`
- `currency`
- exact `tariff` version

Completed stays cannot be edited through the model to rewrite their operational/financial values. Payments and tariffs are read-only in the application admin. Site time zone and currency cannot change after operational history exists because they affect historical interpretation.

## State machines

### Parking spot

```text
FREE --entry--> OCCUPIED --successful/waived checkout--> FREE
FREE <------manager------> BLOCKED
FREE/BLOCKED --administrative--> inactive
```

`OCCUPIED` is controlled by stay operations and cannot be set manually. An occupied spot cannot be blocked, deactivated, renamed, or moved to another site.

### Stay

```text
ACTIVE --failed simulated payment--> ACTIVE
ACTIVE --successful payment-------> CLOSED
ACTIVE --zero-charge waiver-------> CLOSED
```

A closed stay cannot return to active and cannot be financially rewritten.

### Tariff

A site has at most one `is_active=True` tariff version. Creating a version atomically closes the prior active version and opens the next version. Stays keep the tariff foreign key chosen at entry.

## Database invariants

PostgreSQL constraints enforce, among other rules:

- one active stay per parking spot;
- one active stay per vehicle per parking lot;
- exit cannot precede entry;
- active/closed state must match exit timestamp presence;
- one successful or waived payment per stay;
- non-negative payment and tariff monetary values;
- positive billing interval;
- valid tariff effective ranges;
- unique tariff version per parking lot;
- at most one active tariff per parking lot;
- unique idempotency key within scope + actor + parking lot.

## Transaction strategy

Entry and checkout run inside `transaction.atomic()`.

Entry locks the relevant vehicle and spot rows. Automatic assignment uses `SELECT ... FOR UPDATE SKIP LOCKED` so simultaneous entries cannot claim the same available spot. PostgreSQL partial unique constraints provide a second integrity boundary.

Checkout locks the stay and spot, recalculates the final amount, records payment/waiver, updates the stay, frees the spot, and creates the audit event inside one transaction. A controlled failed payment records a failure but deliberately leaves the stay active and the spot occupied.

## Idempotency

Mutation requests can bind an idempotency key to:

- operation scope;
- authenticated actor;
- parking lot;
- canonical hash of semantic request content.

Equivalent retry -> original response.

Same key + different content -> conflict.

Concurrent same-key requests serialize through the database uniqueness constraint and row lock. A request does not create a second operation.

## Time and money

Django stores aware instants in UTC. Billing duration compares UTC instants, which reflects real elapsed time through DST transitions. Calendar report filters are interpreted in each parking lot's local IANA time zone and converted to half-open UTC ranges.

Monetary arithmetic uses `Decimal`. Cross-site comparison keeps each site's currency attached and never produces an invalid aggregate across currencies.
