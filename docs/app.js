// Radiniai (analize.json, kas valandą) + sandorių žurnalas (sandoriai.json, įrašomas per GitHub API su vartotojo raktu).
const REPO = "VytisCode/skelbimu-medziokle", ZFAILAS = "docs/sandoriai.json";
const VMI_RIBA = 1900, PLATFORMU_RIBA = 30;   // registracijos priminimas; platformos praneša VMI nuo 30 pardavimų / 2000 €
const fmt = n => n == null || isNaN(n) ? "—" : (Math.round(n * 100) / 100).toLocaleString("lt-LT", {maximumFractionDigits: 2}) + " €";
const $ = id => document.getElementById(id);
const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
const link = (href, txt, cls) => { const a = el("a", cls || "", txt); a.href = href; a.target = "_blank"; a.rel = "noopener"; return a; };
const today = () => new Date().toISOString().slice(0, 10);
const days = (a, b) => Math.round((new Date(b) - new Date(a)) / 864e5);
const num = v => v === "" || v == null ? null : Number(v);
const LABEL = {verta: "Pirkti", derėtis: "Derėtis", tikrinti: "Patikrinti", nežinoma: "Laukia vertinimo", praleisti: "Praleisti"};
let D, B, filter = "verta", items = [], sha = null, editIdx = null, evidence = null;

// ---------- Kainų ašis: visi taškai vienoje linijoje, 100 % = naujo kaina (arba įprasta naudoto kaina) ----------
const pc = (v, base) => Math.round(v / base * 100) + " %";
function priceAxis(r) {
  const comps = r.visi_palyginami || [];
  if (!r.kaina || (!comps.length && !r.naujo_min)) return null;
  const base = r.naujo_min || r.mediana;
  const vals = comps.map(c => c.kaina).concat([r.kaina, r.tiketina_pardavimo, r.naujo_min, r.max_pirkimo].filter(Boolean));
  const top = Math.max(...vals) * 1.08;
  const X = v => (v / top * 100).toFixed(2) + "%";
  const box = el("div", "axisbox");
  // trumpa lentelė: kiek kas kainuoja ir kiek tai procentų nuo 100 %
  const sum = el("table", "axt"); const tb = el("tbody");
  const row = (k, t, v) => { const tr = el("tr", k); const td = el("td"); td.append(el("i", "k " + k), document.createTextNode(t)); tr.append(td, el("td", "n", v)); tb.append(tr); };
  const p = v => base ? " · " + pc(v, base) : "";
  row("me", "Šis skelbimas", fmt(r.kaina) + p(r.kaina));
  if (comps.length) { const lo = Math.min(...comps.map(c => c.kaina)), hi = Math.max(...comps.map(c => c.kaina));
    row("other", `Kiti ${comps.length} panašūs`, `${fmt(lo)}–${fmt(hi)}` + (base ? ` · ${pc(lo, base)}–${pc(hi, base)}` : "")); }
  if (r.tiketina_pardavimo) row("sell", "Tu parduosi už ~", fmt(r.tiketina_pardavimo) + p(r.tiketina_pardavimo));
  if (r.max_pirkimo) row("zone", "Apsimoka pirkti iki", fmt(r.max_pirkimo) + p(r.max_pirkimo));
  if (r.naujo_min) row("new", "Naujas parduotuvėje", fmt(r.naujo_min) + " · 100 %");
  sum.append(tb); box.append(sum);
  box.append(el("div", "sub", r.naujo_min ? "100 % = pigiausia naujo kaina parduotuvėje." : `100 % = įprasta naudoto kaina (${fmt(base)}). Naujo kainą Claude suras rytinėje peržiūroje.`));

  const ax = el("div", "axis");
  if (r.max_pirkimo) { const z = el("div", "zone"); z.style.width = X(r.max_pirkimo); z.title = "Apsimoka pirkti iki " + fmt(r.max_pirkimo); ax.append(z);
    }
  ax.append(el("div", "line"));
  if (base) [0.5, 1].forEach(f => { if (base * f > top) return; const t = el("div", "tick"); t.style.left = X(base * f); t.append(el("span", "", Math.round(f * 100) + " %")); ax.append(t); });
  for (const c of comps) { const d = link(c.nuoroda, ""); d.className = "dot other" + ((c.rizikos || []).length ? " risky" : ""); d.style.left = X(c.kaina);
    d.title = c.pavadinimas + " – " + fmt(c.kaina); d.setAttribute("aria-label", d.title); ax.append(d); }
  const pin = (v, cls, txt, lane) => { const d = el("div", "pin " + cls + " " + lane); d.style.left = X(v); d.append(el("span", "", txt)); ax.append(d);
    const dot = el("div", "dot " + cls); dot.style.left = X(v); ax.append(dot); };
  pin(r.kaina, "me", "Šis " + fmt(r.kaina), "up");
  if (r.tiketina_pardavimo) pin(r.tiketina_pardavimo, "sell", "Parduosi " + fmt(r.tiketina_pardavimo), "down");
  if (r.naujo_min) pin(r.naujo_min, "new", "Naujas " + fmt(r.naujo_min), Math.abs(r.naujo_min - r.kaina) / top < 0.3 ? "up2" : "up");
  box.append(ax);
  box.append(evidence_(r, base));
  return box;
}

