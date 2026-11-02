/* منصة فريق أبو نواف — واجهة التشغيل */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, m => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));
const api = async (u, o) => { const r = await fetch(u, o); if (!r.ok) throw new Error((await r.text()).slice(0, 200)); return r.json(); };
const num = n => (n ?? 0).toLocaleString("en-US");
const dt = s => (s || "").replace("T", " ").replace(/\+00:00|Z$/, "").slice(0, 16);
function toast(msg) { const t = $("#toast"); t.textContent = msg; t.classList.add("show"); clearTimeout(t._t); t._t = setTimeout(() => t.classList.remove("show"), 3200); }
function copyEl(id) { navigator.clipboard.writeText($("#" + id).textContent).then(() => toast("تم النسخ ✓")); }

const VIEWS = {
  dash: ["لوحة القيادة", "نظرة شاملة على الموقع والعملاء المحتملين وكلمات البحث — بيانات حقيقية"],
  leads: ["صيد العملاء المحتملين", "منشورات وصفحات عامة يطلب أصحابها خدمة — مع رابط مباشر لكل حالة"],
  keywords: ["ذكاء كلمات البحث", "كلمات مستخرجة من اقتراحات Google و Bing الحقيقية + تحليل النية والفرصة"],
  seo: ["مدقق SEO الحي", "زحف فعلي لـ ant.xo.je مع حل تحدي الاستضافة وقراءة كل الصفحات"],
  competitors: ["المنافسون", "من يتصدر نفس الكلمات، وما ثغرته القابلة للاستغلال"],
  tools: ["الأدوات", "سجل أدوات الفريق وفحص حالتها الحية + الأدوات المفعّلة في هذه المنصة"],
  social: ["القنوات الرسمية", "فحص حي لكل حسابات سوشيال ميديا وملف GitHub"],
  report: ["التقرير الشامل", "تقرير تدقيق كامل مبني على بيانات الزحف والبحث الفعلية"]
};

$$("#nav button").forEach(b => b.onclick = () => {
  $$("#nav button").forEach(x => x.classList.remove("active"));
  b.classList.add("active");
  const v = b.dataset.view;
  $$(".view").forEach(s => s.classList.remove("active"));
  $("#v-" + v).classList.add("active");
  $("#viewTitle").textContent = VIEWS[v][0];
  $("#viewSub").textContent = VIEWS[v][1];
  window.scrollTo({ top: 0, behavior: "smooth" });
  loadView(v);
});

const loaded = {};
function loadView(v) { if (loaded[v]) return; loaded[v] = 1; ({ dash: loadDash, leads: loadLeads, keywords: loadKw, seo: () => loadAudit(false), competitors: loadComp, tools: () => loadTools(false), social: loadSocial, report: () => loadReport(false) }[v])(); }

function gauge(label, val) {
  const r = 34, c = 2 * Math.PI * r, off = c * (1 - (val || 0) / 100);
  const col = val >= 80 ? "#10b981" : val >= 60 ? "#22d3ee" : val >= 40 ? "#f59e0b" : "#f43f5e";
  return `<div class="gauge"><svg viewBox="0 0 80 80">
    <circle cx="40" cy="40" r="${r}" fill="none" stroke="#16233c" stroke-width="8"/>
    <circle cx="40" cy="40" r="${r}" fill="none" stroke="${col}" stroke-width="8" stroke-linecap="round"
      stroke-dasharray="${c}" stroke-dashoffset="${off}" style="transition:stroke-dashoffset .8s"/>
  </svg><div class="g-val">${val ?? "—"}</div><div class="g-lab">${label}</div></div>`;
}

