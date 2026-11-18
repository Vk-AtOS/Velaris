# HR core research: system of record, India payroll rules, applicant tracking, resume parsing and matching, skills vocabularies

Snapshot date 2026-11-11. Repo metadata (licence, last push, stars, archived) fetched with `gh api repos/OWNER/REPO` on that date.
Conventions: **[read]** = source or official docs read in this session; **[docs]** = README / official docs only (copyleft, source not opened); **[meta]** = metadata only, nothing else opened; **[unverified]** = stated from secondary sources or prior knowledge, not confirmed against a primary source in this session.
Licence rule followed: for GPL / AGPL / LGPL / MPL / custom-licence projects, only README and official documentation were read. No code from any project is reproduced here.

---

## 1. Verification table

### 1.1 The named candidates

| Path as given | Exists? | Licence as fetched | Last push | Stars | Archived | Status in 2026 | Verdict |
|---|---|---|---|---|---|---|---|
| frappe/hrms | yes | GPL-3.0 | 2026-11-11 | 9,044 | no | Very active (commit on default branch the same day) | **Study, docs only.** Best reference for payroll document chain. |
| horilla-opensource/horilla | **moved**: API resolves to `horilla/horilla-hr` | LGPL-2.1 | 2026-11-11 | 1,508 | no | Active; default branch is `2.0` | Skip for payroll (no India statutory layer seen in metadata). Docs only if studied. [meta] |
| orangehrm/orangehrm | yes | GPL-3.0 | 2026-06-28 | 1,161 | no | Slow: last push and latest release (v5.9) both 2026-06-28 | Skip. PHP, no India statutory payroll in the open edition [unverified]. [meta] |
| opencats/OpenCATS | yes | GitHub reports NOASSERTION. `LICENSE.md` says dual: new code MPL-2.0, original 2007 code under "CATS Public License 1.1a" (a modified MPL) | 2026-11-11 | 781 | no | Active again; release v0.12.0 on 2026-10-22 | **Avoid reading source** (custom legacy licence). Concept-level reference only. |
| srbhr/Resume-Matcher | yes | Apache-2.0 | 2026-11-11 | 29,244 | no | Very active | **Study** [read]. Note it is a job-seeker tailoring tool, not a recruiter-side ranker. |
| AnasAito/SkillNER | yes | MIT | 2024-01-28 (last default-branch commit 2023-08-22) | 216 | no | **Stale** | Skip as a dependency; mechanism noted [read]. Its skill database is derived from the EMSI/Lightcast list, whose data terms are not an open licence [unverified]. |
| ESCO skills data | yes (esco.ec.europa.eu) | Free download; reuse governed by the Commission reuse policy (Decision 2011/833/EU cited on ESCO documents). Exact attribution wording not fetched | Current version v1.2.1, last update 2025-12-10 | n/a | n/a | Maintained; delta files published per version | **Use as the primary vocabulary.** |
| O*NET skills data | yes (onetcenter.org) | CC BY 4.0 (stated on the database page) | Current release 31.0; site updated 2026-10-06 | n/a | n/a | Maintained | **Use as secondary** (occupation-to-skill/technology links). US-centric. |

### 1.2 Additional projects checked

