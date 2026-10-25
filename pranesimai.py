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

ANALIZE = Path("docs/analize.json")
PRANESTA = Path("data/pranesta.json")
SVETAINE = "https://vytiscode.github.io/skelbimu-medziokle/"
SPRENDIMAI = ("verta", "derėtis")
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


def main():
    user, pw, to = (os.environ.get(k, "").strip() for k in ("GMAIL_USER", "GMAIL_PASSWORD", "RECIPIENT_EMAIL"))
    if not (user and pw and to):
        print("Gmail secrets nenustatyti – pranešimai nesiunčiami.")
        return
    # App password Google rodo kaip „abcd efgh ijkl mnop“ – tarpai ir eilučių lūžiai tik kosmetika
    pw = "".join(pw.split())
    user = "".join(user.split())
    print("Patikra: GMAIL_USER su @:", "@" in user, "| App password 16 raidžių:", len(pw) == 16 and pw.isalpha())
    pranesta = set(json.loads(PRANESTA.read_text())) if PRANESTA.exists() else set()
    radiniai = json.loads(ANALIZE.read_text()).get("radiniai", [])
    nauji = [r for r in radiniai if r.get("sprendimas") in SPRENDIMAI and str(r["id"]) not in pranesta]
    if not nauji:
        print("Naujų radinių pranešimui nėra.")
        return
    nauji.sort(key=lambda r: -(r.get("balas") or 0))
    msg = laiskas(nauji[:MAX_LAISKE], len(nauji))
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
            break
        except smtplib.SMTPAuthenticationError as e:
            print("Gmail atmetė prisijungimą – patikrink GMAIL_USER ir GMAIL_PASSWORD (reikia App password):", e.smtp_code)
            sys.exit(0)
        except Exception as e:
            klaidos.append(f"{etapas}: {type(e).__name__}: {e}")
            time.sleep(5)
    else:
        print("Laiško išsiųsti nepavyko:", "; ".join(klaidos))
        sys.exit(0)
    pranesta.update(str(r["id"]) for r in nauji)
    PRANESTA.write_text(json.dumps(sorted(pranesta), ensure_ascii=False))
    print(f"Išsiųsta apie {len(nauji)} radinius.")


if __name__ == "__main__":
    main()
