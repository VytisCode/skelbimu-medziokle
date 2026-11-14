#!/usr/bin/env python3
"""Vienkartinis patikrinimas: kurias parduotuves / nuolaidų svetaines galima mandagiai atidaryti per LT proxy.
Kaip kainos.py: tikras roboto vardas, laikosi robots.txt, viena GET užklausa, jokio apsaugų apėjimo. Nieko nesaugo."""
import re, sys, time, urllib.error, urllib.parse, urllib.request, urllib.robotparser
from skelbiu import proxy_url

UA = "skelbimu-medziokle-kainos/1.0 (+https://github.com/VytisCode/skelbimu-medziokle)"
URLS = """
https://www.amazon.pl/gp/bestsellers/diy
https://www.amazon.fr/gp/bestsellers/diy
https://www.amazon.it/gp/bestsellers/diy
https://www.amazon.es/gp/bestsellers/diy
https://www.amazon.nl/gp/bestsellers/diy
https://www.amazon.se/gp/bestsellers/diy
https://camelcamelcamel.com/top_drops?locale=DE
https://de.camelcamelcamel.com/top_drops
https://www.pepper.nl/
https://www.chollometro.com/
https://www.preisjaeger.at/
https://www.pepper.it/
https://www.hotukdeals.com/
https://geizhals.eu/
https://www.idealo.fr/
https://www.idealo.it/
https://www.idealo.es/
https://www.alza.de/
https://www.bergfreunde.de/
https://www.bike24.de/
https://www.notebooksbilliger.de/
https://www.polo-motorrad.com/de-de/
https://www.motoin.de/
https://www.mediamarkt.de/
https://www.decathlon.de/
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
