"""
features.py  —  4 new routes for FakeGuard
──────────────────────────────────────────
  GET  /api/dashboard          Personal dashboard stats
  GET  /api/trending           Trending fake news feed
  GET  /api/bookmarks          List bookmarks
  POST /api/bookmarks/{id}     Save a bookmark
  DEL  /api/bookmarks/{id}     Remove a bookmark
  GET  /api/export/{id}        Download PDF report

Add to main.py:
    from features import router as feat_router
    app.include_router(feat_router)

Add to requirements.txt:
    reportlab>=4.0.0
"""

import io
from collections import Counter
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

import models
from database import get_db
from auth import get_current_user

# ── ReportLab ─────────────────────────────────────────────────────────────
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table,
    TableStyle, HRFlowable,
)
from reportlab.graphics.shapes import Drawing, Rect, String, Wedge
from reportlab.graphics import renderPDF

router = APIRouter()


# ══════════════════════════════════════════════════════════════════════════
# 1.  PERSONAL DASHBOARD
# ══════════════════════════════════════════════════════════════════════════

@router.get("/api/dashboard")
def dashboard(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(models.NewsCheck)
        .filter(models.NewsCheck.user_id == current_user.id)
        .order_by(models.NewsCheck.checked_at.desc())
        .all()
    )

    total     = len(rows)
    fake      = sum(1 for r in rows if r.final_verdict == "FAKE")
    real      = sum(1 for r in rows if r.final_verdict == "REAL")
    uncertain = total - fake - real
    today     = datetime.utcnow().date()

    # ── Checks per day – last 30 days ─────────────────────────────────────
    day_counter = Counter()
    for r in rows:
        diff = (today - r.checked_at.date()).days
        if diff <= 29:
            day_counter[diff] += 1

    checks_by_day = [
        {
            "date":  (today - timedelta(days=i)).strftime("%b %d"),
            "count": day_counter.get(i, 0),
        }
        for i in range(29, -1, -1)
    ]

    # ── Verdict trend – last 14 days ──────────────────────────────────────
    trend_counter: dict[int, Counter] = {}
    for r in rows:
        diff = (today - r.checked_at.date()).days
        if diff <= 13:
            if diff not in trend_counter:
                trend_counter[diff] = Counter()
            trend_counter[diff][r.final_verdict] += 1

    verdict_trend = [
        {
            "date":  (today - timedelta(days=i)).strftime("%b %d"),
            "fake":  trend_counter.get(i, Counter())["FAKE"],
            "real":  trend_counter.get(i, Counter())["REAL"],
        }
        for i in range(13, -1, -1)
    ]

    # ── Streak ────────────────────────────────────────────────────────────
    check_dates = sorted({r.checked_at.date() for r in rows}, reverse=True)
    streak = 0
    for i, d in enumerate(check_dates):
        if (today - d).days == i:
            streak += 1
        else:
            break

    # ── Bookmarked check ids ──────────────────────────────────────────────
    bm_ids = {b.check_id for b in db.query(models.Bookmark)
              .filter(models.Bookmark.user_id == current_user.id).all()}

    # ── Recent ────────────────────────────────────────────────────────────
    recent = [
        {
            "id":            r.id,
            "snippet":       r.news_text[:80] + "…",
            "final_verdict": r.final_verdict,
            "ml_confidence": round((r.ml_confidence or 0) * 100, 1),
            "checked_at":    r.checked_at.isoformat(),
            "bookmarked":    r.id in bm_ids,
        }
        for r in rows[:12]
    ]

    return {
        "total": total, "fake": fake, "real": real, "uncertain": uncertain,
        "checks_by_day":  checks_by_day,
        "verdict_trend":  verdict_trend,
        "recent":         recent,
        "streak":         streak,
        "member_since":   current_user.created_at.strftime("%B %Y"),
    }


# ══════════════════════════════════════════════════════════════════════════
# 2.  TRENDING FAKE NEWS FEED
# ══════════════════════════════════════════════════════════════════════════

