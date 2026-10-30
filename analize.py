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
    if "dyson" in paieska:
        m = re.search(r"\b(v\s?\d{1,2}|gen5|airwrap|supersonic|corrale|pure\s?cool|hot\s?\+?\s?cool|omni)\b", p)
        return "dyson-" + (m.group(1).replace(" ", "") if m else ("priedai" if priedas else "kita"))
    if "thermomix" in paieska:
        m = re.search(r"\btm\s?([567])\b", p)
        return "thermomix-tm" + m.group(1) if m else "thermomix-kita"
    if "kitchenaid" in paieska:
        m = re.search(r"\b(artisan|classic|heavy\s?duty|mini|5ksm\w*)\b", p)
        return "kitchenaid-" + (m.group(1).replace(" ", "") if m else "kita")
    if "sonos" in paieska:
        m = re.search(r"\b(era\s?\d{3}|one\s?sl|one|beam|arc|ray|move|roam|sub|five|play\s?:?\s?\d|ace)\b", p)
        return "sonos-" + (re.sub(r"[\s:]", "", m.group(1)) if m else "kita")
    if "robot" in paieska:
        m = re.search(r"\b(roborock|dreame|ecovacs|xiaomi|roomba)\b\s*([a-z]{0,2}\s?\d{1,3}\s?(max\s?v?|maxv|pro|ultra|plus|\+)?)?", p)
        if m and m.group(2):
            return f"{m.group(1)}-" + re.sub(r"\s", "", m.group(2))
        return "robotas-kita"
    if "ipad" in paieska:
        m = re.search(r"ipad\s*(pro|air|mini)?\s*(\d{1,2})?", p)
        if not m:
            return "ipad-kita"
        return "ipad-" + (m.group(1) or "bazinis") + ("-" + m.group(2) if m.group(2) else "")
    if "fotoaparat" in paieska:
        m = re.search(r"\b(x-?t\d{1,2}|x-?s\d{1,2}|x-?e\d|x100\w*|x-?h\d\w?|a7\s?(r|s|c)?\s?(i{1,3}v?|\d)?|a6\d{3}|eos\s?r\d*|z\s?\d{1,2}|gr\s?i{1,3}x?)\b", p)
        return "foto-" + (re.sub(r"[\s-]", "", m.group(1)) if m else "kita")
    if "bosch" in paieska:
        m = re.search(r"\b(g[a-z]{2})\s?(\d{2}v?)?-?(\d{1,3})?", p)
        return "bosch-" + (m.group(1) + (m.group(2) or "") + ("-" + m.group(3) if m.group(3) else "") if m else ("priedas" if priedas else "kita"))
    if "vezimel" in paieska:
        m = re.search(r"\b(bugaboo|cybex|joolz|stokke|thule)\s*([a-z]+\s?\d?)?", p)
        return (m.group(1) + ("-" + m.group(2).replace(" ", "") if m.group(2) else "")) if m else "vezimelis-kita"
    if "steam" in paieska:
        if "deck" not in p:
            return "steamdeck-kita"
        return "steamdeck-" + ("oled" if "oled" in p else "lcd") + ("-" + re.search(r"(64|256|512|1tb)", p).group(1) if re.search(r"(64|256|512|1tb)", p) else "")
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


# Aprašymo žodžiai: rizikos (galimi defektai) ir privalumai. Ieškoma be diakritikų.
RIZIKOS = {"defekt": "defektas", "neveik": "neveikia", "suged": "sugedęs", "dalims": "dalims", "iskil": "įskilęs",
           "skilin": "skilinėjęs", "truksta": "trūksta detalių", "be pakrov": "be pakrovėjo", "be krovikl": "be kroviklio",
           "uzrakint": "užrakintas", "icloud": "iCloud", "blokuot": "užblokuotas", "braizyt": "braižytas", "ilenk": "įlenkimai",
           "drift": "pultelių drift", "silpna baterij": "silpna baterija", "baterija laiko": "baterijos būklė",
           "remont": "remontuotas", "taisyt": "taisytas", "neoriginal": "neoriginalus", "kopija": "kopija",
           "replika": "replika", "nepatikrint": "nepatikrintas", "kaip yra": "„kaip yra“", "atristas": "atrištas (modifikuotas)",
           "atrist": "atrištas (modifikuotas)"}
PRIVALUMAI = {"garantij": "garantija", "cekis": "čekis", "cekiu": "čekis", "kvit": "kvitas", "saskait": "sąskaita",
              "su dez": "su dėže", "originali dez": "su dėže", "komplekt": "komplektas", "nenaudot": "nenaudotas", "mazai naudot": "mažai naudotas",
              "ideal": "ideali būklė", "puikios bukles": "puiki būklė", "labai geros bukles": "labai gera būklė",
              "nauja": "nauja", "naujas": "naujas", "originali pakuot": "originali pakuotė"}


