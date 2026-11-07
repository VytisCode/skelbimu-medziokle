# Kasdienis Claude vertinimas

Šias instrukcijas kiekvieną rytą vykdo Claude suplanuota užduotis. Tikslas: pradedančiajam perpardavėjui
(2–3 val. per savaitę, kapitalas 200–300 €, gyvena Vilniuje; kitur – tik siunta į paštomatą) pasakyti, ką pirkti, už kiek ir už kiek parduoti.
Taupyk limitą: dirbk tiesiai, be ilgų paaiškinimų. Per dieną: ne daugiau 15 naudotų skelbimų (A dalis) ir 8 naujų daiktų kainų patikrų (B dalis).

**A dalis – naudoti skelbimai (Skelbiu.lt).**

## Žingsniai

1. `python3 analize.py` (sukuria `docs/analize.json` iš naujausių duomenų).
2. Iš `docs/analize.json` → `radiniai` paimk skelbimus, kurių sprendimas `verta`, `derėtis`, `tikrinti` arba
   `nežinoma`, ir kurių dar nėra `data/vertinimai.json` (arba įvertinti prieš > 3 dienas ir kaina pasikeitė).
   Pirmenybė: `verta` (laiško kandidatai), tada didžiausias galimas pelnas, tada naujausi. Ne daugiau 15.
3. Kiekvienam (vienodo modelio skelbimams paieškos daryk vieną kartą):
   - Tiksliai atpažink modelį (pvz. „Makita DTD152Z be baterijos“, „LEGO 42125 Ferrari 488 GTE“). Perskaityk VISĄ aprašymą:
     jei aprašyme kitas modelis ar karta nei pavadinime (pvz. pavadinime Fenix 7, aprašyme Fenix 5), vertink pagal aprašymą ir
     sprendimas `tikrinti`. Defektai aprašyme (neveikia, Wi-Fi, įskilęs, užrakintas) – niekada ne `verta`.
   - Naujo daikto kaina: 2–3 patikimos ES / LT e. parduotuvės su kaina ir siuntimu į Lietuvą (WebSearch,
     „standard“, daugiausia 2 paieškos modeliui). Kiekvieną įrašyk į `parduotuves` su tikslia produkto nuoroda.
   - Tikėtina pardavimo kaina Lietuvoje naudotam daiktui (realiai parduodama, ne prašoma): remkis
     `docs/analize.json` → `rinka`, `data/skelbimai.json` panašiais skelbimais, būkle, komplektacija.
     Niekada ne daugiau 85 % naujo kainos. `kainos_pagrindimas` – vienas sakinys, iš ko tai išvesta (skaičiai).
   - Didelis daiktas (netelpa į paštomatą) ne iš Vilniaus – `praleisti`.
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
   - TIK `verta` ir `derėtis` (ir `tikrinti`, jei trūksta vieno atsakymo) – pradedančiajam suprantama instrukcija,
     trumpai ir be mokslo:
     - `apie`: 1–2 sakiniai – kas tai, versijos / kartos ir kas lemia kainą.
     - `tikrinti`: 3–5 konkretūs dalykai, ką patikrinti ar paklausti prieš perkant (serijos nr., baterija, komplektas, padirbiniai).
     - `galimybe`: kodėl tai proga – palygink su brangesniais to paties modelio skelbimais (ar matai skirtumą?), su nauja kaina.
     - `pardavimas`: 2–4 patarimai, kaip ir už kiek parduoti (kaina skelbime, ką paminėti, sezonas).
4. Įrašyk į `data/vertinimai.json` (raktas – skelbimo `id`):
   ```json
   {"modelis": "", "naujo_kaina": 0, "naujo_saltinis": "https://…",
    "parduotuves": [{"parduotuve": "pigu.lt", "kaina": 0, "su_siuntimu": true, "url": "https://…"}],
    "tiketina_pardavimo": 0, "kainos_pagrindimas": "", "patikimumas": "vidutinis", "sprendimas": "verta",
    "priezastis": "", "rizikos": "", "skelbimo_tekstas": "", "stovas": false, "ivertinta": "YYYY-MM-DD",
    "apie": "", "tikrinti": [], "galimybe": "", "pardavimas": []}
   ```
5. Įrodymai pirkiniams: `docs/sandoriai.json` (pildo vartotojas svetainėje). Jei kuris įrašas turi nuorodą, bet neturi
   `irodymas`, užpildyk jį iš `data/skelbimai.json` (pavadinimas, kaina, vieta_laikas, aprasymas ≤ 600 simb., bukle,
   pastebetas, uzfiksuota, saltinis: "istorija"). Kitų žurnalo laukų nekeisk.
6. Atlik B dalį (žemiau).
7. Vėl `python3 analize.py`, tada `git pull --rebase origin main`, commit „Claude vertinimas YYYY-MM-DD“, push į `main`.

## B dalis – nauji daiktai: ES parduotuvė → parduoti Lietuvoje

Vartotojo testas (nuo 2026-11-07, kelias savaites): ar naują daiktą galima nupirkti ES e. parduotuvėje pigiau ir parduoti LT.
Skelbiu.lt – tik LT kainų šaltinis. Duomenys `data/nauji.json`, svetainė `docs/nauji.html` skaičiuoja pelną pati.