@router.get("/api/trending")
def trending(
    hours: int = 24,
    db: Session = Depends(get_db),
):
    since = datetime.utcnow() - timedelta(hours=hours)
    rows  = (
        db.query(models.NewsCheck)
        .filter(models.NewsCheck.checked_at >= since)
        .all()
    )

    if not rows:
        return {"trending": [], "stats": {"total_checks": 0, "fake_pct": 0}}

    # Group by 80-char fingerprint
    groups: dict[str, dict] = {}
    for r in rows:
        key = r.news_text[:80].strip().lower()
        if key not in groups:
            groups[key] = {
                "snippet":  r.news_text[:110] + ("…" if len(r.news_text) > 110 else ""),
                "verdicts": Counter(),
                "checks":   0,
                "latest":   r.checked_at,
            }
        groups[key]["verdicts"][r.final_verdict] += 1
        groups[key]["checks"]  += 1
        if r.checked_at > groups[key]["latest"]:
            groups[key]["latest"] = r.checked_at

    sorted_groups = sorted(groups.values(), key=lambda x: -x["checks"])[:20]

    trending_list = []
    for g in sorted_groups:
        v = g["verdicts"]
        dominant = v.most_common(1)[0][0] if v else "UNCERTAIN"
        trending_list.append({
            "snippet":          g["snippet"],
            "check_count":      g["checks"],
            "dominant_verdict": dominant,
            "fake_count":       v["FAKE"],
            "real_count":       v["REAL"],
            "uncertain_count":  v["UNCERTAIN"],
            "last_checked":     g["latest"].isoformat(),
        })

    total   = len(rows)
    fake_ct = sum(1 for r in rows if r.final_verdict == "FAKE")
    return {
        "trending":     trending_list,
        "period_hours": hours,
        "stats": {
            "total_checks": total,
            "fake_pct":     round(fake_ct / total * 100, 1) if total else 0,
            "fake_count":   fake_ct,
            "real_count":   sum(1 for r in rows if r.final_verdict == "REAL"),
        },
    }


# ══════════════════════════════════════════════════════════════════════════
# 3.  BOOKMARKS
# ══════════════════════════════════════════════════════════════════════════

