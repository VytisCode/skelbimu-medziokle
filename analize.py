#!/usr/bin/env python3
"""
Radinių analizė: kiekvienam atrinktam skelbimui apskaičiuoja tikėtiną pardavimo kainą, visus kaštus (atsiėmimas
ar siunta pagal miestą, pakuotė), pelną, maksimalią pirkimo kainą, patikimumą, sprendimą ir balą reitingui.
Kiekvienas skaičius turi „įrodymus“: panašių skelbimų sąrašą su nuorodomis ir skaičiavimo žingsnius.

Kainos šaltiniai (pagal svarbą):
  1. Claude vertinimas (vertinimai.json, kasdienė rutina): modelis, naujo daikto kainos parduotuvėse su nuorodomis,
     tikėtina pardavimo kaina, skelbimo tekstas.
  2. Panašūs skelbimai iš sukauptos istorijos (tas pats modelio raktas): prašomų kainų mediana × nuolaida,
     nes realiai parduodama pigiau nei prašoma.
  3. Naujo daikto kaina × lubos: naudoto niekas nepirks brangiau nei naujo.

Prielaidos – nustatymai.json. Naudojimas: python analize.py [vertinimai.json] [išvestis.json]
"""
import json
import re
import statistics
import sys
import unicodedata
import urllib.parse
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKELBIMAI = ROOT / "data" / "skelbimai.json"
N = json.loads((ROOT / "nustatymai.json").read_text(encoding="utf-8"))
PAIESKOS = {p["pavadinimas"]: p for p in json.loads((ROOT / "paieskos.json").read_text(encoding="utf-8"))["paieskos"]}
SVIEZUMAS_VAL = 72        # rodyti skelbimus, pastebėtus per paskutines N valandų

# Žodžiai, rodantys, kad tai ne pats daiktas, o priedas / žaidimas – kitas modelio raktas.
PRIEDAI = ("žaidim", "zaidim", "pultel", "joy-con", "joycon", "dėkl", "dekl", "vairas", "kroviklis", "pakroveja",
           "pakrovėja", "dirželis", "dirzelis", "adapter", "baterij", "stiklas", "plėvel", "laikikl", "propeler")


