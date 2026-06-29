# BACKUP_AND_RESTORE — Резервное копирование и восстановление

> Статус: технический раздел готов; расписание/хранилище уточняются по ответам (RPO/RTO).
> ⚠️ Простое `cp database.db` во время работы парныера небезопасно — SQLite может быть в середине
> записи. Используйте `sqlite3 .backup` (онлайн-бэкап) или копируйте при остановленном процессе.

## Что копировать

| Объект | Путь | Критичность | Примечание |
|---|---|---|---|
| Память просмотренных | `database.db` | 🔴 высокая | потеря → массовые повторные уведомления |
| Конфигурация | `config.toml` (+`.env`) | 🔴 высокая | содержит секреты — шифровать/хранить отдельно |
| Cookies | `storage/*.json` | 🟠 средняя | потеря → новый логин/покупка cookies |
| Результаты | `result/*.xlsx` | 🟠 средняя | по ценности данных |
| Пользовательские фильтры | в `config.toml` | 🔴 | часть конфига |
| Логи | `logs/*.log` | 🟢 низкая | обычно не бэкапят |

## Команда онлайн-бэкапа SQLite (безопасно при работающем парсере)
```bash
# создаёт консистентную копию даже во время записи
sqlite3 /path/to/database.db ".backup '/path/to/backups/database_$(date +%F_%H-%M-%S).db'"
# проверка целостности копии
sqlite3 /path/to/backups/database_*.db "PRAGMA integrity_check;"
```

## Скрипт бэкапа (пример, кандидат для `scripts/backup.sh`)
```bash
#!/usr/bin/env bash
set -euo pipefail
APP=/opt/parser_avito           # каталог проекта на сервере
DST=/opt/parser_avito/backups
TS=$(date +%F_%H-%M-%S)
mkdir -p "$DST"
sqlite3 "$APP/database.db" ".backup '$DST/database_$TS.db'"
tar czf "$DST/config_$TS.tar.gz" -C "$APP" config.toml .env storage 2>/dev/null || true
# ротация: хранить 14 последних
ls -1t "$DST"/database_*.db | tail -n +15 | xargs -r rm --
ls -1t "$DST"/config_*.tar.gz | tail -n +15 | xargs -r rm --
```
> Для Docker: либо запускать `sqlite3 .backup` на хосте по пути volume, либо
> `docker exec avito sqlite3 /app/database.db ".backup '/app/backups/...'"` (нужен sqlite3 в образе).

## Расписание (предложение, уточнить по RPO)
- `database.db` — каждые 6–12 часов (cron).
- `config.toml`/`.env`/`storage` — при изменении + раз в сутки.
- Внешнее хранилище (S3/Backblaze/Google Drive) — по желанию (см. опросник).

Пример cron:
```
0 */6 * * * /opt/parser_avito/scripts/backup.sh >> /opt/parser_avito/logs/backup.log 2>&1
```

## Ротация и проверка
- Хранить N последних копий (пример: 14). Старые удалять.
- Регулярно проверять `PRAGMA integrity_check;` на копии.
- Бэкап секретов хранить **отдельно** и в зашифрованном виде.

## Восстановление
```bash
# 1. Остановить парсер
docker compose down            # или systemctl stop parser_avito
# 2. Восстановить БД
cp /opt/parser_avito/backups/database_YYYY-MM-DD_HH-MM-SS.db /opt/parser_avito/database.db
sqlite3 /opt/parser_avito/database.db "PRAGMA integrity_check;"
# 3. Восстановить конфиг/cookies при необходимости
tar xzf /opt/parser_avito/backups/config_YYYY-...tar.gz -C /opt/parser_avito
# 4. Запустить
docker compose up -d           # или systemctl start parser_avito
```

## Тест восстановления (обязателен перед продакшеном)
1. Снять бэкап, развернуть в отдельном каталоге, запустить с тем же `config.toml`.
2. Убедиться, что дедуп работает (не шлёт старые объявления) и парсер стартует.
3. Зафиксировать фактический RTO (время восстановления) — сверить с требуемым.

## RPO / RTO
- **RPO** (допустимая потеря данных) и **RTO** (время восстановления) — определить из опросника (G.45).
- При частоте бэкапа 6 ч RPO ≈ до 6 часов «памяти просмотренных» (на практике приведёт лишь к
  повторным уведомлениям, не к потере результатов, если Excel бэкапится тоже).
