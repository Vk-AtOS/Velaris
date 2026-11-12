"""
Dated registry of GST figures for an IT services company (outward supply of services).

Same rules as PAYROLL_ENGINE/statutory.py: verified=True only for what was read in the
primary text on `fetched_on` (note says where); unverified entries are never used by the
engine (strict mode) and make the result needs_review.

Primary texts read on FETCHED:
  SRC_RATE_CT   CGST rate notification 11/2017-CT(Rate), GST Council consolidated copy "as
                amended upto 1st April 2019" (serial 21, heading 9983, and serial 22, 9984).
  SRC_RATE_IT   IGST rate notification 8/2017-IT(Rate), consolidated to 1 April 2019 (same).
  SRC_GAZ_15    Gazette G.S.R. 663(E), notification 15/2025-CT(Rate) of 17 Sep 2025, in force
                22 Sep 2025: the latest amendment of 11/2017 that touches serial 21; it only
                re-words item (ii) and removes item (ia), the 9% column is not changed.
                Amendments of 11/2017 between 2019 and 2025 other than 15/2025 were NOT read.
  SRC_IGST_ACT  Integrated GST Act, 2017 (Gazette copy on cbic-gst.gov.in): s.2(6), s.12, s.13, s.16.
  SRC_CIRC_242  CBIC Circular 242/36/2024-GST, 31 Dec 2024.
  SRC_RULE46    CGST Rules, 2017, rule 46 (CBIC tax information portal, current text).
  SRC_EINV      Notification 10/2023-CT, 10 May 2023 (GST Council copy).
  SRC_SOC       Scheme of Classification of Services (GST Council copy).
"""
from datetime import date
from typing import Dict, List

from velaris.agents.PAYROLL_ENGINE.registry import Entry

FETCHED = date(2026, 11, 12)
GST_START = date(2017, 7, 1)

SRC_RATE_CT = "https://www.gstcouncil.gov.in/sites/default/files/2024-02/11-rate_notification-cgst-01.04.2019.pdf"
SRC_RATE_IT = "https://www.gstcouncil.gov.in/sites/default/files/2024-02/8-rate_notification-igst-01.04.2019.pdf"
SRC_GAZ_15 = "https://egazette.gov.in/WriteReadData/2025/266220.pdf"
SRC_IGST_ACT = "https://cbic-gst.gov.in/aces/Documents/IGST-bill.pdf"
SRC_CIRC_242 = "https://gstcouncil.gov.in/sites/default/files/2025-01/circular-no-242-2024.pdf"
SRC_RULE46 = "https://taxinformation.cbic.gov.in/content/html/tax_repository/gst/rules/cgst_rules/active/chapter6/rule46_v1.00.html"
SRC_EINV = "https://www.gstcouncil.gov.in/sites/default/files/2024-05/10ct_eng.pdf"
SRC_SOC = "https://www.gstcouncil.gov.in/sites/default/files/2024-02/scheme_of_classification_of_services_amended.pdf"
SRC_RCM_CT = "https://www.gstcouncil.gov.in/sites/default/files/2024-02/13-reverse_charge-cgst-01.04.2019-revised.pdf"

NOT_READ_RATE = ("Rate read in the 2019 consolidated notification and the 17 Sep 2025 amendment "
                 "(15/2025-CT(Rate), serial 21) that leaves it unchanged; other amendments 2019-2025 not read.")