| Repo | Licence as fetched | Last push | Stars | Archived | Verdict |
|---|---|---|---|---|---|
| frappe/india-payroll | GPL-3.0 | 2026-11-07 | 28 | no | **Study, README only [docs].** The only maintained open project found that covers EPF/EPS/EDLI split, ESI, state professional tax, LWF, both tax regimes, 24Q and Form 16. New and small. |
| frappe/india_payroll (underscore) | "other" | 2023-05-04 | 3 | **yes** | Skip (archived predecessor). |
| euron-sde-team/euron-open-hrms | MIT | 2026-10-23 | 15 | no | **Study [read].** Small, but a clean permissive example of rules-as-data payroll (TypeScript). India pack is already out of date (see 2.2). |
| openfisca/openfisca-core | AGPL-3.0 | 2026-11-01 | 252 | no | **Study, docs only [docs].** Best model for effective-dated statutory parameters. |
| PolicyEngine/policyengine-core | AGPL-3.0 | 2026-11-11 | 22 | no | Skip (fork lineage of the same idea). [meta] |
| OCA/payroll | AGPL-3.0 | 2026-11-11 | 125 | no | Skip. [meta] |
| odoo/odoo | NOASSERTION (LGPL per upstream, not confirmed here) | 2026-11-11 | 55,714 | no | Skip. India payroll localisation is not in the community tree [unverified]. [meta] |
| ever-co/ever-gauzy | AGPL-3.0 | 2026-11-11 | 8,775 | no | Skip. [meta] |
| gamonoid/icehrm | NOASSERTION | 2026-11-10 | 739 | no | Skip. [meta] |
| hcengineering/platform | EPL-2.0 | 2026-11-09 | 28,092 | no | Skip (weak copyleft; general workspace platform with a recruiting module). [meta] |
| interviewstreet/hiring-agent | MIT | 2026-10-30 | 7,346 | no | **Study [read].** Best worked example of LLM rubric scoring with code-enforced constraints, and of its failure modes. Depends on PyMuPDF (AGPL). |
| docling-project/docling | MIT | 2026-11-11 | 70,445 | no | Candidate for layout-aware document conversion. [meta] |
| microsoft/markitdown | MIT | 2026-11-07 | 194,923 | no | Simple document-to-markdown; used by Resume-Matcher. [meta] |
| jsvine/pdfplumber | MIT | 2026-10-15 | 10,895 | no | Permissive PDF text + layout. [meta] |
| py-pdf/pypdf | NOASSERTION (BSD-style per upstream, not confirmed) | 2026-11-10 | 10,298 | no | Check licence file before use. [meta] |
| pymupdf/PyMuPDF | **AGPL-3.0** | 2026-11-11 | 11,112 | no | **Avoid** as a dependency. |
| Unstructured-IO/unstructured | Apache-2.0 | 2026-11-06 | 15,717 | no | Heavier alternative. [meta] |
| google/langextract | Apache-2.0 | 2026-11-10 | 39,304 | no | LLM extraction with source grounding (each value tied to a source span). Idea worth taking. [meta + description] |
| 567-labs/instructor | MIT | 2026-11-10 | 14,106 | no | Schema-validated LLM output with retry. [meta] |
| dottxt-ai/outlines | Apache-2.0 | 2026-09-21 | 16,007 | no | Constrained decoding for local models. [meta] |
| urchade/GLiNER | Apache-2.0 | 2026-11-11 | 4,251 | no | Small zero-shot NER model, runs locally. Candidate for span proposal without an LLM. [meta] |
| OmkarPathak/pyresparser | GPL-3.0 | 2023-09-13 | 959 | no | Skip (copyleft and stale). |
| OmkarPathak/ResumeParser | MIT | 2026-02-04 | 343 | no | Skip (older rule/NER approach). [meta] |
| xitanggg/open-resume | AGPL-3.0 | 2024-10-29 | 8,975 | no | Skip (copyleft, stale). |
| jsonresume/resume-schema | MIT | 2026-06-12 | 2,387 | **yes** | Schema repo is archived; `jsonresume/jsonresume.org` (MIT, pushed 2026-11-07) is the live home. Use the schema shape as a public reference, not as a dependency. |
| nestauk/ojd_daps_skills | MIT | 2025-06-09 | 162 | no | **Study [read].** Extract-then-map design with a threshold ladder over the taxonomy hierarchy. Not updated for 17 months. |
| KonstantinosPetrakis/esco-skill-extractor | MIT | 2025-06-12 | 32 | no | **Study [read].** The 250-line minimum of embedding-based ESCO linking. |
| tabiya-tech/tabiya-livelihoods-classifier | MIT | 2026-11-05 | 7 | no | Note: entity extraction + vector search onto ESCO, five entity types. README only read. |
| tabiya-tech/taxonomy-model-application | MIT | 2026-11-11 | 20 | no | Platform for localising an ESCO-derived taxonomy. Relevant idea: a local, versioned overlay on ESCO. [meta + description] |
| techwolf-ai/workrb | Apache-2.0 | 2026-11-10 | 45 | no | Benchmark toolkit for job-skill matching, normalisation, extraction. Use for evaluation, not runtime. README only read. |
| kris927b/SkillSpan | MIT | 2025-02-13 | 69 | no | Annotated skill-span dataset. [meta] |
| moj-analytical-services/splink | MIT | 2026-11-11 | 2,573 | no | **Study.** Docs site confirms Splink 5 is released and the model is Fellegi-Sunter; theory page fetched (navigation and headings only), source not read. |
| dedupeio/dedupe | MIT | 2025-07-29 | 4,529 | no | Active-learning dedupe; slower cadence. [meta] |
| J535D165/recordlinkage | BSD-3-Clause | 2024-02-21 | 1,067 | no | Stale. [meta] |
| zinggAI/zingg | AGPL-3.0 | 2026-11-03 | 1,272 | no | Avoid (copyleft, Spark). |
| rapidfuzz/RapidFuzz | MIT | 2026-11-09 | 4,198 | no | String similarity if stdlib `difflib` is not enough. [meta] |
| daviddrysdale/python-phonenumbers | Apache-2.0 | 2026-11-06 | 3,779 | no | Phone normalisation to E.164. [meta] |
| fairlearn/fairlearn | MIT | 2026-11-07 | 2,306 | no | **Reference** for group metrics (selection rate, ratios). Source not read. |
| dssg/aequitas | MIT | 2026-05-12 | 777 | no | Reference for audit report layout. [meta] |
| Trusted-AI/AIF360 | Apache-2.0 | 2026-06-15 | 2,882 | no | Heavy; skip. [meta] |
| fidelity/jurity | Apache-2.0 | 2024-10-11 | 59 | no | Stale. [meta] |
| fair-search/fairsearch-fair-python | NOASSERTION | 2020-05-13 | 16 | no | Avoid (no clear licence, stale). The FA*IR paper is the usable source. |
| KCachel/fairranktune | BSD-3-Clause | 2024-05-03 | 6 | no | Skip. [meta] |
| plutomi/plutomi | Apache-2.0 | 2025-04-10 | 72 | no | Skip (self-described work in progress). |
| cross-solution/YAWIK | MIT | 2023-08-30 | 132 | no | Skip (stale PHP). |
| Assystant/SpotAxis | MIT | 2025-10-06 | 34 | no | Skip. [meta] |
| microsoft/SkillLens | MIT | 2026-10-29 | 184 | no | **Not relevant**: it is about agent "skills", not labour-market skills. |

Not found: `frappe/india-compliance` returned 404 at that path.

Search note: no permissive, maintained, recruiter-side ATS of meaningful size was found. The ATS space on GitHub in 2026 is dominated by job-seeker tools. No maintained permissive India income-tax engine was found either; every hit was a single-author calculator with no licence or no activity.

---

## 2. Sub-areas

### 2.1 HR system of record

**What we already have.** Eight agents, each with its own storage: `EMPLOYEE_ONBOARDING` keeps an `employees` table (name, email, department, role) in its own SQLite file; `LEAVE_MANAGEMENT`, `PERFORMANCE_REVIEW_ENGINE`, `ATTENDANCE_MONITOR`, `EMPLOYEE_METRICS_ENGINE` and `PAYROLL_ENGINE` refer to employees by a free-form `employee_id` string. There is no single employee master, no employment history, and no shared ledger. That is the gap in this sub-area; leave, onboarding checklists, OKRs and attendance flags already exist and are not re-recommended here.

**How the reference projects work.**
- Frappe HR [docs]: everything hangs off one Employee document. Pay is not a field on the employee; it is a separate, dated link (Salary Structure Assignment with a base amount and a From Date). Changing pay means adding a new assignment, not editing the old one. Payroll then reads "the assignment in force on the slip date".
- euron-open-hrms [read, architecture doc and type definitions]: per-employee statutory settings are a separate record from the salary (PF applicable or not, restrict-to-ceiling flag, hand-entered override, PT exemption flag). Engagement type carries a `gratuityEligible` flag so interns, vendors and freelancers never accrue gratuity.

**What makes them good.** Dated assignments instead of mutable fields; statutory eligibility stored as explicit per-employee facts rather than inferred each month; one identity that every module joins to.

**What they get wrong.** Frappe lets a submitted document be amended or cancelled, with the history held in ordinary rows rather than a tamper-evident log [unverified: framework behaviour from prior knowledge, not fetched]. Neither project separates "person" from "employment" (a rehire is awkward), and neither records who approved a pay change in a way that cannot be rewritten.

