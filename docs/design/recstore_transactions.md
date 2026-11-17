# Per-record state with multi-record transactions (KAN-64)

## Problem
Scheduler, interview-session and ESIGN state were one JSON document each, capped at 1 MiB, loaded, decrypted and rewritten whole
by every request. One flood (or one busy organisation) fills the file for everybody; the cap that protects the file is the limit
for the whole deployment. Tokens were found by scanning the document.

## Decision
* One sealed file per record (`velaris/agentkit/recstore.py`: 64 KiB per record, key outside VELARIS_DATA, bound to its
  collection and key). The number of records is no longer limited by the document cap.
* `velaris/agentkit/recdoc.py` (`RecDoc`) keeps the `load()` / `update(fn)` shape of JsonState, so the agents' logic is unchanged:
  `d["bookings"][id]`, `d["tokens"][hash]`, `del`, in-place mutation. `update` writes what `fn` changed as ONE transaction.
* ESIGN (`onboarding_shard.ShardedStore`, same methods as `Store`): one record per request (its signers, evidence and tokens are
  parts of that one record, so a request is atomic by construction) plus a token index hash -> request, updated in the same
  transaction, so a signing link is found with one read.

## Transaction (write-ahead journal)
1. take the agent-wide cross-process lock; replay any journal found (below);
2. run `fn` on a view; nothing is written while it runs (raising = nothing happened);
3. refuse now any record over the size cap (a journal that can never be applied would wedge the store);
4. write the JOURNAL: all changed records, sealed, temp + fsync + rename (the commit point);
5. apply the records one by one (each is itself an atomic rename); 6. remove the journal.

Crash argument: before 4 completes there is no journal, so the old records are untouched (a half-written temp file is ignored
and never renamed into place). After 4 the journal is whole; whoever takes the lock next (a writer) or finds a journal while
reading (a reader waits for the lock) replays it; applying is idempotent. A record file is never torn because every write is an
atomic rename. So after `kill -9` at any point a booking, its token and its draft are all new or all old.

Readers take no lock unless a journal is waiting, so reads do not queue behind writers.

## Concurrency
Writers of one agent queue on one lock (a booking must be checked against every other booking of the org, so one lock per org
would be the finest correct grain; the agent-wide lock is the simple version). Two-process test: no lost update.

## Migration (versioned, inside the key-signed window)
First access folds the old file in: it is read by JsonState (sealed files as usual; a plaintext file only while the key-signed
migration window of `velaris/core/vault.py` is open, otherwise PlaintextRefused = fail closed), every record is written, the marker
record `_meta/migrated` is written LAST, then the old file is deleted (it would otherwise keep personal data that erasure no
longer reaches). A crash repeats the idempotent copy, or only the delete. Record schema_version/migration hooks are RecordStore's.

## Limits (ponytail)
* Iterating a collection (all bookings of an org) reads every record of it. Add a per-org index record when it gets hot.
* One writer at a time per agent. Per-org locks if throughput needs it.
* Interview events (hash-chained log) keep their own append-only files; only the session record changed.
