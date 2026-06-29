# WEBHOOK_N8N_INTEGRATION — Интеграция через Webhook и n8n

> Статус: **РЕАЛИЗОВАНО** (по подтверждению пользователя) и **проверено локальным smoke-тестом**
> (см. `TEST_REPORT.md`, Уровень 2). Изменения внесены на ветке `claude/gracious-gauss-rnq17p`.
> Реальная отправка в боевой n8n проверяется на сервере (egress песочницы блокирует внешние хосты).
>
> Внесённые файлы: `integrations/notifications/webhook.py` (новый), правки в
> `factory.py`, `base.py`, `composite.py`, `telegram.py`, `vk.py`, `dto.py`, `parser_cls.py`,
> `config.toml`, `config.example.toml`.
>
> Отличие от первоначального проекта: payload дополнительно содержит **`source`** — исходную
> поисковую ссылку Avito, чтобы n8n маршрутизировал объявления **по друзьям** (у каждого свои поиски).
> `source` прокинут через `notify_many(..., source=url)` обратносовместимо (`**kwargs`), TG/VK не затронуты.
>
> ⚠️ Ограничение: GUI (`AvitoParser.py`) при сохранении конфига не знает про webhook-поля и может их
> затереть. На сервере GUI не используется — настройка только через `config.toml`/`.env`. Если нужен
> webhook в GUI — добавить виджеты (отдельная небольшая задача).

## Зачем
Выбранный канал — **Webhook/n8n**. В текущей версии (3.2.15) нотификаторов только два (Telegram, VK).
Нужно добавить **`WebhookNotifier`**, который шлёт POST с JSON по каждому новому объявлению.
n8n принимает webhook и делает «раздачу» нескольким друзьям + персональные фильтры/формат/кнопки.

## Целевой поток
```mermaid
flowchart LR
    P[parser_avito 24/7] -->|POST JSON на новое объявление| N[n8n Webhook node]
    N --> F{Фильтры/маршрутизация по другу}
    F --> T1[Telegram друг 1]
    F --> T2[Telegram друг 2]
    F --> X[Google Sheets / CRM / прочее]
    P -. spfa.ru cookies .-> AV[Avito.ru]
```
Преимущества: парсер остаётся **единым 24/7 инстансом** (один `config.toml`, один `database.db`),
а вся персонализация и масштабирование «на друзей» — в n8n. Не требуется мультиарендная переработка.

## Предлагаемая доработка (3 точки, ядро не меняется)
Согласно `docs/DOCS.md` («Добавление нового типа уведомлений»): новый класс + строка в фабрике + поля конфига.

### 1. Новый файл `integrations/notifications/webhook.py`
```python
import requests
from loguru import logger

from integrations.notifications.base import Notifier
from integrations.notifications.transport import send_with_retries
from integrations.notifications.utils import get_first_image, get_price
from models import Item


class WebhookNotifier(Notifier):
    """Шлёт объявление как JSON POST на webhook (n8n/прочее)."""

    def __init__(self, url: str, secret: str | None = None, timeout: int = 10):
        self.url = url
        self.secret = secret
        self.timeout = timeout

    def _payload(self, ad: Item = None, message: str = None) -> dict:
        if message and not ad:
            return {"type": "message", "text": message}
        return {
            "type": "ad",
            "id": getattr(ad, "id", None),
            "title": getattr(ad, "title", None),
            "price": get_price(ad),
            "url": f"https://www.avito.ru/{getattr(ad, 'urlPath', '') or ''}",
            "short_url": f"https://avito.ru/{getattr(ad, 'id', '')}",
            "seller": getattr(ad, "sellerId", None),
            "image": get_first_image(ad=ad),
            "is_promotion": getattr(ad, "isPromotion", False),
        }

    def notify(self, ad: Item = None, message: str = None):
        headers = {"Content-Type": "application/json"}
        if self.secret:
            headers["X-Webhook-Secret"] = self.secret

        def _send():
            return requests.post(
                self.url,
                json=self._payload(ad=ad, message=message),
                headers=headers,
                timeout=self.timeout,
            )

        try:
            send_with_retries(_send)
        except Exception as e:
            logger.warning(f"[webhook] не удалось отправить: {e}")
```

### 2. Подключение в `integrations/notifications/factory.py`
```python
# добавить импорт
from integrations.notifications.webhook import WebhookNotifier
# внутри build_notifier(), рядом с TG/VK:
if getattr(config, "webhook_url", None):
    notifiers.append(WebhookNotifier(url=config.webhook_url,
                                     secret=getattr(config, "webhook_secret", None)))
```

### 3. Поля конфигурации
- В `dto.py` (`AvitoConfig`): `webhook_url: str = None`, `webhook_secret: str = None`.
- В `config.toml`/`config.example.toml`: `webhook_url = ""`, `webhook_secret = ""` (секрет — через `.env`/на сервере).

> Изменения локализованы, ядро `parser_cls.py` не трогаем — соответствует архитектуре проекта.

## Пример JSON, который получит n8n
```json
{
  "type": "ad",
  "id": 1234567890,
  "title": "iPhone 16 128GB",
  "price": "75000",
  "url": "https://www.avito.ru/krasnodar/telefony/...",
  "short_url": "https://avito.ru/1234567890",
  "seller": "some-seller-slug",
  "image": "https://.../image.jpg",
  "is_promotion": false
}
```

## Настройка n8n (общая схема)
1. Нода **Webhook** (POST, путь напр. `/avito`), включить «Respond immediately».
2. (Опц.) Проверка `X-Webhook-Secret` (нода IF) — отбросить чужие запросы.
3. **Switch/Filter** — маршрутизация по другу (например, по ключевым словам/цене/категории).
4. Ноды **Telegram** (по одному credential на друга) или единый бот с разными chat_id.
5. (Опц.) **Dedup** в n8n (по `id`+`price`) — резервно к дедупу парсера.
6. (Опц.) Запись в **Google Sheets/БД** для истории.

## Безопасность
- Webhook n8n должен быть за HTTPS (reverse-proxy) и/или проверять секрет-заголовок.
- `webhook_secret` хранить в `.env`/на сервере, не в git.
- Если n8n на том же сервере — можно вызывать по внутренней сети (без публичного доступа).

## Дубли/идемпотентность
- Парсер уже шлёт уведомление только по «новым» (после фильтра просмотренных). Но из-за порядка
  notify→save (#300) при сбое возможен повтор. Рекомендация: **закрыть P0.1** (порядок save→notify)
  и добавить dedup в n8n как страховку.

---

## Статус внедрения
✅ Внесено и проверено локально (T1–T5 в `TEST_REPORT.md`). Финальный код `WebhookNotifier`
может включать дополнительные поля payload (`source`, `total_views`, `today_views`) —
см. `integrations/notifications/webhook.py`.

## Что осталось (на сервере)
1. Прописать `webhook_url` (и при желании `webhook_secret`) в `config.toml`/`.env` (URL вашего n8n).
2. В n8n создать Webhook-ноду и маршрутизацию по `source`/контенту для каждого друга.
3. Прогнать боевую проверку доставки (Уровень 4 `TEST_REPORT.md`).