/* ─────────── DASHBOARD ─────────── */
async function loadDash() {
  try {
    const o = await api("/api/overview");
    $("#kLeads").textContent = num(o.leads.total);
    $("#kLeadsFoot").textContent = `${o.leads.hot} ساخن · ${num(o.leads.raw)} نتيجة خام · ${dt(o.leads.generated_at)}`;
    $("#kKw").textContent = num(o.keywords.total);
    $("#kKwFoot").textContent = `${num(o.keywords.queries_used)} استعلام اقتراح حقيقي`;
    $("#kScore").textContent = o.site.scores?.overall ?? "—";
    $("#kScoreFoot").textContent = `${o.site.pages} صفحات · تحليل حي`;
    $("#kTools").textContent = `${o.tools.total}`;
    $("#kToolsFoot").textContent = `${o.accounts.total} قناة سوشيال`;
    $("#navLeads").textContent = num(o.leads.total);
    $("#navKw").textContent = num(o.keywords.total);
    $("#navTools").textContent = o.tools.total;
    const intents = o.keywords.intents || {};
    const max = Math.max(...Object.values(intents), 1);
    $("#intentBars").innerHTML = Object.entries(intents).sort((a, b) => b[1] - a[1]).map(([k, v]) => `
      <div style="margin-bottom:10px">
        <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:3px">
          <span>${esc(k)}</span><span class="num">${num(v)}</span></div>
        <div class="bar"><i style="width:${(v / max * 100).toFixed(1)}%"></i></div>
      </div>`).join("");
  } catch (e) { toast("تعذر تحميل اللوحة: " + e.message); }

  try {
    const a = await api("/api/seo/audit");
    $("#auditAt").textContent = dt(a.crawled_at);
    $("#gauges").innerHTML = ["seo:SEO", "performance:الأداء", "security:الأمان", "content:المحتوى"]
      .map(x => { const [k, l] = x.split(":"); return gauge(l, a.scores[k]); }).join("");
    const bad = (a.issues || []).filter(i => ["critical", "high", "medium"].includes(i.severity)).slice(0, 5);
    $("#topIssues").innerHTML = bad.map(i => `<div class="issue">
      <div class="sev ${i.severity}"></div><div><h4>${esc(i.title)}</h4>
      <p>${esc(i.detail)}</p><div class="fix">✔ ${esc(i.fix)}</div></div></div>`).join("") || "<div class='empty'>لا مشكلات حرجة</div>";
  } catch (e) { $("#gauges").innerHTML = `<div class="empty">${esc(e.message)}</div>`; }

  try {
    const l = await api("/api/leads?limit=6");
    $("#topLeads").innerHTML = l.leads.map(x => `<div style="display:flex;gap:10px;align-items:center;padding:8px 0;border-bottom:1px solid rgba(27,39,64,.6)">
      <span class="score-pill ${x.score >= 75 ? "s-hot" : x.score >= 55 ? "s-warm" : "s-watch"}">${x.score}</span>
      <div style="flex:1;overflow:hidden"><span class="lead-title">${esc(x.title)}</span>
      <span class="lead-snip">${esc(x.platform)} · ${esc(x.service)}</span></div>
      <a class="btn sm" href="${esc(x.url)}" target="_blank" rel="noopener">فتح</a></div>`).join("");
  } catch (e) { }
  $("#healthTxt").textContent = "الخادم يعمل";
}