def aprasymo_analize(s: dict) -> dict:
    if s.get("pilnas_aprasymas", "").startswith("Aprašymas:"):     # ankstesnio atpažinimo liekana
        s["pilnas_aprasymas"] = s["pilnas_aprasymas"][len("Aprašymas:"):].strip()
    if len(s.get("bukle") or "") < 4:
        s.pop("bukle", None)
    tekstas = be_diakritiku(" ".join([s.get("pavadinimas", ""), s.get("pilnas_aprasymas") or s.get("aprasymas", ""),
                                      " ".join(s.get("parametrai") or []), s.get("bukle", "")]))
    rizikos = sorted({v for k, v in RIZIKOS.items() if k in tekstas})
    privalumai = sorted({v for k, v in PRIVALUMAI.items() if re.search(r"\b" + re.escape(k), tekstas)})
    apr = s.get("pilnas_aprasymas") or s.get("aprasymas") or ""
    return {"rizikos_zodziai": rizikos, "privalumai": privalumai, "aprasymo_ilgis": len(apr),
            "pilnas": bool(s.get("pilnas_aprasymas"))}


MENESIAI = {"sausio": 1, "vasario": 2, "kovo": 3, "balandžio": 4, "gegužės": 5, "birželio": 6, "liepos": 7,
            "rugpjūčio": 8, "rugsėjo": 9, "spalio": 10, "lapkričio": 11, "gruodžio": 12}


