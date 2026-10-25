#!/usr/bin/env python3
"""
Radinių analizė: kiekvienam atrinktam skelbimui apskaičiuoja tikėtiną pardavimo kainą, pelną, maksimalią pirkimo
kainą, patikimumą, sprendimą ir balą reitingui.

Kainos šaltiniai (pagal svarbą):
  1. Claude vertinimas (vertinimai.json, kasdienė rutina): modelis, naujo daikto kaina ES su siuntimu, tikėtina
     pardavimo kaina, skelbimo tekstas.
  2. Panašūs skelbimai iš sukauptos istorijos (tas pats modelio raktas): prašomų kainų mediana × 0,9,
     nes realiai parduodama pigiau nei prašoma.
  3. Naujo daikto kaina × 0,85 – lubos: naudoto niekas nepirks brangiau nei naujo.

Naudojimas: python analize.py [vertinimai.json] [išvestis.json]
"""
import json
import re
import statistics
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKELBIMAI = ROOT / "data" / "skelbimai.json"

KASTAI = 6.0              # kelionė / siuntimas, kai daiktą parsivežu (€)
VALANDOS = 1.5            # mano laikas vienam sandoriui: nuvažiuoti, nufotografuoti, įdėti, parduoti
MIN_PELNAS = 20.0         # mažiau neverta mano laiko
MIN_ROI = 0.35            # pelnas / pirkimo kaina
NUOLAIDA_PARDAVIMUI = 0.9 # prašoma kaina → tikėtina pardavimo kaina
NAUJO_LUBOS = 0.85        # naudotas daiktas ≤ 85 % naujo kainos
SVIEZUMAS_VAL = 72        # rodyti skelbimus, pastebėtus per paskutines N valandų

# Žodžiai, rodantys, kad tai ne pats daiktas, o priedas / žaidimas / rinkinys – kitas modelio raktas.
PRIEDAI = ("žaidim", "zaidim", "pultel", "joy-con", "joycon", "dėkl", "dekl", "vairas", "kroviklis", "pakroveja",
           "pakrovėja", "dirželis", "dirzelis", "adapter", "baterij", "akumuliatorius ", "stiklas", "plėvel")