def be_diakritiku(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", (t or "").lower()) if not unicodedata.combining(c))


def eur(x: float) -> str:
    return f"{x:,.1f}".rstrip("0").rstrip(".").replace(",", " ").replace(".", ",") + " €"


def modelio_raktas(s: dict) -> str:
    """Iš pavadinimo išgauna palyginamą modelio raktą, pvz. lego-42125, makita-dtd152, switch-oled, garmin-fenix-7x."""
    p = be_diakritiku(s.get("pavadinimas"))
    a = be_diakritiku(s.get("aprasymas"))
    paieska = be_diakritiku(s.get("paieska"))
    priedas = any(be_diakritiku(z) in p for z in PRIEDAI)

    if "lego" in paieska:
        m = re.search(r"\b(\d{5,6}|\d{4})\b", p) or re.search(r"\b(\d{5,6})\b", a)
        if m and not (len(m.group(1)) == 4 and 1990 <= int(m.group(1)) <= 2035):
            return "lego-" + m.group(1)
        return "lego-rinkinys"
    for gam in ("makita", "dewalt", "milwaukee"):
        if gam in paieska:
            m = re.search(r"\b([a-z]{1,4})\s?-?(\d{3,4})[a-z]*\b", p)
            if m and m.group(1) not in ("mm", "kw", "v", "ah", "w", "nm"):
                return f"{gam}-{m.group(1)}{m.group(2)}"
            return f"{gam}-" + ("priedas" if priedas else "kita")
    if "switch" in paieska or "nintendo" in paieska:
        if "switch" not in p and "nintendo" not in p:
            return "switch-kita"          # kitų gamintojų konsolės (pvz. Retroid) – ne Switch rinka
        konsole = re.search(r"switch\s*(su\b|\+)|konsol|\bv[12]\b|oled|lite|atrist", p)
        zaidimas = re.search(r"\b(zelda|mario|splatoon|minecraft|pokemon)\b", p) and not p.startswith("nintendo")
        if (priedas or zaidimas) and not konsole:
            return "switch-priedai"
        if re.search(r"switch\s*2\b", p):
            return "switch-2"
        return "switch-oled" if "oled" in p else "switch-lite" if "lite" in p else "switch-v1"
    if "playstation" in paieska:
        if not re.search(r"ps\s?5|playstation", p):
            return "ps5-kita"
        if (priedas or "zaidim" in p) and not re.search(r"konsol|\bsu\b|\+|825|1tb|digital|disc|slim|pro\b", p):
            return "ps5-priedai"
        return "ps5-pro" if re.search(r"\bpro\b", p) else "ps5-digital" if "digital" in p else "ps5-slim" if "slim" in p else "ps5"
    if "garmin" in paieska:
        m = re.search(r"\b(fenix|venu|forerunner|instinct|epix|tactix|vivoactive|edge|enduro|hrm|zumo)\s*([a-z]*\s?\d+[a-z]?|crossover|sq)?", p)
        if m:
            return "garmin-" + m.group(1) + ("-" + m.group(2).replace(" ", "") if m.group(2) else "")
        return "garmin-kita"
    if "kindle" in paieska:
        m = re.search(r"\b(paperwhite|oasis|scribe|colorsoft|basic)\b", p)
        return "kindle-" + (m.group(1) if m else ("priedai" if priedas else "kita"))
    if "gopro" in paieska:
        m = re.search(r"hero\s?(\d{1,2})|\b(max|mini)\b", p)
        return "gopro-" + ((m.group(1) or m.group(2)) if m else ("priedai" if priedas else "kita"))
    if "dji" in paieska:
        m = re.search(r"\b(mini\s?\d(\s?pro)?|air\s?\d[s]?|avata\s?\d?|osmo\s?\w+|neo|flip|mavic\s?\w+|action\s?\d)\b", p)
        return "dji-" + (m.group(1).replace(" ", "") if m else ("priedai" if priedas else "kita"))
    zodziai = re.findall(r"[a-z0-9]{3,}", p)[:3]
    return "-".join(zodziai) or "nezinoma"


def paieskos_fraze(s: dict, raktas: str, claude: dict | None) -> str:
    if claude and claude.get("modelis"):
        return claude["modelis"]
    if raktas.endswith(("-kita", "-rinkinys", "-priedai", "-priedas")):
        return re.sub(r"\s+", " ", s.get("pavadinimas", ""))[:60]
    return raktas.replace("-", " ").replace("switch ", "nintendo switch ")


def parduotuviu_nuorodos(fraze: str) -> list[dict]:
    q = urllib.parse.quote_plus(fraze)
    return [{"pavadinimas": "kaina24.lt", "url": f"https://www.kaina24.lt/search?q={q}"},
            {"pavadinimas": "pigu.lt", "url": f"https://pigu.lt/lt/search?q={q}"},
            {"pavadinimas": "idealo.de (ES)", "url": f"https://www.idealo.de/preisvergleich/MainSearchProductCategory.html?q={q}"},
            {"pavadinimas": "Google Shopping", "url": f"https://www.google.com/search?tbm=shop&q={q}"}]


def miestas(s: dict) -> str:
    return (s.get("vieta_laikas") or "").split(",")[0].strip()


def kastai(s: dict) -> dict:
    """Pirkimo logistika pagal miestą ir dydį. Didelis daiktas ne vietiniame mieste – nepervežamas."""
    vietinis = miestas(s) in N["vietiniai_miestai"]
    tekstas = be_diakritiku(s.get("pavadinimas", "") + " " + s.get("aprasymas", ""))
    didelis = any(be_diakritiku(z) in tekstas for z in N["dideli_daiktai"])
    if vietinis:
        budas, atgabenimas, val = f"atsiimti vietoje ({miestas(s)})", N["atsiemimas_vietoje_eur"], N["laikas_vietoje_val"]
    else:
        budas, atgabenimas, val = f"siunta į paštomatą iš {miestas(s) or 'kito miesto'}", N["siunta_i_mane_eur"], N["laikas_siunta_val"]
    return {"budas": budas, "atgabenimas": atgabenimas, "pardavimas": N["pardavimo_kastai_eur"],
            "viso": atgabenimas + N["pardavimo_kastai_eur"], "valandos": val, "vietinis": vietinis, "didelis": didelis,
            "nepervezamas": didelis and not vietinis}


def palyginami(raktas: str, sid: str, visi: list[dict]) -> list[dict]:
    komp = [s for s in visi if s["_raktas"] == raktas and s["id"] != sid and s.get("kaina")
            and not re.search(r"\b(perku|pirksiu|pirkciau|supirk)", be_diakritiku(s["pavadinimas"]))]
    if len(komp) >= 3:                      # išmetame aiškias išskirtis (klaidingos kainos, rinkiniai)
        med = statistics.median(k["kaina"] for k in komp)
        komp = [k for k in komp if med / 3 <= k["kaina"] <= med * 3]
    return sorted(komp, key=lambda k: k["kaina"])


def ivertinti(s: dict, visi: list[dict], claude: dict | None) -> dict:
    kaina = s.get("kaina") or 0
    raktas = s["_raktas"]
    komp = palyginami(raktas, s["id"], visi)
    kainos = [k["kaina"] for k in komp]
    med = statistics.median(kainos) if len(kainos) >= 3 else None     # 1–2 skelbimai – ne rinka, o atsitiktinumas
    sklaida = None
    if len(kainos) >= 4 and med:
        q = statistics.quantiles(kainos, n=4)
        sklaida = (q[2] - q[0]) / med
    k = kastai(s)
    zingsniai, saltiniai = [], []
    pardavimo = None
    if med:
        pardavimo = med * N["nuolaida_pardavimui"]
        saltiniai.append(f"{len(komp)} panašių skelbimų mediana {eur(med)}")
        zingsniai.append(f"Panašūs skelbimai ({raktas}): {len(komp)} vnt., kainos {eur(min(kainos))}–{eur(max(kainos))}, "
                         f"mediana {eur(med)} × {N['nuolaida_pardavimui']:.2f} (realiai parduodama pigiau nei prašoma) = {eur(pardavimo)}")
    elif kainos:
        zingsniai.append(f"Panašių skelbimų tik {len(kainos)} – per mažai kainai nustatyti")
    naujo = (claude or {}).get("naujo_kaina")
    if claude and claude.get("tiketina_pardavimo"):
        pardavimo = float(claude["tiketina_pardavimo"])
        saltiniai.insert(0, "Claude įvertinimas")
        zingsniai.append(f"Claude įvertinimas ({claude.get('ivertinta', '')}): {eur(pardavimo)}"
                         + (f" – {claude['kainos_pagrindimas']}" if claude.get("kainos_pagrindimas") else ""))
    if naujo:
        lubos = float(naujo) * N["naujo_lubos"]
        saltiniai.append(f"naujas ~{eur(float(naujo))}")
        if pardavimo is None or pardavimo > lubos:
            zingsniai.append(f"Lubos: naujas {eur(float(naujo))} × {N['naujo_lubos']:.2f} = {eur(lubos)} – naudoto brangiau niekas nepirks")
            pardavimo = lubos

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
        zingsniai.append("Grupė nevienalytė (skirtingi daiktai), todėl patikimumas žemas, kol neįvertins Claude")

    r = {"modelis": (claude or {}).get("modelis") or raktas, "raktas": raktas, "palyginamu": len(komp),
         "mediana": round(med) if med else None, "naujo_kaina": naujo, "patikimumas": patik, "saltiniai": saltiniai,
         "kastai": k, "palyginami": [{"pavadinimas": x["pavadinimas"][:80], "kaina": x["kaina"], "nuoroda": x["nuoroda"],
                                      "vieta_laikas": x.get("vieta_laikas", "")} for x in komp[:10]],
         "parduotuves": (claude or {}).get("parduotuves") or [],
         "parduotuviu_paieska": parduotuviu_nuorodos(paieskos_fraze(s, raktas, claude))}
    if k["nepervezamas"]:
        r.update(tiketina_pardavimo=round(pardavimo) if pardavimo else None, pelnas=None, roi=None, max_pirkimo=None,
                 pelnas_per_val=None, sprendimas="praleisti", balas=0,
                 priezastis=f"didelis daiktas {miestas(s)} – netelpa į siuntą, važiuoti neapsimoka")
        zingsniai.append(r["priezastis"])
    elif pardavimo is None or not kaina:
        r.update(tiketina_pardavimo=None, pelnas=None, roi=None, max_pirkimo=None, pelnas_per_val=None,
                 sprendimas="tikrinti" if not kaina else "nežinoma",
                 priezastis="nėra kainos" if not kaina else "per mažai panašių skelbimų – įvertins Claude", balas=0)
    else:
        pelnas = pardavimo - kaina - k["viso"]
        roi = pelnas / kaina
        max_pirkimo = min((pardavimo - k["viso"]) / (1 + N["min_roi"]), pardavimo - k["viso"] - N["min_pelnas_eur"])
        zingsniai += [f"Kaštai: {k['budas']} {eur(k['atgabenimas'])} + pakuotė / pardavimas {eur(k['pardavimas'])} = {eur(k['viso'])}",
                      f"Pelnas = {eur(pardavimo)} − {eur(kaina)} − {eur(k['viso'])} = {eur(pelnas)} ({roi:.0%} pirkimo kainos)",
                      f"Mokėti ne daugiau: min(({eur(pardavimo)} − {eur(k['viso'])}) / {1 + N['min_roi']:.2f}; "
                      f"{eur(pardavimo)} − {eur(k['viso'])} − {eur(N['min_pelnas_eur'])}) = {eur(max(max_pirkimo, 0))}",
                      f"Laikas ~{k['valandos']} val. → {eur(pelnas / k['valandos'])}/val."]
        if pelnas >= N["min_pelnas_eur"] and roi >= N["min_roi"] and patik != "žemas":
            spr, prz = "verta", f"pelnas ~{eur(pelnas)} ({roi:.0%}), {k['budas']}"
        elif pelnas >= N["min_pelnas_eur"] and roi >= N["min_roi"]:
            spr, prz = "tikrinti", "atrodo pelninga, bet per mažai duomenų – patikrink panašius skelbimus"
        elif patik != "žemas" and max_pirkimo > 0 and kaina - max_pirkimo <= max(15, kaina * 0.25):
            spr, prz = "derėtis", f"verta tik nusiderėjus iki {eur(max_pirkimo)}"
        else:
            spr, prz = "praleisti", "per brangu perpardavimui"
        svoris = {"aukštas": 1.0, "vidutinis": 0.75, "žemas": 0.4}.get(patik, 0.5)
        balas = max(0.0, (pelnas / k["valandos"]) * 1.2 * svoris + roi * 30 * svoris)
        sezonas = PAIESKOS.get(s.get("paieska"), {}).get("sezonas_menesiai") or []
        if datetime.now().month in sezonas:
            balas *= N["sezono_daugiklis"]
            zingsniai.append(f"Sezonas: šiuo mėnesiu paklausa didesnė, balas × {N['sezono_daugiklis']}")
        r.update(tiketina_pardavimo=round(pardavimo), pelnas=round(pelnas), roi=round(roi, 2),
                 max_pirkimo=round(max_pirkimo) if max_pirkimo > 0 else 0,
                 pelnas_per_val=round(pelnas / k["valandos"]), sprendimas=spr, priezastis=prz, balas=round(min(balas, 100)))
    if claude:
        for key in ("sprendimas", "priezastis", "skelbimo_tekstas", "rizikos", "ivertinta", "stovas", "naujo_saltinis"):
            if claude.get(key) not in (None, ""):
                r[key] = claude[key]
        if k["nepervezamas"]:
            r["sprendimas"] = "praleisti"
    r["zingsniai"] = zingsniai
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
    out = {"sugeneruota": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "prielaidos": N,
           "skelbimu_istorijoje": len(visi), "radiniai": radiniai,
           "rinka": {k: {"n": len(v), "mediana": round(statistics.median(v)), "min": min(v), "max": max(v)}
                     for k, v in rinka.items() if len(v) >= 2}}
    isvestis.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Radinių: {len(radiniai)}", dict(Counter(r["sprendimas"] for r in radiniai)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