def skelbimo_amzius(s: dict) -> int | None:
    """Kiek dienų skelbimas įdėtas / atnaujintas (iš „prieš 3 d.“, „spalio 21 d.“) arba nuo pirmo pastebėjimo."""
    t = (s.get("vieta_laikas") or "").split(",")[-1].strip()
    now = datetime.now()
    m = re.search(r"prieš (\d+) d", t)
    if m:
        d = int(m.group(1))
    elif re.search(r"prieš \d+ (val|min)", t):
        d = 0
    else:
        m = re.search(r"([a-ząčęėįšųūž]+) (\d{1,2}) d", t)
        d = None
        if m and m.group(1) in MENESIAI:
            data = datetime(now.year, MENESIAI[m.group(1)], int(m.group(2)))
            if data > now:
                data = data.replace(year=now.year - 1)
            d = (now - data).days
    if s.get("pastebetas"):
        nuo = (datetime.now(timezone.utc) - datetime.strptime(s["pastebetas"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)).days
        d = max(d or 0, nuo)
    return d


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


PERKA = re.compile(r"\b(perku|pirksiu|pirkciau|nupirksiu|supirk|ieskau|iesko|ieskom|domina|reikalingas|reikalinga)\b")


def perka(s: dict) -> bool:
    """Pirkimo / paieškos skelbimai („Ieškau Steam Deck“) – ne pasiūla, nei radinys, nei palyginimas."""
    return bool(PERKA.search(be_diakritiku(s.get("pavadinimas"))))


def palyginamas(s: dict) -> bool:
    """Į rinkos palyginimą – tik tinkami skelbimai ir tie, kurie atmesti vien dėl kainų ribų (ne automobiliai su „Sonos“ aprašyme)."""
    if s.get("tinka", True):
        return True
    if s.get("atmesta_nes") not in ("per pigu", "per brangu"):
        return False
    mx = PAIESKOS.get(s.get("paieska"), {}).get("max_kaina")
    return not (mx and s.get("kaina") and s["kaina"] > mx * 2)


def palyginami(raktas: str, sid: str, visi: list[dict]) -> list[dict]:
    komp = [s for s in visi if s["_raktas"] == raktas and s["id"] != sid and s.get("kaina")
            and not perka(s)]
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
        elif patik != "žemas" and max_pirkimo > 0 and kaina - max_pirkimo <= kaina * 0.25:
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
        for key in ("sprendimas", "priezastis", "skelbimo_tekstas", "rizikos", "ivertinta", "stovas", "naujo_saltinis",
                    "apie", "tikrinti", "galimybe", "pardavimas", "kainos_pagrindimas"):
            if claude.get(key) not in (None, ""):
                r[key] = claude[key]
        if k["nepervezamas"]:
            r["sprendimas"] = "praleisti"
    # Sprendimas turi atitikti skaičius: jei apsimoka ir už prašomą kainą – ne „derėtis“; jei ne – ne „verta“.
    mp = r.get("max_pirkimo")
    if kaina and mp is not None and r.get("pelnas") is not None:
        if r["sprendimas"] == "derėtis" and mp >= kaina:
            r["sprendimas"] = "verta" if patik != "žemas" else "tikrinti"
            r["priezastis"] = (f"apsimoka ir už prašomą {eur(kaina)} (riba {eur(mp)}), pelnas ~{eur(r['pelnas'])}"
                               + ("" if patik != "žemas" else " – bet kaina neaiški, patikrink panašius"))
        elif r["sprendimas"] == "derėtis" and mp <= 0:
            r["sprendimas"], r["priezastis"] = "praleisti", "neapsimoka net nusiderėjus"
        elif r["sprendimas"] == "verta" and mp < kaina:
            r["sprendimas"], r["priezastis"] = "derėtis", f"verta tik nusiderėjus iki {eur(mp)} (prašo {eur(kaina)})"
    # Vieta tarp to paties modelio skelbimų ir „kodėl būtent šis“.
    ap = aprasymo_analize(s)
    r["aprasymas_analize"] = ap
    if kaina and len(kainos) >= 2:
        visos = sorted(kainos + [kaina])
        vieta = visos.index(kaina) + 1
        med_v = statistics.median(kainos)
        nuolaida = 1 - kaina / med_v
        r["pozicija"] = {"vieta": vieta, "is": len(visos), "min": min(kainos), "max": max(kainos), "mediana": med_v,
                         "nuolaida": round(nuolaida, 2)}
        if vieta == 1:
            sak = f"Pigiausias iš {len(visos)} to paties modelio skelbimų"
        else:
            sak = f"{vieta}-as pigiausias iš {len(visos)}"
        sak += f" (kiti {eur(min(kainos))}–{eur(max(kainos))}, mediana {eur(med_v)})"
        sak += f", {abs(nuolaida):.0%} {'pigiau' if nuolaida >= 0 else 'brangiau'} už medianą."
    else:
        sak = "Panašių skelbimų dar per mažai palyginti."
    istartinas = kaina and r.get("mediana") and kaina < 0.55 * r["mediana"]
    if istartinas:
        sak += " Įtartinai pigu – perskaityk aprašymą, paklausk apie defektus."
    if ap["rizikos_zodziai"]:
        sak += " Aprašyme: " + ", ".join(ap["rizikos_zodziai"]) + "."
    if ap["privalumai"]:
        sak += " Privalumai: " + ", ".join(ap["privalumai"]) + "."
    if not ap["aprasymo_ilgis"]:
        sak += " Aprašymo nėra – klausk pardavėjo būklės ir komplektacijos."
    r["kodel"] = sak
    # Rizikos žodžiai arba įtartinai maža kaina be pilno aprašymo – ne „Pirkti“, o „Patikrinti“.
    if r["sprendimas"] in ("verta", "derėtis") and (ap["rizikos_zodziai"] or (istartinas and not (claude and claude.get("tiketina_pardavimo")))):
        r["sprendimas"] = "tikrinti"
        r["priezastis"] = ("aprašyme: " + ", ".join(ap["rizikos_zodziai"])) if ap["rizikos_zodziai"] else "įtartinai pigu – patikrink, ar tai ne senesnis modelis ar defektas"
        r["balas"] = round((r.get("balas") or 0) * 0.6)
    elif r.get("balas"):
        r["balas"] = min(100, round(r["balas"] + 3 * len(ap["privalumai"])))
    r["visi_palyginami"] = [{"kaina": x["kaina"], "nuoroda": x["nuoroda"], "pavadinimas": x["pavadinimas"][:60],
                             "rizikos": aprasymo_analize(x)["rizikos_zodziai"], "vieta_laikas": x.get("vieta_laikas", "")}
                            for x in komp[:40]]
    r["amzius_d"] = skelbimo_amzius(s)
    r["derybos"] = derybos(s, r, komp)
    naujo_kainos = [p_["kaina"] for p_ in r["parduotuves"] if p_.get("kaina")]
    r["naujo_min"] = min(naujo_kainos) if naujo_kainos else (float(naujo) if naujo else None)
    if s.get("pradine_kaina") and kaina and s["pradine_kaina"] > kaina:
        r["kaina_sumazejo"] = {"nuo": s["pradine_kaina"], "iki": kaina}
        if r.get("balas"):
            r["balas"] = min(100, r["balas"] + 5)
    r["zingsniai"] = zingsniai
    r.update(paaiskinimas(s, r, istartinas))
    r["saugumas"] = saugumas(s, r, istartinas)
    return r


APPLE = ("ipad", "iphone", "macbook", "apple watch", "airpods")


def saugumas(s: dict, r: dict, istartinas) -> dict:
    """Kaip apsisaugoti nuo sukčių: rizikos lygis ir konkretūs žingsniai šiam skelbimui."""
    kaina = s.get("kaina") or 0
    k = r.get("kastai") or {}
    pav = be_diakritiku(s.get("pavadinimas"))
    if k.get("vietinis"):
        lygis = "didelė" if istartinas else "maža"
        zingsniai = ["Susitik gyvai viešoje vietoje (prekybos centre, prie degalinės), dienos metu.",
                     "Prieš mokėdamas įjunk ir patikrink daiktą: ar veikia, ar sutampa modelis, ar nėra defektų, kurių nebuvo nuotraukose.",
                     "Mokėk tik pamatęs daiktą: grynais arba mokėjimu telefonu vietoje. Jokių avansų ir „rezervacijos mokesčių“."]
    else:
        lygis = "didelė" if istartinas or kaina > 150 else "vidutinė"
        zingsniai = ["Nepervesk pinigų iš anksto. Paprašyk išperkamosios siuntos (LP Express ir Omniva tai siūlo): sumokėsi atsiimdamas, o pardavėjas bus susietas su siunta.",
                     "Jei pardavėjas sutinka tik su išankstiniu pavedimu, paprašyk nuotraukos, kurioje šalia daikto būtų lapelis su tavo vardu ir šiandienos data, ir trumpo vaizdo įrašo, kad daiktas veikia.",
                     "Pavedimą daryk tik į banko sąskaitą tuo pačiu vardu kaip pardavėjo. Prieš tai pagooglink sąskaitos numerį ir telefoną kartu su žodžiu „sukčius“.",
                     "Pažiūrėk kitus pardavėjo skelbimus Skelbiu.lt: kelis tokius pačius daiktus už itin mažą kainą dažniausiai skelbia sukčiai.",
                     "Nespausk jokių siuntų ar mokėjimų nuorodų, kurias atsiunčia pardavėjas, ir niekur neįvesk kortelės duomenų. Visada pats sumokėk už siuntą per kurjerio programėlę."]
        if kaina > 150:
            zingsniai.append(f"Suma didelė ({eur(kaina)}). Jei nesutinka siųsti išperkamąja siunta, verčiau praleisk arba važiuok pasiimti.")
    if any(z in pav for z in APPLE):
        zingsniai.append("Apple daiktai: paprašyk serijos numerio ir patikrink checkcoverage.apple.com. Prieš mokėdamas įsitikink, kad išjungtas „Find My“ (iCloud užraktas).")
    if istartinas:
        zingsniai.insert(0, "Kaina įtartinai maža. Tai dažniausias sukčių masalas, todėl būk ypač atsargus.")
    zingsniai.append("Išsaugok susirašinėjimą ir skelbimo nuorodą. Jei apgautų, pranešk policijai per epolicija.lt.")
    zinute = ("Ar galėtumėte išsiųsti išperkamąja siunta (LP Express ar Omniva)? Sumokėčiau atsiimdamas. "
              "Ir ar galėtumėte atsiųsti nuotrauką su lapeliu, ant kurio užrašyta šiandienos data?") if not k.get("vietinis") else None
    return {"lygis": lygis, "zingsniai": zingsniai, "zinute": zinute}


def paaiskinimas(s: dict, r: dict, istartinas) -> dict:
    """Žmoniška išvada ir argumentai už / prieš – kad būtų aišku, kodėl siūloma arba atmesta."""
    kaina, pelnas, roi, riba = s.get("kaina"), r.get("pelnas"), r.get("roi"), r.get("max_pirkimo")
    po, ap, k = r.get("pozicija") or {}, r.get("aprasymas_analize") or {}, r.get("kastai") or {}
    uz, pries, logistika = [], [], None
    if po.get("is"):
        pig = po["vieta"] - 1
        txt = f"Iš {po['is']} panašių skelbimų " + ("pigesnio nėra" if pig == 0 else "pigesnis tik vienas" if pig == 1 else f"pigesnių yra {pig}")
        txt += f"; įprasta kaina ~{eur(po['mediana'])}"
        (uz if po["nuolaida"] >= 0.15 else pries).append(txt + (f", šis {pct(po['nuolaida'])} pigesnis." if po["nuolaida"] > 0 else f", šis ne pigesnis už kitus."))
    if r.get("naujo_min") and kaina:
        (uz if kaina <= r["naujo_min"] * 0.6 else pries).append(f"Naujas parduotuvėje nuo {eur(r['naujo_min'])}, šis kainuoja {pct(kaina / r['naujo_min'])} naujo kainos.")
    if pelnas is not None:
        if pelnas >= N["min_pelnas_eur"] and roi >= N["min_roi"]:
            uz.append(f"Pelnas ~{eur(pelnas)} ({pct(roi)} įdėtų pinigų) – virš tavo ribų ({eur(N['min_pelnas_eur'])} ir {pct(N['min_roi'])}).")
        else:
            if pelnas < N["min_pelnas_eur"]:
                pries.append(f"Pelnas būtų tik ~{eur(pelnas)} – mažiau nei tavo minimumas {eur(N['min_pelnas_eur'])}.")
            if roi < N["min_roi"]:
                pries.append(f"Grąža {pct(roi)} – mažiau nei {pct(N['min_roi'])}; pinigai užšaltų už per mažą naudą.")
    if r["sprendimas"] == "derėtis" and riba:
        pries.append(f"Prašo {eur(kaina)}, o apsimoka tik už ≤ {eur(riba)}.")
    if r.get("palyginamu", 0) < 3 and not r.get("ivertinta"):
        pries.append(f"Rasta tik {skelbimu(r.get('palyginamu', 0))} – nėra su kuo patikimai palyginti (Claude įvertins rytinėje peržiūroje).")
    elif r.get("patikimumas") == "žemas":
        pries.append("Panašūs skelbimai labai skirtingi (įvairūs modeliai ar rinkiniai), todėl kaina neaiški.")
    if k.get("nepervezamas"):
        pries.append(f"Didelis daiktas {miestas(s)} – netelpa į paštomatą, o važiuoti neapsimoka.")
    elif k.get("budas"):
        logistika = f"{k['budas'][0].upper() + k['budas'][1:]}: kaštai ~{eur(k.get('viso', 0))}, laikas ~{str(k.get('valandos')).replace('.', ',')} val."
    if ap.get("rizikos_zodziai"):
        pries.append("Aprašyme minima: " + ", ".join(ap["rizikos_zodziai"]) + ".")
    if istartinas:
        pries.append("Įtartinai pigu (< 55 % įprastos kainos) – dažniausiai tai senesnis modelis, defektas ar apgaulė.")
    if ap.get("privalumai"):
        uz.append("Aprašyme: " + ", ".join(ap["privalumai"]) + ".")
    if not ap.get("aprasymo_ilgis"):
        pries.append("Aprašymo beveik nėra – būklė nežinoma.")
    if r.get("kaina_sumazejo"):
        uz.append(f"Kaina jau sumažinta nuo {eur(r['kaina_sumazejo']['nuo'])} – pardavėjas linkęs nusileisti.")

    spr = r["sprendimas"]
    if spr == "verta":
        isv = f"Pirk, jei gausi ne daugiau kaip už {eur(riba)}. Tikėtinas pelnas ~{eur(pelnas)}."
    elif spr == "derėtis":
        isv = f"Pirk tik nusiderėjęs iki {eur(riba)} (dabar prašo {eur(kaina)})."
    elif spr == "tikrinti":
        isv = "Gali būti proga, bet pirma patikrink: " + (pries[0][0].lower() + pries[0][1:] if pries else r.get("priezastis", ""))
    elif spr == "nežinoma":
        isv = "Kol kas neaišku – trūksta duomenų kainai nustatyti."
    else:
        isv = "Praleisk: " + (pries[0][0].lower() + pries[0][1:] if pries else r.get("priezastis", ""))
    return {"isvada": isv, "uz": uz, "pries": pries, "logistika": logistika}


def pct(x) -> str:
    return f"{round(x * 100)} %"


def skelbimu(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} panašus skelbimas"
    if 2 <= n % 10 <= 9 and not 12 <= n % 100 <= 19:
        return f"{n} panašūs skelbimai"
    return f"{n} panašių skelbimų"


def derybos(s: dict, r: dict, komp: list[dict]) -> dict | None:
    """Derybų suflerys: siūloma kaina, riba ir argumentai – kiekvienas su įrodymu (skaičiais ar nuoroda)."""
    kaina = s.get("kaina")
    if not kaina or r["sprendimas"] == "praleisti" or not r.get("tiketina_pardavimo"):
        return None
    riba = r.get("max_pirkimo") or 0
    siulymas = max(5, int(min(kaina * 0.85, riba or kaina) // 5 * 5))
    arg = []
    pigesni = [k for k in komp if k["kaina"] < kaina]
    if pigesni:
        p = min(pigesni, key=lambda k: k["kaina"])
        arg.append({"t": f"Pigesnių panašių skelbimų: {len(pigesni)}, pigiausias {eur(p['kaina'])}", "url": p["nuoroda"]})
    if r.get("mediana") and kaina > r["mediana"] * 0.9:
        arg.append({"t": f"Panašių skelbimų mediana {eur(r['mediana'])} – šio kaina ne žemiau rinkos"})
    if r.get("naujo_min"):
        arg.append({"t": f"Naujas parduotuvėje {eur(r['naujo_min'])} – naudotas be garantijos turi būti gerokai pigesnis ({kaina / r['naujo_min']:.0%} naujo kainos)"})
    ap = r.get("aprasymas_analize") or {}
    if ap.get("rizikos_zodziai"):
        arg.append({"t": "Aprašyme minima: " + ", ".join(ap["rizikos_zodziai"]) + " – trūkumai mažina vertę"})
    if not ap.get("privalumai") or not any(z in ap.get("privalumai", []) for z in ("čekis", "kvitas", "garantija", "sąskaita")):
        arg.append({"t": "Nėra čekio ar garantijos – pirkėjui didesnė rizika"})
    if r.get("amzius_d") and r["amzius_d"] >= 14:
        arg.append({"t": f"Skelbimas kabo jau ~{r['amzius_d']} d. – pardavėjas greičiausiai nori parduoti"})
    if r.get("kaina_sumazejo"):
        arg.append({"t": f"Kaina jau mažinta nuo {eur(r['kaina_sumazejo']['nuo'])} – pardavėjas linkęs nusileisti"})
    k = r.get("kastai") or {}
    arg.append({"t": "Galiu atsiimti greitai ir atsiskaityti iškart" if k.get("vietinis")
                else f"Siuntimą (~{eur(k.get('atgabenimas', 0))}) apmokėsiu pats – pardavėjui jokio vargo"})
    pelnas = r.get("pelnas") or 0
    tarp = int(((siulymas + min(kaina, riba or kaina)) / 2) // 5 * 5)
    if tarp <= siulymas:
        tarp = None
    planas = [f"Pirma žinutė: siūlyk {eur(siulymas)} – tai {pct(1 - siulymas / kaina)} mažiau nei prašo ({eur(kaina)})."]
    if tarp:
        planas.append(f"Jei atsisako – kelk iki {eur(tarp)}.")
    if riba >= kaina:
        planas.append(f"Jei visai nenuleidžia – vis tiek pirk už {eur(kaina)}: pelnas ~{eur(pelnas)}. Šio radinio dėl derybų neprarask.")
    elif riba and riba <= siulymas:
        planas = [f"Siūlyk {eur(riba)} ({pct(1 - riba / kaina)} mažiau nei prašo) ir daugiau nekelk – brangiau pelnas per mažas."]
    elif riba:
        planas.append(f"Paskutinis siūlymas {eur(riba)}. Jei nori daugiau – nepirk: pelnas nukristų žemiau {eur(N['min_pelnas_eur'])}.")
    return {"siulymas": siulymas, "tarpinis": tarp, "riba": riba, "argumentai": arg[:3], "planas": planas,
            "kodel_suma": (f"Kodėl {eur(siulymas)}? ~15 % nuolaida – įprastas pirmas siūlymas: pardavėjo neįžeidžia ir palieka vietos susitikti per vidurį. "
                           "Ar tai veikia būtent tau, parodys derybų statistika žurnale."),
            "nauda": f"Kiekvienas nusiderėtas euras = +1 € pelno: už {eur(kaina)} uždirbtum ~{eur(pelnas)}, už {eur(siulymas)} – ~{eur(pelnas + kaina - siulymas)}."}


def kalibracija() -> dict:
    """Savikalibracija: kai yra ≥ 5 parduoti daiktai su užfiksuota rinkos mediana, nuolaida pardavimui
    imama iš tikrų pardavimų (pardavimo kaina / mediana pirkimo metu), ribojant 0,6–1,05."""
    try:
        sand = json.loads((ROOT / "docs" / "sandoriai.json").read_text(encoding="utf-8")).get("sandoriai", [])
    except (OSError, ValueError):
        sand = []
    santykiai = [x["pardavimo_kaina"] / x["irodymas"]["vertinimas"]["mediana"] for x in sand
                 if x.get("busena") == "parduota" and x.get("pardavimo_kaina")
                 and ((x.get("irodymas") or {}).get("vertinimas") or {}).get("mediana")]
    if len(santykiai) >= 5:
        N["nuolaida_pardavimui"] = round(min(1.05, max(0.6, statistics.mean(santykiai))), 3)
        return {"pardavimu": len(santykiai), "nuolaida": N["nuolaida_pardavimui"]}
    return {"pardavimu": len(santykiai), "nuolaida": N["nuolaida_pardavimui"], "reikia": 5}


def pardavimo_pagalba(visi: list[dict]) -> dict:
    """Atsargoms: kiek dabar prašo konkurentai (to paties modelio aktyvūs skelbimai) ir siūloma pardavimo kaina."""
    try:
        sand = json.loads((ROOT / "docs" / "sandoriai.json").read_text(encoding="utf-8")).get("sandoriai", [])
    except (OSError, ValueError):
        return {}
    riba = (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = {}
    for x in sand:
        if x.get("busena") != "atsargose":
            continue
        ir = x.get("irodymas") or {}
        raktas = modelio_raktas({"pavadinimas": ir.get("pavadinimas") or x.get("pavadinimas", ""),
                                 "aprasymas": ir.get("aprasymas", ""), "paieska": x.get("kategorija", "")})
        konk = sorted([s for s in visi if s["_raktas"] == raktas and s.get("kaina") and s.get("paskutini_karta_matytas", "") >= riba
                       and s.get("id") != ir.get("skelbimo_id")], key=lambda s: s["kaina"])
        if not konk:
            out[x.get("id", "")] = {"raktas": raktas, "konkurentu": 0}
            continue
        med = statistics.median(k["kaina"] for k in konk)
        out[x.get("id", "")] = {"raktas": raktas, "konkurentu": len(konk), "mediana": med, "pigiausias": konk[0]["kaina"],
                                "siuloma_kaina": int(max(konk[0]["kaina"], med * 0.95) // 5 * 5),
                                "konkurentai": [{"pavadinimas": k["pavadinimas"][:60], "kaina": k["kaina"], "nuoroda": k["nuoroda"]}
                                                for k in konk[:5]]}
    return out


REKOMENDACIJOS = ROOT / "data" / "rekomendacijos.json"
GERI = ("verta", "derėtis")


def _laikas(t: str | None):
    return datetime.strptime(t, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) if t else None


def rekomendaciju_istorija(radiniai: list[dict], istorija: dict, vertinimai: dict) -> dict:
    """Kiekvienas kada nors rekomenduotas („Pirkti“ / „Derėtis“) skelbimas lieka data/rekomendacijos.json.
    Kada skelbimas dingo, nustato skelbiu.py (atidaro jo puslapį). Gyvavimo laikas = nuo pastebėjimo iki dingimo;
    jei tarp paskutinio „dar yra“ ir „nebėra“ praėjo daugiau nei 7 val., rodomas intervalas, ne tikslus skaičius."""
    try:
        rek = json.loads(REKOMENDACIJOS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        rek = {}
    dabar_ = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not rek:   # pirmas kartas: ankstesni Claude „verta“ / „derėtis“ vertinimai
        for sid, v in vertinimai.items():
            s = istorija.get(sid)
            if s and v.get("sprendimas") in GERI and v.get("ivertinta"):
                rek[sid] = {"rekomenduota": max(s.get("pastebetas", ""), v["ivertinta"] + "T04:45:00Z"),
                            "sprendimas": v["sprendimas"], "tiketina_pardavimo": v.get("tiketina_pardavimo"),
                            "pelnas": round(v["tiketina_pardavimo"] - s["kaina"] - 6) if v.get("tiketina_pardavimo") and s.get("kaina") else None}
    for r in radiniai:
        if r["sprendimas"] not in GERI:
            continue
        e = rek.setdefault(str(r["id"]), {"rekomenduota": dabar_})
        e["paskutini_karta_rekomenduota"] = dabar_
        if r["sprendimas"] == "verta" or e.get("sprendimas") != "verta":
            e["sprendimas"] = r["sprendimas"]
        e.update(pelnas=r.get("pelnas"), max_pirkimo=r.get("max_pirkimo"), tiketina_pardavimo=r.get("tiketina_pardavimo"),
                 vietinis=bool((r.get("kastai") or {}).get("vietinis")))
    REKOMENDACIJOS.write_text(json.dumps(rek, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        sand = json.loads((ROOT / "docs" / "sandoriai.json").read_text(encoding="utf-8")).get("sandoriai", [])
    except (OSError, ValueError):
        sand = []
    pirkta = {str((x.get("irodymas") or {}).get("skelbimo_id")) for x in sand} | {x.get("nuoroda") for x in sand}
    irasai = []
    for sid, e in rek.items():
        s = istorija.get(sid)
        if not s:
            continue
        busena = "nupirkta" if sid in pirkta or s.get("nuoroda") in pirkta else "dingo" if s.get("dingo") else "aktyvus"
        x = {"id": sid, "pavadinimas": s.get("pavadinimas"), "nuoroda": s.get("nuoroda"), "nuotrauka": s.get("nuotrauka"),
             "kaina": s.get("kaina"), "vieta_laikas": s.get("vieta_laikas"), "paieska": s.get("paieska"),
             "pastebetas": s.get("pastebetas"), "rekomenduota": e.get("rekomenduota"), "sprendimas": e.get("sprendimas"),
             "pelnas": e.get("pelnas"), "max_pirkimo": e.get("max_pirkimo"), "tiketina_pardavimo": e.get("tiketina_pardavimo"),
             "vietinis": e.get("vietinis"), "busena": busena, "dingo": s.get("dingo"),
             "dar_buvo": max(s.get("paskutini_karta_matytas", ""), s.get("aktyvus_patikrinta", "")) or None}
        if s.get("dingo"):
            nuo, iki = _laikas(s["pastebetas"]), _laikas(s["dingo"])
            dar_buvo = _laikas(max(s.get("paskutini_karta_matytas", ""), s.get("aktyvus_patikrinta", "")) or s["pastebetas"])
            x["gyvavo_val"] = round((iki - nuo).total_seconds() / 3600, 1)
            x["gyvavo_min_val"] = round((dar_buvo - nuo).total_seconds() / 3600, 1)
            x["tikslu"] = (iki - dar_buvo).total_seconds() <= 7 * 3600
        irasai.append(x)
    irasai.sort(key=lambda x: x.get("dingo") or x.get("rekomenduota") or "", reverse=True)
    dingo = [x for x in irasai if x["busena"] == "dingo"]
    tikslus = sorted(x["gyvavo_val"] for x in dingo if x.get("tikslu"))
    return {"irasai": irasai, "rekomenduota": len(irasai), "dingo": len(dingo),
            "nupirkta": sum(x["busena"] == "nupirkta" for x in irasai),
            "praleistas_pelnas": round(sum(x.get("pelnas") or 0 for x in dingo if (x.get("pelnas") or 0) > 0)),
            "gyvavo_mediana_val": round(statistics.median(tikslus), 1) if tikslus else None,
            "dingo_per_24h": sum(v <= 24 for v in tikslus), "tiksliu": len(tikslus)}


def main() -> int:
    vert_kelias = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "vertinimai.json"
    isvestis = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "docs" / "analize.json"
    istorija = json.loads(SKELBIMAI.read_text(encoding="utf-8"))
    try:
        vertinimai = json.loads(vert_kelias.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        vertinimai = {}
    kal = kalibracija()
    visi = [s for s in istorija.values() if not perka(s) and palyginamas(s)]
    for s in visi:
        s["_raktas"] = modelio_raktas(s)
    riba = (datetime.now(timezone.utc) - timedelta(hours=SVIEZUMAS_VAL)).strftime("%Y-%m-%dT%H:%M:%SZ")
    radiniai = []
    for s in visi:
        if not s.get("tinka") or s.get("pastebetas", "") < riba:
            continue
        a = ivertinti(s, visi, vertinimai.get(s["id"]))
        radiniai.append({k: s.get(k) for k in ("id", "nuoroda", "pavadinimas", "kaina", "nuotrauka", "aprasymas",
                                               "vieta_laikas", "paieska", "pastebetas", "parametrai", "pilnas_aprasymas",
                                               "bukle")} | a)
    istor = rekomendaciju_istorija(radiniai, istorija, vertinimai)
    tvarka = {"verta": 0, "derėtis": 1, "tikrinti": 2, "nežinoma": 3, "praleisti": 4}
    radiniai.sort(key=lambda r: (tvarka.get(r["sprendimas"], 9), -(r["balas"] or 0)))
    rinka = {}
    for s in visi:
        if s.get("kaina"):
            rinka.setdefault(s["_raktas"], []).append(s["kaina"])
    out = {"sugeneruota": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "prielaidos": N,
           "skelbimu_istorijoje": len(visi), "radiniai": radiniai, "kalibracija": kal,
           "pardavimas": pardavimo_pagalba(visi), "istorija": istor,
           "rinka": {k: {"n": len(v), "mediana": round(statistics.median(v)), "min": min(v), "max": max(v)}
                     for k, v in rinka.items() if len(v) >= 2}}
    isvestis.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Radinių: {len(radiniai)}", dict(Counter(r["sprendimas"] for r in radiniai)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
