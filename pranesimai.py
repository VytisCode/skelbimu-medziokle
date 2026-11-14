"""Siunčia Gmail laišką apie naujus „verta“ / „derėtis“ radinius.

Slaptažodžiai tik iš GitHub Secrets: GMAIL_USER, GMAIL_PASSWORD (app password), RECIPIENT_EMAIL.
Jau praneštų skelbimų id saugomi data/pranesta.json, kad tas pats nebūtų siunčiamas du kartus.
"""
import json
import os
import smtplib
import sys
import time
from email.header import Header
from email.utils import formataddr
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape
from pathlib import Path
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import re

ANALIZE = Path("docs/analize.json")
PRANESTA = Path("data/pranesta.json")
SVETAINE = "https://vytiscode.github.io/skelbimu-medziokle/"
SPRENDIMAI = ("verta",)
MAX_LAISKE = 5


def eur(x):
    return "?" if x is None else f"{x:.0f} €"


def kiek(n):
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} skelbimą"
    if 2 <= n % 10 <= 9 and not 12 <= n % 100 <= 19:
        return f"{n} skelbimus"
    return f"{n} skelbimų"


def pastraipos(r):
    """Vienas radinys – tie patys paaiškinimai kaip svetainėje, paprastais sakiniais."""
    p = [r.get("isvada") or f"Prašo {eur(r.get('kaina'))}."]
    p.append(f"Prašo {eur(r.get('kaina'))}, perpardavęs gautum ~{eur(r.get('tiketina_pardavimo'))}.")
    p += ["✓ " + x for x in r.get("uz", [])[:3]]
    p += ["✗ " + x for x in r.get("pries", [])[:2]]
    if r.get("naujo_min"):
        p.append(f"Naujas parduotuvėje – nuo {eur(r['naujo_min'])}.")
    planas = (r.get("derybos") or {}).get("planas")
    if planas:
        p.append("Derybos: " + planas[0])
    if r.get("logistika"):
        p.append(r["logistika"])
    g = r.get("saugumas")
    if g:
        p.append(f"Sukčių rizika: {g['lygis']}. {g['zingsniai'][0]}")
    return p


def laiskas(siusti, viso):
    vienas = len(siusti) == 1
    pirmas = siusti[0]
    tema = (f"{pirmas['pavadinimas'][:45]} už {eur(pirmas.get('kaina'))} – galima uždirbti ~{eur(pirmas.get('pelnas'))}" if vienas
            else f"Radau {kiek(viso)} verta pažiūrėti – geriausias {pirmas['pavadinimas'][:35]} (~{eur(pirmas.get('pelnas'))})")
    ivadas = "radau skelbimą, kurį verta pažiūrėti." if vienas else f"radau {kiek(viso)}, kuriuos verta pažiūrėti. Geriausi viršuje."
    txt, html = [f"Labas,\n\n{ivadas}"], [f"<p>Labas,</p><p>{escape(ivadas)}</p>"]
    for r in siusti:
        pa = pastraipos(r)
        txt.append(f"{r['pavadinimas']}\n" + "\n".join(pa) + f"\n{r['nuoroda']}")
        html.append(
            f'<div style="margin:18px 0;padding:14px 16px;border:1px solid #ddd;border-radius:10px">'
            f'<div style="font-size:17px;font-weight:bold;margin-bottom:6px">{escape(r["pavadinimas"])}</div>'
            + "".join(f'<p style="margin:4px 0">{escape(x)}</p>' for x in pa)
            + f'<p style="margin:10px 0 0"><a href="{escape(r["nuoroda"])}" style="background:#2e7d4f;color:#fff;padding:8px 14px;border-radius:6px;text-decoration:none;display:inline-block">Atidaryti skelbimą</a></p></div>')
    if viso > len(siusti):
        txt.append(f"Dar {viso - len(siusti)} rasi svetainėje.")
        html.append(f"<p>Dar {viso - len(siusti)} rasi svetainėje.</p>")
    pabaiga = "Visi palyginimai ir derybų patarimai – svetainėje. Pirkti ar ne, sprendi tu."
    txt.append(f"{pabaiga}\n{SVETAINE}")
    html.append(f'<p>{pabaiga}<br><a href="{SVETAINE}">{SVETAINE}</a></p>')
    msg = MIMEMultipart("alternative")
    msg.attach(MIMEText("\n\n".join(txt), "plain", "utf-8"))
    msg.attach(MIMEText('<div style="font-family:Arial,sans-serif;font-size:15px;line-height:1.45;color:#222;max-width:560px">' + "".join(html) + "</div>", "html", "utf-8"))
    msg["Subject"] = tema
    return msg


