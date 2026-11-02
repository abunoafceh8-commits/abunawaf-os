Deno.serve(async (req: Request) => {
  const cors = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "authorization, apikey, content-type",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "content-type": "application/json; charset=utf-8",
  };
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  const u = new URL(req.url);
  let p = u.pathname.replace(/^\/functions\/v1\/[^/]+/, "");
  p = p.replace(/^\/?api(?=\/|$)/, "") || "/";
  const json = (o: unknown, code = 200) => new Response(JSON.stringify(o), { status: code, headers: cors });

  try {
    if (p === "/" || p === "/health")
      return json({ ok: true, service: "abunawaf-api", runtime: "deno-edge", time: new Date().toISOString() });

    /* ── تقييم رابط عميل: جلب الصفحة + استخراج + تحليل النية ── */
    if (p === "/read-url") {
      let target = u.searchParams.get("url") || "";
      if (req.method === "POST") {
        try { const b = await req.json(); target = b.url || target; } catch (_e) { /* ignore */ }
      }
      if (!target) return json({ error: "أرسل الرابط في ?url= أو في جسم الطلب" }, 400);
      let parsed: URL;
      try { parsed = new URL(target); } catch (_e) { return json({ error: "رابط غير صالح" }, 400); }
      if (!/^https?:$/.test(parsed.protocol)) return json({ error: "بروتوكول غير مدعوم" }, 400);
      const blocked = ["localhost", "127.0.0.1", "0.0.0.0", "169.254.169.254", "::1"];
      if (blocked.some(d => parsed.hostname === d || parsed.hostname.endsWith(".local")))
        return json({ error: "عنوان داخلي غير مسموح" }, 400);
      const t0 = Date.now();
      const r = await fetch(parsed.toString(), {
        headers: {
          "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
          "accept-language": "ar,en;q=0.8",
        },
        redirect: "follow",
      });
      let html = (await r.text()).slice(0, 900000);
      let method = "deno-edge · fetch + استخراج نص";
      if (r.status >= 400 || html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim().length < 400) {
        try {
          const alt = await fetch("https://r.jina.ai/" + parsed.toString(), { headers: { accept: "text/plain" } });
          const t = await alt.text();
          if (alt.ok && t.length > 400) { html = "<title>" + t.split("\n")[0].slice(0, 120) + "</title>" + t; method = "r.jina.ai reader (احتياطي)"; }
        } catch (_e) { /* ignore */ }
      }
      const pick = (re: RegExp) => { const m = html.match(re); return m ? m[1].trim() : ""; };
      const title = pick(/<title[^>]*>([\s\S]{1,300}?)<\/title>/i) || pick(/property=["']og:title["'][^>]*content=["']([^"']+)/i);
      const desc = pick(/name=["']description["'][^>]*content=["']([^"']{1,600})/i) ||
                   pick(/property=["']og:description["'][^>]*content=["']([^"']{1,600})/i);
      const site = pick(/property=["']og:site_name["'][^>]*content=["']([^"']+)/i);
      const text = html.replace(/<script[\s\S]*?<\/script>/gi, " ").replace(/<style[\s\S]*?<\/style>/gi, " ")
        .replace(/<[^>]+>/g, " ").replace(/&nbsp;/g, " ").replace(/&amp;/g, "&").replace(/&quot;/g, '"')
        .replace(/\s+/g, " ").trim();
      const words = text ? text.split(/\s+/).length : 0;

      const WEIGHTS: Record<string, number> = {
        "مسروق": 14, "مخترق": 16, "اختراق": 14, "هاك": 6, "استرجاع": 13, "استعادة": 13, "مقفل": 10, "موقوف": 11,
        "محظور": 10, "باند": 12, "ابتزاز": 16, "تهكير": 12, "قرصنة": 13, "مفخ": 12, "المبتز": 16, "انتحال": 13,
        "سرقة": 11, "حسابي": 12, "حساب": 8, "سناب": 8, "انستقرام": 9, "واتساب": 9, "تيك توك": 8, "فيسبوك": 9,
        "تلجرام": 8, "كلمة السر": 10, "كلمة المرور": 10, "تحقق": 7, "رمز": 6, "شخص": 4, "محتاج": 9, "محتاج مساعده": 12,
        "مساعده": 8, "مساعدة": 8, "أبي": 5, "ابغى": 8, "ضروري": 8, "تكفون": 9, "وش الحل": 10, "لا اعرف": 5,
      };
      const hay = (" " + title + " " + desc + " " + text.slice(0, 3000) + " ").toLowerCase();
      const signals: string[] = [];
      let score = 0;
      for (const k of Object.keys(WEIGHTS)) {
        if (hay.includes(k)) { signals.push(k); score += WEIGHTS[k]; }
      }
      score = Math.max(0, Math.min(100, score));
      const tier = score >= 75 ? "ساخن" : score >= 55 ? "دافئ" : "مراقبة";
      const action = score >= 75
        ? "ردّ عام سريع + عرض مساعدة مجانية دون طلب أي بيانات"
        : score >= 55 ? "راقب المنشور وردّ إن أضاف تفاصيل" : "أرشفة — إشارة ضعيفة";

      const service = /ابتزاز|تهديد|مبتز/.test(hay) ? "مكافحة ابتزاز"
        : /موقوف|مقفل|باند|محظور/.test(hay) ? "استعادة حساب موقوف"
        : /مجهول|انتحال|ينتحل/.test(hay) ? "كشف هوية OSINT"
        : "استعادة حساب مسروق";
      return json({
        ok: true, url: parsed.toString(), status: r.status, final_url: r.url, site,
        title, description: desc, words, ms: Date.now() - t0,
        score, tier, signals, action, suggested_service: service,
        method, chars: text.length,
        excerpt: text.slice(0, 1200),
        intent: score >= 75 ? "نية شراء عالية" : score >= 55 ? "اهتمام واضح" : "إشارة عامة",
      });
    }

    /* ── توسيع كلمات البحث من اقتراحات Google + Bing ── */
    if (p === "/expand") {
      const seed = (u.searchParams.get("seed") || "").trim();
      if (!seed) return json({ error: "أرسل بذرة البحث في ?seed=" }, 400);
      const safe = encodeURIComponent(seed);
      const out: Record<string, string[]> = { google: [], bing: [] };
      const jobs = [
        fetch(`https://suggestqueries.google.com/complete/search?client=firefox&hl=ar&q=${safe}`)
          .then(r => r.json()).then(j => { if (Array.isArray(j?.[1])) out.google = j[1]; }).catch(() => {}),
        fetch(`https://api.bing.com/osjson.aspx?query=${safe}&market=ar-SA`)
          .then(r => r.json()).then(j => { if (Array.isArray(j?.[1])) out.bing = j[1]; }).catch(() => {}),
      ];
      await Promise.all(jobs);
      const merged = Array.from(new Set([...out.google, ...out.bing].map((s: string) => String(s).trim()).filter(Boolean)));
      return json({ seed, count: merged.length, merged, raw: out, engines: { google: out.google.length, bing: out.bing.length } });
    }

    /* ── إحصاءات قاعدة البيانات (خدمة) ── */
    if (p === "/stats") {
      const url = Deno.env.get("SUPABASE_URL");
      const key = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
      if (!url || !key) return json({ error: "بيئة غير مهيّأة" }, 500);
      const r = await fetch(url + "/rest/v1/rpc/os_stats", {
        method: "POST",
        headers: { apikey: key, Authorization: "Bearer " + key, "Content-Type": "application/json" },
        body: "{}",
      });
      return json({ ok: true, stats: await r.json() });
    }

    return json({ error: "مسار غير معروف: " + p }, 404);
  } catch (e) {
    return json({ error: String((e as Error).message || e) }, 500);
  }
});