PARAMS: Dict[str, List[Entry]] = {
    # SAC 9983 (998311-998319 are information technology services): serial 21(ii) "other professional,
    # technical and business services". SAC 9984 online information services: serial 22(ii).
    "cgst_rate:9983": [Entry(9, GST_START, SRC_RATE_CT, FETCHED, True, "11/2017-CT(R) serial 21(ii): 9. " + NOT_READ_RATE)],
    "igst_rate:9983": [Entry(18, GST_START, SRC_RATE_IT, FETCHED, True, "8/2017-IT(R) serial 21(ii): 18. " + NOT_READ_RATE)],
    "cgst_rate:9984": [Entry(9, GST_START, SRC_RATE_CT, FETCHED, True,
                             "11/2017-CT(R) serial 22(ii): 9 (e-book supplies at 2.5 are a separate item). " + NOT_READ_RATE)],
    "igst_rate:9984": [Entry(18, GST_START, SRC_RATE_IT, FETCHED, True, "8/2017-IT(R) serial 22(ii): 18. " + NOT_READ_RATE)],
    "sgst_rate:TAMIL_NADU": [Entry(9, GST_START, None, None, False,
                                   "Tamil Nadu's own State tax rate notification was not found/read (ctd.tn.gov.in "
                                   "search returned no 2025 text). The Central rate is 9; the State rate is NOT assumed equal.")],
    "export_of_services": [Entry(
        ("supplier located in India", "recipient located outside India", "place of supply outside India",
         "payment received in convertible foreign exchange", "supplier and recipient not merely establishments of a "
         "distinct person"), GST_START, SRC_IGST_ACT, FETCHED, True,
        "IGST Act s.2(6) (all five conditions) and s.16(1)(a): export of services is a zero rated supply; s.16(3): "
        "either supply under bond/Letter of Undertaking without paying IGST, or pay IGST and claim refund. "
        "Place of supply for a recipient outside India: s.13(2), location of the recipient.")],
    "pos_rule_registered": [Entry("location of the registered recipient", GST_START, SRC_IGST_ACT, FETCHED, True,
                                  "IGST Act s.12(2)(a). Special services in s.12(3)-(14) (immovable property, events, "
                                  "passenger transport, telecom, ...) are NOT handled.")],
    "pos_rule_unregistered": [Entry("recipient's location where address on record exists, else supplier's location",
                                    GST_START, SRC_IGST_ACT, FETCHED, True,
                                    "IGST Act s.12(2)(b). Circular 242/36/2024-GST (31 Dec 2024): the State of the "
                                    "recipient recorded on the tax invoice is treated as the address on record.")],
    "einvoice_aggregate_turnover_threshold": [
        Entry(50000000, date(2023, 8, 1), SRC_EINV, FETCHED, True,
              "Notification 10/2023-CT: 'ten crore' replaced by 'five crore rupees' in 13/2020-CT w.e.f. 1 Aug 2023 "
              "(aggregate turnover in any preceding financial year from 2017-18 onwards, rule 46(s)). The e-invoice "
              "portal's notification list shows no later change to the threshold; exemptions (SEZ units, insurers, "
              "etc.) and the 30-day reporting limit were not read at a notification and are not applied.")],
    "invoice_serial_max_chars": [Entry(16, GST_START, SRC_RULE46, FETCHED, True,
                                       "Rule 46(b): consecutive serial number not exceeding sixteen characters, "
                                       "letters, digits, '-' and '/', unique for a financial year.")],
    "unregistered_recipient_details_value": [Entry(50000, GST_START, SRC_RULE46, FETCHED, True,
                                                   "Rule 46(e): name, address, delivery address and State and its code "
                                                   "of an unregistered recipient where taxable value is Rs 50,000 or more.")],
    "tax_invoice_particulars": [Entry((
        "supplier_name", "supplier_address", "supplier_gstin", "invoice_number", "invoice_date", "description",
        "sac", "total_value", "taxable_value", "tax_rate", "tax_amount", "reverse_charge_flag"),
        GST_START, SRC_RULE46, FETCHED, True,
        "Rule 46 (a),(b),(c),(g),(h),(j),(k),(l),(m),(p) always; (d) recipient name/address/GSTIN if registered; "
        "(e) as above; (n) place of supply with State name for inter-State supply; export endorsement and country "
        "of destination for exports; (q) signature or digital signature (not required for an electronic invoice); "
        "(r) QR code with IRN where an e-invoice is required.")],
    # RCM: read only in the 2019 consolidated 13/2017-CT(R) and 10/2017-IT(R); later amendments not read.
    "rcm_services_candidates": [Entry({
        "import_of_service": "IGST 10/2017 serial 1: any service supplied by a person located in a non-taxable territory to a person in the taxable territory other than a non-taxable online recipient",
        "director_services": "13/2017-CT(R) serial 6: services by a director of a company or body corporate to that company",
        "legal_services": "13/2017-CT(R) serial 2: services by an individual advocate or firm of advocates to a business entity",
        "sponsorship": "13/2017-CT(R) serial 4: sponsorship services to a body corporate or partnership firm",
        "security_services": "13/2017-CT(R) serial 14: security services (supply of personnel) to a registered person, other than a body corporate",
        "arbitral_tribunal": "13/2017-CT(R) serial 3"},
        GST_START, SRC_RCM_CT, FETCHED, False,
        "Categories read in the consolidated notifications 'amended upto 1st April 2019'. Amendments since were not "
        "read (e.g. 07/2025-CT(Rate)), so the list is not confirmed current: needs_review.")],
}

SAC_RATE_KEY = {"9983": "9983", "9984": "9984"}


def sac_group(sac: str) -> str:
    """The 4-digit heading of a SAC, or '' if it is not 4-8 digits."""
    s = str(sac).strip()
    return s[:4] if s.isdigit() and 4 <= len(s) <= 8 else ""
