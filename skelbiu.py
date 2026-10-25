#!/usr/bin/env python3
"""
Skelbiu.lt paieškų stebėjimas. Skelbiu.lt saugo Cloudflare, kuris paprastas HTTP užklausas blokuoja (403),
todėl naudojama tikra Chromium naršyklė per proxy: viena sesija visoms paieškoms, po vieną puslapį kiekvienai.
Nuotraukos, šriftai, stiliai ir trečiųjų šalių (reklamos, analitikos) užklausos blokuojami – saugomas tik
nuotraukos adresas. Nauji skelbimai atrenkami pagal raktažodžius ir
kainų ribas, istorija saugoma data/skelbimai.json, paleidimo būsena – data/busena.json.

Proxy: GitHub Secrets LUMINOR_PROXY_SERVER / _USERNAME / _PASSWORD (tokie pat vardai kaip pensijų projekte).
Formatai: HOST:PORT:USER:PASS, USER:PASS@HOST:PORT arba http://…
Sistema niekada nieko neperka, nerašo pardavėjams ir nededa skelbimų – tik skaito viešas paieškos puslapius.
"""
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SKELBIMAI = DATA / "skelbimai.json"
BUSENA = DATA / "busena.json"
PAVYZDYS = DATA / "pavyzdys.html"          # puslapio kopija, kai skelbimų nerasta (atpažinimui taisyti)
UA = ("Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/129.0.0.0 Mobile Safari/537.36")
BLOKAVIMO_ZYMES = ("cf-browser-verification", "challenge-platform", "cf_chl_", "Just a moment...",
                   "Attention Required! | Cloudflare", "captcha")


def dabar() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def proxy_url() -> str:
    server = os.getenv("LUMINOR_PROXY_SERVER", "").strip().strip("'\"")
    user = os.getenv("LUMINOR_PROXY_USERNAME", "").strip().strip("'\"")
    pw = os.getenv("LUMINOR_PROXY_PASSWORD", "").strip().strip("'\"")
    if not server:
        return ""
    schema = re.match(r"^[a-zA-Z][\w+.-]*://", server)
    parts = server.split(":")
    if len(parts) == 4 and parts[1].isdigit() and not schema:
        server, user, pw = f"{parts[0]}:{parts[1]}", user or parts[2], pw or parts[3]
    if "@" in server and not schema:
        auth, server = server.rsplit("@", 1)
        if ":" in auth and not user:
            user, pw = auth.split(":", 1)
    if not re.match(r"^[a-zA-Z][\w+.-]*://", server):
        server = "http://" + server
    if user and "@" not in server:
        p = urllib.parse.urlsplit(server)
        server = f"{p.scheme}://{urllib.parse.quote(user)}:{urllib.parse.quote(pw)}@{p.netloc}"
    return server


def paslepti(tekstas: str) -> str:
    """Žurnalas viešas – neatskleidžiame proxy adreso ir prisijungimo duomenų."""
    for name in ("LUMINOR_PROXY_SERVER", "LUMINOR_PROXY_USERNAME", "LUMINOR_PROXY_PASSWORD"):
        v = os.getenv(name, "").strip()
        if v:
            tekstas = tekstas.replace(v, "***")
    return tekstas


class Narsykle:
    """Viena Chromium sesija visoms paieškoms (Cloudflare patikra praeinama vieną kartą)."""
    LEIDZIAMI = ("skelbiu.lt", "challenges.cloudflare.com")

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        p = urllib.parse.urlsplit(proxy_url())
        self._pw = sync_playwright().start()
        self._br = self._pw.chromium.launch(
            headless=False, args=["--disable-blink-features=AutomationControlled"],
            proxy={"server": f"http://{p.hostname}:{p.port}", "username": urllib.parse.unquote(p.username or ""),
                   "password": urllib.parse.unquote(p.password or "")})
        ctx = self._br.new_context(locale="lt-LT", timezone_id="Europe/Vilnius", viewport={"width": 1366, "height": 800})
        self.page = ctx.new_page()
        self.baitai = 0
        self.page.route("**/*", self._filtras)
        self.page.on("response", self._skaiciuoti)
        return self

    def _filtras(self, route):
        r = route.request
        host = urllib.parse.urlsplit(r.url).hostname or ""
        if r.resource_type in ("image", "media", "font", "stylesheet") or not any(host.endswith(h) for h in self.LEIDZIAMI):
            return route.abort()
        return route.continue_()

    def _skaiciuoti(self, resp):
        try:
            self.baitai += int(resp.headers.get("content-length", "0"))
        except ValueError:
            pass

    def atidaryti(self, url: str, laukti: str = "standard-list-item") -> tuple[int, str, int]:
        pries = self.baitai
        resp = self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
        kodas = resp.status if resp else 0
        for _ in range(30):                    # Cloudflare patikra paprastai praeina per kelias sekundes
            html_ = self.page.content()
            if laukti in html_ or ("challenge-platform" not in html_ and "cf_chl_" not in html_):
                break
            time.sleep(1)
        html_ = self.page.content()
        if laukti in html_ or "standard-list-item" in html_:
            kodas = 200
        return kodas, html_, self.baitai - pries

    def __exit__(self, *a):
        self._br.close()
        self._pw.stop()


