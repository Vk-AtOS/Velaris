# 05. Job publishing, lawful sourcing, careers intake, outreach, offers and e-signature, onboarding

Snapshot date 2026-11-11. Repo metadata from `gh api repos/OWNER/REPO` on that date; licences marked "LICENSE read" were taken from the LICENSE file itself because the API returned NOASSERTION.

Conventions used throughout:
- **[read]** = taken from source or docs opened in this session.
- **[docs only]** = copyleft or source-available project; only README and official docs were read, no source.
- **[secondary]** = from a third-party article, not the primary source. Treat as a lead, not a fact.
- **[memory]** = from my own knowledge, not fetched in this session. Verify before relying on it.
- **[LAWYER]** = a legal conclusion that needs a qualified Indian lawyer before we build on it.

Licence rule applied: permissive repos were shallow-cloned and read; for GPL / AGPL / LGPL / MPL / FSL / mixed-licence projects no source file was opened. No code from any project is reproduced here.

What already exists and is not re-recommended: `departments/hr/RECRUITMENT_ATS/main.py` (8-stage pipeline, stage history, stale list, CSV export, SQLite) and `departments/hr/EMPLOYEE_ONBOARDING/main.py` (11-item fixed checklist with due-day offsets, overdue list, percent progress, SQLite). Neither has: a job record, any publishing, an application intake, consent or retention, documents, outreach, offers, signatures, verification, provisioning, probation, approvals or ledger writes. Everything below is additive to those two.

---

## 1. Verification table

### 1a. Candidates named in the brief

| Path | Licence as fetched | Last push | Stars | Status | Verdict |
|---|---|---|---|---|---|
| speedyapply/JobSpy | MIT | 2026-10-27 | 4,700 | active. `Bunsly/JobSpy` and `cullenwatson/JobSpy` both redirect here, so this is the canonical repo | **Study the data model, avoid the mechanism.** It scrapes LinkedIn, Indeed, Glassdoor, Naukri and others and advertises "proxy support to bypass blocking". It reads job ads, it does not post them, and running it breaks those sites' terms. |
| documenso/documenso | AGPL-3.0 | 2026-11-11 | 15,722 | active. README says external pull requests are no longer accepted | **Study [docs only].** Confirmed AGPL. |
| docusealco/docuseal | AGPL-3.0 | 2026-11-09 | 19,040 | active | **Study [docs only].** Confirmed AGPL. Reminders, SMS identity check, bulk send and conditional fields are listed as paid "Pro" features in the README. |
| formbricks/formbricks | Mixed (LICENSE read): AGPLv3 for the core, a separate enterprise licence under `apps/web/modules/ee`, MIT only for the SDK packages | 2026-11-11 | 13,234 | active | **Skip.** It is a survey tool, not an application-intake tool, and the core is AGPL. |
| opencats/OpenCATS | Dual (LICENSE.md read): MPL-2.0 for new code, "CATS Public License 1.1a" (a modified MPL) for the 2007 code | 2026-11-11 | 781 | active, with a modernisation roadmap | **Study [docs only].** Weak copyleft, PHP, built for staffing agencies. Useful as a feature inventory only. |

### 1b. Others found and checked