def be_diakritiku(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", t.lower()) if not unicodedata.combining(c))


def modelio_raktas(s: dict) -> str:
    """Iš pavadinimo išgauna palyginamą modelio raktą, pvz. lego-42125, makita-dtd152, switch-oled, garmin-fenix-7x."""
    p = be_diakritiku(s.get("pavadinimas", ""))
    a = be_diakritiku(s.get("aprasymas", ""))
    paieska = be_diakritiku(s.get("paieska", ""))
    priedas = any(be_diakritiku(z) in p for z in PRIEDAI)

    if "lego" in paieska:
        m = re.search(r"\b(\d{5,6}|\d{4})\b", p) or re.search(r"\b(\d{5,6})\b", a)
        if m and not (len(m.group(1)) == 4 and 1990 <= int(m.group(1)) <= 2035):
            return "lego-" + m.group(1)
        return "lego-rinkinys"
    if "makita" in paieska:
        m = re.search(r"\b([a-z]{2,4})\s?(\d{3,4})[a-z]*\b", p)
        if m and m.group(1) not in ("mm", "kw", "v", "ah"):
            return "makita-" + m.group(1) + m.group(2)
        return "makita-" + ("priedas" if priedas else "kita")
    if "switch" in paieska or "nintendo" in paieska:
        konsole = re.search(r"switch\s*(su\b|\+)|konsol|\bv[12]\b|oled|lite|atrist", p)
        zaidimas = re.search(r"\b(zelda|mario|splatoon|minecraft|pokemon)\b", p) and not p.startswith("nintendo")
        if (priedas or zaidimas) and not konsole:
            return "switch-priedai"
        if re.search(r"switch\s*2\b", p):
            return "switch-2"
        if "oled" in p:
            return "switch-oled"
        if "lite" in p:
            return "switch-lite"
        return "switch-v1"
    if "garmin" in paieska:
        m = re.search(r"\b(fenix|venu|forerunner|instinct|epix|tactix|vivoactive|edge|enduro|hrm|zumo)\s*([a-z]*\s?\d+[a-z]?|crossover|sq)?", p)
        if m:
            return "garmin-" + m.group(1) + ("-" + m.group(2).replace(" ", "") if m.group(2) else "")
        return "garmin-kita"
    zodziai = [z for z in re.findall(r"[a-z0-9]{3,}", p)][:3]
    return "-".join(zodziai) or "nezinoma"


def palyginami(raktas: str, sid: str, visi: list[dict]) -> list[float]:
    kainos = [s["kaina"] for s in visi if s["_raktas"] == raktas and s["id"] != sid and s.get("kaina")
              and not re.search(r"\b(perku|pirksiu|pirkciau|supirk)", be_diakritiku(s["pavadinimas"]))]
    if len(kainos) >= 3:                      # išmetame aiškias išskirtis (klaidingos kainos, rinkiniai)
        med = statistics.median(kainos)
        kainos = [k for k in kainos if med / 3 <= k <= med * 3]
    return kainos


def ivertinti(s: dict, visi: list[dict], claude: dict | None) -> dict:
    kaina = s.get("kaina") or 0
    raktas = s["_raktas"]
    komp = palyginami(raktas, s["id"], visi)
    med = statistics.median(komp) if len(komp) >= 3 else None     # 1–2 skelbimai – ne rinka, o atsitiktinumas
    sklaida = (statistics.quantiles(komp, n=4)[2] - statistics.quantiles(komp, n=4)[0]) / med if len(komp) >= 4 and med else None

    saltiniai = []
    pardavimo = None
    if med:
        pardavimo = med * NUOLAIDA_PARDAVIMUI
        saltiniai.append(f"{len(komp)} panašių skelbimų mediana {med:.0f} €")
    naujo = (claude or {}).get("naujo_kaina")
    if claude and claude.get("tiketina_pardavimo"):
        pardavimo = float(claude["tiketina_pardavimo"])
        saltiniai.insert(0, "Claude įvertinimas")
    if naujo:
        lubos = float(naujo) * NAUJO_LUBOS
        saltiniai.append(f"naujas ES ~{float(naujo):.0f} €")
        if pardavimo is None or pardavimo > lubos:
            pardavimo = lubos

    # Patikimumas: Claude jį nustato pats; kitaip – pagal palyginamų kiekį ir sklaidą.
    if claude and claude.get("patikimumas"):
        patik = claude["patikimumas"]
    elif len(komp) >= 8 and (sklaida is None or sklaida < 0.5):
        patik = "aukštas"
    elif len(komp) >= 4 or naujo:
        patik = "vidutinis"
    else:
        patik = "žemas"
    if raktas.endswith(("-kita", "-rinkinys", "-priedai", "-priedas")) and not claude:
        patik = "žemas"         # nevienalytė grupė (pjūklas ir įrankių rinkinys) – mediana nieko nesako

    r = {"modelis": (claude or {}).get("modelis") or raktas, "raktas": raktas, "palyginamu": len(komp),
         "mediana": round(med) if med else None, "naujo_kaina": naujo, "patikimumas": patik,
         "saltiniai": saltiniai}
    if pardavimo is None or not kaina:
        r.update(tiketina_pardavimo=None, pelnas=None, roi=None, max_pirkimo=None, pelnas_per_val=None,
                 sprendimas="tikrinti" if not kaina else "nežinoma",
                 priezastis="nėra kainos" if not kaina else "per mažai panašių skelbimų – įvertins Claude", balas=0)
    else:
        pelnas = pardavimo - kaina - KASTAI
        roi = pelnas / kaina
        max_pirkimo = min((pardavimo - KASTAI) / (1 + MIN_ROI), pardavimo - KASTAI - MIN_PELNAS)
        if pelnas >= MIN_PELNAS and roi >= MIN_ROI and patik != "žemas":
            spr, prz = "verta", f"pelnas ~{pelnas:.0f} € ({roi:.0%})"
        elif pelnas >= MIN_PELNAS and roi >= MIN_ROI:
            spr, prz = "tikrinti", "atrodo pelninga, bet per mažai duomenų – patikrink kainą pats"
        elif patik != "žemas" and max_pirkimo > 0 and kaina - max_pirkimo <= max(15, kaina * 0.25):
            spr, prz = "derėtis", f"verta tik nusiderėjus iki {max_pirkimo:.0f} €"
        else:
            spr, prz = "praleisti", "per brangu perpardavimui"
        svoris = {"aukštas": 1.0, "vidutinis": 0.75, "žemas": 0.4}.get(patik, 0.5)
        balas = max(0.0, min(100.0, (pelnas / VALANDOS) * 1.2 * svoris + roi * 30 * svoris))
        r.update(tiketina_pardavimo=round(pardavimo), pelnas=round(pelnas), roi=round(roi, 2),
                 max_pirkimo=round(max_pirkimo) if max_pirkimo > 0 else 0,
                 pelnas_per_val=round(pelnas / VALANDOS), sprendimas=spr, priezastis=prz, balas=round(balas))
    if claude:
        for k in ("sprendimas", "priezastis", "skelbimo_tekstas", "rizikos", "ivertinta", "stovas", "naujo_saltinis"):
            if claude.get(k):
                r[k] = claude[k]
    return r


def main() -> int:
    vert_kelias = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "vertinimai.json"
    isvestis = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "docs" / "analize.json"
    istorija = json.loads(SKELBIMAI.read_text(encoding="utf-8"))
    try:
        vertinimai = json.loads(vert_kelias.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        vertinimai = {}
    visi = list(istorija.values())
    for s in visi:
        s["_raktas"] = modelio_raktas(s)
    riba = (datetime.now(timezone.utc) - timedelta(hours=SVIEZUMAS_VAL)).strftime("%Y-%m-%dT%H:%M:%SZ")
    radiniai = []
    for s in visi:
        if not s.get("tinka") or s.get("pastebetas", "") < riba:
            continue
        a = ivertinti(s, visi, vertinimai.get(s["id"]))
        radiniai.append({k: s.get(k) for k in ("id", "nuoroda", "pavadinimas", "kaina", "nuotrauka", "aprasymas",
                                               "vieta_laikas", "paieska", "pastebetas", "parametrai")} | a)
    tvarka = {"verta": 0, "derėtis": 1, "tikrinti": 2, "nežinoma": 3, "praleisti": 4}
    radiniai.sort(key=lambda r: (tvarka.get(r["sprendimas"], 9), -(r["balas"] or 0)))
    rinka = {}
    for s in visi:
        if s.get("kaina"):
            rinka.setdefault(s["_raktas"], []).append(s["kaina"])
    out = {"sugeneruota": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "prielaidos": {"kastai": KASTAI, "valandos": VALANDOS, "min_pelnas": MIN_PELNAS, "min_roi": MIN_ROI},
           "skelbimu_istorijoje": len(visi), "radiniai": radiniai,
           "rinka": {k: {"n": len(v), "mediana": round(statistics.median(v))} for k, v in rinka.items() if len(v) >= 2}}
    isvestis.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    print(f"Radinių: {len(radiniai)}", dict(Counter(r["sprendimas"] for r in radiniai)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