// Įrodymų lentelė: kiekviena kaina su nuoroda
function evidence_(r, base) {
  const comps = r.visi_palyginami || [];
  const rows = comps.map(c => ({t: c.pavadinimas, url: c.nuoroda, v: c.kaina, risk: c.rizikos || [], cls: ""}));
  rows.push({t: "ŠIS SKELBIMAS", url: r.nuoroda, v: r.kaina, cls: "me"});
  (r.parduotuves || []).forEach(p => p.kaina && rows.push({t: "Naujas – " + (p.parduotuve || "parduotuvė"), url: p.url, v: p.kaina, cls: "new"}));
  rows.sort((a, b) => a.v - b.v);
  const det = el("details", "evid");
  det.append(el("summary", "", `Įrodymai: ${comps.length} panašūs skelbimai` + ((r.parduotuves || []).length ? ` ir ${r.parduotuves.length} parduotuvės` : "") + " su nuorodomis"));
  const t = el("table", "evt"); const tb = el("tbody");
  for (const x of rows) {
    const tr = el("tr", x.cls); const td = el("td");
    if (x.url) td.append(link(x.url, x.t)); else td.textContent = x.t;
    x.risk && x.risk.forEach(z => td.append(el("span", "flag risk", "⚠ " + z)));
    tr.append(td, el("td", "n", fmt(x.v)), el("td", "n", base ? pc(x.v, base) : "")); tb.append(tr);
  }
  t.append(tb); det.append(t);
  if (!(r.parduotuves || []).length) { det.append(el("div", "sub", "Naujo kainos Claude dar nepatikrino. Greita paieška:"));
    const q = el("div", "shops"); (r.parduotuviu_paieska || []).forEach(p => q.append(link(p.url, p.pavadinimas, "chip"))); det.append(q); }
  return det;
}

// ---------- Derybų suflerys: 3 žingsniai su sumomis ----------
function coach(r, open) {
  const d = r.derybos; if (!d || !d.planas) return null;
  const det = el("details", "coach"); det.open = !!open;
  det.append(el("summary", "", `Derybos: pradėk nuo ${fmt(d.siulymas)}`));
  const ol = el("ol", "plan"); d.planas.forEach(t => ol.append(el("li", "", t))); det.append(ol);
  const local = r.kastai && r.kastai.vietinis;
  const txt = `Laba diena, ar „${r.pavadinimas}“ dar parduodamas? Ar viskas veikia, nėra defektų? Kas įeina į komplektą? ` +
    `Galėčiau sumokėti ${d.siulymas} € ` + (local ? "ir atsiimti greitai." : "– jei išsiųstumėte išperkamąja siunta, sumokėčiau atsiimdamas.") + " Ačiū!";
  const pre = el("pre", "", txt); const btn = el("button", "copy", "Kopijuoti pirmą žinutę"); btn.type = "button";
  btn.onclick = () => navigator.clipboard.writeText(txt).then(() => btn.textContent = "Nukopijuota – įklijuok Skelbiu.lt žinutėje", () => getSelection().selectAllChildren(pre));
  det.append(pre, btn);
  det.append(el("p", "why", d.nauda), el("p", "why", d.kodel_suma));
  if (d.argumentai.length) {
    det.append(el("div", "sub", "Jei pardavėjas nenori leisti – paminėk:"));
    const ul = el("ul", "comps"); d.argumentai.forEach(a => { const li = el("li"); if (a.url) li.append(link(a.url, a.t)); else li.textContent = a.t; ul.append(li); }); det.append(ul);
  }
  return det;
}

// ---------- Apsauga nuo sukčių ----------
function safety(r, open) {
  const g = r.saugumas; if (!g) return null;
  const det = el("details", "safe s-" + g.lygis); det.open = !!open && g.lygis !== "maža";
  det.append(el("summary", "", `Sukčių rizika: ${g.lygis}. Kaip apsisaugoti`));
  const ol = el("ol", "plan"); g.zingsniai.forEach(t => ol.append(el("li", "", t))); det.append(ol);
  if (g.zinute) { const pre = el("pre", "", g.zinute); const b = el("button", "copy", "Kopijuoti klausimą pardavėjui"); b.type = "button";
    b.onclick = () => navigator.clipboard.writeText(g.zinute).then(() => b.textContent = "Nukopijuota", () => getSelection().selectAllChildren(pre)); det.append(pre, b); }
  return det;
}

// ---------- Kodėl taip / kodėl ne ----------
function reasons(r) {
  const box = el("div", "reasons");
  (r.uz || []).forEach(t => box.append(el("div", "rz plus", "✓ " + t)));
  (r.pries || []).forEach(t => box.append(el("div", "rz minus", "✗ " + t)));
  if (r.logistika) box.append(el("div", "rz", "🚚 " + r.logistika));
  return box;
}

