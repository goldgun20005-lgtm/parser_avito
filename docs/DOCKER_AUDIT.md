# DOCKER_AUDIT — Аудит контейнеризации

> Статус: **Подтверждено кодом** (`Dockerfile`, `docker-compose.yml`, `entrypoint.sh`, `Makefile`).
> Сборка/запуск контейнера в окружении аудита **не выполнялись** (Docker-демон недоступен) —
> это уровень 3 в `TEST_REPORT.md`, отложен.

## 1. Анализ `Dockerfile`

```
FROM python:3.11-slim
# apt: библиотеки для Chromium (libnss3, libatk, libgbm, ...)
# pip install -r requirements.txt
# python -m playwright install chromium-headless-shell
# COPY . /app ; ENTRYPOINT bash /entrypoint.sh -> python parser_cls.py
```

| Параметр | Значение | Оценка |
|---|---|---|
| Базовый образ | `python:3.11-slim` | ✅ ок |
| Версия Python | 3.11 | ✅ совпадает с требованиями |
| Системные пакеты | библиотеки для Chromium | ⚠️ нужны только для Playwright |
| Установка Chromium | `playwright install chromium-headless-shell` | ⚠️ **не используется** основным потоком (curl_cffi) |
| Пользователь | **root** (нет `USER`) | 🔴 запуск от root |
| Размер образа | большой (Chromium + libs) | ⚠️ можно сильно ужать |
| Healthcheck | **нет** | 🔴 нет |
| Restart policy | задаётся в compose | — |
| Volumes | задаются в compose | — |
| .dockerignore | есть, покрывает данные/логи | ✅ |
| ENTRYPOINT | `bash entrypoint.sh` → `parser_cls.py` | ✅ серверный режим |
| Обработка сигналов | `bash` + `python` без `exec` | 🔴 SIGTERM может не дойти до Python |
| Слои/кэш | requirements копируются до кода | ✅ кэш-дружелюбно |

### Ключевые проблемы Dockerfile
1. **Запуск от root** — нет непривилегированного пользователя (`SECURITY_AUDIT.md`).
2. **Chromium в образе не нужен** для серверного потока → лишние ~сотни МБ и время сборки.
   (Логин в аккаунт через headed-браузер в контейнере всё равно не работает.)
3. **Нет `exec`** в entrypoint → процесс Python — не PID 1 → **SIGTERM от `docker stop` не доставляется
   приложению**, контейнер убивается по таймауту (SIGKILL). Нет graceful shutdown.
   Митигируется `init: true` в compose, но лучше `exec python ...`.
4. **Нет HEALTHCHECK** — Docker не знает, «жив» ли парсер (процесс может висеть без полезной работы).

## 2. Анализ `entrypoint.sh`

```bash
wait_seconds=1; sleep 1; cd /app; exec python parser_cls.py
```
- ✅ **ИСПРАВЛЕНО:** добавлен `exec` → python становится PID 1 и получает SIGTERM от `docker stop`.
  В паре с обработчиком SIGTERM/SIGINT в `parser_cls.py` (`stop_event`) это даёт graceful shutdown.
- Рекомендация по `init: true` уже учтена в `docker-compose.prod.yml`.

## 3. Анализ `docker-compose.yml`

```yaml
services:
  parser_avito:
    container_name: avito
    image: ghcr.io/duff89/parser_avito:latest   # ⚠️ устаревший тег (#293)
    restart: always
    volumes:
      - ./config.toml:/app/config.toml:ro
      - ./cookies.json:/app/cookies.json:Z       # ⚠️ путь не совпадает с кодом
      - ./result:/app/result:Z
      - type: bind
        source: database.db
        target: /app/database.db
        bind: { create_host_path: false }
```

