"""Offer letter content: the default template, the placeholder whitelist, and rendering to text, HTML and PDF lines.

A template is plain text in paragraphs separated by a blank line. A paragraph that is exactly `{compensation_table}`
becomes the compensation table (with its arithmetic); every other paragraph is substituted by the safe engine
(velaris.agentkit.onboarding_template): only the names in ALLOWED, no code, no attribute access.

The default wording is a starting point for a lawyer to replace, not legal advice: notice period, probation,
termination, confidentiality, non-compete and stamp duty clauses are deliberately absent because they are
the company's and its lawyer's to write.
"""
from __future__ import annotations

import html
from typing import Any, Dict, List, Tuple

from velaris.agentkit import onboarding_template as tpl
from velaris.agentkit.onboarding_pdf import Line

ALLOWED = ("candidate_name", "role_title", "department", "location", "join_date", "manager_name", "company_name",
           "annual_ctc", "monthly_ctc", "offer_expiry", "probation_months", "compensation_table")

DEFAULT_TEMPLATE = """Offer of employment

Dear {candidate_name},

{company_name} is pleased to offer you the position of {role_title} in the {department} team, based at {location}. Your proposed date of joining is {join_date} and you will report to {manager_name}.

Your compensation is set out below. The annual cost to company is Rs. {annual_ctc}.

{compensation_table}

Your probation period is {probation_months} months.

This offer is valid until {offer_expiry}. To accept, follow the instructions that came with this letter. The terms of employment are in the appointment letter and the company policies, which you will receive before you join.

Yours sincerely,
{company_name}"""

Block = Tuple[str, Any]


def blocks(template: str, values: Dict[str, Any], comp: Dict[str, Any]) -> List[Block]:
    """[("p", text) | ("table", comp)] with every other placeholder substituted (raises tpl.TemplateError)."""
    out: List[Block] = []
    for para in template.strip().split("\n\n"):
        if para.strip() == "{compensation_table}":
            out.append(("table", comp))
        else:
            out.append(("p", tpl.render(para, values, ALLOWED)))
    return out


def _table_rows(comp: Dict[str, Any]) -> List[List[str]]:
    c, e = comp["components"], comp["employer_contributions"]
    rows = [["Component", "Per month (Rs.)", "Per year (Rs.)"]]

    def add(label: str, monthly: Any) -> None:
        yearly = None if monthly is None else f"{float(monthly) * 12:,.2f}"
        rows.append([label, "to be confirmed" if monthly is None else f"{float(monthly):,.2f}",
                     "to be confirmed" if yearly is None else yearly])

    add("Basic", c["basic"])
    add("House rent allowance", c["hra"])
    add("Special allowance", c["special_allowance"])
    add("Gross salary", c["gross"])
    if comp["structure"]["ctc_includes_employer_contributions"]:
        add("Employer provident fund", e["epf"])
        add("Employer ESI", e["esi"])
    rows.append(["Cost to company", f"{float(comp['monthly_ctc']):,.2f}", f"{float(comp['annual_ctc']):,.2f}"])
    return rows


def to_text(bl: List[Block], review_note: str = "") -> str:
    parts = []
    for kind, content in bl:
        if kind == "p":
            parts.append(content)
        else:
            parts.append("\n".join("  ".join(r) for r in _table_rows(content)) +
                         "\nArithmetic: " + "; ".join(f"{l['item']} = {l['formula']} = {l['amount']}"
                                                       for l in content["lines"] if l["formula"]))
    return "\n\n".join(parts) + (f"\n\n{review_note}" if review_note else "")


def to_html(bl: List[Block], title: str) -> str:
    out = [f"<!doctype html><html><head><meta charset=\"utf-8\"><title>{html.escape(title)}</title></head><body>"]
    for kind, content in bl:
        if kind == "p":
            out.append("<p>" + html.escape(content).replace("\n", "<br>") + "</p>")
        else:
            rows = _table_rows(content)
            out.append("<table border=\"1\" cellpadding=\"4\"><tr>" + "".join(f"<th>{html.escape(h)}</th>" for h in rows[0]) + "</tr>")
            out += ["<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in r) + "</tr>" for r in rows[1:]]
            out.append("</table><p><small>Arithmetic: " + html.escape("; ".join(
                f"{l['item']}: {l['formula']} = {l['amount']}" for l in content["lines"] if l["formula"])) + "</small></p>")
    out.append("</body></html>")
    return "\n".join(out)


def to_pdf_lines(bl: List[Block]) -> List[Line]:
    lines: List[Line] = []
    for n, (kind, content) in enumerate(bl):
        if kind == "p":
            if n == 0:
                lines.append(("h1", content))
            else:
                lines += [("p", content), ("gap", "")]
        else:
            rows = _table_rows(content)
            lines.append(("rowb", rows[0]))
            lines += [("rowb" if r[0] in ("Gross salary", "Cost to company") else "row", r) for r in rows[1:]]
            lines.append(("gap", ""))
            lines += [("p", f"{l['item']}: {l['formula']} = {l['amount']}") for l in content["lines"] if l["formula"]]
            lines.append(("gap", ""))
    return lines
