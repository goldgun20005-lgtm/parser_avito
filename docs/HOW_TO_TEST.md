# HOW_TO_TEST — Как протестировать прямо сейчас

> Тестирование «снизу вверх»: сначала проверяем внутреннюю логику (без Avito), затем связку с n8n,
> затем боевой запрос к Avito. Каждый уровень не требует предыдущего, но логично идти по порядку.

## Подготовка (один раз)

```bash
# из корня проекта (ветка claude/gracious-gauss-rnq17p)
python -m venv .venv

# Linux / macOS:
source .venv/bin/activate
# Windows (PowerShell):
#   .venv\Scripts\Activate.ps1

pip install -r requirements.txt          # полный набор
# или лёгкий серверный набор (без GUI/Playwright):
# pip install -r requirements-server.txt
```

---

## Уровень 0 — Само-тест без Avito (30 секунд) ✅ самый быстрый

Проверяет всю «машинерию»: импорт, webhook + `source`, дедуп SQLite + миграцию,
устойчивый парсинг, атомарную запись Excel. Сеть к Avito НЕ нужна.

```bash
python scripts/selftest.py
```
Ожидаемо: `ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ ✅` и код возврата 0.
Если что-то падает — значит проблема в окружении/зависимостях, а не в Avito.

---

## Уровень 1 — Тест связки с вашим n8n (без Avito)

Шлёт ОДНО тестовое объявление тем же кодом, что и боевой парсер. В n8n убедитесь,
что Webhook-нода получила JSON (поле `source` — для маршрутизации по другу).

```bash
python scripts/send_test_webhook.py https://ВАШ-n8n/webhook/avito
# с секретом (заголовок X-Webhook-Secret):
python scripts/send_test_webhook.py https://ВАШ-n8n/webhook/avito МОЙ_СЕКРЕТ
```
В n8n: открыть workflow → нода **Webhook** → **Executions** — должен появиться вызов с телом:
```json
{ "type": "ad", "source": "https://www.avito.ru/test-search-link",
  "id": 1234567890, "title": "ТЕСТ: iPhone 16 128GB", "price": "75000", "url": "...", "image": null }
```
Здесь же отладьте маршрутизацию: Switch/IF по `source` → нужный друг.

---

## Уровень 2 — Боевой одноразовый прогон к Avito

> ⚠️ С «голого» IP (дата-центр/случайный) Avito почти наверняка отдаст 403.
> Нужен антиблок: **spfa.ru** (ваш выбор) и/или прокси РФ.

1. Подготовьте конфиг и секреты:
   ```bash
   cp config.example.toml config.toml
   cp .env.example .env
   ```
2. В `config.toml`: вставьте ОДНУ узкую ссылку-поиск в `urls`, `count = 1`,
   `one_time_start = true`, `save_xlsx = true`, `use_bypass_api = true`.
3. В `.env`: задайте секреты (они переопределяют config.toml):
   ```
   AVITO_COOKIES_API_KEY=ваш_ключ_spfa
   AVITO_WEBHOOK_URL=https://ВАШ-n8n/webhook/avito
   # при наличии прокси:
   # AVITO_PROXY_STRING=user:pass@host:port
   ```
   Подгрузить переменные: Linux/macOS — `set -a; . ./.env; set +a` ; Windows — задать через `$env:`.
4. Запуск:
   ```bash
   python parser_cls.py
   ```
5. Что проверить:
   - в `logs/app.log` — строка `Запуск AvitoParse v3.2.15`;
   - `Объявлений перед чисткой N` и `После фильтрации …` (объявления извлеклись);
   - появился `result/avito.xlsx` и `database.db`;
   - в n8n пришли объявления;
   - в конце — `Хорошие запросы: Nшт, плохие: Mшт`.
   - **Признак блокировки:** `Запрос заблокирован (403/429)` → нужен прокси/проверьте spfa-ключ.

---

## Уровень 3 — Проверка дедупликации (главное для мониторинга)

Запустите Уровень 2 **второй раз подряд** (тот же `config.toml`/БД):
```bash
python parser_cls.py
```
Ожидаемо: после фильтра «просмотренные» новых объявлений почти не будет, **webhook'и
повторно НЕ шлются** (в логах `После фильтрации _filter_viewed осталось 0`).
Это подтверждает, что вы не будете спамить друзей повторами.

---

## Уровень 4 — Docker (когда будете готовы)

```bash
cp config.example.toml config.toml && cp .env.example .env   # заполнить
touch database.db && mkdir -p result storage logs backups
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml logs -f --tail=100
```
Проверка persistence: `docker compose -f docker-compose.prod.yml restart` → `database.db`/`result` на месте.

---

## Шпаргалка
| Хочу проверить | Команда |
|---|---|
| Что код вообще работает | `python scripts/selftest.py` |
| Что n8n принимает | `python scripts/send_test_webhook.py <URL>` |
| Реальный парсинг Avito | `python parser_cls.py` (config + spfa/прокси) |
| Что нет повторов | запустить `parser_cls.py` дважды |