| Аспект | Состояние | Оценка |
|---|---|---|
| Источник образа | `ghcr.io/...:latest` | 🔴 **устарел** (#293, ≈3.2.07). Не использовать. |
| restart | `always` | ✅ (для 24/7 лучше `unless-stopped`) |
| init | **нет** | 🔴 нет reaper зомби / проброса сигналов |
| Volume config.toml | `:ro` | ✅ |
| Volume cookies.json | `./cookies.json:/app/cookies.json` | 🔴 **код пишет в `storage/own_cookies.json` и `storage/cookies_external.json`**, а не `/app/cookies.json` → cookies **не персистятся** |
| Volume result | `./result` | ✅ |
| Volume database.db | bind, `create_host_path:false` | ⚠️ требует `touch database.db` заранее, иначе ошибка |
| Volume logs | **нет** | 🔴 `logs/app.log` теряется при пересоздании контейнера |
| Volume storage | **нет** | 🔴 свои/внешние cookies теряются |
| healthcheck | нет | 🔴 |
| logging limits | нет | 🔴 json-логи Docker растут без ограничений |
| resource limits | нет | ⚠️ нет лимитов CPU/RAM |
| user / security_opt / cap_drop | нет | ⚠️ от root, без ужесточения |

### Что реально нужно монтировать (по коду)
| Путь в контейнере | Что | Источник в коде |
|---|---|---|
| `/app/config.toml` | конфиг (ro) | `load_config.py` |
| `/app/database.db` | память просмотренных | `db_service.py` (CWD=/app) |
| `/app/result` | Excel-результаты | `parser/export/factory.py` (`output_dir="result"`) |
| `/app/storage` | свои/внешние cookies | `own_cookies.py`, `external_api.py` (`storage/...json`) |
| `/app/logs` | логи | `parser_cls.py` (`logs/app.log`) |

> ⚠️ Текущий `cookies.json`-volume в compose **не соответствует** путям в коде — это баг конфигурации.
> В production-варианте нужно монтировать каталог `./storage`, а не `cookies.json`.

## 4. Сравнение: готовый образ vs локальная сборка

### Вариант A — готовый образ `ghcr.io/duff89/parser_avito:latest`
| Критерий | Факт |
|---|---|
| Существует? | ✅ да |
| Версия внутри | ≈ **3.2.07** (по #293), не соответствует release 3.2.15 |
| Когда собран | устарел (~несколько месяцев) |
| Архитектуры | linux/amd64, linux/arm64 |
| Доверять `latest`? | 🔴 **Нет** (#293) |
| Можно закрепить digest/tag? | Версионные теги до ~3.2.07; свежих нет |

### Вариант B — локальная сборка из исходников
| Критерий | Оценка |
|---|---|
| Собирается ли Dockerfile | Ожидаемо да (синтаксис ок; зависит от доступа к apt/pip/playwright CDN) |
| Время сборки | Долго (Chromium + apt + pip) |
| Совпадение версии с репо | ✅ да (собирается из текущего кода 3.2.15) |
| Системные зависимости | Покрыты apt-слоем |

### Рекомендация
**Использовать вариант B — локальную сборку** из конкретного release-tag / commit SHA (для воспроизводимости),
а не `latest`. После сборки тегировать образ своей версией и при желании запушить в свой registry.
Готовый `latest` не использовать из-за #293.

## 5. Обновление без потери данных
Возможно при условии, что **все данные на volume** (config, database.db, result, storage, logs).
Тогда `docker compose pull/build && up -d` не затрагивает данные. В текущем compose это **не выполнено**
(нет volume для `storage` и `logs`, неверный путь cookies) → требуется production-compose (см. `DEPLOYMENT_OPTIONS.md`/§20 промта).

## 6. Итог по Docker
- Базовая контейнеризация рабочая, но **production-неготова**: root, нет healthcheck/init/exec,
  нет volume для logs/storage, неверный путь cookies, устаревший публичный образ, нет лимитов и ротации логов.
- Все эти пункты вынесены в `IMPROVEMENT_ROADMAP.md` (P1) и будут закрыты production-вариантом compose
  на этапе развёртывания (Фаза C).
