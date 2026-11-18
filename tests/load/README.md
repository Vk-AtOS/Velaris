# Velaris load results

`python3.11 tools/load_velaris.py --users 50 --seconds 20 [--workers N]` starts the API on loopback with throw-away credentials,
drives signed concurrent users against `/health`, `/agents`, `/trace/verify` and `/mail/mailboxes`, and writes
`results/velaris-<UTC>.json` (requests, errors, throughput, p50/p95/p99, start-up and first-catalogue time, trace entries written
and whether `/trace/verify` still answers afterwards).

Read the numbers for what they are: ONE machine, the generator and the server on the same CPU, no Redis, no Postgres, no network
hop between the gateway and Velaris, and (for the file committed here) a laptop that was running a dozen other jobs. They are a
regression baseline and a design-limit measurement. The acceptance run (50 and then 1000 users, against the real deployment with
the real gateway in front) needs the target environment: run the same tool there (`--workers` as configured) and attach the file.

Known findings from the first run (50 users, 1 worker, loaded laptop): start-up 37 s because every agent is imported before the
first request (4.7 s of CPU alone); the first `/agents` call builds the catalogue (15 s here); `/agents` then costs about 76 ms
of CPU per call to serialise the 346-agent catalogue (13 requests/s), and should be cached as bytes or paginated before it is
shown to many users at once.
