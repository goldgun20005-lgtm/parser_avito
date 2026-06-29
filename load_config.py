import os
import re
import tomllib
from pathlib import Path

import tomli_w

from dto import AvitoConfig

# Секреты можно держать вне config.toml (в .env / переменных окружения).
# Если переменная задана и непуста — она переопределяет значение из config.toml.
# Это позволяет НЕ хранить токены/прокси/ключи в отслеживаемом git файле.
_SECRET_STR_ENV = {
    "tg_token": "AVITO_TG_TOKEN",
    "vk_token": "AVITO_VK_TOKEN",
    "cookies_api_key": "AVITO_COOKIES_API_KEY",
    "proxy_string": "AVITO_PROXY_STRING",
    "proxy_change_url": "AVITO_PROXY_CHANGE_URL",
    "proxy_notifier": "AVITO_PROXY_NOTIFIER",
    "webhook_url": "AVITO_WEBHOOK_URL",
    "webhook_secret": "AVITO_WEBHOOK_SECRET",
}
_SECRET_LIST_ENV = {
    "tg_chat_id": "AVITO_TG_CHAT_ID",
    "vk_user_id": "AVITO_VK_USER_ID",
}


def _apply_env_overrides(avito: dict) -> dict:
    """Подставляет секреты из переменных окружения поверх config.toml."""
    for field, env in _SECRET_STR_ENV.items():
        value = os.environ.get(env)
        if value:
            avito[field] = value
    for field, env in _SECRET_LIST_ENV.items():
        value = os.environ.get(env)
        if value:
            # допускаем разделители: запятая, пробел, перевод строки
            avito[field] = [v.strip() for v in re.split(r"[,\s]+", value.strip()) if v.strip()]
    return avito


def load_avito_config(path: str = "config.toml") -> AvitoConfig:
    with open(path, "rb") as f:
        data = tomllib.load(f)
    avito = _apply_env_overrides(data.get("avito", {}))
    return AvitoConfig(**avito)


def save_avito_config(config: dict):
    with Path("config.toml").open("wb") as f:
        tomli_w.dump(config, f)
