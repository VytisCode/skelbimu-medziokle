"""Siunčia Gmail laišką apie naujus „verta“ / „derėtis“ radinius.

Slaptažodžiai tik iš GitHub Secrets: GMAIL_USER, GMAIL_PASSWORD (app password), RECIPIENT_EMAIL.
Jau praneštų skelbimų id saugomi data/pranesta.json, kad tas pats nebūtų siunčiamas du kartus.
"""
import json
import os
import smtplib
import sys
from email.mime.text import MIMEText
from pathlib import Path

ANALIZE = Path("docs/analize.json")
PRANESTA = Path("data/pranesta.json")
SVETAINE = "https://vytiscode.github.io/skelbimu-medziokle/"
SPRENDIMAI = ("verta", "derėtis")
MAX_LAISKE = 5


def eur(x):
    return "—" if x is None else f"{x:.0f} €"


def blokas(r):
    d = r.get("derybos") or {}
    eil = [
        f"{r['pavadinimas']} – prašo {eur(r.get('kaina'))} ({r['sprendimas'].upper()})",
        f"  Parduosi už ~{eur(r.get('tiketina_pardavimo'))}, pelnas {eur(r.get('pelnas'))}, mokėk ne daugiau {eur(r.get('max_pirkimo'))}",
    ]
    if r.get("naujo_min"):
        eil.append(f"  Naujas parduotuvėje nuo {eur(r['naujo_min'])}")
    if r.get("kodel"):
        eil.append(f"  {r['kodel']}")
    if d.get("siulymas"):
        eil.append(f"  Derybos: siūlyk {eur(d['siulymas'])}, riba {eur(d.get('riba'))}")
    eil.append(f"  {(r.get('kastai') or {}).get('budas', '')} · patikimumas {r.get('patikimumas', '?')}")
    eil.append(f"  {r['nuoroda']}")
    return "\n".join(eil)


def main():
    user, pw, to = (os.environ.get(k, "").strip() for k in ("GMAIL_USER", "GMAIL_PASSWORD", "RECIPIENT_EMAIL"))
    if not (user and pw and to):
        print("Gmail secrets nenustatyti – pranešimai nesiunčiami.")
        return
    pranesta = set(json.loads(PRANESTA.read_text())) if PRANESTA.exists() else set()
    radiniai = json.loads(ANALIZE.read_text()).get("radiniai", [])
    nauji = [r for r in radiniai if r.get("sprendimas") in SPRENDIMAI and str(r["id"]) not in pranesta]
    if not nauji:
        print("Naujų radinių pranešimui nėra.")
        return
    nauji.sort(key=lambda r: -(r.get("balas") or 0))
    siusti = nauji[:MAX_LAISKE]
    tekstas = "\n\n".join(blokas(r) for r in siusti)
    if len(nauji) > len(siusti):
        tekstas += f"\n\nDar {len(nauji) - len(siusti)} – žr. svetainėje."
    tekstas += f"\n\nVisi radiniai ir įrodymai: {SVETAINE}\nSistema nieko neperka ir nerašo – sprendi tu."
    msg = MIMEText(tekstas, "plain", "utf-8")
    msg["Subject"] = f"Skelbimai: {len(nauji)} nauji radiniai, geriausias {siusti[0]['pavadinimas'][:40]} ({eur(siusti[0].get('pelnas'))})"
    msg["From"], msg["To"] = user, to
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
            s.login(user, pw)
            s.send_message(msg)
    except Exception as e:
        print("Laiško išsiųsti nepavyko:", type(e).__name__, e)
        sys.exit(0)
    pranesta.update(str(r["id"]) for r in nauji)
    PRANESTA.write_text(json.dumps(sorted(pranesta), ensure_ascii=False))
    print(f"Išsiųsta apie {len(nauji)} radinius.")


if __name__ == "__main__":
    main()