/* ─────────── LEADS ─────────── */
let LEADS = { leads: [], facets: {} };
async function loadLeads() {
  const p = new URLSearchParams();
  if ($("#leadTier").value) p.set("tier", $("#leadTier").value);
  if ($("#leadPlatform").value) p.set("platform", $("#leadPlatform").value);
  if ($("#leadService").value) p.set("service", $("#leadService").value);
  if ($("#leadQ").value) p.set("q", $("#leadQ").value);
  p.set("include_raw", $("#leadRaw").checked);
  try {
    const d = await api("/api/leads?" + p);
    LEADS = d;
    $("#leadCount").textContent = `${d.count} نتيجة`;
    $("#leadMeta").textContent = `آخر صيد: ${dt(d.meta.generated_at)}`;
    const f = d.facets;
    if (!$("#leadPlatform").dataset.filled) {
      $("#leadPlatform").innerHTML = `<option value="">كل المنصات</option>` + f.platforms.map(x => `<option>${esc(x)}</option>`).join("");
      $("#leadService").innerHTML = `<option value="">كل الخدمات</option>` + f.services.map(x => `<option>${esc(x)}</option>`).join("");
      $("#leadPlatform").dataset.filled = 1;
    }
    $("#leadRows").innerHTML = d.leads.length ? d.leads.map(x => `
      <tr>
        <td><span class="chip ${x.tier === "ساخن" ? "bad" : x.tier === "دافئ" ? "warn" : "cy"}">${esc(x.tier)}</span></td>
        <td><span class="score-pill ${x.score >= 75 ? "s-hot" : x.score >= 55 ? "s-warm" : "s-watch"}">${x.score}</span></td>
        <td style="max-width:480px"><span class="lead-title">${esc(x.title || "—")}</span>
          <span class="lead-snip">${esc(x.snippet || "")}</span></td>
        <td><span class="chip">${esc(x.platform)}</span>${x.kind ? `<br><span class="chip ${x.kind === "منافس" ? "warn" : x.kind === "استغاثة منشورة" ? "ok" : "cy"}" style="margin-top:3px">${esc(x.kind)}</span>` : ""}</td>
        <td style="font-size:12px">${esc(x.service)}</td>
        <td>${(x.signals || []).slice(0, 3).map(s => `<span class="sig">${esc(s)}</span>`).join("") || "<span class='sig'>—</span>"}</td>
        <td><a class="btn sm" href="${esc(x.url)}" target="_blank" rel="noopener">فتح ↗</a></td>
      </tr>`).join("") : `<tr><td colspan="7"><div class="empty">لا نتائج بهذه الفلاتر</div></td></tr>`;
    $("#leadSources").innerHTML = (d.sources || []).map(s => `<tr>
      <td>${esc(s.query)}</td><td class="mono" style="max-width:320px;overflow:hidden;text-overflow:ellipsis">${esc(s.q)}</td>
      <td><span class="chip ${s.status === "ok" ? "ok" : "bad"}">${esc(s.status)}</span></td>
      <td class="num">${s.found}</td></tr>`).join("") || "<tr><td colspan=4 class='empty'>—</td></tr>";
  } catch (e) { $("#leadRows").innerHTML = `<tr><td colspan="7"><div class="empty">${esc(e.message)}</div></td></tr>`; }
}
["leadTier", "leadPlatform", "leadService", "leadRaw"].forEach(id => $("#" + id).onchange = loadLeads);
$("#leadQ").oninput = (() => { let t; return () => { clearTimeout(t); t = setTimeout(loadLeads, 350); }; })();

