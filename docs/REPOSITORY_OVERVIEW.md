# REPOSITORY_OVERVIEW — Инвентаризация репозитория

> Статус: **Подтверждено кодом** (статический анализ рабочей копии).
> Дата аудита: 2026-06-29. Аудит проводился без изменения исходного кода.

## 1. Идентификация версии и состояния

| Параметр | Значение | Источник |
|---|---|---|
| Аудируемый репозиторий (форк) | `goldgun20005-lgtm/parser_avito` | `git remote -v` |
| Оригинал (upstream) | `Duff89/parser_avito` | README, `Dockerfile` LABEL |
| Текущая ветка | `claude/gracious-gauss-rnq17p` | `git rev-parse` |
| Последний commit | `c6e373c` «feat: 3.2.15» | `git log -1` |
| Дата последнего commit | 2026-06-15 22:44 +0300 | `git log -1` |
| Версия приложения | **3.2.15** | `version.py` |
| Расхождение форка с `master` | **нет** (ветка == master) | `git log master..HEAD` |
| Локальные git-теги | отсутствуют (форк теги не подтянул) | `git tag` |
| LICENSE-файл | **ОТСУТСТВУЕТ** | `ls LICENSE*` |

### Данные по upstream `Duff89/parser_avito` (через GitHub API/Web, 2026-06-29)

| Параметр | Значение |
|---|---|
| Звёзды / форки | ~650 / ~176 |
| Открытых Issues | **39** |
| Последний release | **v3.2.15** (2026-06-15), всего ~27 релизов |
| Язык | Python (96.9%) |
| CI/CD | Есть: `.github/workflows/docker.yml`, `release.yml` |
| Docker-образ | `ghcr.io/duff89/parser_avito` (linux/amd64 + arm64) |
| Лицензия | **Не объявлена** (только дисклеймер «as is» в README) |

> ⚠️ Issue **#293** (open): Docker-образы на ghcr.io **перестали обновляться после v3.2.07**. Тег `latest` фактически устарел — см. `DOCKER_AUDIT.md`.

## 2. Наличие инженерных практик

