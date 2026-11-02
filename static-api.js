/* ══════════════════════════════════════════════════════════════
   static-api.js — طبقة توافق تجعل المنصة تعمل بالكامل على استضافة
   ثابتة (GitHub Pages) بنفس واجهات الـAPI الأصلية.
   البيانات تأتي من data/*.json التي يحدّثها GitHub Actions كل 6 ساعات.
   ما لا يمكن تنفيذه في المتصفح (زحف/صيد حي) يعرض رسالة واضحة + رابط التشغيل.
   ══════════════════════════════════════════════════════════════ */
(function () {
  if (!window.STATIC_MODE) return;
  const BASE = (function () {
    try {
      const src = document.currentScript && document.currentScript.src;
      if (src) return src.replace(/[^/]+$/, "");
    } catch (e) {}
    return location.origin + location.pathname.replace(/[^/]*$/, "");
  })();
  const D = BASE + "data/";
  const cache = {};
  const origFetch = window.fetch.bind(window);
  const LS_KEY = "abunawaf_manual_leads";
  window.ACTIONS_URL = window.ACTIONS_URL || "https://github.com/abunoafceh8-commits/abunawaf-os/actions";

  async function j(name) {
    if (cache[name]) return cache[name];
    const r = await origFetch(D + name, { cache: "no-cache" });
    if (!r.ok) throw new Error("ملف البيانات غير متوفر: " + name);
    cache[name] = await r.json();
    return cache[name];
  }
  const manual = () => { try { return JSON.parse(localStorage.getItem(LS_KEY) || "[]"); } catch (e) { return []; } };
  const saveManual = (list) => localStorage.setItem(LS_KEY, JSON.stringify(list));
  const tierOf = (s) => (s >= 75 ? "ساخن" : s >= 55 ? "دافئ" : "مراقبة");

  function merged(base) {
    const seen = new Set(base.map(l => (l.url || "").split("?")[0].replace(/\/$/, "")));
    const extra = manual().filter(m => !seen.has((m.url || "").split("?")[0].replace(/\/$/, "")))
      .map(m => Object.assign({
        kind: "مُضاف يدوياً", signals: [], snippet: m.note || "", title: m.name || "عميل محتمل",
        score: 75, action: "تواصل مباشرة عبر القناة المذكورة", platform: "مباشر",
        service: "—", query: "إدخال محلي", manual: true
      }, m, { tier: tierOf(+m.score || 75) }));
    return base.concat(extra).map(l => Object.assign({}, l, { tier: l.tier || tierOf(+l.score || 0) }));
  }

  function leadsResponse(params) {
    return j("leads.json").then(d => {
      let base = params.get("include_raw") === "true" ? (d.all || d.leads) : d.leads;
      let rows = merged(base);
      const f = { platforms: [...new Set(rows.map(r => r.platform))].sort(), services: [...new Set(rows.map(r => r.service))].sort() };
      f.tiers = { "ساخن": 0, "دافئ": 0, "مراقبة": 0 };
      rows.forEach(r => { f.tiers[r.tier] = (f.tiers[r.tier] || 0) + 1; });
      f.total = rows.length; f.raw_total = (d.all || []).length;
      const tier = params.get("tier"), plat = params.get("platform"), svc = params.get("service"), q = params.get("q");
      if (tier) rows = rows.filter(r => r.tier === tier);
      if (plat) rows = rows.filter(r => r.platform === plat);
      if (svc) rows = rows.filter(r => r.service === svc);
      if (q) { const qq = q.toLowerCase(); rows = rows.filter(r => ((r.title || "") + (r.snippet || "") + r.url).toLowerCase().includes(qq)); }
      const min = +(params.get("min_score") || 0);
      rows = rows.filter(r => (r.score || 0) >= min).sort((a, b) => b.score - a.score);
      const limit = +(params.get("limit") || 500);
      return { meta: d.meta || {}, sources: d.sources || [], facets: f, count: rows.length, leads: rows.slice(0, limit) };
    });
  }

  function kwResponse(params) {
    return j("keywords.json").then(d => {
      let rows = d.keywords;
      const intent = params.get("intent"), q = params.get("q");
      if (intent) rows = rows.filter(k => k.intent === intent);
      if (q) rows = rows.filter(k => k.keyword.toLowerCase().includes(q.toLowerCase()));
      const sortKey = { opportunity: "opportunity", popularity: "popularity", difficulty: "difficulty", buyer_intent: "buyer_intent" }[params.get("sort") || "opportunity"];
      rows = rows.slice().sort((a, b) => (sortKey === "difficulty" ? a.difficulty - b.difficulty : b[sortKey] - a[sortKey]));
      const intents = {};
      d.keywords.forEach(k => { intents[k.intent] = (intents[k.intent] || 0) + 1; });
      return { meta: d.meta, intents, total: d.keywords.length, count: rows.length, keywords: rows.slice(0, +(params.get("limit") || 300)) };
    });
  }

  const ROUTES = {
    "/api/overview": () => j("overview.json"),
    "/api/leads": (p) => leadsResponse(p),
    "/api/leads/status": () => j("overview.json").then(o => ({ job: { running: false, error: null }, last_run: o.leads.generated_at, static: true })),
    "/api/leads/refresh": () => ({ status: "static", message: "التحديث الحي يحتاج خادماً. شغّل سير العمل من GitHub Actions.", actions: window.ACTIONS_URL }),
    "/api/leads/add": (p, body) => {
      const list = manual(); list.push(JSON.parse(body || "{}")); saveManual(list);
      return { ok: true, item: list[list.length - 1], local: true };
    },
    "/api/keywords": (p) => kwResponse(p),
    "/api/keywords/clusters": () => j("clusters.json"),
    "/api/keywords/expand": (p) => j("expansions.json").then(x => x[p.get("seed")] || { seed: p.get("seed"), merged: [], count: 0, raw: { google: [], bing: [] }, note: "غير مُجمَّع مسبقاً — التوسيع الحي يحتاج خادماً" }),
    "/api/seo/audit": () => j("audit.json"),
    "/api/seo/fixes": () => j("fixes.json"),
    "/api/tools": () => j("tools.json"),
    "/api/social": () => j("social.json"),
    "/api/competitors": () => j("competitors.json"),
    "/api/read-url": () => ({ error: "قراءة الروابط تحتاج خادماً (trafilatura). متاحة عند تشغيل نسخة FastAPI.", url: "" }),
  };

  window.fetch = async function (input, init) {
    const url = typeof input === "string" ? input : (input && input.url) || "";
    if (!url.startsWith("/api/")) return origFetch(input, init);
    const [path, qs] = url.split("?");
    const params = new URLSearchParams(qs || "");
    const body = init && init.body;
    if (path === "/api/report") {
      const r = await origFetch(D + "report.md");
      return new Response(await r.text(), { status: 200, headers: { "Content-Type": "text/markdown; charset=utf-8" } });
    }
    const route = ROUTES[path];
    if (!route) return new Response(JSON.stringify({ error: "مسار غير متاح في النسخة الثابتة: " + path }), { status: 404, headers: { "Content-Type": "application/json" } });
    try {
      const out = await route(params, body);
      return new Response(JSON.stringify(out), { status: out && out.error && !out.leads ? 502 : 200, headers: { "Content-Type": "application/json; charset=utf-8" } });
    } catch (e) {
      return new Response(JSON.stringify({ error: e.message }), { status: 500, headers: { "Content-Type": "application/json" } });
    }
  };

  // إعادة توجيه روابط التصدير إلى ملفات CSV المُولّدة
  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll('a[href^="/api/leads/export.csv"]').forEach(a => a.href = D + "leads.csv");
    document.querySelectorAll('a[href^="/api/keywords/export.csv"]').forEach(a => a.href = D + "keywords.csv");
    document.querySelectorAll('a[href="/api/report"]').forEach(a => a.href = D + "report.md");
  });
})();
