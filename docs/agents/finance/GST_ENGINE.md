# GST_ENGINE

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/GST_ENGINE/main.py` (266 lines)

## Purpose

GST_ENGINE: GST on outward supplies of services by an IT services company registered in Tamil Nadu.

  validate_gstin(g)             structure and check character
  price_outward_supply(...)     tax on one supply: CGST+SGST (intra-State) or IGST (inter-State) by the
                                place-of-supply rules for services, or zero rated export of services
  validate_invoice(invoice)     rule 46 particulars, GSTIN checks, e-invoice applicability
  monthly_summary(...)          data in the shape of GSTR-1 and GSTR-3B tables (not a filing)
  rcm_check(kind)               candidate reverse-charge categories for a purchase (needs_review)

Every rate and threshold is in statutory.py with its source; unverified ones are not used and the
result is needs_review with no tax amount. Not handled: SEZ supplies, services whose place of
supply falls under s.12(3)-(14), composition/exempt supplies, credit notes, amendments, input tax
credit. These figures need an accountant's check before use.

## Class `GstEngine`

- `health_check()`
- `validate_gstin(gstin)`
- `price_outward_supply(supplier_gstin, sac, taxable_value, invoice_date, recipient_gstin, recipient_state_code, recipient_outside_india, payment_in_convertible_forex, distinct_person, lut, sez)`
- `validate_invoice(invoice, aggregate_turnover)` — Rule 46 particulars, GSTINs, and whether an e-invoice (IRN, QR code) is required.
- `rcm_check(kind, on)` — Is `kind` (a key of rcm_services_candidates) a reverse-charge candidate? Always needs_review: not confirmed current.
- `monthly_summary(supplies, period, purchases)` — supplies: kwargs of price_outward_supply plus invoice_number. period 'YYYY-MM'.

## Depends on

- `velaris.agents.GST_ENGINE`
- `velaris.agents.GST_ENGINE.gstin`
- `velaris.agents.PAYROLL_ENGINE.registry`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** `departments/hr/PAYROLL_ENGINE/registry.py`
- **tests:** `velaris/tests/test_alias_layers.py`, `velaris/tests/test_gst_engine.py`