**Minimum original design (about 300 lines + migration).**
- `person` (stable identity: legal name, date of birth, contact, government ids stored encrypted and never sent to a model).
- `employment` (one row per stint: person, legal entity, work location with its **local body code** for professional tax, engagement type, start, end, exit reason).
- `employment_fact` (append-only, effective-dated key/value: designation, department, manager, PF applicable, ESI covered, tax regime chosen, UAN/ESIC numbers). Reads are always "as of date D".
- `compensation_assignment` (append-only: structure id, annual CTC in paise, effective from, approved by).
- Every write goes through one function that appends to the hash-linked ledger and requires a named approver for compensation, exit and regime changes.
- Existing agents keep working: they are given a lookup from their current `employee_id` string to `employment.id`; no agent is rewritten in the first step.

**Beyond them.** "As of" reads make any past payslip reproducible from the ledger alone. A pay change proposed by a model is only a draft row until a person approves it; the approval is itself a ledger entry that the payroll run cites.

---

### 2.2 India statutory payroll rules

**What we already have, and what is wrong with it.** `PAYROLL_ENGINE/main.py` computes EPF as 12 percent of full basic with **no wage ceiling**, ESI as a monthly test on gross against 21,000, and professional tax from a three-row **monthly** table labelled "Karnataka/TN typical". TDS is passed in by the caller. Rates are module constants with no effective date, and amounts are floats. For a Tamil Nadu employer this is wrong in at least three ways: PT in Tamil Nadu is half-yearly and set by the local body; the EPF ceiling exists and changed in September 2026; ESI coverage is decided per contribution period, not per month.

#### The statutory facts, with their authority

| Rule | Value found | Authority and how far it was verified |
|---|---|---|
| EPF wage ceiling | Rs 15,000 per month until 16 Sep 2026; **Rs 25,000 from 17 Sep 2026** | PMO release dated 16 Sep 2026 (Cabinet approval) fetched from pmindia.gov.in. The notification date of 17 Sep 2026 comes from two professional-firm alerts (KPMG, EY). The gazette text itself was not read. A secondary source records the 15,000 ceiling being re-notified on 29 May 2026 (S.O. 2702(E)) before the increase [unverified]. |
| EPF rates and employer split | Employee 12 percent; employer 12 percent split between EPS and EPF, plus EDLI and administrative charges | The existence of the EPF / EPS / EDLI / admin split is confirmed by the frappe/india-payroll README. The exact percentages (8.33 / 3.67 / 0.5 / 0.5) are **[unverified]** here: the EPFO contribution page returned 404. Take them from the EPFO site or the Scheme text before coding. |
| ESI | Employee 0.75 percent, employer 3.25 percent; coverage ceiling Rs 21,000 per month (Rs 25,000 for persons with disability); two contribution periods a year | Secondary sources agree; esic.gov.in/wages returned no content. **[unverified against ESIC]**. The frappe/india-payroll README confirms one behaviour: coverage is decided on full monthly gross so a loss-of-pay month does not wrongly pull a high earner in. |
| Tamil Nadu professional tax | **Half-yearly**, on half-yearly gross income. Greater Chennai Corporation schedule with effect from the second half of 2024-25: 21,001-30,000 Rs 180; 30,001-45,000 Rs 425; 45,001-60,000 Rs 930; 60,001-75,000 Rs 1,025; above 75,000 Rs 1,250. Employers deduct from August salary and remit by 30 September for the first half | Fetched from chennaicorporation.gov.in (revenue department page and 2026 press release). The nil band up to 21,000 was not in the extract [unverified]. **Other Tamil Nadu corporations, municipalities and panchayats set their own amounts**; only Chennai was fetched. |
| Professional tax annual limit | Rs 2,500 per person per year (Article 276) | From comments in the MIT repo; not checked against the Constitution text [unverified]. |
| Income tax, new regime, FY 2025-26 (AY 2026-27) | Nil to 4 lakh; 5 percent to 8 lakh; 10 percent to 12 lakh; 15 percent to 16 lakh; 20 percent to 20 lakh; 25 percent to 24 lakh; 30 percent above | Fetched from the income-tax e-filing portal page for salaried individuals, AY 2026-27. |
| Income tax, tax year 2026-27 | Same slab structure; rebate up to Rs 60,000 for taxable income up to 12 lakh; standard deduction Rs 75,000 | Secondary source only. The Finance Bill 2026 exists on indiabudget.gov.in but was not read. **[unverified]** |
| Income-tax Act, 2025 | In force from 1 April 2026. Uses "tax year". **Form 16 is replaced by Form No. 130** for tax year 2026-27 onward | The Form 130 FAQ on incometaxindia.gov.in was found and its opening answer fetched. New section and form numbers for the salary TDS return (the old 24Q) were **not** verified. |
| Labour codes | All four codes in force from 21 Nov 2025; final Central Rules notified 8-9 May 2026; state rules arriving through 2026 | PIB release and a Ministry FAQ PDF (16 Mar 2026) were found; dates of the rules are from secondary sources [unverified]. |
| "Wages" under the Code on Wages | Inclusive definition with listed exclusions; where excluded items exceed half of total remuneration, the excess is treated as wages | Secondary sources [unverified against the Code text]. Whether this definition is the EPF contribution base is **unsettled** according to the one source that discussed it. |
| Gratuity | 15 days' wages per completed year (15/26 of monthly wages); five years' service required, except death or disablement; **fixed-term employees eligible after one year** | The fixed-term rule is from the Ministry FAQ (fetched extract). Formula and the Rs 20 lakh ceiling are from MIT-repo comments and secondary sources [unverified]. Tamil Nadu state rules under the codes: not checked. |

Two things in this table matter more than any repository: a statutory ceiling changed **mid-month** (17 September 2026), and the income-tax statute, form numbers and wage definition all changed within one year. Any design that stores a rate as a constant is already wrong.

