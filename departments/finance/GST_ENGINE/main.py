"""
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
"""
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from velaris.agents.GST_ENGINE import statutory
from velaris.agents.GST_ENGINE.gstin import validate_gstin as _validate_gstin
from velaris.agents.PAYROLL_ENGINE.registry import Run, inr, money, paise

STATE_KEY = {"33": "TAMIL_NADU"}      # only the State this registry holds a State rate for
HUNDRED = Decimal(100)


def _as_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


class GstEngine:
    def health_check(self) -> Dict[str, Any]:
        return {"agent": "GST_ENGINE", "status": "ok"}

    def validate_gstin(self, gstin: Any) -> Dict[str, Any]:
        return _validate_gstin(gstin)

    # ── tax on one supply ────────────────────────────────────────────────
    def price_outward_supply(self, *, supplier_gstin: str, sac: str, taxable_value: Any, invoice_date: Any,
                             recipient_gstin: Optional[str] = None, recipient_state_code: Optional[str] = None,
                             recipient_outside_india: bool = False, payment_in_convertible_forex: Optional[bool] = None,
                             distinct_person: bool = False, lut: bool = False, sez: bool = False) -> Dict[str, Any]:
        on = _as_date(invoice_date)
        value = money(taxable_value)
        run = Run(statutory.PARAMS, on)
        out: Dict[str, Any] = {"sac": sac, "taxable_value": inr(value), "lines": []}
        sup = _validate_gstin(supplier_gstin)
        if not sup["valid"]:
            return self._done(run, out, status="invalid", reasons=[f"supplier GSTIN: {sup['reason']}"])
        group = statutory.sac_group(sac)
        if group not in statutory.SAC_RATE_KEY:
            run.review(f"SAC {sac!r}: no verified rate in the registry (only headings 9983 and 9984)")
        elif str(sac).strip() == "998431":
            run.review("SAC 998431 (online text information) may be an e-book supply at 2.5%: classify before pricing")
        if sez:
            run.review("supply to an SEZ developer/unit is zero rated (s.16(1)(b)) with its own conditions: not handled")
        if run.reasons:
            return self._done(run, out)

        if recipient_outside_india:
            return self._export(run, out, value, payment_in_convertible_forex, distinct_person, lut, group)

        # Place of supply within India (IGST Act s.12(2)).
        rec = _validate_gstin(recipient_gstin) if recipient_gstin else None
        if rec is not None and not rec["valid"]:
            return self._done(run, out, status="invalid", reasons=[f"recipient GSTIN: {rec['reason']}"])
        if rec:
            run.param("pos_rule_registered")
            pos, basis = rec["state_code"], "registered recipient: its location, State code from its GSTIN (s.12(2)(a))"
        elif recipient_state_code:
            run.param("pos_rule_unregistered")
            pos, basis = str(recipient_state_code), "unregistered recipient: State on the invoice = address on record (s.12(2)(b), Circular 242/36/2024)"
        else:
            run.param("pos_rule_unregistered")
            pos, basis = sup["state_code"], "unregistered recipient, no address on record: supplier's location (s.12(2)(b))"
        intra = pos == sup["state_code"]
        out.update(place_of_supply_state_code=pos, supply_type="intra-State" if intra else "inter-State",
                   place_of_supply_basis=basis)
        if intra:
            key = STATE_KEY.get(sup["state_code"])
            cgst = run.param(f"cgst_rate:{statutory.SAC_RATE_KEY.get(group, '')}")
            sgst = run.param(f"sgst_rate:{key}") if key else None
            if key is None:
                run.review(f"no State tax rate in the registry for State code {sup['state_code']}")
            if run.reasons:
                return self._done(run, out)
            c, s = paise(value * Decimal(cgst) / HUNDRED), paise(value * Decimal(sgst) / HUNDRED)
            out["tax"] = {"cgst": inr(c), "sgst": inr(s), "igst": "0.00"}
            out["lines"] += [f"CGST {cgst}% of {inr(value)} = {inr(c)}", f"SGST {sgst}% of {inr(value)} = {inr(s)}"]
            total = c + s
        else:
            igst = run.param(f"igst_rate:{statutory.SAC_RATE_KEY[group]}")
            if igst is None:
                return self._done(run, out)
            i = paise(value * Decimal(igst) / HUNDRED)
            out["tax"] = {"cgst": "0.00", "sgst": "0.00", "igst": inr(i)}
            out["lines"].append(f"IGST {igst}% of {inr(value)} = {inr(i)}")
            total = i
        out["invoice_total"] = inr(value + total)
        return self._done(run, out)

    def _export(self, run: Run, out: Dict[str, Any], value: Decimal, forex: Optional[bool], distinct: bool,
                lut: bool, group: str) -> Dict[str, Any]:
        conditions = run.param("export_of_services")
        out.update(supply_type="export of services", conditions_s2_6=list(conditions or ()))
        if forex is None:
            run.review("export of services needs payment in convertible foreign exchange (s.2(6)(iv)): "
                       "payment_in_convertible_forex was not given")
        elif not forex:
            run.review("payment not received in convertible foreign exchange: not an export of services under "
                       "s.2(6); the tax treatment (and the RBI-permitted exceptions) needs review")
        if distinct:
            run.review("supplier and recipient are establishments of a distinct person: not an export (s.2(6)(v))")
        if run.reasons:
            return self._done(run, out)
        out["zero_rated"] = True
        if lut:
            out["tax"] = {"cgst": "0.00", "sgst": "0.00", "igst": "0.00"}
            out["lines"].append("zero rated, supplied under Letter of Undertaking without payment of IGST (s.16(3)(a)); "
                                "invoice carries the LUT export endorsement and the country of destination (rule 46)")
        else:
            igst = run.param(f"igst_rate:{statutory.SAC_RATE_KEY[group]}")
            if igst is None:
                return self._done(run, out)
            i = paise(value * Decimal(igst) / HUNDRED)
            out["tax"] = {"cgst": "0.00", "sgst": "0.00", "igst": inr(i)}
            out["lines"].append(f"zero rated, no LUT: IGST {igst}% = {inr(i)} paid, refund claimed under s.16(3)(b)")
        if not run.reasons:
            out["invoice_total"] = inr(value + Decimal(out["tax"]["igst"]))
        return self._done(run, out)

    @staticmethod
    def _done(run: Run, out: Dict[str, Any], *, status: Optional[str] = None, reasons: Optional[List[str]] = None) -> Dict[str, Any]:
        reasons = (reasons or []) + run.reasons
        st = status or ("needs_review" if reasons else "ok")
        if st != "ok":
            out.pop("invoice_total", None)
            out["tax"] = None
        return {**out, "status": st, "review_reasons": reasons, "parameters_used": run.parameters(),
                "disclaimer": "Computed from the registry; needs an accountant's check before use."}

    # ── invoice validation ───────────────────────────────────────────────
    def validate_invoice(self, invoice: Dict[str, Any], *, aggregate_turnover: Any = None) -> Dict[str, Any]:
        """Rule 46 particulars, GSTINs, and whether an e-invoice (IRN, QR code) is required.

        aggregate_turnover: the largest aggregate turnover in any preceding financial year from 2017-18.
        """
        on = _as_date(invoice.get("invoice_date", date.today()))
        run = Run(statutory.PARAMS, on)
        particulars = run.param("tax_invoice_particulars") or ()
        max_len = run.param("invoice_serial_max_chars")
        errors: List[str] = []
        for f in particulars:
            if invoice.get(f) in (None, ""):
                errors.append(f"missing {f}")
        sup = _validate_gstin(invoice.get("supplier_gstin"))
        if not sup["valid"]:
            errors.append(f"supplier GSTIN: {sup['reason']}")
        number = str(invoice.get("invoice_number", ""))
        if max_len and (len(number) > max_len or not all(c.isalnum() or c in "-/" for c in number)):
            errors.append(f"invoice_number must be at most {max_len} characters of letters, digits, '-' and '/'")
        rec_gstin = invoice.get("recipient_gstin")
        if rec_gstin:
            rec = _validate_gstin(rec_gstin)
            if not rec["valid"]:
                errors.append(f"recipient GSTIN: {rec['reason']}")
            elif not invoice.get("recipient_name") or not invoice.get("recipient_address"):
                errors.append("registered recipient: name and address required (rule 46(d))")
        elif invoice.get("export"):
            for f in ("recipient_name", "recipient_address", "country_of_destination", "export_endorsement"):
                if not invoice.get(f):
                    errors.append(f"export invoice: missing {f}")
        else:
            limit = run.param("unregistered_recipient_details_value")
            if limit is not None and money(invoice.get("taxable_value", 0)) >= limit:
                for f in ("recipient_name", "recipient_address", "recipient_state_code"):
                    if not invoice.get(f):
                        errors.append(f"unregistered recipient, value {limit} or more: missing {f}")
        inter = bool(rec_gstin and _validate_gstin(rec_gstin)["valid"] and sup["valid"]
                     and _validate_gstin(rec_gstin)["state_code"] != sup["state_code"])
        if (inter or invoice.get("inter_state")) and not invoice.get("place_of_supply"):
            errors.append("inter-State supply: place of supply with the name of the State is required (rule 46(n))")
        threshold = run.param("einvoice_aggregate_turnover_threshold")
        einv: Dict[str, Any] = {"threshold": threshold}
        if aggregate_turnover is None:
            run.review("aggregate_turnover not given: e-invoice applicability cannot be decided")
            einv["required"] = None
        else:
            einv["required"] = money(aggregate_turnover) > threshold if threshold else None
            if einv["required"] and not (invoice.get("irn") and invoice.get("qr_code")):
                errors.append("e-invoice required: IRN and QR code missing (rule 46(r))")
            einv["note"] = ("exemptions (e.g. SEZ units, insurers) and the 30-day reporting limit were not read at "
                            "a notification and are not applied")
        status = "needs_review" if run.reasons else ("invalid" if errors else "ok")
        return {"status": status, "errors": errors, "review_reasons": run.reasons, "e_invoice": einv,
                "parameters_used": run.parameters()}

    def rcm_check(self, kind: str, on: Any = None) -> Dict[str, Any]:
        """Is `kind` (a key of rcm_services_candidates) a reverse-charge candidate? Always needs_review: not confirmed current."""
        when = _as_date(on or date.today())
        run = Run(statutory.PARAMS, when)
        cands = run.param("rcm_services_candidates")
        hit = statutory.PARAMS["rcm_services_candidates"][0].value.get(kind)
        return {"status": "needs_review", "kind": kind, "candidate": hit, "review_reasons": run.reasons,
                "parameters_used": run.parameters(), "confirmed": cands is not None}

    # ── monthly summary ──────────────────────────────────────────────────
    def monthly_summary(self, supplies: List[Dict[str, Any]], period: str,
                        purchases: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """supplies: kwargs of price_outward_supply plus invoice_number. period 'YYYY-MM'.

        Returns GSTR-1 and GSTR-3B style tables as data. A supply that needs review is listed under
        'needs_review' and left out of the totals, and the summary is then needs_review too.
        purchases: [{"kind": key of rcm_services_candidates, "taxable_value"}] - listed, never totalled.
        """
        y, m = (int(p) for p in period.split("-"))
        zero = Decimal(0)
        t = {"b2b_4A": [], "exports_6A": [], "b2c_inter_state": [], "b2c_intra_state": []}
        three_b = {"3.1(a)_taxable_value": zero, "3.1(b)_zero_rated_value": zero, "cgst": zero, "sgst": zero, "igst": zero}
        review, bad, pos_wise = [], [], {}
        for s in supplies:
            r = self.price_outward_supply(**{k: v for k, v in s.items() if k != "invoice_number"})
            ref = s.get("invoice_number")
            d = _as_date(s["invoice_date"])
            if (d.year, d.month) != (y, m):
                bad.append({"invoice": ref, "reason": f"invoice date {d} is outside {period}"})
                continue
            if r["status"] != "ok":
                (review if r["status"] == "needs_review" else bad).append({"invoice": ref, "reasons": r["review_reasons"]})
                continue
            row = {"invoice": ref, "taxable_value": r["taxable_value"], **r["tax"],
                   "place_of_supply": r.get("place_of_supply_state_code")}
            v = money(r["taxable_value"])
            if r.get("zero_rated"):
                t["exports_6A"].append({**row, "with_payment_of_igst": r["tax"]["igst"] != "0.00"})
                three_b["3.1(b)_zero_rated_value"] += v
            else:
                three_b["3.1(a)_taxable_value"] += v
                key = "b2b_4A" if s.get("recipient_gstin") else ("b2c_intra_state" if r["supply_type"] == "intra-State" else "b2c_inter_state")
                t[key].append(row)
                if key == "b2c_inter_state":
                    pos_wise[row["place_of_supply"]] = pos_wise.get(row["place_of_supply"], zero) + v
            for head in ("cgst", "sgst", "igst"):
                three_b[head] += money(r["tax"][head])
        rcm = [{"kind": p["kind"], "taxable_value": inr(money(p["taxable_value"])), **self.rcm_check(p["kind"], date(y, m, 1))}
               for p in (purchases or [])]
        status = "needs_review" if (review or bad or rcm) else "ok"
        return {
            "period": period, "status": status, "needs_review": review, "invalid": bad,
            "gstr1": {**t, "note": "B2C inter-State rows are not split into Table 5 and Table 7: the large-invoice "
                      "threshold was not read at a primary source. Table layout follows the return's named tables, "
                      "not checked against the GST portal's JSON schema. Not a filing."},
            "gstr3b": {"3.1(a)_outward_taxable_supplies": {"taxable_value": inr(three_b["3.1(a)_taxable_value"]),
                                                           "cgst": inr(three_b["cgst"]), "sgst": inr(three_b["sgst"]),
                                                           "igst": inr(three_b["igst"])},
                       "3.1(b)_zero_rated": {"taxable_value": inr(three_b["3.1(b)_zero_rated_value"])},
                       "3.1(d)_inward_reverse_charge": {"candidates": rcm, "totals": None,
                                                         "note": "reverse-charge list not confirmed current: no amounts"},
                       "3.2_inter_state_to_unregistered_by_place_of_supply": {k: inr(v) for k, v in pos_wise.items()}},
            "note": "igst in 3.1(a) includes IGST paid on exports without LUT; check against 3.1(b). "
                    "Needs an accountant's check before use.",
        }
