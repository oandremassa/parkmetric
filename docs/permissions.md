# Permissions

## Matrix

| Action | Administrator | Manager | Operator |
|---|---:|---:|---:|
| Manage users/roles/access | All | No | No |
| Create/edit parking lots | All | No | No |
| View assigned parking lots | All | Yes | Yes |
| Create/edit/block spots | All | Assigned | No |
| Create tariff versions | All | Assigned | No |
| Register vehicle entries | All | Assigned | Assigned |
| Confirm checkout / simulated payment | All | Assigned | Assigned |
| View operational stays/payments | All | Assigned | Assigned |
| Historical analytics | All | Assigned | No |
| Audit trail | All | Assigned | No |
| CSV exports | All | Assigned | No |

Only administrators can grant/revoke site access or change roles.

## Enforcement points

Authorization is intentionally repeated at trust boundaries, not merely represented in navigation:

1. Page decorators reject role-inappropriate URLs.
2. Site-specific object retrieval is restricted to accessible site IDs.
3. Forms scope parking-lot/spot/vehicle selectors.
4. Service functions verify site-operation permission even when invoked outside a view.
5. DRF querysets are scoped before object lookup, returning 404 for cross-site identifiers.
6. Report and CSV endpoints enforce manager/admin role plus site access.
7. Inactive accounts are logged out by middleware; permission helpers also reject them.

A parking lot may be operationally inactive while its historical data remains visible to authorized users. Operational inactivity is not used to erase authorization history.

## Data leakage controls

Cross-site objects are filtered before searches, selectors, details, APIs, and exports. A user cannot broaden access by editing URL IDs or query parameters. Tests cover direct URLs and API object IDs from another site.
