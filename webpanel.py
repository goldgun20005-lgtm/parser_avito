"""
webpanel.py — простая веб-панель управления Avito Parser (без сторонних зависимостей).

Запуск:
    python webpanel.py                 # http://127.0.0.1:8000
    python webpanel.py --port 8080 --host 127.0.0.1

Возможности:
  • редактирование ВСЕХ настроек через браузер (пишется в config.toml);
  • Старт/Стоп парсера (parser_cls.py) как подпроцесса;
  • просмотр логов logs/app.log;
  • тест webhook / Telegram / VK.

⚠️ Безопасность: по умолчанию слушает ТОЛЬКО 127.0.0.1 (локально). Не выставляйте панель
наружу без обратного прокси с авторизацией — она пишет конфиг и запускает процессы.
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import tomllib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
CONFIG = ROOT / "config.toml"
EXAMPLE = ROOT / "config.example.toml"
LOG = ROOT / "logs" / "app.log"
INDEX = ROOT / "web" / "index.html"

LIST_KEYS = {"urls", "keys_word_white_list", "keys_word_black_list", "seller_black_list", "tg_chat_id", "vk_user_id"}
INT_KEYS = {"count", "min_price", "max_price", "max_age", "pause_general", "pause_between_links",
            "retry_delay", "timeout", "max_count_of_retry", "block_threshold"}
BOOL_KEYS = {"ignore_reserv", "ignore_promotion", "one_time_start", "one_file_for_link", "parse_views",
             "save_xlsx", "use_bypass_api", "use_own_cookies", "tg_only_text", "use_webdriver"}

proc: subprocess.Popen | None = None


# ─────────────────────────── config ───────────────────────────
def read_config() -> dict:
    path = CONFIG if CONFIG.exists() else (EXAMPLE if EXAMPLE.exists() else None)
    if not path:
        return {}
    with open(path, "rb") as f:
        return tomllib.load(f).get("avito", {})


def coerce(avito: dict) -> dict:
    out = {}
    for k, v in avito.items():
        if k in LIST_KEYS:
            if isinstance(v, str):
                v = [s.strip() for s in v.splitlines() if s.strip()]
            out[k] = list(v or [])
        elif k in INT_KEYS:
            try:
                out[k] = int(v)
            except (TypeError, ValueError):
                out[k] = 0
        elif k in BOOL_KEYS:
            out[k] = bool(v)
        elif k.startswith("__"):
            continue
        else:
            out[k] = "" if v is None else v
    return out


def write_config(avito: dict):
    # сливаем поверх существующего, чтобы не потерять незнакомые поля
    current = read_config()
    current.update(coerce(avito))
    try:
        from load_config import save_avito_config
        save_avito_config({"avito": current})
    except Exception:
        # запасной путь без зависимостей проекта
        import tomli_w  # type: ignore
        with open(CONFIG, "wb") as f:
            tomli_w.dump({"avito": current}, f)


# ─────────────────────────── process control ───────────────────────────
def is_running() -> bool:
    return proc is not None and proc.poll() is None


def start_proc():
    global proc
    if is_running():
        return
    LOG.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen([sys.executable, "parser_cls.py"], cwd=ROOT)


def stop_proc():
    global proc
    if not is_running():
        return
    try:
        if os.name == "nt":
            proc.terminate()
        else:
            proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=15)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    proc = None


def tail(path: Path, n: int) -> str:
    if not path.exists():
        return ""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-n:])
    except Exception as e:
        return f"(ошибка чтения логов: {e})"


# ─────────────────────────── tests ───────────────────────────
def _as_list(v):
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        return [s.strip() for s in v.replace(",", "\n").splitlines() if s.strip()]
    return []


def test_webhook(body) -> dict:
    url = body.get("url")
    if not url:
        return {"ok": False, "error": "не задан webhook_url"}
    try:
        from integrations.notifications.webhook import WebhookNotifier
        from models import Item

        class P:
            value = 75000
        ad = Item(id=1234567890, title="ТЕСТ из веб-панели", urlPath="test/iphone", sellerId="test")
        ad.priceDetailed = P()
        WebhookNotifier(url=url, secret=body.get("secret") or None).notify(
            ad=ad, source="https://www.avito.ru/test-search-link")
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def test_telegram(body) -> dict:
    token = body.get("token")
    chats = _as_list(body.get("chat_id"))
    if not token or not chats:
        return {"ok": False, "error": "нужны token и chat_id"}
    try:
        from integrations.notifications.telegram import TelegramNotifier
        for c in chats:
            TelegramNotifier(bot_token=token, chat_id=c, proxy=body.get("proxy") or None).notify(
                message="Тест из веб-панели Avito Parser")
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def test_vk(body) -> dict:
    token = body.get("token")
    users = _as_list(body.get("user_id"))
    if not token or not users:
        return {"ok": False, "error": "нужны token и user_id"}
    try:
        from integrations.notifications.vk import VKNotifier
        for u in users:
            VKNotifier(vk_token=token, user_id=u).notify(message="Тест из веб-панели Avito Parser")
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ─────────────────────────── HTTP ───────────────────────────
class Handler(BaseHTTPRequestHandler):
    def _send(self, code, data, ctype="application/json"):
        body = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if "json" in ctype or "html" in ctype else ""))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode())
        except Exception:
            return {}

    def do_GET(self):
        p = urlparse(self.path)
        if p.path in ("/", "/index.html"):
            return self._send(200, INDEX.read_bytes(), "text/html")
        if p.path == "/api/config":
            return self._send(200, {"avito": coerce(read_config())})
        if p.path == "/api/status":
            return self._send(200, {"running": is_running()})
        if p.path == "/api/logs":
            n = int(parse_qs(p.query).get("n", ["300"])[0])
            return self._send(200, {"text": tail(LOG, n)})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        p = urlparse(self.path)
        try:
            if p.path == "/api/config":
                write_config(self._body()); return self._send(200, {"ok": True})
            if p.path == "/api/start":
                start_proc(); return self._send(200, {"ok": True, "running": is_running()})
            if p.path == "/api/stop":
                stop_proc(); return self._send(200, {"ok": True, "running": is_running()})
            if p.path == "/api/test-webhook":
                return self._send(200, test_webhook(self._body()))
            if p.path == "/api/test-telegram":
                return self._send(200, test_telegram(self._body()))
            if p.path == "/api/test-vk":
                return self._send(200, test_vk(self._body()))
        except Exception as e:
            return self._send(500, {"ok": False, "error": str(e)})
        return self._send(404, {"error": "not found"})

    def log_message(self, *a):
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Avito Parser — панель управления: http://{args.host}:{args.port}")
    print("Остановить: Ctrl+C")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop_proc()


if __name__ == "__main__":
    main()