| Path | Licence as fetched | Last push | Stars | Status | Verdict |
|---|---|---|---|---|---|
| **MatthiasValvekens/pyHanko** | MIT | 2026-11-11 | 799 | active | **Study and depend on. Top pick for e-signature.** Python PDF signing and validation: PAdES baseline profiles, RFC 3161 timestamps, PKCS#11 tokens, remote signing. |
| MatthiasValvekens/certomancer | MIT | 2026-11-06 | 30 | active | Study. Test PKI (fake CA, TSA, OCSP) for exercising a signing flow offline. |
| m32/endesive | MIT | 2026-10-31 | 277 | active | Study as a second opinion. Smaller Python signer for PDF, email and XML. |
| open-pdf-sign/open-pdf-sign | Apache-2.0 | 2026-02-09 | 953 | slow | Skip (Java CLI). |
| digitorus/pdfsign | BSD-2-Clause | 2026-10-26 | 172 | active | Skip (Go). |
| vbuch/node-signpdf | MIT | 2026-11-07 | 942 | active | Skip (Node). |
| esig/dss | LGPL-2.1 | 2026-11-04 | 1,050 | active | Reference [docs only]. The EU reference implementation for AdES; Java. |
| letsseal/letsseal | Apache-2.0 | 2026-10-19 | 379 | active, new | Watch. Defines a "sealed evidence anchored to a ledger" file-proof format; relevant to our ledger idea, unproven. |
| OpenSignLabs/OpenSign | Mixed (LICENSE read): AGPL-3.0 plus a separately licensed directory | 2026-11-10 | 7,250 | active | Study [docs only]. Email OTP for guest signers is the notable feature. |
| LibreSign/libresign | AGPL-3.0 | 2026-11-11 | 844 | active | Skip (Nextcloud app). |
| **MicroPyramid/opensource-job-portal** | MIT | 2026-10-30 | 494 | active | **Study.** Django + SvelteKit job board from an Indian company; emits JobPosting markup and a sitemap. |
| ever-jobs/ever-jobs | MIT | 2026-11-11 | 141 | active | Avoid the mechanism. An aggregator that scrapes 160+ boards, including LinkedIn and Naukri. Read side only. |
| strelov1/freehire | MIT | 2026-11-11 | 3,486 | active | Skip. Job-seeker search engine fed from company career pages. Shows that a well-marked careers page gets picked up by aggregators for free. |
| fossjobs/fossjobs | MIT | 2025-05-06 | 382 | stale | Skip. |
| jobberbase/jobberbase | MIT | 2019-01-19 | 284 | dead | Skip. |
| tramcar/tramcar | MIT | 2024-03-18 | 66 | dead | Skip. |
| nueno-co/nueno | AGPL-3.0 | 2022-07-27 | 269 | dead | Skip. |
| frappe/hrms | GPL-3.0 | 2026-11-11 | 9,044 | active | **Study [docs only].** Best open model of the whole chain: Job Opening, Job Applicant, Job Offer, Appointment Letter, Employee Onboarding template. Indian vendor. |
| horilla/horilla-hr (was horilla-opensource/horilla) | LGPL-2.1 | 2026-11-11 | 1,508 | active, v2 branch | Study [docs only]. Django HRMS with recruitment, onboarding, assets and document requests. |
| odoo/odoo | LGPL-3 (LICENSE read) | 2026-11-11 | 55,714 | active | Reference [docs only]. |
| orangehrm/orangehrm | GPL-3.0 | 2026-06-28 | 1,161 | slow | Skip. |
| OCA/hr | AGPL-3.0 | 2026-11-11 | 286 | active | Skip. |
| aureuserp/aureuserp | MIT | 2026-11-06 | 12,193 | active | Optional. Laravel ERP with a recruitment plugin; permissive but PHP. Not read. |
| **chiefonboarding/ChiefOnboarding** | AGPL-3.0 | 2026-11-08 | 935 | active | **Study [docs only].** The only dedicated open onboarding product: pre-boarding, sequences, admin tasks, provisioning manifests. |
| lantingzhang1119/cohort-harbor | MIT | 2026-11-04 | 194 | active, new, single author | Optional. Policy versions, acknowledgement by exam, private files with watermark and audit log. Not read beyond README. |
| heyform/heyform | AGPL-3.0 | 2026-11-11 | 9,071 | active | Skip. |
| OpnForm/OpnForm | Mixed (LICENSE read): AGPLv3 plus an enterprise directory | 2026-11-09 | 4,003 | active | Skip. |
| ohmyform/ohmyform | AGPL-3.0 | 2024-10-31 | 2,887 | **archived** | Skip. |
| baptisteArno/typebot.io | FSL-1.1-Apache-2.0 (LICENSE read; source-available) | 2026-11-07 | 10,622 | active | Avoid. Not open source until the delayed Apache conversion. |
| formio/formio | OSL-3.0 | 2026-11-09 | 2,329 | active | Skip (copyleft). |
| surveyjs/survey-library | MIT | 2026-11-11 | 4,930 | active | Optional. JSON-schema-driven form renderer; the idea (form as data) is what matters. |
| formtools/core | none | 2023-09-08 | 210 | dead | Avoid (no licence). |
| nocodb/nocodb | "Sustainable Use License" (LICENSE read) | 2026-11-11 | 65,507 | active | Avoid (source-available). |
| altcha-org/altcha | MIT | 2026-10-22 | 2,894 | active | **Study.** Proof-of-work spam check with no third-party service; fits local-first. |
| tus/tusd | MIT | 2026-11-05 | 3,918 | active | Skip. Resumable uploads are not needed for 5 MB CVs. |
| Cisco-Talos/clamav | GPL-2.0 | 2026-11-06 | 7,540 | active | **Use as a separate daemon, do not link or copy.** Talking to `clamd` over its socket does not make our code a derivative work [LAWYER if distributed bundled]. |
| VirusTotal/yara | BSD-3-Clause | 2026-10-27 | 10,027 | active | Optional second scanner. |
| collective/icalendar | BSD-2-Clause | 2026-11-11 | 1,187 | active | Study / optional dependency for calendar files. |
| allenporter/ical | Apache-2.0 | 2026-11-11 | 50 | active | Optional. |
| calcom/cal.diy (calcom/cal.com now redirects here) | MIT (LICENSE read) | 2026-11-11 | 49,936 | active. README warns it is the community edition for "personal, non-production use" | Reference only. Too large to read for one feature; note the licence changed from what most people remember. |
| knadh/listmonk | AGPL-3.0 | 2026-11-11 | 24,252 | active | Study [docs only] for list hygiene (bounces, unsubscribe). Indian author. |
| useplunk/plunk, usesend/useSend | AGPL-3.0 | 2026-11 | 5.6k / 4.8k | active | Skip. |
| mautic/mautic | GPL-3.0 (LICENSE.txt read) | 2026-11-11 | 10,965 | active | Reference [docs only] for sequence concepts. |
| twentyhq/twenty | Mixed (LICENSE read): AGPLv3 with commercial files and some MIT packages | 2026-11-11 | 60,785 | active | Skip. |
| Kozea/WeasyPrint | BSD-3-Clause | 2026-11-10 | 9,779 | active | **Use.** HTML and CSS to PDF in Python; the natural offer-letter renderer. |
| py-pdf/pypdf | BSD-3-Clause text (LICENSE read) | 2026-11-11 | 10,298 | active | Use for reading and stamping PDFs. |
| python-openxml/python-docx | MIT | 2026-08-01 | 5,765 | active | Optional, if HR insists on editing templates in Word. |
| elapouya/python-docx-template | LGPL-2.1 | 2026-07-07 | 2,732 | active | Avoid copying; use as an unmodified library only if needed. |
| pdfme/pdfme | MIT | 2026-11-01 | 5,047 | active | Optional (TypeScript template designer). |
| gotenberg/gotenberg | MIT | 2026-11-10 | 13,563 | active | Optional (DOCX to PDF through a LibreOffice container). |
| Hopding/pdf-lib | MIT | 2024-07-17 | 8,672 | stale | Skip. |
| carboneio/carbone, open-xml-templating/docxtemplater, Stirling-Tools/Stirling-PDF, LibrePDF/OpenPDF | NOASSERTION, LICENSE not read | 2026 | - | active | Not assessed. |
| mindee/doctr | Apache-2.0 | 2026-11-11 | 6,430 | active | Optional OCR for uploaded identity documents. |
| sherlock-project/sherlock | MIT | 2026-11-11 | 109,913 | active | **Avoid for hiring.** Username lookups across sites build a profile the candidate never agreed to. |

Corrections to the candidate list:
1. JobSpy is canonical at `speedyapply/JobSpy`; the older owner names redirect. It is a scraper, not a multiposting tool.
2. Formbricks is not simply AGPL: it is AGPL core + enterprise directory + MIT SDKs.
3. OpenCATS is MPL-2.0 plus an older modified-MPL licence, not GPL.
4. `calcom/cal.com` now resolves to `calcom/cal.diy` under MIT.
5. **No maintained open-source multiposting tool was found.** GitHub searches for "multiposting", "job distribution" and "Indeed XML feed" returned only abandoned or zero-star repos. The reason is in section 2: the big boards gate posting behind partner contracts, so there is nothing for an open tool to call.

---

## 2. Job boards: what is possible for free in 2026

