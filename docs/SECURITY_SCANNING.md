# Secret scanning and the gitleaks baseline (KAN-203)

CI runs gitleaks (`.github/workflows/ci.yml`, job `secrets`) with `.gitleaks.toml`, which extends the default rules.

## Baseline

`.gitleaksignore` (repo root, read automatically by gitleaks) lists the fingerprints of findings that were reviewed on
22 Nov 2026. All of them are invented test fixtures in `velaris/tests/`; none is a live secret and none is
a service-issued credential. Fingerprints are bound to a commit, file, rule and line, so a secret added in any new
commit is still reported and fails the scan.

## Owner decision (22 Nov 2026)

Credentials found in the history of the Vk-AtOS repositories are test-only. They will not be rotated and history
will not be rewritten before the sale.

## Rules

- Never add a finding that is a real secret to `.gitleaksignore` or `.gitleaks.toml`: remove it from the tree.
- Prefer building fixtures at run time or reading env vars over literals, even in tests.
- To check the full history locally, run gitleaks v8.30.1 (the version used for the baseline) with `.gitleaks.toml`.