**How the reference projects work.**
1. **Document chain (Frappe HR)** [docs]. Payroll Period (the tax year) -> Income Tax Slab (rates for that year, with an effective date and an optional condition on employee fields) -> Salary Component (one payslip line, typed Earning or Deduction) -> Salary Structure (which components, and a formula or fixed amount for each) -> Salary Structure Assignment (employee, base amount, from date) -> Payroll Entry (finds employees, creates one Salary Slip each, posts accounting entries).
2. **Components carry a condition and a formula** [docs]. Both are Python-like expressions evaluated per slip. They can reference `base`, other components by abbreviation, employee fields, and the slip start date. The docs show a professional-tax component that returns a different amount in one month of the year, written as a date condition.
3. **Income tax as a special component** [docs]. A deduction flagged "variable based on taxable salary" ignores the formula path: the system projects annual taxable earnings, subtracts declared exemptions, applies the slab for the payroll period, and spreads the remaining liability over the remaining months. A declaration made mid-year takes effect from the next run; unsubmitted proofs are trued up in the last run of the period.
4. **India layer (frappe/india-payroll)** [docs]. Adds EPF with ceiling and the employer split, an ECR export, ESI, a "state-wise slab engine covering monthly and half-yearly states" for professional tax including one-month special charges and exemption thresholds, labour welfare fund at state-specific frequencies, both tax regimes with surcharge and marginal relief, a regime comparison page for employees, 24Q filing and Form 16 generation, and statutory registers.
5. **Rule packs as data (euron-open-hrms)** [read]. A country ruleset is a list of pay components. Each component has a type (earning, deduction, tax, employer contribution), a side (employee or employer), and one of three calculation methods: flat amount, percent of a named base, or progressive slabs over a base. Two separate numeric guards exist and are named differently on purpose: a **cap** limits the base before the percentage is applied (EPF), while a **ceiling/threshold** switches the whole component on or off (ESI). Salary structures are also data: each line is percent of CTC, percent of basic, flat monthly, or "balance" (whatever remains), so the breakup always reconciles to CTC. Professional tax is a per-state table converted into an ordinary slab component, with an explicit list of states that levy none and a reason returned with every zero.
6. **Effective-dated parameters (OpenFisca)** [docs]. Every legal number is a parameter file holding a list of `date: value` pairs, each with a reference to the legal source. A scale is a list of brackets where the threshold and the rate each have their own date history. A value of null from some date ends the parameter. Formulas never contain numbers; they ask for "parameters at this period". Formulas themselves can be dated too, so a rule that was replaced keeps its old logic for old periods. Three scale types are distinguished: marginal rate (income tax), marginal amount, and single amount (a flat amount per band, which is what professional tax is).

**What makes them good.**
- Separation of three things that change at different speeds: the law (parameters), the employer's pay policy (structures), and the employee's facts (assignments).
- OpenFisca's per-value dates and source references make "what was the rule on date D" a lookup rather than an archaeology exercise.
- The cap-versus-ceiling distinction removes a whole class of EPF/ESI bugs.
- The "balance" component guarantees the breakup sums to CTC without rounding drift.
- Returning a reason with every zero amount makes payslips explainable.

**What they get wrong.**
- Frappe's formulas are evaluated strings. That is flexible but makes the rule set unauditable as data, and an expression evaluator is an attack surface. It conflicts with our rule that money is computed by fixed code.
- euron-open-hrms dates a whole country pack with one `effectiveFrom` label rather than each value. Its India pack still caps EPF at 15,000 and its docs say income tax is typed in by HR each run. It labels Tamil Nadu's half-yearly amounts with a warning note but its engine is monthly.
- None of the projects models a mid-month change of a parameter, the contribution-period rule for ESI, or the Code on Wages add-back as first-class logic (as far as README and docs show).
- None of them describes a tamper-evident record of a finalised payslip; corrections are ordinary edits or cancel-and-amend [unverified beyond the docs read].

**Minimum original design (about 1,100 lines in five modules, stdlib + Decimal).**

1. *Parameter store* (about 200 lines). One table: parameter key, jurisdiction (IN, IN-TN, IN-TN-local-body-code), effective-from, effective-to, value (scalar or bracket list), scale type (marginal-rate, single-amount), citation (document title, number, date, URL), SHA-256 of the saved source PDF, approved-by, ledger sequence. Lookup is `param(key, jurisdiction, on_date)` with fallback from local body to state to country. No value is ever edited; a correction is a new row. Adding a row is an approval-gated action.
2. *Component engine* (about 300 lines). Components are typed records, not expressions: method (flat, percent, slab), base (a named sum of earning components), cap parameter key, eligibility parameter key, rounding rule key, side. The engine is a pure function of (employment facts as of the period, attendance and loss-of-pay days, structure, parameter snapshot) and returns lines, each carrying the parameter row ids and input values it used. All amounts are integer paise; rounding is a named per-component rule taken from the statute, not a global default.
3. *Period logic* (about 200 lines), the part no reference project gets fully right:
   - EPF: resolve the ceiling by the date rule the notification prescribes. September 2026 needs an explicit decision (see open questions) and must not be guessed.
   - ESI: coverage decided at the start of each contribution period and held to its end; the engine keeps a per-employee "covered until" fact.
   - Tamil Nadu PT: project half-year gross per employee, look up the single-amount scale for the work location's local body, deduct in the configured month(s), true up at the half-year end.
   - Code-on-Wages base: a deterministic function that sums excluded components, compares with half of total remuneration, and returns the statutory wage. Used for gratuity now; switchable for EPF once the position is settled.
4. *TDS projection* (about 250 lines). Year-to-date actual taxable pay plus projected pay for remaining months, less standard deduction and regime-allowed declarations, through the marginal-rate scale, rebate, surcharge with marginal relief and cess; subtract tax already deducted; spread over remaining months. Regime choice is an employment fact with an effective date. Output includes the full working so the employee can check it.
5. *Run lifecycle* (about 150 lines). Draft run -> diff against previous month per employee -> named approval -> finalise (ledger entry with the hash of every payslip and of the parameter snapshot) -> corrections only by a separate adjustment run. Gratuity and full-and-final sit here as their own computation with the eligibility facts listed above.

Drop for now: multi-state PT, labour welfare fund automation, ECR/24Q file generation (produce the register as CSV first), flexible benefits, arrears across tax years, old-regime exemption proofs beyond a simple declared total.

