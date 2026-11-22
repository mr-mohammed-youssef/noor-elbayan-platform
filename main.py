import hashlib
import json
import mimetypes
import os
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "platform.db"
VIDEOS_DIR = BASE_DIR / "protected_videos"
TICKET_IMAGES_DIR = BASE_DIR / "ticket_images"
TEMPLATES_DIR = BASE_DIR / "templates"

VIDEOS_DIR.mkdir(exist_ok=True)
TICKET_IMAGES_DIR.mkdir(exist_ok=True)
TEMPLATES_DIR.mkdir(exist_ok=True)

ALLOWED_VIDEO_EXT = {".mp4", ".webm", ".ogg", ".mov", ".m4v"}
ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
BRANCHES = ["النحو", "الصرف", "البلاغة", "الأدب", "النصوص", "المطالعة", "الإنشاء"]
GRADES = [
    "الأول الثانوي الأزهري",
    "الثاني الثانوي الأزهري",
    "الثالث الثانوي الأزهري",
]
TRACKS = ["علمي", "أدبي"]

TEACHER_MAIN_PHOTO = "https://www.mohammedyoussef2027.com/public/heroPhotos/teacher-photo.png"


def hash_secret(val: str) -> str:
    return hashlib.sha256(val.encode("utf-8")).hexdigest()


DEFAULT_SETTINGS = {
    "vodafone_number": "01066329782",
    "admin_whatsapp": "201066329782",
    "admin_email": "mohmed@mr.com",
    "admin_password_hash": hash_secret("admin123456"),
    "global_notice": "",
    "teacher_image": TEACHER_MAIN_PHOTO,
}


def extract_youtube_id(url: str) -> str:
    if not url:
        return ""
    patterns = [r"(?:v=|/embed/|/shorts/|youtu\.be/)([A-Za-z0-9_-]{11})"]
    for pat in patterns:
        m = re.search(pat, url.strip())
        if m:
            return m.group(1)
    return ""


(TEMPLATES_DIR / "layout.html").write_text(
    """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{{ title }} | نور البيان — أ. محمد يوسف</title>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800;900&display=swap" />
  <style>
    :root {
      --bg: #eef3f8;
      --card: #ffffff;
      --card2: #e6eef5;
      --txt: #0b192c;
      --muted: #496073;
      --pri: #1d4ed8;
      --olive: #4d5d2b;
      --olive-soft: rgba(77, 93, 43, 0.14);
      --gold: #a16207;
      --err: #dc2626;
      --bdr: #cbd8e6;
      --glyph: rgba(29, 78, 216, 0.075);
      --shadow: 0 10px 26px rgba(11, 25, 44, 0.08);
    }
    body.dark {
      --bg: #05080f;
      --card: #0c1320;
      --card2: #131e2e;
      --txt: #f1f5f9;
      --muted: #94a3b8;
      --pri: #3b82f6;
      --olive: #8fa34b;
      --olive-soft: rgba(143, 163, 75, 0.16);
      --gold: #fbbf24;
      --err: #f87171;
      --bdr: #1e2d42;
      --glyph: rgba(143, 163, 75, 0.09);
      --shadow: 0 12px 30px rgba(0, 0, 0, 0.55);
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Cairo', sans-serif; }
    body {
      background: var(--bg);
      color: var(--txt);
      min-height: 100vh;
      line-height: 1.65;
      position: relative;
      overflow-x: hidden;
    }

    /* بانر دعاء مدمج داخل الصفحة لمدة 4 ثوانٍ (يظهر عند فتح المنصة أو Refresh فقط) */
    .inline-dua-banner {
      max-width: 1240px;
      margin: 14px auto 0;
      padding: 12px 18px;
      border-radius: 16px;
      background: linear-gradient(120deg, rgba(11, 25, 44, 0.94), rgba(29, 78, 216, 0.88), rgba(60, 74, 33, 0.92));
      color: #f8fafc;
      border: 1px solid rgba(143, 163, 75, 0.55);
      box-shadow: var(--shadow);
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 14px;
      flex-wrap: wrap;
      transition: max-height 0.45s ease, opacity 0.45s ease, margin 0.45s ease, padding 0.45s ease;
      max-height: 160px;
      opacity: 1;
      overflow: hidden;
    }
    .inline-dua-banner.dua-done {
      max-height: 0;
      opacity: 0;
      margin-top: 0;
      padding-top: 0;
      padding-bottom: 0;
      border-width: 0;
      pointer-events: none;
    }
    .inline-dua-left { display: flex; align-items: center; gap: 12px; }
    .inline-dua-avatar {
      width: 52px; height: 52px; border-radius: 50%; object-fit: cover;
      border: 2px solid #8fa34b; flex-shrink: 0;
    }
    .inline-dua-text { font-weight: 900; font-size: 1.05rem; }
    .inline-dua-sub { font-size: 0.78rem; opacity: 0.88; }

    #arabicBg { position: fixed; inset: 0; pointer-events: none; z-index: 0; overflow: hidden; }
    .ar-glyph {
      position: absolute; font-weight: 900; color: var(--glyph); user-select: none;
      will-change: transform;
      animation: letterDrift var(--dur, 18s) ease-in-out var(--delay, 0s) infinite alternate;
    }
    @keyframes letterDrift {
      0% { transform: translate(0px, 0px) rotate(-6deg); }
      50% { transform: translate(var(--dx, 16px), var(--dy, -22px)) rotate(8deg); }
      100% { transform: translate(calc(var(--dx, 16px) * -0.7), var(--dy, -22px)) rotate(-10deg); }
    }
    .page-layer { position: relative; z-index: 1; }
    .topbar {
      background: var(--card); border-bottom: 1px solid var(--bdr);
      padding: 10px 20px; display: flex; justify-content: space-between; align-items: center;
      gap: 12px; flex-wrap: wrap; position: sticky; top: 0; z-index: 20;
    }
    .brand-box { display: flex; align-items: center; gap: 10px; }
    .brand-logo-badge {
      width: 38px; height: 38px; border-radius: 10px;
      background: linear-gradient(135deg, var(--pri), var(--olive));
      color: #fff; font-weight: 900; display: grid; place-items: center; font-size: 1rem;
    }
    .theme-pill {
      display: inline-flex; align-items: center; gap: 6px; padding: 5px 12px;
      border-radius: 999px; border: 1px solid var(--bdr); background: var(--card2);
      color: var(--txt); font-weight: 800; cursor: pointer; font-size: 0.84rem;
    }
    .global-alert {
      max-width: 1240px; margin: 12px auto 0; background: var(--olive-soft);
      border: 1px solid var(--olive); color: var(--olive);
      border-radius: 12px; padding: 10px 16px; font-weight: 800;
    }
    .card {
      background: var(--card); border: 1px solid var(--bdr); border-radius: 16px;
      padding: 20px; box-shadow: var(--shadow); margin-bottom: 16px;
    }
    .btn {
      display: inline-flex; align-items: center; justify-content: center; gap: 6px;
      padding: 9px 16px; border-radius: 10px; border: none; font-weight: 800;
      cursor: pointer; text-decoration: none; font-size: 0.9rem;
    }
    .btn-blue { background: var(--pri); color: #fff; }
    .btn-olive { background: var(--olive); color: #fff; }
    .btn-red { background: var(--err); color: #fff; }
    .btn-out { background: transparent; color: var(--txt); border: 1px solid var(--bdr); }
    .btn-sm { padding: 6px 12px; font-size: 0.82rem; border-radius: 8px; }
    .field { margin-bottom: 12px; }
    label { display: block; font-weight: 700; margin-bottom: 5px; font-size: 0.9rem; }
    input, select, textarea {
      width: 100%; padding: 10px 12px; border-radius: 10px; border: 1px solid var(--bdr);
      background: var(--card2); color: var(--txt); font-size: 0.93rem; outline: none;
    }
    textarea { min-height: 84px; resize: vertical; }
    .grid2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 14px; }
    .grid3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px; }
    .row {
      background: var(--card2); border: 1px solid var(--bdr); border-radius: 12px;
      padding: 12px 14px; margin-top: 10px; display: flex; justify-content: space-between;
      align-items: center; gap: 10px; flex-wrap: wrap;
    }
    .pill { display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 0.78rem; font-weight: 800; }
    .pill-ok { background: var(--olive-soft); color: var(--olive); }
    .pill-warn { background: rgba(161, 98, 7, 0.16); color: var(--gold); }
    .msg-err {
      background: rgba(220, 38, 38, 0.12); border: 1px solid rgba(220, 38, 38, 0.35);
      color: var(--err); padding: 10px 14px; border-radius: 10px; font-weight: 800; margin-bottom: 12px;
    }
    .msg-ok {
      background: var(--olive-soft); border: 1px solid var(--olive);
      color: var(--olive); padding: 10px 14px; border-radius: 10px; font-weight: 800; margin-bottom: 12px;
    }
    .muted { color: var(--muted); }

    .dash-shell {
      max-width: 1240px; margin: 18px auto; padding: 0 14px 40px;
      display: grid; grid-template-columns: 1fr 255px; gap: 18px; align-items: start;
    }
    .dash-shell.collapsed { grid-template-columns: 1fr 74px; }
    @media (max-width: 880px) {
      .dash-shell, .dash-shell.collapsed { grid-template-columns: 1fr; }
    }
    .right-drawer {
      background: var(--card); border: 1px solid var(--bdr); border-radius: 16px;
      padding: 14px 10px; box-shadow: var(--shadow); position: sticky; top: 68px;
    }
    .drawer-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; padding: 0 4px; }
    .collapse-btn {
      width: 28px; height: 28px; border-radius: 8px; border: none;
      background: var(--pri); color: #fff; font-weight: 900; cursor: pointer;
    }
    .nav-item-link {
      display: flex; align-items: center; gap: 10px; width: 100%; text-align: right;
      padding: 10px 12px; border-radius: 10px; border: none; background: transparent;
      color: var(--txt); font-weight: 800; text-decoration: none; cursor: pointer;
      font-size: 0.9rem; margin-bottom: 4px;
    }
    .nav-item-link.active { background: var(--pri); color: #fff; }
    .sub-nav { padding-right: 16px; margin-bottom: 6px; }
    .sub-link {
      display: block; padding: 6px 10px; border-radius: 8px; color: var(--muted);
      text-decoration: none; font-weight: 700; font-size: 0.84rem; margin-bottom: 2px;
    }
    .sub-link.active, .sub-link:hover { background: var(--olive-soft); color: var(--olive); }
    .dash-shell.collapsed .nav-label, .dash-shell.collapsed .sub-nav, .dash-shell.collapsed .drawer-title { display: none; }

    .kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 14px; margin-bottom: 16px; }
    .kpi-card {
      background: linear-gradient(135deg, #1d4ed8 0%, #0f172a 100%);
      color: #fff; border-radius: 14px; padding: 18px;
      display: flex; justify-content: space-between; align-items: center;
      box-shadow: var(--shadow);
    }
    .kpi-card.olive-kpi { background: linear-gradient(135deg, #4d5d2b 0%, #1c2410 100%); }
    .kpi-num { font-size: 1.6rem; font-weight: 900; line-height: 1.1; }
    .kpi-lbl { font-size: 0.88rem; font-weight: 700; opacity: 0.95; margin-top: 4px; }
    .kpi-icon-box {
      width: 44px; height: 44px; border-radius: 12px; background: rgba(255, 255, 255, 0.18);
      display: grid; place-items: center; font-size: 1.2rem; font-weight: 900;
    }

    .progress-layout { display: grid; grid-template-columns: 280px 1fr; gap: 16px; margin-bottom: 16px; }
    @media (max-width: 820px) { .progress-layout { grid-template-columns: 1fr; } }
    .progress-frame {
      background: var(--card); border: 2px solid var(--olive); border-radius: 16px;
      padding: 18px; text-align: center;
    }
    .teacher-color-meter {
      position: relative; width: 128px; height: 138px; margin: 8px auto 10px;
      border-radius: 16px; overflow: hidden; border: 2px solid var(--bdr);
    }
    .teacher-color-meter img { width: 100%; height: 100%; object-fit: cover; display: block; }
    .teacher-color-meter .bw-layer { filter: grayscale(100%) contrast(1.08); }
    .teacher-color-meter .color-reveal {
      position: absolute; inset: 0; overflow: hidden; transition: clip-path 0.5s ease;
    }
    .prog-bar-bg {
      height: 8px; border-radius: 999px; background: var(--card2);
      border: 1px solid var(--bdr); overflow: hidden; margin: 10px 0;
    }
    .prog-bar-fill { height: 100%; background: var(--olive); border-radius: 999px; transition: width 0.4s ease; }

    .course-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(265px, 1fr)); gap: 16px; }
    .course-card {
      background: var(--card); border: 1px solid var(--bdr); border-radius: 16px;
      overflow: hidden; display: flex; flex-direction: column; justify-content: space-between;
      box-shadow: var(--shadow);
    }
    .branch-hero-banner {
      background: linear-gradient(135deg, #0b192c 0%, #1d4ed8 58%, #3c4a21 100%);
      color: #fff; border-radius: 16px; padding: 18px; margin-bottom: 16px;
      display: flex; justify-content: space-between; align-items: center; gap: 16px; flex-wrap: wrap;
    }
    .branch-book-card {
      display: flex; align-items: center; gap: 12px;
      background: rgba(255, 255, 255, 0.1); border: 1px solid rgba(255, 255, 255, 0.22);
      padding: 10px 14px; border-radius: 14px;
    }
    .branch-book-card img {
      width: 68px; height: 78px; object-fit: cover; border-radius: 10px; border: 2px solid #fff;
    }
    .course-banner {
      height: 145px; position: relative; overflow: hidden;
      background: linear-gradient(135deg, #0b192c, #2f3b19);
      color: #fff; padding: 14px; display: flex; justify-content: space-between; align-items: flex-end;
    }
    .course-banner img.book-thumb {
      width: 64px; height: 78px; object-fit: cover; border-radius: 10px;
      border: 2px solid rgba(255, 255, 255, 0.7);
    }
    .course-body { padding: 14px; }
    .course-title { font-weight: 900; font-size: 1rem; margin-bottom: 8px; }

    .split-auth {
      max-width: 1060px; margin: 18px auto; padding: 0 14px;
      display: grid; grid-template-columns: 1fr 1.1fr; gap: 20px; align-items: stretch;
    }
    @media (max-width: 840px) { .split-auth { grid-template-columns: 1fr; } }
    .promo-pane {
      background: linear-gradient(160deg, #0b192c 0%, #1d4ed8 60%, #3b4920 100%);
      color: #fff; border-radius: 20px; padding: 26px;
      display: flex; flex-direction: column; justify-content: space-between; min-height: 440px;
    }
    .promo-pane.olive-mode { background: linear-gradient(160deg, #1b2610 0%, #4d5d2b 65%, #0f172a 100%); }
    .promo-img {
      width: 190px; height: 210px; object-fit: cover; border-radius: 16px;
      border: 2px solid rgba(255, 255, 255, 0.35); margin: 14px auto 0; display: block;
    }
    .step-track { height: 5px; background: var(--card2); border-radius: 999px; overflow: hidden; margin-bottom: 14px; }
    .step-fill { height: 100%; background: var(--olive); }

    .secure-player-box {
      position: relative; width: 100%; max-width: 820px; margin: 12px auto 0;
      border-radius: 14px; overflow: hidden; background: #000; border: 1px solid var(--bdr); user-select: none;
    }
    .secure-player-box video, .secure-player-box iframe {
      width: 100%; display: block; height: 440px; max-height: 70vw; border: none;
    }
    .watermark-layer { position: absolute; inset: 0; pointer-events: none; z-index: 5; overflow: hidden; }
    .watermark-tag {
      position: absolute; color: rgba(255, 255, 255, 0.28); font-size: 0.84rem;
      font-weight: 800; transform: rotate(-15deg); white-space: nowrap;
      animation: wmDrift 12s infinite alternate ease-in-out;
    }
    @keyframes wmDrift {
      0% { top: 14%; right: 8%; }
      50% { top: 46%; right: 32%; }
      100% { top: 72%; right: 12%; }
    }
    body.privacy-blur .secure-player-box video,
    body.privacy-blur .secure-player-box iframe { filter: blur(18px); }
    .ticket-img-thumb {
      max-width: 240px; max-height: 170px; border-radius: 10px;
      border: 1px solid var(--bdr); margin-top: 8px; display: block;
    }
    .branch-toggle-grid {
      display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 8px; margin: 10px 0;
    }
    .branch-check-pill {
      display: flex; align-items: center; gap: 6px; padding: 7px 10px;
      border-radius: 10px; background: var(--card); border: 1px solid var(--bdr);
      font-size: 0.84rem; font-weight: 800; cursor: pointer;
    }
    .branch-check-pill input { width: auto; }
  </style>
</head>
<body>
  <div id="arabicBg" aria-hidden="true"></div>
  <div class="page-layer">
    <header class="topbar">
      <div class="brand-box">
        <div class="brand-logo-badge">جخ</div>
        <div>
          <div style="font-weight:900; font-size:1.05rem; color:var(--pri);">نور البيان — أ. محمد يوسف</div>
          <div class="muted" style="font-size:0.78rem; font-weight:700;">اللغة العربية للثانوية الأزهرية (خبرة 20 عاماً)</div>
        </div>
      </div>

      <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
        <button type="button" class="theme-pill" id="themeToggle">☀️ نهار / 🌙 ليل</button>
        <a class="btn btn-out btn-sm" href="/">الرئيسية</a>
        <a class="btn btn-out btn-sm" href="/student">بوابة الطالب</a>
        {% if not student %}
          <a class="btn btn-out btn-sm" href="/admin">لوحة الأدمن</a>
        {% endif %}
      </div>
    </header>

    <!-- رسالة الدعاء: تظهر فقط عند فتح المنصة أو عمل Refresh لمدة 4 ثوانٍ -->
    <div class="inline-dua-banner dua-done" id="inlineDuaBanner">
      <div class="inline-dua-left">
        <img
          class="inline-dua-avatar"
          src="{{ settings.teacher_image }}"
          alt="الأستاذ محمد يوسف"
          onerror="this.style.display='none';"
        />
        <div>
          <div class="inline-dua-text">اللهم فهمني كما فهمت داوود وسليمان</div>
          <div class="inline-dua-sub">دعاء البداية • الأستاذ محمد يوسف — مدرس أول اللغة العربية الأزهرية</div>
        </div>
      </div>
      <button type="button" class="btn btn-out btn-sm" style="color:#fff; border-color:rgba(255,255,255,0.35);" id="hideDuaBtn">إخفاء</button>
    </div>

    {% if global_notice %}
      <div class="global-alert">📢 تنبيه الإدارة: {{ global_notice }}</div>
    {% endif %}

    {% block content %}{% endblock %}
  </div>

  <script>
    if (localStorage.getItem("nb_py_theme") === "dark") document.body.classList.add("dark");
    document.getElementById("themeToggle").addEventListener("click", function () {
      const dark = document.body.classList.toggle("dark");
      localStorage.setItem("nb_py_theme", dark ? "dark" : "light");
    });

    // إظهار الدعاء لمدة 4 ثوانٍ فقط عند فتح المنصة لأول مرة أو عند عمل Refresh
    (function setupDuaOnOpenOrRefresh() {
      const banner = document.getElementById("inlineDuaBanner");
      if (!banner) return;
      const navEntries = performance.getEntriesByType ? performance.getEntriesByType("navigation") : [];
      const navType = navEntries && navEntries.length > 0 ? navEntries[0].type : "navigate";
      const alreadyShownInSession = sessionStorage.getItem("nb_dua_shown") === "1";
      const isRefresh = navType === "reload";

      function hideBanner() { banner.classList.add("dua-done"); }

      if (!alreadyShownInSession || isRefresh) {
        sessionStorage.setItem("nb_dua_shown", "1");
        banner.classList.remove("dua-done");
        const timer = setTimeout(hideBanner, 4000);
        document.getElementById("hideDuaBtn")?.addEventListener("click", function () {
          clearTimeout(timer);
          hideBanner();
        });
      }
    })();

    (function renderAnimatedArabicLetters() {
      const container = document.getElementById("arabicBg");
      const letters = "أبجدهوزحطيكلمنسعفصقرشتثخذضظغى".split("");
      const sides = ["right", "left"];
      for (let i = 0; i < 38; i++) {
        const span = document.createElement("span");
        span.className = "ar-glyph";
        span.textContent = letters[i % letters.length];
        const side = sides[i % 2];
        const horiz = 2 + ((i * 17) % 21);
        const vert = 3 + ((i * 13) % 90);
        const size = 24 + ((i * 7) % 28);
        const dur = 14 + ((i * 3) % 12);
        const delay = -((i * 2.3) % 10);
        const dx = (i % 2 === 0 ? 1 : -1) * (14 + (i % 16));
        const dy = (i % 3 === 0 ? -1 : 1) * (18 + (i % 20));
        span.style[side] = horiz + "%";
        span.style.top = vert + "%";
        span.style.fontSize = size + "px";
        span.style.setProperty("--dur", dur + "s");
        span.style.setProperty("--delay", delay + "s");
        span.style.setProperty("--dx", dx + "px");
        span.style.setProperty("--dy", dy + "px");
        container.appendChild(span);
      }
    })();

    document.addEventListener("contextmenu", function (e) {
      if (e.target.closest(".secure-player-box")) e.preventDefault();
    });
    document.addEventListener("keydown", function (e) {
      if (
        (e.ctrlKey && ["s", "u", "p"].includes(e.key.toLowerCase())) ||
        e.key === "PrintScreen" ||
        (e.ctrlKey && e.shiftKey && ["i", "j", "c"].includes(e.key.toLowerCase()))
      ) {
        if (e.key === "PrintScreen") {
          document.body.classList.add("privacy-blur");
          setTimeout(() => document.body.classList.remove("privacy-blur"), 2500);
        }
        if (document.querySelector(".secure-player-box")) e.preventDefault();
      }
    });
    document.addEventListener("visibilitychange", function () {
      if (document.hidden) {
        document.querySelectorAll(".secure-player-box video").forEach((v) => v.pause());
      }
    });
  </script>
</body>
</html>""",
    encoding="utf-8",
)