NUSTATYMAI = json.loads(Path("nustatymai.json").read_text(encoding="utf-8"))
DEFEKTAI = re.compile(r"neveik|wi-?fi|neprisijung|įskil|iskil|suskil|skilęs|užrakint|uzrakint|dalims|be pulto|sugad|defekt|"
                      r"nekraun|neįsijung|neisijung|blokuot|icloud", re.I)


PADIRBINIAI = re.compile(r"supersonic|airwrap|corrale|airpods", re.I)


def tinka_laiskui(r) -> str | None:
    """Grąžina priežastį, kodėl NEsiųsti (None – siųsti). Ribos: nustatymai.json → laiskai."""
    L = NUSTATYMAI.get("laiskai", {})
    if r.get("sprendimas") != "verta":
        return "ne „Pirkti“"
    if (r.get("pelnas") or 0) < L.get("min_pelnas_eur", 20):
        return "per mažas pelnas"
    if (r.get("kaina") or 0) > L.get("max_kaina_eur", 300):
        return "brangiau nei kapitalas"
    if r.get("amzius_d") is not None and r["amzius_d"] > L.get("max_amzius_d", 7):
        return "senas skelbimas"
    if DEFEKTAI.search((r.get("pilnas_aprasymas") or r.get("aprasymas") or "") + " " + (r.get("pavadinimas") or "")):
        return "defekto žodžiai aprašyme"
    if r.get("modelio_neatitikimas"):
        return "modelis neaiškus"
    if PADIRBINIAI.search(r.get("pavadinimas") or "") and not (r.get("kastai") or {}).get("vietinis"):
        return "dažnai klastojamas daiktas siunta"
    return None


def tyla() -> bool:
    nuo, iki = NUSTATYMAI.get("laiskai", {}).get("tylos_valandos", [23, 7])
    h = datetime.now(ZoneInfo("Europe/Vilnius")).hour
    return h >= nuo or h < iki


def nauju_laiskas(progos):
    pirmas = progos[0]
    tema = (f"Naujas iš ES: {pirmas['modelis'][:45]} – galima uždirbti ~{eur(pirmas.get('pelnas'))}" if len(progos) == 1
            else f"Nauji iš ES: {len(progos)} progos – geriausia {pirmas['modelis'][:35]} (~{eur(pirmas.get('pelnas'))})")
    txt, html = ["Labas,\n\nradau naujų daiktų, kuriuos ES parduotuvėje galima nupirkti pigiau, nei jie parduodami Lietuvoje."], \
        ["<p>Labas,</p><p>radau naujų daiktų, kuriuos ES parduotuvėje galima nupirkti pigiau, nei jie parduodami Lietuvoje.</p>"]
    for r in progos[:MAX_LAISKE]:
        es = r["es"][0]
        pa = [f"Pirk: {es.get('parduotuve')} už {eur(es['viso'])} su siuntimu į LT.",
              f"Lietuvoje pigiausia parduotuvė: {eur(r.get('lt_min'))}. Parduosi ~{eur(r.get('pardavimo'))}.",
              r.get("skaiciavimas", ""),
              "Prieš pirkdamas krepšelyje patikrink galutinę kainą su siuntimu į Lietuvą ir ar prekė dar yra."]
        txt.append(f"{r['modelis']}\n" + "\n".join(pa) + f"\n{es.get('url', '')}")
        html.append('<div style="margin:18px 0;padding:14px 16px;border:1px solid #ddd;border-radius:10px">'
                    f'<div style="font-size:17px;font-weight:bold;margin-bottom:6px">{escape(r["modelis"])}</div>'
                    + "".join(f'<p style="margin:4px 0">{escape(x)}</p>' for x in pa)
                    + f'<p style="margin:10px 0 0"><a href="{escape(es.get("url", SVETAINE))}" style="background:#2a62b8;color:#fff;padding:8px 14px;border-radius:6px;text-decoration:none;display:inline-block">Atidaryti parduotuvę</a></p></div>')
    txt.append(f"Visi skaičiavimai: {SVETAINE}nauji.html")
    html.append(f'<p>Visi skaičiavimai: <a href="{SVETAINE}nauji.html">{SVETAINE}nauji.html</a></p>')
    return tema, txt, html


