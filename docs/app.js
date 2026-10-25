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

// ---------- Kainų skalė ----------
const SVG = "http://www.w3.org/2000/svg";
const sv = (tag, attrs, parent) => { const e = document.createElementNS(SVG, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.append(e); return e; };
function scale(r) {
  const others = (r.visi_palyginami || []).map(p => p.kaina);
  const marks = [r.kaina, r.tiketina_pardavimo, r.max_pirkimo || null, r.naujo_min].filter(v => v != null && v > 0);
  const all = others.concat(marks);
  if (!r.kaina || others.length < 2) return null;
  const lo = Math.min(...all), hi = Math.max(...all), W = 320, L = 12, R = 308, Y = 34;
  const x = v => hi === lo ? (L + R) / 2 : L + (v - lo) / (hi - lo) * (R - L);
  const svg = sv("svg", {viewBox: "0 0 320 64", class: "scale", role: "img", "aria-label": "Kainų palyginimas"});
  sv("line", {x1: L, x2: R, y1: Y, y2: Y, class: "axis"}, svg);
  if (r.mediana) { sv("line", {x1: x(r.mediana), x2: x(r.mediana), y1: Y - 14, y2: Y + 14, class: "med"}, svg); }
  if (r.max_pirkimo) { sv("line", {x1: x(r.max_pirkimo), x2: x(r.max_pirkimo), y1: Y - 10, y2: Y + 10, class: "maxb"}, svg); }
  // kiti skelbimai – kiekvienas taškas yra nuoroda; vienodos kainos išdėstomos vertikaliai
  const seen = {};
  (r.visi_palyginami || []).forEach(p => {
    const k = Math.round(x(p.kaina)); const n = seen[k] = (seen[k] || 0) + 1;
    const a = sv("a", {href: p.nuoroda, target: "_blank", rel: "noopener"}, svg);
    sv("title", {}, a).textContent = p.pavadinimas + " – " + fmt(p.kaina);
    sv("circle", {cx: x(p.kaina), cy: Y + (n % 2 ? -1 : 1) * Math.floor(n / 2) * 7, r: 4.5, class: "other"}, a);
  });
  if (r.tiketina_pardavimo) sv("path", {d: `M${x(r.tiketina_pardavimo)} ${Y - 18} l-5 -8 h10z`, class: "sell"}, svg);
  if (r.naujo_min) sv("rect", {x: x(r.naujo_min) - 5, y: Y + 13, width: 10, height: 10, transform: `rotate(45 ${x(r.naujo_min)} ${Y + 18})`, class: "new"}, svg);
  sv("circle", {cx: x(r.kaina), cy: Y, r: 7, class: "me"}, svg);
  sv("text", {x: L, y: 62}, svg).textContent = fmt(lo);
  sv("text", {x: R, y: 62, "text-anchor": "end"}, svg).textContent = fmt(hi);
  const box = el("div");
  const lg = el("div", "legend");
  const item = (color, t, shape, w) => { const s = el("span"); const i = el("i"); i.style.background = `var(${color})`; if (shape) i.style.borderRadius = shape; if (w) i.style.width = w; s.append(i, document.createTextNode(t)); lg.append(s); };
  item("--accent", "šis " + fmt(r.kaina));
  item("--skip", "kiti skelbimai (" + others.length + ", spausk tašką)");
  if (r.mediana) item("--fg", "mediana " + fmt(r.mediana), "1px", "3px");
  if (r.tiketina_pardavimo) item("--ok", "▼ parduosi ~" + fmt(r.tiketina_pardavimo), "0", "0");
  if (r.max_pirkimo) item("--ok", "mokėk ≤ " + fmt(r.max_pirkimo), "1px", "3px");
  if (r.naujo_min) item("--warn", "naujas nuo " + fmt(r.naujo_min), "2px");
  box.append(svg, lg);
  return box;
}

// ---------- Radinio kortelė ----------
function card(r, big) {
  const c = el("article", "card" + (big ? " big" : ""));
  const img = el("img"); img.loading = "lazy"; img.alt = ""; img.referrerPolicy = "no-referrer";
  img.onerror = () => img.style.visibility = "hidden"; if (r.nuotrauka) img.src = r.nuotrauka;
  const body = el("div", "body");
  const top = el("div", "top");
  top.append(link(r.nuoroda, r.pavadinimas || "(be pavadinimo)"), el("span", "verdict v-" + r.sprendimas, LABEL[r.sprendimas] || r.sprendimas));
  const nums = el("div", "nums");
  const n = (t, v, cls) => { const s = el("span", "", t); s.append(el("b", cls || "", v)); nums.append(s); };
  n("Prašo", fmt(r.kaina)); n("Parduosi už ~", fmt(r.tiketina_pardavimo));
  n("Pelnas", fmt(r.pelnas), r.pelnas > 0 ? "pos" : r.pelnas < 0 ? "neg" : "");
  n("Mokėk ne daugiau", r.max_pirkimo ? fmt(r.max_pirkimo) : "—");
  body.append(top, nums);
  if (r.kodel) body.append(el("div", "kodel", r.kodel));
  const sc = scale(r); if (sc) body.append(sc);
  const ap = r.aprasymas_analize || {};
  if ((ap.rizikos_zodziai || []).length || (ap.privalumai || []).length || r.bukle) {
    const f = el("div", "flags");
    if (r.bukle) f.append(el("span", "flag", "Būklė: " + r.bukle));
    (ap.rizikos_zodziai || []).forEach(z => f.append(el("span", "flag risk", "⚠ " + z)));
    (ap.privalumai || []).forEach(z => f.append(el("span", "flag plus", "✓ " + z)));
    body.append(f);
  }
  body.append(el("div", "meta", [r.modelis, "patikimumas: " + r.patikimumas, r.kastai && r.kastai.budas,
    r.pelnas_per_val != null ? "~" + fmt(r.pelnas_per_val) + "/val." : "", r.vieta_laikas].filter(Boolean).join(" · ")));
  if (r.stovas) body.append(el("div", "why", "Stovo tipo proga: naujas ES su siuntimu pigesnis nei LT skelbimuose."));
  if (r.rizikos) body.append(el("div", "meta", "Claude: " + r.rizikos));

  const apr = r.pilnas_aprasymas || r.aprasymas;
  if (apr) { const d = el("details"); d.append(el("summary", "", r.pilnas_aprasymas ? "Pilnas aprašymas" : "Aprašymo pradžia"), el("p", "meta", apr)); body.append(d); }

  const how = el("details"); how.append(el("summary", "", "Kaip apskaičiuota"));
  const ol = el("ol", "steps"); (r.zingsniai || []).forEach(z => ol.append(el("li", "", z))); how.append(ol);
  if (r.palyginami && r.palyginami.length) {
    how.append(el("div", "sub", "Panašūs skelbimai (" + r.palyginamu + "):"));
    const ul = el("ul", "comps");
    r.palyginami.forEach(p => { const li = el("li"); li.append(link(p.nuoroda, p.pavadinimas), el("span", "mono", " " + fmt(p.kaina))); ul.append(li); });
    how.append(ul);
  }
  body.append(how);

  const shop = el("details"); shop.append(el("summary", "", r.parduotuves && r.parduotuves.length ? "Naujo kainos parduotuvėse (" + r.parduotuves.length + ")" : "Naujo kaina parduotuvėse"));
  if (r.parduotuves && r.parduotuves.length) {
    const ul = el("ul", "comps");
    r.parduotuves.forEach(p => { const li = el("li"); li.append(link(p.url, p.parduotuve || p.url), el("span", "mono", " " + fmt(p.kaina) + (p.su_siuntimu ? " su siuntimu" : ""))); ul.append(li); });
    shop.append(ul);
  } else shop.append(el("div", "sub", "Claude dar nepatikrino (tikrina kas rytą). Greita paieška:"));
  const q = el("div", "shops"); (r.parduotuviu_paieska || []).forEach(p => q.append(link(p.url, p.pavadinimas, "chip"))); shop.append(q);
  body.append(shop);

  if (r.skelbimo_tekstas) {
    const d = el("details"); d.append(el("summary", "", "Paruoštas skelbimo tekstas"));
    const pre = el("pre", "", r.skelbimo_tekstas); const btn = el("button", "copy", "Kopijuoti"); btn.type = "button";
    btn.onclick = () => navigator.clipboard.writeText(r.skelbimo_tekstas).then(() => btn.textContent = "Nukopijuota", () => getSelection().selectAllChildren(pre));
    d.append(pre, btn); body.append(d);
  }
  const buy = el("button", "copy", "Pirkau → į žurnalą"); buy.type = "button";
  buy.onclick = () => openForm(null, r);
  body.append(buy);
  c.append(img, body); return c;
}

function render() {
  const R = D.radiniai;
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
  const rows = R.filter(r => filter === "visi" || r.sprendimas === filter);
  $("cards").replaceChildren(...(rows.length ? rows.map(r => card(r)) : [el("p", "note", "Šioje grupėje šiuo metu nieko nėra.")]));
  const m = Object.entries(D.rinka).sort((x, y) => y[1].n - x[1].n);
  $("market").replaceChildren(...m.map(([k, v]) => { const tr = el("tr"); tr.append(el("td", "", k), el("td", "n", v.n), el("td", "n", fmt(v.mediana)), el("td", "n", fmt(v.min) + "–" + fmt(v.max))); return tr; }));
  const p = D.prielaidos;
  $("assumptions").textContent =
    `Prielaidos: vietiniai miestai ${p.vietiniai_miestai.join(", ")} (atsiėmimas ${fmt(p.atsiemimas_vietoje_eur)}, ~${p.laikas_vietoje_val} val.), kiti – siunta į paštomatą ${fmt(p.siunta_i_mane_eur)} (~${p.laikas_siunta_val} val.), dideli daiktai iš kitų miestų praleidžiami. ` +
    `Pakuotė / pardavimas ${fmt(p.pardavimo_kastai_eur)}. „Pirkti“ tik kai pelnas ≥ ${fmt(p.min_pelnas_eur)} ir ≥ ${Math.round(p.min_roi * 100)} % pirkimo kainos, be įtartinų žodžių aprašyme. ` +
    `Tikėtina kaina = ${Math.round(p.nuolaida_pardavimui * 100)} % panašių skelbimų medianos arba Claude įvertinimas, bet ne daugiau ${Math.round(p.naujo_lubos * 100)} % naujo kainos. Istorijoje ${D.skelbimu_istorijoje} skelbimų.`;
}

function renderStatus() {
  const st = $("status"); st.replaceChildren();
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
  if (r.status === 409 || r.status === 422) { await loadLedger(); throw new Error("žurnalas ką tik pasikeitė kitur – pakartok"); }
  if (!r.ok) throw new Error("HTTP " + r.status);
  sha = (await r.json()).content.sha;
}

function renderLedger() {
  const done = items.filter(s => s.busena !== "atsargose"), stock = items.filter(s => s.busena === "atsargose");
  const realized = done.reduce((a, s) => a + profit(s), 0);
  const cash = done.reduce((a, s) => a + (s.pardavimo_kaina || 0) - (s.pardavimo_kastai || 0), 0) - items.reduce((a, s) => a + cost(s), 0);
  const hours = items.reduce((a, s) => a + (s.laikas_min || 0), 0) / 60;
  const tied = stock.reduce((a, s) => a + cost(s), 0), invested = done.reduce((a, s) => a + cost(s), 0);
  const sold = done.filter(s => s.busena === "parduota" && s.pardavimo_data && s.pirkimo_data);
  const avgDays = sold.length ? sold.reduce((a, s) => a + days(s.pirkimo_data, s.pardavimo_data), 0) / sold.length : null;
  const errs = sold.filter(s => s.tiketina && s.pardavimo_kaina).map(s => Math.abs(s.pardavimo_kaina - s.tiketina) / s.tiketina);
  const K = [
    ["Grynieji iš veiklos", fmt(cash), cash >= 0 ? "pos" : "neg", "pardavimai − visos išlaidos"],
    ["Uždirbta (užbaigti)", fmt(realized), realized >= 0 ? "pos" : "neg", done.length + " užbaigti sandoriai"],
    ["Pelnas per valandą", hours ? fmt(realized / hours) : "—", "", hours.toFixed(1).replace(".", ",") + " val. iš viso"],
    ["Grąža (ROI)", invested ? Math.round(realized / invested * 100) + " %" : "—", "", "nuo užbaigtų pirkimų"],
    ["Atsargose", fmt(tied), "", stock.length + " daiktai laukia pardavimo"],
    ["Vid. pardavimo laikas", avgDays == null ? "—" : Math.round(avgDays) + " d.", "", "nuo pirkimo iki pardavimo"],
    ["Prognozės paklaida", errs.length ? Math.round(errs.reduce((a, e) => a + e, 0) / errs.length * 100) + " %" : "—", "", "tikėtina vs. tikra kaina"],
  ];
  $("kpis").replaceChildren(...K.map(([t, v, c, s]) => { const d = el("div", "kpi"); d.append(el("span", "eyebrow", t), el("b", c, v), el("small", "", s)); return d; }));

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
  $("vmi").replaceChildren(v);
  $("vmiTop").replaceChildren(...(lvl ? [v.cloneNode(true)] : []));

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

function showEvidence() {
  const box = $("evidence");
  if (!evidence) { box.textContent = "Skelbimo įrodymas užfiksuojamas automatiškai, kai spaudi „Pirkau“ prie radinio."; return; }
  box.replaceChildren(el("b", "", "Įrodymas (užfiksuota " + (evidence.uzfiksuota || "").slice(0, 16).replace("T", " ") + "): "),
    document.createTextNode([evidence.pavadinimas, fmt(evidence.kaina), evidence.vieta_laikas, evidence.bukle ? "būklė: " + evidence.bukle : ""].filter(Boolean).join(" · ")));
  if (evidence.aprasymas) box.append(el("div", "", "„" + evidence.aprasymas + "“"));
}
const FIELDS = ["pavadinimas", "kategorija", "nuoroda", "busena", "pirkimo_data", "pirkimo_kaina", "pirkimo_kastai", "pardavimo_data", "pardavimo_kaina", "pardavimo_kastai", "platforma", "laikas_min", "pastabos"];
function openForm(idx, r) {
  editIdx = idx;
  let s = idx != null ? items[idx] : {busena: "atsargose", pirkimo_data: today(), pirkimo_kastai: 0, pardavimo_kastai: 0, laikas_min: 0, platforma: "Skelbiu.lt"};
  if (r) {
    s = {...s, pavadinimas: r.pavadinimas, nuoroda: r.nuoroda, pirkimo_kaina: r.kaina, pirkimo_kastai: r.kastai ? r.kastai.atgabenimas : 0,
      kategorija: r.paieska, laikas_min: r.kastai ? Math.round(r.kastai.valandos * 60) : 0};
    s.tiketina = r.tiketina_pardavimo;
    s.irodymas = {skelbimo_id: r.id, pavadinimas: r.pavadinimas, kaina: r.kaina, nuoroda: r.nuoroda, vieta_laikas: r.vieta_laikas, bukle: r.bukle || "",
      aprasymas: (r.pilnas_aprasymas || r.aprasymas || "").slice(0, 600), nuotrauka: r.nuotrauka, pastebetas: r.pastebetas,
      vertinimas: {tiketina_pardavimo: r.tiketina_pardavimo, mediana: r.mediana, palyginamu: r.palyginamu, sprendimas: r.sprendimas, kodel: r.kodel},
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
$("addBtn").onclick = () => openForm(null);
$("closeForm").onclick = () => { $("formPanel").hidden = true; };
$("form").onsubmit = async e => {
  e.preventDefault();
  const s = {};
  for (const k of FIELDS) s[k] = $("f_" + k).value.trim ? $("f_" + k).value.trim() : $("f_" + k).value;
  for (const k of ["pirkimo_kaina", "pirkimo_kastai", "pardavimo_kaina", "pardavimo_kastai", "laikas_min"]) s[k] = num(s[k]);
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
  $("tokenInput").value = ""; $("tokenPanel").hidden = true; await loadLedger();
};
const csvCell = v => { const s = v == null ? "" : String(v); return /[";\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
$("csvBtn").onclick = () => {
  const head = ["Daiktas", "Kategorija", "Būsena", "Pirkimo data", "Pirkimo kaina", "Atgabenimo kaštai", "Pardavimo data", "Pardavimo kaina", "Pardavimo kaštai", "Platforma", "Pelnas", "Sugaišta min", "Skelbimo nuoroda", "Užfiksuota skelbimo kaina", "Įrodymas užfiksuotas", "Skelbimo aprašymas", "Pastabos"];
  const lines = [head.join(";")].concat(items.map(s => [s.pavadinimas, s.kategorija, s.busena, s.pirkimo_data, s.pirkimo_kaina, s.pirkimo_kastai, s.pardavimo_data, s.pardavimo_kaina, s.pardavimo_kastai, s.platforma,
    profit(s), s.laikas_min, s.nuoroda, s.irodymas && s.irodymas.kaina, s.irodymas && s.irodymas.uzfiksuota, s.irodymas && s.irodymas.aprasymas, s.pastabos].map(csvCell).join(";")));
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob(["﻿" + lines.join("\n")], {type: "text/csv;charset=utf-8"}));
  a.download = "perpardavimas-" + today() + ".csv"; a.click();
};

Promise.all([fetch("analize.json", {cache: "no-store"}).then(r => r.json()), fetch("busena.json", {cache: "no-store"}).then(r => r.json())])
  .then(([d, b]) => { D = d; B = b; renderStatus(); render(); })
  .catch(() => { $("status").replaceChildren(el("span", "chip bad", "Nepavyko įkelti radinių. Pabandyk po kelių minučių.")); });
loadLedger();