(TEMPLATES_DIR / "landing.html").write_text(
    """{% extends "layout.html" %}
{% block content %}
<div class="split-auth">
  <div class="promo-pane">
    <div>
      <span class="pill" style="background:rgba(255,255,255,0.2); color:#fff;">خبرة 20 عاماً في المنهج الأزهري</span>
      <h1 style="font-size:1.7rem; font-weight:900; margin-top:12px;">الأستاذ محمد يوسف</h1>
      <p style="margin-top:8px; font-size:0.95rem; opacity:0.95;">
        مدرس أول اللغة العربية للثانوية الأزهرية (الأول، الثاني، والثالث الثانوي — علمي وأدبي). شرح الفروع السبعة، تفعيل كل فرع بشكل مستقل، أكواد سنتر لمرة واحدة، واجبات إلكترونية، وامتحانات شاملة.
      </p>
    </div>
    <img class="promo-img" src="{{ settings.teacher_image }}" alt="الأستاذ محمد يوسف" onerror="this.style.display='none';" />
  </div>

  <div class="card" style="display:flex; flex-direction:column; justify-content:center; margin-bottom:0;">
    <h2 style="font-size:1.45rem; font-weight:900; margin-bottom:8px;">أهلاً بك في منصة نور البيان ✦ ۝ جخ ۝ ✦</h2>
    <p class="muted" style="margin-bottom:20px;">اختر إنشاء حساب جديد للانضمام، أو سجل دخولك لحسابك الحالي لمتابعة فروع اللغة العربية.</p>
    <div style="display:flex; gap:12px; flex-wrap:wrap;">
      <a class="btn btn-olive" style="flex:1; min-width:170px;" href="/student?tab=register&step=1">ابدأ معنا الآن</a>
      <a class="btn btn-blue" style="flex:1; min-width:170px;" href="/student?tab=login">تسجيل الدخول</a>
    </div>
  </div>
</div>
{% endblock %}""",
    encoding="utf-8",
)