async function runHarvest() {
  if (window.STATIC_MODE) {
    toast("التحديث الحي يعمل عبر GitHub Actions — سأفتح لك صفحة التشغيل");
    setTimeout(() => window.open(window.ACTIONS_URL || "https://github.com/abunoafceh8-commits/abunawaf-os/actions", "_blank"), 700);
    return;
  }
  const b = $("#harvestBtn"); b.disabled = true; b.innerHTML = `<span class="spin"></span> يعمل…`;
  try {
    await api("/api/leads/refresh", { method: "POST" });
    const poll = setInterval(async () => {
      const s = await api("/api/leads/status");
      $("#harvestStatus").textContent = s.job.running ? "جارٍ قراءة المصادر الحقيقية…" : "";
      if (!s.job.running) {
        clearInterval(poll); b.disabled = false; b.textContent = "⚡ صيد جديد";
        toast(s.job.error ? "خطأ: " + s.job.error : "تم الصيد ✓");
        loadLeads();
      }
    }, 4000);
  } catch (e) { b.disabled = false; b.textContent = "⚡ صيد جديد"; toast("فشل: " + e.message); }
}
async function readUrl() {
  if (window.STATIC_MODE) { toast("قراءة الروابط (trafilatura) تحتاج الخادم — متاحة في نسخة FastAPI"); return; }
  const u = $("#readUrl").value.trim();
  if (!u) return;
  const out = $("#readOut");
  out.style.display = "block";
  out.innerHTML = `<span class="spin"></span> يقرأ الصفحة ويستخرج النص…`;
  try {
    const d = await api("/api/read-url?url=" + encodeURIComponent(u));
    out.innerHTML = `<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:6px">
        <span class="score-pill ${d.score >= 75 ? "s-hot" : d.score >= 55 ? "s-warm" : "s-watch"}">${d.score}</span>
        <span class="chip cy">${esc(d.suggested_service)}</span>
        <span class="chip">${esc(d.method)}</span>
        <span class="chip">${num(d.chars)} حرف</span>
        <button class="btn sm" onclick="prefillLead('${esc(u).replace(/'/g, "\\'")}', ${d.score}, '${esc(d.suggested_service)}')">+ أضفه للقائمة</button>
      </div>
      <div style="font-size:12.5px;color:var(--muted);max-height:130px;overflow:auto">${esc(d.excerpt)}</div>
      <div style="margin-top:6px">${(d.signals || []).map(s => `<span class="sig">${esc(s)}</span>`).join(" ")}</div>`;
  } catch (e) { out.innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
}
function prefillLead(url, score, service) {
  $("#mUrl").value = url; $("#mScore").value = score;
  if ([...$("#mService").options].some(o => o.value === service)) $("#mService").value = service;
  $("#mName").value = "من رابط مفحوص"; openLeadModal();
}

function openLeadModal() { $("#leadModal").classList.add("open"); }
async function saveLead() {
  const body = { name: $("#mName").value, url: $("#mUrl").value, platform: $("#mPlatform").value, service: $("#mService").value, score: $("#mScore").value, note: $("#mNote").value };
  try { await api("/api/leads/add", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }); $("#leadModal").classList.remove("open"); toast("تمت الإضافة ✓"); loadLeads(); }
  catch (e) { toast("خطأ: " + e.message); }
}

