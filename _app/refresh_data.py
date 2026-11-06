# -*- coding: utf-8 -*-
"""
refresh_data.py — نقطة تشغيل التحديث الكامل (تُستخدم في GitHub Actions).
1. صيد عملاء محتملين جديد (Bing SERP عبر قارئ صفحات).
2. تحديث كلمات البحث أسبوعياً (أو عند FORCE_KEYWORDS=1).
3. إعادة بناء النسخة الثابتة (SITE_OUT يحدد مجلد الإخراج).
"""
import os, subprocess, sys, json, datetime, time

BASE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def run(name, script, timeout=2400):
    print(f"\n=== {name} ===", flush=True)
    t0 = time.time()
    p = subprocess.run([PY, script], cwd=BASE, capture_output=True, text=True, timeout=timeout)
    print((p.stdout or "")[-4000:])
    if p.returncode != 0:
        print("STDERR:", (p.stderr or "")[-2000:], file=sys.stderr)
    print(f"--- {name}: {round(time.time()-t0)}s rc={p.returncode}", flush=True)
    return p.returncode == 0


def keywords_age_days():
    p = os.path.join(BASE, "data", "keywords.json")
    if not os.path.exists(p):
        return 999
    meta = json.load(open(p, encoding="utf-8")).get("meta", {})
    try:
        gen = datetime.datetime.fromisoformat(meta["generated_at"])
        return (datetime.datetime.now() - gen).days
    except Exception:
        return 999


if __name__ == "__main__":
    ok1 = run("صيد العملاء (X + ويب)", "harvest_x.py", timeout=2400)
    try:
        age = keywords_age_days()
    except Exception:
        age = 999
    if os.environ.get("FORCE_KEYWORDS") == "1" or age >= 7:
        run("كلمات البحث", "harvest_keywords.py", timeout=1800)
    else:
        print(f"كلمات البحث حديثة ({age} يوم) — تم تخطيها")
    run("بناء النسخة الثابتة", "build_static.py", timeout=900)
    print("\n✔ انتهى التحديث", datetime.datetime.now(datetime.timezone.utc).isoformat())
