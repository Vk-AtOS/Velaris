# Research 03: company chat and company email, with an AI participant

Researched 2026-11-11. Method: GitHub API (`repos/OWNER/NAME`, `/license`, `/readme`, `/releases/latest`), LICENSE files fetched directly where the API said NOASSERTION or returned nothing, PyPI JSON for library licences, RFC 8621 text for the undo-send mechanism, and shallow clones (read only, nothing executed) of permissively licensed repos. For GPL, AGPL and source-available projects only README, LICENSE and public docs were read; no source.

Licence consequences in this document are a description of what the licence files say and of common practice. They are not legal conclusions. A lawyer has to confirm them before anything is bundled into a product that is sold.

Marking used below: **[V]** fetched today; **[M]** from prior knowledge of public specs or docs, not re-fetched today, treat as unverified.

---

## 1. Verification table

All rows: repo exists at the path shown, not archived, unless stated. Stars and push dates as returned by the GitHub API on 2026-11-11.

### 1a. The candidate list

| Repo | Licence as fetched | Last push | Stars | Status | Verdict |
|---|---|---|---|---|---|
| zulip/zulip | Apache-2.0 (LICENSE is the plain Apache text; no carve-out seen in the file head) | 2026-11-11 | 26,207 | Active; release 12.4 on 2026-11-06 | **Study** (source may be read). Best chat data model. |
| mattermost/mattermost | Mixed, per LICENSE.txt: compiled versions produced by the vendor are MIT; building from source is AGPL-3.0 or a commercial licence; `server/templates/`, `server/i18n/`, `server/public/`, `webapp/` are Apache-2.0; `server/enterprise/` has its own "Source Available License" (production use requires agreeing to the vendor's enterprise terms). Trademark use needs written approval. | 2026-11-11 | 39,580 | Active | **Docs only.** Do not read server source. Avoid as a dependency. |
| RocketChat/Rocket.Chat | MIT for everything outside `apps/meteor/ee/` and `ee/`; those directories are under an Enterprise Edition licence (production use only with a subscription agreement) | 2026-11-11 | 46,451 | Active | **Skip.** MIT core is readable, but the MongoDB/Meteor design does not fit our stack and the ee boundary is easy to cross by accident. |
| element-hq/synapse | AGPL-3.0, with a LICENSE-COMMERCIAL file alongside (dual licence) | 2026-11-11 | 4,786 | Active; v1.165.0 on 2026-11-10 | **Docs and Matrix spec only.** The old matrix-org/synapse (Apache-2.0, 12,090 stars) is archived, last push 2024-04-26. |
| Conduit (timokoesters/conduit is a GitHub mirror; famedly/conduit on GitHub is 404; the real home is GitLab famedly/conduit) | Apache-2.0 (mirror) | 2026-11-10 (GitLab last activity 2026-11-10) | 607 mirror / 963 GitLab | Alive, slow | Study only if needed |
| conduwuit (girlbossceo/conduwuit now redirects to x86pup/conduwuit) | Apache-2.0 | 2026-05-29 | 27 | **Archived. Dead.** | Skip |
| matrix-construct/tuwunel | Apache-2.0 | 2026-11-11 | 2,762 | Active; README calls itself the official successor to conduwuit with full-time staff and government sponsorship | **Run unmodified** candidate if we ever want Matrix |
| continuwuity/continuwuity | Apache-2.0 | 2026-11-11 | 1,171 | Active community fork (primary forge is elsewhere, GitHub is a mirror); last GitHub release v26.7.2 on 2026-08-07 | Alternative to tuwunel |
| stalwartlabs/stalwart (stalwartlabs/mail-server redirects here) | GitHub API reports no licence. README says dual: AGPL-3.0 and Stalwart Enterprise License v2 (proprietary); each file carries its own notice (REUSE). LICENSES directory holds AGPL-3.0-only, LicenseRef-SEL, plus Apache-2.0, MIT and Unlicense texts for some files. | 2026-11-10 | 15,861 | Active; v1.1.0 on 2026-11-09 | **Docs only. Run unmodified as optional separate service; do not bundle without legal advice.** |
| roundcube/roundcubemail | GPL-3.0 (API; the repo's licence file may carry plugin/skin exceptions, not checked) | 2026-11-11 | 7,268 | Active; 1.7.6 on 2026-11-09 | Skip (PHP, GPL, IMAP-era design) |
| the-djmaze/snappymail | AGPL-3.0 | 2026-11-11 | 1,753 | Active; v3.0.1 on 2026-11-09 | Skip |
| Mail-0/Zero | MIT (LICENSE fetched) | 2026-10-27 | 10,884 | Active | **Study** (AI client; source may be read) |
| elie222/inbox-zero | **Not plain AGPL.** LICENSE is AGPL-3.0 plus "additional terms": no commercial monetisation of the software or derivatives without written permission, and organisations with five or more business users need an enterprise licence. | 2026-11-11 | 12,988 | Active | **Avoid.** README and public docs only. Never read source, never bundle. |
| mailcow/mailcow-dockerized | GPL-3.0 | 2026-11-10 | 13,779 | Active | Skip (a bundle of Postfix, Dovecot, Rspamd, SOGo; heavy; GPL) |

### 1b. Corrections to the candidate list

1. inbox-zero is AGPL with added commercial restrictions, which makes it effectively source-available for our purposes. It is the most dangerous item on the list for a product that will be sold.
2. Mattermost is not simply "MIT" or "AGPL". Vendor-built binaries are MIT; source is AGPL or commercial; one directory is source-available.
3. Stalwart's repo was renamed from mail-server to stalwart, and is AGPL-3.0 or a proprietary enterprise licence. Its Sieve interpreter repo (stalwartlabs/sieve) is archived and AGPL/SEL; development moved into the main repo. Its mail-auth library is Apache-2.0 or MIT.
4. conduwuit is archived. Two live successors exist: tuwunel and continuwuity. Conduit itself lives on GitLab.
5. Synapse is dual AGPL/commercial; the Apache-licensed original is archived.

### 1c. Better or newer projects found

| Repo | Licence as fetched | Last push | Stars | What it is | Verdict |
|---|---|---|---|---|---|
| **suitenumerique/messages** | MIT (LICENSE fetched) | 2026-11-11 | 208 | Collaborative inbox in Django + React: Python inbound SMTP front end, Python delivery agent, direct-to-MX or relay outbound, DKIM/ARC, rspamd, shared mailboxes, AI summary and labelling | **Study first.** Closest thing to what we want, in our language, permissive. |
| **mjl-/mox** | MIT (README; includes some BSD-3 and MPL-2.0 data) | 2026-10-27 | 5,940 | Single-binary Go mail server: SMTP, IMAP4, webmail, SPF/DKIM/DMARC, reputation, Bayesian junk filter, ACME, MTA-STS/DANE, HTTP/JSON send API and webhooks | **Run unmodified** candidate. Version v0.0.17 (2026-08-19): still pre-1.0. |
| basecamp/once-campfire | MIT | 2026-11-06 | 4,825 | Small single-tenant chat (Rails, SQLite) | Study as the "smallest complete chat" |
| mattermost/mattermost-plugin-agents | Apache-2.0 (LICENSE fetched) | 2026-11-11 | 257 | AI agents inside chat with per-tool approval | **Study** (its approval model is the best documented) |
| langchain-ai/agents-from-scratch | MIT | 2026-08-11 | 2,443 | Reference email assistant with triage, human-in-the-loop and memory | **Study** |
| langchain-ai/executive-ai-assistant, langchain-ai/agent-inbox | MIT | 2026-07-27, 2026-09-18 | 2,206 / 1,097 | Earlier versions of the same idea | Both **archived**; skip |
| humanlayer/humanlayer | Apache-2.0 | 2026-11-05 | 12,859 | Human approval for agent tool calls | Not examined in depth |
| livekit/livekit | Apache-2.0 | 2026-11-11 | 22,148 | WebRTC media server for calls | **Run unmodified** when calls are needed |
| jitsi/jitsi-meet | Apache-2.0 | 2026-11-11 | 30,221 | Meeting stack | Alternative for calls |
| centrifugal/centrifugo | Apache-2.0 | 2026-11-11 | 10,963 | Real-time pub/sub server | Not needed; Redis plus our own queue is enough |
| apache/james-project | Apache-2.0 | 2026-11-11 | 1,052 | Java mail server with JMAP | Permissive JMAP server, but a JVM service; skip unless JMAP server is required |
| cyrusimap/cyrus-imapd | BSD-style (COPYING fetched) | 2026-11-11 | 653 | IMAP/JMAP/CalDAV server | Heavy to operate; skip |
| rspamd/rspamd | Apache-2.0 (LICENSE fetched) | 2026-11-11 | 2,568 | Spam filter with HTTP scan API | **Run unmodified** |
| aio-libs/aiosmtpd | Apache-2.0 | 2026-11-01 | 374 | Python asyncio SMTP server library | **Use as a library** |
| haraka/Haraka, postalserver/postal | MIT | 2026-11 | 5,635 / 16,949 | Node SMTP server; Ruby outbound delivery platform | Skip (wrong stack) |
| docker-mailserver/docker-mailserver, Mailu/Mailu, modoboa/modoboa | MIT, MIT (LICENSE.md fetched), ISC | 2026-11 | 19,738 / 7,614 / 3,543 | Bundles around Postfix/Dovecot | Wrappers are permissive, the bundled daemons have their own licences; skip |
| foxcpp/maddy | GPL-3.0 | 2026-11-11 | 6,128 | Go all-in-one mail server | Skip (mox is the MIT equivalent) |
| bulwarkmail/webmail | AGPL-3.0-only with an app-store permission; derived from an earlier MIT project | 2026-11-11 | 1,462 | JMAP webmail for Stalwart | Docs only |
| root-fr/jmap-webmail | MIT | 2026-09-20 | 238 | The MIT ancestor of the above | Study if we build a JMAP webmail |
| thunderbird/stormbox | MPL-2.0 | 2026-11-10 | 121 | Prototype JMAP webmail with a browser-local SQLite cache | Read the architecture docs; MPL is file-level copyleft |
| fastmail/overture | MIT | 2026-11-11 | 769 | JS framework behind a large JMAP webmail | Reference |
| jmapio/jmap | Apache-2.0 | 2026-11-04 | 1,387 | The JMAP spec sources | Standard |
| htunnicliff/jmap-jam | MIT (package.json; no LICENSE file at root) | 2026-11-10 | 93 | Tiny typed TypeScript JMAP client | Library candidate |
| wyattjoh/jmap-mcp | MIT | 2026-11-04 | 179 | MCP server over JMAP | Shows an AI-over-JMAP shape |
| matrix-org/matrix-spec, matrix-js-sdk, matrix-rust-sdk | Apache-2.0 | 2026-11 | 333 / 2,199 / 2,357 | Spec and client SDKs | Standard and libraries |
| matrix-nio/matrix-nio | ISC (LICENSE.md fetched) | 2026-10-22 | 710 | Python Matrix client | Library candidate |
| ruma/ruma | MIT | 2026-11-11 | 748 | Rust Matrix types | Reference |
| element-hq/element-web, dendrite, element-call, matrix-authentication-service | AGPL-3.0 | 2026 | n/a | Client, Go homeserver, calls, auth | Docs only |
| stoatchat/stoatchat (formerly revoltchat/backend) | AGPL-3.0, with some crates under their own licence | 2026-11-11 | 3,464 | Discord-like chat | Skip |
| tinode/chat | GPL-3.0 | 2026-10-25 | 13,565 | Chat server | Skip |
| hcengineering/platform | EPL-2.0 | 2026-11-09 | 28,092 | All-in-one workspace with chat | Not examined |
| macro-inc/macro | AGPL-3.0 | 2026-11-11 | 6,255 | Unified email + chat + docs + agents workspace | Product reference only; docs only |
| kurrier-org/kurrier | not determined (API says NOASSERTION) | 2026-11-08 | 1,073 | Self-hosted email/calendar workspace | Not examined |
| Kozea/Radicale, jelmer/xandikos, sabre-io/Baikal | GPL-3.0 | 2026-11 | 5,205 / 614 / 3,371 | CalDAV/CardDAV servers | Run-unmodified only; prefer writing our own minimal CalDAV later |
| nextcloud/spreed, nextcloud/mail, linagora/tmail-flutter | AGPL-3.0 | 2026-11 | n/a | Talk, mail app, JMAP mobile client | Skip |
| processone/ejabberd | GPL-2.0 with OpenSSL exception | 2026-11-10 | 6,750 | XMPP server | Skip |

Python libraries (licence from PyPI metadata today): aiosmtpd 1.4.6 Apache-2.0; aiosmtplib 5.1.3 MIT; dkimpy 1.1.8 "BSD-like"; authheaders 0.16.3 MIT; pyspf 2.0.14 PSF; dnspython 2.9.2 ISC; sievelib 1.6.0 MIT; icalendar 7.3.0 BSD-2-Clause; vobject 0.9.9 Apache; caldav 3.7.0 "GPL-3.0-or-later OR Apache-2.0"; slixmpp 1.17.0 MIT (its GitHub copy is archived; development is elsewhere); matrix-nio 0.26.0 ISC. **Avoid:** aioimaplib 2.0.3 (GPL-3.0-only), jmapc 0.4.1 (GPL-3.0-only), aioxmpp (LGPLv3+), mautrix and py-vapid (MPL-2.0, usable but file-level copyleft). Node: nodemailer, imapflow, postal-mime carry MIT-style licence text (LICENSE fetched; the API could not classify them). The Python standard library covers `email`, `smtplib`, `imaplib`.

Not found at the path guessed: ValiMail/authheaders, bjc/prosody, iNPUTmice/lttrs-android, stalwartlabs/webmail, matrix-org/sliding-sync-proxy, linagora/twake-mail. Prosody (XMPP server, believed MIT) was therefore not verified.

### 1d. Public standards that let us write our own

- Chat: Matrix client-server spec (Apache-2.0 text); XMPP (RFC 6120/6121 plus XEPs). [M]
- Email transport and format: SMTP RFC 5321, message format RFC 5322, MIME RFC 2045 onward, submission RFC 6409. [M]
- Email access: IMAP4rev2 RFC 9051; JMAP core RFC 8620 and JMAP Mail RFC 8621 [V for 8621]; JMAP over WebSocket RFC 8887, JMAP Sieve RFC 9661, JMAP Contacts RFC 9610, JMAP Sharing RFC 9670 (numbers as listed in the Stalwart README today).
- Authentication: SPF RFC 7208, DKIM RFC 6376, DMARC RFC 7489, ARC RFC 8617; transport security MTA-STS RFC 8461, TLS reporting RFC 8460, DANE RFC 6698.
- Filters: Sieve RFC 5228, ManageSieve RFC 5804.
- Calendar and contacts: iCalendar RFC 5545, iTIP RFC 5546, CalDAV RFC 4791, CalDAV scheduling RFC 6638, vCard RFC 6350, CardDAV RFC 6352.
- Delayed send: FUTURERELEASE RFC 4865, referenced by RFC 8621. [V]

---

## 2. Team chat

### How it works

**Zulip (Apache-2.0; public subsystem docs read today).**
- Data model: organisation, channel ("stream"), topic, message. A topic is a short string on the message, not a separate object, so every channel message belongs to exactly one named conversation. Direct messages are addressed to a set of users. [M for the schema detail]
- Per-recipient state: one row per (user, message) holds that user's flags (read, mentioned, starred). The docs describe this row and an optimisation, "soft deactivation", that stops creating rows for users who have not logged in for a while and backfills them on return. [V]
- Real-time delivery: every state change is an "event", a small dictionary with a type, sent to an explicit list of user ids. The call that emits the event is made inside the database transaction and fires only on commit. Events go through a queue to a separate long-lived process that keeps one in-memory event queue per connected client. Clients register (which returns a queue id, a last event id and, in the same call, the full initial state so there is no gap between snapshot and stream), then long-poll with the last event id they have processed; the server deletes acknowledged events. That acknowledgement is what gives effectively exactly-once delivery across dropped connections. A heartbeat event is sent about every 45 seconds; idle queues are garbage-collected after about 10 minutes; a client that gets "queue not found" simply reloads its initial state. The docs say the whole delivery system is about 2,000 lines. [V]
- Ordering: message ids are assigned by the database, so one total order per organisation; event ids are a per-queue counter. [V for event ids, M for message ids]
- Local echo: the sending client shows the message immediately with a temporary local id, sends that id and its queue id with the request, and the server includes the local id in the event delivered to that one queue so the client can swap temporary for real without a flicker. [V]
- Unread state: the initial state includes the list of unread message ids grouped by conversation (channel + topic, one-to-one sender, group) plus the ids that mention the user. Counts are derived on the client. Three event types keep it correct: new message, flag update, and message update (a topic rename moves unread ids). [V]
- Search: PostgreSQL built-in full-text search with a custom English stop-word list; the index for a new message is updated in the background after delivery so sending is not slowed. An alternative extension gives all-language search. Search composes with the same "narrow" filters used for normal browsing. [V]
- Notifications: the event process decides, per recipient, whether the user is idle (no live queue, or presence says idle) and if so queues an email or mobile push; the check is repeated when a queue is garbage-collected so a message is not missed when a laptop sleeps. Emails are batched over a delay. [V]
- Bots: a bot is a user row with an owner and an API key; "generic" bots act through the same API as people, "incoming webhook" bots can only post, "outgoing webhook" bots receive an HTTP call when mentioned. Permissions are therefore ordinary user permissions plus channel subscription. [M]

**Matrix (spec, Apache-2.0; homeservers tuwunel/continuwuity Apache-2.0, Synapse AGPL).** [M throughout]
- Data model: a room is an append-only graph of signed events; state (name, members, power levels) is itself events. Threads and edits and reactions are events that relate to another event. There is no channel/topic split; "spaces" group rooms.
- Delivery: the client calls a sync endpoint with an opaque "since" token and gets a batch plus the next token. Ordering inside one server is that server's stream order; across servers the graph is merged by a state-resolution algorithm, which is the hard and expensive part and exists only for federation.
- Unread: read receipts and a private "fully read" marker are events per room; the server computes notification and highlight counts per room using push rules.
- Bots: either an ordinary user with an access token, or an "application service" registered by the admin that may claim a namespace of users and receives all matching events by HTTP push. Permissions are numeric power levels per room.
- End-to-end encryption is the default for private rooms in common clients, which means a server-side assistant cannot read content unless it is a member with keys.

**Mattermost (docs and LICENSE only).** [M] Teams, channels, posts; a thread is posts that share a root id; real-time over a WebSocket carrying typed events; unread via per-member last-viewed timestamps and mention counts; search via the database or an enterprise search engine; integrations via bot accounts, webhooks, slash commands and server plugins.

**Campfire (MIT; schema read today).** Rooms (open, closed, direct), memberships, messages. The membership row holds a single `unread_at` timestamp, an "involvement" level (everything, mentions, nothing, invisible) and a connection counter that doubles as presence. Messages carry a client-generated id for de-duplication. Bots are users with a token and a webhook URL. This is the minimum that still feels complete. [V for schema]

**Rocket.Chat.** [M] MongoDB documents for rooms, subscriptions (per-user per-room unread counter), messages; real-time through a publish/subscribe protocol over WebSocket. Not studied further.

### What makes them good

- Zulip's topic field solves the main failure of channel chat: several conversations interleaved in one stream. It also gives an AI a natural unit to summarise, triage and reply to.
- Zulip's register-then-poll protocol with acknowledged event ids is simple, survives restarts and bad networks, and makes every client (web, bot, AI) use the same path.
- Sending the snapshot and opening the queue atomically removes a whole class of race bugs.
- Campfire shows that one timestamp per membership is enough for unread in a small company.
- The Mattermost agents plugin's shared-channel approval rules (section 4) are the clearest written model of who may approve what.

### What they get wrong (for us)

- Matrix pays for federation and encryption everywhere: a signed event graph, state resolution, key management. We need none of it on one machine, and encryption actively blocks an assistant.
- Zulip's per-(user, message) row grows as users times messages; fine for one company, and the docs admit it needs soft deactivation at scale.
- Zulip's event queues live in process memory; a restart forces every client to reload.
- Mattermost and Rocket.Chat gate compliance features (retention, export, audit) behind enterprise licences, which is exactly what our ledger gives for free.
- None of them treats an AI message as a proposal that is not yet a message. Bots just post.

### Minimum original design (prose; about 3,000 lines of Python in modules under 600 lines each, plus roughly 3,500 lines of React)

- Tables: `channel` (kind: public, private, direct, group), `membership` (user, channel, role, notify level, last_read_message_id), `message` (id from a sequence, channel, topic text, sender, body markdown, rendered html, client_nonce, edited_at, deleted_at), `message_revision` (append-only history for edits and deletes), `mention` (message, user or group), `reaction`, `attachment` (content-addressed blob), and `user_flag` only for exceptions (starred, mentioned-unread) rather than one row per recipient.
- Unread: per membership, a last-read message id plus a per-topic override table for "read this topic but not that one". Unread count is a count over an index range. This is Campfire's simplicity with Zulip's topic granularity.
- Ordering: the message id sequence is the order. One machine, one PostgreSQL, so no clocks and no merge.
- Delivery: on commit, write an event (type, payload, recipient user ids) to a Redis stream per organisation. A FastAPI endpoint serves Server-Sent Events or a WebSocket; each client presents the last event id it processed, and the server replays from the stream. Because the queue lives in Redis rather than process memory, restarts do not drop clients. Register returns snapshot plus cursor in one transaction.
- Presence and typing: ephemeral Redis keys with a short expiry; never written to PostgreSQL or the ledger.
- Search: a generated `tsvector` column with a GIN index, using the `simple` configuration so Indian-language and mixed text is not mangled by English stemming; add trigram search for names. Filters (channel, topic, sender, has-file, date) are ordinary SQL.
- Bots and the assistant: a bot is a principal with scoped capabilities (read channel X, propose message in X, post without approval in X). The assistant is a principal like any other; the difference is that its writes land in a proposal table (section 4) unless a capability says otherwise.
- Edits, deletes, retention: edits and deletes append a revision and a ledger entry; retention is a per-channel policy applied by a nightly job that tombstones bodies and records the purge in the ledger.
- Calls: not built. Run LiveKit (Apache-2.0) unmodified later and store only room tokens and call records.
- Bridges and federation: not built. If ever needed, expose a subset of the Matrix client-server API or run tuwunel beside us.

### Beyond them

- Every message, edit, delete, approval and retention purge is a hash-linked ledger entry, which is the compliance export others sell.
- The assistant's drafts are visible in the thread as pending proposals with an approve/edit/reject control, not as bot posts.
- Topic-level summaries cached against the last message id they cover, so "catch me up" costs nothing until new messages arrive.
- One conversation model for chat topics and email threads (section 3), so a topic can be "this email thread, discussed internally".

---

## 3. Email

### How it works

**A modern all-in-one server (Stalwart; README and docs only, AGPL/SEL).** One Rust process speaks SMTP in and out, IMAP, POP3, JMAP, ManageSieve, CalDAV, CardDAV and WebDAV, over one storage abstraction that can sit on an embedded key-value store, PostgreSQL, SQLite or others, with blobs optionally in object storage and full-text search built in or delegated. Inbound mail passes SPF, DKIM, DMARC and ARC checks, a rule-based and statistical spam filter with reputation and greylisting, then Sieve scripts, then delivery. Outbound goes through a queue with retry schedules, per-destination throttling, DKIM signing with key rotation, MTA-STS and DANE. It also handles TLS certificates automatically and can manage DNS records. [V from README]

**mox (MIT; README read).** The same idea in one Go binary with a narrower scope: SMTP, IMAP4, its own webmail and admin UI, SPF/DKIM/DMARC with aggregate reports, per-user reputation and Bayesian junk filtering learned from what users mark as junk, slow-down of unknown senders instead of plain greylisting, a temporary "Rejects" mailbox so false positives can be recovered, automatic TLS, MTA-STS and DANE, and an HTTP/JSON API with webhooks for sending and for incoming-message events. A quickstart command generates the config and prints the DNS records to create. No JMAP, CalDAV or Sieve listed. [V]

**suitenumerique/messages (MIT; docs and module docstrings read).** This is the one to learn from because it is not a mail server in the classical sense; it is an application that owns the mailbox.
- Inbound: a stateless, queue-less SMTP front end (a Python asyncio SMTP library; an older variant used a classical MTA with a filter hook). During the recipient command it asks the backend over HTTP whether the address exists; during the data command it posts the raw message to the backend and waits. The backend's answer is translated into one SMTP reply. The rule is "losing mail is worse than asking for a retry": only a short explicit list of outcomes becomes a permanent rejection, everything else is a temporary failure so the sending server retries. Partial delivery is a temporary failure of the whole envelope, which requires per-recipient delivery to be idempotent. A circuit breaker counts only backend failures.
- Inbound pipeline, per recipient mailbox, in order: integration webhooks that may drop, defer or pre-decide; ARC check against an explicit allow-list of trusted sealers (fail closed: an empty list trusts nobody, because anyone can produce a valid seal); deterministic header rules; a call to the spam filter's HTTP scan endpoint with the raw message and the SMTP envelope as headers; DKIM/DMARC verdict; after-delivery webhooks. Each step returns continue, retry or drop. The spam verdict is three-valued (undecided, spam, not spam) and later steps are skipped once decided. The application does not interpret the spam score; it maps the filter's named action to an outcome. Two user-visible results: a hard junk flag, and a softer "possibly spam" banner on mail that still reaches the inbox.
- Storage: PostgreSQL holds mailboxes, threads, messages, recipients, labels, contacts and access rows; raw messages are content-addressed blobs with optional offload to object storage; search is a separate full-text engine indexed asynchronously.
- Sharing: access is granted at three levels, mail domain, mailbox and thread, so a shared mailbox is simply a mailbox with several access rows and a thread can be shared with a colleague without sharing the mailbox.
- Outbound: a draft is a message row. Sending composes the MIME, signs it with DKIM (keys per domain in the database), stores the blob, and a background worker delivers either directly to the recipient's mail exchangers (resolve, sort by priority, try each, retry failed recipients on the next host) or through a relay. Resolved addresses are checked against private and loopback ranges because the recipient's DNS is attacker-controlled. Delivery status is stored per recipient.
- It deliberately offers no IMAP or POP3. The web client and API are the only way in.
- AI: thread summary, a compose helper and automatic labelling, the last being a classifier that picks from the mailbox's existing labels.

**What a JMAP client needs (RFC 8620/8621).** [M except where marked] One HTTPS session endpoint that lists accounts and capabilities; one API endpoint that takes a batch of method calls where later calls can reference earlier results; a small set of object types (Mailbox, Thread, Email, EmailSubmission, Identity, SearchSnippet, VacationResponse); get / changes / set / query / queryChanges on each; an opaque state string per type so a client asks "what changed since state X" instead of rescanning; blob upload and download endpoints; and a push channel (event stream or WebSocket) that only says "type T changed for account A". Labels and folders are both "mailboxes" and a message can be in several. Flags are keywords such as `$seen`, `$draft`, `$flagged`. A draft is an Email with `$draft` in the Drafts mailbox. Sending is creating an EmailSubmission that points at an Email. **Undo send is in the standard:** EmailSubmission has an `undoStatus` of pending, final or canceled; a client cancels by setting it to canceled while pending and gets a `cannotUnsend` error if too late; delayed sending uses the FUTURERELEASE SMTP extension. [V in RFC 8621 text]

**What makes deliverability hard.** [M; widely documented but not re-fetched today]
- The receiving side judges the sending IP and domain, not the software. A new IP has no reputation; home and many cloud ranges are on blocklists by policy.
- Outbound port 25 is commonly blocked on consumer and small-business lines, and a matching forward and reverse DNS name (which only the ISP or host can set) is expected.
- SPF, DKIM and DMARC must all be present and aligned; large mailbox providers have required this for bulk senders since 2024 along with one-click unsubscribe and low complaint rates.
- Forwarding and mailing lists break SPF and often DKIM; ARC exists to carry the original verdict, and is only useful when the receiver trusts the sealer.
- Operational duties: bounce handling, retry queues over days, feedback loops, DMARC report reading, key rotation, TLS, and never becoming an open relay or a backscatter source.
- Inbound needs a public address reachable on port 25 all the time, and a secondary or a sender that retries.

### What makes them good

- Messages' split (dumb SMTP edge, all policy in the application, temporary failure by default) is small, testable and safe.
- Its three-valued verdict and "the filter decides, we map the action" keeps spam policy out of our code.
- mox proves a permissive, single-binary server with sane defaults and a JSON API exists.
- JMAP's state strings and batched calls are the right client protocol shape even if we never implement the RFC fully; modelling our API on it keeps the door open to standard clients.
- Stalwart shows the ceiling: one process, one store, every protocol.

### What they get wrong (for us)

- Stalwart and the classic bundles assume the mail server owns the mailbox and everything else is a client. Then the assistant, approvals and ledger have to live outside and reconcile, and the licence is AGPL.
- Messages needs a separate search cluster, an identity server and object storage; too heavy for one machine.
- mox has no JMAP, calendar or Sieve, is pre-1.0, and its storage is its own, so shared mailboxes and approvals would again be bolted on.
- Roundcube-era webmail talks IMAP per request and has no concept of shared ownership or drafts-awaiting-approval.
- Nobody solves the India small-office reality for you: no static IP, port 25 closed, zero budget.

### Minimum original design (prose; about 4,500 lines of Python excluding the webmail UI, which is roughly 4,000 lines of React)

Three stages, each usable alone.

1. **Connector stage (about 1,200 lines).** Most customers already have mail somewhere. Sync an existing mailbox over IMAP with the standard library, send through that provider's submission port, and store normalised messages in our tables. This gives the assistant, approvals and ledger with no deliverability work at all. It is how the AI clients studied in section 4 operate.
2. **Own mailbox stage (about 2,300 lines).**
   - Tables: `mail_domain` (with DKIM keys), `mailbox`, `mailbox_access` (user or group, role), `thread`, `email` (headers, parsed body, keywords array, blob id, thread id), `email_mailbox` (many-to-many so labels work the JMAP way), `blob` (content-addressed, on local disk), `submission` (envelope, send_at, undo status, per-recipient delivery status), `filter_rule`.
   - Inbound: a small asyncio SMTP listener built on the Apache-licensed library, stateless, calling our delivery function in process. Pipeline of steps returning continue / retry / drop: recipient check, size and parse limits, authentication verdicts (permissive DKIM and SPF libraries plus DNS), optional call to an unmodified spam-filter service, our rules, store, index, emit the same real-time event the chat uses. Temporary failure unless on an explicit permanent list.
   - Outbound: compose with the standard library, DKIM-sign, write the submission with a send-at time, and let one worker deliver through a configured relay by default; direct-to-MX only as an opt-in for customers with a clean static IP and reverse DNS.
   - Threading by the References and In-Reply-To headers with a normalised-subject fallback. Search with the same PostgreSQL full-text setup as chat.
   - Filters: store rules as structured conditions and actions (a subset of what Sieve expresses) and offer Sieve import/export later through the MIT parser library rather than writing an interpreter.
   - API shaped like JMAP (state token per type, changes-since, batched set) without claiming conformance.
3. **Standards stage (optional, later).** A JMAP-conformant endpoint; calendar as iCalendar objects with invitation handling over email (iTIP) using the BSD library; CalDAV/CardDAV only if phone sync is demanded.

DNS helper: generate and verify the SPF, DKIM, DMARC, MX and MTA-STS records and show a pass/fail self-check, as mox and Messages both do.

### Beyond them

- The same proposal-and-ledger path for a human's scheduled send, an assistant's draft and an automatic rule action.
- Shared mailbox with assignment, internal notes on a thread that are chat messages (never sent), and collision warning when two people draft a reply.
- A per-recipient delivery timeline (queued, relayed, bounced, DMARC-failed) in plain language.
- Spam verdict explanations the assistant can read and summarise, with user "junk / not junk" feeding reputation per sender.

---

## 4. AI on top

### How it works

**Triage rules.**
- inbox-zero (README only; licence forbids more): the user writes rules "in plain English"; the product pre-drafts replies in the user's style and can block cold email. From older public docs [M, unverified today]: each rule combines an AI instruction with optional static conditions (from, to, subject, body) and a list of actions (label, archive, draft reply, reply, forward, mark read, call a webhook), and each rule can be set to run automatically or to wait for confirmation.
- agents-from-scratch (MIT; source read): a first model call classifies each incoming email into exactly three outcomes, respond, notify or ignore, using a prompt that holds the user's background and triage preferences. "Respond" goes to a drafting agent with tools; "notify" pauses and shows the email to the human, who may ignore it or reply with an instruction; "ignore" ends. Preferences are plain text stored in a memory store and rewritten by a model call whenever the human edits or rejects something, so the rules learn.
- Zero (MIT; source layout and its workflow README read): a workflow engine where a workflow is a named list of steps, each with an enable flag, a condition, an action and an error policy (continue, fail, retry), all sharing a context object. The default workflow decides whether a thread deserves a draft, generates it, and saves it to the provider's Drafts. Labelling and summaries are other steps. Mail stays with the upstream provider; the app keeps a per-user synced copy.
- Messages (MIT): classification is constrained to the mailbox's existing labels, which keeps output checkable.

**Holding drafts for approval.**
- agents-from-scratch: tool calls are split into two sets. Calls in the human-review set (send email, schedule meeting, ask the user a question) raise an interrupt before executing. The interrupt carries the proposed action and its arguments, a rendered description, and which responses are allowed: accept, edit (human changes the arguments, then it runs), ignore, or respond (free-text feedback returned to the agent as the tool result so it tries again). The graph's state is checkpointed, so the pause can last days. Other tools run without asking.
- Mattermost agents plugin (Apache-2.0; docs read): in shared channels every tool call has four roles. The initiator is whoever invoked the agent; the approver is always the initiator, never another member or an admin; the executor is the identity whose credentials run the tool, by default the initiator's, so the agent can never do more than the person who asked; observers see that a tool ran but not its arguments or private results by default. Admins set a policy per tool; tools that declare themselves read-only default to auto-run in direct messages, everything else asks each time; unreviewed tools are flagged.
- JMAP: the standard already separates "an Email exists in Drafts" from "an EmailSubmission was created", and gives submissions a pending state that can be cancelled. Approval fits between those two objects without inventing anything.

**Undo send.** A delay between "send pressed" and "handed to the wire", with a cancel during the delay. JMAP expresses it as `undoStatus`; classic clients do it with a client-side timer, which loses the message if the tab closes. Server-side hold is the correct form.

**AI chat participants.** The Mattermost plugin: mention the agent in a channel or talk in a direct message; summarise thread, unread messages or channel; keyword plus semantic search over messages (it requires the vector extension for PostgreSQL); the agent exposes the chat itself as a tool server so external assistants can read and post with the signed-in user's permissions. [V from README and docs]

### What makes them good

- Three-way triage is small enough to evaluate and explain.
- "Respond with feedback" as a fourth approval option, beside accept, edit and reject, is what makes approval a conversation rather than a gate.
- Executor equals initiator closes the privilege-escalation hole where a bot with broad rights acts for a user with narrow ones.
- Learning preferences from edits means the rule set improves without a settings page.

### What they get wrong

- Approval state lives in an agent framework's checkpoint or a chat post, not in a durable, auditable record tied to the exact bytes that will be sent.
- Nothing binds the approval to the content: edit after approve is possible in most flows.
- Plain-English rules are unpredictable; there is no way to see why a rule fired or to test it against last month's mail.
- Incoming email is untrusted text fed straight to a model that holds send tools. None of the projects examined documents a defence beyond approval.
- inbox-zero's licence makes it unusable for a product that is sold.

### Minimum original design (prose; about 1,200 lines)

- `proposal` table used by chat and email alike: kind (send email, post message, apply label, archive, forward, edit, delete), target, payload, payload hash, proposer (assistant or rule or human), initiator (the human on whose behalf), required approver, status (pending, approved, rejected, expired, executed, cancelled), hold-until time, feedback text.
- State machine: propose, then approve / edit (creates a new proposal that supersedes the old one) / reject / respond-with-feedback, then execute. Each transition appends a ledger entry containing the payload hash and the previous entry's hash. The executor refuses to run if the payload hash differs from the approved one.
- Execution always goes through the submission or message outbox with a hold-until time. A human pressing send is a proposal that is auto-approved with a short hold; that is undo send. An assistant draft is the same row waiting for a person.
- Triage rule = structured part plus optional instruction: deterministic conditions (sender, domain, mailbox, has attachment, thread state) evaluated first in SQL; an optional natural-language condition evaluated by a model that must return one of a fixed set of outcomes plus a one-line reason; a list of actions; a mode (propose, or auto for a named list of reversible actions such as label and archive). Never auto for send, forward, delete.
- Dry run: any rule can be replayed against stored mail to show what it would have done.
- Capability rule: the assistant acts with the initiator's permissions, never its own.
- Untrusted content: message bodies are passed to the model as quoted data, tools that send or forward are unavailable in the same call that reads external mail unless a human approval sits between them, and links and addresses in a proposed reply are checked against the thread's participants.
- Summaries are cached per thread or topic against the last message id covered.

### Beyond them

- One approval inbox across chat and email, backed by the ledger, exportable as proof of who approved what text and when.
- Approval bound to a content hash.
- Rule explanations and replay.
- Per-action reversibility classes that decide what may ever run without a person.

---

## 5. Build versus run-unmodified

| Area | Option | What it means | Licence consequence for a sold product (needs a lawyer) | Recommendation |
|---|---|---|---|---|
| Chat | **Build our own**, Zulip-style model, standards-informed | About 3,000 lines of Python plus the React client | Our code, no obligations. Zulip is Apache-2.0, so studying its source is allowed; we still copy nothing. | **Recommended.** Chat for one organisation on one machine is tractable, and approvals and the ledger must sit in the write path. |
| Chat | Run tuwunel (or continuwuity) unmodified, write our own client to the Matrix spec | A Rust service beside ours; we store nothing | Apache-2.0: redistribution allowed with notices. Low risk. | Keep as the fallback if federation or bridges are ever required. Costs: a second store, encryption versus an assistant that must read, approvals outside the server. |
| Chat | Run Mattermost vendor binary | Vendor-compiled build is MIT per its licence file; source builds are AGPL or commercial; enterprise directory is source-available; trademark restricted | Shipping a vendor binary under MIT looks possible on paper but features we need are licence-gated and the name cannot be used freely. | Not recommended. |
| Chat | Run Synapse or Rocket.Chat | AGPL/commercial; MIT core with enterprise carve-out | AGPL obligations on distribution and on network use of modified versions; enterprise parts need a paid agreement. | Avoid. |
| Calls | Run LiveKit unmodified, later | Separate media server | Apache-2.0. | Defer; run unmodified when needed. Do not write a media server. |
| Email, application layer (mailbox store, shared mailboxes, webmail, rules, AI) | **Build our own** on PostgreSQL | About 4,500 lines of Python plus UI | Our code. Libraries used are Apache-2.0, MIT, ISC, BSD or standard library. dkimpy's "BSD-like" wording should be read by the lawyer. | **Recommended.** This is where the product's value and the approval path live. |
| Email, existing mailboxes | **Build a connector** (IMAP in, submission out) first | About 1,200 lines | Standard library only. Avoid the GPL IMAP and JMAP client libraries named in section 1c. | **Recommended as stage 1.** No deliverability problem, works on a laptop. |
| Email, inbound SMTP edge | Build a thin listener on the Apache-licensed asyncio SMTP library | A few hundred lines | Apache-2.0 library. | Recommended for stage 2. Writing the SMTP protocol engine itself would be unreasonable; using a permissive library is not. |
| Email, outbound delivery | Send through a relay by default; direct delivery opt-in | Config, plus a small queue worker | None from us. The relay has its own terms and cost. | Recommended. Direct delivery from a local machine in India will mostly fail (port 25, reverse DNS, reputation). [M] |
| Email, spam filtering | Run rspamd unmodified, talk to it over HTTP | Separate service, optional | Apache-2.0. | Recommended once we accept mail from the internet. |
| Email, full server | Run mox unmodified | One Go binary gives SMTP, IMAP, webmail, JSON API and webhooks | MIT, with small BSD-3 and MPL-2.0 parts noted in its README. Bundling appears allowed with notices. | **The permissive run-unmodified option** if a customer needs IMAP for phone clients. Pre-1.0. |
| Email, full server | Run Stalwart unmodified, talk JMAP | The most complete server: JMAP, IMAP, CalDAV, CardDAV, Sieve | AGPL-3.0 or a paid proprietary licence. Talking to it over a network protocol as a separate program is commonly treated as not making our code a derivative work, but that is exactly the question to put to a lawyer. Distributing it inside our installer brings AGPL duties for that component at minimum; some features need the paid licence. | Do not bundle. Support it as something a customer installs themselves and we connect to by JMAP. |
| Webmail | Build our own in the existing React dashboard | About 4,000 lines | Ours. | Recommended. Roundcube (GPL) and SnappyMail and Bulwark (AGPL) are not embeddable in a sold closed product without their terms applying. |
| Calendar and contacts | Build minimal iCalendar handling with the BSD library; CalDAV later | A few hundred lines to start | BSD-2-Clause. The GPL CalDAV servers would be run-unmodified only. | Defer CalDAV. |
| AI triage and approval | **Build our own** | About 1,200 lines | Ours. inbox-zero must not be used or read: its licence forbids commercial use and use by organisations of five or more without a paid licence. | **Recommended.** |

Short form: build chat; build the email application layer and a connector first; use permissive libraries for the SMTP edge; run rspamd and, where a full server is needed, mox unmodified; treat Stalwart as customer-installed and optional; build the AI approval layer ourselves.

---

## 6. Open questions and unverified items

Open questions
1. Local-first on one machine cannot receive internet mail without a public, always-on address on port 25 and an MX record. Is stage 1 (connect existing mailboxes) acceptable as the first release, with own-domain mail later through a small public relay host?
2. Zero budget versus outbound reputation: which relay is acceptable, and who pays when the free allowance ends? Not researched.
3. Do customers need phone mail clients (which implies IMAP or JMAP and pushes toward running mox or Stalwart) or is web plus our own mobile view enough?
4. Is federation or bridging to other chat systems a real requirement? If not, Matrix buys nothing.
5. Indian-language search quality: the `simple` text configuration is a safe default but has no stemming. Needs a test on real data.
6. Retention and legal hold rules for India (and whether email records fall under any sector rule) were not researched.
7. Lawyer questions: AGPL and a separately running, unmodified server shipped alongside; the "BSD-like" licence of the DKIM library; MPL-2.0 libraries inside a closed product; the Mattermost MIT-binary clause; use of any project's name in our marketing.

Unverified or from memory (marked [M] above)
- Matrix internals (event graph, state resolution, sync tokens, power levels, application services) come from prior knowledge of the public spec; the spec was not re-read today.
- Mattermost and Rocket.Chat architecture descriptions are from prior knowledge of public docs.
- Zulip: message-id ordering, the bot types and the flags detail are from memory; the events, unread, search, local echo and notification mechanisms were read in the docs today.
- inbox-zero rule structure beyond "plain English rules" and "pre-drafts replies" is from memory of older docs.
- All deliverability statements, including port 25 blocking in India and the 2024 bulk-sender requirements.
- RFC numbers other than 8621 were not individually checked; several were copied from the Stalwart README.
- Roundcube's exact licence wording (possible exceptions), the Rocket.Chat free-tier limits, Prosody's licence, and the licences of kurrier-org/kurrier and hcengineering/platform's components were not checked.
- Zulip's LICENSE was confirmed as Apache-2.0 by API and file head only; the repository was not searched for separately licensed subdirectories.
- Stalwart's per-file licence split (which files are AGPL and which enterprise-only) was not examined, since that would require reading source.
- Line-count estimates for our own design are rough judgements, not measurements.
- mox, tuwunel and LiveKit were not run; "run unmodified" verdicts rest on READMEs and licences only.
