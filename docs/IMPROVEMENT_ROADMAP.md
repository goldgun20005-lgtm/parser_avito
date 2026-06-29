# IMPROVEMENT_ROADMAP — Дорожная карта улучшений

> Приоритеты: **P0** (критично/данные/безопасность) → **P1** (стабильность) →
> **P2** (архитектура) → **P3** (продуктовые функции). Для каждого пункта: проблема,
> решение, затрагиваемые файлы, сложность, риск, эффект.

## P0 — критические

### ✅ P0.1 Потеря данных и дубли из-за порядка notify→save (#300) — СДЕЛАНО
- **Было:** `notify_many` и `__save_viewed` шли до записи Excel (в конце ссылки); сбой → потеря/дубли.
- **Сделано:** порядок изменён на **save_result → notify → mark_viewed**, сохранение перенесено
  на каждую страницу. Гарантия at-least-once (дубль при сбое, но не потеря).
- **Файлы:** `parser_cls.py`. Проверено: статическая проверка порядка + smoke-тест.

### ✅ P0.2 Дедуп без UNIQUE → рост БД — СДЕЛАНО
- **Сделано:** `PRIMARY KEY (id, price)`, `INSERT OR IGNORE`, `PRAGMA journal_mode=WAL`,
  авто-миграция старых БД с дедупом строк.
- **Файлы:** `db_service.py`. Проверено smoke-тестом (4→2 строки, PK, WAL).

### ✅ P0.3 Секреты в git/`config.toml` — СДЕЛАНО
- **Сделано:** `load_config.py` читает секреты из переменных окружения (`AVITO_*`), которые
  переопределяют `config.toml`. Расширен `.gitignore` (`.env`, `storage/`, `database.db`, `result/`,
  `logs/`, `backups/`, `venv/`, `__pycache__/`). `config.toml` остаётся в репо БЕЗ реальных секретов
  (чтобы не ломать релизный пайплайн), реальные значения — в `.env`/окружении.
- **Файлы:** `load_config.py`, `.gitignore`, `.env.example`, `config.example.toml`. Проверено smoke-тестом.

### P0.4 Невозможность понять, что парсер «встал»
- **Проблема:** нет healthcheck/heartbeat; зависший процесс выглядит «живым».
- **Решение:** writeheartbeat-файл/метрику последнего успешного цикла + HEALTHCHECK в Docker; алерт при простое.
- **Файлы:** `parser_cls.py`, `Dockerfile`, `docker-compose`. См. `MONITORING.md`.
- **Сложность:** средняя. **Риск:** низкий. **Эффект:** высокий.

### P0.5 Неконтролируемый рост логов в Docker
- **Проблема:** нет ограничения json-логов Docker (loguru-файл ротируется, а stdout — нет).
- **Решение:** `logging: max-size/max-file` в compose; volume для `logs/`.
- **Файлы:** `docker-compose`. **Сложность:** низкая. **Эффект:** средний.

## P1 — стабильность