def sveikatos_laiskas(problemos):
    tema = "Skelbimų medžioklė: sistema neveikia kaip turi"
    txt = ["Labas,", "radau problemų, dėl kurių gali praleisti progas:"] + ["– " + p for p in problemos] + [SVETAINE]
    html = ["<p>Labas,</p><p>radau problemų, dėl kurių gali praleisti progas:</p><ul>"] + [f"<li>{escape(p)}</li>" for p in problemos] + [f"</ul><p><a href=\"{SVETAINE}\">{SVETAINE}</a></p>"]
    return tema, txt, html


def sudaryti(tema, txt, html):
    msg = MIMEMultipart("alternative")
    msg.attach(MIMEText("\n\n".join(txt), "plain", "utf-8"))
    msg.attach(MIMEText('<div style="font-family:Arial,sans-serif;font-size:15px;line-height:1.45;color:#222;max-width:560px">' + "".join(html) + "</div>", "html", "utf-8"))
    msg["Subject"] = tema
    return msg


def siusti(user, pw, to, msg) -> bool:
    msg["From"], msg["To"] = formataddr((str(Header("Skelbimų medžioklė", "utf-8")), user)), to
    klaidos = []
    for bandymas in range(3):
        etapas = "jungiamasi"
        try:
            if bandymas == 1:  # atsarginis kelias – STARTTLS per 587
                s = smtplib.SMTP("smtp.gmail.com", 587, timeout=60)
                etapas = "starttls"; s.starttls()
            else:
                s = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60)
            etapas = "prisijungimas"; s.login(user, pw)
            etapas = "siuntimas"; s.sendmail(user, [a.strip() for a in to.split(",") if a.strip()], msg.as_string())
            s.quit()
            return True
        except smtplib.SMTPAuthenticationError as e:
            print("Gmail atmetė prisijungimą – patikrink GMAIL_USER ir GMAIL_PASSWORD (reikia App password):", e.smtp_code)
            return False
        except Exception as e:
            klaidos.append(f"{etapas}: {type(e).__name__}: {e}")
            time.sleep(5)
    print("Laiško išsiųsti nepavyko:", "; ".join(klaidos))
    return False


def problemos(a) -> list[str]:
    sv = a.get("sveikata") or {}
    out = []
    now = datetime.now(timezone.utc)
    cv = sv.get("claude_vertinimas")
    if not cv or now.date() - datetime.strptime(cv, "%Y-%m-%d").date() > timedelta(days=1):
        out.append(f"Claude vertinimas nevyko nuo {cv or 'niekada'}. Patikrink suplanuotą užduotį „Skelbimų vertinimas“.")
    nd = sv.get("nauji_atnaujinta")
    if not nd or now.date() - datetime.strptime(nd, "%Y-%m-%d").date() > timedelta(days=3):
        out.append(f"Naujų daiktų ES kainos neatnaujintos nuo {nd or 'niekada'}.")
    return out


