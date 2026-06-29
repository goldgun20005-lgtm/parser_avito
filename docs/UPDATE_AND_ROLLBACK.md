# UPDATE_AND_ROLLBACK — Обновление и откат

> Статус: технический раздел готов. Принцип: **не использовать `latest` вслепую** —
> закреплять конкретный release-tag / commit SHA / Docker digest.

## Почему не `latest`
- Issue **#293**: публичный образ `ghcr.io/duff89/parser_avito:latest` устарел (≈3.2.07).
- Свежие версии (3.2.13–3.2.15) часто содержат фиксы блокировок/уведомлений, но и регрессии
  (см. свежие #306/#307). Поэтому обновление — через staging и закреплённую версию.

## Стратегия версионирования
- Работать на форке (`goldgun20005-lgtm/parser_avito`), ветка `claude/gracious-gauss-rnq17p`.
- Для продакшена фиксировать:
  - **commit SHA** (например текущий `c6e373c` = 3.2.15) или git-tag;
  - собранный **Docker-образ** тегировать своей версией (`parser_avito:3.2.15`) и хранить digest.

## План обновления (по шагам)
1. **Проверить новый release** upstream и его дату.
2. **Прочитать changelog** (`docs/CHANGELOG.md`) и release notes.
3. **Проверить Issues** новой версии (нет ли свежих критичных, как #306/#307).
4. **Сделать backup** (`BACKUP_AND_RESTORE.md`): `database.db`, `config.toml`, `storage/`.
5. **Развернуть на staging** (отдельный каталог/сервер/compose-проект) из нужного commit/tag.
6. **Smoke test** (Уровни 2–4 из `TEST_REPORT.md`): парсинг, дедуп, уведомления.
7. **Проверить Telegram/VK** на staging.
8. **Проверить SQLite** (миграции/целостность) на копии БД.
9. **Обновить production**: переключить на новый образ/код, `up -d`.
10. **Проверка после обновления** (чек-лист ниже).
11. При проблеме — **rollback**.

## Обновление (Docker, локальная сборка)
```bash
cd /opt/parser_avito
# зафиксировать текущую версию для отката
git rev-parse HEAD > .last_good_commit
# подтянуть нужную версию
git fetch origin && git checkout <tag-или-commit>
# backup перед сборкой
./scripts/backup.sh
# собрать и перезапустить
docker compose build
docker compose up -d
docker compose logs -f --tail=100
```

## Откат (rollback)
```bash
cd /opt/parser_avito
git checkout "$(cat .last_good_commit)"
# при необходимости восстановить БД из бэкапа (см. BACKUP_AND_RESTORE.md)
docker compose build && docker compose up -d
```
> Если использовали закреплённый Docker digest — откат = вернуть прежний образ:
> `image: parser_avito@sha256:<previous-digest>` и `up -d`.

## Чек-лист после обновления
- [ ] Контейнер `running`, нет рестарт-петли (`docker inspect RestartCount`).
- [ ] В логах есть `Запуск AvitoParse v<новая версия>`.
- [ ] Один проход извлекает объявления (нет сплошных `ValidationError`).
- [ ] Уведомление приходит (тестовое/реальное).
- [ ] Повторный проход не дублирует уведомления (дедуп жив).
- [ ] `database.db`/`result`/`storage` на месте (данные не потеряны).
- [ ] Нет роста ошибок 403/429 относительно прошлой версии.

## Автообновления
- **Не рекомендуется** автоматически тянуть upstream в production без ручной проверки
  (риск регрессий — пример #306/#307). Если нужны авто-обновления — только до staging + ручной promote.