def kaina_is(tekstas: str):
    m = re.search(r"(\d[\d\s .]*(?:,\d{1,2})?)\s*(?:€|EUR|&euro;)", tekstas)
    if not m:
        return None
    s = re.sub(r"[\s .]", "", m.group(1)).replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def svarus(t: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t))).strip()


def _klase(blokas: str, klase: str) -> str:
    m = re.search(r'<div class="' + klase + r'">(.*?)</div>', blokas, re.S)
    return svarus(m.group(1)) if m else ""


def atpazinti(puslapis: str) -> list[dict]:
    """Skelbimų kortelės: <a ... class="js-cfuser-link standard-list-item" data-item-id="ID"> ... </a>."""
    rasti = []
    for m in re.finditer(r'<a href="(/skelbimai/[^"]+?-(\d+)\.html)"[^>]*class="js-cfuser-link standard-list-item[^"]*"'
                         r'[^>]*>(.*?)</a>\s*</div>', puslapis, re.S):
        nuoroda, sid, blokas = m.groups()
        img = re.search(r'<img src="(https://[^"]+)"', blokas)
        parametrai = [svarus(x) for x in re.findall(r'<div class="param">(.*?)</div>', blokas, re.S)]
        rasti.append({
            "id": sid,
            "nuoroda": "https://www.skelbiu.lt" + nuoroda,
            "pavadinimas": _klase(blokas, "title"),
            "kaina": kaina_is(_klase(blokas, "price")),
            "nuotrauka": img.group(1) if img else "",
            "aprasymas": _klase(blokas, "first-dataline")[:500],
            "vieta_laikas": _klase(blokas, "second-dataline") or _klase(blokas, "second-line"),
            "parametrai": parametrai,
        })
    return rasti


def tinka(s: dict, p: dict, visada_isimti: list[str]) -> tuple[bool, str]:
    tekstas = (s["pavadinimas"] + " " + s["aprasymas"]).lower()
    for z in visada_isimti + p.get("isimti", []):
        if z.lower() in tekstas:
            return False, f"išimtas žodis „{z}“"
    rz = [z.lower() for z in p.get("raktazodziai", [])]
    if rz and not any(z in tekstas for z in rz):
        return False, "nėra raktažodžio"
    k = s["kaina"]
    if k is None:
        return False, "nėra kainos"
    if p.get("min_kaina") is not None and k < p["min_kaina"]:
        return False, "per pigu"
    if p.get("max_kaina") is not None and k > p["max_kaina"]:
        return False, "per brangu"
    return True, ""


