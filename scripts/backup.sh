#!/usr/bin/env bash
# Daily ERP backup: database + uploaded files, copied somewhere other than the server.
#
#   SITE=erp.ubcsolar.com BACKUP_DEST=/mnt/offsite/erp scripts/backup.sh
#   SITE=erp.ubcsolar.com BACKUP_DEST=gdrive:ubc-solar-erp-backups scripts/backup.sh   (rclone remote)
#
# Run it daily from cron as the bench user, e.g.
#   30 3 * * * SITE=... BACKUP_DEST=... /path/to/UBC-Solar-ERP/scripts/backup.sh >> ~/erp-backup.log 2>&1
#
# Optional: SLACK_WEBHOOK_URL posts a message to the maintainers' channel if the backup fails.
# KEEP_DAYS (default 30) is how long old backups are kept at the destination.

set -euo pipefail

BENCH="${BENCH:-$HOME/frappe-bench}"
SITE="${SITE:?Set SITE to the ERP site name}"
DEST="${BACKUP_DEST:?Set BACKUP_DEST to a folder or an rclone remote (remote:path)}"
KEEP_DAYS="${KEEP_DAYS:-30}"

fail() {
	echo "Backup FAILED: $1" >&2
	if [[ -n "${SLACK_WEBHOOK_URL:-}" ]]; then
		curl -fsS -X POST -H 'Content-type: application/json' \
			--data "{\"text\":\":warning: ERP backup failed on $(hostname): $1\"}" "$SLACK_WEBHOOK_URL" >/dev/null || true
	fi
	exit 1
}
trap 'fail "line $LINENO"' ERR

cd "$BENCH"
bench --site "$SITE" backup --with-files >/dev/null

BACKUP_DIR="sites/$SITE/private/backups"
latest_db=$(ls -t "$BACKUP_DIR"/*-database.sql.gz | head -1)
prefix="${latest_db%-database.sql.gz}"
files=("$prefix"-*)
[[ ${#files[@]} -ge 1 ]] || fail "no backup files were produced"

if [[ "$DEST" == *:* && "$DEST" != /* ]]; then
	command -v rclone >/dev/null || fail "BACKUP_DEST looks like an rclone remote but rclone isn't installed"
	for f in "${files[@]}"; do rclone copy "$f" "$DEST"; done
	rclone delete --min-age "${KEEP_DAYS}d" "$DEST" || true
else
	mkdir -p "$DEST"
	cp "${files[@]}" "$DEST"/
	find "$DEST" -type f -mtime +"$KEEP_DAYS" -delete
fi

echo "Backup OK: $(basename "$prefix") -> $DEST (${#files[@]} files)"