**Beyond them.**
- Every payslip line cites the parameter row and therefore the government document behind it. A payslip can be regenerated for any past month from the ledger and must match its stored hash.
- When a parameter row is proposed (for example the 25,000 ceiling), the system re-runs the last finalised month under the new value and shows the per-employee difference before anyone approves the change.
- A model may read a new circular and **propose** a parameter row with the citation filled in. It cannot activate it. Activation is a named approval, and the source PDF hash is stored with it.
- Ship a file of test vectors taken from worked examples in government FAQs and circulars; the engine must reproduce them exactly. This is the "one runnable check" for a money path.
- Fail closed: if no parameter row covers the pay date, the run stops. The current agent would silently use last year's constant.

---

### 2.3 Applicant tracking

**What we already have.** `RECRUITMENT_ATS` has a `candidates` table with one `role` and one `client` per candidate, a fixed list of eight stages, a `stage_history` table, a stale-candidate query and a CSV export. Any stage can move to any other stage; a candidate cannot apply to two roles; nothing is approved or ledgered. Stage tracking and stale alerts exist and are not re-recommended.

**How the reference projects work.**
- OpenCATS [concept level only; documentation site returned no content and source was not opened]: the long-standing open ATS for agency recruiting. Its public feature descriptions centre on candidates, companies, contacts, job orders, and a "pipeline" that joins a candidate to a job order with a status and an activity log. Everything below about it is **[unverified]** beyond that.
- Frappe HR [unverified: recruitment docs were not fetched in this session; from prior knowledge]: Job Requisition -> Job Opening -> Job Applicant -> Interview (with interview rounds and feedback) -> Job Offer -> Employee, each a document that references the previous one.
- hiring-agent [read]: explicitly states it is not an ATS. Its README is useful for what an ATS must not delegate: it describes a low cut-off used only to remove the bottom of the distribution, with everything else going to human review, and it links public criticism of its own score variance.

**What makes them good.** The join entity (candidate x opening) is the real unit of work, not the candidate. Offers and hires are separate documents that reference the application, which gives a natural approval point.

**What they get wrong.** Stage lists are global rather than per opening; rejections often lack a structured reason, which makes later fairness analysis impossible; duplicates are handled by manual merge only.

**Minimum original design (about 350 lines).**
- `requisition` (role, location, headcount, must-have and nice-to-have skill ids, scoring config version, hiring manager, approved-by).
- `candidate` (a person; see 2.6 for identity).
- `application` (candidate x requisition, source, consent record, current stage).
- `stage_def` per requisition with an explicit allowed-transition table. Terminal stages: hired, rejected, withdrawn.
- `stage_event` append-only (application, from, to, actor, reason code, free text, ledger sequence). Current stage is derived from the last event.
- `scorecard` (interviewer, per-criterion rating, evidence text) and `offer` (compensation in paise, approver, sent-at).
- Rules enforced in code: a rejection needs a reason code from a closed list; sending an offer, sending a rejection and deleting candidate data each require a named approver; no stage change is ever made by a model.
- Migration: existing `candidates` rows become one candidate plus one application each; existing `stage_history` rows become stage events.

**Beyond them.** Because every transition is an event with a reason code, the fairness audit in 2.7 and time-in-stage metrics are queries over one table. Hire converts an application into a draft `employment` row in the system of record, so onboarding starts from verified data rather than retyping.

---

### 2.4 Resume parsing

**How the reference projects work.**
1. **Resume-Matcher** [read `apps/backend/app/services/parser.py`, `ats_parse/`].
   - Upload validation before parsing: container checks for PDF, DOC and DOCX; bounded stream decoding with a byte budget so a crafted PDF cannot exhaust memory; page limits; a concurrency limiter and a hard deadline around conversion, which runs in a worker thread.
   - Conversion to markdown with a general document-to-markdown library.
   - One LLM call: "output JSON matching this schema", validated by a Pydantic model, retried up to three times, rejected if the result is structurally valid but empty.
   - **Deterministic repair after the LLM.** Two passes over the original markdown: one finds month-inclusive date ranges by regex and restores months the model dropped (it tends to turn "Jun 2020 - Aug 2021" into "2020 - 2021"); the other finds skill-list lines in the source and re-adds items the model summarised away. A source line counts as a skill list only if it has at least three short items and at least two of them were already extracted, so one coincidental match cannot pull in an unrelated line.
   - A separate "parse check" module extracts the PDF with layout (text boxes, page geometry, image count) and runs checks: is there a text layer, are glyphs garbled, is the page multi-column, are there tables, text boxes, repeated header/footer lines, images, contact info, recognisable section headings, parseable dates. A "round trip" check measures how much of the structured resume survives re-extraction and in what order.
2. **hiring-agent** [read `pdf.py`, `models.py`, `transform.py`, README].
   - PDF to markdown-like text (via a bundled PyMuPDF-based converter).
   - **One LLM call per section** (basics, work, education, skills, projects, awards), each with its own prompt template and its own Pydantic return model passed as a JSON schema for structured output. Sections are assembled into a JSON-Resume-shaped object, then normalised by plain code (date-range parsing, URL to network/username).
   - Enrichment from public profile links found in the resume.
3. **google/langextract** [description only]: extraction where each value is tied to its source span. Named here because it is the property both projects above lack natively.

**What makes them good.**
- Resume-Matcher treats the upload as hostile input and bounds every resource.
- Its repair passes are the right instinct: after the model answers, go back to the source text with deterministic code and fix the classes of error the model is known to make.
- Per-section extraction (hiring-agent) keeps each call small enough for a local model and localises failures.
- Layout checks tell you *why* a resume parsed badly instead of silently producing a thin record.

**What they get wrong.**
- Neither verifies that every extracted value actually occurs in the source. A model can invent an employer or a degree and both pipelines will accept it if the schema validates.
- hiring-agent's own README links a public report that **invisible text embedded in a PDF inflated scores**. Neither pipeline compares the text layer with what a human would see.
- hiring-agent depends on PyMuPDF, which is AGPL.
- Resume-Matcher's month and skill repairs are English-only patterns.
- Neither stores field-level provenance, so a reviewer cannot click a field and see where it came from.

