# نقطة دخول Vercel (ASGI) — جاهزة للنشر عند توفّر مفتاح Vercel صالح
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from server.app import app  # noqa: E402,F401