(TEMPLATES_DIR / "student.html").write_text(
    """{% extends "layout.html" %}
{% block content %}
{% if not student %}
  {% if auth_tab == 'login' %}
    <div class="split-auth">
      <div class="promo-pane">
        <div>
          <h2 style="font-size:1.35rem; font-weight:900;">انضم الآن لمجتمع طلاب الثانوية الأزهرية</h2>
          <p style="margin-top:10px; font-size:0.92rem; opacity:0.95;">تعلم اللغة العربية وفروعها السبعة بأسلوب منظم مع أ. محمد يوسف.</p>
        </div>
        <img class="promo-img" src="{{ settings.teacher_image }}" alt="الأستاذ محمد يوسف" onerror="this.style.display='none';" />
      </div>

      <div class="card" style="margin-bottom:0;">
        <h2 style="text-align:center; font-weight:900; margin-bottom:6px;">أهلاً تاني! جاهز للمذاكرة؟</h2>
        <p class="muted" style="text-align:center; font-size:0.88rem; margin-bottom:14px;">ادخل على حسابك برقم الهاتف وكلمة السر، أو أدخل كود السنتر لفتح المنصة فوراً.</p>
        <div style="display:flex; gap:8px; justify-content:center; margin-bottom:16px; border-bottom:1px solid var(--bdr); padding-bottom:10px; flex-wrap:wrap;">
          <a class="btn btn-blue btn-sm" href="/student?tab=login">تسجيل الدخول برقم الهاتف</a>
          <a class="btn btn-olive btn-sm" href="/student?tab=center">دخول بكود السنتر</a>
          <a class="btn btn-out btn-sm" href="/student?tab=register&step=1">إنشاء حساب جديد</a>
        </div>

        {% if error %}<div class="msg-err">{{ error }}</div>{% endif %}
        {% if notice %}<div class="msg-ok">{{ notice }}</div>{% endif %}

        <form method="post" action="/student/login">
          <div class="field"><label>رقم الهاتف</label><input name="phone" type="tel" required placeholder="01xxxxxxxxx" /></div>
          <div class="field"><label>كلمة السر</label><input name="password" type="password" required placeholder="••••••••" /></div>
          <div style="margin-bottom:14px;">
            <a href="/student?tab=forgot" style="font-size:0.86rem; font-weight:800; color:var(--pri);">هل نسيت كلمة السر؟ اضغط هنا</a>
          </div>
          <button type="submit" class="btn btn-blue" style="width:100%;">تسجيل الدخول</button>
        </form>
      </div>
    </div>

  {% elif auth_tab == 'center' %}
    <!-- دخول طالب السنتر بكود السنتر لمرة واحدة لفتح المنصة -->
    <div class="split-auth">
      <div class="promo-pane olive-mode">
        <div>
          <h2 style="font-size:1.35rem; font-weight:900;">دخول طلاب السنتر بكود التفعيل</h2>
          <p style="margin-top:10px; font-size:0.92rem; opacity:0.95;">أدخل بياناتك وكود السنتر المخصص لمرة واحدة ليتم فتح المنصة لك مباشرة.</p>
        </div>
        <img class="promo-img" src="{{ settings.teacher_image }}" alt="الأستاذ محمد يوسف" onerror="this.style.display='none';" />
      </div>

      <div class="card" style="margin-bottom:0;">
        <h2 style="font-weight:900; margin-bottom:8px;">تفعيل المنصة بكود السنتر</h2>
        <p class="muted" style="font-size:0.88rem; margin-bottom:14px;">يُستخدم كود السنتر مرة واحدة فقط لفتح المنصة على حسابك.</p>
        {% if error %}<div class="msg-err">{{ error }}</div>{% endif %}
        {% if notice %}<div class="msg-ok">{{ notice }}</div>{% endif %}

        <form method="post" action="/student/center-login">
          <div class="field"><label>كود السنتر (لمرة واحدة) *</label><input name="center_code" type="text" required placeholder="مثال: CTR-XXXXXX" /></div>
          <div class="field"><label>اسم الطالب *</label><input name="name" type="text" required placeholder="الاسم الثلاثي" /></div>
          <div class="field"><label>رقم هاتف الطالب *</label><input name="phone" type="tel" required placeholder="01xxxxxxxxx" /></div>
          <div class="grid2">
            <div class="field">
              <label>الصف الدراسي *</label>
              <select name="grade">
                {% for g in grades %}<option value="{{ g }}">{{ g }}</option>{% endfor %}
              </select>
            </div>
            <div class="field">
              <label>الشعبة *</label>
              <select name="track">
                {% for tr in tracks %}<option value="{{ tr }}">{{ tr }}</option>{% endfor %}
              </select>
            </div>
          </div>
          <button type="submit" class="btn btn-olive" style="width:100%;">فتح المنصة بكود السنتر</button>
        </form>

        <div style="margin-top:14px; text-align:center; font-size:0.86rem;">
          <a href="/student?tab=login" style="color:var(--pri); font-weight:800;">العودة لتسجيل الدخول العادي</a>
        </div>
      </div>
    </div>

  {% elif auth_tab == 'forgot' %}
    <div class="card" style="max-width:520px; margin:24px auto;">
      <h2 style="font-weight:900; margin-bottom:8px;">استعادة كلمة السر</h2>
      <p class="muted" style="font-size:0.88rem; margin-bottom:14px;">أدخل رقم هاتف الطالب ورقم هاتف ولي الأمر لتعيين كلمة سر جديدة.</p>
      {% if error %}<div class="msg-err">{{ error }}</div>{% endif %}
      {% if notice %}<div class="msg-ok">{{ notice }}</div>{% endif %}
      <form method="post" action="/student/reset-password">
        <div class="field"><label>رقم هاتف الطالب *</label><input name="phone" type="tel" required placeholder="01xxxxxxxxx" /></div>
        <div class="field"><label>رقم هاتف ولي الأمر *</label><input name="parent_phone" type="tel" required placeholder="01xxxxxxxxx" /></div>
        <div class="field"><label>كلمة السر الجديدة *</label><input name="new_password" type="password" required minlength="4" /></div>
        <button type="submit" class="btn btn-olive" style="width:100%;">تعيين كلمة السر الجديدة</button>
      </form>
      <div style="margin-top:12px; text-align:center;">
        <a href="/student?tab=login" style="font-weight:800; color:var(--pri); font-size:0.88rem;">العودة لتسجيل الدخول</a>
      </div>
    </div>

  {% else %}
    <div class="split-auth">
      <div class="promo-pane olive-mode">
        <div>
          <h2 style="font-size:1.35rem; font-weight:900;">طلب إنشاء حساب طالب جديد</h2>
          <p style="margin-top:10px; font-size:0.92rem; opacity:0.95;">أدخل بياناتك بدقة وسيتم ربطك بمنهج صفك وشعبتك تلقائياً.</p>
        </div>
        <img class="promo-img" src="{{ settings.teacher_image }}" alt="الأستاذ محمد يوسف" onerror="this.style.display='none';" />
      </div>

      <div class="card" style="margin-bottom:0;">
        <div style="display:flex; justify-content:space-between; font-size:0.84rem; font-weight:800; color:var(--olive);">
          <span>الخطوة {{ 'الثانية' if step == 2 else 'الأولى' }}</span>
          <span>{{ '70%' if step == 2 else '35%' }}</span>
        </div>
        <div class="step-track">
          <div class="step-fill" style="width:{{ '70%' if step == 2 else '35%' }};"></div>
        </div>

        {% if error %}<div class="msg-err">{{ error }}</div>{% endif %}

        {% if step != 2 %}
          <form method="get" action="/student">
            <input type="hidden" name="tab" value="register" />
            <input type="hidden" name="step" value="2" />
            <div class="grid2">
              <div class="field"><label>الاسم الأول *</label><input name="first_name" type="text" value="{{ draft.first_name }}" required /></div>
              <div class="field"><label>الاسم الثاني *</label><input name="second_name" type="text" value="{{ draft.second_name }}" required /></div>
              <div class="field"><label>الاسم الثالث *</label><input name="third_name" type="text" value="{{ draft.third_name }}" required /></div>
              <div class="field"><label>رقم هاتف الطالب *</label><input name="phone" type="tel" value="{{ draft.phone }}" required placeholder="01xxxxxxxxx" /></div>
            </div>
            <button type="submit" class="btn btn-blue" style="width:100%;">التالي</button>
          </form>
        {% else %}
          <form method="post" action="/student/register">
            <input type="hidden" name="full_name" value="{{ (draft.first_name ~ ' ' ~ draft.second_name ~ ' ' ~ draft.third_name).strip() }}" />
            <input type="hidden" name="phone" value="{{ draft.phone }}" />
            <div class="field">
              <label>الصف الدراسي *</label>
              <select name="grade">
                {% for g in grades %}<option value="{{ g }}">{{ g }}</option>{% endfor %}
              </select>
            </div>
            <div class="field">
              <label>الشعبة *</label>
              <select name="track">
                {% for tr in tracks %}<option value="{{ tr }}">{{ tr }}</option>{% endfor %}
              </select>
            </div>
            <div class="field"><label>رقم هاتف ولي الأمر *</label><input name="parent_phone" type="tel" required placeholder="01xxxxxxxxx" /></div>
            <div class="grid2">
              <div class="field"><label>المحافظة *</label><input name="governorate" type="text" required placeholder="مثال: الشرقية" /></div>
              <div class="field"><label>كلمة السر *</label><input name="password" type="password" required minlength="4" /></div>
            </div>
            <div style="display:flex; gap:10px; margin-top:8px;">
              <a class="btn btn-out" style="background:#eab308; color:#0b192c; border:none;" href="/student?tab=register&step=1">السابق</a>
              <button type="submit" class="btn btn-olive" style="flex:1;">إنشاء الحساب</button>
            </div>
          </form>
        {% endif %}

        <div style="margin-top:14px; text-align:center; font-size:0.86rem;">
          يوجد لديك حساب بالفعل؟ <a href="/student?tab=login" style="color:var(--pri); font-weight:800;">ادخل إلى حسابك الآن !</a>
        </div>
      </div>
    </div>
  {% endif %}

{% else %}
  <div class="dash-shell" id="studentShell">
    <div>
      {% if notice %}<div class="msg-ok">{{ notice }}</div>{% endif %}
      {% if error %}<div class="msg-err">{{ error }}</div>{% endif %}

      {% if section == 'home' %}
        <div class="kpi-grid">
          <div class="kpi-card olive-kpi">
            <div>
              <div class="kpi-num">{{ completed_count }}</div>
              <div class="kpi-lbl">محاضرات مكتملة</div>
            </div>
            <div class="kpi-icon-box">✓</div>
          </div>
          <div class="kpi-card">
            <div>
              <div class="kpi-num">{{ total_lectures }}</div>
              <div class="kpi-lbl">محاضرات منهجك الحالية</div>
            </div>
            <div class="kpi-icon-box">💡</div>
          </div>
          <div class="kpi-card olive-kpi">
            <div>
              <div class="kpi-num">{{ active_branches_list|length }} / {{ branches|length }}</div>
              <div class="kpi-lbl">الفروع المفعلة لك</div>
            </div>
            <div class="kpi-icon-box">📚</div>
          </div>
        </div>

        <div class="progress-layout">
          <div class="progress-frame">
            <div style="font-weight:900;">مستوى تقدمك</div>
            <div class="teacher-color-meter" title="تتلون صورة الأستاذ محمد يوسف كلما شاهدت وأتممت محاضرات أكثر">
              <img class="bw-layer" src="{{ settings.teacher_image }}" alt="محمد يوسف" onerror="this.style.display='none';" />
              <div class="color-reveal" style="clip-path: inset({{ 100 - perf_pct }}% 0 0 0);">
                <img src="{{ settings.teacher_image }}" alt="محمد يوسف ملون" onerror="this.style.display='none';" />
              </div>
            </div>
            <div style="font-size:1.3rem; font-weight:900; color:var(--olive);">% {{ perf_pct }}</div>
            <div class="prog-bar-bg">
              <div class="prog-bar-fill" style="width:{{ perf_pct }}%;"></div>
            </div>
            <div class="muted" style="font-size:0.78rem;">تزيد الألوان بإتمام المحاضرات وتقل إن نقصت نسبة الإنجاز</div>
          </div>

          <div class="card" style="margin-bottom:0;">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:10px;">
              <div>
                <h2 style="font-size:1.15rem; font-weight:900;">أهلاً بك يا {{ student.name }}</h2>
                <div class="muted" style="font-size:0.84rem;">{{ student.grade }} • شعبة {{ student.track }}</div>
              </div>
              <a class="btn btn-olive btn-sm" href="/student?section=account&sub=billing">دفع الفرع / كود التفعيل</a>
            </div>
            <p class="muted" style="font-size:0.9rem; margin-bottom:10px;">
              <strong>الفروع المفعلة حالياً:</strong>
              {% if active_branches_list %}
                {{ active_branches_list | join(' — ') }}
              {% else %}
                لم يتم تفعيل أي فرع بعد؛ اختر «دفع الفرع» لتحويل اشتراك الفرع المطلوب مباشرة على واتساب 01066329782.
              {% endif %}
            </p>
            <div style="display:flex; gap:8px; flex-wrap:wrap;">
              {% for br in branches %}
                <a class="btn btn-out btn-sm" href="/student?section=courses&sub=branch&branch={{ br | urlencode }}">{{ br }}</a>
              {% endfor %}
            </div>
          </div>
        </div>

        <div class="card">
          <h3 style="font-weight:900; margin-bottom:12px;">محاضراتك الحالية</h3>
          {% if recent_lectures %}
            <div class="course-grid">
              {% for lec in recent_lectures %}
                <div class="course-card">
                  <div class="course-banner">
                    <div>
                      <span class="pill" style="background:rgba(255,255,255,0.2); color:#fff;">{{ lec.branch }}</span>
                      <div style="font-weight:900; font-size:0.92rem; margin-top:6px;">{{ student.grade }}</div>
                    </div>
                    <img class="book-thumb" src="{{ branch_photos.get(lec.branch, settings.teacher_image) }}" alt="كتاب {{ lec.branch }}" onerror="this.style.display='none';" />
                  </div>
                  <div class="course-body">
                    <div class="course-title">{{ lec.title }}</div>
                    <div class="muted" style="font-size:0.82rem; margin-bottom:10px;">شعبة: {{ lec.track }}</div>
                    <a class="btn btn-blue btn-sm" style="width:100%;" href="/lecture/{{ lec.id }}">الدخول للمحاضرة</a>
                  </div>
                </div>
              {% endfor %}
            </div>
          {% else %}
            <p class="muted">لا توجد محاضرات منشورة لصفك وشعبتك بعد.</p>
          {% endif %}
        </div>

      {% elif section == 'courses' %}
        <div class="branch-hero-banner">
          <div>
            <span class="pill" style="background:rgba(255,255,255,0.18); color:#fff;">
              {{ selected_branch if sub == 'branch' else 'منهج ' ~ student.grade }}
            </span>
            <h2 style="font-size:1.3rem; font-weight:900; margin-top:6px;">
              {% if sub == 'branch' %}فرع {{ selected_branch }} — الأستاذ محمد يوسف
              {% elif sub == 'exams' %}الامتحانات الشاملة — {{ student.grade }}
              {% else %}كورساتي ومحاضراتي — {{ student.grade }}
              {% endif %}
            </h2>
            <div style="font-size:0.86rem; opacity:0.9;">شعبة: {{ student.track }}</div>
          </div>
          <div class="branch-book-card">
            <img src="{{ current_branch_photo }}" alt="الأستاذ محمد يوسف وماسك كتاب الفرع" onerror="this.style.display='none';" />
            <div>
              <div style="font-weight:900; font-size:0.9rem;">أ. محمد يوسف</div>
              <div style="font-size:0.8rem; opacity:0.9;">كتاب {{ selected_branch if sub == 'branch' else 'اللغة العربية' }}</div>
            </div>
          </div>
        </div>

        <div class="card">
          {% if sub == 'exams' %}
            {% if exams %}
              {% for ex in exams %}
                <div class="row">
                  <div><strong>{{ ex.title }}</strong> <span class="muted">({{ ex.questions|length }} سؤال)</span></div>
                  {% if active_branches_list %}
                    <a class="btn btn-olive btn-sm" href="/exam/{{ ex.id }}">بدء الامتحان</a>
                  {% else %}
                    <a class="btn btn-blue btn-sm" href="/student?section=account&sub=billing">دفع الفرع</a>
                  {% endif %}
                </div>
              {% endfor %}
            {% else %}
              <p class="muted">لا توجد امتحانات شاملة متاحة حالياً.</p>
            {% endif %}
          {% else %}
            {% set branch_is_open = (sub != 'branch') or (selected_branch in active_branches_list) %}
            {% if not branch_is_open %}
              <div class="msg-err">
                فرع «{{ selected_branch }}» غير مفعل على حسابك حالياً.
              </div>
              <div style="display:flex; gap:10px; flex-wrap:wrap; margin-bottom:14px;">
                <a
                  class="btn btn-olive"
                  target="_blank"
                  rel="noopener"
                  href="https://wa.me/{{ settings.admin_whatsapp }}?text={{ ('عاوز ادفع اشتراك فرع ' ~ selected_branch) | urlencode }}"
                >دفع الفرع ({{ selected_branch }}) عبر واتساب 01066329782</a>
                <a class="btn btn-blue" href="/student?section=account&sub=billing">إدخال كود تفعيل الفرع</a>
              </div>
            {% endif %}

            {% if lectures %}
              <div class="course-grid">
                {% for lec in lectures %}
                  <div class="course-card">
                    <div class="course-banner">
                      <div>
                        <span class="pill" style="background:rgba(255,255,255,0.2); color:#fff;">{{ lec.branch }}</span>
                        <div style="font-weight:900; font-size:0.9rem; margin-top:6px;">{{ lec.track }}</div>
                      </div>
                      <img class="book-thumb" src="{{ branch_photos.get(lec.branch, settings.teacher_image) }}" alt="كتاب {{ lec.branch }}" onerror="this.style.display='none';" />
                    </div>
                    <div class="course-body">
                      <div class="course-title">{{ lec.title }}</div>
                      {% if lec.id in completed_ids %}
                        <div style="margin-bottom:8px;"><span class="pill pill-ok">مكتملة ✓</span></div>
                      {% endif %}
                      {% if lec.branch in active_branches_list %}
                        <a class="btn btn-olive btn-sm" style="width:100%;" href="/lecture/{{ lec.id }}">الدخول للمحاضرة</a>
                      {% else %}
                        <a
                          class="btn btn-blue btn-sm"
                          style="width:100%;"
                          target="_blank"
                          rel="noopener"
                          href="https://wa.me/{{ settings.admin_whatsapp }}?text={{ ('عاوز ادفع اشتراك فرع ' ~ lec.branch) | urlencode }}"
                        >دفع الفرع ({{ lec.branch }})</a>
                      {% endif %}
                    </div>
                  </div>
                {% endfor %}
              </div>
            {% else %}
              <p class="muted">لا توجد محاضرات منشورة في هذا القسم حالياً.</p>
            {% endif %}
          {% endif %}
        </div>

      {% elif section == 'forum' %}
        <div class="card">
          <h2 style="font-size:1.15rem; font-weight:900; margin-bottom:12px;">المنتدى والدعم العلمي المباشر (مع إرفاق صورة)</h2>
          <form method="post" action="/student/support" enctype="multipart/form-data">
            <div class="field">
              <label>فرع اللغة العربية</label>
              <select name="branch">
                {% for br in branches %}<option value="{{ br }}">{{ br }}</option>{% endfor %}
              </select>
            </div>
            <div class="field"><label>اكتب سؤالك العلمي *</label><textarea name="question" required placeholder="اكتب سؤالك هنا..."></textarea></div>
            <div class="field">
              <label>إرفاق صورة للسؤال (اختياري)</label>
              <input name="question_image" type="file" accept=".png,.jpg,.jpeg,.webp,.gif,image/*" />
            </div>
            <button type="submit" class="btn btn-blue">إرسال السؤال للأستاذ</button>
          </form>
        </div>

        <div class="card">
          <h3 style="font-weight:900; margin-bottom:10px;">أسئلتي وردود الأستاذ</h3>
          {% if tickets %}
            {% for t in tickets %}
              <div class="row" style="display:block;">
                <div><strong>{{ t.branch }}:</strong> {{ t.question }}</div>
                {% if t.image_filename %}
                  <img class="ticket-img-thumb" src="/ticket-images/{{ t.image_filename }}" alt="صورة السؤال" />
                {% endif %}
                {% if t.reply %}
                  <div style="margin-top:8px;"><span class="pill pill-ok">رد الأستاذ: {{ t.reply }}</span></div>
                {% else %}
                  <div style="margin-top:8px;"><span class="pill pill-warn">بانتظار رد الأستاذ</span></div>
                {% endif %}
              </div>
            {% endfor %}
          {% else %}
            <p class="muted">لم ترسل أسئلة بعد.</p>
          {% endif %}
        </div>

      {% elif section == 'account' %}
        {% if sub == 'billing' %}
          <div class="card">
            <h2 style="font-size:1.15rem; font-weight:900; margin-bottom:10px;">دفع الفرع وتفعيل الاشتراك</h2>
            <p class="muted" style="font-size:0.9rem; margin-bottom:12px;">
              اختر الفرع ثم اضغط «دفع الفرع» لتحويل اشتراكه مباشرة على واتساب رقم <strong>01066329782</strong> برسالة جاهزة، ثم أدخل كود الفرع لمرة واحدة.
            </p>

            <div class="field">
              <label>اختر الفرع للضغط على «دفع الفرع»:</label>
              <select id="payBranchSelect">
                {% for br in branches %}
                  <option value="{{ br }}">{{ br }} {{ '(مفعل)' if br in active_branches_list else '(غير مفعل)' }}</option>
                {% endfor %}
              </select>
            </div>
            <a
              id="payBranchWaLink"
              class="btn btn-olive"
              style="width:100%;"
              target="_blank"
              rel="noopener"
              href="https://wa.me/{{ settings.admin_whatsapp }}?text={{ 'عاوز ادفع اشتراك فرع النحو' | urlencode }}"
            >دفع الفرع — إرسال طلب على واتساب (01066329782)</a>

            <form method="post" action="/student/redeem-code" style="margin-top:18px; padding-top:16px; border-top:1px solid var(--bdr);">
              <div class="field"><label>تفعيل الفرع بكود لمرة واحدة</label><input name="code" type="text" required placeholder="مثال: BRN-XXXXXX" /></div>
              <button type="submit" class="btn btn-blue">تفعيل الفرع بالكود</button>
            </form>
          </div>

          <script>
            const selBr = document.getElementById("payBranchSelect");
            const waLink = document.getElementById("payBranchWaLink");
            const waNum = "{{ settings.admin_whatsapp }}";
            function syncWaLink() {
              const b = selBr ? selBr.value : "النحو";
              waLink.href = "https://wa.me/" + waNum + "?text=" + encodeURIComponent("عاوز ادفع اشتراك فرع " + b);
            }
            selBr?.addEventListener("change", syncWaLink);
            syncWaLink();
          </script>

        {% elif sub == 'security' %}
          <div class="card">
            <h2 style="font-size:1.15rem; font-weight:900; margin-bottom:12px;">الأمان وتغيير كلمة السر</h2>
            <form method="post" action="/student/change-password" style="max-width:440px;">
              <div class="field"><label>كلمة السر الحالية</label><input name="old_password" type="password" required /></div>
              <div class="field"><label>كلمة السر الجديدة</label><input name="new_password" type="password" required minlength="4" /></div>
              <button type="submit" class="btn btn-blue">تحديث كلمة السر</button>
            </form>
          </div>

        {% else %}
          <div class="card">
            <h2 style="font-size:1.15rem; font-weight:900; margin-bottom:12px;">الملف الشخصي</h2>
            <div class="row"><div><strong>الاسم:</strong> {{ student.name }}</div></div>
            <div class="row"><div><strong>رقم الهاتف:</strong> {{ student.phone }}</div></div>
            <div class="row"><div><strong>رقم ولي الأمر:</strong> {{ student.parent_phone }}</div></div>
            <div class="row"><div><strong>الصف والشعبة:</strong> {{ student.grade }} — {{ student.track }}</div></div>
            <div class="row"><div><strong>الفروع المفعلة:</strong> {{ active_branches_list | join('، ') if active_branches_list else 'لا يوجد' }}</div></div>
          </div>
        {% endif %}
      {% endif %}
    </div>

    <aside class="right-drawer">
      <div class="drawer-top">
        <span class="drawer-title" style="font-weight:900; font-size:0.92rem;">القائمة</span>
        <button type="button" class="collapse-btn" id="collapseDrawerBtn" title="تصغير النافذة">❯</button>
      </div>

      <a class="nav-item-link {{ 'active' if section == 'home' else '' }}" href="/student?section=home">
        <span>🏠</span><span class="nav-label">الرئيسية</span>
      </a>

      <a class="nav-item-link {{ 'active' if section == 'courses' else '' }}" href="/student?section=courses&sub=mine">
        <span>📚</span><span class="nav-label">فروع اللغة العربية</span>
      </a>
      <div class="sub-nav">
        <a class="sub-link {{ 'active' if section == 'courses' and sub == 'mine' else '' }}" href="/student?section=courses&sub=mine">كورساتي</a>
        {% for br in branches %}
          <a class="sub-link {{ 'active' if section == 'courses' and sub == 'branch' and selected_branch == br else '' }}" href="/student?section=courses&sub=branch&branch={{ br | urlencode }}">
            {{ br }} {{ '✓' if br in active_branches_list else '🔒' }}
          </a>
        {% endfor %}
        <a class="sub-link {{ 'active' if section == 'courses' and sub == 'exams' else '' }}" href="/student?section=courses&sub=exams">الامتحانات الشاملة</a>
      </div>

      <a class="nav-item-link {{ 'active' if section == 'forum' else '' }}" href="/student?section=forum">
        <span>💬</span><span class="nav-label">المنتدى</span>
      </a>

      <a class="nav-item-link {{ 'active' if section == 'account' else '' }}" href="/student?section=account&sub=profile">
        <span>👤</span><span class="nav-label">حسابي</span>
      </a>
      <div class="sub-nav">
        <a class="sub-link {{ 'active' if section == 'account' and sub == 'profile' else '' }}" href="/student?section=account&sub=profile">الملف الشخصي</a>
        <a class="sub-link {{ 'active' if section == 'account' and sub == 'billing' else '' }}" href="/student?section=account&sub=billing">دفع الفرع والأكواد</a>
        <a class="sub-link {{ 'active' if section == 'account' and sub == 'security' else '' }}" href="/student?section=account&sub=security">الأمان وكلمة السر</a>
      </div>

      <div style="margin-top:12px; padding-top:10px; border-top:1px solid var(--bdr);">
        <a class="btn btn-red btn-sm" style="width:100%;" href="/student/logout"><span class="nav-label">تسجيل الخروج</span><span>⎋</span></a>
      </div>
    </aside>
  </div>

  <script>
    document.getElementById("collapseDrawerBtn")?.addEventListener("click", function () {
      const shell = document.getElementById("studentShell");
      shell.classList.toggle("collapsed");
      this.textContent = shell.classList.contains("collapsed") ? "❮" : "❯";
    });
  </script>
{% endif %}
{% endblock %}""",
    encoding="utf-8",
)