1. Produktų sąrašas `produktai` – iki 30 konkrečių naujų modelių. Rinkis: populiarūs Skelbiu.lt (`docs/analize.json` → `rinka`,
   n ≥ 4), naujas kainuoja 60–400 €, telpa į paštomatą, ne šalmai / kėdutės / maistas / kosmetika. Pvz. DJI Osmo Pocket 3,
   GoPro Hero 13, Garmin Venu 3, Garmin Forerunner 265, Kindle Paperwhite, LEGO Technic rinkiniai, Makita DTD153Z, Dyson V-serija,
   Nintendo Switch žaidimai / pultai. Nenaudingus (3 kartus iš eilės `ne`) pakeisk naujais.
2. Kasdien atnaujink iki 8 produktų, kurių `atnaujinta` seniausia (> 3 d.) arba kurių kainų dar nėra. KAINAS RENKA
   AUTOMATAS (`kainos.py`, GitHub Actions per LT proxy) – tavo darbas rasti TIKSLIAS PRODUKTŲ NUORODAS (WebSearch „standard“,
   ≤ 3 paieškos produktui). Kaina, kurią matai paieškoje, gali būti įrašyta kaip pradinė su `patikrinta`, automatas ją pakeis.
   - `lt`: 2–3 LT parduotuvių produkto puslapiai: pigu.lt, varle.lt, bigbox.lt, technorama.lt, topocentras.lt, 1a.lt,
     senukai.lt. NE kaina24.lt / kainos.lt (blokuoja automatą). Be LT kainos produktas nevertinamas.
   - `es`: 1–3 ES parduotuvių, kurios SIUNČIA Į LIETUVĄ (`parduotuves` sąrašas žemiau), produkto puslapiai su `siunta_eur`
     į LT. Jei siuntimo į LT kainos nežinai – įrašyk geriausią įvertį ir `pastaba`.
     Parduotuvę, kuri nesiunčia į LT, įrašyk į `parduotuves` su `siuncia_i_lt: false` ir jos nebenaudok.
   - Žiūrėk `docs/analize.json` → `nauji.tikrinamos`: parduotuvių su `neveikia` nuorodas pakeisk kitų parduotuvių nuorodomis.
   - `skelbiu_tinka` / `skelbiu_atmesti`: regex (be diakritikų) Skelbiu.lt pavadinimams, kad būtų lyginama tik tas pats modelis
     (pvz. Pocket 3: tinka `pocket\\s*3`, atmesti `pocket\\s*[24]|combo|creator`). Privaloma.
   - Atranka pagal duomenis: pirmenybė modeliams, kurių nauji Skelbiu.lt skelbimai ar LT parduotuvės kaina bent 20 % didesnė
     už ES kainą su siuntimu. Jei ES kaina ≥ naujų Skelbiu skelbimų kainos (kaip GoPro 13 2026-11-07), produktą keisk.
   - `patikrinta`: data (YYYY-MM-DD) kiekvienai kainai; produktui `atnaujinta`.
   - Lygink TIK tą patį modelį ir komplektaciją (pvz. Pocket 3 vs Pocket 3 Creator Combo – skirtingi produktai).
   - `raktas`: `docs/analize.json` → `rinka` raktas, kuriuo Skelbiu.lt žymi tą modelį (pvz. `dji-osmopocket`), jei yra.
3. `parduotuves` – ES parduotuvių sąrašas su `pavadinimas`, `salis`, `url`, `siuncia_i_lt` (true / false / null – nežinoma),
   `siunta_eur`, `pastaba`, `patikrinta`. Papildyk, kai randi naują pigią parduotuvę, siunčiančią į LT.
4. Formatas:
   ```json
   {"atnaujinta": "YYYY-MM-DD", "parduotuves": [...],
    "produktai": [{"id": "dji-osmo-pocket-3", "modelis": "DJI Osmo Pocket 3", "kategorija": "DJI", "raktas": "dji-osmopocket",
      "lt": [{"parduotuve": "pigu.lt", "kaina": 0, "url": "https://…", "patikrinta": "YYYY-MM-DD"}],
      "es": [{"parduotuve": "Amazon.de", "salis": "DE", "kaina": 0, "siunta_eur": 0, "url": "https://…", "patikrinta": "YYYY-MM-DD", "pastaba": ""}],
      "atnaujinta": "YYYY-MM-DD", "pastabos": ""}]}
   ```
5. Niekada neįrašyk kainos be nuorodos ir neišgalvok kainų. Jei nepavyko rasti – palik tuščią ir parašyk `pastabos`.

## Taisyklės

- Niekada nieko nepirk, nerašyk pardavėjams, nedėk skelbimų.
- Repo viešas: jokių asmens duomenų (vardų, telefonų, adresų). Žurnalas vieša vartotojo sutikimu.
- Nekeisk `skelbiu.py`, workflow failų ir `pension-fund-tracker` repo.
- Pabaigoje viena eilutė: kiek įvertinta, kiek „verta“, geriausias radinys su pelnu; kiek naujų daiktų atnaujinta ir geriausia ES proga.
