"""Design system WafaClub pour Streamlit (CSS + helpers)."""

from __future__ import annotations

import streamlit as st

from ..i18n import is_rtl

BASE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Noto+Kufi+Arabic:wght@400;500;600;700&display=swap');

:root {
  --wafa-navy: #0B3C6E;
  --wafa-navy-deep: #072A4F;
  --wafa-blue: #1E6FA8;
  --wafa-sky: #E8F2FB;
  --wafa-gold: #D99A2B;
  --wafa-gold-soft: #FFF4DC;
  --wafa-green: #12805C;
  --wafa-green-soft: #E6F7F0;
  --wafa-red: #B5413A;
  --wafa-red-soft: #FDECEA;
  --wafa-bg: #F4F7FB;
  --wafa-ink: #0B2545;
  --wafa-muted: #64748B;
  --wafa-border: #E5ECF5;
}

html, body, [class*="css"] {
  font-family: 'Plus Jakarta Sans', 'Segoe UI', system-ui, -apple-system, sans-serif;
}

.stApp {
  background:
    radial-gradient(1200px 380px at 90% -120px, rgba(30,111,168,.08), transparent 60%),
    var(--wafa-bg);
  color: var(--wafa-ink);
}

[data-testid="stHeader"] {
  background: transparent;
}
[data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu, footer {
  visibility: hidden;
  height: 0;
}
[data-testid="stStatusWidget"] { visibility: hidden; }

.block-container {
  padding-top: 1.7rem;
  padding-bottom: 4.5rem;
  max-width: 1180px;
}

h1, h2, h3, h4 {
  color: var(--wafa-ink);
  letter-spacing: -0.025em;
}
p, li { color: #334155; }
a { color: var(--wafa-blue); }
code, pre, .wafa-code, .wafa-code * {
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', monospace !important;
  direction: ltr;
  unicode-bidi: embed;
}

/* --- Boutons Streamlit --- */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
  border-radius: 13px;
  min-height: 2.75rem;
  font-weight: 650;
  font-family: inherit;
  border: 1px solid var(--wafa-border);
  transition: transform .16s ease, box-shadow .16s ease, background .16s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover, .stFormSubmitButton > button:hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 20px rgba(11,60,110,.12);
  border-color: #C9D9EA;
}
button[data-testid="stBaseButton-primary"],
button[kind="primary"],
button[data-testid="stBaseButton-primaryFormSubmit"],
button[kind="primaryFormSubmit"] {
  background: linear-gradient(135deg, var(--wafa-navy), #145A92);
  color: #fff !important;
  border-color: transparent;
}
button[data-testid="stBaseButton-primary"] *,
button[kind="primary"] *,
button[data-testid="stBaseButton-primaryFormSubmit"] *,
button[kind="primaryFormSubmit"] * { color: #fff !important; }
button[data-testid="stBaseButton-secondary"], button[kind="secondary"] {
  background: #fff;
  color: var(--wafa-navy);
}
button[data-testid="stBaseButton-primary"]:hover,
button[kind="primary"]:hover,
button[data-testid="stBaseButton-primaryFormSubmit"]:hover,
button[kind="primaryFormSubmit"]:hover {
  color: #fff;
}

/* --- Formulaires --- */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stDateInput"] input,
[data-testid="stSelectbox"] > div > div,
[data-testid="stTextArea"] textarea {
  border-radius: 12px !important;
  font-family: inherit;
}
[data-testid="stWidgetLabel"] p {
  font-size: .86rem;
  font-weight: 650;
  color: #334155;
}
[data-testid="stForm"] {
  border: 1px solid var(--wafa-border);
  border-radius: 20px;
  background: #fff;
  padding: 1.25rem 1.25rem .8rem;
  box-shadow: 0 12px 35px rgba(11,60,110,.05);
}
[data-testid="stExpander"] {
  border: 1px solid var(--wafa-border);
  border-radius: 16px;
  background: #fff;
}
[data-testid="stAlert"] {
  border-radius: 14px;
}
[data-testid="stTabs"] button {
  font-weight: 650;
  font-family: inherit;
}
[data-testid="stDataFrame"] {
  border: 1px solid var(--wafa-border);
  border-radius: 16px;
  overflow: hidden;
}

/* --- Sidebar --- */
[data-testid="stSidebar"] {
  background:
    radial-gradient(420px 240px at 0% 0%, rgba(217,154,43,.16), transparent 65%),
    linear-gradient(180deg, #072A4F 0%, #0B3C6E 65%, #0D4579 100%);
  border-right: none;
}
[data-testid="stSidebar"] > div { padding-top: 1.1rem; }
[data-testid="stSidebar"] * { color: #EDF5FD; }
[data-testid="stSidebar"] .stButton > button {
  justify-content: flex-start;
  text-align: left;
  background: rgba(255,255,255,.055);
  border: 1px solid rgba(255,255,255,.075);
  color: #EDF5FD;
  font-weight: 550;
  min-height: 2.55rem;
  box-shadow: none;
}
[data-testid="stSidebar"] .stButton > button:hover {
  background: rgba(255,255,255,.13);
  border-color: rgba(255,255,255,.18);
  transform: none;
}
[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"],
[data-testid="stSidebar"] button[kind="primary"] {
  background: #FFFFFF;
  color: var(--wafa-navy) !important;
  border-color: #fff;
  font-weight: 750;
}
[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] *,
[data-testid="stSidebar"] button[kind="primary"] * { color: var(--wafa-navy) !important; }
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p { color: #C9DDF2; font-size: .76rem; }
[data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div {
  background: rgba(255,255,255,.08);
  border: 1px solid rgba(255,255,255,.14);
  color: #fff;
}
[data-testid="stSidebar"] [data-testid="stSelectbox"] svg { fill: #fff; }
[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,.12); }
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p { color: #B9D2EA; }
[data-testid="stSidebar"] .stButton > button p { color: inherit; }
.wafa-sidebar-section {
  text-transform: uppercase;
  letter-spacing: .16em;
  font-size: .64rem;
  font-weight: 750;
  color: #93B7D6 !important;
  margin: 1.25rem 0 .4rem .15rem;
}
.wafa-sidebar-user {
  display: flex; gap: .7rem; align-items: center;
  padding: .75rem .8rem; margin: .4rem 0 .9rem;
  background: rgba(255,255,255,.07);
  border: 1px solid rgba(255,255,255,.1);
  border-radius: 16px;
}
.wafa-avatar {
  width: 38px; height: 38px; border-radius: 12px;
  background: linear-gradient(135deg, #F4C66A, #D99A2B);
  color: #082A4A; font-weight: 800; font-size: .82rem;
  display: flex; align-items: center; justify-content: center;
  flex: 0 0 auto;
}
.wafa-sidebar-user strong { display:block; font-size:.88rem; line-height:1.15; color:#fff !important; }
.wafa-sidebar-user span { display:block; font-size:.72rem; color:#AFCDE7 !important; margin-top:.12rem; }
.wafa-sidebar-foot {
  margin-top: 1.4rem; padding-top: .9rem; border-top: 1px solid rgba(255,255,255,.12);
  font-size: .67rem; color: #9FC0DC !important; line-height: 1.5;
}

/* --- Logo --- */
.wafa-logo { display: flex; align-items: center; gap: .62rem; text-decoration: none; }
.wafa-logo-mark {
  width: 39px; height: 39px; border-radius: 13px;
  display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #F6D48A 0%, #D99A2B 100%);
  color: #072A4F; font-weight: 900; font-size: 1.15rem;
  box-shadow: 0 8px 18px rgba(217,154,43,.28);
  flex: 0 0 auto;
}
.wafa-logo-text { font-size: 1.32rem; font-weight: 800; letter-spacing: -.035em; color: var(--wafa-ink); line-height: 1; }
.wafa-logo-text span { color: var(--wafa-gold); }
.wafa-logo.on-dark .wafa-logo-text { color: #fff; }
.wafa-logo-slogan { font-size: .64rem; color: #9FC0DC !important; margin-top: .25rem; letter-spacing: .01em; }
.wafa-logo-wrap { margin-bottom: .6rem; }

/* --- En-tête de page --- */
.wafa-eyebrow {
  text-transform: uppercase; letter-spacing: .15em; font-size: .68rem;
  font-weight: 800; color: var(--wafa-blue); margin-bottom: .35rem;
}
.wafa-page-title { font-size: clamp(1.55rem, 2.4vw, 2.05rem); font-weight: 800; margin: 0; color: var(--wafa-ink); }
.wafa-page-subtitle { color: var(--wafa-muted); font-size: .95rem; margin: .35rem 0 1.25rem; max-width: 760px; }
.wafa-section-title { font-size: 1.08rem; font-weight: 800; color: var(--wafa-ink); margin: .2rem 0 .1rem; }
.wafa-section-subtitle { font-size: .84rem; color: var(--wafa-muted); margin-bottom: .7rem; }

/* --- Cartes --- */
.wafa-card {
  background: #fff; border: 1px solid var(--wafa-border); border-radius: 20px;
  padding: 1.15rem 1.2rem; box-shadow: 0 10px 30px rgba(11,60,110,.055);
  animation: wafaFade .32s ease both;
}
.wafa-card.tight { padding: .9rem 1rem; }
.wafa-card.flat { box-shadow: none; }
.wafa-card.gold { background: linear-gradient(145deg, #FFFDF8, #FFF5DE); border-color: #F0DFB9; }
.wafa-card.green { background: linear-gradient(145deg, #F7FEFB, #EAF9F2); border-color: #CDEBDD; }
.wafa-card.navy { background: linear-gradient(135deg, var(--wafa-navy-deep), #145A92); border: none; color: #fff; }
.wafa-card.navy * { color: #fff; }
@keyframes wafaFade { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: none; } }

.wafa-stat { min-height: 112px; }
.wafa-stat-top { display:flex; align-items:center; justify-content:space-between; gap:.6rem; }
.wafa-stat-label { font-size: .78rem; color: var(--wafa-muted); font-weight: 650; }
.wafa-stat-value { font-size: 1.6rem; font-weight: 800; letter-spacing: -.04em; color: var(--wafa-ink); margin-top: .45rem; line-height: 1.1; }
.wafa-stat-hint { font-size: .72rem; color: var(--wafa-muted); margin-top: .3rem; }
.wafa-icon {
  width: 40px; height: 40px; border-radius: 13px; display:flex; align-items:center; justify-content:center;
  flex: 0 0 auto;
}
.wafa-icon.blue { background: var(--wafa-sky); color: var(--wafa-blue); }
.wafa-icon.green { background: var(--wafa-green-soft); color: var(--wafa-green); }
.wafa-icon.gold { background: var(--wafa-gold-soft); color: #A66E08; }
.wafa-icon.red { background: var(--wafa-red-soft); color: var(--wafa-red); }
.wafa-icon.navy { background: var(--wafa-navy); color: #fff; }

/* --- Badges --- */
.wafa-badge {
  display:inline-flex; align-items:center; gap:.3rem;
  border-radius: 999px; padding: .24rem .58rem;
  font-size: .68rem; font-weight: 750; line-height: 1.25; white-space: nowrap;
}
.wafa-badge.blue { background:#E8F2FB; color:#155E8F; }
.wafa-badge.green { background:#E6F7F0; color:#0E6B4D; }
.wafa-badge.gold { background:#FFF4DC; color:#946108; }
.wafa-badge.red { background:#FDECEA; color:#A53831; }
.wafa-badge.gray { background:#F1F5F9; color:#475569; }
.wafa-badge.navy { background:rgba(255,255,255,.14); color:#fff; border:1px solid rgba(255,255,255,.18); }

/* --- Hero points --- */
.wafa-points-hero {
  position: relative; overflow: hidden;
  border-radius: 24px; padding: 1.55rem 1.65rem;
  background:
    radial-gradient(420px 220px at 92% 10%, rgba(244,198,106,.30), transparent 60%),
    radial-gradient(380px 260px at 5% 120%, rgba(74,158,217,.35), transparent 60%),
    linear-gradient(130deg, #072A4F 0%, #0B3C6E 52%, #135E96 100%);
  color: #fff; box-shadow: 0 18px 44px rgba(7,42,79,.22);
}
.wafa-points-hero::after {
  content:""; position:absolute; width: 210px; height:210px; border-radius:50%;
  border: 1px solid rgba(255,255,255,.12); right:-50px; top:-70px;
}
.wafa-points-hero .label { font-size:.74rem; text-transform:uppercase; letter-spacing:.16em; opacity:.75; font-weight:700; }
.wafa-points-hero .value { font-size: clamp(2.5rem, 5vw, 3.5rem); font-weight: 800; line-height:1; letter-spacing:-.055em; margin:.3rem 0 .15rem; }
.wafa-points-hero .value small { font-size:.95rem; font-weight:600; opacity:.7; letter-spacing:0; margin-left:.35rem; }
.wafa-points-hero .caption { font-size:.82rem; opacity:.78; }
.wafa-progress { height: 9px; border-radius:999px; background: rgba(255,255,255,.18); overflow:hidden; margin-top: 1rem; }
.wafa-progress > span { display:block; height:100%; border-radius:999px; background: linear-gradient(90deg, #F4C66A, #F7D98F); }
.wafa-progress.dark { background:#E8EEF6; }
.wafa-progress.dark > span { background: linear-gradient(90deg, var(--wafa-navy), #2E86C1); }

/* --- Divers --- */
.wafa-reward-icon {
  width: 52px; height: 52px; border-radius: 16px;
  display:flex; align-items:center; justify-content:center; font-size: 1.5rem;
  background: linear-gradient(145deg, #FFF7E6, #FCE9BF);
  border: 1px solid #F2DDAE; flex: 0 0 auto;
}
.wafa-code {
  display:block; text-align:center; font-size: 1.25rem; font-weight: 800; letter-spacing: .12em;
  background: #F8FAFD; border: 1.5px dashed #BBD0E6; border-radius: 14px;
  padding: .85rem 1rem; color: var(--wafa-navy); margin: .6rem 0;
}
.wafa-code.light { background: rgba(255,255,255,.12); border-color: rgba(255,255,255,.4); color:#fff; }
.wafa-qr-frame {
  background:#fff; border:1px solid var(--wafa-border); border-radius:24px; padding:1.1rem;
  box-shadow: 0 14px 36px rgba(11,60,110,.08);
}
.wafa-muted { color: var(--wafa-muted); font-size:.82rem; }
.wafa-small { font-size:.76rem; color: var(--wafa-muted); }
.wafa-strong { font-weight: 800; color: var(--wafa-ink); }
.wafa-divider { height:1px; background:var(--wafa-border); margin:1rem 0; }
.wafa-row { display:flex; align-items:center; justify-content:space-between; gap:.75rem; }
.wafa-pill-row { display:flex; flex-wrap:wrap; gap:.4rem; }
.wafa-empty {
  text-align:center; padding: 2.3rem 1.25rem; border: 1px dashed #C9D8E8;
  border-radius: 20px; background: rgba(255,255,255,.6);
}
.wafa-empty .icon { width:52px; height:52px; margin:0 auto .7rem; border-radius:16px; background:var(--wafa-sky); color:var(--wafa-blue); display:flex; align-items:center; justify-content:center; }
.wafa-empty h4 { margin:0 0 .25rem; font-size:1rem; }
.wafa-empty p { margin:0; color:var(--wafa-muted); font-size:.82rem; }
.wafa-notification {
  display:flex; gap:.85rem; padding:1rem 1.05rem; border-radius:16px;
  border:1px solid var(--wafa-border); background:#fff; margin-bottom:.6rem;
}
.wafa-notification.unread { border-left:4px solid var(--wafa-gold); background:#FFFDF7; }
.wafa-notification .dot { width:9px; height:9px; border-radius:50%; background:var(--wafa-gold); margin-top:.35rem; flex:0 0 auto; }
.wafa-line { display:flex; justify-content:space-between; gap:1rem; padding:.55rem 0; border-bottom:1px solid #F0F4F9; font-size:.82rem; }
.wafa-line:last-child { border-bottom:none; }
.wafa-line span:first-child { color:var(--wafa-muted); }
.wafa-review { background:#F8FAFD; border:1px solid var(--wafa-border); border-radius:16px; padding:1rem 1.1rem; }
.wafa-legal {
  margin-top: 2.2rem; padding-top: 1rem; border-top: 1px solid var(--wafa-border);
  font-size: .7rem; color: #8494A8; line-height: 1.65;
}
.wafa-legal strong { color: #5C6E84; }
.wafa-public-header { display:flex; align-items:center; justify-content:space-between; gap:1rem; padding:.4rem 0 1.1rem; }
.wafa-chip {
  display:inline-flex; align-items:center; gap:.4rem; border-radius:999px;
  padding:.35rem .7rem; background:rgba(255,255,255,.12); color:#fff;
  border:1px solid rgba(255,255,255,.18); font-size:.72rem; font-weight:650;
}
.wafa-hero {
  position:relative; overflow:hidden; border-radius:28px; padding: clamp(1.6rem, 4vw, 3.2rem);
  background:
    radial-gradient(600px 300px at 95% 0%, rgba(217,154,43,.26), transparent 60%),
    radial-gradient(600px 380px at 0% 100%, rgba(46,134,193,.30), transparent 60%),
    linear-gradient(135deg, #072A4F, #0B3C6E 55%, #135E96);
  color:#fff; box-shadow: 0 24px 60px rgba(7,42,79,.22);
}
.wafa-hero::after {
  content:""; position:absolute; width:340px; height:340px; border-radius:50%;
  border:1px solid rgba(255,255,255,.12); right:-100px; bottom:-160px;
}
.wafa-hero h1 { color:#fff; font-size: clamp(2.1rem, 5.2vw, 4rem); line-height:1.02; letter-spacing:-.055em; margin:.55rem 0 .8rem; font-weight:800; }
.wafa-hero h1 .gold { color:#F4C66A; }
.wafa-hero p { color:#D7E6F4; max-width:590px; font-size: clamp(.95rem, 1.4vw, 1.08rem); line-height:1.7; }
.wafa-hero .wafa-slogan { color:#FFF4DC; font-weight:650; font-size:.85rem; letter-spacing:.01em; }
.wafa-hero-grid { display:grid; grid-template-columns: minmax(0, 1.35fr) minmax(250px, .65fr); gap: 2.2rem; align-items:center; position:relative; z-index:1; }
.wafa-hero-chips { display:flex; flex-wrap:wrap; gap:.5rem; margin-top:1.2rem; }
.wafa-hero-chips span { display:inline-flex; gap:.4rem; align-items:center; border:1px solid rgba(255,255,255,.17); background:rgba(255,255,255,.08); border-radius:999px; padding:.38rem .66rem; font-size:.7rem; color:#E5F1FA; }
.wafa-hero-visual { position:relative; min-height: 270px; display:flex; align-items:center; justify-content:center; }
.wafa-demo-card { width: min(280px, 100%); border-radius: 22px; padding: 1.2rem; color:#0B2545; background: linear-gradient(155deg,#FFFFFF,#EEF6FD); box-shadow: 0 28px 50px rgba(0,0,0,.22); transform: rotate(-2.2deg); }
.wafa-demo-card-top { display:flex; justify-content:space-between; align-items:center; font-size:.64rem; text-transform:uppercase; letter-spacing:.12em; font-weight:800; color:#5C7894; }
.wafa-demo-dot { width:8px; height:8px; border-radius:50%; background:#12805C; }
.wafa-demo-points { font-size:2.5rem; font-weight:800; letter-spacing:-.055em; color:#0B3C6E; margin:.7rem 0 .1rem; line-height:1; }
.wafa-demo-points small { font-size:.7rem; color:#64748B; letter-spacing:0; font-weight:600; }
.wafa-demo-name { font-size:.7rem; color:#64748B; }
.wafa-demo-progress { height:6px; border-radius:999px; background:#DDEAF5; margin:.75rem 0 .9rem; overflow:hidden; }
.wafa-demo-progress span { display:block; width:66%; height:100%; border-radius:999px; background:linear-gradient(90deg,#12805C,#39B68A); }
.wafa-demo-foot { display:flex; align-items:center; gap:.55rem; background:#fff; border:1px solid #E5ECF5; border-radius:14px; padding:.55rem; }
.wafa-demo-foot strong { font-size:.66rem; }
.wafa-demo-foot span { font-size:.58rem; color:#64748B; }
.wafa-demo-qr { width:38px; height:38px; border-radius:10px; display:flex; align-items:center; justify-content:center; color:#0B3C6E; background:#E8F2FB; flex:0 0 auto; }
.wafa-demo-badge { margin-left:auto; background:#E6F7F0; color:#12805C; border-radius:8px; padding:.2rem .4rem; font-size:.65rem; font-weight:800; }
.wafa-hero-float { position:absolute; display:flex; align-items:center; gap:.4rem; border-radius:12px; background:rgba(255,255,255,.96); color:#0B2545; padding:.5rem .65rem; font-size:.64rem; font-weight:700; box-shadow:0 12px 26px rgba(0,0,0,.18); z-index:2; }
.wafa-hero-float svg { color:#D99A2B; }
.wafa-hero-float.float-a { top: 6%; left: -8%; transform: rotate(2deg); }
.wafa-hero-float.float-b { bottom: 4%; right: -5%; transform: rotate(-2deg); }
.wafa-feature { height: 100%; }
.wafa-feature h4 { font-size: .95rem; margin:.1rem 0 .3rem; }
.wafa-feature p { font-size:.8rem; color:var(--wafa-muted); line-height:1.55; margin:0; }
.wafa-step-num {
  width:34px; height:34px; border-radius:11px; display:flex; align-items:center; justify-content:center;
  background:var(--wafa-navy); color:#fff; font-weight:800; font-size:.85rem; flex:0 0 auto;
}
.wafa-cta-band {
  border-radius:24px; padding:2rem; color:#fff;
  background: radial-gradient(500px 220px at 10% 10%, rgba(217,154,43,.28), transparent 60%), linear-gradient(120deg, #0B3C6E, #135E96);
}
.wafa-cta-band h2 { color:#fff; margin:.1rem 0 .45rem; }
.wafa-cta-band p { color:#D7E6F4; }
.wafa-auth-aside {
  border-radius:24px; padding:1.7rem; color:#fff; min-height: 500px;
  background: radial-gradient(380px 260px at 100% 0%, rgba(217,154,43,.32), transparent 65%), linear-gradient(150deg, #072A4F, #0B3C6E 60%, #145A92);
}
.wafa-auth-aside h2 { color:#fff; font-size:1.5rem; line-height:1.2; }
.wafa-auth-aside p, .wafa-auth-aside li { color:#D7E6F4; font-size:.84rem; }
.wafa-demo {
  border: 1px dashed #C8D8E8; border-radius:18px; background:#F8FAFD; padding:1rem;
}
.stTabs [data-baseweb="tab-list"] { gap: .35rem; }
.stTabs [data-baseweb="tab"] { border-radius: 10px 10px 0 0; padding-left: 1rem; padding-right: 1rem; }

@media (max-width: 900px) {
  .wafa-hero-grid { grid-template-columns: 1fr; gap: 1.2rem; }
  .wafa-hero-visual { min-height: 230px; margin-top:.5rem; }
  .wafa-hero-float.float-a { left: 2%; }
  .wafa-hero-float.float-b { right: 2%; }
}
@media (max-width: 780px) {
  .block-container { padding: 1rem .85rem 3rem; }
  .wafa-hero { border-radius: 22px; }
  .wafa-hero h1 { font-size: 2.15rem; }
  .wafa-page-title { font-size: 1.55rem; }
  .wafa-stat { min-height: 96px; }
  .wafa-stat-value { font-size: 1.35rem; }
  .wafa-card { border-radius: 17px; padding: 1rem; }
  .wafa-points-hero { border-radius: 20px; padding: 1.25rem; }
  .wafa-code { font-size: 1rem; }
  .wafa-auth-aside { min-height: unset; }
}
</style>
"""


def rtl_css() -> str:
    return """
<style>
.stApp, [data-testid="stSidebar"], [data-testid="stSidebar"] *, .stMarkdown, .wafa-card, .wafa-page-title,
.wafa-page-subtitle, .wafa-hero, .wafa-auth-aside, .wafa-stat, [data-testid="stWidgetLabel"] p {
  direction: rtl;
  text-align: right;
}
html, body, .stApp, h1, h2, h3, h4, p, li, label, button, input, textarea {
  font-family: 'Noto Kufi Arabic', 'Tahoma', 'Segoe UI', sans-serif;
}
.wafa-hero h1, .wafa-page-title, .wafa-stat-value { text-align: right; }
.wafa-code, code, pre, .wafa-ltr { direction: ltr !important; text-align: center; unicode-bidi: embed; }
.wafa-logo { direction: ltr; }
.wafa-logo-slogan, .wafa-legal { text-align: right; }
.wafa-row, .wafa-line, .wafa-stat-top { flex-direction: row-reverse; }
[data-testid="stTextInput"] input[type="tel"], [data-testid="stTextInput"] input[type="email"] {
  direction: ltr; text-align: left;
}
[data-testid="stSidebar"] .stButton > button { justify-content: flex-start; text-align: right; }
.wafa-progress > span { float: right; }
.wafa-empty { text-align: center; }
</style>
"""


def inject_theme(lang: str = "fr", *, public: bool = False) -> None:
    st.markdown(BASE_CSS, unsafe_allow_html=True)
    if is_rtl(lang):
        st.markdown(rtl_css(), unsafe_allow_html=True)
    if public:
        st.markdown(
            """
<style>
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display: none !important; }
.stApp { background: #F7F9FC; }
</style>
""",
            unsafe_allow_html=True,
        )