(TEMPLATES_DIR / "lecture.html").write_text(
    """{% extends "layout.html" %}
{% block content %}
<div class="dash-shell" style="grid-template-columns:1fr;">
  <div class="card">
    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
      <div>
        <h2 style="font-size:1.25rem; font-weight:900;">{{ lecture.title }}</h2>
        <div class="muted">{{ lecture.branch }} • {{ lecture.grade }} • {{ lecture.track }}</div>
      </div>
      <a class="btn btn-out btn-sm" href="/student?section=courses&sub=branch&branch={{ lecture.branch | urlencode }}">العودة لفرع {{ lecture.branch }}</a>
    </div>
  </div>

  {% if lecture.branch not in active_branches_list %}
    <div class="card">
      <div class="msg-err">فرع «{{ lecture.branch }}» غير مفعل على حسابك.</div>
      <a
        class="btn btn-olive"
        target="_blank"
        rel="noopener"
        href="https://wa.me/{{ settings.admin_whatsapp }}?text={{ ('عاوز ادفع اشتراك فرع ' ~ lecture.branch) | urlencode }}"
      >دفع الفرع ({{ lecture.branch }}) عبر واتساب 01066329782</a>
    </div>
  {% else %}
    <div class="card">
      <h3 style="font-weight:900; margin-bottom:10px;">1. مشغل الفيديو المحمي</h3>
      <div class="secure-player-box">
        <div class="watermark-layer">
          <div class="watermark-tag">{{ student.name }} • {{ student.phone }}</div>
        </div>
        {% if lecture.youtube_id %}
          <iframe
            src="https://www.youtube-nocookie.com/embed/{{ lecture.youtube_id }}?rel=0&modestbranding=1"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowfullscreen
          ></iframe>
        {% elif lecture.video_url %}
          <video controls controlsList="nodownload noplaybackrate" disablePictureInPicture preload="metadata" src="{{ lecture.video_url }}"></video>
        {% else %}
          <video controls controlsList="nodownload noplaybackrate" disablePictureInPicture preload="metadata" src="/video/{{ lecture.id }}"></video>
        {% endif %}
      </div>
    </div>

    <div class="card">
      <h3 style="font-weight:900; margin-bottom:10px;">2. الواجب الإلكتروني للمحاضرة (5 أسئلة)</h3>
      {% if quiz_result %}
        <div class="msg-ok">تم تصحيح الواجب فوراً: درجتك {{ quiz_result.score }} من {{ quiz_result.total }}.</div>
      {% endif %}
      <form method="post" action="/lecture/{{ lecture.id }}/quiz">
        {% for q in lecture.quiz %}
          <div class="row" style="display:block;">
            <div style="font-weight:800; margin-bottom:8px;">س{{ loop.index }}: {{ q.question }}</div>
            {% for opt in q.options %}
              <label style="display:flex; align-items:center; gap:8px; font-weight:600; margin-bottom:5px; cursor:pointer;">
                <input type="radio" name="q_{{ loop.index0 }}" value="{{ opt }}" style="width:auto;" required />
                <span>{{ opt }}</span>
              </label>
            {% endfor %}
          </div>
        {% endfor %}
        <button type="submit" class="btn btn-olive" style="margin-top:12px;">تسليم الواجب ومعرفة النتيجة</button>
      </form>
    </div>

    <div class="card">
      <h3 style="font-weight:900; margin-bottom:10px;">3. نموذج إجابات الواجب الإلكتروني</h3>
      {% if lecture.answer_key_url %}
        <a class="btn btn-blue btn-sm" href="{{ lecture.answer_key_url }}" target="_blank" rel="noopener">فتح نموذج الإجابات</a>
      {% else %}
        {% for q in lecture.quiz %}
          <div class="row"><div>س{{ loop.index }}: {{ q.question }}</div><span class="pill pill-ok">الإجابة: {{ q.answer }}</span></div>
        {% endfor %}
      {% endif %}
    </div>

    <div class="card">
      <h3 style="font-weight:900; margin-bottom:10px;">4. ملف المذكرة / السبورة (PDF)</h3>
      {% if lecture.pdf_url %}
        <a class="btn btn-olive btn-sm" href="{{ lecture.pdf_url }}" target="_blank" rel="noopener">تحميل / مراجعة ملف المذكرة</a>
      {% else %}
        <p class="muted">لم يتم إرفاق ملف PDF لهذه المحاضرة.</p>
      {% endif %}
    </div>
  {% endif %}
</div>
{% endblock %}""",
    encoding="utf-8",
)

