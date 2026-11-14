#!/usr/bin/env python3
"""Vienkartinis patikrinimas: kurias parduotuves / nuolaidų svetaines galima mandagiai atidaryti per LT proxy.
Kaip kainos.py: tikras roboto vardas, laikosi robots.txt, viena GET užklausa, jokio apsaugų apėjimo. Nieko nesaugo."""
import re, sys, time, urllib.error, urllib.parse, urllib.request, urllib.robotparser
from skelbiu import proxy_url

UA = "skelbimu-medziokle-kainos/1.0 (+https://github.com/VytisCode/skelbimu-medziokle)"
URLS = """
https://www.mydealz.de/gruppe/motorrad
https://www.mydealz.de/gruppe/werkzeug
https://www.pepper.pl/
https://www.dealabs.com/
https://geizhals.de/?cat=wzakkuschr
https://www.idealo.de/preisvergleich/MainSearchProductCategory.html?q=makita+ddf482z
https://www.ceneo.pl/;szukaj-makita+ddf482z
https://www.amazon.de/gp/bestsellers/diy
https://www.24mx.lt/
https://www.24mx.de/
https://www.xlmoto.de/
https://www.louis.de/
https://www.fc-moto.de/
https://www.ebay.de/sch/i.html?_nkw=xj6+windschild
https://allegro.pl/listing?string=xj6%20szyba
https://www.kleinanzeigen.de/s-xj6-windschild/k0
https://www.vinted.lt/catalog?search_text=makita
https://www.motomoto24.com/
https://www.kaina24.lt/
https://www.kainos.lt/
https://pigu.lt/lt/
https://www.varle.lt/
https://www.skelbiu.lt/
""".split()
MARK = ("captcha", "cf-challenge", "challenge-platform", "access denied", "robot check", "are you a human", "px-captcha", "datadome")

def main():
    px = proxy_url()
    op = urllib.request.build_opener(*( [urllib.request.ProxyHandler({"http": px, "https": px})] if px else []))
    print(f"proxy={'taip' if px else 'NE'}")
    viso = 0
    for u in URLS:
        p = urllib.parse.urlparse(u)
        rob = f"{p.scheme}://{p.netloc}/robots.txt"
        r = "?"
        try:
            t = op.open(urllib.request.Request(rob, headers={"User-Agent": UA}), timeout=20).read(300_000).decode("utf-8", "ignore")
            rp = urllib.robotparser.RobotFileParser(); rp.parse(t.splitlines())
            r = "leidžia" if rp.can_fetch(UA, u) else "DRAUDŽIA"
        except Exception as e:
            r = f"robots klaida {type(e).__name__} {getattr(e,'code','')}"
        if r == "DRAUDŽIA":
            print(f"{p.netloc:28} robots.txt DRAUDŽIA – neatidaryta"); continue
        try:
            resp = op.open(urllib.request.Request(u, headers={"User-Agent": UA, "Accept-Language": "lt,en;q=0.8"}), timeout=30)
            h = resp.read(3_000_000); kod = resp.status
        except urllib.error.HTTPError as e:
            h = e.read(200_000) if hasattr(e, "read") else b""; kod = e.code
        except Exception as e:
            print(f"{p.netloc:28} KLAIDA {type(e).__name__}"); continue
        viso += len(h)
        s = h.decode("utf-8", "ignore")
        tit = re.search(r"<title[^>]*>(.*?)</title>", s, re.S | re.I)
        zym = [m for m in MARK if m in s.lower()]
        kainos = len(re.findall(r"\d+[.,]\d{2}\s?(?:€|EUR|zł)", s))
        print(f"{p.netloc:28} HTTP {kod} {len(h)//1024:5} KB kainų~{kainos:4} robots:{r} žymės:{zym} title:{(tit.group(1).strip()[:60] if tit else '-')!r}")
        time.sleep(2)
    print(f"Iš viso per proxy ~{viso//1024} KB")

if __name__ == "__main__":
    sys.exit(main())