**Minimum original design (about 400 lines, with one permissive PDF library and Pydantic).**
1. *Intake guard*: size, page and time limits; reject encrypted files; store the original bytes by content hash.
2. *Text extraction* with a permissive library, keeping character positions and font size/colour where available. Flag and exclude text that is tiny, white-on-white or outside the page box, and record that it was excluded. If there is no text layer, mark "needs OCR" and stop rather than guess.
3. *Deterministic fields first*: email, phone (normalised to E.164), profile URLs, date ranges, all by regex over the visible text, each with its character span.
4. *Model proposes the rest*: one call per section against a strict schema (work entries, education entries, skill phrases). The resume text is passed as data inside a delimited block and the system prompt says to treat it as data only; this is the existing guardrail capability, applied here.
5. *Grounding check, in code*: every string the model returns must be found in the visible source text after normalisation (case, whitespace, punctuation). Unfound values are dropped and logged; an entry with an unfound employer or institution is marked "unverified" for the reviewer. Dates the model returned are replaced by the regex-found dates nearest the entry.
6. *Derived facts, in code*: total experience is computed by merging date intervals, never taken from the model.
7. *Output*: structured profile plus, per field, the source span and which stage produced it. Write the parse (file hash, model id, prompt hash, dropped values) to the ledger.

Drop: OCR, photo handling, non-English resumes (flag and route to a person), profile-link enrichment.

**Beyond them.** Because a value cannot enter the record unless it is in the document, prompt injection inside a resume can at worst cause omissions, not fabrications. Parse results are cached by file hash and prompt hash, so the same file always yields the same record: the variance problem reported for hiring-agent cannot occur at this stage.

---

### 2.5 Resume-to-job matching and ranking

**What we already have.** `HR_TALENT_ENGINE` validates a candidate profile and then returns "not implemented", with a note that the previous version mixed hash noise into the result. There is no working scorer.

**How the reference projects work.**
1. **Resume-Matcher scoring** [read `services/ats.py`, `text_match.py`, `refiner.py`]. Entirely deterministic; the module header says so. Five sub-scores on 0-100:
   - keyword match (weight 0.40): share of job keywords found in the resume text as whole terms;
   - skills coverage (0.20): share of the job's required plus preferred skills found in the resume's skill list, falling back to whole-term search of the full text;
   - title match (0.15): 100 if the exact job title is in the headline, 75 if only in the summary, otherwise up to 50 scaled by word overlap after removing filler words;
   - section completeness (0.15): contact info plus four standard sections present;
   - date consistency (0.10): share of dates written in the dominant format.
   A sub-score that cannot be evaluated (no job title, fewer than two dates) is reported as null and its weight is redistributed over the rest. Term matching uses word boundaries so "java" does not match "javascript", with special handling for scripts that do not use spaces. Missing keywords are listed in the order the job posting gives them so output is stable between runs.
2. **hiring-agent scoring** [read `evaluator.py`, `models.py`, `roles/*/role.json`, criteria template]. A role is a config file: categories each with a maximum (for the shipped intern role: open source 35, self projects 30, production experience 25, technical skills 10, AI fluency 10), a list of bonus rules, a bonus cap, and overall minimum and maximum. One LLM call receives the structured resume as text and must return, per category, a score, the maximum and **non-empty evidence**. The response model is generated from the role config so the JSON schema names exactly those categories. Bonus rules are the interesting part: each rule lists its allowed point values, the generated schema restricts the field to exactly that set, and for rank-based rules the model must return the rank and **Python recomputes the points from the rank tiers and rejects a mismatch**. The bonus total is computed in code and clamped to the cap. The criteria prompt forbids using name, gender, college, grades or location.
3. **Published criticism of hiring-agent** [linked from its own README, not independently read]: the same resume scored differently across repeated runs; subjective categories were the noisy ones; a rubric built around public code contributions disadvantages people whose work is private.

**What makes them good.**
- Resume-Matcher: every number is explainable and repeatable; unknown is represented as unknown rather than as zero.
- hiring-agent: rubric as data per role; evidence required for every score; the model is boxed in by an enumerated schema and code re-derives anything that can be derived.

**What they get wrong.**
- Resume-Matcher measures keyword presence, which rewards stuffing and has no notion of synonyms, recency or depth. Two of its five components measure formatting, not fit. That suits its purpose (helping a candidate pass keyword filters) but not ours.
- hiring-agent still lets the model choose the main category numbers within a wide band, which is where the reported variance comes from. A fairness instruction in a prompt is not a control.
- Neither normalises skills to a vocabulary, so "PostgreSQL" and "Postgres" are different strings.
- Neither audits outcomes by group.

**Minimum original design (about 300 lines).**
The model never produces a number. Scoring is a fixed function over features, and the features are either computed by code or are model-proposed spans that code has verified.

- *Requisition config* (versioned, approved): must-have skill ids, nice-to-have skill ids, minimum years, required education level if any, weights.
- *Features, all deterministic*: must-have coverage and nice-to-have coverage over normalised skill ids (2.6); years of relevant experience from merged date intervals of roles whose extracted skills intersect the requisition's; recency (months since each matched skill last appears in a dated role); title similarity by token overlap; education requirement met or not; unknowns stay null with weight redistributed.
- *Evidence*: for each matched skill, the source spans from the parse. A skill that appears only in a skills list and in no dated role is counted at a lower configured weight.
- *Gates versus score*: a missing must-have does not auto-reject. It produces a "missing must-have" flag the reviewer sees first. Only a person moves an application to rejected.
- *Output*: score, per-feature breakdown, evidence spans, config version, parse hash. Same inputs always give the same output; the result is written to the ledger.
- *Scorer input is a redacted struct*: name, gender, age, photo, address, college name and any free text are not fields of the struct, so they cannot influence the score. This is enforced by the type, not by an instruction.

Drop: learned ranking models, embedding similarity between whole resume and whole job description (opaque and not needed once skills are normalised), external profile signals.

**Beyond them.** A reviewer's override (advance despite low score, reject despite high) is captured with a reason code and becomes the dataset for periodically reviewing the weights, with a person approving any weight change. Weight changes are replayed against past applications to show how rankings would have moved before approval.

---

### 2.6 Skills vocabulary, extraction and normalisation; candidate deduplication

#### Skills