| Board | Free programmatic route | Paid or partner route | Manual free posting | Source |
|---|---|---|---|---|
| **Google for Jobs** | **Yes.** Put schema.org `JobPosting` JSON-LD on each job page of our own careers site. India is in the supported-region list. Notify with the Indexing API (`URL_UPDATED`, `URL_DELETED`), which is restricted to JobPosting and livestream pages, costs nothing, and defaults to 200 publish requests per day per project. Also submit a sitemap with accurate `lastmod`. | None needed | Not a board; there is nothing to post manually | [read] [JobPosting doc](https://developers.google.com/search/docs/appearance/structured-data/job-posting), [Indexing API usage](https://developers.google.com/search/apis/indexing-api/v3/using-api), [quota](https://developers.google.com/search/apis/indexing-api/v3/quota-pricing) |
| **Indeed** | **Partly.** The XML feed is the route for a direct employer. Indeed's March 2026 policy removed free visibility for single-source feeds *where the jobs could have come through an integrated ATS*; it says feeds from ATSs without an Indeed integration, naming "homegrown systems", are not affected. So a home-built system's feed is still eligible, but Indeed must accept the feed and can require sponsorship at any time. | Job Sync API (GraphQL: create, upsert, expire, status) is described as "for ATS partners", needs integration review, and the ATS guidelines reportedly require at least ten clients [secondary]. One third-party guide says direct-employer access opened on 2026-07-31; the official pages I read do not say this. **Unverified.** Sponsored jobs are pay-per-click. | Yes. India is listed as having no free-post cap; free posts show for up to 120 days. | [read] [XML feed reference](https://docs.indeed.com/job-sync-xml/xml-feed), [Job Sync API](https://docs.indeed.com/job-sync-api), [FAQ](https://docs.indeed.com/job-sync-api/faq), [single-source feed policy](https://www.indeed.com/help/employers/articles/single-source-feed-policy-effective-march-31-2026), [free job post limit](https://www.indeed.com/help/employers/articles/free-job-post-limit) |
| **LinkedIn** | **No.** The Job Posting API page opens with "We are currently not accepting new partnerships for LinkedIn's Job Posting API". Use is "restricted to those developers approved by LinkedIn" with a signed agreement. "Basic Jobs" (the renamed "Limited Listings") are free but only reach LinkedIn through an approved partner's API or feed. Partners are forbidden from marketing it as "a free way to post jobs to LinkedIn". | Talent Solutions partner (ATS or job distributor); Promoted jobs and Job Slots are paid | Yes, by a person in the LinkedIn UI: one free post active at a time, active up to 14 days, auto-closes at 30 days if not promoted, applications capped (typically 10 to 30). A reported cap of 150 active limited listings per company from 2026-09-14 is [secondary]. | [read] [Job Posting API overview](https://learn.microsoft.com/en-us/linkedin/talent/job-postings/api/overview), [free job post help](https://www.linkedin.com/help/linkedin/answer/a517777) |
| **Naukri** | **No public API found.** Posting from an ATS is a commercial integration arranged with Naukri's team; Greenhouse's help page says the customer needs a paid Naukri subscription plus a paid integration module. | Paid job packs (about ₹3,300 to ₹6,000 for small packs [secondary]) | Reported: one free job a month for verified company accounts, live 7 days, 50 applications [secondary; Naukri's own page returned 403 to me] | [read] [Greenhouse Naukri integration](https://support.greenhouse.io/hc/en-us/articles/16297968058651-Naukri-integration); [secondary] [100hires India guide](https://100hires.com/best-job-posting-sites-in-india.html) |
| **Foundit (ex-Monster India)** | None found | Sales-quoted | Not published | [secondary] same guide. **Unverified.** |
| **Shine** | None found | About ₹999 for 2 jobs [secondary] | None listed | [secondary]. **Unverified.** |
| **Apna** | None found | From about ₹699 a post [secondary] | Conflicting reports (one says a free post stays live 15 days) | [secondary]. **Unverified.** |
| **Internshala** | None found | Premium from about ₹2,999 a month [secondary] | Reported free tier: 1 listing a month, 20 applications [secondary] | [secondary]. **Unverified.** |
| **Wellfound** | None found | Paid ads and seats priced in USD [secondary] | Reported unlimited free listings for startups [secondary; sources disagree] | [secondary]. **Unverified.** |
| **Hirist** | None found | Sales-quoted | Reported basic free plan [secondary] | [secondary]. **Unverified.** |
| **Instahyre** | None found | Not public | Reported free plan with 3 tech and 10 non-tech slots [secondary] | [secondary]. **Unverified.** |
| **National Career Service (ncs.gov.in)** | None documented. The Labour Ministry says NCS takes vacancies in through API links with private job portals, but that is a government-to-portal arrangement with no public developer programme I could find. | None; the NCS FAQ says it "does not charge any fee at any stage" | **Yes.** Employer registers (PAN for proprietors; Udyam-registered MSMEs have a linked route) and posts vacancies by hand. | [read] NCS FAQ text via ncs.gov.in; [secondary] ministry press releases |
| **Aggregators (Jooble, Adzuna, Talent.com, Jora and similar)** | Usually accept an employer XML feed or simply crawl pages carrying JobPosting markup. Not verified per aggregator in this session. | Sponsored clicks | n/a | [memory]. **Unverified.** |

Plain conclusion for a zero-budget Indian company:
1. The only fully free, fully programmatic, no-contract route is **our own careers page with JobPosting markup, pushed through the Google Indexing API**. That also feeds every aggregator that crawls structured data.
2. **Indeed by XML feed** is the one big board where a home-built system may still get free organic listing. It needs a one-time manual request to Indeed and may be refused.
3. **Everything else is manual posting by a person**, within each board's free limits. LinkedIn is closed to new API partners; Naukri and the Indian boards sell integrations.
4. So the product feature is not "multiposting". It is a **posting pack**: per board, the system prepares the exact text, fields and a tracked apply link, a named person approves it, a person pastes it, and the system records where and when it went live and when it must come down.

### How a "job feed" is structured (the three shapes that matter)

- **Page-level markup, push notification (Google)** [read]. One URL per job. Required properties: `title`, `description` (HTML, must be the full job, not a teaser), `datePosted`, `hiringOrganization`, `jobLocation` with `addressCountry` (or `jobLocationType: TELECOMMUTE` plus `applicantLocationRequirements` for fully remote). Recommended: `validThrough`, `employmentType` (fixed enum), `baseSalary` (must be the real figure, not an estimate), `identifier`, `directApply`. Expiry rule: Google "does not allow expired job postings"; to take one down, set `validThrough` in the past, or return 404/410, or remove the markup, and then send `URL_DELETED`. Content rules that bite: no login wall in front of the description, no fee from applicants, no "collecting CVs" for roles that are not open.
- **Full-snapshot pull feed (Indeed XML)** [read]. One document: a `source` root with one `job` element per opening. Required per job: title, date first published, a `referencenumber` that must never change, requisition id, URL, company, city, state, country, contact email, description; ATS vendors add publisher and source name. Rules: the feed must contain **every** job on the careers site ("does not support partial job opt-in"); a job is removed by leaving it out; reusing a reference number shows only the first; a future date hides the job; Indeed re-reads a hosted feed four times a day. Application duplicates are defined as same job id plus same email within 120 days.
- **Per-job API calls (Indeed Job Sync, LinkedIn Job Posting)** [read docs]. Create, upsert, expire by the sender's own posting id. Indeed: "Jobs do not expire automatically. Call the API to expire jobs"; a job can be reactivated within 30 days with the same id; Indeed can block an integration that sends stale jobs.
- **How an open-source board does it (PeelJobs, MIT)** [read `site/src/routes/(site)/jobs/[id]/+page.svelte`, `backend/psite/sitemaps.py`, `backend/dashboard/tasks.py`]. The job page builds the JSON-LD object from the job record in the front end; a Django sitemap class lists live jobs with daily change frequency; a scheduled task finds jobs published exactly N days ago and emails an expiry notice.
- **The read side (JobSpy, MIT)** [read `jobspy/model.py`]. One flat record for a job from any board: site, URL, direct URL, title, company, location, date posted, job type list, pay interval with min, max and currency, remote flag, level, function, description, skills, experience range, vacancy count. Useful as a checklist of fields other systems expect.

What they get wrong:
- PeelJobs computes `validThrough` in the browser as "published + 30 days" while the server expires jobs in a separate task, so the markup and the real state can disagree; country and currency are hard-coded.
- Feed formats have no notion of *who approved* a posting or *why* it was withdrawn.
- Scrapers such as JobSpy and ever-jobs treat blocking as a technical obstacle (proxies) rather than a refusal.

---

## 3. Sub-areas

### 3a. Publishing job openings

**How it works (best references: Google's spec, Indeed's feed spec, PeelJobs, Frappe HR docs).** Frappe HR [docs only] keeps a Job Opening with title, designation, department, a "publish on website" switch and open/closed status, optionally capped by a staffing plan; a closed opening stops accepting applicants. The public page and the feed are both projections of that one record.

**What makes it good.** One record, many projections. A stable id per opening that never changes. Expiry treated as a first-class state because both Google and Indeed punish stale jobs.

**Minimum original design (~350 lines, stdlib plus one HTTP client).**
- A `JobOpening` record: stable public id, title, HTML description, location or remote rule, employment type, optional salary band, opening date, closing date, status (`draft`, `approved`, `live`, `closed`, `filled`, `withdrawn`), named approver, content hash.
- Three pure functions from that record: JSON-LD object for the page; one `job` element for the XML feed; a plain-text posting pack per manual board (LinkedIn, Naukri, NCS, Indeed UI) with that board's field limits and a tracked apply URL carrying a source tag.
- A validator that refuses to approve a record missing any Google-required property, with a salary that is not the real band, or with a closing date in the past.
- One expiry routine, run daily and on every status change: when a job leaves `live`, set `validThrough` to now, drop it from the feed and sitemap, queue `URL_DELETED`, and open a task for each board where a person posted it by hand ("take down by date X").
- A `Placement` row per board: who posted, when, the live URL, the board's own expiry date, and when it was taken down.
- Indexing API notifier behind a switch, since it needs a Google service account that owns the site in Search Console.

**Beyond them.**
- The approval and the exact published bytes go to the hash-linked ledger, so "what did we advertise, and who signed it off" has one answer.
- The model may draft the description; deterministic checks decide whether it can go out (required fields, pay band inside the approved band, no age/gender/community wording, closing date present).
- Source tags on apply links give a cost-free per-board yield report, which tells a zero-budget company where to spend its one free LinkedIn slot.

### 3b. Finding candidates lawfully

Ranked by safety and yield for a small company:

1. **Inbound applications through our own careers page.** The candidate gives the data and the consent in one step. No terms problem.
2. **Referrals.** The clean pattern is a referral *link*: the employee sends the link, the candidate applies personally. An employee typing a friend's details into our system puts personal data in without that person's consent or notice.
3. **Talent pool re-discovery.** Search past applicants for a new role. Lawful only inside the purpose and period the candidate agreed to, so the consent text must say "this role and similar future roles for N months", and each record needs an expiry date. No open project implements this properly; it is a query plus a rule.
4. **GitHub public API** [read] [search docs](https://docs.github.com/en/rest/search/search), [Acceptable Use Policies](https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies). User search is free: 30 requests a minute when authenticated, 1,000 results per query. But the Acceptable Use Policies say information from the service, "whether scraped, collected through our API, or obtained otherwise", may not be used "for spamming purposes, including for the purposes of sending unsolicited emails to users or selling personal information, such as to recruiters, headhunters, and job boards". So: finding a person is allowed; mailing an address taken from GitHub is not. Workable use: the system proposes public profiles with the reason for the match; a recruiter opens the profile and makes contact only through a channel the person has themselves advertised for work contact, one message, by hand. A profile "hireable" flag exists [memory].
5. **Stack Overflow and other public developer profiles.** The Stack Exchange API exposes public profiles without email addresses [memory]; the same no-harvest logic applies. **API terms not fetched: unverified.**
6. **People-search and enrichment tools.** Avoid. They infer or buy contact details the person never gave us, and under the DPDP Act we would be the party answerable for having them. Sherlock-style username sweeps are the same problem.

Routes that break a site's terms:
- **Scraping LinkedIn** in any form. User Agreement section 8.2 [read] forbids software, scripts, robots, crawlers or browser plugins that "scrape or copy the Services, including profiles and other data", forbids using bots or automated methods to access the service or send messages, and forbids copying information obtained from the service through third parties. This rules out JobSpy-style tools, browser extensions that export profiles, and bought LinkedIn datasets. [User Agreement](https://www.linkedin.com/legal/user-agreement)
- **Scraping Naukri, Indeed, Glassdoor** with JobSpy or ever-jobs: same class of breach; these tools exist to read job ads but the terms problem is identical. Each board's terms were not individually fetched.
- **Emailing addresses harvested from GitHub** (commit metadata or profile), as above.

**Minimum original design (~300 lines).** A `Lead` record that cannot exist without a `source` (inbound, referral link, pool, public profile) and a `lawful_basis` (consent with a notice version, or "public profile, contact not yet made"). Pool search is a filter over past candidates whose consent is still in date. Public-profile search stores only the profile URL, the public fields shown, the query that found it and the match reason; it never stores an email it was not given. Every proposed contact is a draft that a named recruiter must approve and send.

**Beyond them.** A lead with no lawful basis is unrepresentable in the schema, not merely discouraged. The ledger holds the query and the reason for every sourced lead, which is the record a candidate or regulator would ask for.

### 3c. Careers site and application intake

**How the good ones work.** Frappe HR and Horilla [docs only] render the careers page from the job record and take applications into a Job Applicant record through a web form. PeelJobs [read] does the same with a separate front end. Form builders (SurveyJS, MIT) treat the form as a JSON document: field list, types, validation rules, conditional display; the renderer is generic. ALTCHA (MIT) [README level] replaces a third-party captcha with a proof-of-work challenge the server issues and verifies itself.

**What they get wrong.** None of the HR suites show a consent notice with a version, a retention date, or a withdrawal path on the application form. Duplicate handling is usually "same email".

**Minimum original design (~400 lines).**
- Careers pages rendered server-side from `JobOpening` (crawlers must see the JSON-LD without running scripts; no login wall).
- One application form defined as data: name, email, phone, CV file, a few role questions. Do not ask for Aadhaar, PAN, date of birth, photo, caste, religion or marital status at this stage.
- Notice and consent block: what is collected, why, how long, how to withdraw, who to complain to; an unticked box; the notice version and the time stored with the application.
- File handling: accept PDF and DOCX only; size cap; check the file's leading bytes, not the extension; store under a random name outside the web root; compute a SHA-256; stream to a local `clamd` over its socket before the file is marked usable [memory for the protocol]; never open the file in the request handler; serve it back only as a download with a fixed content type.
- Spam: a hidden field that humans leave empty, a minimum fill time, a per-address rate limit, and a self-hosted proof-of-work challenge.
- Duplicates: normalised email and normalised phone as keys, plus the CV hash. Same person, same job, inside 120 days (Indeed's own window) is a duplicate that updates the existing application; same person, different job is a new application on the same candidate.
- Email confirmation link before the application counts, which also proves the address for later outreach.

**Beyond them.** Every intake writes the consent record and file hash to the ledger. A retention sweeper deletes or anonymises on the date promised and records that it did. Model-based CV parsing produces *proposals* shown next to the original; the stored fields are the ones a person confirmed.

### 3d. Outreach and invitations

**How the good ones work.** listmonk and Mautic [docs only] separate templates, lists, a send queue with rate limiting, bounce processing and an unsubscribe list that is checked at send time. ChiefOnboarding [README] calls drip steps "sequences": items released by day offset or when an earlier item is completed. Calendar invitations are plain iCalendar text (RFC 5545) carried in the email as a `text/calendar; method=REQUEST` part (RFC 5546 and RFC 6047) [memory for the RFC details]; the `icalendar` library (BSD-2) builds them, though for one event the format is small enough to write directly.

**The parts that are easy to get wrong** [memory]:
- An invitation is identified by `UID`. Rescheduling is the same `UID` with a higher `SEQUENCE`; cancelling is `METHOD:CANCEL` with the same `UID`. A new `UID` creates a second event in the candidate's calendar.
- Times need an explicit zone (`Asia/Kolkata`) or UTC; floating times shift for remote candidates.
- `ORGANIZER` must be a mailbox that can receive the accept/decline replies.
- Bulk mail to Gmail and Yahoo addresses needs SPF, DKIM, DMARC and one-click unsubscribe headers (RFC 8058).

**Minimum original design (~350 lines).**
- `Template` (subject, body, allowed variables; unknown variables fail the render).
- `Sequence` as an ordered list of steps: template, delay, stop conditions (reply received, stage changed, unsubscribed, consent expired).
- `Message` rows with states `drafted`, `approved`, `sent`, `bounced`, `replied`; nothing leaves `drafted` without a named approver. Approving a sequence for one candidate approves those exact rendered messages, not a blank cheque.
- A suppression table checked immediately before every send, fed by unsubscribe links (signed token, no login), bounces and withdrawal of consent.
- Interview invitations: one ICS builder, a stored `UID` and sequence counter per interview, reminder messages at fixed offsets, cancel and reschedule as updates to the same event.
- Sending through the company's own SMTP; no third-party marketing service.

**Beyond them.** The ledger entry for each send holds the rendered body hash, the approver and the consent record relied on. Cold outreach to a sourced lead is capped at one message unless the person replies; the cap is in code, not policy.

**Legal note.** India has no general statute on unsolicited commercial email comparable to its telecom rules for SMS and voice; promotional SMS needs registered headers and templates under TRAI's rules [memory, LAWYER]. Recruitment email to a person who did not apply still involves processing their personal data, which is where the DPDP Act applies (section 4).

### 3e. Offer letters and e-signature

**How the AGPL projects do it** [docs only: Documenso [signing workflow](https://docs.documenso.com/docs/concepts/signing-workflow) and [signing certificates](https://docs.documenso.com/docs/concepts/signing-certificates) pages, DocuSeal and OpenSign READMEs].
1. **Data model.** A document (draft, pending, completed, rejected); recipients with a role (signer, approver, viewer, CC) and optionally a signing position; fields (signature, initials, date, text, checkbox) each tied to one recipient and a page position.
2. **Flow.** Owner prepares, places fields, sends. Each recipient gets an emailed link that is unique to them. Signing is parallel by default or sequential by position. Optional checks before signing: email verification, an access code sent separately, a passkey (Documenso); email OTP for guests (OpenSign); SMS verification (DocuSeal, paid tier).
3. **What a "signature" is.** The recipient draws, types or uploads an image. That image is placed on the page. It carries no cryptography.
4. **The seal.** When the last required recipient finishes, the *platform* signs the finished PDF once with its own X.509 certificate: hash the document, sign the hash with the platform's private key, embed signature and certificate in the PDF. Documenso states it plainly: "The signature is applied at the platform level, not by individual signers." A trusted timestamp from a timestamp authority can be added. With a self-signed certificate the integrity check still works but PDF readers show a warning; a CA-issued certificate on Adobe's trust list shows a green tick. Documenso also offers hardware key storage and a remote-signing route to trust service providers for higher EU signature levels.
5. **Signer identity evidence.** An audit log of events with "IP addresses and timestamps for each action", when each recipient viewed and signed, and which authentication was used; the log can be attached to the document.

**What they get wrong, or leave unsaid.**
- The cryptographic signature proves *the platform* sealed the file. It proves nothing by itself about the candidate. Identity rests entirely on "someone with access to this mailbox clicked", plus an IP address.
- The audit log lives in the vendor's database. It is tamper-evident only if you trust that database.
- None of them maps to Indian law: no Aadhaar eSign, no DSC token support described in the docs I read.

**The permissive and standards route to the same result.**
- **Standards** [memory for the standard names]: PDF signatures per ISO 32000; PAdES baseline profiles (ETSI EN 319 142) B-B, B-T (adds a timestamp), B-LT (adds validation data), B-LTA (adds an archival document timestamp); CMS (RFC 5652) for the signature container; RFC 3161 for timestamps.
- **pyHanko (MIT)** [read: `docs/lib-guide/signing.rst`, `docs/lib-guide/validation/diff-analysis.rst`, outline of `sign/signers/pdf_byterange.py`, `cms_embedder.py`, `diff_analysis/policy_api.py`]. The mechanism: the signer appends an incremental update containing a signature field and a signature object whose contents entry is a fixed-size placeholder; the byte range covers the whole file except that placeholder; the digest of that range is signed; the resulting CMS object is written into the reserved space. Because the update is incremental, earlier signatures stay valid. Three features matter for us:
  - **PAdES profiles and RFC 3161 timestamps** are settings, including the long-term archival profile.
  - **Interrupted signing.** pyHanko can prepare the document, hand back the digest, stop, and later accept a complete CMS container produced elsewhere, even when "the signer's certificate is unknown until the remote signing service produces its response". That is exactly the shape of India's eSign service: the application sends a document hash to a licensed provider, the person authenticates with Aadhaar OTP, and a signature over the hash comes back.
  - **Difference analysis on validation.** Changes after a signature are classified by level: none, archival updates only, form filling and further signatures, annotations, or other. So a validator can say "signed, then only another signature was added" versus "signed, then altered".
  - It also signs with **PKCS#11 tokens**, which is how a director's USB Digital Signature Certificate is used.
- **certomancer (MIT)** gives a throwaway CA and timestamp server for tests.
- **WeasyPrint (BSD)** renders the letter from an HTML template; **pypdf (BSD)** reads and stamps.

**What makes an electronic signature valid in India.**
- **Recognised electronic signatures** [secondary: [law-firm summary](https://www.amsshardul.com/insight/modernizing-e-signature-laws-in-india/)]. Under the Information Technology Act 2000, section 3 covers digital signatures (asymmetric key pair plus hash, issued by a licensed certifying authority: the DSC), and section 3A covers electronic signatures by a technique listed in the Second Schedule, which currently lists authentication "using Aadhaar or other e-KYC services" (Aadhaar eSign, added 2015; other e-KYC added 2019). Section 5 gives these the same effect as a handwritten signature where a law requires one.
- **Contracts formed electronically.** Section 10A says a contract is not unenforceable solely because it was formed by electronic means [secondary, same source]. So a candidate clicking "I accept this offer" can form a binding contract. That click is **not** a section 3A electronic signature; it is conduct, and its weight depends on the evidence we can produce.
- **Excluded documents.** The First Schedule excludes negotiable instruments other than cheques, powers of attorney, trusts, wills and (with 2022 changes) certain property contracts [secondary]. An offer or appointment letter is not on that list.
- **How to get Aadhaar eSign.** The Controller of Certifying Authorities publishes the eSign API specification (v3.3 dated December 2020 was the newest I found; [CCA PDF](https://www.cca.gov.in/sites/files/pdf/esign/eSign-APIv3.3.pdf), not read in full). The application provider signs a request and sends it to a licensed eSign service provider under an agreement with that provider. **It is a paid, contracted service; I found no free route and no published price. Unverified.**
- **Evidence in court.** Electronic records need a certificate under the Bharatiya Sakshya Adhiniyam 2023 (section 63, successor to section 65B of the Evidence Act) [memory, LAWYER].
- **Stamp duty** on employment agreements and bonds in Tamil Nadu, and whether an offer letter attracts any [LAWYER].
- **Appointment order** requirements under Tamil Nadu shops and establishments law [memory, LAWYER].

**Click-to-sign versus a legally recognised signature, in one table.**

| | Click-to-accept with evidence bundle | Organisation seal (PAdES, our certificate) | Aadhaar eSign | DSC on a token |
|---|---|---|---|---|
| Proves the file is unchanged | only with a stored hash | yes | yes | yes |
| Proves who signed | mailbox control, OTP, IP | the organisation only | the Aadhaar holder, via a licensed provider | the certificate holder |
| Section 3 / 3A signature | no | no, unless the certificate is a licensed DSC | yes | yes |
| Cost | none | none (self-signed) | per signature, contract | certificate fee; directors usually already hold one for company filings [memory] |
| Fit | the candidate's acceptance | every document we issue | bonds, or where the other side insists | the company signatory |

**Minimum original design (~450 lines plus pyHanko, WeasyPrint).**
1. `OfferTemplate` in HTML with a fixed variable list; rendering with a missing or unknown variable fails.
2. Figures (pay, joining date, probation length) come from structured fields validated against the approved band for the role; the model may draft wording but cannot set a number.
3. A named approver approves the rendered PDF by its SHA-256. Any change voids the approval.
4. The company signatory signs: PAdES with the director's DSC token if available, otherwise the organisation certificate. Add an RFC 3161 timestamp when a timestamp service is reachable; when offline, record that and timestamp later.
5. The candidate gets a single-use, expiring link; proves mailbox control with a one-time code; sees the full PDF; must tick an explicit statement and type their name; can decline with a reason.
6. On acceptance, build an evidence record: document hash, candidate email, code delivery and verification times, IP address and browser string, the exact statement shown, the typed name. Append a human-readable evidence page, then apply the final organisation seal over the whole file as an incremental update, so the signatory's signature remains valid.
7. Write the document hash and evidence hash to the ledger. The ledger chain, not our application database, is what makes the audit trail tamper-evident.
8. A `verify` function: check signatures, classify post-signature changes, compare the hash to the ledger entry.
9. Leave a seam for Aadhaar eSign: the same prepare-digest, wait, embed-CMS path pyHanko documents.

**Beyond them.** The open tools keep the audit log beside the document; we bind the two (evidence page inside the sealed file, hash in an external chain). Approval is tied to the bytes, which none of them do for the sender side. A second timestamp from a different authority costs nothing and removes a single point of trust.

### 3f. Onboarding beyond a checklist

**How the good ones work** [docs only].
- **Frappe HR** [read docs](https://docs.frappe.io/hr/employee-onboarding): an Employee Onboarding document is created for an approved applicant from an Onboarding Template tied to department, designation and grade. Each template activity has a name, an assigned user or role, a start offset in days, a duration and a weight. Submitting it creates a project and one task per activity, with dates that skip holidays. The employee record can be created only when all mandatory tasks are done; status becomes Completed when every activity is finished.
- **ChiefOnboarding** [README]: starts before day one with pre-boarding pages; separates new-hire to-dos (which can contain forms) from admin to-dos for colleagues; "sequences" release items by time or when an earlier item is completed; "manifests" describe API calls that create accounts in other systems or produce documents to sign; resources and short courses; introductions.
- **Horilla** [README]: document requests with approval, asset tracking, onboarding and offboarding flows.
- **CohortHarbor** [README]: policy documents with versions, reading plus a test as proof of acknowledgement, private file storage with watermarking and an audit log.

**What makes them good.** Template plus offsets relative to the joining date (the existing checklist already does this). Tasks owned by a role, not a person. Gates: something cannot happen until something else is done. Separate lists for the new hire and for staff.

**What they get wrong for India.** No handling rules for Aadhaar or PAN. No verification states on documents (received is treated as verified). No probation clock. Provisioning runs automatically once configured, with no approval step.

**Minimum original design (~500 lines).**
- **Template with gates.** Each item: owner role, offset from joining date, working-day arithmetic against the Tamil Nadu holiday list, `blocks` relationships, and an evidence requirement (a file, a field, an acknowledgement or an approval). The existing fixed checklist becomes the default template.
- **Document collection with states**: `requested`, `received`, `verified`, `rejected`, `expired`; verifier name and date on each.
  - **PAN**: format check (five letters, four digits, one letter; fourth character indicates holder type) [memory]; store encrypted; display masked.
  - **Aadhaar**: do not store the full number or an unmasked copy. Ask for masked Aadhaar (first eight digits hidden; [UIDAI FAQ](https://www.uidai.gov.in/283-faqs/aadhaar-online-services/e-aadhaar/1887-what-is-masked-aadhaar.html)); store the last four digits only; if an unmasked copy is uploaded, redact before saving and discard the original. UIDAI has said unlicensed private entities are "not permitted to collect or keep copies of Aadhaar card" [secondary, 2022 release], and in 2026 is onboarding registered "offline verification seeking entities" [secondary]. Whether a small employer must register to verify the signed QR code [LAWYER].
  - **UAN**: EPFO allows monthly returns only for members whose Aadhaar is seeded and verified against the UAN [secondary: [EPFO circular](https://epfindia.gov.in/site_docs/PDFs/Circulars/Y2024-2025/Mandatory_aadhaar_seeding_11062024.pdf) listed, not read]. Prefer that the employee seeds Aadhaar in the EPFO member portal themselves so we hold only the UAN [memory, LAWYER].
  - **Bank details**: IFSC format check, account number entered twice, cancelled-cheque image; any later change requires a second person's approval, because payroll diversion is the usual fraud.
  - Education and experience letters: store, hash, mark verified by a named person.
- **Background verification as a case**, not a checkbox: written consent first (stored with its version); one check per claim (identity, address, education, last employer, references); each check has a method, a result, evidence and a verifier; the hiring manager sees only "clear / discrepancy / pending", not the documents. DigiLocker offers a consent-based requester API for issued documents; private companies registered in India can apply through the API Setu partner portal, with no published fee schedule or sandbox [secondary; [requester terms](https://cf-media.api-setu.in/resources/DigiLocker-Terms-of-User-Requester-june-2025.pdf) listed, not read]. Treat as a later option. Court-record and police checks [LAWYER].
- **Asset and account provisioning**: a provisioning *request* per account or device, approved by a named person, executed by a small adapter or done by hand, with the serial number or account id recorded. The same rows drive offboarding: every grant has a matching revoke.
- **Policy acknowledgement**: each policy has a version and a content hash; the acknowledgement records employee, version, hash and time, and optionally a short comprehension question. A new version re-opens the acknowledgement.
- **First-week plan**: a dated schedule generated from the template, sent as calendar invitations through the outreach module; the buddy is an assigned person with their own tasks.
- **Probation tracking**: start date, length from the offer letter, review points (the existing 30/60/90 items), and a decision task (confirm, extend, end) that opens a fixed number of days before the end date and escalates if untouched; the confirmation letter goes through the offer-letter pipeline.

**Beyond them.** Sensitive fields are encrypted and every read is logged to the ledger with the reader's name and purpose. Documents collected for verification get a deletion date at the moment of collection. The onboarding record is created only from an accepted, sealed offer, so the chain job → application → offer → employee is unbroken and checkable.

---

## 4. Legal and terms-of-use notes

Nothing here is legal advice. Items tagged [LAWYER] should be confirmed before launch.

### Digital Personal Data Protection Act 2023 and Rules 2025

Read from the Gazette text of the Act (PRS copy, converted locally):
- **Section 3(c)(ii)**: the Act does not apply to personal data "made or caused to be made publicly available by the Data Principal to whom such personal data relates" or by someone legally obliged to publish it. The Act's own illustration is a person blogging their details on social media. Consequence: a developer's self-published public profile may sit outside the Act. This does **not** override a website's terms of use, and it does not cover data other people published about them. [LAWYER on how far this reaches for recruiting.]
- **Section 5**: every consent request must come with or after a notice stating the personal data and purpose, how to withdraw consent and use the grievance route, and how to complain to the Board; available in English or a Schedule Eight language (Tamil is one).
- **Section 6**: consent must be "free, specific, informed, unconditional and unambiguous with a clear affirmative action", limited to data necessary for the stated purpose; withdrawal must be as easy as giving it; withdrawal does not undo earlier lawful processing.
- **Section 7(i)**: processing without consent is allowed "for the purposes of employment or those related to safeguarding the employer from loss or liability". This clearly helps for employees. Whether it covers *candidates* before any employment exists is not settled by the text. **Design on consent for candidates; rely on 7(i) only for employees.** [LAWYER]
- **Section 8(7)**: unless another law requires retention, erase personal data when consent is withdrawn "or as soon as it is reasonable to assume that the specified purpose is no longer being served, whichever is earlier", and make processors erase too. For a rejected candidate the purpose ends with the decision unless they agreed to stay in the pool.
- **Section 8(5), 8(6)**: reasonable security safeguards; notify the Board and each affected person of a breach.
- **Sections 11 to 13**: rights to a summary of data held and who it was shared with, to correction and erasure, and to grievance redress.
- **Schedule**: penalties up to ₹250 crore for failing to take reasonable security safeguards [amount from memory; the lines I read show ₹200 crore for breach-notification failure and ₹50 crore for other breaches].

Commencement [secondary: [AZB note](https://www.azbpartners.com/bank/indias-digital-personal-data-protection-act-phased-rollout-and-key-compliance-milestones/); sources differ by a day on dates]:
- November 2025: Rules notified; definitions and the Data Protection Board provisions in force.
- November 2026 (this week): consent manager registration.
- **May 2027**: the substantive duties, including sections 3 to 17 (notice, consent, legitimate uses, fiduciary obligations, rights) and Rules 3 and 5 to 16. So there is roughly a six-month runway, and whatever we build should meet these from the start.

Rules details that I could only get second-hand and that matter to our design [secondary, **unverified against the Gazette**]: a requirement to keep processing logs for at least one year; notice to the person 48 hours before erasure in some cases; fixed retention periods in the Third Schedule that apply to certain large platform classes rather than to everyone.

Design consequences:
1. Versioned notice shown at application; consent stored with version, time and scope.
2. Separate, optional consent for "keep me in the talent pool for N months".
3. A retention date on every candidate record; a sweeper that erases or anonymises and logs it.
4. A withdrawal and erasure path that needs no login.
5. A hash-linked ledger must not hold personal data in clear, or erasure becomes impossible. Store hashes and opaque ids in the ledger; keep the personal data in erasable rows. (The existing audit chain was flagged for exactly this: email and IP in an append-only table.)
6. Any outside service that touches candidate data (email relay, verification vendor) is a processor we answer for.

### Aadhaar
- Do not make Aadhaar a condition of applying. Collect nothing Aadhaar-related before an offer is accepted.
- After joining, hold the minimum: last four digits and a masked copy at most. Statutory basis for an employer to ask for Aadhaar for provident fund purposes rests on the Code on Social Security section 142 and EPFO circulars [secondary]. [LAWYER]

### Electronic signature
See 3e. Summary: Aadhaar eSign and DSC are recognised signatures; a click is evidence of acceptance under section 10A, not a signature. Stamp duty and Tamil Nadu appointment-order rules [LAWYER].

### Site terms
- LinkedIn User Agreement 8.2: no scraping, no bots, no copying obtained data [read].
- GitHub Acceptable Use Policies section 7: API use is allowed but the information may not be used for unsolicited email or sold to recruiters [read].
- Google job posting content policies: no expired jobs, no login wall, no applicant fees, no CV collection for closed roles; violations risk a manual action [read].
- Indeed: the feed must contain all jobs; staffing agencies generally must sponsor [read for the first, secondary for the second].
- LinkedIn partner terms forbid describing an integration as a free way to post to LinkedIn [read].

### Discrimination and advert wording
Job adverts should not state preferences by gender, age, religion, caste or marital status. Specific statutes and their reach for a private employer in Tamil Nadu [LAWYER].

---

## 5. Open questions and unverified items

1. **Indeed for a direct employer.** Will Indeed accept a new single-employer XML feed from a home-built system in India and show it organically? The policy text says such feeds are "not affected", but acceptance is at Indeed's discretion. Needs one email to Indeed. The claim that the Job Sync API opened to direct employers on 2026-07-31 is from one third-party guide and contradicts the wording of the API page I read.
2. **All Indian board terms** (Naukri, Foundit, Shine, Apna, Internshala, Wellfound, Hirist, Instahyre): free limits and prices are from third-party articles, mostly one source that sells a competing product. Naukri's pricing page refused my request. Someone should open each employer page while logged in and record the real limits.
3. **NCS**: no public API found; employer steps are from secondary guides.
4. **Aggregator feeds** (Jooble, Adzuna, Talent.com): not checked.
5. **LinkedIn Basic Jobs cap of 150** per company from September 2026: one secondary source.
6. **Stack Exchange API terms**: not fetched.
7. **DPDP Rules 2025 text**: not read directly; MeitY's site returned 403. The Act was read. Whether section 7(i) covers candidates, and the reach of the public-data exclusion, need a lawyer.
8. **IT Act sections 3, 3A, 5, 10A, First and Second Schedules**: taken from a law-firm summary, not the bare Act. The evidentiary presumption for secure electronic signatures and the BSA section 63 certificate are from memory.
9. **Aadhaar eSign cost and onboarding** with a licensed provider: not found. CCA API specification located but not read in full.
10. **UIDAI rules for employers**: the 2022 statement and the 2026 offline-verification programme are from press reports; the Aadhaar (Authentication and Offline Verification) Regulations 2021 were located but not read.
11. **DocuSeal's own documentation site** redirected to a raw cloud host during fetch, so I did not follow it; DocuSeal findings are from its README only.
12. **ChiefOnboarding sequence triggers and manifest format**: the docs landing page had no detail; described from the README only.
13. **Frappe HR Job Opening**: closing date, route and salary fields exist in the product as I remember it, but the doc page I read does not list them.
14. **clamd stream protocol, iCalendar and RFC 8058 details, PAdES profile names, PAN format**: from memory; all are stable public standards and easy to confirm.
15. **Free RFC 3161 timestamp services** suitable for production, and whether any is run by an Indian licensed certifying authority: not checked.
16. **Not read at all** (metadata only): aureuserp, cohort-harbor beyond README, letsseal beyond README, endesive, certomancer, cal.diy, surveyjs, altcha source.
17. Search tooling note: the configured search provider rate-limited early, so most searches used the built-in web search and page fetch; page fetches are summarised by a small model, so direct quotes above should be re-checked against the linked page before being quoted onward.
