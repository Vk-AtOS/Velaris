#!/usr/bin/env bash
# Nightly Velaris backup (VEL-32): snapshot, encrypt, send off-site, keep the signed trace head apart, prune.
# Run by deploy/systemd/velaris-backup.timer (VPS) or by cron / a compose host's timer. Settings (environment):
#   VELARIS_DATA          data directory (default /var/lib/velaris; on compose: the velaris_data volume's _data path)
#   BACKUP_DIR            local archive directory (default /var/backups/velaris), RETAIN_DAYS local copies (default 14)
#   AGE_RECIPIENT         age public key: the archive is encrypted before it leaves the host. The private key stays OFF the host.
#   VELARIS_BACKUP_REMOTE rclone destination for archives, e.g. s3remote:bucket/velaris (unset = local only)
#   VELARIS_ANCHOR_REMOTE rclone destination for the signed trace head, kept apart from the archives (different prefix or
#                         account): restoring an old archive cannot also restore an old head unseen.
#   PYTHON                interpreter (default python3.11)
# Exit 0 = archive written (and sent, when a remote is set). A plaintext archive is never sent off-site.
set -euo pipefail
DATA="${VELARIS_DATA:-/var/lib/velaris}"; OUT="${BACKUP_DIR:-/var/backups/velaris}"; KEEP="${RETAIN_DAYS:-14}"
PY="${PYTHON:-python3.11}"; HERE="$(cd "$(dirname "$0")" && pwd)"; STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$OUT"; chmod 700 "$OUT"

"$PY" "$HERE/velaris_backup.py" backup --data "$DATA" --out "$OUT" --lock-stores
ARCH="$(ls -t "$OUT"/velaris-data-*.tar.gz | head -1)"
echo "$(date -u +%FT%TZ) archive $(basename "$ARCH") ($(stat -c %s "$ARCH" 2>/dev/null || stat -f %z "$ARCH") bytes)"

if [[ -n "${VELARIS_BACKUP_REMOTE:-}" ]]; then
    [[ -n "${AGE_RECIPIENT:-}" ]] || { echo "ERROR: VELARIS_BACKUP_REMOTE is set but AGE_RECIPIENT is not: refusing to send a plaintext archive" >&2; exit 1; }
    age -r "$AGE_RECIPIENT" -o "$ARCH.age" "$ARCH"
    rclone copy --immutable "$ARCH.age" "$VELARIS_BACKUP_REMOTE"
    rclone copy --immutable "$ARCH.sha256" "$VELARIS_BACKUP_REMOTE"
    rm -f "$ARCH.age"
    echo "$(date -u +%FT%TZ) sent encrypted to $VELARIS_BACKUP_REMOTE"
fi

if [[ -n "${VELARIS_ANCHOR_REMOTE:-}" && -s "$DATA/trace.head" ]]; then
    cp "$DATA/trace.head" "$OUT/trace.head.$STAMP"
    rclone copy --immutable "$OUT/trace.head.$STAMP" "$VELARIS_ANCHOR_REMOTE"
    rm -f "$OUT/trace.head.$STAMP"
    echo "$(date -u +%FT%TZ) trace head copied to $VELARIS_ANCHOR_REMOTE"
fi

find "$OUT" -name 'velaris-data-*.tar.gz*' -mtime +"$KEEP" -delete