(TEMPLATES_DIR / "exam.html").write_text(
    """{% extends "layout.html" %}
{% block content %}
<div class="dash-shell" style="grid-template-columns:1fr;">
  <div class="card">
    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
      <div>
        <h2 style="font-size:1.25rem; font-weight:900;">{{ exam.title }}</h2>
        <div class="muted">{{ exam.grade }} • {{ exam.track }} • عدد الأسئلة: {{ exam.questions|length }}</div>
      </div>
      <a class="btn btn-out btn-sm" href="/student?section=courses&sub=exams">العودة للامتحانات</a>
    </div>
  </div>

  {% if exam_result %}
    <div class="card"><div class="msg-ok">نتيجة الامتحان الشامل: {{ exam_result.score }} من {{ exam_result.total }}.</div></div>
  {% endif %}

  <div class="card">
    <form method="post" action="/exam/{{ exam.id }}/submit">
      {% for q in exam.questions %}
        <div class="row" style="display:block;">
          <div style="font-weight:800; margin-bottom:8px;">{{ loop.index }}. {{ q.question }}</div>
          {% for opt in q.options %}
            <label style="display:flex; align-items:center; gap:8px; font-weight:600; margin-bottom:5px; cursor:pointer;">
              <input type="radio" name="q_{{ loop.index0 }}" value="{{ opt }}" style="width:auto;" required />
              <span>{{ opt }}</span>
            </label>
          {% endfor %}
        </div>
      {% endfor %}
      <button type="submit" class="btn btn-blue" style="margin-top:14px;">إنهاء وتسليم الامتحان</button>
    </form>
  </div>
</div>
{% endblock %}""",
    encoding="utf-8",
)