| # | Проблема | Решение | Файлы | Статус |
|---|---|---|---|---|
| P1.1 | Нет graceful shutdown (SIGTERM не доходит) | `exec python` в entrypoint, `init: true`, обработчик SIGTERM/SIGINT → `stop_event`, прерываемые паузы | `entrypoint.sh`, `parser_cls.py`, `docker-compose.prod.yml` | ✅ СДЕЛАНО |
| P1.2 | Ретраи без backoff/jitter | экспоненциальный backoff + jitter (cap 60с) в `HttpClient._backoff_delay` | `parser/http/client.py` | ✅ СДЕЛАНО |
| P1.5 | Хрупкость Pydantic (#306/#307) | `extra="ignore"` + парсинг объявлений по одному (битые пропускаются) | `models.py`, `parser_cls.py` | ✅ СДЕЛАНО |
| P1.7 | Backup БД/результатов | скрипт + cron (sqlite `.backup`) | `scripts/backup.sh` | ✅ СДЕЛАНО |
| P1.10 | Неверный volume cookies в compose | монтировать `./storage`, а не `cookies.json` | `docker-compose.prod.yml` | ✅ СДЕЛАНО |
| P1.4 | Атомарность записи Excel | сохранение во временный файл + `os.replace` | `parser/export/excel.py` | ✅ СДЕЛАНО |
| P1.6 | Отдельные уведомления об ошибках | алерт через нотификатор при 3/10/30 ошибках подряд | `parser_cls.py` | ✅ СДЕЛАНО |
| P1.8 | Пин версий + UTF-8 + раздельные requirements | `curl_cffi==0.15.0`, `httpx==0.28.1`, UTF-8, `requirements-server.txt` | `requirements*.txt` | ✅ СДЕЛАНО |
| P1.3 | Нет rate limiting / circuit breaker | адаптация паузы при росте ошибок; circuit breaker по доле 403/429 | `parser/http/client.py` | ⏳ TODO |
| P1.9 | Docker от root, без HEALTHCHECK | non-root в Dockerfile; HEALTHCHECK (в prod-compose уже есть healthcheck+лимиты) | `Dockerfile` | ⏳ TODO (требует build-теста) |

## P2 — архитектура

| # | Улучшение | Решение | Файлы | Сложн. |
|---|---|---|---|---|
| P2.1 | Разделить scheduler и parser | вынести цикл/расписание из `__main__` в отдельный планировщик | `parser_cls.py`, новый `scheduler` | сред. |
| P2.2 | Абстракция «просмотренных» | интерфейс `SeenStore` (SQLite/Postgres/Redis) | `db_service.py` → `seen/` | сред. |
| P2.3 | Транзакции/миграции | atomic-операции, alembic/SQL-миграции | `db_service.py` | сред. |
| P2.4 | PostgreSQL | реализация `ResultStorage` + `SeenStore` на PG | `parser/export/`, `seen/` | сред. |
| P2.5 | Конфиг через ENV + валидация | Pydantic Settings, валидация значений | `load_config.py`, `dto.py` | сред. |
| P2.6 | Очередь задач | Redis + Celery/RQ для воркеров | новый слой | высок. |
| P2.7 | Тесты | unit на фильтры/модели/дедуп + smoke | `tests/` | сред. |
| P2.8 | Экспорт CSV/JSON | новые `ResultStorage` | `parser/export/` | низк. |
| P2.9 | Webhook-нотификатор | новый `Notifier` (POST) → n8n/CRM | `integrations/notifications/` | низк. |

## P3 — продуктовые функции

| Улучшение | Где переиспользовать существующее | Сложн. |
|---|---|---|
| Telegram-бот управления (вкл/выкл, фильтры, кнопки) | поверх `Notifier`/конфига; новый процесс (aiogram) | высок. |
| Web UI / админ-панель | поверх ядра + API | высок. |
| Несколько пользователей / проектов | PostgreSQL + мультиарендность | высок. |
| История цены + графики | таблица истории на основе `(id, price, ts)` | сред. |
| Избранное / скрытие продавца | хранилище предпочтений + кнопки в TG | сред. |
| Поиск аномально низкой цены / рейтинг / ИИ-резюме | аналитический слой поверх результатов | сред.-высок. |
| Webhook / n8n / CRM (amoCRM/Bitrix) | Webhook-нотификатор (P2.9) | сред. |
| REST API для сторонних клиентов | FastAPI поверх ядра | высок. |

## Рекомендуемая последовательность внедрения
1. **P0.3 → P0.1 → P0.2** (безопасность и целостность данных — до любого продакшена).
2. **P1.1, P1.9, P1.10, P0.4, P0.5** (production-Docker: graceful shutdown, healthcheck, volumes, логи).
3. **P1.2/P1.3, P1.5, P1.6** (устойчивость к блокировкам и изменениям Avito + алерты об ошибках).
4. **P1.7** (backup) и `MONITORING.md` (наблюдаемость).
5. Далее по потребности — P2 (если переход к сервису) и P3 (продуктовые фичи).
