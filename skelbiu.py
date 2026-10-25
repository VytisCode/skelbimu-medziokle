#!/usr/bin/env python3
"""
Skelbiu.lt paieškų stebėjimas. Kiekvienai paieškai iš paieskos.json – VIENA lengva HTTP užklausa per proxy
(be naršyklės, be nuotraukų: saugomas tik nuotraukos adresas). Nauji skelbimai atrenkami pagal raktažodžius ir
kainų ribas, istorija saugoma data/skelbimai.json, paleidimo būsena – data/busena.json.

Proxy: GitHub Secrets LUMINOR_PROXY_SERVER / _USERNAME / _PASSWORD (tokie pat vardai kaip pensijų projekte).
Formatai: HOST:PORT:USER:PASS, USER:PASS@HOST:PORT arba http://…
Sistema niekada nieko neperka, nerašo pardavėjams ir nededa skelbimų – tik skaito viešas paieškos puslapius.
"""
import gzip
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
PAVYZDYS = DATA / "pavyzdys.html"          # pirmo puslapio kopija, kad būtų galima pataisyti atpažinimą
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


def parsisiusti(url: str, proxy: str) -> tuple[int, str, int]:
    """Grąžina (HTTP kodas, HTML, gautų baitų kiekis per proxy)."""
    handlers = [urllib.request.ProxyHandler({"http": proxy, "https": proxy} if proxy else {})]
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "lt-LT,lt;q=0.9",
        "Accept-Encoding": "gzip",
    })
    try:
        with opener.open(req, timeout=40) as r:
            raw = r.read()
            kodas = r.status
            enc = r.headers.get("Content-Encoding", "")
    except urllib.error.HTTPError as e:
        raw = e.read() or b""
        kodas = e.code
        enc = e.headers.get("Content-Encoding", "") if e.headers else ""
    baitai = len(raw)
    if enc == "gzip":
        raw = gzip.decompress(raw)
    return kodas, raw.decode("utf-8", "replace"), baitai


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


def atpazinti(puslapis: str) -> list[dict]:
    """Ieško skelbimų nuorodų /skelbimai/...-ID.html ir aplink jas esančios kainos, nuotraukos, pavadinimo.
    Atpažinimas sąmoningai paprastas: po pirmo tikro paleidimo bus pataisytas pagal data/pavyzdys.html."""
    rasti: dict[str, dict] = {}
    for m in re.finditer(r'href="((?:https://www\.skelbiu\.lt)?/skelbimai/[^"#?]*?-(\d{6,})\.html)"', puslapis):
        nuoroda, sid = m.group(1), m.group(2)
        if not nuoroda.startswith("http"):
            nuoroda = "https://www.skelbiu.lt" + nuoroda
        # skelbimo „kortelė“: tekstas nuo šios nuorodos iki kitos kito skelbimo nuorodos (ne daugiau 4000 simb.)
        pab = puslapis.find('/skelbimai/', m.end() + 200)
        blokas = puslapis[max(0, m.start() - 1500): (pab if 0 < pab < m.end() + 4000 else m.end() + 4000)]
        irasas = rasti.setdefault(sid, {"id": sid, "nuoroda": nuoroda, "pavadinimas": "", "kaina": None,
                                        "nuotrauka": "", "aprasymas": ""})
        po = puslapis[m.end(): m.end() + 2500]
        if not irasas["pavadinimas"]:
            t = re.search(r'title="([^"]{4,200})"', puslapis[m.start(): m.start() + 600])
            h = re.search(r"<h[1-4][^>]*>(.*?)</h[1-4]>", po, re.S)
            irasas["pavadinimas"] = svarus(t.group(1) if t else (h.group(1) if h else ""))
        if irasas["kaina"] is None:
            irasas["kaina"] = kaina_is(svarus(po))
        if not irasas["nuotrauka"]:
            img = re.search(r'(?:data-src|src)="(https://[^"]+\.(?:jpe?g|webp|png)[^"]*)"', blokas)
            irasas["nuotrauka"] = img.group(1) if img else ""
        if not irasas["aprasymas"]:
            d = re.search(r'class="[^"]*(?:description|text)[^"]*"[^>]*>(.*?)</', po, re.S)
            irasas["aprasymas"] = svarus(d.group(1))[:400] if d else ""
    return list(rasti.values())


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

    matyti_dabar: set[str] = set()
    for i, p in enumerate(cfg["paieskos"]):
        b = {"pavadinimas": p["pavadinimas"]}
        try:
            kodas, puslapis, baitai = parsisiusti(p["url"], proxy)
        except Exception as e:  # noqa: BLE001
            b.update(kodas=None, klaida=paslepti(f"{e.__class__.__name__}: {e}"))
            print(f"[{p['pavadinimas']}] nepavyko: {b['klaida']}")
            busena["paieskos"].append(b)
            continue
        blokuota = [z for z in BLOKAVIMO_ZYMES if z.lower() in puslapis.lower()]
        rasti = atpazinti(puslapis) if kodas == 200 else []
        if i == 0:
            PAVYZDYS.write_text(puslapis, encoding="utf-8")
        t = re.search(r"<title>(.*?)</title>", puslapis, re.S)
        b.update(kodas=kodas, kb_per_proxy=round(baitai / 1024, 1), puslapio_pavadinimas=svarus(t.group(1)) if t else "",
                 blokavimo_zymes=blokuota, rasta_skelbimu=len(rasti), nauju=0, atrinkta_nauju=0)
        for s in rasti:
            matyti_dabar.add(s["id"])
            ok, priezastis = tinka(s, p, cfg.get("visada_isimti", []))
            senas = istorija.get(s["id"])
            if senas:
                senas["paskutini_karta_matytas"] = laikas
                senas.pop("dingo", None)
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
        time.sleep(3)

    # „Dingo“ – tik spėjimas: stebime pirmą paieškos puslapį, todėl skelbimas gali būti tiesiog nustumtas žemiau.
    for sid, s in istorija.items():
        if sid not in matyti_dabar and "dingo" not in s:
            s["dingo"] = laikas

    SKELBIMAI.write_text(json.dumps(istorija, ensure_ascii=False, indent=1), encoding="utf-8")
    BUSENA.write_text(json.dumps(busena, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if any(b.get("kodas") == 200 and b.get("rasta_skelbimu") for b in busena["paieskos"]) else 1


if __name__ == "__main__":
    sys.exit(main())
