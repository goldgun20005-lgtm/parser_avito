"""
Webhook-нотификатор: шлёт объявление как JSON POST (n8n / любой приёмник).
См. docs/WEBHOOK_N8N_INTEGRATION.md
"""
import requests
from loguru import logger

from integrations.notifications.base import Notifier
from integrations.notifications.transport import send_with_retries
from integrations.notifications.utils import get_first_image, get_price
from models import Item


class WebhookNotifier(Notifier):
    """Отправляет объявление JSON-POST'ом на webhook (например, в n8n)."""

    def __init__(self, url: str, secret: str | None = None, timeout: int = 10):
        self.url = url
        self.secret = secret
        self.timeout = timeout

    def _payload(self, ad: Item = None, message: str = None, source: str = None) -> dict:
        if message and not ad:
            return {"type": "message", "text": message, "source": source}
        return {
            "type": "ad",
            # source = исходная поисковая ссылка Avito (для маршрутизации по друзьям в n8n)
            "source": source,
            "id": getattr(ad, "id", None),
            "title": getattr(ad, "title", None),
            "price": get_price(ad),
            "url": f"https://www.avito.ru/{getattr(ad, 'urlPath', '') or ''}",
            "short_url": f"https://avito.ru/{getattr(ad, 'id', '')}",
            "seller": getattr(ad, "sellerId", None),
            "image": get_first_image(ad=ad),
            "is_promotion": getattr(ad, "isPromotion", False),
            "total_views": getattr(ad, "total_views", None),
            "today_views": getattr(ad, "today_views", None),
        }

    def notify(self, ad: Item = None, message: str = None, source: str = None, **kwargs):
        headers = {"Content-Type": "application/json"}
        if self.secret:
            headers["X-Webhook-Secret"] = self.secret

        payload = self._payload(ad=ad, message=message, source=source)

        def _send():
            return requests.post(
                self.url,
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )

        try:
            send_with_retries(_send)
        except Exception as e:
            logger.warning(f"[webhook] не удалось отправить: {e}")
