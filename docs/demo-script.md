# Three-minute demo script

**0:00–0:25 — Context**  
Open the overview. Explain that ParkMetric manages several parking sites and separates live occupancy from historical analytics. Change the selected site and point out site currency/time zone context.

**0:25–0:55 — Entry**  
Open **Register entry**. Select a vehicle, leave the spot blank, and submit. Show the success message and the automatically assigned spot in **Active stays**. Mention that allocation is protected with PostgreSQL row locking and active-stay constraints.

**0:55–1:35 — Checkout and pricing**  
Open the active stay. Show the pricing breakdown: elapsed time, interval rounding, 24-hour cap, and tariff version. Run a controlled failed payment first and show that the stay/spot remain active. Retry with a new idempotency key via the form and simulate success. Open the completed record and simulated receipt.

**1:35–2:05 — Tariff history**  
As manager/admin, open **Tariffs**. Point out old/new versions. Explain that a stay keeps the version from entry, so later tariff changes do not rewrite history.

**2:05–2:35 — Analytics and export**  
Return to **Overview**. Change the date range. Show entries, exits, simulated revenue, average ticket denominator, average stay, hourly peak, daily/monthly/annual tables, and site comparison. Explain that currencies are not incorrectly summed. Open history/payments and export a filtered CSV.

**2:35–3:00 — Security/API/audit**  
Open **Audit trail** and one user access screen. Mention three roles and server-side site restrictions. Finish at `/api/docs/`, explaining that the HTML product and API share the same business services and idempotency rules.