// ---------- Radinio kortelė ----------
function card(r, big) {
  const c = el("article", "card" + (big ? " big" : ""));
  const img = el("img"); img.loading = "lazy"; img.alt = ""; img.referrerPolicy = "no-referrer";
  img.onerror = () => img.style.visibility = "hidden"; if (r.nuotrauka) img.src = r.nuotrauka;
  const head = el("div", "head"); const tt = el("div", "tt");
  tt.append(link(r.nuoroda, r.pavadinimas || "(be pavadinimo)"), el("span", "verdict v-" + r.sprendimas, LABEL[r.sprendimas] || r.sprendimas));
  head.append(img, tt);
  const body = el("div", "body");
  body.append(el("p", "isvada", r.isvada || r.priezastis || ""));
  const nums = el("div", "nums");
  const n = (t, v, cls) => { const s = el("span", "", t); s.append(el("b", cls || "", v)); nums.append(s); };
  n("Prašo", fmt(r.kaina)); n("Parduosi už ~", fmt(r.tiketina_pardavimo));
  n("Pelnas", fmt(r.pelnas), r.pelnas > 0 ? "pos" : r.pelnas < 0 ? "neg" : "");
  n("Mokėk ne daugiau", r.max_pirkimo ? fmt(r.max_pirkimo) : "—");
  body.append(nums, reasons(r));
  const axb = priceAxis(r); if (axb) body.append(axb);
  if (r.bukle) body.append(el("div", "meta", "Būklė: " + r.bukle));
  const sf = safety(r, big); if (sf) body.append(sf);
  const co = coach(r, big); if (co) body.append(co);
  body.append(el("div", "meta", [r.modelis, "kainos patikimumas: " + r.patikimumas, r.pelnas_per_val != null ? "~" + fmt(r.pelnas_per_val) + "/val." : "", r.vieta_laikas].filter(Boolean).join(" · ")));
  if (r.stovas) body.append(el("div", "why", "Stovo tipo proga: naujas ES su siuntimu pigesnis nei LT skelbimuose."));
  if (r.rizikos) body.append(el("div", "meta", "Claude: " + r.rizikos));

  const apr = r.pilnas_aprasymas || r.aprasymas;
  if (apr) { const d = el("details"); d.append(el("summary", "", r.pilnas_aprasymas ? "Pilnas aprašymas" : "Aprašymo pradžia"), el("p", "meta", apr)); body.append(d); }

  const how = el("details"); how.append(el("summary", "", "Kaip apskaičiuota"));
  const ol = el("ol", "steps"); (r.zingsniai || []).forEach(z => ol.append(el("li", "", z))); how.append(ol);
  body.append(how);

  if (r.skelbimo_tekstas) {
    const d = el("details"); d.append(el("summary", "", "Paruoštas skelbimo tekstas"));
    const pre = el("pre", "", r.skelbimo_tekstas); const btn = el("button", "copy", "Kopijuoti"); btn.type = "button";
    btn.onclick = () => navigator.clipboard.writeText(r.skelbimo_tekstas).then(() => btn.textContent = "Nukopijuota", () => getSelection().selectAllChildren(pre));
    d.append(pre, btn); body.append(d);
  }
  const buy = el("button", "copy", "Pirkau → į žurnalą"); buy.type = "button";
  buy.onclick = () => { try { localStorage.setItem("pirkau", JSON.stringify(r)); } catch {} location.href = "zurnalas.html#naujas"; };
  body.append(buy);
  c.append(head, body); return c;
}

function render() {
  const R = D.radiniai;
  if ($("market")) {
    const m = Object.entries(D.rinka).sort((x, y) => y[1].n - x[1].n);
    $("market").replaceChildren(...m.map(([k, v]) => { const tr = el("tr"); tr.append(el("td", "", k), el("td", "n", v.n), el("td", "n", fmt(v.mediana)), el("td", "n", fmt(v.min) + "–" + fmt(v.max))); return tr; }));
    assumptions();
  }
  if (!$("cards")) return;
  const cnt = k => R.filter(r => r.sprendimas === k).length;
  const best = R.filter(r => r.sprendimas === "verta" || r.sprendimas === "derėtis").sort((a, b) => b.balas - a.balas).slice(0, 3);
  $("bestWrap").hidden = !best.length;
  $("best").replaceChildren(...best.map(r => card(r, true)));
  const profit = R.filter(r => r.sprendimas === "verta").reduce((s, r) => s + (r.pelnas || 0), 0);
  $("tiles").replaceChildren(...[["verta", "Pirkti", cnt("verta")], ["derėtis", "Derėtis", cnt("derėtis")], ["tikrinti", "Patikrinti", cnt("tikrinti")], ["verta", "Galimas pelnas", fmt(profit)]]
    .map(([k, t, v]) => { const b = el("button", "tile"); b.type = "button"; b.append(el("span", "eyebrow", t), el("b", "", v));
      b.onclick = () => { filter = k; render(); $("radiniai").scrollIntoView({behavior: "smooth"}); }; return b; }));
  $("tabs").replaceChildren(...["verta", "derėtis", "tikrinti", "nežinoma", "praleisti", "visi"].map(k => {
    const b = el("button", "", (LABEL[k] || "Visi") + " (" + (k === "visi" ? R.length : cnt(k)) + ")");
    b.type = "button"; b.setAttribute("aria-pressed", k === filter); b.onclick = () => { filter = k; render(); }; return b;
  }));
  // piltuvas: kiek peržiūrėta ir kodėl atmesta – kad būtų matyti, jog tikrinama plačiai
  let fu = $("funnel"); if (!fu) { fu = el("p", "note"); fu.id = "funnel"; $("tiles").after(fu); }
  const why = {}; const add = k => why[k] = (why[k] || 0) + 1;
  R.forEach(r => { const z = r.priezastis || "";
    if (r.sprendimas === "praleisti") add(z.startsWith("didelis") ? "didelis daiktas iš kito miesto" : "per mažas pelnas ar grąža");
    else if (r.sprendimas === "nežinoma") add("nėra su kuo palyginti (įvertins Claude)");
    else if (r.sprendimas === "tikrinti") add("įtartina kaina, defektai ar neaiškus modelis"); });
  const kat = new Set(R.map(r => r.paieska)).size;
  fu.textContent = `Dabar stebima ${R.length} skelbimų iš ${kat} kategorijų (${(B && B.paieskos || []).length} paieškos). Atmesta ar laukia: ` +
    Object.entries(why).sort((a, b) => b[1] - a[1]).map(([k, v]) => `${k} – ${v}`).join(", ") + ". Kiekvieno priežastis – kortelėje.";
  const rows = R.filter(r => filter === "visi" || r.sprendimas === filter);
  $("cards").replaceChildren(...(rows.length ? rows.map(r => card(r)) : [el("p", "note", "Šioje grupėje šiuo metu nieko nėra.")]));
}

