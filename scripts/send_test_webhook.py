"""
send_test_webhook.py — отправляет ТЕСТОВОЕ объявление в ваш webhook (n8n),
чтобы проверить связку «парсер -> n8n -> раздача друзьям» без обращения к Avito.

Использование:
    python scripts/send_test_webhook.py https://ВАШ-n8n/webhook/avito
    # или через переменные окружения:
    AVITO_WEBHOOK_URL=https://... AVITO_WEBHOOK_SECRET=... python scripts/send_test_webhook.py

Что делает: формирует образец объявления и шлёт его тем же кодом (WebhookNotifier),
что и боевой парсер. В n8n вы увидите JSON с полем "source" для маршрутизации.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from loguru import logger  # noqa: E402
from models import Item  # noqa: E402
from integrations.notifications.webhook import WebhookNotifier  # noqa: E402


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("AVITO_WEBHOOK_URL", "")
    secret = os.environ.get("AVITO_WEBHOOK_SECRET") or (sys.argv[2] if len(sys.argv) > 2 else None)

    if not url:
        print("Укажите URL webhook: python scripts/send_test_webhook.py <URL> [SECRET]")
        print("или задайте переменную окружения AVITO_WEBHOOK_URL")
        return 2

    class P:
        value = 75000

    ad = Item(
        id=1234567890,
        title="ТЕСТ: iPhone 16 128GB",
        urlPath="krasnodar/telefony/mobilnye_telefony/apple/iphone_16_test",
        sellerId="test-seller",
    )
    ad.priceDetailed = P()

    notifier = WebhookNotifier(url=url, secret=secret)
    logger.info(f"Отправляю тестовое объявление на {url} (secret={'да' if secret else 'нет'})")
    notifier.notify(ad=ad, source="https://www.avito.ru/test-search-link")
    logger.info("Готово. Проверьте, пришёл ли запрос в n8n (нода Webhook -> Executions).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
