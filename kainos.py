#!/usr/bin/env python3
"""
Naujų daiktų kainų tikrintuvas (mandagus): kartą per parą atsisiunčia data/nauji.json produktų puslapius per LT proxy
ir ištraukia kainą iš viešų schema.org / meta žymių. Laikosi robots.txt, prisistato tikru vardu, neapeina jokių
apsaugų: jei parduotuvė atsako 403 / captcha ar robots.txt draudžia – tik pažymi „neprieinama“ ir eina toliau.
Rezultatas – data/kainos_auto.json: {url: {kaina, laikas, klaida}}. Nieko neperka, tik skaito.
"""
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import datetime, timedelta, timezone
from pathlib import Path

from skelbiu import dabar, paslepti, proxy_url

ROOT = Path(__file__).resolve().parent
NAUJI = ROOT / "data" / "nauji.json"
AUTO = ROOT / "data" / "kainos_auto.json"
UA = "skelbimu-medziokle-kainos/1.0 (+https://github.com/VytisCode/skelbimu-medziokle)"
MAX_NUORODU = 60
DAZNIS_VAL = 20
MAX_BAITU = 1_500_000


def skaicius(t) -> float | None:
    if t is None:
        return None
    if isinstance(t, (int, float)):
        return float(t) if 1 <= t <= 20000 else None
    m = re.search(r"\d[\d\s.,]*", str(t).replace("\xa0", " "))
    if not m:
        return None
    x = m.group(0).replace(" ", "")
    if "," in x and "." in x:
        x = x.replace(".", "").replace(",", ".") if x.rfind(",") > x.rfind(".") else x.replace(",", "")
    elif "," in x:
        x = x.replace(",", ".") if len(x.split(",")[-1]) <= 2 else x.replace(",", "")
    try:
        v = float(x)
    except ValueError:
        return None
    return v if 1 <= v <= 20000 else None


def _offers(o, out):
    if isinstance(o, list):
        for x in o:
            _offers(x, out)
    elif isinstance(o, dict):
        if "price" in o or "lowPrice" in o:
            v = skaicius(o.get("lowPrice") or o.get("price"))
            if v and "OutOfStock" not in str(o.get("availability", "")):
                out.append((v, str(o.get("priceCurrency") or "EUR").upper()))
        for v in o.values():
            if isinstance(v, (dict, list)):
                _offers(v, out)


def istraukti_kaina(h: str) -> tuple[float | None, str]:
    out = []
    for blk in re.findall(r"<script[^>]+application/ld\+json[^>]*>(.*?)</script>", h, re.S | re.I):
        try:
            _offers(json.loads(blk.strip()), out)
        except ValueError:
            continue
    eur = [v for v, c in out if c in ("EUR", "")]
    if eur:
        return min(eur), "json-ld"
    for pat in (r'<meta[^>]+(?:property|itemprop|name)="(?:product:price:amount|og:price:amount|price)"[^>]+content="([^"]+)"',
                r'itemprop="price"[^>]*content="([^"]+)"'):
        m = re.search(pat, h, re.I)
        if m and skaicius(m.group(1)):
            return skaicius(m.group(1)), "meta"
    return None, ""


def istraukti_paveiksla(h: str) -> str | None:
    for blk in re.findall(r"<script[^>]+application/ld\+json[^>]*>(.*?)</script>", h, re.S | re.I):
        try:
            d = json.loads(blk.strip())
        except ValueError:
            continue
        for o in (d if isinstance(d, list) else d.get("@graph", [d]) if isinstance(d, dict) else []):
            if not isinstance(o, dict) or "Product" not in str(o.get("@type", "")):
                continue
            im = o.get("image")
            im = im[0] if isinstance(im, list) and im else im
            im = im.get("url") if isinstance(im, dict) else im
            if isinstance(im, str) and im.startswith("https://"):
                return im
    m = re.search(r'<meta[^>]+property="og:image"[^>]+content="(https://[^"]+)"', h, re.I)
    return m.group(1) if m else None


def main() -> int:
    try:
        d = json.loads(NAUJI.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print("data/nauji.json nėra.")
        return 0
    try:
        auto = json.loads(AUTO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        auto = {}
    riba = (datetime.now(timezone.utc) - timedelta(hours=DAZNIS_VAL)).strftime("%Y-%m-%dT%H:%M:%SZ")
    urls = []
    for p in d.get("produktai", []):
        for x in p.get("lt", []) + p.get("es", []):
            u = x.get("url") or ""
            if u.startswith("https://") and u not in urls and (auto.get(u, {}).get("laikas", "") < riba or auto.get(u, {}).get("v", 1) < 2):
                urls.append(u)
    urls = urls[:MAX_NUORODU]
    if not urls:
        print("Visos kainos šviežios.")
        return 0
    px = proxy_url()
    handlers = [urllib.request.ProxyHandler({"http": px, "https": px})] if px else []
    op = urllib.request.build_opener(*handlers)
    robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
    gauta, kb = 0, 0.0
    for u in urls:
        host = urllib.parse.urlsplit(u).netloc
        if host not in robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                with op.open(urllib.request.Request(f"https://{host}/robots.txt", headers={"User-Agent": UA}), timeout=20) as r:
                    rp.parse(r.read(200_000).decode("utf-8", "replace").splitlines())
                robots[host] = rp
            except Exception:  # noqa: BLE001 – be robots.txt nesiunčiam
                robots[host] = None
        e = {"laikas": dabar(), "v": 2}
        rp = robots[host]
        if rp is None:
            e["klaida"] = "robots.txt neprieinamas"
        elif not rp.can_fetch(UA, u):
            e["klaida"] = "robots.txt draudžia"
        else:
            try:
                req = urllib.request.Request(u, headers={"User-Agent": UA, "Accept-Language": "lt,en;q=0.8"})
                with op.open(req, timeout=30) as r:
                    h = r.read(MAX_BAITU).decode("utf-8", "replace")
                kb += len(h) / 1024
                v, budas = istraukti_kaina(h)
                pav = istraukti_paveiksla(h)
                if pav:
                    e["paveikslas"] = pav[:400]
                if v:
                    e.update(kaina=v, budas=budas, kainos_laikas=e["laikas"])
                    gauta += 1
                else:
                    e["klaida"] = "kaina puslapyje nerasta"
            except urllib.error.HTTPError as ex:
                e["klaida"] = f"neprieinama (HTTP {ex.code})"
            except Exception as ex:  # noqa: BLE001
                e["klaida"] = paslepti(f"{type(ex).__name__}: {ex}")[:120]
            time.sleep(3)
        senas = auto.get(u, {})
        if "paveikslas" not in e and senas.get("paveikslas"):
            e["paveikslas"] = senas["paveikslas"]
        if "kaina" not in e and senas.get("kaina"):
            e["kaina_anksciau"], e["kainos_laikas"] = senas["kaina"], senas.get("kainos_laikas")
        auto[u] = e
        print(f"{host}: {e.get('kaina') or e.get('klaida')}")
    AUTO.write_text(json.dumps(auto, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Kainos: {gauta}/{len(urls)}, ~{kb:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