function assumptions() {
  const p = D.prielaidos;
  $("assumptions").textContent =
    `Prielaidos: vietiniai miestai ${p.vietiniai_miestai.join(", ")} (atsiėmimas ${fmt(p.atsiemimas_vietoje_eur)}, ~${p.laikas_vietoje_val} val.), kiti – siunta į paštomatą ${fmt(p.siunta_i_mane_eur)} (~${p.laikas_siunta_val} val.), dideli daiktai iš kitų miestų praleidžiami. ` +
    `Pakuotė / pardavimas ${fmt(p.pardavimo_kastai_eur)}. „Pirkti“ tik kai pelnas ≥ ${fmt(p.min_pelnas_eur)} ir ≥ ${Math.round(p.min_roi * 100)} % pirkimo kainos, be įtartinų žodžių aprašyme. ` +
    `Tikėtina kaina = ${Math.round(p.nuolaida_pardavimui * 100)} % panašių skelbimų medianos arba Claude įvertinimas, bet ne daugiau ${Math.round(p.naujo_lubos * 100)} % naujo kainos. Istorijoje ${D.skelbimu_istorijoje} skelbimų. ` +
    (D.kalibracija && D.kalibracija.pardavimu >= 5 ? `Pardavimo nuolaida kalibruota pagal ${D.kalibracija.pardavimu} tavo pardavimus.` : `Savikalibracija įsijungs po 5 pardavimų (dabar ${D.kalibracija ? D.kalibracija.pardavimu : 0}).`);
}