/* ─────────── KEYWORDS ─────────── */
async function loadKw() {
  try {
    const d = await api("/api/keywords?limit=500");
    $("#kwTotal").textContent = num(d.total);
    $("#kwQueries").textContent = num(d.meta.queries_used);
    const buyers = (d.keywords || []).filter(k => k.buyer_intent >= 80).length;
    $("#kwBuyers").textContent = num(buyers);
    const trend = [...d.keywords].sort((a, b) => b.popularity - a.popularity)[0];
    $("#kwTrend").textContent = trend ? trend.popularity : "—";
    if (!$("#kwIntent").dataset.filled) {
      $("#kwIntent").innerHTML = `<option value="">كل النوايا</option>` + Object.keys(d.intents).map(x => `<option>${esc(x)}</option>`).join("");
      $("#kwIntent").dataset.filled = 1;
    }
    renderKw(d);
    const c = await api("/api/keywords/clusters?k=6");
    $("#clusters").innerHTML = (c.clusters || []).map(cl => `
      <div style="margin-bottom:12px;padding:10px;border-radius:11px;background:var(--panel2);border:1px solid var(--line)">
        <div style="display:flex;justify-content:space-between;font-size:12.5px;font-weight:700">
          <span>${esc(cl.label)}</span><span class="chip cy">${cl.size} كلمة</span></div>
        <div style="font-size:11px;color:var(--dim);margin:3px 0 6px">فرصة ${cl.avg_opportunity} · صعوبة ${cl.avg_difficulty}</div>
        <div>${(cl.top || []).slice(0, 6).map(k => `<a class="sig" href="#" onclick="event.preventDefault();document.getElementById('kwQ').value='${esc(k.keyword)}';loadKwRows();">${esc(k.keyword)}</a>`).join(" ")}</div>
      </div>`).join("");
  } catch (e) { toast("خطأ كلمات: " + e.message); }
}
function renderKw(d) {
  const rows = d.keywords || [];
  $("#kwCount").textContent = rows.length + " كلمة";
  $("#kwRows").innerHTML = rows.slice(0, 300).map(k => `<tr>
    <td><b style="font-size:13px">${esc(k.keyword)}</b></td>
    <td><span class="chip ${k.intent.includes("استعادة") ? "vi" : k.intent.includes("ابتزاز") ? "bad" : "cy"}">${esc(k.intent)}</span></td>
    <td><div style="display:flex;align-items:center;gap:6px"><div class="bar b3" style="width:56px"><i style="width:${k.popularity}%"></i></div><span class="num" style="font-size:11px">${k.popularity}</span></div></td>
    <td><div style="display:flex;align-items:center;gap:6px"><div class="bar b2" style="width:56px"><i style="width:${k.difficulty}%"></i></div><span class="num" style="font-size:11px">${k.difficulty}</span></div></td>
    <td class="num">${k.buyer_intent}</td>
    <td><b class="num" style="color:${k.opportunity >= 80 ? "#4ade80" : k.opportunity >= 65 ? "#67e8f9" : "#94a3b8"}">${k.opportunity}</b></td>
    <td style="font-size:11px;color:var(--dim)">${esc((k.engines || []).join(" + "))}</td>
    <td><button class="btn sm" onclick="useKw('${esc(k.keyword).replace(/'/g, "\\'")}')">استخدام</button></td>
  </tr>`).join("");
}
function loadKwRows() {
  const p = new URLSearchParams({ limit: 500, sort: $("#kwSort").value });
  if ($("#kwIntent").value) p.set("intent", $("#kwIntent").value);
  if ($("#kwQ").value) p.set("q", $("#kwQ").value);
  api("/api/keywords?" + p).then(renderKw);
}
["kwIntent", "kwSort"].forEach(id => $("#" + id).onchange = loadKwRows);
$("#kwQ").oninput = (() => { let t; return () => { clearTimeout(t); t = setTimeout(loadKwRows, 350); }; })();
function useKw(k) {
  navigator.clipboard.writeText(k); toast("نُسخت: " + k);
}
async function expandKw() {
  const seed = $("#expSeed").value.trim(); if (!seed) return;
  $("#expOut").innerHTML = "<div class='empty'><span class='spin'></span> يستعلم…</div>";
  try {
    const d = await api("/api/keywords/expand?seed=" + encodeURIComponent(seed));
    $("#expOut").innerHTML = `<div style="font-size:12px;color:var(--dim);margin-bottom:6px">Google: ${d.raw.google.length} · Bing: ${d.raw.bing.length}</div>` +
      d.merged.map(x => `<span class="sig" style="font-size:12px;padding:4px 9px;margin:2px" onclick="navigator.clipboard.writeText('${esc(x).replace(/'/g, "\\'")}');toast('نُسخت')">${esc(x)}</span>`).join("");
  } catch (e) { $("#expOut").innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
}

/* ─────────── SEO ─────────── */
async function loadAudit(refresh) {
  const btn = $("#auditBtn"); if (btn) { btn.disabled = true; btn.innerHTML = `<span class="spin"></span> يزحف…`; }
  try {
    const a = await api("/api/seo/audit" + (refresh ? "?refresh=true" : ""));
    $("#seoAt").textContent = dt(a.crawled_at);
    $("#seoServer").textContent = "الخادم: " + (a.checks.server || "?");
    $("#seoServer").className = "chip";
    $("#seoChallenge").textContent = a.checks.js_challenge ? "تحدي JS مفعّل ⚠" : "لا تحديات JS ✓";
    $("#seoChallenge").className = "chip " + (a.checks.js_challenge ? "bad" : "ok");
    $("#seoTtfb").textContent = "TTFB " + a.checks.ttfb_ms + "ms";
    $("#seoTtfb").className = "chip " + (a.checks.ttfb_ms < 400 ? "ok" : "warn");
    $("#gauges2").innerHTML = ["seo:SEO", "performance:الأداء", "security:الأمان", "content:المحتوى"]
      .map(x => { const [k, l] = x.split(":"); return gauge(l, a.scores[k]); }).join("");
    const c = a.checks;
    $("#seoChecks").innerHTML = [
      ["HSTS", c.hsts], ["CSP", c.csp], ["X-Frame-Options", c.x_frame], ["Gzip", c.gzip],
      ["robots.txt", c.robots_ok], ["sitemap.xml", c.sitemap_ok], ["صفحة الأدوات قابلة للفهرسة", c.tools_page_indexable],
      ["404 صحيح", !c.soft404]
    ].map(([k, v]) => `<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid rgba(27,39,64,.6);font-size:12.5px">
      <span>${k}</span><span class="chip ${v ? "ok" : "bad"}">${v ? "✓" : "✗"}</span></div>`).join("") +
      `<div style="font-size:11.5px;color:var(--dim);margin-top:8px">HTML: ${(c.html_bytes / 1024).toFixed(0)}KB · أصول: ${(c.assets_bytes / 1024).toFixed(0)}KB · روابط sitemap: ${c.sitemap_urls}</div>`;

    const order = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };
    $("#issueList").innerHTML = [...(a.issues || [])].sort((x, y) => order[x.severity] - order[y.severity]).map(i => `
      <div class="issue"><div class="sev ${i.severity}"></div><div style="flex:1">
        <h4>${esc(i.title)} <span class="chip ${i.severity === "critical" || i.severity === "high" ? "bad" : i.severity === "medium" ? "warn" : "ok"}">${esc(i.severity)}</span>
        <span class="chip">${esc(i.area)}</span></h4>
        <p>${esc(i.detail)}</p><div class="fix">✔ ${esc(i.fix)}</div></div></div>`).join("");

    $("#pageRows").innerHTML = Object.entries(a.pages || {}).map(([p, v]) => `<tr>
      <td class="mono">${esc(p)}</td>
      <td><span class="chip ${v.status === 200 ? "ok" : "bad"}">${v.status}</span></td>
      <td class="num" style="color:${v.title_len > 60 ? "#fb7185" : "#4ade80"}">${v.title_len ?? "—"}</td>
      <td class="num" style="color:${v.desc_len > 160 ? "#fb7185" : v.desc_len < 70 ? "#fbbf24" : "#4ade80"}">${v.desc_len ?? "—"}</td>
      <td class="num">${v.h2_count ?? "—"}</td>
      <td class="num">${v.words ?? "—"}</td>
      <td class="num">${v.img_no_alt ?? "—"}</td>
      <td class="num">${v.ldjson ?? 0}</td>
      <td class="num">${v.latency_ms ?? "—"}ms</td></tr>`).join("");

    const f = await api("/api/seo/fixes");
    $("#fixRows").innerHTML = f.current_vs_suggested.map(x => `<tr>
      <td class="mono" style="font-size:11px">${esc(x.path)}</td>
      <td style="font-size:12px"><b>${esc(x.suggested_title)}</b><br><span class="chip ${x.title_len <= 60 ? "ok" : "warn"}">${x.title_len} حرف</span></td>
      <td style="font-size:11.5px;color:var(--muted)">${esc(x.suggested_desc)} <span class="chip ${x.desc_len <= 160 ? "ok" : "warn"}">${x.desc_len}</span></td></tr>`).join("");
    $("#newPages").innerHTML = f.new_pages.map(p => `<div style="padding:9px 0;border-bottom:1px solid rgba(27,39,64,.6)">
      <b style="font-size:13px">${esc(p.title)}</b>
      <div style="font-size:11.5px;color:var(--dim)">${esc(p.slug)} · ${esc(p.kw)}</div>
      <div style="font-size:11.5px;color:#67e8f9">${esc(p.why)}</div></div>`).join("");
    $("#quickWins").innerHTML = f.quick_wins.map(w => `<div style="display:flex;gap:8px;padding:5px 0;font-size:12.5px"><span style="color:var(--emerald)">✔</span><span>${esc(w)}</span></div>`).join("");
    $("#schemaBox").textContent = JSON.stringify(f.schema_example, null, 2);
  } catch (e) {
    $("#issueList").innerHTML = `<div class="empty">${esc(e.message)}</div>`;
  } finally { if (btn) { btn.disabled = false; btn.textContent = "⟳ إعادة الزحف الآن"; } }
}

