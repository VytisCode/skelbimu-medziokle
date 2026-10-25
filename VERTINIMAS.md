# Kasdienis Claude vertinimas

Šias instrukcijas kiekvieną rytą vykdo Claude suplanuota užduotis. Tikslas: pradedančiajam perpardavėjui
(2–3 val. per savaitę, kapitalas 200–300 €, gyvena Vilniuje / Kėdainiuose; kitur – tik siunta į paštomatą) pasakyti, ką pirkti, už kiek ir už kiek parduoti.
Taupyk limitą: dirbk tiesiai, be ilgų paaiškinimų, ne daugiau 25 skelbimų per dieną.

## Žingsniai

1. `python3 analize.py` (sukuria `docs/analize.json` iš naujausių duomenų).
2. Iš `docs/analize.json` → `radiniai` paimk skelbimus, kurių sprendimas `verta`, `derėtis`, `tikrinti` arba
   `nežinoma`, ir kurių dar nėra `data/vertinimai.json` (arba įvertinti prieš > 3 dienas ir kaina pasikeitė).
   Pirmenybė: didžiausias galimas pelnas, tada naujausi. Ne daugiau 25.
3. Kiekvienam (vienodo modelio skelbimams paieškos daryk vieną kartą):
   - Tiksliai atpažink modelį (pvz. „Makita DTD152Z be baterijos“, „LEGO 42125 Ferrari 488 GTE“).
   - Naujo daikto kaina: 2–3 patikimos ES / LT e. parduotuvės su kaina ir siuntimu į Lietuvą (WebSearch,
     „standard“, daugiausia 2 paieškos modeliui). Kiekvieną įrašyk į `parduotuves` su tikslia produkto nuoroda.
   - Tikėtina pardavimo kaina Lietuvoje naudotam daiktui (realiai parduodama, ne prašoma): remkis
     `docs/analize.json` → `rinka`, `data/skelbimai.json` panašiais skelbimais, būkle, komplektacija.
     Niekada ne daugiau 85 % naujo kainos. `kainos_pagrindimas` – vienas sakinys, iš ko tai išvesta (skaičiai).
   - Didelis daiktas (netelpa į paštomatą) ne iš Vilniaus / Kėdainių – `praleisti`.
   - Patikimumas: `aukštas` (daug panašių skelbimų ir aiški naujo kaina), `vidutinis`, `žemas`.
   - Sprendimas: `verta` (pelnas ≥ 20 € ir ≥ 35 % po 6 € kaštų), `derėtis` (verta tik už mažesnę kainą – nurodyk
     kiek), `praleisti`. Priežastis – vienas sakinys lietuviškai, su skaičiais.
   - Rizikos: padirbiniai, užrakinti / „atrišti“ įrenginiai, baterijų nusidėvėjimas, trūkstamos detalės,
     „tik dalims“. Šalmai, vaikiškos automobilinės kėdutės ir kiti daiktai, kurių saugumo neįvertinsi iš
     nuotraukos – visada `praleisti`.
   - „Stovo tipo“ proga: jei tokie daiktai LT skelbimuose prašomi ≥ 25 % brangiau nei naujas ES su siuntimu,
     pažymėk `stovas: true` (tada verta pirkti naują ES ir parduoti LT).
   - Skelbimo tekstas Skelbiu.lt / Vinted: pavadinimas eilutėje, tada 3–5 sakiniai (būklė, komplektacija,
     kodėl verta, atsiėmimas / siuntimas). Be asmeninių duomenų.
4. Įrašyk į `data/vertinimai.json` (raktas – skelbimo `id`):
   ```json
   {"modelis": "", "naujo_kaina": 0, "naujo_saltinis": "https://…",
    "parduotuves": [{"parduotuve": "pigu.lt", "kaina": 0, "su_siuntimu": true, "url": "https://…"}],
    "tiketina_pardavimo": 0, "kainos_pagrindimas": "", "patikimumas": "vidutinis", "sprendimas": "verta",
    "priezastis": "", "rizikos": "", "skelbimo_tekstas": "", "stovas": false, "ivertinta": "YYYY-MM-DD"}
   ```
5. Įrodymai pirkiniams: privatus žurnalas https://claude.ai/artifact/BnoZFVQTbE2ErNKnU8aGji (ArtifactData,
   kolekcija `sandoriai`). Kiekvienam dokumentui su `skelbimo_id`, bet be `irodymas`, rask skelbimą
   `data/skelbimai.json` ir `update` lauką `irodymas` = {skelbimo_id, pavadinimas, kaina, nuoroda, vieta_laikas,
   aprasymas (≤500 simb.), nuotrauka, pastebetas, uzfiksuota (dabar), saltinis: "istorija"} (su `if_version`).
   Žurnalo duomenų niekada nekelk į repo.
6. Vėl `python3 analize.py`, tada `git pull --rebase origin main`, commit „Claude vertinimas YYYY-MM-DD“, push į `main`.

## Taisyklės

- Niekada nieko nepirk, nerašyk pardavėjams, nedėk skelbimų.
- Repo viešas: jokių vartotojo pirkimų, pardavimų, pelno ar asmeninių duomenų.
- Nekeisk `skelbiu.py`, workflow failų ir `pension-fund-tracker` repo.
- Pabaigoje viena eilutė: kiek įvertinta, kiek „verta“, geriausias radinys su pelnu.
