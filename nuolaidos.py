#!/usr/bin/env python3
"""
ES nuolaidų rinkiklis (nauji daiktai). Mandagiai: tikras roboto vardas, laikomasi robots.txt, jokio apsaugų apėjimo.

  python nuolaidos.py feed            – „karščiausios“ akcijos iš ES nuolaidų bendruomenių (RSS) → data/nuolaidos.json
  python nuolaidos.py lt "užklausa"…  – LT kainos (kainos.lt, varle, pigu, Vinted nauji) → data/lt_kainos.json

Nieko neperka, nerašo pardavėjams, tik skaito viešus puslapius.
"""
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from skelbiu import proxy_url

ROOT = Path(__file__).resolve().parent
UA = "skelbimu-medziokle-kainos/1.0 (+https://github.com/VytisCode/skelbimu-medziokle)"
FEED_OUT = ROOT / "data" / "nuolaidos.json"
LT_OUT = ROOT / "data" / "lt_kainos.json"

SALTINIAI = {
    "DE": "https://www.mydealz.de",
    "AT": "https://www.preisjaeger.at",
    "PL": "https://www.pepper.pl",
    "FR": "https://www.dealabs.com",
    "ES": "https://www.chollometro.com",
}
# Netinkami: saugumo daiktai iš perpardavimo, paslaugos, maistas, kelionės, prenumeratos.
NETINKA = re.compile(
    r"\b(helm|helme|kask|casque|casco|kindersitz|fotelik|si[eè]ge auto|silla de coche|abo|abonnement|vertrag|tarif|"
    r"gutschein|kupon|coupon|cupón|voucher|flug|vol |lot |vuelo|hotel|reise|urlaub|pizza|lieferando|restaurant|"
    r"streaming|netflix|disney\+|spotify|game pass|freebie|gratis|kostenlos|darmowe|gratuit)\b", re.I)

_robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}


def opener():
    px = proxy_url()
    return urllib.request.build_opener(*([urllib.request.ProxyHandler({"http": px, "https": px})] if px else []))


OP = opener()


def leidzia(url: str) -> bool:
    p = urllib.parse.urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in _robots:
        try:
            t = OP.open(urllib.request.Request(base + "/robots.txt", headers={"User-Agent": UA}), timeout=20).read(400_000)
            rp = urllib.robotparser.RobotFileParser()
            rp.parse(t.decode("utf-8", "ignore").splitlines())
            _robots[base] = rp
        except urllib.error.HTTPError as e:
            _robots[base] = None if e.code in (404, 410) else False
        except Exception:
            _robots[base] = False
    rp = _robots[base]
    if rp is None:
        return True
    if rp is False:
        return False
    return rp.can_fetch(UA, url)


def gauti(url: str, limit: int = 3_000_000) -> tuple[int, str]:
    if not leidzia(url):
        return -1, ""
    try:
        r = OP.open(urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "lt,en;q=0.8"}), timeout=30)
        return r.status, r.read(limit).decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""


def kaina(t: str) -> float | None:
    m = re.search(r"(\d{1,5}(?:[.\s]\d{3})*(?:[.,]\d{1,2})?)\s?(?:€|EUR|zł|PLN)|€\s?(\d{1,5}(?:[.,]\d{1,2})?)", t)
    if not m:
        return None
    x = (m.group(1) or m.group(2)).replace(" ", "")
    if "," in x:
        x = x.replace(".", "").replace(",", ".")
    try:
        v = float(x)
    except ValueError:
        return None
    if "zł" in m.group(0) or "PLN" in m.group(0):
        v = round(v / 4.25, 2)  # apytikslis PLN→EUR
    return v if 1 <= v <= 5000 else None


def tag(item: str, name: str) -> str:
    m = re.search(rf"<{name}[^>]*>(.*?)</{name}>", item, re.S | re.I)
    if not m:
        return ""
    v = m.group(1).strip()
    v = re.sub(r"^<!\[CDATA\[(.*)\]\]>$", r"\1", v, flags=re.S)
    return html.unescape(re.sub(r"<[^>]+>", " ", v)).strip()


