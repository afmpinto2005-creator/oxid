#!/usr/bin/env python3
"""
Vinted Favorites Tracker
-------------------------
Procura os artigos mais recentes para um conjunto de palavras-chave em vários
mercados da Vinted, ordena-os pelo número de favoritos e envia um resumo
para o Telegram.

Instalar dependências:
    pip install requests

Configurar TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID abaixo (ou como variáveis
de ambiente) e correr:
    python vinted_favorites_tracker.py
"""

import os
import time
import requests

# ----------------------- CONFIGURAÇÃO -----------------------

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8899886970:AAF3MK8FRVDAHmhCxPpP7phVJp5NNhny4k8")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "8153467059")

# Domínios Vinted a monitorizar
DOMAINS = ["pt", "fr", "es"]

# Palavras-chave a pesquisar (aplicadas em todos os domínios acima)
KEYWORDS = [
    "relogio vintage",
    "anel",
    "japan style",
    "orologio",
    "montre",
    "y2k",
]

TOP_N = 15              # quantos artigos mostrar no resumo final
ITEMS_PER_SEARCH = 60   # artigos recentes a buscar por palavra-chave/domínio
MIN_FAVORITES = 1       # ignora artigos com menos favoritos que isto

# --------------------------------------------------------------


class VintedClient:
    def __init__(self, domain: str):
        self.base = f"https://www.vinted.{domain}"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
        })
        # Uma visita normal à homepage dá os cookies de sessão
        # que a API interna exige para responder.
        try:
            self.session.get(self.base, timeout=15)
        except requests.RequestException as e:
            print(f"[aviso] não consegui abrir sessão em {self.base}: {e}")

    def search(self, query: str, per_page: int = 60):
        url = f"{self.base}/api/v2/catalog/items"
        params = {
            "search_text": query,
            "order": "newest_first",
            "per_page": per_page,
            "page": 1,
        }
        try:
            resp = self.session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            return resp.json().get("items", [])
        except requests.RequestException as e:
            print(f"[aviso] falha a pesquisar '{query}' em {self.base}: {e}")
            return []


def collect_items():
    """Percorre todos os domínios e palavras-chave, devolve dict id -> item."""
    found = {}
    for domain in DOMAINS:
        client = VintedClient(domain)
        for kw in KEYWORDS:
            items = client.search(kw, per_page=ITEMS_PER_SEARCH)
            for item in items:
                item_id = item.get("id")
                fav = item.get("favourite_count", 0) or 0
                if item_id is None or fav < MIN_FAVORITES:
                    continue
                if item_id not in found or fav > found[item_id]["favourite_count"]:
                    path = item.get("path")
                    url = f"{client.base}{path}" if path else item.get("url", "")
                    price = item.get("price", {}) or {}
                    found[item_id] = {
                        "id": item_id,
                        "title": item.get("title", "sem título"),
                        "price": price.get("amount", "?"),
                        "currency": price.get("currency_code", ""),
                        "favourite_count": fav,
                        "url": url,
                        "domain": domain,
                    }
            time.sleep(0.5)  # não martelar a API
    return found


def format_message(items):
    if not items:
        return "Não encontrei artigos novos com favoritos nas palavras-chave configuradas."

    lines = ["🔥 *Top artigos por favoritos (últimos dias)*\n"]
    for i, item in enumerate(items[:TOP_N], start=1):
        lines.append(
            f"{i}. [{item['title']}]({item['url']})\n"
            f"   💶 {item['price']} {item['currency']} · ❤️ {item['favourite_count']} favoritos · 🌍 .{item['domain']}"
        )
    return "\n".join(lines)


def send_telegram_message(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    # Telegram tem limite de 4096 caracteres por mensagem
    chunks = [text[i:i + 4000] for i in range(0, len(text), 4000)] or [text]
    for chunk in chunks:
        resp = requests.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": chunk,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }, timeout=15)
        if not resp.ok:
            print(f"[erro] Telegram: {resp.status_code} {resp.text}")


def main():
    print("A procurar artigos...")
    found = collect_items()
    ranked = sorted(found.values(), key=lambda x: x["favourite_count"], reverse=True)
    message = format_message(ranked)
    print(message)
    send_telegram_message(message)
    print("Enviado para o Telegram.")


if __name__ == "__main__":
    main()