| Практика | Наличие | Комментарий |
|---|---|---|
| CI/CD | ✅ | GitHub Actions: сборка Windows .exe (release.yml) + Docker (docker.yml) |
| Автосборка Docker | ⚠️ | Workflow есть, но публикация сломана (#293) |
| Тесты (unit/integration) | ❌ | Тестов в репозитории нет |
| Линтер (flake8/ruff) | ❌ | Конфигурации нет |
| Type checking (mypy) | ❌ | Нет, хотя аннотации типов в коде присутствуют |
| Security scanning | ❌ | Нет (dependabot/codeql/trivy не настроены) |
| Pre-commit hooks | ❌ | Нет |
| `.gitignore` | ⚠️ | Почти пустой — игнорирует только `.secret.txt` |
| `.dockerignore` | ✅ | Покрывает `database.db`, `result/`, `logs/`, `cookies.json`, `state.json` |

## 3. Структура репозитория

### 3.1. Точки входа

| Файл | Назначение | Режим |
|---|---|---|
| `AvitoParser.py` | Графический интерфейс на Flet (desktop). `ft.app(target=main)` | GUI |
| `parser_cls.py` | Класс `AvitoParse` + блок `__main__` с бесконечным циклом | CLI / сервер / Docker |
| `entrypoint.sh` | Docker-entrypoint: `python parser_cls.py` | Docker |
| `get_cookies.py` | Playwright-клиент получения cookies (см. §5 — фактически не используется в основном потоке) | вспомог. |
| `utils/prompt_user_login.py` | Playwright-логин в аккаунт Avito (кнопка в GUI) | GUI |

### 3.2. Конфигурация

| Файл | Назначение |
|---|---|
| `config.toml` | **Единственный** источник настроек (URL, токены, фильтры, прокси, паузы). **Закоммичен в git.** |
| `load_config.py` | Загрузка (`tomllib`) и сохранение (`tomli_w`) конфига |
| `dto.py` | `@dataclass AvitoConfig` — типизированная модель конфига; `Proxy`, `ProxySplit` |
| `version.py` | `VERSION = "3.2.15"` |
| `lang.py` | Строки подсказок (tooltip) для GUI |

### 3.3. Хранение данных

| Объект | Где | Что хранит |
|---|---|---|
| `database.db` (SQLite) | корень проекта | таблица `viewed(id, price)` — память просмотренных объявлений |
| `db_service.py` | — | `SQLiteDBHandler` (singleton) — работа с `viewed` |
| `result/avito.xlsx` | каталог `result/` | результаты парсинга (Excel) |
| `storage/own_cookies.json` | `storage/` | свои cookies (логин-флоу) |
| `storage/cookies_external.json` | `storage/` | cookies от сервиса spfa.ru |
| `logs/app.log` | `logs/` | логи (loguru, ротация 5 МБ, хранение 5 дней) |

### 3.4. Бизнес-логика парсинга (`parser/`)

| Путь | Назначение |
|---|---|
| `parser/http/client.py` | `HttpClient` на `curl_cffi` — запросы, ретраи, обработка блокировок (401/403/429) |
| `parser/cookies/base.py` | абстракция `CookiesProvider` |
| `parser/cookies/factory.py` | выбор провайдера cookies по конфигу |
| `parser/cookies/own_cookies.py` | `OwnCookiesProvider` — свои cookies из файла |
| `parser/cookies/external_api.py` | `ExternalApiCookiesProvider` — cookies от spfa.ru (покупка/разблокировка) |
| `parser/proxies/proxy.py` | `NoProxy` / `ServerProxy` / `MobileProxy` |
| `parser/proxies/proxy_factory.py` | выбор типа прокси по конфигу |
| `parser/export/base.py` | абстракция `ResultStorage` |
| `parser/export/excel.py` | `ExcelStorage` (openpyxl) |
| `parser/export/composite.py` | `CompositeResultStorage`, `NullResultStorage` |
| `parser/export/factory.py` | сборка хранилища результатов |

### 3.5. Фильтрация

| Путь | Назначение |
|---|---|
| `filters/ads_filter.py` | `AdsFilter.apply()` — конвейер фильтров: просмотренные → цена → стоп-слова → ключевые слова → гео → продавец → возраст → резерв → продвижение |

### 3.6. Интеграции / уведомления (`integrations/notifications/`)

| Путь | Назначение |
|---|---|
| `base.py` | абстракция `Notifier`, дефолтное форматирование |
| `factory.py` | сборка нотификаторов из конфига (TG/VK) |
| `composite.py` | `CompositeNotifier` (рассылка во все), `NullNotifier` |
| `telegram.py` | `TelegramNotifier` (фото/текст, fallback на multipart, retry) |
| `vk.py` | `VKNotifier` (отправка от имени сообщества, загрузка фото) |
| `transport.py` | `send_with_retries()` — общий retry для уведомлений |
| `utils.py` | экранирование MarkdownV2, выбор картинки, цена |

### 3.7. Утилиты (`utils/`)

| Путь | Назначение |
|---|---|
| `build_api_params.py` | формирует параметры для API-эндпоинта пагинации |
| `normalize_parametr.py` | нормализация сложных фильтров Avito в query-параметры |
| `parse_phone.py` | `ParsePhone` — получение телефонов через spfa.ru (**отключено в коде**, см. ARCHITECTURE_AUDIT) |
| `prompt_user_login.py` | Playwright-логин и сохранение «своих» cookies |

### 3.8. Прочее

| Файл | Назначение |
|---|---|
| `models.py` | Pydantic-модели объявлений: `Item`, `ItemsResponse`, `PriceDetailed`, … |
| `common_data.py` | статические `HEADERS` для запросов |
| `hide_private_data.py` | маскирование секретов в логах (`mask_sensitive_data`, `log_config`) |
| `playwright_setup.py` | проверка/установка Playwright (для .exe-сборки) |
| `Dockerfile`, `docker-compose.yml`, `Makefile` | контейнеризация |
| `run_avito_parser.bat` | запуск под Windows |
| `requirements.txt` | зависимости (в кодировке **UTF-16**) |
| `assets/` | иконка, gif |
| `docs/` | документация проекта |

## 4. Механизмы (где искать)

| Механизм | Реализация |
|---|---|
| Получение объявлений | `parser_cls.py: fetch_data()` (1-я стр., HTML) + `fetch_api_data()` (стр. 2+, JSON API `/web/1/js/items`) |
| Извлечение JSON со страницы | `parser_cls.py: find_json_on_page()` — ищет `<script type="mime/invalid" data-mfe-state="true">` |
| Определение «новизны» | `db_service.py: record_exists(id, price)` — ключ дедупликации `(id, price)` |
| Фильтрация | `filters/ads_filter.py` |
| Уведомления | `integrations/notifications/*` |
| Экспорт | `parser/export/*` |
| Работа с cookies | `parser/cookies/*` |
| Работа с прокси | `parser/proxies/*` |
| Антиблокировка | `parser/http/client.py` (ретраи 401/403/429 → `handle_block` cookies+proxy) |

## 5. Замечания по инвентаризации (расхождения «код ↔ заявления»)

1. **`use_webdriver`** — присутствует в `config.toml`, `dto.py:47`, GUI (`AvitoParser.py:690`), но **нигде не читается** в потоке запросов. Запросы всегда идут через `curl_cffi`. Опция — фактически no-op.
2. **`get_cookies.py`** (модульная функция `get_cookies`, строка 210) — **не импортируется** нигде в основном потоке. Playwright реально задействован только в `utils/prompt_user_login.py` (кнопка GUI «Войти в аккаунт»).
3. **`parse_phone`** — функционал отключён в коде (`parser_cls.py:265` условие всегда истинно → ранний возврат), помечен «future feat». Issue #259 это подтверждает.
4. **`config.toml` закоммичен в git** и НЕ в `.gitignore` → риск утечки секретов (см. `SECURITY_AUDIT.md`).
5. **Нет LICENSE** — условия переиспользования юридически не определены.
