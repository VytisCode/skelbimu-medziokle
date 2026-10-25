#!/usr/bin/env python3
"""Vienkartinis bandymas: ar Skelbiu.lt per proxy atsidaro tikroje Chromium naršyklėje (Cloudflare patikra).
Nuotraukos, šriftai ir video blokuojami, kad būtų mažiau proxy srauto."""
import json
import sys
import time
import urllib.parse
from pathlib import Path

from playwright.sync_api import sync_playwright

import skelbiu

URL = "https://www.skelbiu.lt/skelbimai/?keywords=makita"


def main() -> int:
    p = urllib.parse.urlsplit(skelbiu.proxy_url())
    proxy = {"server": f"http://{p.hostname}:{p.port}", "username": urllib.parse.unquote(p.username or ""),
             "password": urllib.parse.unquote(p.password or "")}
    rez = {"paleista": skelbiu.dabar()}
    baitai = 0
    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=False, proxy=proxy, args=["--disable-blink-features=AutomationControlled"])
        ctx = br.new_context(locale="lt-LT", timezone_id="Europe/Vilnius", viewport={"width": 1366, "height": 800})
        page = ctx.new_page()
        page.route("**/*", lambda r: r.abort() if r.request.resource_type in ("image", "media", "font") else r.continue_())

        def skaiciuoti(resp):
            nonlocal baitai
            try:
                baitai += int(resp.headers.get("content-length", "0"))
            except ValueError:
                pass
        page.on("response", skaiciuoti)
        resp = page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        rez["pirmas_kodas"] = resp.status if resp else None
        for _ in range(30):
            if "/skelbimai/" in page.content() and "challenge-platform" not in page.content():
                break
            time.sleep(1)
        html = page.content()
        rez.update(pavadinimas=page.title(), blokuota="challenge-platform" in html or "cf_chl_" in html,
                   skelbimu=len(skelbiu.atpazinti(html)), kb_apytiksliai=round(baitai / 1024))
        Path("data/narsykle_pavyzdys.html").write_text(html, encoding="utf-8")
        br.close()
    Path("data/narsykles_bandymas.json").write_text(json.dumps(rez, ensure_ascii=False, indent=1), encoding="utf-8")
    print(rez)
    return 0


if __name__ == "__main__":
    sys.exit(main())