def feed() -> int:
    try:
        sena = json.loads(FEED_OUT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        sena = {"akcijos": []}
    riba = datetime.now(timezone.utc) - timedelta(days=5)
    turimi = {a["nuoroda"]: a for a in sena.get("akcijos", []) if a.get("data", "") >= riba.strftime("%Y-%m-%d")}
    busena = {}
    for salis, base in SALTINIAI.items():
        url = base + "/rss/hot"
        kod, t = gauti(url)
        items = re.findall(r"<item>(.*?)</item>", t, re.S)
        busena[salis] = {"url": url, "kodas": kod, "irasu": len(items)}
        print(f"{salis} {url} HTTP {kod} įrašų {len(items)}")
        for it in items:
            pav = tag(it, "title")
            nuor = tag(it, "link")
            apr = tag(it, "description")[:400]
            m = re.search(r'<pepper:merchant[^>]*name="([^"]*)"[^>]*?(?:price="([^"]*)")?', it)
            parduot = html.unescape(m.group(1)) if m else ""
            kn = kaina(m.group(2)) if m and m.group(2) else (kaina(pav) or kaina(apr))
            try:
                d = parsedate_to_datetime(tag(it, "pubDate")).astimezone(timezone.utc)
            except Exception:
                d = datetime.now(timezone.utc)
            if not nuor or not kn or d < riba or NETINKA.search(pav):
                continue
            turimi[nuor] = {"salis": salis, "pavadinimas": pav, "kaina_eur": kn, "parduotuve": parduot,
                            "nuoroda": nuor, "data": d.strftime("%Y-%m-%dT%H:%MZ"), "aprasymas": apr}
        time.sleep(3)
    ak = sorted(turimi.values(), key=lambda a: a["data"], reverse=True)[:300]
    FEED_OUT.write_text(json.dumps({"atnaujinta": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
                                    "saltiniai": busena, "akcijos": ak}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Išsaugota {len(ak)} akcijų")
    return 0


LT_PAIESKOS = {
    "kainos.lt": "https://www.kainos.lt/paieska?q={q}",
    "varle.lt": "https://www.varle.lt/search/?q={q}",
    "pigu.lt": "https://pigu.lt/lt/search?q={q}",
    "vinted.lt (nauji)": "https://www.vinted.lt/catalog?search_text={q}&status_ids[]=6&status_ids[]=1&order=price_low_to_high",
}


def lt(uzklausos: list[str]) -> int:
    try:
        rez = json.loads(LT_OUT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        rez = {}
    for q in uzklausos[:15]:
        irasas = {"laikas": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "saltiniai": {}}
        for vardas, sabl in LT_PAIESKOS.items():
            url = sabl.format(q=urllib.parse.quote_plus(q))
            kod, t = gauti(url)
            kainos = []
            for blk in re.findall(r"<script[^>]+application/ld\+json[^>]*>(.*?)</script>", t, re.S | re.I):
                kainos += [float(x) for x in re.findall(r'"(?:price|lowPrice)"\s*:\s*"?(\d+(?:\.\d+)?)', blk)]
            if not kainos:
                kainos = [v for v in (kaina(x) for x in re.findall(r"\d[\d\s.,]*\s?€", t[:2_000_000])) if v][:40]
            kainos = sorted(k for k in kainos if 1 <= k <= 5000)
            irasas["saltiniai"][vardas] = {"url": url, "kodas": kod, "kainos": kainos[:12],
                                           "min": kainos[0] if kainos else None,
                                           "mediana": kainos[len(kainos) // 2] if kainos else None}
            print(f"{q!r:30} {vardas:18} HTTP {kod} kainų {len(kainos)} min {kainos[0] if kainos else '-'}")
            time.sleep(2)
        rez[q] = irasas
    LT_OUT.write_text(json.dumps(rez, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "feed":
        sys.exit(feed())
    if len(sys.argv) >= 3 and sys.argv[1] == "lt":
        sys.exit(lt(sys.argv[2:]))
    print(__doc__)
    sys.exit(1)