function renderStatus() {
  const st = $("status"); if (!st) return; st.replaceChildren();
  const t = new Date(B.paleista).toLocaleString("lt-LT", {timeZone: "Europe/Vilnius", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit"});
  st.append(el("span", "chip " + (Date.now() - new Date(B.paleista) > 3 * 3600e3 ? "bad" : "ok"), "Paieška " + t));
  const bad = B.paieskos.filter(p => p.kodas !== 200);
  st.append(el("span", "chip " + (bad.length ? "bad" : ""), B.paieskos.length + " paieškos" + (bad.length ? ", nepavyko: " + bad.map(p => p.pavadinimas).join(", ") : "")));
}

// ---------- Žurnalas ----------
const token = () => { try { return localStorage.getItem("gh_token") || ""; } catch { return ""; } };
const b64 = s => btoa(String.fromCharCode(...new TextEncoder().encode(s)));
const unb64 = s => new TextDecoder().decode(Uint8Array.from(atob(s.replace(/\n/g, "")), c => c.charCodeAt(0)));
const cost = s => (s.pirkimo_kaina || 0) + (s.pirkimo_kastai || 0);
const profit = s => s.busena === "atsargose" ? null : (s.pardavimo_kaina || 0) - (s.pardavimo_kastai || 0) - cost(s);
function msg(t) { $("msg").textContent = t; $("msg").hidden = !t; }

async function loadLedger() {
  try {
    if (token()) {
      const r = await fetch(`https://api.github.com/repos/${REPO}/contents/${ZFAILAS}?ref=main`, {headers: {Authorization: "Bearer " + token(), Accept: "application/vnd.github+json"}, cache: "no-store"});
      if (r.status === 404) { items = []; sha = null; }
      else if (r.ok) { const j = await r.json(); sha = j.sha; items = JSON.parse(unb64(j.content)).sandoriai || []; }
      else if (r.status === 401) { msg("GitHub raktas nebegalioja – įvesk naują."); try { localStorage.removeItem("gh_token"); } catch {} }
      else throw new Error("HTTP " + r.status);
    } else {
      const r = await fetch("sandoriai.json", {cache: "no-store"});
      items = r.ok ? (await r.json()).sandoriai || [] : [];
    }
  } catch (e) { msg("Nepavyko įkelti žurnalo: " + e.message); }
  renderLedger();
}
async function saveLedger(note) {
  if (!token()) { $("tokenPanel").hidden = false; $("tokenPanel").scrollIntoView({behavior: "smooth"}); throw new Error("reikia GitHub rakto"); }
  const body = {message: note, content: b64(JSON.stringify({sandoriai: items}, null, 1) + "\n"), branch: "main"};
  if (sha) body.sha = sha;
  const r = await fetch(`https://api.github.com/repos/${REPO}/contents/${ZFAILAS}`, {method: "PUT", headers: {Authorization: "Bearer " + token(), Accept: "application/vnd.github+json"}, body: JSON.stringify(body)});
  if (r.status === 409 || r.status === 422) { await loadLedger().then(() => {
  if (location.hash === "#naujas" && $("form")) {
    let r = null; try { r = JSON.parse(localStorage.getItem("pirkau")); localStorage.removeItem("pirkau"); } catch {}
    if (r) openForm(null, r);
  }
  if (location.hash === "#raktas" && $("tokenPanel")) { $("tokenPanel").hidden = false; $("tokenPanel").scrollIntoView(); }
}); throw new Error("žurnalas ką tik pasikeitė kitur – pakartok"); }
  if (!r.ok) throw new Error("HTTP " + r.status);
  sha = (await r.json()).content.sha;
}

function sellHelp() {
  const box = $("sell"); if (!box) return;
  const stock = items.filter(s => s.busena === "atsargose");
  if (!stock.length || !D) { box.replaceChildren(); return; }
  const P = D.pardavimas || {};
  box.replaceChildren(el("h2", "", "Atsargų pardavimas"), ...stock.map(s => {
    const p = P[s.id] || {}; const c = el("div", "panel");
    const d = s.pirkimo_data ? days(s.pirkimo_data, today()) : 0;
    c.append(el("div", "row", null)); c.firstChild.append(el("b", "", s.pavadinimas), el("span", "pill " + (d > 14 ? "p-atsargose" : ""), d + " d. atsargose"));
    if (!p.konkurentu) c.append(el("div", "note", "Šiuo metu aktyvių to paties modelio skelbimų nerasta – kaina pagal tikėtiną: " + fmt(s.tiketina)));
    else {
      c.append(el("div", "", `Siūloma pardavimo kaina: ${fmt(p.siuloma_kaina)} (konkurentų: ${p.konkurentu}, pigiausias ${fmt(p.pigiausias)}, mediana ${fmt(p.mediana)})`));
      const ul = el("ul", "comps"); p.konkurentai.forEach(k => { const li = el("li"); li.append(link(k.nuoroda, k.pavadinimas), el("span", "mono", " " + fmt(k.kaina))); ul.append(li); }); c.append(ul);
    }
    if (d > 14) c.append(el("div", "msg", "Guli ilgiau nei 14 d. – sumažink kainą 5–10 % arba atnaujink skelbimą su naujomis nuotraukomis."));
    return c;
  }));
}

function renderLedger() {
  remind();
  vmi();
  sellHelp();
  if (!$("kpis")) return;
  const done = items.filter(s => s.busena !== "atsargose"), stock = items.filter(s => s.busena === "atsargose");
  const realized = done.reduce((a, s) => a + profit(s), 0);
  const cash = done.reduce((a, s) => a + (s.pardavimo_kaina || 0) - (s.pardavimo_kastai || 0), 0) - items.reduce((a, s) => a + cost(s), 0);
  const hours = items.reduce((a, s) => a + (s.laikas_min || 0), 0) / 60;
  const tied = stock.reduce((a, s) => a + cost(s), 0), invested = done.reduce((a, s) => a + cost(s), 0);
  const sold = done.filter(s => s.busena === "parduota" && s.pardavimo_data && s.pirkimo_data);
  const avgDays = sold.length ? sold.reduce((a, s) => a + days(s.pirkimo_data, s.pardavimo_data), 0) / sold.length : null;
  const errs = sold.filter(s => s.tiketina && s.pardavimo_kaina).map(s => Math.abs(s.pardavimo_kaina - s.tiketina) / s.tiketina);
  // derybos: skaičiuojama tik ten, kur derėtasi – „nesiderėjau“ neiškreipia statistikos
  const ask = s => s.prasyta ?? (s.irodymas && s.irodymas.kaina);
  const tried = items.filter(s => (s.derybos === "sutiko" || s.derybos === "nesutiko") && ask(s) && s.pirkimo_kaina != null);
  const won = tried.filter(s => s.derybos === "sutiko");
  const saved = won.reduce((a, s) => a + ask(s) - s.pirkimo_kaina, 0), wonAsk = won.reduce((a, s) => a + ask(s), 0);
  const noTry = items.filter(s => s.derybos === "ne").length;
  const sTried = sold.filter(s => (s.pardavimo_derybos === "nuleidau" || s.pardavimo_derybos === "nenuleidau") && s.pardavimo_prasyta && s.pardavimo_kaina != null);
  const sGave = sTried.filter(s => s.pardavimo_derybos === "nuleidau");
  const given = sGave.reduce((a, s) => a + s.pardavimo_prasyta - s.pardavimo_kaina, 0), gaveAsk = sGave.reduce((a, s) => a + s.pardavimo_prasyta, 0);
  const K = [
    ["Grynieji iš veiklos", fmt(cash), cash >= 0 ? "pos" : "neg", "pardavimai − visos išlaidos"],
    ["Uždirbta (užbaigti)", fmt(realized), realized >= 0 ? "pos" : "neg", done.length + " užbaigti sandoriai"],
    ["Pelnas per valandą", hours ? fmt(realized / hours) : "—", "", hours.toFixed(1).replace(".", ",") + " val. iš viso"],
    ["Grąža (ROI)", invested ? Math.round(realized / invested * 100) + " %" : "—", "", "nuo užbaigtų pirkimų"],
    ["Atsargose", fmt(tied), "", stock.length + " daiktai laukia pardavimo"],
    ["Vid. pardavimo laikas", avgDays == null ? "—" : Math.round(avgDays) + " d.", "", "nuo pirkimo iki pardavimo"],
    ["Prognozės paklaida", errs.length ? Math.round(errs.reduce((a, e) => a + e, 0) / errs.length * 100) + " %" : "—", "", "tikėtina vs. tikra kaina"],
    ["Derybos perkant", tried.length ? `${won.length} iš ${tried.length}` : "—", "", tried.length ? `pavyko · sutaupyta ${fmt(saved)} (${wonAsk ? Math.round(saved / wonAsk * 100) : 0} % nuo prašytos, kai nuleido) · nesiderėta ${noTry}` : "pažymėk „Derybos“ pirkinio formoje"],
    ["Derybos parduodant", sTried.length ? `${sGave.length} iš ${sTried.length}` : "—", "", sTried.length ? `kartų nuleidai · atiduota ${fmt(given)} (${gaveAsk ? Math.round(given / gaveAsk * 100) : 0} % nuo tavo kainos)` : "pažymėk „Derybos“ pardavimo formoje"],
  ];
  $("kpis").replaceChildren(...K.map(([t, v, c, s]) => { const d = el("div", "kpi"); d.append(el("span", "eyebrow", t), el("b", c, v), el("small", "", s)); return d; }));

  const rows = [...items].map((s, i) => [s, i]).sort((a, b) => (b[0].pirkimo_data || "").localeCompare(a[0].pirkimo_data || ""));
  $("rows").replaceChildren(...(rows.length ? rows.map(([s, i]) => {
    const tr = el("tr", "click"); tr.onclick = () => openForm(i);
    const p = profit(s), h = (s.laikas_min || 0) / 60;
    const err = s.busena === "parduota" && s.tiketina && s.pardavimo_kaina ? Math.round((s.pardavimo_kaina - s.tiketina) / s.tiketina * 100) + " %" : "—";
    const st = el("td"); st.append(el("span", "pill p-" + s.busena, {atsargose: "Atsargose", parduota: "Parduota", nurasyta: "Nurašyta"}[s.busena]));
    tr.append(el("td", "t", s.pavadinimas), st, el("td", "", s.pirkimo_data || ""), el("td", "n", fmt(cost(s))),
      el("td", "n", s.busena === "parduota" ? fmt(s.pardavimo_kaina) : "—"), el("td", "n " + (p > 0 ? "pos" : p < 0 ? "neg" : ""), p == null ? "—" : fmt(p)),
      el("td", "n", p != null && h ? fmt(p / h) : "—"), el("td", "n", s.pirkimo_data ? days(s.pirkimo_data, s.pardavimo_data || today()) : "—"), el("td", "n", err));
    return tr;
  }) : [(() => { const tr = el("tr"); const td = el("td", "note", "Dar nėra pirkinių. Prie radinio spausk „Pirkau → į žurnalą“ arba „+ Naujas pirkinys“."); td.colSpan = 9; tr.append(td); return tr; })()]));

  const M = {};
  for (const s of items) {
    if (s.pirkimo_data) { const m = s.pirkimo_data.slice(0, 7); (M[m] ||= {n: 0, in: 0, out: 0, h: 0}); M[m].out += cost(s); M[m].h += (s.laikas_min || 0) / 60; }
    if (s.busena === "parduota" && s.pardavimo_data) { const m = s.pardavimo_data.slice(0, 7); (M[m] ||= {n: 0, in: 0, out: 0, h: 0}); M[m].n++; M[m].in += s.pardavimo_kaina || 0; M[m].out += s.pardavimo_kastai || 0; }
  }
  $("months").replaceChildren(...Object.keys(M).sort().reverse().map(m => { const v = M[m]; const tr = el("tr");
    tr.append(el("td", "", m), el("td", "n", v.n), el("td", "n", fmt(v.in)), el("td", "n", fmt(v.out)), el("td", "n " + (v.in - v.out >= 0 ? "pos" : "neg"), fmt(v.in - v.out)), el("td", "n", v.h.toFixed(1).replace(".", ","))); return tr; }));
}

function vmi() {
  // VMI priminimas: šių metų pardavimų suma ir skaičius
  const y = today().slice(0, 4);
  const ys = items.filter(s => s.busena === "parduota" && (s.pardavimo_data || "").startsWith(y));
  const sum = ys.reduce((a, s) => a + (s.pardavimo_kaina || 0), 0);
  const lvl = sum >= VMI_RIBA || ys.length >= PLATFORMU_RIBA ? "alert" : sum >= VMI_RIBA * 0.75 || ys.length >= PLATFORMU_RIBA * 0.75 ? "warn" : "";
  const v = el("div", "vmi " + lvl);
  v.append(el("div", "row", null));
  v.firstChild.append(el("b", "", lvl === "alert" ? "Laikas registruotis VMI" : "VMI registracijos riba"), el("span", "mono", fmt(sum) + " / " + fmt(VMI_RIBA)));
  const bar = el("div", "bar"); const i = el("i"); i.style.width = Math.min(100, sum / VMI_RIBA * 100) + "%"; bar.append(i); v.append(bar);
  v.append(el("div", "note", `${y} m. pardavimai: ${ys.length} vnt. (platformos praneša VMI nuo ${PLATFORMU_RIBA} pardavimų arba 2000 €). ` +
    (lvl === "alert" ? "Pasiekei savo ribą – registruok individualią veiklą (pažyma arba verslo liudijimas) ir pasitikrink VMI." : lvl === "warn" ? "Artėji prie ribos – pasiruošk registracijai." : "Priminsiu, kai artėsi prie ribos.")));
  if ($("vmi")) $("vmi").replaceChildren(v);
  if ($("vmiTop")) $("vmiTop").replaceChildren(...(lvl ? [v.cloneNode(true)] : []));

}

function remind() {
  const box = $("remind"); if (!box) return;
  const stock = items.filter(s => s.busena === "atsargose");
  const r = el("div", "remind");
  r.append(el("div", "", "Nupirkai? Prie skelbimo spausk „Pirkau → į žurnalą“ – užfiksuos kainą, aprašymą ir įrankio vertinimą kaip įrodymą."));
  if (!token()) { const d = el("div", "note", "Pirmą kartą prireiks GitHub rakto (~2 min.) – "); const a = el("a", "", "instrukcija žurnale"); a.href = "zurnalas.html#raktas"; d.append(a); r.append(d); }
  if (stock.length) {
    const old = Math.max(...stock.map(s => s.pirkimo_data ? days(s.pirkimo_data, today()) : 0));
    const d = el("div", "", `Atsargose ${stock.length} daiktai (seniausias ${old} d.). Pardavei? `); const a = el("a", "", "Atnaujink žurnalą"); a.href = "zurnalas.html"; d.append(a); r.append(d);
  }
  box.replaceChildren(r);
}

function showEvidence() {
  const box = $("evidence");
  if (!evidence) { box.textContent = "Skelbimo įrodymas užfiksuojamas automatiškai, kai spaudi „Pirkau“ prie radinio."; return; }
  box.replaceChildren(el("b", "", "Įrodymas (užfiksuota " + (evidence.uzfiksuota || "").slice(0, 16).replace("T", " ") + "): "),
    document.createTextNode([evidence.pavadinimas, fmt(evidence.kaina), evidence.vieta_laikas, evidence.bukle ? "būklė: " + evidence.bukle : ""].filter(Boolean).join(" · ")));
  if (evidence.aprasymas) box.append(el("div", "", "„" + evidence.aprasymas + "“"));
}
const FIELDS = ["pavadinimas", "kategorija", "nuoroda", "busena", "pirkimo_data", "prasyta", "derybos", "pirkimo_kaina", "pirkimo_kastai", "pardavimo_data", "pardavimo_prasyta", "pardavimo_derybos", "pardavimo_kaina", "pardavimo_kastai", "platforma", "laikas_min", "pastabos"];
function openForm(idx, r) {
  editIdx = idx;
  let s = idx != null ? items[idx] : {busena: "atsargose", pirkimo_data: today(), pirkimo_kastai: 0, pardavimo_kastai: 0, laikas_min: 0, platforma: "Skelbiu.lt"};
  if (r) {
    s = {...s, pavadinimas: r.pavadinimas, nuoroda: r.nuoroda, prasyta: r.kaina, pirkimo_kaina: r.kaina, pirkimo_kastai: r.kastai ? r.kastai.atgabenimas : 0,
      kategorija: r.paieska, laikas_min: r.kastai ? Math.round(r.kastai.valandos * 60) : 0};
    s.tiketina = r.tiketina_pardavimo;
    s.irodymas = {skelbimo_id: r.id, pavadinimas: r.pavadinimas, kaina: r.kaina, nuoroda: r.nuoroda, vieta_laikas: r.vieta_laikas, bukle: r.bukle || "",
      aprasymas: (r.pilnas_aprasymas || r.aprasymas || "").slice(0, 600), nuotrauka: r.nuotrauka, pastebetas: r.pastebetas,
      vertinimas: {tiketina_pardavimo: r.tiketina_pardavimo, mediana: r.mediana, palyginamu: r.palyginamu, sprendimas: r.sprendimas, kodel: r.kodel, siulymas: r.derybos && r.derybos.siulymas, riba: r.derybos && r.derybos.riba},
      uzfiksuota: new Date().toISOString()};
  }
  for (const k of FIELDS) $("f_" + k).value = s[k] ?? "";
  $("f_tiketina").value = s.tiketina ?? "";
  evidence = s.irodymas || null; showEvidence();
  $("formTitle").textContent = idx != null ? "Redaguoti sandorį" : "Naujas pirkinys";
  $("delBtn").hidden = idx == null;
  $("formPanel").hidden = false; $("formPanel").scrollIntoView({behavior: "smooth"});
  if (!token()) $("tokenPanel").hidden = false;
}
if ($("form")) {
$("addBtn").onclick = () => openForm(null);
$("closeForm").onclick = () => { $("formPanel").hidden = true; };
$("form").onsubmit = async e => {
  e.preventDefault();
  const s = {};
  for (const k of FIELDS) s[k] = $("f_" + k).value.trim ? $("f_" + k).value.trim() : $("f_" + k).value;
  for (const k of ["prasyta", "pardavimo_prasyta", "pirkimo_kaina", "pirkimo_kastai", "pardavimo_kaina", "pardavimo_kastai", "laikas_min"]) s[k] = num(s[k]);
  s.tiketina = num($("f_tiketina").value); s.pardavimo_data = s.pardavimo_data || null; s.irodymas = evidence;
  if (s.busena === "parduota" && (s.pardavimo_kaina == null || !s.pardavimo_data)) { msg("Parduotam daiktui įrašyk pardavimo datą ir kainą."); return; }
  const before = JSON.stringify(items);
  if (editIdx != null) items[editIdx] = {...items[editIdx], ...s, atnaujinta: new Date().toISOString()};
  else items.push({...s, id: Date.now().toString(36), sukurta: new Date().toISOString()});
  $("saveBtn").disabled = true;
  try { await saveLedger((editIdx != null ? "Žurnalas: atnaujinta " : "Žurnalas: pirkta ") + s.pavadinimas.slice(0, 40)); $("formPanel").hidden = true; msg(""); }
  catch (err) { items = JSON.parse(before); msg("Neišsaugota: " + err.message); }
  $("saveBtn").disabled = false; renderLedger();
};
$("delBtn").onclick = async () => {
  if ($("delBtn").dataset.sure !== "1") { $("delBtn").dataset.sure = "1"; $("delBtn").textContent = "Tikrai ištrinti?"; return; }
  $("delBtn").dataset.sure = ""; $("delBtn").textContent = "Ištrinti";
  const before = JSON.stringify(items); const name = items[editIdx].pavadinimas;
  items.splice(editIdx, 1);
  try { await saveLedger("Žurnalas: ištrinta " + name.slice(0, 40)); $("formPanel").hidden = true; } catch (err) { items = JSON.parse(before); msg("Neištrinta: " + err.message); }
  renderLedger();
};
$("tokenForm").onsubmit = async e => {
  e.preventDefault();
  try { localStorage.setItem("gh_token", $("tokenInput").value.trim()); } catch { msg("Naršyklė neleidžia išsaugoti rakto."); return; }
  $("tokenInput").value = ""; $("tokenPanel").hidden = true; await loadLedger().then(() => {
  if (location.hash === "#naujas" && $("form")) {
    let r = null; try { r = JSON.parse(localStorage.getItem("pirkau")); localStorage.removeItem("pirkau"); } catch {}
    if (r) openForm(null, r);
  }
  if (location.hash === "#raktas" && $("tokenPanel")) { $("tokenPanel").hidden = false; $("tokenPanel").scrollIntoView(); }
});
};
const csvCell = v => { const s = v == null ? "" : String(v); return /[";\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
$("csvBtn").onclick = () => {
  const head = ["Daiktas", "Kategorija", "Būsena", "Pirkimo data", "Prašė skelbime", "Derybos", "Pirkimo kaina", "Atgabenimo kaštai", "Pardavimo data", "Mano prašyta", "Pardavimo derybos", "Pardavimo kaina", "Pardavimo kaštai", "Platforma", "Pelnas", "Sugaišta min", "Skelbimo nuoroda", "Užfiksuota skelbimo kaina", "Įrodymas užfiksuotas", "Skelbimo aprašymas", "Pastabos"];
  const lines = [head.join(";")].concat(items.map(s => [s.pavadinimas, s.kategorija, s.busena, s.pirkimo_data, s.prasyta, s.derybos, s.pirkimo_kaina, s.pirkimo_kastai, s.pardavimo_data, s.pardavimo_prasyta, s.pardavimo_derybos, s.pardavimo_kaina, s.pardavimo_kastai, s.platforma,
    profit(s), s.laikas_min, s.nuoroda, s.irodymas && s.irodymas.kaina, s.irodymas && s.irodymas.uzfiksuota, s.irodymas && s.irodymas.aprasymas, s.pastabos].map(csvCell).join(";")));
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob(["﻿" + lines.join("\n")], {type: "text/csv;charset=utf-8"}));
  a.download = "perpardavimas-" + today() + ".csv"; a.click();
};

}

Promise.all([fetch("analize.json", {cache: "no-store"}).then(r => r.json()), fetch("busena.json", {cache: "no-store"}).then(r => r.json())])
  .then(([d, b]) => { D = d; B = b; renderStatus(); render(); sellHelp(); })
  .catch(() => { $("status").replaceChildren(el("span", "chip bad", "Nepavyko įkelti radinių. Pabandyk po kelių minučių.")); });
loadLedger().then(() => {
  if (location.hash === "#naujas" && $("form")) {
    let r = null; try { r = JSON.parse(localStorage.getItem("pirkau")); localStorage.removeItem("pirkau"); } catch {}
    if (r) openForm(null, r);
  }
  if (location.hash === "#raktas" && $("tokenPanel")) { $("tokenPanel").hidden = false; $("tokenPanel").scrollIntoView(); }
});