**How the reference projects work.**
1. **esco-skill-extractor** [read, 257 lines]. Loads ESCO skills and occupations from CSV (id and description), embeds every description once with a small sentence-embedding model and caches the matrix. For input text: split on line breaks, full stops, commas, semicolons and the words "and"/"or"; embed each fragment; cosine similarity against all skills; take the best match per fragment if it clears a threshold (0.6 for skills, 0.55 for occupations by default). Returns ESCO ids.
2. **Nesta ojd_daps_skills** [read `map_skills/skill_mapper.py`, config for ESCO, multi-skill rules]. Two stages. *Extract*: a trained NER model tags SKILL, EXPERIENCE and BENEFIT spans; rule-based splitting turns "using and providing clinical supervision" into two skills using the dependency parse. *Map*: embed spans and taxonomy labels (preferred and alternative labels), then a **threshold ladder**: accept the closest individual skill if similarity is at least 0.7; otherwise walk up the taxonomy hierarchy from the most specific level to the most general and accept either the level whose members are most common among the near neighbours (above a share threshold) or the level whose name is closest (above 0.5). Every result carries the match type and score. A hard-coded override table wins over everything. The taxonomy is a config file (ESCO v1.1.1, Lightcast, or a toy one), so the vocabulary can be swapped.
3. **SkillNER** [read structure and matcher names]. No embeddings. A cascade of phrase matchers over a tokenised text against a skill database: full multi-word match, abbreviation match, exact single-token match (the high-confidence group), then lower-confidence matchers on normalised surface forms and on individual distinctive tokens, with a scoring step to resolve overlaps. Tokens consumed by a high-confidence match are marked so later matchers skip them.
4. **Tabiya classifier** [README only]. Entity extraction for five types (occupation, skill, qualification, experience, domain) followed by vector search onto ESCO entries.
5. **WorkRB** [README only]. An evaluation toolkit: download ontologies and datasets, run tasks (job-skill matching, skill normalisation, skill extraction, similarity), compare against baselines.