@router.get("/api/bookmarks")
def get_bookmarks(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bms = (
        db.query(models.Bookmark)
        .filter(models.Bookmark.user_id == current_user.id)
        .order_by(models.Bookmark.saved_at.desc())
        .all()
    )
    result = []
    for b in bms:
        c = b.check
        if c:
            result.append({
                "bookmark_id":   b.id,
                "check_id":      b.check_id,
                "note":          b.note,
                "saved_at":      b.saved_at.isoformat(),
                "snippet":       c.news_text[:110] + "…",
                "final_verdict": c.final_verdict,
                "ml_confidence": round((c.ml_confidence or 0) * 100, 1),
                "ai_summary":    c.ai_summary or "",
                "checked_at":    c.checked_at.isoformat(),
            })
    return result


@router.post("/api/bookmarks/{check_id}")
def add_bookmark(
    check_id: int,
    note: Optional[str] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check = db.query(models.NewsCheck).filter(
        models.NewsCheck.id == check_id,
        models.NewsCheck.user_id == current_user.id,
    ).first()
    if not check:
        raise HTTPException(404, "Check not found")

    existing = db.query(models.Bookmark).filter(
        models.Bookmark.user_id == current_user.id,
        models.Bookmark.check_id == check_id,
    ).first()
    if existing:
        return {"message": "Already bookmarked", "bookmark_id": existing.id}

    bm = models.Bookmark(user_id=current_user.id, check_id=check_id, note=note or "")
    db.add(bm); db.commit(); db.refresh(bm)
    return {"message": "Bookmarked", "bookmark_id": bm.id}


@router.delete("/api/bookmarks/{check_id}")
def remove_bookmark(
    check_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bm = db.query(models.Bookmark).filter(
        models.Bookmark.user_id == current_user.id,
        models.Bookmark.check_id == check_id,
    ).first()
    if not bm:
        raise HTTPException(404, "Bookmark not found")
    db.delete(bm); db.commit()
    return {"message": "Removed"}


# ══════════════════════════════════════════════════════════════════════════
# 4.  EXPORT PDF REPORT
# ══════════════════════════════════════════════════════════════════════════

_VC = {
    "FAKE":      colors.HexColor("#ff4a1c"),
    "REAL":      colors.HexColor("#22c55e"),
    "UNCERTAIN": colors.HexColor("#f59e0b"),
}
_VB = {
    "FAKE":      "#1a0800",
    "REAL":      "#001a08",
    "UNCERTAIN": "#1a1200",
}


def _verdict_color(v):
    return _VC.get(v or "UNCERTAIN", colors.grey)


def _pie_drawing(fake, real, uncertain, size=90):
    """SVG-style pie chart using ReportLab Drawing."""
    total = fake + real + uncertain or 1
    d     = Drawing(size, size)
    cx, cy, r = size / 2, size / 2, size / 2 - 4
    slices = [
        (real,      colors.HexColor("#22c55e")),
        (fake,      colors.HexColor("#ff4a1c")),
        (uncertain, colors.HexColor("#f59e0b")),
    ]
    import math
    angle = 0.0
    for val, col in slices:
        sweep = (val / total) * 360
        if sweep > 0:
            w = Wedge(cx, cy, r, angle, angle + sweep, fillColor=col, strokeColor=None)
            d.add(w)
        angle += sweep
    # donut hole
    from reportlab.graphics.shapes import Circle
    d.add(Circle(cx, cy, r * 0.52,
                 fillColor=colors.HexColor("#0d0d18"), strokeColor=None))
    d.add(String(cx, cy - 4, str(total),
                 fontName="Helvetica-Bold", fontSize=14,
                 fillColor=colors.HexColor("#f0ece0"), textAnchor="middle"))
    return d


def build_pdf(check: models.NewsCheck, user: models.User) -> bytes:
    buf  = io.BytesIO()
    W, H = A4
    doc  = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=22 * mm, rightMargin=22 * mm,
        topMargin=18 * mm, bottomMargin=20 * mm,
    )
    cw   = W - 44 * mm          # content width
    vc   = check.final_verdict or "UNCERTAIN"
    vcol = _verdict_color(vc)
    vbg  = colors.HexColor(_VB.get(vc, "#111118"))

    # ── Styles ────────────────────────────────────────────────────────────
    s = getSampleStyleSheet()

    def sty(name, **kw):
        return ParagraphStyle(name, **kw)

    ttl  = sty("T",  fontName="Helvetica-Bold", fontSize=20,
                     textColor=colors.HexColor("#f0ece0"), spaceAfter=3, leading=24)
    sub  = sty("S",  fontName="Helvetica",      fontSize=9,
                     textColor=colors.HexColor("#888888"), spaceAfter=14)
    sec  = sty("SE", fontName="Helvetica-Bold", fontSize=10,
                     textColor=colors.HexColor("#cccccc"), spaceAfter=7, spaceBefore=12)
    bod  = sty("B",  fontName="Helvetica",      fontSize=10,
                     textColor=colors.HexColor("#dddddd"), spaceAfter=8, leading=15)
    sml  = sty("SM", fontName="Helvetica",      fontSize=8,
                     textColor=colors.HexColor("#aaaaaa"), spaceAfter=5, leading=12)
    verd = sty("V",  fontName="Helvetica-Bold", fontSize=26,
                     textColor=vcol, spaceAfter=4, leading=30)
    note = sty("N",  fontName="Helvetica-Oblique", fontSize=7,
                     textColor=colors.HexColor("#666666"), leading=10)

    story = []

    # ── Top accent bar ────────────────────────────────────────────────────
    bar = Drawing(cw, 10)
    bar.add(Rect(0, 0, cw, 10, fillColor=colors.HexColor("#ff4a1c"), strokeColor=None))
    bar.add(String(8, 2, "FAKEGUARD  ·  AI-POWERED FACT CHECK REPORT",
                   fontName="Helvetica-Bold", fontSize=7,
                   fillColor=colors.white))
    bar.add(String(cw - 6, 2,
                   datetime.utcnow().strftime("Generated %d %b %Y %H:%M UTC"),
                   fontName="Helvetica", fontSize=6,
                   fillColor=colors.HexColor("#ffccaa"), textAnchor="end"))
    story.append(bar)
    story.append(Spacer(1, 8 * mm))

    # ── Title block ───────────────────────────────────────────────────────
    story.append(Paragraph("Fact-Check Report", ttl))
    story.append(Paragraph(
        f"User: <b>{user.username}</b>  ·  "
        f"Check #<b>{check.id}</b>  ·  "
        f"{check.checked_at.strftime('%d %B %Y, %H:%M')} UTC",
        sub,
    ))
    story.append(HRFlowable(width=cw, thickness=1,
                             color=colors.HexColor("#2a2a3a"), spaceAfter=10))

    # ── Verdict banner ────────────────────────────────────────────────────
    icon = {"FAKE": "FAKE NEWS DETECTED", "REAL": "VERIFIED REAL",
            "UNCERTAIN": "VERDICT UNCERTAIN"}.get(vc, vc)

    pie = _pie_drawing(
        fake      = sum(1 for _ in [check] if check.ml_verdict == "FAKE"),
        real      = sum(1 for _ in [check] if check.ml_verdict == "REAL"),
        uncertain = sum(1 for _ in [check] if (check.ml_verdict or "") not in ("FAKE","REAL")),
        size=80,
    )

    vt = Table(
        [[
            [Paragraph(icon, verd),
             Paragraph(f"Combined score: {round((check.final_score or 0)*100, 1)}%", sml)],
            [Paragraph("ML Confidence", sml),
             Paragraph(f"{round((check.ml_confidence or 0)*100,1)}%",
                       sty("MC", fontName="Helvetica-Bold", fontSize=18,
                           textColor=_verdict_color(check.ml_verdict), leading=22))],
            [Paragraph("AI Confidence", sml),
             Paragraph(f"{check.ai_confidence or '—'}%",
                       sty("AC", fontName="Helvetica-Bold", fontSize=18,
                           textColor=_verdict_color(check.ai_verdict), leading=22))],
        ]],
        colWidths=[cw * 0.42, cw * 0.28, cw * 0.30],
    )
    vt.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), vbg),
        ("BOX",           (0, 0), (-1, -1), 1.5, vcol),
        ("LINEAFTER",     (0, 0), (1, -1),  0.4, colors.HexColor("#333344")),
        ("TOPPADDING",    (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING",   (0, 0), (-1, -1), 14),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(vt)
    story.append(Spacer(1, 7 * mm))

    # ── Engine breakdown ──────────────────────────────────────────────────
    story.append(Paragraph("Analysis Engines", sec))
    et = Table(
        [
            ["Engine", "Verdict", "Confidence", "Details"],
            [
                Paragraph("<b>🤖 ML Model</b>", sml),
                Paragraph(f"<b>{check.ml_verdict or '—'}</b>",
                          sty("mv", fontName="Helvetica-Bold", fontSize=10,
                              textColor=_verdict_color(check.ml_verdict), leading=14)),
                Paragraph(f"{round((check.ml_confidence or 0)*100, 1)}% fake  /  "
                          f"{round((check.ml_real_prob or 0)*100, 1)}% real", sml),
                Paragraph((check.ml_model_name or "—")[:55], sml),
            ],
            [
                Paragraph("<b>🧠 Claude AI</b>", sml),
                Paragraph(f"<b>{check.ai_verdict or '—'}</b>",
                          sty("av", fontName="Helvetica-Bold", fontSize=10,
                              textColor=_verdict_color(check.ai_verdict), leading=14)),
                Paragraph(f"{check.ai_confidence or '—'}%", sml),
                Paragraph("claude-sonnet (Anthropic)", sml),
            ],
        ],
        colWidths=[cw * 0.17, cw * 0.15, cw * 0.33, cw * 0.35],
    )
    et.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  colors.HexColor("#0a0a0f")),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.HexColor("#888888")),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0),  7),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.HexColor("#111118"),
                                             colors.HexColor("#0d0d14")]),
        ("BOX",           (0, 0), (-1, -1), 0.5, colors.HexColor("#2a2a3a")),
        ("INNERGRID",     (0, 0), (-1, -1), 0.3, colors.HexColor("#1e1e2e")),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(et)
    story.append(Spacer(1, 7 * mm))

    # ── AI summary ────────────────────────────────────────────────────────
    if check.ai_summary and "No AI key" not in (check.ai_summary or ""):
        story.append(Paragraph("AI Summary", sec))
        story.append(Paragraph(check.ai_summary, bod))
        story.append(Spacer(1, 4 * mm))

    # ── Analyzed text ─────────────────────────────────────────────────────
    story.append(Paragraph("Analyzed Text", sec))
    preview = check.news_text[:1400]
    if len(check.news_text) > 1400:
        preview += "… [truncated]"
    story.append(Paragraph(
        preview.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"),
        bod,
    ))
    story.append(Spacer(1, 6 * mm))

    # ── Disclaimer ────────────────────────────────────────────────────────
    story.append(HRFlowable(width=cw, thickness=0.5,
                             color=colors.HexColor("#222233"), spaceAfter=5))
    story.append(Paragraph(
        "This report is generated by FakeGuard using ML and Claude AI. "
        "Results are probabilistic — always verify through multiple credible sources.",
        note,
    ))

    # ── Page footer ───────────────────────────────────────────────────────
    def footer(canvas_obj, _doc):
        canvas_obj.saveState()
        canvas_obj.setFont("Helvetica", 7)
        canvas_obj.setFillColor(colors.HexColor("#555566"))
        canvas_obj.drawString(22 * mm, 13 * mm, "FakeGuard  ·  AI-Powered Fact Checking")
        canvas_obj.drawRightString(W - 22 * mm, 13 * mm,
                                    f"Page {_doc.page}  ·  fakeguard.app")
        canvas_obj.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


@router.get("/api/export/{check_id}")
def export_pdf(
    check_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check = db.query(models.NewsCheck).filter(
        models.NewsCheck.id == check_id,
        models.NewsCheck.user_id == current_user.id,
    ).first()
    if not check:
        raise HTTPException(404, "Check not found")

    pdf = build_pdf(check, current_user)
    fname = f"fakeguard_{check_id}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
