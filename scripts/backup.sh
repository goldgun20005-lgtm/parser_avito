#!/usr/bin/env bash
# backup.sh — безопасный онлайн-бэкап Avito Parser (см. docs/BACKUP_AND_RESTORE.md)
# Использует sqlite3 .backup (консистентно даже при работающем парсере).
# Запуск по cron, например:  0 */6 * * * /opt/parser_avito/scripts/backup.sh >> logs/backup.log 2>&1
set -euo pipefail

APP="${APP_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
DST="$APP/backups"
TS="$(date +%F_%H-%M-%S)"
KEEP="${KEEP:-14}"   # сколько копий хранить

mkdir -p "$DST"

# 1) База просмотренных (консистентная копия)
if [ -f "$APP/database.db" ]; then
  sqlite3 "$APP/database.db" ".backup '$DST/database_$TS.db'"
  sqlite3 "$DST/database_$TS.db" "PRAGMA integrity_check;" | head -1
else
  echo "WARN: $APP/database.db не найден"
fi

# 2) Конфиг, секреты, cookies, результаты (архив)
tar czf "$DST/state_$TS.tar.gz" -C "$APP" \
  $( [ -f "$APP/config.toml" ] && echo config.toml ) \
  $( [ -f "$APP/.env" ] && echo .env ) \
  $( [ -d "$APP/storage" ] && echo storage ) \
  $( [ -d "$APP/result" ] && echo result ) 2>/dev/null || true

# 3) Ротация
ls -1t "$DST"/database_*.db 2>/dev/null | tail -n +$((KEEP+1)) | xargs -r rm --
ls -1t "$DST"/state_*.tar.gz 2>/dev/null | tail -n +$((KEEP+1)) | xargs -r rm --

echo "OK: backup $TS -> $DST"