**The vocabularies.**
- **ESCO** v1.2.1: free, multilingual (28 languages), downloadable as CSV, with preferred labels, alternative labels, a skill hierarchy, occupation-to-skill relations, and delta files between versions. Weak on specific software products and versions.
- **O*NET** 31.0: CC BY 4.0. Occupation-centred, with skills, knowledge, abilities and a technology-skills list per occupation. US labour market.
- **India**: a national classification of occupations and national skills qualification material exist as government publications; they were **not** fetched in this session and their machine-readable availability is an open question.
- Lightcast Open Skills (the source behind SkillNER's database): free to browse, but its terms are not an open licence [unverified]. Do not ship its data.

**What makes them good.** Extract and map are separate steps with separate confidence. Nesta's ladder degrades gracefully to a broader category instead of forcing a wrong specific match, and records which rung matched. SkillNER's ordering (certain matches first, consuming tokens) is cheap and precise. A swappable taxonomy config keeps the vocabulary from leaking into the code.

**What they get wrong.** A fixed cosine threshold over a general embedding model confuses near neighbours ("Java" and "JavaScript" are close in embedding space). Splitting on the word "and" breaks skills that contain it. None keeps a reviewed local alias table that improves over time, and none versions the mapping so that a taxonomy update can be replayed.

**Minimum original design (about 300 lines; no model needed for the first version).**
1. `skill` table loaded from ESCO CSV (id, preferred label, alternative labels, parent ids, ESCO version), plus `skill_alias` (surface form -> skill id, source = esco / local / reviewed, added-by, ledger sequence), plus a small `local_skill` table for tools ESCO lacks, each linked to a parent ESCO concept.
2. Normalise surface forms (case, punctuation, common suffix variants) and build one dictionary from all labels and aliases.
3. Matching order: exact dictionary match on phrases from the resume's skill lists and on n-grams from role descriptions (longest match first, consuming tokens); then abbreviation table; then, optionally, embedding nearest neighbour with a high threshold, used **only to propose** an alias for review, never to assign silently.
4. Unmatched phrases go to a review queue with their frequency. A person maps each once; the alias table grows; the next resume matches deterministically.
5. Every assignment records match type and alias row id, so a mapping can be explained and, when ESCO publishes a new version, replayed using the delta file.

**Beyond them.** The alias table is a ledgered, reviewed asset specific to our hiring; it removes the model from the steady-state path. Requisitions and resumes are normalised by the same function, so matching in 2.5 is set arithmetic over ids.

#### Candidate deduplication

**How the reference projects work.** Splink [docs page headings fetched; mechanism from the published Fellegi-Sunter model, source not read] and the wider record-linkage family work the same way. For each pair of records, compare a set of fields; each comparison falls into a level (exact, close, different, missing). For each level there are two probabilities: *m*, the chance of seeing that level when the two records are the same person, and *u*, the chance when they are not. The log of m/u is the match weight for that observation; weights are summed across fields and added to a prior to give a match probability. To avoid comparing every pair, *blocking rules* only generate pairs that agree on something cheap (same email domain and surname initial, same phone suffix). m and u are estimated from the data by expectation-maximisation, with u often estimated from random pairs. Term-frequency adjustment makes agreement on a rare name count for more than agreement on a common one. Pairs above a threshold are clustered into entities.

**What makes them good.** Missing values contribute nothing instead of counting as disagreement. Every link decision decomposes into per-field weights a person can read. Blocking keeps it fast.

**What they get wrong (for our case).** They are built for millions of records with no reliable keys. Recruitment data usually has an email and a phone number. Running a trained probabilistic model for a few thousand candidates is more machinery than the problem needs, and unsupervised parameter estimates are unstable on small data.

**Minimum original design (about 200 lines, stdlib plus a phone-number library).**
1. Normalise: email (lower-case, trim; keep the raw form too), phone to E.164, profile URLs to a canonical slug, name to tokens.
2. Deterministic keys: same normalised email, or same phone, or same profile slug -> **proposed** duplicate with reason. Same resume file hash -> same document.
3. For the rest, block on (surname token, first initial) or (phone last six digits), then score with fixed, hand-set weights in the Fellegi-Sunter shape: name similarity level, date-of-birth agreement if present, overlap of employer names and date ranges from the parsed history. Missing fields add zero.
4. Nothing merges automatically. Deterministic-key matches and high scores go to a review list; a named person confirms. A merge is a ledger event that links two candidate ids to a surviving one and can be reversed; no row is deleted.
5. On a confirmed merge, applications from both records attach to the survivor so "applied before" is visible to the recruiter.

Adopt Splink only if candidate volume grows past the point where hand-set weights and a review list are workable.

**Beyond them.** Re-application detection becomes a first-class signal on the application rather than an after-the-fact cleanup. Shared contact details (one phone number across many candidates, typical of an agency or a family number) are detected as a pattern and excluded from the key set rather than causing false merges.

---

### 2.7 Bias and fairness auditing of ranking

**How the reference projects work.**
- The standard screening test is the four-fifths rule: compute each group's selection rate (selected divided by applicants), divide by the highest group's rate to get the impact ratio, and flag any ratio below 0.80. For scores rather than pass/fail decisions, the common variant uses the share of each group scoring above the overall median as the "rate". [Secondary sources; the underlying guidelines were not read.]
- fairlearn [meta; source not read] provides group-wise metric tables (a metric computed per group with differences and ratios) and aequitas [meta] produces audit reports across several group-fairness definitions. Both expect a table of decisions plus a group column.
- hiring-agent's approach is an instruction in the prompt not to use name, gender, college, grades or location. Its README links public analysis showing score variance and a successful hidden-text manipulation.
- Ranked-list fairness (for example the FA*IR line of work) checks whether each prefix of a ranking contains at least a minimum share of a protected group. The only repository found has no clear licence and has not been touched since 2020; the paper is the usable source.

**What makes them good.** The impact ratio is simple, explainable and can be computed per stage. Group metric tables make disparities visible without a model.

**What they get wrong.** A ratio on small numbers is noise, and most tools do not refuse to report it. Auditing only the final hire hides where in the funnel the disparity arises. Prompt-level fairness instructions are not testable. The toolkits assume the group attribute is available and reliable; in India, attributes such as caste or religion should generally not be collected for hiring at all, and proxies (college, home town, surname, career gaps) carry the same information.

**Minimum original design (about 150 lines).**
1. *By construction*: the scorer in 2.5 receives a struct with no name, gender, age, address, photo or institution name. A unit test asserts those fields do not exist on the type.
2. *Perturbation test*: for a sample of resumes, change only the redacted attributes in the source document (name, pronouns, address, institution name), re-run parse and score, and assert the score is identical. Any difference is a defect in the parser's leakage, reported with the field that changed.
3. *Funnel audit*: for each requisition and overall, and for each stage transition, selection rate and impact ratio by any attribute the organisation lawfully holds with consent (collected separately from the application, stored separately, never joined into the scorer). Below a minimum count per group the report prints "insufficient data" rather than a ratio.
4. *Score audit*: share above the median score per group, and the same ratio.
5. *Override audit*: rate at which human reviewers override the ranking, by group and by reviewer.
6. The audit is a scheduled, read-only report written to the ledger. It never changes a ranking; a flagged disparity opens a review item for a named person.

**Beyond them.** Because scoring is deterministic and its inputs are redacted by type, the audit separates two questions the reference tools conflate: is the scorer blind (provable, items 1-2), and are outcomes skewed anyway through the requisition's own criteria or through human decisions (measurable, items 3-5). The second is where the real findings will be, and it points at a requirement to change rather than a model to retrain.

---

## 3. Open questions and things not verified

**Statutory, need a primary source before any code is written**
1. EPF ceiling change on 17 September 2026: how September 2026 wages are treated (whole month at the new ceiling, split, or from the October wage month). The EPFO FAQ exists (cited by a professional-firm alert) but was not read.
2. EPF employer split percentages, EDLI and admin charge rates and their own ceilings after the change: not confirmed from EPFO.
3. Whether the Code on Wages definition is now the EPF contribution base. One source describes practitioner disagreement. Needs the Scheme text or EPFO guidance.
4. ESI: rates, ceilings, contribution-period dates and the rounding rule were not confirmed on esic.gov.in (page returned empty).
5. Tamil Nadu professional tax outside Chennai: each local body's schedule must be obtained for every work location in use. The nil band in the Chennai schedule was not in the fetched extract. The deduction month for the second half-year was not fetched.
6. Income tax for tax year 2026-27: slabs, rebate, standard deduction, surcharge and cess must be read from the Finance Act 2026 and the Income-tax Act, 2025. New section numbers for salary TDS and the new number of the quarterly salary TDS statement were not verified. Only the Form 16 -> Form 130 change was confirmed from the department's own FAQ.
7. Gratuity: formula, ceiling, the continuous-service reading used in Tamil Nadu, and how service before 21 November 2025 is treated under the revised wage definition.
8. Tamil Nadu state rules under the four labour codes: status not checked.
9. Tamil Nadu labour welfare fund and any shops-and-establishments obligations: not researched.
10. Data protection obligations for candidate and employee data (consent, retention, deletion) under current Indian law: not researched. This affects resume storage, the dedupe merge history and the separate store for audit attributes.

**Projects**
11. OpenCATS: only the licence file and repo metadata were read. Its data model as described here is from general product knowledge and should be treated as unverified.
12. Horilla, OrangeHRM, icehrm, Odoo, ever-gauzy, OCA/payroll: metadata only. No claim is made about their features.
13. frappe/india-payroll: README only. It has 28 stars and is new; how complete or correct its rules are is unknown. Its docs folder listing returned nothing through the API.
14. Splink, fairlearn, aequitas: mechanisms described from the published methods and documentation headings, not from source.
15. ESCO reuse terms: the download page says free of charge; the exact attribution requirement was not fetched. O*NET's CC BY 4.0 statement was fetched.
16. An Indian national occupation/skills classification in machine-readable form: not searched for successfully.
17. Lightcast Open Skills terms: not fetched; treated as non-open on the strength of prior knowledge only.
18. py-pdf/pypdf and odoo/odoo licences show as NOASSERTION in the API and were not resolved by reading the licence file.
19. Firecrawl search was rate-limited partway through; four planned searches (EPFO rates, OpenCATS docs, Splink detail, ranked fairness) did not run or were replaced by direct page fetches.

**Design decisions that need an owner**
20. Which permissive PDF library to standardise on (pdfplumber is MIT; docling is MIT and handles layout but is much heavier).
21. Whether a local embedding model is allowed at all for skill-alias proposals, or whether the first version is dictionary-only.
22. Who the named approvers are for: parameter activation, payroll finalisation, offer release, rejection, candidate merge.