(TEMPLATES_DIR / "admin.html").write_text(
    """{% extends "layout.html" %}
{% block content %}
{% if not is_admin %}
<div class="card" style="max-width:450px; margin:24px auto;">
  <h2 style="font-weight:900; margin-bottom:12px;">دخول لوحة تحكم الأدمن</h2>
  {% if error %}<div class="msg-err">{{ error }}</div>{% endif %}
  <form method="post" action="/admin/login">
    <div class="field"><label>البريد الإلكتروني</label><input name="email" type="email" value="{{ settings.admin_email }}" required /></div>
    <div class="field"><label>كلمة المرور</label><input name="password" type="password" required /></div>
    <button type="submit" class="btn btn-blue" style="width:100%;">دخول اللوحة</button>
  </form>
</div>
{% else %}
<div class="dash-shell">
  <div>
    {% if notice %}<div class="msg-ok">{{ notice }}</div>{% endif %}
    {% if error %}<div class="msg-err">{{ error }}</div>{% endif %}

    <section id="tab-students" class="card admin-tab">
      <h2 style="font-size:1.15rem; font-weight:900; margin-bottom:12px;">1. طلاب الجخ وتفعيل كل فرع لوحده ({{ students|length }})</h2>
      <div class="grid3">
        <div class="field"><label>بحث فوري بالاسم</label><input id="stuSearchName" type="text" placeholder="اكتب اسم الطالب..." /></div>
        <div class="field">
          <label>فلترة بالصف</label>
          <select id="stuFilterGrade">
            <option value="">كل الصفوف</option>
            {% for g in grades %}<option value="{{ g }}">{{ g }}</option>{% endfor %}
          </select>
        </div>
        <div class="field">
          <label>فلترة بالشعبة</label>
          <select id="stuFilterTrack">
            <option value="">كل الشعب</option>
            {% for tr in tracks %}<option value="{{ tr }}">{{ tr }}</option>{% endfor %}
          </select>
        </div>
      </div>

      {% for s in students %}
        <div class="row stu-item" style="display:block;" data-name="{{ s.name }}" data-grade="{{ s.grade }}" data-track="{{ s.track }}">
          <div style="display:flex; justify-content:space-between; align-items:center; gap:10px; flex-wrap:wrap;">
            <div>
              <strong>{{ s.name }}</strong>
              <span class="pill pill-ok">نسبة التلوين: {{ s.perf_pct }}%</span>
              <div class="muted" style="font-size:0.84rem;">
                طالب: {{ s.phone }} • ولي الأمر: {{ s.parent_phone }} • {{ s.grade }} ({{ s.track }}) • كلمة السر: {{ s.password }}
              </div>
            </div>
            <form method="post" action="/admin/students/delete" style="margin:0;">
              <input type="hidden" name="phone" value="{{ s.phone }}" />
              <button type="submit" class="btn btn-red btn-sm">حذف نهائي</button>
            </form>
          </div>

          <form method="post" action="/admin/students/set-branches" style="margin-top:10px;">
            <input type="hidden" name="phone" value="{{ s.phone }}" />
            <div class="branch-toggle-grid">
              {% for br in branches %}
                <label class="branch-check-pill">
                  <input type="checkbox" name="branches" value="{{ br }}" {{ 'checked' if br in s.active_branches else '' }} />
                  <span>{{ br }}</span>
                </label>
              {% endfor %}
            </div>
            <button type="submit" class="btn btn-olive btn-sm">حفظ تفعيل الفروع للطالب</button>
          </form>
        </div>
      {% endfor %}
    </section>

    <section id="tab-subscribers" class="card admin-tab" style="display:none;">
      <h2 style="font-size:1.15rem; font-weight:900; margin-bottom:12px;">2. الطلاب المشتركين ونسبة إنجازهم ({{ subscribers|length }})</h2>
      {% for sub in subscribers %}
        <div class="row">
          <div>
            <strong>{{ sub.name }}</strong> <span class="muted">({{ sub.grade }} • {{ sub.track }})</span>
            <div class="muted" style="font-size:0.84rem;">
              الفروع المفعلة: {{ sub.active_branches | join('، ') }} • المحاضرات: {{ sub.completed_count }} / {{ sub.total_lectures }} • نسبة الأداء: {{ sub.perf_pct }}%
            </div>
          </div>
          <span class="pill pill-ok">{{ sub.perf_pct }}%</span>
        </div>
      {% endfor %}
    </section>

    <section id="tab-lectures" class="card admin-tab" style="display:none;">
      <h2 style="font-size:1.15rem; font-weight:900; margin-bottom:12px;">3. إضافة محاضرات (ملف فيديو أو رابط فيديو محمي + كويز 5 أسئلة)</h2>
      <form method="post" action="/admin/lectures/add" enctype="multipart/form-data">
        <div class="grid2">
          <div class="field"><label>اسم المحاضرة *</label><input name="title" type="text" required /></div>
          <div class="field">
            <label>الفرع *</label>
            <select name="branch">
              {% for br in branches %}<option value="{{ br }}">{{ br }}</option>{% endfor %}
            </select>
          </div>
          <div class="field">
            <label>الصف الدراسي *</label>
            <select name="grade">
              {% for g in grades %}<option value="{{ g }}">{{ g }}</option>{% endfor %}
            </select>
          </div>
          <div class="field">
            <label>الشعبة *</label>
            <select name="track">
              <option value="علمي وأدبي معاً">علمي وأدبي معاً</option>
              <option value="علمي">علمي فقط</option>
              <option value="أدبي">أدبي فقط</option>
            </select>
          </div>
        </div>
        <div class="grid2">
          <div class="field">
            <label>ملف الفيديو من جهازك (اختياري إذا وضعت رابط فيديو)</label>
            <input name="video_file" type="file" accept=".mp4,.webm,.ogg,.mov,.m4v,video/*" />
          </div>
          <div class="field">
            <label>أو رابط فيديو لتشغيله كفيديو محمي داخل المنصة</label>
            <input name="video_url" type="url" placeholder="https://... (رابط فيديو مباشر أو يوتيوب)" />
          </div>
        </div>
        <div class="grid2">
          <div class="field"><label>رابط المذكرة / السبورة (PDF)</label><input name="pdf_url" type="url" placeholder="https://..." /></div>
          <div class="field"><label>رابط ملف الإجابات</label><input name="answer_key_url" type="url" placeholder="https://..." /></div>
        </div>

        {% for i in range(1, 6) %}
          <div class="row" style="display:block;">
            <div class="field"><label>السؤال {{ i }} *</label><input name="q_{{ i }}_text" type="text" required /></div>
            <div class="grid2">
              <div class="field"><label>الاختيار 1 *</label><input name="q_{{ i }}_o1" type="text" required /></div>
              <div class="field"><label>الاختيار 2 *</label><input name="q_{{ i }}_o2" type="text" required /></div>
              <div class="field"><label>الاختيار 3 *</label><input name="q_{{ i }}_o3" type="text" required /></div>
              <div class="field"><label>الاختيار 4 *</label><input name="q_{{ i }}_o4" type="text" required /></div>
            </div>
            <div class="field">
              <label>الإجابة الصحيحة (1 إلى 4) *</label>
              <select name="q_{{ i }}_correct">
                <option value="1">الاختيار 1</option>
                <option value="2">الاختيار 2</option>
                <option value="3">الاختيار 3</option>
                <option value="4">الاختيار 4</option>
              </select>
            </div>
          </div>
        {% endfor %}
        <button type="submit" class="btn btn-olive" style="margin-top:12px;">نشر المحاضرة</button>
      </form>

      {% for lec in lectures %}
        <div class="row">
          <div>
            <strong>{{ lec.title }}</strong> <span class="muted">({{ lec.branch }} • {{ lec.grade }} • {{ lec.track }})</span>
            {% if lec.video_url %}<span class="pill pill-ok">رابط محمي</span>{% endif %}
          </div>
          <form method="post" action="/admin/lectures/delete" style="margin:0;">
            <input type="hidden" name="lecture_id" value="{{ lec.id }}" />
            <button type="submit" class="btn btn-red btn-sm">حذف</button>
          </form>
        </div>
      {% endfor %}
    </section>

    <section id="tab-exams" class="card admin-tab" style="display:none;">
      <h2 style="font-size:1.15rem; font-weight:900; margin-bottom:12px;">4. إضافة الامتحانات الشاملة (حتى 50 سؤالاً)</h2>
      <form method="post" action="/admin/exams/add" id="examForm">
        <div class="grid2">
          <div class="field"><label>عنوان الامتحان الشامل *</label><input name="title" type="text" required /></div>
          <div class="field">
            <label>الصف الدراسي *</label>
            <select name="grade">
              {% for g in grades %}<option value="{{ g }}">{{ g }}</option>{% endfor %}
            </select>
          </div>
          <div class="field">
            <label>الشعبة *</label>
            <select name="track">
              <option value="علمي وأدبي معاً">علمي وأدبي معاً</option>
              <option value="علمي">علمي فقط</option>
              <option value="أدبي">أدبي فقط</option>
            </select>
          </div>
        </div>
        <input type="hidden" name="questions_json" id="questionsJsonInput" />
        <div id="dynamicQuestions"></div>
        <div style="display:flex; gap:10px; flex-wrap:wrap; margin-top:10px;">
          <button type="button" class="btn btn-out btn-sm" id="addQuestionBtn">+ إضافة سؤال (حد أقصى 50)</button>
          <button type="submit" class="btn btn-olive">حفظ ونشر الامتحان الشامل</button>
        </div>
      </form>

      {% for ex in exams %}
        <div class="row">
          <div><strong>{{ ex.title }}</strong> <span class="muted">({{ ex.grade }} • {{ ex.track }} • {{ ex.questions|length }} سؤال)</span></div>
          <form method="post" action="/admin/exams/delete" style="margin:0;">
            <input type="hidden" name="exam_id" value="{{ ex.id }}" />
            <button type="submit" class="btn btn-red btn-sm">حذف</button>
          </form>
        </div>
      {% endfor %}
    </section>

    <!-- 5. توليد أكواد سنتر لوحدها وأكواد فتح الفروع لوحدها (كل كود يولد ويستخدم مرة واحدة) -->
    <section id="tab-codes" class="card admin-tab" style="display:none;">
      <h2 style="font-size:1.15rem; font-weight:900; margin-bottom:12px;">5. توليد أكواد السنتر لوحدها وأكواد فتح الفروع لوحدها (لمرة واحدة)</h2>

      <div class="grid2">
        <form method="post" action="/admin/codes/generate-center" class="row" style="display:block; margin-top:0;">
          <div style="font-weight:900; margin-bottom:8px; color:var(--pri);">توليد كود سنتر (يفتح المنصة لمرة واحدة)</div>
          <button type="submit" class="btn btn-blue btn-sm">توليد كود سنتر لمرة واحدة</button>
        </form>

        <form method="post" action="/admin/codes/generate-branch" class="row" style="display:block; margin-top:0;">
          <div style="font-weight:900; margin-bottom:8px; color:var(--olive);">توليد كود فتح فرع لوحده (يستخدم مرة واحدة)</div>
          <div class="field">
            <select name="target_branch">
              {% for br in branches %}<option value="{{ br }}">{{ br }}</option>{% endfor %}
            </select>
          </div>
          <button type="submit" class="btn btn-olive btn-sm">توليد كود الفرع لمرة واحدة</button>
        </form>
      </div>

      {% for c in codes %}
        <div class="row">
          <div>
            <strong>{{ c.code }}</strong> —
            {% if c.code_type == 'center' %}
              <span class="pill" style="background:rgba(29,78,216,0.16); color:var(--pri);">كود سنتر (فتح المنصة • مرة واحدة)</span>
            {% else %}
              <span class="pill pill-ok">كود فرع: {{ c.target_branch }} (مرة واحدة)</span>
            {% endif %}
          </div>
          <span class="pill {{ 'pill-warn' if c.used_by else 'pill-ok' }}">
            {{ 'مستخدم بواسطة: ' ~ c.used_by if c.used_by else 'متاح لمرة واحدة' }}
          </span>
        </div>
      {% endfor %}
    </section>

    <section id="tab-payments" class="card admin-tab" style="display:none;">
      <h2 style="font-size:1.15rem; font-weight:900; margin-bottom:12px;">6. أسئلة الطلاب وصور الدعم العلمي</h2>
      {% for t in tickets %}
        <div class="row" style="display:block;">
          <div><strong>{{ t.student_name }} ({{ t.branch }}):</strong> {{ t.question }}</div>
          {% if t.image_filename %}
            <img class="ticket-img-thumb" src="/ticket-images/{{ t.image_filename }}" alt="صورة السؤال" />
          {% endif %}
          <form method="post" action="/admin/tickets/reply" style="display:flex; gap:8px; margin-top:8px;">
            <input type="hidden" name="ticket_id" value="{{ t.id }}" />
            <input name="reply" type="text" value="{{ t.reply or '' }}" placeholder="اكتب رد الأستاذ هنا..." />
            <button type="submit" class="btn btn-olive btn-sm">إرسال الرد</button>
          </form>
        </div>
      {% endfor %}
    </section>

    <section id="tab-admin-mgmt" class="card admin-tab" style="display:none;">
      <h2 style="font-size:1.15rem; font-weight:900; margin-bottom:12px;">7. صور الفروع والإعدادات العامة</h2>
      <form method="post" action="/admin/settings">
        <div class="grid2">
          <div class="field"><label>رقم فودافون كاش</label><input name="vodafone_number" type="text" value="{{ settings.vodafone_number }}" required /></div>
          <div class="field"><label>رقم واتساب الإدارة</label><input name="admin_whatsapp" type="text" value="{{ settings.admin_whatsapp }}" required /></div>
        </div>
        <div class="field"><label>رابط صورة الأستاذ الرئيسية</label><input name="teacher_image" type="url" value="{{ settings.teacher_image }}" required /></div>
        <div class="field"><label>رسالة / تنبيه عام أعلى المنصة</label><input name="global_notice" type="text" value="{{ settings.global_notice }}" placeholder="اتركه فارغاً لإخفاء التنبيه..." /></div>

        <div class="muted" style="font-weight:800; margin:10px 0 6px;">رابط صورة المستر وماسك كتاب كل فرع:</div>
        <div class="grid2">
          {% for br in branches %}
            <div class="field">
              <label>صورة {{ br }}</label>
              <input name="branch_img_{{ br }}" type="url" value="{{ branch_photos.get(br, settings.teacher_image) }}" required />
            </div>
          {% endfor %}
        </div>
        <button type="submit" class="btn btn-olive btn-sm">حفظ الإعدادات وصور الفروع</button>
      </form>

      <form method="post" action="/admin/change-password" style="margin-top:18px; padding-top:16px; border-top:1px solid var(--bdr);">
        <div class="field"><label>كلمة سر الأدمن الجديدة</label><input name="new_password" type="password" required minlength="6" /></div>
        <button type="submit" class="btn btn-red btn-sm">تغيير كلمة سر الأدمن</button>
      </form>
    </section>
  </div>

  <aside class="right-drawer">
    <div class="drawer-top">
      <span class="drawer-title" style="font-weight:900; font-size:0.92rem;">إدارة المنصة</span>
    </div>
    <button type="button" class="nav-item-link active" data-tab="tab-students">1. طلاب الجخ (فروع)</button>
    <button type="button" class="nav-item-link" data-tab="tab-subscribers">2. المشتركين</button>
    <button type="button" class="nav-item-link" data-tab="tab-lectures">3. إضافة محاضرات</button>
    <button type="button" class="nav-item-link" data-tab="tab-exams">4. الامتحانات الشاملة</button>
    <button type="button" class="nav-item-link" data-tab="tab-codes">5. أكواد السنتر والفروع</button>
    <button type="button" class="nav-item-link" data-tab="tab-payments">6. الدعم والصور</button>
    <button type="button" class="nav-item-link" data-tab="tab-admin-mgmt">7. صور الفروع والإعدادات</button>
    <div style="margin-top:12px; padding-top:10px; border-top:1px solid var(--bdr);">
      <a class="btn btn-red btn-sm" style="width:100%;" href="/admin/logout">قفل اللوحة</a>
    </div>
  </aside>
</div>

<script>
  document.querySelectorAll(".nav-item-link[data-tab]").forEach((btn) => {
    btn.addEventListener("click", function () {
      document.querySelectorAll(".nav-item-link[data-tab]").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".admin-tab").forEach((t) => (t.style.display = "none"));
      btn.classList.add("active");
      document.getElementById(btn.dataset.tab).style.display = "block";
    });
  });

  function applyStudentFilters() {
    const q = (document.getElementById("stuSearchName")?.value || "").trim().toLowerCase();
    const g = document.getElementById("stuFilterGrade")?.value || "";
    const tr = document.getElementById("stuFilterTrack")?.value || "";
    document.querySelectorAll(".stu-item").forEach((el) => {
      const name = (el.dataset.name || "").toLowerCase();
      const matchName = !q || name.includes(q);
      const matchGrade = !g || el.dataset.grade === g;
      const matchTrack = !tr || el.dataset.track === tr;
      el.style.display = (matchName && matchGrade && matchTrack) ? "block" : "none";
    });
  }
  document.getElementById("stuSearchName")?.addEventListener("input", applyStudentFilters);
  document.getElementById("stuFilterGrade")?.addEventListener("change", applyStudentFilters);
  document.getElementById("stuFilterTrack")?.addEventListener("change", applyStudentFilters);

  const dynWrap = document.getElementById("dynamicQuestions");
  let qCount = 0;
  function addExamQuestionBlock() {
    if (qCount >= 50) return;
    qCount += 1;
    const idx = qCount;
    const box = document.createElement("div");
    box.className = "row ex-q-block";
    box.style.display = "block";
    box.innerHTML = `
      <div style="font-weight:800; margin-bottom:6px;">سؤال ${idx}</div>
      <div class="field"><input type="text" class="ex-q-txt" placeholder="نص السؤال..." required /></div>
      <div class="grid2">
        <input type="text" class="ex-o1" placeholder="الاختيار 1" required />
        <input type="text" class="ex-o2" placeholder="الاختيار 2" required />
        <input type="text" class="ex-o3" placeholder="الاختيار 3" required />
        <input type="text" class="ex-o4" placeholder="الاختيار 4" required />
      </div>
      <div class="field" style="margin-top:8px;">
        <label>الإجابة الصحيحة (1 إلى 4)</label>
        <select class="ex-ans">
          <option value="1">الاختيار 1</option>
          <option value="2">الاختيار 2</option>
          <option value="3">الاختيار 3</option>
          <option value="4">الاختيار 4</option>
        </select>
      </div>
    `;
    dynWrap?.appendChild(box);
  }
  if (dynWrap) {
    addExamQuestionBlock();
    document.getElementById("addQuestionBtn")?.addEventListener("click", addExamQuestionBlock);
    document.getElementById("examForm")?.addEventListener("submit", function () {
      const items = [];
      document.querySelectorAll(".ex-q-block").forEach((blk) => {
        const opts = [
          blk.querySelector(".ex-o1").value.trim(),
          blk.querySelector(".ex-o2").value.trim(),
          blk.querySelector(".ex-o3").value.trim(),
          blk.querySelector(".ex-o4").value.trim(),
        ];
        const ansIdx = parseInt(blk.querySelector(".ex-ans").value, 10) - 1;
        items.push({
          question: blk.querySelector(".ex-q-txt").value.trim(),
          options: opts,
          answer: opts[ansIdx] || opts[0],
        });
      });
      document.getElementById("questionsJsonInput").value = JSON.stringify(items);
    });
  }
</script>
{% endif %}
{% endblock %}""",
    encoding="utf-8",
)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app = FastAPI(title="Noor El-Bayan Platform")
app.mount("/ticket-images", StaticFiles(directory=str(TICKET_IMAGES_DIR)), name="ticket_images")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS students (
                phone TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                parent_phone TEXT NOT NULL,
                governorate TEXT NOT NULL DEFAULT '',
                password TEXT NOT NULL,
                grade TEXT NOT NULL,
                track TEXT NOT NULL,
                subscribed INTEGER NOT NULL DEFAULT 0,
                active_branches TEXT NOT NULL DEFAULT '[]',
                completed_lectures TEXT NOT NULL DEFAULT '[]'
            );
            CREATE TABLE IF NOT EXISTS lectures (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                branch TEXT NOT NULL,
                grade TEXT NOT NULL,
                track TEXT NOT NULL,
                filename TEXT NOT NULL DEFAULT '',
                video_url TEXT NOT NULL DEFAULT '',
                pdf_url TEXT NOT NULL DEFAULT '',
                answer_key_url TEXT NOT NULL DEFAULT '',
                quiz_json TEXT NOT NULL DEFAULT '[]'
            );
            CREATE TABLE IF NOT EXISTS exams (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                grade TEXT NOT NULL,
                track TEXT NOT NULL,
                questions_json TEXT NOT NULL DEFAULT '[]'
            );
            CREATE TABLE IF NOT EXISTS access_codes (
                code TEXT PRIMARY KEY,
                code_type TEXT NOT NULL DEFAULT 'branch',
                target_branch TEXT NOT NULL DEFAULT '',
                used_by TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS tickets (
                id TEXT PRIMARY KEY,
                student_phone TEXT NOT NULL,
                student_name TEXT NOT NULL,
                branch TEXT NOT NULL,
                question TEXT NOT NULL,
                image_filename TEXT NOT NULL DEFAULT '',
                reply TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        s_cols = {r["name"] for r in conn.execute("PRAGMA table_info(students)").fetchall()}
        if "governorate" not in s_cols:
            conn.execute("ALTER TABLE students ADD COLUMN governorate TEXT NOT NULL DEFAULT ''")
        if "active_branches" not in s_cols:
            conn.execute("ALTER TABLE students ADD COLUMN active_branches TEXT NOT NULL DEFAULT '[]'")
        l_cols = {r["name"] for r in conn.execute("PRAGMA table_info(lectures)").fetchall()}
        if "video_url" not in l_cols:
            conn.execute("ALTER TABLE lectures ADD COLUMN video_url TEXT NOT NULL DEFAULT ''")
        c_cols = {r["name"] for r in conn.execute("PRAGMA table_info(access_codes)").fetchall()}
        if "code_type" not in c_cols:
            conn.execute("ALTER TABLE access_codes ADD COLUMN code_type TEXT NOT NULL DEFAULT 'branch'")
        if "target_branch" not in c_cols:
            conn.execute("ALTER TABLE access_codes ADD COLUMN target_branch TEXT NOT NULL DEFAULT ''")
        t_cols = {r["name"] for r in conn.execute("PRAGMA table_info(tickets)").fetchall()}
        if "image_filename" not in t_cols:
            conn.execute("ALTER TABLE tickets ADD COLUMN image_filename TEXT NOT NULL DEFAULT ''")
        for k, v in DEFAULT_SETTINGS.items():
            conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
        for br in BRANCHES:
            conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (f"branch_photo_{br}", TEACHER_MAIN_PHOTO))


ensure_schema()


def get_settings() -> Dict[str, str]:
    data = dict(DEFAULT_SETTINGS)
    with get_conn() as conn:
        for row in conn.execute("SELECT key, value FROM settings").fetchall():
            data[row["key"]] = row["value"]
    return data


def get_branch_photos(settings: Dict[str, str]) -> Dict[str, str]:
    fallback = settings.get("teacher_image") or TEACHER_MAIN_PHOTO
    return {br: (settings.get(f"branch_photo_{br}") or fallback) for br in BRANCHES}


def os_time_ms() -> int:
    return int(time.time() * 1000)


def current_student(request: Request) -> Optional[Dict[str, Any]]:
    phone = request.cookies.get("stu_phone", "").strip()
    if not phone:
        return None
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM students WHERE phone = ?", (phone,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["completed_list"] = json.loads(d.get("completed_lectures") or "[]")
        branches_raw = json.loads(d.get("active_branches") or "[]")
        if not branches_raw and d.get("subscribed"):
            branches_raw = list(BRANCHES)
        d["active_branches_list"] = [b for b in branches_raw if b in BRANCHES]
        return d


def is_admin_logged_in(request: Request) -> bool:
    return request.cookies.get("adm_auth") == "ok"


def compute_perf_pct(student: Dict[str, Any], all_lectures: List[Dict[str, Any]]) -> int:
    relevant = [
        l for l in all_lectures
        if l["grade"] == student["grade"] and l["track"] in ("علمي وأدبي معاً", student["track"])
    ]
    if not relevant:
        return 0
    done = len([x for x in student.get("completed_list", []) if x in {r["id"] for r in relevant}])
    return min(100, int(round((done / len(relevant)) * 100)))


@app.get("/", response_class=HTMLResponse)
def landing_page(request: Request) -> HTMLResponse:
    settings = get_settings()
    stu = current_student(request)
    return templates.TemplateResponse(
        request=request,
        name="landing.html",
        context={
            "title": "الرئيسية",
            "student": stu,
            "settings": settings,
            "global_notice": settings.get("global_notice", ""),
        },
    )


@app.get("/student", response_class=HTMLResponse)
def student_page(
    request: Request,
    tab: str = "login",
    step: int = 1,
    section: str = "home",
    sub: str = "mine",
    branch: str = "",
    first_name: str = "",
    second_name: str = "",
    third_name: str = "",
    phone: str = "",
    error: str = "",
    notice: str = "",
) -> HTMLResponse:
    settings = get_settings()
    branch_photos = get_branch_photos(settings)
    stu = current_student(request)
    active_branch = branch if branch in BRANCHES else BRANCHES[0]
    lectures: List[Dict[str, Any]] = []
    recent_lectures: List[Dict[str, Any]] = []
    exams: List[Dict[str, Any]] = []
    tickets: List[Dict[str, Any]] = []
    perf_pct = 0
    total_lectures = 0
    completed_count = 0

    if stu:
        with get_conn() as conn:
            all_lec = [dict(r) for r in conn.execute("SELECT * FROM lectures").fetchall()]
            grade_track_lec = [
                l for l in all_lec
                if l["grade"] == stu["grade"] and l["track"] in ("علمي وأدبي معاً", stu["track"])
            ]
            total_lectures = len(grade_track_lec)
            completed_count = len([x for x in stu["completed_list"] if x in {r["id"] for r in grade_track_lec}])
            recent_lectures = grade_track_lec[:4]
            if sub == "branch":
                lectures = [l for l in grade_track_lec if l["branch"] == active_branch]
            else:
                lectures = grade_track_lec

            all_ex = [dict(r) for r in conn.execute("SELECT * FROM exams").fetchall()]
            for ex in all_ex:
                ex["questions"] = json.loads(ex.get("questions_json") or "[]")
            exams = [
                ex for ex in all_ex
                if ex["grade"] == stu["grade"] and ex["track"] in ("علمي وأدبي معاً", stu["track"])
            ]
            tickets = [
                dict(r) for r in conn.execute(
                    "SELECT * FROM tickets WHERE student_phone = ?", (stu["phone"],)
                ).fetchall()
            ]
            perf_pct = compute_perf_pct(stu, all_lec)

    return templates.TemplateResponse(
        request=request,
        name="student.html",
        context={
            "title": "بوابة الطالب",
            "student": stu,
            "active_branches_list": stu["active_branches_list"] if stu else [],
            "auth_tab": tab if tab in {"login", "register", "forgot", "center"} else "login",
            "step": 2 if step == 2 else 1,
            "draft": {
                "first_name": first_name,
                "second_name": second_name,
                "third_name": third_name,
                "phone": phone,
            },
            "section": section if section in {"home", "courses", "forum", "account"} else "home",
            "sub": sub,
            "branches": BRANCHES,
            "grades": GRADES,
            "tracks": TRACKS,
            "selected_branch": active_branch,
            "branch_photos": branch_photos,
            "current_branch_photo": branch_photos.get(active_branch, settings["teacher_image"]),
            "lectures": lectures,
            "recent_lectures": recent_lectures,
            "total_lectures": total_lectures,
            "completed_count": completed_count,
            "completed_ids": set(stu["completed_list"]) if stu else set(),
            "exams": exams,
            "tickets": tickets,
            "perf_pct": perf_pct,
            "settings": settings,
            "global_notice": settings.get("global_notice", ""),
            "error": error,
            "notice": notice,
        },
    )


@app.post("/student/center-login")
def student_center_login(
    center_code: str = Form(...),
    name: str = Form(...),
    phone: str = Form(...),
    grade: str = Form(...),
    track: str = Form(...),
) -> RedirectResponse:
    c_val = center_code.strip().upper()
    p = phone.strip()
    n = name.strip()
    if not c_val or not p or not n:
        return RedirectResponse(url="/student?tab=center&error=" + quote("أدخل كود السنتر والاسم ورقم الهاتف."), status_code=302)

    with get_conn() as conn:
        row = conn.execute("SELECT * FROM access_codes WHERE code = ?", (c_val,)).fetchone()
        if not row or row["code_type"] != "center":
            return RedirectResponse(url="/student?tab=center&error=" + quote("كود السنتر غير صحيح."), status_code=302)
        if row["used_by"]:
            return RedirectResponse(url="/student?tab=center&error=" + quote("كود السنتر مستخدم من قبل (يستخدم مرة واحدة فقط)."), status_code=302)

        existing = conn.execute("SELECT * FROM students WHERE phone = ?", (p,)).fetchone()
        if existing:
            conn.execute(
                "UPDATE students SET name = ?, grade = ?, track = ?, subscribed = 1, active_branches = ? WHERE phone = ?",
                (n, grade.strip(), track.strip(), json.dumps(BRANCHES, ensure_ascii=False), p),
            )
        else:
            conn.execute(
                "INSERT INTO students (phone, name, parent_phone, governorate, password, grade, track, subscribed, active_branches, completed_lectures) VALUES (?, ?, ?, '', ?, ?, ?, 1, ?, '[]')",
                (p, n, p, f"CTR-{c_val[-6:]}", grade.strip(), track.strip(), json.dumps(BRANCHES, ensure_ascii=False)),
            )
        conn.execute("UPDATE access_codes SET used_by = ? WHERE code = ?", (p, c_val))

    resp = RedirectResponse(url="/student?notice=" + quote("تم تفعيل كود السنتر وفتح المنصة لك بنجاح."), status_code=302)
    resp.set_cookie("stu_phone", p, httponly=True, samesite="lax")
    return resp


@app.post("/student/register")
def student_register(
    full_name: str = Form(...),
    phone: str = Form(...),
    parent_phone: str = Form(...),
    governorate: str = Form(...),
    grade: str = Form(...),
    track: str = Form(...),
    password: str = Form(...),
) -> RedirectResponse:
    p = phone.strip()
    pp = parent_phone.strip()
    if not p or not pp or not full_name.strip():
        return RedirectResponse(url="/student?tab=register&step=1&error=" + quote("جميع الحقول الإجبارية مطلوبة."), status_code=302)
    with get_conn() as conn:
        if conn.execute("SELECT phone FROM students WHERE phone = ?", (p,)).fetchone():
            return RedirectResponse(url="/student?tab=register&step=1&error=" + quote("رقم الهاتف مسجل مسبقاً."), status_code=302)
        conn.execute(
            "INSERT INTO students (phone, name, parent_phone, governorate, password, grade, track, subscribed, active_branches, completed_lectures) VALUES (?, ?, ?, ?, ?, ?, ?, 0, '[]', '[]')",
            (p, full_name.strip(), pp, governorate.strip(), password, grade.strip(), track.strip()),
        )
    resp = RedirectResponse(url="/student?notice=" + quote("تم إنشاء حسابك بنجاح."), status_code=302)
    resp.set_cookie("stu_phone", p, httponly=True, samesite="lax")
    return resp


@app.post("/student/login")
def student_login(phone: str = Form(...), password: str = Form(...)) -> RedirectResponse:
    p = phone.strip()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM students WHERE phone = ?", (p,)).fetchone()
        if not row or row["password"] != password:
            return RedirectResponse(url="/student?tab=login&error=" + quote("رقم الهاتف أو كلمة السر غير صحيحة."), status_code=302)
    resp = RedirectResponse(url="/student", status_code=302)
    resp.set_cookie("stu_phone", p, httponly=True, samesite="lax")
    return resp


@app.post("/student/reset-password")
def student_reset_password(
    phone: str = Form(...),
    parent_phone: str = Form(...),
    new_password: str = Form(...),
) -> RedirectResponse:
    p = phone.strip()
    pp = parent_phone.strip()
    with get_conn() as conn:
        row = conn.execute("SELECT phone FROM students WHERE phone = ? AND parent_phone = ?", (p, pp)).fetchone()
        if not row:
            return RedirectResponse(url="/student?tab=forgot&error=" + quote("رقم الطالب أو رقم ولي الأمر غير مطابق."), status_code=302)
        conn.execute("UPDATE students SET password = ? WHERE phone = ?", (new_password, p))
    return RedirectResponse(url="/student?tab=login&notice=" + quote("تم تعيين كلمة السر الجديدة بنجاح."), status_code=302)


@app.get("/student/logout")
def student_logout() -> RedirectResponse:
    resp = RedirectResponse(url="/student?tab=login", status_code=302)
    resp.delete_cookie("stu_phone")
    return resp


@app.post("/student/redeem-code")
def student_redeem_code(request: Request, code: str = Form(...)) -> RedirectResponse:
    stu = current_student(request)
    if not stu:
        return RedirectResponse(url="/student", status_code=302)
    c_val = code.strip().upper()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM access_codes WHERE code = ?", (c_val,)).fetchone()
        if not row:
            return RedirectResponse(url="/student?section=account&sub=billing&error=" + quote("الكود غير صحيح."), status_code=302)
        if row["used_by"]:
            return RedirectResponse(url="/student?section=account&sub=billing&error=" + quote("هذا الكود تم استخدامه من قبل (كود لمرة واحدة)."), status_code=302)
        if row["code_type"] == "center":
            conn.execute("UPDATE access_codes SET used_by = ? WHERE code = ?", (stu["phone"], c_val))
            conn.execute(
                "UPDATE students SET subscribed = 1, active_branches = ? WHERE phone = ?",
                (json.dumps(BRANCHES, ensure_ascii=False), stu["phone"]),
            )
            return RedirectResponse(url="/student?section=account&sub=billing&notice=" + quote("تم تفعيل كود السنتر وفتح جميع الفروع بنجاح."), status_code=302)

        target_br = row["target_branch"] if row["target_branch"] in BRANCHES else BRANCHES[0]
        updated_branches = set(stu["active_branches_list"])
        updated_branches.add(target_br)
        conn.execute("UPDATE access_codes SET used_by = ? WHERE code = ?", (stu["phone"], c_val))
        conn.execute(
            "UPDATE students SET subscribed = 1, active_branches = ? WHERE phone = ?",
            (json.dumps(list(updated_branches), ensure_ascii=False), stu["phone"]),
        )
    return RedirectResponse(
        url="/student?section=account&sub=billing&notice=" + quote(f"تم تفعيل فرع «{target_br}» بنجاح بالكود (لمرة واحدة)."),
        status_code=302,
    )


@app.post("/student/support")
async def student_support(
    request: Request,
    branch: str = Form(...),
    question: str = Form(...),
    question_image: Optional[UploadFile] = File(None),
) -> RedirectResponse:
    stu = current_student(request)
    if not stu:
        return RedirectResponse(url="/student", status_code=302)

    img_filename = ""
    if question_image and question_image.filename:
        ext = Path(Path(question_image.filename).name).suffix.lower()
        if ext not in ALLOWED_IMAGE_EXT:
            return RedirectResponse(url="/student?section=forum&error=" + quote("صيغة الصورة غير مدعومة."), status_code=302)
        img_filename = f"qimg_{os_time_ms()}{ext}"
        with open(TICKET_IMAGES_DIR / img_filename, "wb") as out:
            while True:
                chunk = await question_image.read(512 * 1024)
                if not chunk:
                    break
                out.write(chunk)

    tkt_id = f"tkt_{os_time_ms()}"
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO tickets (id, student_phone, student_name, branch, question, image_filename, reply) VALUES (?, ?, ?, ?, ?, ?, '')",
            (tkt_id, stu["phone"], stu["name"], branch.strip(), question.strip(), img_filename),
        )
    return RedirectResponse(url="/student?section=forum&notice=" + quote("تم إرسال سؤالك للأستاذ."), status_code=302)


