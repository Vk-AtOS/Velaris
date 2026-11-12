"""Velaris company email: a connector to existing mailboxes, our own mailbox store, inbound and
outbound with approval and undo-send, rules, and an assistant that reads and drafts but never sends.

Modules
  common      MailError, audit() (ids and hashes only), clock type
  sanitize    HTML allowlist sanitiser (stdlib), html to text
  mime        parse with email.policy.default into a safe message model; build outgoing MIME
  db          sqlite schema, locking, content-addressed attachment blobs
  store       mailboxes, folders, threads, messages, labels, search (FTS5 or LIKE), attachments
  admin       org settings, delegation, aliases, quota, legal hold, retention, export, erasure
  connector   IMAP (TLS only) sync and SMTP submission over injected transports
  dnsauth     SPF and DMARC from the RFCs over an injected resolver; Authentication-Results
  dkim        DKIM signing and verification (rsa-sha256, ed25519-sha256)
  spam        transparent weighted rules
  smtp        pure SMTP receive state machine (no sockets)
  inbound     delivery pipeline and the asyncio listener (python3.11 -m velaris.mail.inbound)
  outbound    drafts, submissions, approval requirements, undo-send, relay
  rules       per-user rules, vacation responder, loop protection
  assistant   summaries, action items, triage, drafts: through velaris.intel.llm, text fenced
  api         the HTTP router mounted by velaris.api.app

Trust rules: identity comes only from the Caller; every record carries the organisation; email
text is untrusted (screened and fenced before any model reads it); a model never sends anything.
"""