def skaityti(kelias: Path, numatyta):
    try:
        return json.loads(kelias.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return numatyta


def main() -> int:
    DATA.mkdir(exist_ok=True)
    cfg = json.loads((ROOT / "paieskos.json").read_text(encoding="utf-8"))
    istorija = skaityti(SKELBIMAI, {})
    proxy = proxy_url()
    laikas = dabar()
    busena = {"paleista": laikas, "proxy": bool(proxy), "paieskos": []}
    if not proxy:
        print("ĮSPĖJIMAS: proxy nenurodytas (Secrets LUMINOR_PROXY_SERVER tuščias) – užklausų nesiunčiu.")
        busena["klaida"] = "proxy nenurodytas"
        BUSENA.write_text(json.dumps(busena, ensure_ascii=False, indent=1), encoding="utf-8")
        return 1

    with Narsykle() as nar:
        for i, p in enumerate(cfg["paieskos"]):
            apdoroti(nar, i, p, cfg, istorija, busena, laikas)
        busena["detales"] = detales(nar, istorija)
    busena["kb_per_proxy_viso"] = round(sum(b.get("kb_per_proxy") or 0 for b in busena["paieskos"]), 1)
    SKELBIMAI.write_text(json.dumps(istorija, ensure_ascii=False, indent=1), encoding="utf-8")
    BUSENA.write_text(json.dumps(busena, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if any(b.get("kodas") == 200 and b.get("rasta_skelbimu") for b in busena["paieskos"]) else 1


MAX_DETALIU = 6          # skelbimo puslapių per paleidimą – tik perspektyviausiems, kad būtų mažai užklausų


def detales(nar, istorija: dict) -> dict:
    """Atidaro perspektyviausių (pigiausių, palyginti su to paties modelio mediana) skelbimų puslapius ir pasiima
    pilną aprašymą bei būklę – iš jų analizė ieško defektų ir privalumų."""
    import statistics
    from analize import modelio_raktas
    kainos: dict[str, list[float]] = {}
    for s in istorija.values():
        s["_r"] = modelio_raktas(s)
        if s.get("kaina"):
            kainos.setdefault(s["_r"], []).append(s["kaina"])
    kandidatai = []
    for s in istorija.values():
        if not s.get("tinka") or "pilnas_aprasymas" in s or not s.get("kaina"):
            continue
        k = kainos.get(s["_r"], [])
        santykis = s["kaina"] / statistics.median(k) if len(k) >= 3 else 0.9
        if santykis <= 0.9:
            kandidatai.append((santykis, s))
    kandidatai.sort(key=lambda x: x[0])
    rez = {"atidaryta": 0, "kb_per_proxy": 0.0}
    for _, s in kandidatai[:MAX_DETALIU]:
        try:
            kodas, html_, baitai = nar.atidaryti(s["nuoroda"], laukti="description")
        except Exception as e:  # noqa: BLE001
            print(f"Detalės {s['id']}: {paslepti(str(e))[:120]}")
            continue
        rez["atidaryta"] += 1
        rez["kb_per_proxy"] += round(baitai / 1024, 1)
        if not (DATA / "detale_pavyzdys.html").exists():
            (DATA / "detale_pavyzdys.html").write_text(html_, encoding="utf-8")
        s.update(atpazinti_detales(html_))
        s["detales_gautos"] = dabar()
    for s in istorija.values():
        s.pop("_r", None)
    print(f"Detalės: {rez}")
    return rez


def atpazinti_detales(h: str) -> dict:
    out = {}
    m = (re.search(r'itemprop="description"[^>]*>(.*?)</(?:div|p|span)>', h, re.S)
         or re.search(r'<div[^>]+class="[^"]*\bdescription\b[^"]*"[^>]*>(.*?)</div>', h, re.S)
         or re.search(r'<meta property="og:description" content="([^"]*)"', h))
    out["pilnas_aprasymas"] = svarus(m.group(1))[:2000] if m else ""
    b = re.search(r"Būklė:?\s*</?[^>]*>?\s*([A-Za-zĄČĘĖĮŠŲŪŽąčęėįšųūž ]{3,30})", h)
    if b:
        out["bukle"] = svarus(b.group(1))
    return out


def apdoroti(nar, i, p, cfg, istorija, busena, laikas):
    b = {"pavadinimas": p["pavadinimas"]}
    try:
        kodas, puslapis, baitai = nar.atidaryti(p["url"])
    except Exception as e:  # noqa: BLE001
        b.update(kodas=None, klaida=paslepti(f"{e.__class__.__name__}: {e}"))
        print(f"[{p['pavadinimas']}] nepavyko: {b['klaida']}")
        busena["paieskos"].append(b)
        return
    rasti = atpazinti(puslapis) if kodas == 200 else []
    blokuota = [] if rasti else [z for z in BLOKAVIMO_ZYMES if z.lower() in puslapis.lower()]
    if not rasti:                              # kopija tik nesėkmei tirti (kad repo nepūstų kas valandą)
        PAVYZDYS.write_text(puslapis, encoding="utf-8")
    t = re.search(r"<title>(.*?)</title>", puslapis, re.S)
    b.update(kodas=kodas, kb_per_proxy=round(baitai / 1024, 1), puslapio_pavadinimas=svarus(t.group(1)) if t else "",
             blokavimo_zymes=blokuota, rasta_skelbimu=len(rasti), nauju=0, atrinkta_nauju=0)
    for s in rasti:
        ok, priezastis = tinka(s, p, cfg.get("visada_isimti", []))
        senas = istorija.get(s["id"])
        if senas:
            senas["paskutini_karta_matytas"] = laikas
            if s["kaina"] is not None and s["kaina"] != senas.get("kaina"):
                senas.setdefault("kainu_istorija", []).append([laikas, s["kaina"]])
                senas["kaina"] = s["kaina"]
            continue
        b["nauju"] += 1
        b["atrinkta_nauju"] += int(ok)
        istorija[s["id"]] = {**s, "paieska": p["pavadinimas"], "pastebetas": laikas,
                             "paskutini_karta_matytas": laikas, "tinka": ok, "atmesta_nes": priezastis}
    print(f"[{p['pavadinimas']}] HTTP {kodas}, {b['kb_per_proxy']} KB, skelbimų {len(rasti)}, "
          f"naujų {b['nauju']} (atrinkta {b['atrinkta_nauju']})" + (f", BLOKAVIMAS: {blokuota}" if blokuota else ""))
    busena["paieskos"].append(b)
    time.sleep(2)


if __name__ == "__main__":
    sys.exit(main())