@app.post("/student/change-password")
def student_change_password(
    request: Request,
    old_password: str = Form(...),
    new_password: str = Form(...),
) -> RedirectResponse:
    stu = current_student(request)
    if not stu:
        return RedirectResponse(url="/student", status_code=302)
    if stu["password"] != old_password:
        return RedirectResponse(url="/student?section=account&sub=security&error=" + quote("كلمة السر الحالية غير صحيحة."), status_code=302)
    with get_conn() as conn:
        conn.execute("UPDATE students SET password = ? WHERE phone = ?", (new_password, stu["phone"]))
    return RedirectResponse(url="/student?section=account&sub=security&notice=" + quote("تم تحديث كلمة السر بنجاح."), status_code=302)


@app.get("/lecture/{lecture_id}", response_class=HTMLResponse)
def lecture_detail(lecture_id: str, request: Request) -> HTMLResponse:
    stu = current_student(request)
    if not stu:
        return RedirectResponse(url="/student", status_code=302)
    settings = get_settings()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM lectures WHERE id = ?", (lecture_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="المحاضرة غير موجودة.")
    lec = dict(row)
    lec["quiz"] = json.loads(lec.get("quiz_json") or "[]")
    lec["youtube_id"] = extract_youtube_id(lec.get("video_url") or "")
    return templates.TemplateResponse(
        request=request,
        name="lecture.html",
        context={
            "title": lec["title"],
            "student": stu,
            "active_branches_list": stu["active_branches_list"],
            "lecture": lec,
            "quiz_result": None,
            "settings": settings,
            "global_notice": settings.get("global_notice", ""),
        },
    )


@app.post("/lecture/{lecture_id}/quiz", response_class=HTMLResponse)
async def submit_lecture_quiz(lecture_id: str, request: Request) -> HTMLResponse:
    stu = current_student(request)
    if not stu:
        return RedirectResponse(url="/student", status_code=302)
    form = await request.form()
    settings = get_settings()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM lectures WHERE id = ?", (lecture_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="المحاضرة غير موجودة.")
        lec = dict(row)
        quiz = json.loads(lec.get("quiz_json") or "[]")
        score = sum(
            1 for idx, q in enumerate(quiz)
            if str(form.get(f"q_{idx}", "")).strip() == str(q.get("answer", "")).strip()
        )
        completed = set(stu.get("completed_list") or [])
        completed.add(lecture_id)
        conn.execute(
            "UPDATE students SET completed_lectures = ? WHERE phone = ?",
            (json.dumps(list(completed), ensure_ascii=False), stu["phone"]),
        )
    lec["quiz"] = quiz
    lec["youtube_id"] = extract_youtube_id(lec.get("video_url") or "")
    return templates.TemplateResponse(
        request=request,
        name="lecture.html",
        context={
            "title": lec["title"],
            "student": stu,
            "active_branches_list": stu["active_branches_list"],
            "lecture": lec,
            "quiz_result": {"score": score, "total": len(quiz)},
            "settings": settings,
            "global_notice": settings.get("global_notice", ""),
        },
    )


@app.get("/exam/{exam_id}", response_class=HTMLResponse)
def exam_detail(exam_id: str, request: Request) -> HTMLResponse:
    stu = current_student(request)
    if not stu:
        return RedirectResponse(url="/student", status_code=302)
    if not stu["active_branches_list"]:
        return RedirectResponse(url="/student?section=courses&sub=exams&error=" + quote("فعّل فرعاً واحداً على الأقل لدخول الامتحان."), status_code=302)
    settings = get_settings()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM exams WHERE id = ?", (exam_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="الامتحان غير موجود.")
    ex = dict(row)
    ex["questions"] = json.loads(ex.get("questions_json") or "[]")
    return templates.TemplateResponse(
        request=request,
        name="exam.html",
        context={
            "title": ex["title"],
            "student": stu,
            "exam": ex,
            "exam_result": None,
            "settings": settings,
            "global_notice": settings.get("global_notice", ""),
        },
    )


@app.post("/exam/{exam_id}/submit", response_class=HTMLResponse)
async def submit_exam(exam_id: str, request: Request) -> HTMLResponse:
    stu = current_student(request)
    if not stu:
        return RedirectResponse(url="/student", status_code=302)
    form = await request.form()
    settings = get_settings()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM exams WHERE id = ?", (exam_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="الامتحان غير موجود.")
    ex = dict(row)
    qs = json.loads(ex.get("questions_json") or "[]")
    score = sum(
        1 for idx, q in enumerate(qs)
        if str(form.get(f"q_{idx}", "")).strip() == str(q.get("answer", "")).strip()
    )
    ex["questions"] = qs
    return templates.TemplateResponse(
        request=request,
        name="exam.html",
        context={
            "title": ex["title"],
            "student": stu,
            "exam": ex,
            "exam_result": {"score": score, "total": len(qs)},
            "settings": settings,
            "global_notice": settings.get("global_notice", ""),
        },
    )