def main():
    user, pw, to = (os.environ.get(k, "").strip() for k in ("GMAIL_USER", "GMAIL_PASSWORD", "RECIPIENT_EMAIL"))
    if not (user and pw and to):
        print("Gmail secrets nenustatyti – pranešimai nesiunčiami.")
        return
    # App password Google rodo kaip „abcd efgh ijkl mnop“ – tarpai ir eilučių lūžiai tik kosmetika
    pw = "".join(pw.split())
    user = "".join(user.split())
    if tyla():
        print("Tylos valandos (Vilniaus laiku) – laiškai bus išsiųsti ryte.")
        return
    pranesta = set(json.loads(PRANESTA.read_text())) if PRANESTA.exists() else set()
    a = json.loads(ANALIZE.read_text())
    pakeista = False

    # 1. Naudoti daiktai: tik „Pirkti“, perėję visas ribas
    nauji, atmesti = [], {}
    for r in a.get("radiniai", []):
        if str(r["id"]) in pranesta:
            continue
        kodel = tinka_laiskui(r)
        if kodel is None:
            nauji.append(r)
        elif r.get("sprendimas") in ("verta", "derėtis"):
            atmesti[kodel] = atmesti.get(kodel, 0) + 1
    print("Nesiųsta:", atmesti)
    if nauji:
        nauji.sort(key=lambda r: -(r.get("balas") or 0))
        if siusti(user, pw, to, laiskas(nauji[:MAX_LAISKE], len(nauji))):
            pranesta.update(str(r["id"]) for r in nauji)
            pakeista = True
            print(f"Išsiųsta apie {len(nauji)} radinius.")

    # 2. Nauji daiktai iš ES: raktas su kaina, kad pigesnė ES kaina vėl praneštų
    progos = [r for r in (a.get("nauji") or {}).get("produktai", []) if r.get("sprendimas") == "proga"
              and f"naujas:{r['id']}:{round(r['es_kaina'])}" not in pranesta]
    if progos and siusti(user, pw, to, sudaryti(*nauju_laiskas(progos))):
        pranesta.update(f"naujas:{r['id']}:{round(r['es_kaina'])}" for r in progos)
        pakeista = True
        print(f"Išsiųsta apie {len(progos)} naujų daiktų progas.")

    # 2b. Asmeninės paieškos (ne perpardavimui): kiekvienas naujas tinkamas skelbimas arba atpigęs
    asm = [s for s in a.get("asmeniniai", []) if f"asm:{s['id']}:{s.get('kaina')}" not in pranesta]
    if asm:
        tema = (f"Radau: {asm[0]['pavadinimas'][:50]} – {eur(asm[0]['kaina'])}" if len(asm) == 1
                else f"Radau {len(asm)} skelbimus: {asm[0]['paieska']} nuo {eur(asm[0]['kaina'])}")
        txt = ["Labas,\n\ntavo asmeninėje paieškoje atsirado (ar atpigo) šie skelbimai:"]
        html = ["<p>Labas,</p><p>tavo asmeninėje paieškoje atsirado (ar atpigo) šie skelbimai:</p>"]
        for s in asm[:MAX_LAISKE]:
            virs = f" (virš tavo {eur(s['riba'])} ribos – derėkis)" if s.get("riba") and s["kaina"] > s["riba"] else ""
            txt.append(f"{s['pavadinimas']} – {eur(s['kaina'])}{virs} ({s.get('vieta_laikas') or ''})\n{s['nuoroda']}")
            html.append(f'<p style="margin:10px 0"><a href="{escape(s["nuoroda"])}">{escape(s["pavadinimas"])}</a> – '
                        f'<b>{eur(s["kaina"])}</b>{escape(virs)}<br><span style="color:#666">{escape(s.get("vieta_laikas") or "")}</span></p>')
        txt.append("Prieš pirkdamas pasitikrink, ar tinka tavo modeliui (XJ6N, ne Diversion), ir tvirtinimus.")
        html.append("<p>Prieš pirkdamas pasitikrink, ar tinka tavo modeliui (XJ6N, ne Diversion), ir tvirtinimus.</p>")
        if siusti(user, pw, to, sudaryti(tema, txt, html)):
            pranesta.update(f"asm:{s['id']}:{s.get('kaina')}" for s in asm)
            pakeista = True
            print(f"Išsiųsta apie {len(asm)} asmeninius radinius.")

    # 3. Sveikata: kartą per dieną, jei kas nors sustojo
    pr = problemos(a)
    raktas = "sveikata:" + datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if pr and raktas not in pranesta and siusti(user, pw, to, sudaryti(*sveikatos_laiskas(pr))):
        pranesta.add(raktas)
        pakeista = True
    if pakeista:
        PRANESTA.write_text(json.dumps(sorted(pranesta), ensure_ascii=False))


if __name__ == "__main__":
    main()