/* ─────────── COMPETITORS ─────────── */
async function loadComp() {
  try {
    const d = await api("/api/competitors");
    const c = d.competitors || [];
    $("#compList").innerHTML = c.map(x => `<div class="issue" style="align-items:flex-start">
      <div class="sev ${x.threat === "عالٍ" ? "high" : "medium"}"></div><div style="flex:1">
      <h4>${esc(x.name)} <span class="chip ${x.threat === "عالٍ" ? "bad" : "warn"}">تهديد ${esc(x.threat)}</span>
      <span class="chip">${esc(x.type)}</span></h4>
      <p><b>قوته:</b> ${esc(x.strength)}</p><p><b>ثغرته:</b> ${esc(x.weakness)}</p>
      <a class="btn sm" style="margin-top:6px" href="${esc(x.url)}" target="_blank" rel="noopener">زيارة ↗</a></div></div>`).join("");
    $("#compGaps").innerHTML = (d.gaps_for_abunawaf || []).map(g => `<div style="display:flex;gap:8px;padding:6px 0;font-size:13px"><span style="color:var(--amber)">◆</span><span>${esc(g)}</span></div>`).join("");
  } catch (e) { $("#compList").innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
}

/* ─────────── TOOLS ─────────── */
async function loadTools(refresh) {
  try {
    const d = await api("/api/tools" + (refresh ? "?refresh=true" : ""));
    $("#toolsMeta").textContent = "فحص: " + dt(d.summary.checked_at);
    $("#toolsAlive").textContent = `${d.summary.alive}/${d.summary.total} تعمل`;
    $("#toolsAlive").className = "chip " + (d.summary.alive === d.summary.total ? "ok" : "warn");
    $("#toolCards").innerHTML = d.tools.map(t => `<div class="tool">
      <div class="logo">${esc(t.name[0])}</div>
      <div style="min-width:0"><b>${esc(t.name)}</b><small>${esc(t.desc)}</small>
        <span class="chip" style="margin-top:4px">${esc(t.cat)}</span></div>
      <div class="meta">
        <span class="chip ${t.alive ? "ok" : "bad"}">${t.http ? "HTTP " + t.http : "خطأ"}</span>
        <span class="chip">${t.latency_ms ? t.latency_ms + "ms" : t.speed}</span>
        <a class="btn sm" href="${esc(t.url)}" target="_blank" rel="noopener">فتح ↗</a></div></div>`).join("");
    $("#activated").innerHTML = d.activated_here.map(a => `<div style="display:flex;gap:8px;padding:6px 0;border-bottom:1px solid rgba(27,39,64,.6);font-size:12.5px">
      <span class="chip ${a.status === "مفعّل" ? "ok" : "warn"}">${esc(a.status)}</span>
      <div><b>${esc(a.name)}</b><div style="color:var(--dim);font-size:11.5px">${esc(a.use)}</div></div></div>`).join("");
    $("#catalog").innerHTML = d.skills_catalog.map(s => `<div style="margin-bottom:10px">
      <b style="font-size:12.5px;color:#a5b4fc">${esc(s.section)}</b>
      <div>${s.items.map(i => `<span class="sig">${esc(i)}</span>`).join(" ")}</div></div>`).join("");
  } catch (e) { $("#toolCards").innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
}

/* ─────────── SOCIAL ─────────── */
async function loadSocial() {
  try {
    const d = await api("/api/social");
    $("#socialRows").innerHTML = d.accounts.map(a => `<tr>
      <td><b>${esc(a.platform)}</b></td><td class="mono">${esc(a.handle)}</td>
      <td style="font-size:12px">${esc(a.role)}</td>
      <td><span class="chip ${a.http === 200 ? "ok" : "bad"}">${a.http ?? "خطأ"}</span></td>
      <td style="font-size:11.5px;color:var(--dim);max-width:340px">${esc(a.note)}</td>
      <td><a class="btn sm" href="${esc(a.url)}" target="_blank" rel="noopener">فتح ↗</a></td></tr>`).join("");
    const g = d.github || {};
    $("#ghBox").innerHTML = g.error ? `<div class="empty">${esc(g.error)}</div>` : `
      <div class="filters" style="margin:0 0 10px">
        <span class="chip cy">${num(g.public_repos)} مستودع</span>
        <span class="chip">${num(g.followers)} متابع</span>
        <span class="chip">منذ ${esc(g.created_at)}</span>
      </div>
      <div class="tbl-wrap"><table><thead><tr><th>المستودع</th><th>الوصف</th><th>آخر تحديث</th></tr></thead><tbody>
      ${(g.recent_repos || []).map(r => `<tr><td><a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.name)}</a></td>
        <td style="font-size:11.5px;color:var(--muted)">${esc(r.desc)}</td><td class="num" style="font-size:11px">${esc(r.updated)}</td></tr>`).join("")}
      </tbody></table></div>`;
    $("#socialGaps").innerHTML = (d.gaps || []).map(x => `<div style="display:flex;gap:8px;padding:6px 0;font-size:12.5px"><span style="color:var(--amber)">◆</span><span>${esc(x)}</span></div>`).join("");
  } catch (e) { toast("خطأ: " + e.message); }
}