@app.get("/video/{lecture_id}")
def stream_protected_video(lecture_id: str, request: Request) -> StreamingResponse:
    stu = current_student(request)
    if not stu:
        raise HTTPException(status_code=403, detail="غير مسموح بالمشاهدة.")
    with get_conn() as conn:
        lec = conn.execute("SELECT * FROM lectures WHERE id = ?", (lecture_id,)).fetchone()
    if not lec:
        raise HTTPException(status_code=404, detail="الفيديو غير موجود.")
    if lec["branch"] not in stu["active_branches_list"]:
        raise HTTPException(status_code=403, detail="هذا الفرع غير مفعل على حسابك.")
    if not lec["filename"]:
        raise HTTPException(status_code=404, detail="لا يوجد ملف فيديو مرفوع لهذه المحاضرة.")
    file_path = VIDEOS_DIR / lec["filename"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="ملف الفيديو غير موجود.")

    file_size = file_path.stat().st_size
    content_type = mimetypes.guess_type(str(file_path))[0] or "video/mp4"
    range_header = request.headers.get("range")
    start = 0
    end = file_size - 1
    status_code = 200
    if range_header:
        parts = range_header.replace("bytes=", "").strip().split("-")
        if parts[0]:
            start = int(parts[0])
        if len(parts) > 1 and parts[1]:
            end = min(int(parts[1]), file_size - 1)
        status_code = 206
    chunk_size = (end - start) + 1

    def iter_file():
        with open(file_path, "rb") as f:
            f.seek(start)
            rem = chunk_size
            while rem > 0:
                data = f.read(min(65536, rem))
                if not data:
                    break
                rem -= len(data)
                yield data

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(chunk_size),
        "Content-Type": content_type,
        "Content-Disposition": "inline",
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-store, no-cache, must-revalidate",
    }
    if status_code == 206:
        headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"

    return StreamingResponse(iter_file(), status_code=status_code, headers=headers, media_type=content_type)


@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, error: str = "", notice: str = "") -> HTMLResponse:
    # منع وصول الطالب المسجل دخوله إلى لوحة الأدمن
    if current_student(request) is not None and not is_admin_logged_in(request):
        raise HTTPException(status_code=403, detail="غير مسموح للطالب بالدخول إلى لوحة الأدمن.")

    settings = get_settings()
    branch_photos = get_branch_photos(settings)
    logged = is_admin_logged_in(request)
    students: List[Dict[str, Any]] = []
    subscribers: List[Dict[str, Any]] = []
    lectures: List[Dict[str, Any]] = []
    exams: List[Dict[str, Any]] = []
    codes: List[Dict[str, Any]] = []
    tickets: List[Dict[str, Any]] = []

    if logged:
        with get_conn() as conn:
            raw_students = [dict(r) for r in conn.execute("SELECT * FROM students").fetchall()]
            all_lec = [dict(r) for r in conn.execute("SELECT * FROM lectures").fetchall()]
            for s in raw_students:
                s["completed_list"] = json.loads(s.get("completed_lectures") or "[]")
                b_raw = json.loads(s.get("active_branches") or "[]")
                if not b_raw and s.get("subscribed"):
                    b_raw = list(BRANCHES)
                s["active_branches"] = [b for b in b_raw if b in BRANCHES]
                s["perf_pct"] = compute_perf_pct(s, all_lec)
                rel = [
                    l for l in all_lec
                    if l["grade"] == s["grade"] and l["track"] in ("علمي وأدبي معاً", s["track"])
                ]
                s["total_lectures"] = len(rel)
                s["completed_count"] = len([x for x in s["completed_list"] if x in {r["id"] for r in rel}])
                students.append(s)
                if s["active_branches"] or s["subscribed"]:
                    subscribers.append(s)
            lectures = all_lec
            exams = [dict(r) for r in conn.execute("SELECT * FROM exams").fetchall()]
            for ex in exams:
                ex["questions"] = json.loads(ex.get("questions_json") or "[]")
            codes = [dict(r) for r in conn.execute("SELECT * FROM access_codes").fetchall()]
            tickets = [dict(r) for r in conn.execute("SELECT * FROM tickets").fetchall()]

    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "title": "لوحة الأدمن",
            "student": None,
            "is_admin": logged,
            "students": students,
            "subscribers": subscribers,
            "lectures": lectures,
            "exams": exams,
            "codes": codes,
            "tickets": tickets,
            "branches": BRANCHES,
            "branch_photos": branch_photos,
            "grades": GRADES,
            "tracks": TRACKS,
            "settings": settings,
            "global_notice": settings.get("global_notice", ""),
            "error": error,
            "notice": notice,
        },
    )


@app.post("/admin/login")
def admin_login(email: str = Form(...), password: str = Form(...)) -> RedirectResponse:
    settings = get_settings()
    if email.strip() == settings["admin_email"] and hash_secret(password) == settings["admin_password_hash"]:
        resp = RedirectResponse(url="/admin", status_code=302)
        resp.delete_cookie("stu_phone")
        resp.set_cookie("adm_auth", "ok", httponly=True, samesite="lax")
        return resp
    return RedirectResponse(url="/admin?error=" + quote("بيانات الدخول غير صحيحة."), status_code=302)


@app.get("/admin/logout")
def admin_logout() -> RedirectResponse:
    resp = RedirectResponse(url="/admin", status_code=302)
    resp.delete_cookie("adm_auth")
    return resp


@app.post("/admin/students/set-branches")
async def admin_set_student_branches(request: Request) -> RedirectResponse:
    if not is_admin_logged_in(request):
        return RedirectResponse(url="/admin", status_code=302)
    form = await request.form()
    phone = str(form.get("phone", "")).strip()
    selected = [str(x) for x in form.getlist("branches") if str(x) in BRANCHES]
    sub_flag = 1 if selected else 0
    with get_conn() as conn:
        conn.execute(
            "UPDATE students SET active_branches = ?, subscribed = ? WHERE phone = ?",
            (json.dumps(selected, ensure_ascii=False), sub_flag, phone),
        )
    msg = f"تم تحديث فروع الطالب ({', '.join(selected) if selected else 'لا يوجد فرع مفعل'})."
    return RedirectResponse(url="/admin?notice=" + quote(msg), status_code=302)


@app.post("/admin/students/delete")
def admin_delete_student(request: Request, phone: str = Form(...)) -> RedirectResponse:
    if not is_admin_logged_in(request):
        return RedirectResponse(url="/admin", status_code=302)
    with get_conn() as conn:
        conn.execute("DELETE FROM students WHERE phone = ?", (phone,))
    return RedirectResponse(url="/admin?notice=" + quote("تم حذف حساب الطالب نهائياً."), status_code=302)


@app.post("/admin/lectures/add")
async def admin_add_lecture(request: Request, video_file: Optional[UploadFile] = File(None)) -> RedirectResponse:
    if not is_admin_logged_in(request):
        return RedirectResponse(url="/admin", status_code=302)
    form = await request.form()
    title = str(form.get("title", "")).strip()
    branch = str(form.get("branch", "")).strip()
    grade = str(form.get("grade", "")).strip()
    track = str(form.get("track", "")).strip()
    video_url = str(form.get("video_url", "")).strip()
    pdf_url = str(form.get("pdf_url", "")).strip()
    answer_key_url = str(form.get("answer_key_url", "")).strip()

    quiz_items: List[Dict[str, Any]] = []
    for i in range(1, 6):
        q_txt = str(form.get(f"q_{i}_text", "")).strip()
        opts = [
            str(form.get(f"q_{i}_o1", "")).strip(),
            str(form.get(f"q_{i}_o2", "")).strip(),
            str(form.get(f"q_{i}_o3", "")).strip(),
            str(form.get(f"q_{i}_o4", "")).strip(),
        ]
        c_idx = int(str(form.get(f"q_{i}_correct", "1"))) - 1
        if not q_txt or any(not o for o in opts):
            return RedirectResponse(url="/admin?error=" + quote("الكويز إجباري ويجب إدخال 5 أسئلة كاملة."), status_code=302)
        quiz_items.append({"question": q_txt, "options": opts, "answer": opts[max(0, min(3, c_idx))]})

    lec_id = f"lec_{os_time_ms()}"
    stored_name = ""

    if video_file and video_file.filename:
        ext = Path(Path(video_file.filename).name).suffix.lower()
        if ext not in ALLOWED_VIDEO_EXT:
            return RedirectResponse(url="/admin?error=" + quote("صيغة الفيديو غير مدعومة."), status_code=302)
        stored_name = f"{lec_id}{ext}"
        with open(VIDEOS_DIR / stored_name, "wb") as out:
            while True:
                chunk = await video_file.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
    elif not video_url:
        return RedirectResponse(
            url="/admin?error=" + quote("ارفع ملف فيديو من جهازك أو ضع رابط فيديو لتشغيله كفيديو محمي."),
            status_code=302,
        )

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO lectures (id, title, branch, grade, track, filename, video_url, pdf_url, answer_key_url, quiz_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (lec_id, title, branch, grade, track, stored_name, video_url, pdf_url, answer_key_url, json.dumps(quiz_items, ensure_ascii=False)),
        )
    return RedirectResponse(url="/admin?notice=" + quote("تم نشر المحاضرة بالكويز الإجباري."), status_code=302)


@app.post("/admin/lectures/delete")
def admin_delete_lecture(request: Request, lecture_id: str = Form(...)) -> RedirectResponse:
    if not is_admin_logged_in(request):
        return RedirectResponse(url="/admin", status_code=302)
    with get_conn() as conn:
        row = conn.execute("SELECT filename FROM lectures WHERE id = ?", (lecture_id,)).fetchone()
        if row and row["filename"]:
            vp = VIDEOS_DIR / row["filename"]
            if vp.exists():
                os.remove(vp)
        conn.execute("DELETE FROM lectures WHERE id = ?", (lecture_id,))
    return RedirectResponse(url="/admin?notice=" + quote("تم حذف المحاضرة."), status_code=302)


@app.post("/admin/exams/add")
def admin_add_exam(
    request: Request,
    title: str = Form(...),
    grade: str = Form(...),
    track: str = Form(...),
    questions_json: str = Form(...),
) -> RedirectResponse:
    if not is_admin_logged_in(request):
        return RedirectResponse(url="/admin", status_code=302)
    items = json.loads(questions_json or "[]")
    if not items or len(items) > 50:
        return RedirectResponse(url="/admin?error=" + quote("يجب إضافة سؤال واحد على الأقل وبحد أقصى 50 سؤالاً."), status_code=302)
    ex_id = f"ex_{os_time_ms()}"
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO exams (id, title, grade, track, questions_json) VALUES (?, ?, ?, ?, ?)",
            (ex_id, title.strip(), grade.strip(), track.strip(), json.dumps(items, ensure_ascii=False)),
        )
    return RedirectResponse(url="/admin?notice=" + quote("تم نشر الامتحان الشامل."), status_code=302)


@app.post("/admin/exams/delete")
def admin_delete_exam(request: Request, exam_id: str = Form(...)) -> RedirectResponse:
    if not is_admin_logged_in(request):
        return RedirectResponse(url="/admin", status_code=302)
    with get_conn() as conn:
        conn.execute("DELETE FROM exams WHERE id = ?", (exam_id,))
    return RedirectResponse(url="/admin?notice=" + quote("تم حذف الامتحان."), status_code=302)


@app.post("/admin/codes/generate-center")
def admin_generate_center_code(request: Request) -> RedirectResponse:
    if not is_admin_logged_in(request):
        return RedirectResponse(url="/admin", status_code=302)
    code_str = f"CTR-{(os_time_ms() * 7919) % 1000000:06d}"
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO access_codes (code, code_type, target_branch, used_by) VALUES (?, 'center', '', '')",
            (code_str,),
        )
    return RedirectResponse(url="/admin?notice=" + quote(f"تم توليد كود سنتر لمرة واحدة: {code_str}"), status_code=302)


@app.post("/admin/codes/generate-branch")
def admin_generate_branch_code(request: Request, target_branch: str = Form(...)) -> RedirectResponse:
    if not is_admin_logged_in(request):
        return RedirectResponse(url="/admin", status_code=302)
    br = target_branch if target_branch in BRANCHES else BRANCHES[0]
    code_str = f"BRN-{(os_time_ms() * 65537) % 1000000:06d}"
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO access_codes (code, code_type, target_branch, used_by) VALUES (?, 'branch', ?, '')",
            (code_str, br),
        )
    return RedirectResponse(url="/admin?notice=" + quote(f"تم توليد كود فرع «{br}» لمرة واحدة: {code_str}"), status_code=302)


@app.post("/admin/tickets/reply")
def admin_reply_ticket(
    request: Request,
    ticket_id: str = Form(...),
    reply: str = Form(...),
) -> RedirectResponse:
    if not is_admin_logged_in(request):
        return RedirectResponse(url="/admin", status_code=302)
    with get_conn() as conn:
        conn.execute("UPDATE tickets SET reply = ? WHERE id = ?", (reply.strip(), ticket_id))
    return RedirectResponse(url="/admin?notice=" + quote("تم إرسال الرد للطالب."), status_code=302)


@app.post("/admin/settings")
async def admin_settings(request: Request) -> RedirectResponse:
    if not is_admin_logged_in(request):
        return RedirectResponse(url="/admin", status_code=302)
    form = await request.form()
    vodafone_number = str(form.get("vodafone_number", DEFAULT_SETTINGS["vodafone_number"])).strip()
    admin_whatsapp = str(form.get("admin_whatsapp", DEFAULT_SETTINGS["admin_whatsapp"])).strip()
    teacher_image = str(form.get("teacher_image", TEACHER_MAIN_PHOTO)).strip() or TEACHER_MAIN_PHOTO
    global_notice = str(form.get("global_notice", "")).strip()

    with get_conn() as conn:
        for k, v in [
            ("vodafone_number", vodafone_number),
            ("admin_whatsapp", admin_whatsapp),
            ("teacher_image", teacher_image),
            ("global_notice", global_notice),
        ]:
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, v))
        for br in BRANCHES:
            b_img = str(form.get(f"branch_img_{br}", teacher_image)).strip() or teacher_image
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (f"branch_photo_{br}", b_img))

    return RedirectResponse(url="/admin?notice=" + quote("تم حفظ الإعدادات وصور الفروع."), status_code=302)


@app.post("/admin/change-password")
def admin_change_password(request: Request, new_password: str = Form(...)) -> RedirectResponse:
    if not is_admin_logged_in(request):
        return RedirectResponse(url="/admin", status_code=302)
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('admin_password_hash', ?)",
            (hash_secret(new_password),),
        )
    return RedirectResponse(url="/admin?notice=" + quote("تم تغيير كلمة سر الأدمن بنجاح."), status_code=302)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)