/* ─────────── REPORT ─────────── */
async function loadReport(force) {
  if (loaded.report === 2 && !force) return;
  try {
    const txt = await fetch("/api/report").then(r => r.text());
    $("#reportBox").innerHTML = md(txt);
    loaded.report = 2;
  } catch (e) { $("#reportBox").innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
}
function md(t) {
  let h = esc(t);
  h = h.replace(/^### (.*)$/gm, "<h3>$1</h3>").replace(/^## (.*)$/gm, "<h2>$1</h2>").replace(/^# (.*)$/gm, "<h1>$1</h1>");
  h = h.replace(/^&gt; (.*)$/gm, "<blockquote>$1</blockquote>");
  h = h.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/`([^`]+)`/g, "<code>$1</code>");
  h = h.replace(/^\s*[-*] (.*)$/gm, "<li>$1</li>").replace(/(<li>[\s\S]*?<\/li>)/g, m => "<ul>" + m + "</ul>");
  h = h.replace(/\|(.+)\|\n\|[-\s|:]+\|\n((?:\|.*\|\n?)*)/g, (m, head, body) => {
    const th = head.split("|").filter(x => x.trim()).map(x => `<th>${x.trim()}</th>`).join("");
    const tr = body.trim().split("\n").map(r => "<tr>" + r.split("|").filter(x => x.trim()).map(x => `<td>${x.trim()}</td>`).join("") + "</tr>").join("");
    return `<table>${th ? "<thead><tr>" + th + "</tr></thead>" : ""}<tbody>${tr}</tbody></table>`;
  });
  h = h.replace(/^---$/gm, "<hr>");
  h = h.replace(/\n{2,}/g, "</p><p>");
  return "<p>" + h + "</p>";
}

function refreshAll() {
  loaded.dash = 0; loadDash(); toast("جارٍ التحديث…");
}
/* إقلاع */
if (window.STATIC_MODE && window.BUILD_STAMP) {
  const s = document.getElementById("viewSub");
  if (s) s.innerHTML += ` <span class="chip ok" style="margin-inline-start:6px">نسخة ثابتة · ${window.BUILD_STAMP}</span>`;
}
loadDash();
setTimeout(() => { loadLeads(); loadKw(); loadTools(false); loadSocial(); }, 400);
