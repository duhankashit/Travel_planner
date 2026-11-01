"""Builds the downloadable trip-plan PDF (reportlab, no external services)."""
import io
import re
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, HRFlowable, KeepTogether,
                                PageTemplate, Paragraph, Spacer, Table, TableStyle)

from utils import fmt_money

# ------------------------------------------------------------------ fonts
FONT_DIR = Path(__file__).parent / "fonts"
try:
    pdfmetrics.registerFont(TTFont("DejaVu", str(FONT_DIR / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(FONT_DIR / "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold",
                                  italic="DejaVu", boldItalic="DejaVu-Bold")
    BASE, BOLD, FONT_OK = "DejaVu", "DejaVu-Bold", True
except Exception:  # noqa: BLE001  (fallback keeps PDF working, symbols get ASCII-fied)
    BASE, BOLD, FONT_OK = "Helvetica", "Helvetica-Bold", False

# ------------------------------------------------------------------ palette
NAVY = colors.HexColor("#12355B")
TEAL = colors.HexColor("#1B998B")
LIGHT = colors.HexColor("#EEF5F9")
ZEBRA = colors.HexColor("#F7FAFC")
GREEN_BG = colors.HexColor("#E6F6EF")
AMBER_BG = colors.HexColor("#FFF4DB")
GRID = colors.HexColor("#D3DEE8")
GREY = colors.HexColor("#5B6B7B")

PAGE_W, PAGE_H = A4
MARGIN = 15 * mm
CONTENT_W = PAGE_W - 2 * MARGIN

_EMOJI = re.compile("[\U0001F000-\U0001FFFF\u2600-\u26FF\u2700-\u27BF\u2B00-\u2BFF"
                    "\uFE00-\uFE0F\u200d\u2300-\u23FF]")


def clean(text) -> str:
    """Strip emoji (no glyphs in PDF fonts); ASCII-fy symbols if font is missing."""
    t = _EMOJI.sub("", "" if text is None else str(text))
    if not FONT_OK:
        t = (t.replace("₹", "Rs. ").replace("→", "->").replace("•", "-")
              .replace("°", " deg ").replace("–", "-").replace("—", "-"))
    return re.sub(r"[ \t]+", " ", t).strip()


def inline(text) -> str:
    t = escape(clean(text))
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    return t.replace("*", "")


# ------------------------------------------------------------------ styles
def S(name, **kw):
    base = dict(fontName=BASE, fontSize=9.5, leading=13, textColor=colors.HexColor("#1F2933"))
    base.update(kw)
    return ParagraphStyle(name, **base)


ST = {
    "body": S("body"),
    "small": S("small", fontSize=8, leading=10.5, textColor=GREY),
    "cell": S("cell", fontSize=8, leading=10),
    "cellb": S("cellb", fontSize=8, leading=10, fontName=BOLD),
    "head": S("head", fontSize=8, leading=10, fontName=BOLD, textColor=colors.white),
    "h1": S("h1", fontSize=14, leading=18, fontName=BOLD, textColor=NAVY, spaceBefore=10, spaceAfter=2),
    "h2": S("h2", fontSize=10.5, leading=14, fontName=BOLD, textColor=TEAL, spaceBefore=8, spaceAfter=2),
    "day": S("day", fontSize=10.5, leading=14, fontName=BOLD, textColor=NAVY, spaceBefore=8, spaceAfter=2),
    "bullet": S("bullet", leftIndent=12, bulletIndent=2, spaceAfter=1.5),
    "title": S("title", fontSize=24, leading=28, fontName=BOLD, textColor=colors.white),
    "sub": S("sub", fontSize=10.5, leading=15, textColor=colors.HexColor("#D8E8F3")),
}


def P(text, style="body"):
    return Paragraph(inline(text), ST[style])


# ------------------------------------------------------------------ building blocks
def section(title):
    head, rule = P(title, "h1"), HRFlowable(width="100%", thickness=1.2, color=TEAL, spaceAfter=5)
    head.keepWithNext = 1   # never leave a heading alone at the bottom of a page
    rule.keepWithNext = 1
    return [head, rule]


def table(header, rows, widths, align_right=()):
    data = [[P(h, "head") for h in header]]
    for row in rows:
        data.append([c if not isinstance(c, (str, int, float)) else P(c, "cell") for c in row])
    widths = [w * CONTENT_W for w in widths]
    t = Table(data, colWidths=widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, GRID),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), ZEBRA))
    t.setStyle(TableStyle(style))
    return t


def highlight(lines, bg=GREEN_BG, edge=TEAL):
    t = Table([[[P(l, s) for l, s in lines]]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("LINEBEFORE", (0, 0), (0, -1), 3, edge),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return t


def kv_table(pairs):
    data = [[P(k, "cellb"), P(v, "cell")] for k, v in pairs]
    t = Table(data, colWidths=[0.28 * CONTENT_W, 0.72 * CONTENT_W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), LIGHT),
        ("GRID", (0, 0), (-1, -1), 0.4, GRID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def md_to_flow(md):
    out = []
    for raw in (md or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            out.append(P(line.lstrip("#").strip(), "day"))
        elif line[:2] in ("- ", "* "):
            out.append(Paragraph(inline(line[2:]), ST["bullet"], bulletText="•" if FONT_OK else "-"))
        else:
            out.append(P(line))
    return out


def hm(minutes):
    return f"{int(minutes) // 60}h {int(minutes) % 60:02d}m"


# ------------------------------------------------------------------ page decorations
def _decorate(source, dest):
    def draw(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(GRID)
        canvas.line(MARGIN, 12 * mm, PAGE_W - MARGIN, 12 * mm)
        canvas.setFont(BASE, 7.5)
        canvas.setFillColor(GREY)
        canvas.drawString(MARGIN, 8 * mm, clean(f"AI Travel Planner  |  {source} to {dest}"))
        canvas.drawRightString(PAGE_W - MARGIN, 8 * mm, f"Page {doc.page}")
        canvas.restoreState()
    return draw


# ------------------------------------------------------------------ main builder
def build_pdf(state: dict) -> bytes:
    cur = state["currency"]
    m = lambda x: clean(fmt_money(x, cur))  # noqa: E731
    src, dst = state["source"], state["destination"]
    story = []

    # ---- title block
    title = Table(
        [[[P(f"{src}  →  {dst}", "title"),
           Spacer(1, 4),
           P(f"{state['start_date']}  to  {state['end_date']}   |   {state['num_days']} days, "
             f"{state['num_nights']} nights   |   {state['travelers']} traveler(s)", "sub"),
           P(f"Generated {datetime.now():%d %b %Y}", "sub")]]],
        colWidths=[CONTENT_W],
    )
    title.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("LINEBELOW", (0, 0), (-1, -1), 4, TEAL),
        ("LEFTPADDING", (0, 0), (-1, -1), 16),
        ("TOPPADDING", (0, 0), (-1, -1), 18),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
    ]))
    story += [title, Spacer(1, 8)]

    # ---- snapshot
    lo, hi = sorted(state.get("hotel_stars") or [3, 4])
    story += section("Trip snapshot")
    story.append(kv_table([
        ("Route", f"{src} to {dst}"),
        ("Dates", f"{state['start_date']} to {state['end_date']} ({state['num_days']} days)"),
        ("Travelers", str(state["travelers"])),
        ("Max budget", m(state["max_budget"])),
        ("Hotel class", f"{lo}-star" if lo == hi else f"{lo} to {hi} star"),
        ("Food preferences", ", ".join(state.get("food_preferences") or ["Any"])),
        ("In-city transport", ", ".join(state.get("transport_modes") or ["None"])),
    ]))

    # ---- budget
    final = state.get("final", {})
    c = final.get("costs", {})
    if c:
        story += section("Budget summary")
        story.append(table(
            ["Item", "Estimated cost"],
            [
                ["Best flight (round trip, all travelers)", m(c["flights"])],
                ["Best hotel (all rooms, all nights)", m(c["hotels"])],
                ["Local transport + airport transfer", m(c["local_transport"])],
                [P("Booked subtotal", "cellb"), P(m(c["subtotal"]), "cellb")],
                ["Left from your budget", m(c["left_for_food_activities"])],
                ["Estimated food cost", m(c["food_estimate"])],
                [P("Left for activities & shopping", "cellb"), P(m(c["left_after_food"]), "cellb")],
            ],
            [0.68, 0.32],
        ))
        story.append(Spacer(1, 5))
        ok = c["within_budget"]
        story.append(highlight(
            [(("Within budget of " if ok else "OVER budget of ") + m(c["budget"]), "cellb")],
            GREEN_BG if ok else AMBER_BG, TEAL if ok else colors.HexColor("#E09F1F"),
        ))
        if state.get("budget_notes"):
            story.append(Spacer(1, 3))
            story.append(P("Budget split note: " + state["budget_notes"], "small"))

    # ---- itinerary
    if final.get("itinerary_md"):
        story += section("Day-by-day itinerary")
        story += md_to_flow(final["itinerary_md"])

    # ---- flights
    fl = state.get("flights", {})
    story += section("Flights")
    if "best" in fl:
        b = fl["best"]
        story.append(highlight([
            (f"Best flight: {b.get('airline')}", "h2"),
            (f"Total {m(b['total_price'])}  ({m(b['price_per_person_roundtrip'])} per person, round trip)", "body"),
            (f"Out {b.get('outbound_departure')} → {b.get('outbound_arrival')}   |   Return "
             f"{b.get('return_departure')} → {b.get('return_arrival')}   |   {hm(b['duration_minutes'])}, "
             f"{b['stops']} stop(s)", "body"),
            (f"Airports: {fl.get('origin_airport', '')} → {fl.get('destination_airport', '')}", "small"),
        ]))
        story.append(Spacer(1, 6))
        story.append(table(
            ["Airline", "Outbound", "Return", "Duration", "Stops", "Per person", "Total"],
            [[o.get("airline") + (" (best)" if o.get("is_best") else ""),
              f"{o.get('outbound_departure')} → {o.get('outbound_arrival')}",
              f"{o.get('return_departure')} → {o.get('return_arrival')}",
              hm(o["duration_minutes"]), o["stops"],
              m(o["price_per_person_roundtrip"]), m(o["total_price"])] for o in fl["options"]],
            [0.2, 0.17, 0.17, 0.11, 0.07, 0.14, 0.14],
        ))
        if not fl.get("within_budget"):
            story.append(P("No flight fit the flight budget; closest options shown.", "small"))
    else:
        story.append(P(fl.get("error", "Flight data not available.")))

    # ---- hotels
    ho = state.get("hotels", {})
    story += section("Hotels")
    if "best" in ho:
        b = ho["best"]
        story.append(highlight([
            (f"Best hotel: {b['name']}  ({b['star_rating']}-star, {b.get('area', '')})", "h2"),
            (f"{m(b['price_per_night_per_room'])} per night per room  |  {ho['rooms']} room(s) x "
             f"{ho['nights']} night(s) = {m(b['total_price'])}", "body"),
            (f"Guest rating {b['rating']:.1f}/5   |   {b.get('distance_to_center_km', '-')} km from centre", "body"),
            (b.get("why", ""), "small"),
            ("Amenities: " + ", ".join(b.get("amenities", [])), "small"),
        ]))
        story.append(Spacer(1, 6))
        story.append(table(
            ["Hotel", "Class", "Area", "Rating", "Per night/room", "Total stay"],
            [[h["name"] + (" (best)" if h.get("is_best") else ""), f"{h['star_rating']}-star",
              h.get("area", ""), f"{h['rating']:.1f}", m(h["price_per_night_per_room"]),
              m(h["total_price"])] for h in ho["options"]],
            [0.28, 0.1, 0.2, 0.09, 0.17, 0.16],
        ))
        if not ho.get("within_budget"):
            story.append(P("No hotel fit the hotel budget; closest options shown.", "small"))
    else:
        story.append(P(ho.get("reason") or ho.get("error", "Hotel data not available.")))

    # ---- local transport
    tr = state.get("local_transport", {})
    story += section("Local transport")
    if tr.get("modes"):
        if tr.get("best_mode"):
            story.append(highlight([(f"Best in-city option: {tr['best_mode'].title()}", "h2")]))
            story.append(Spacer(1, 6))
        rows = []
        for mode, v in tr["modes"].items():
            unit = "per cab/day" if mode == "cab" else "per person/day"
            rows.append([
                mode.title() + (" (best)" if mode == tr.get("best_mode") else ""),
                "Yes" if v["available"] else "No",
                f"{m(v['daily_cost'])} {unit}", m(v["total_cost"]),
                f"{v['convenience_score']:.0f}/10",
                "; ".join(v.get("pros", [])[:2]) or v.get("coverage", ""),
            ])
        story.append(table(["Mode", "Available", "Cost", "Trip total", "Comfort", "Highlights"],
                           rows, [0.12, 0.125, 0.2, 0.125, 0.115, 0.315]))
        for mode, v in tr["modes"].items():
            if v.get("tips"):
                story.append(P(f"{mode.title()} tip: {v['tips']}", "small"))
        if tr.get("airport_transfer_estimate"):
            story.append(Spacer(1, 3))
            story.append(P(f"Airport transfer (round trip, group): ~{m(tr['airport_transfer_estimate'])}. "
                           f"{tr.get('airport_transfer_tip', '')}", "small"))
    else:
        story.append(P(tr.get("reason") or tr.get("error", "Not available.")))

    # ---- food
    fo = state.get("food", {})
    story += section("Where to eat")
    if fo.get("restaurants"):
        story.append(P("Preferences: " + ", ".join(fo["preferences"]) +
                       f"   |   Estimated food cost ~{m(fo['daily_food_cost_per_person'])} per person per day", "small"))
        if fo.get("local_dishes"):
            story.append(P("Must-try dishes", "h2"))
            for d in fo["local_dishes"]:
                story.append(Paragraph(inline(f"**{d.get('dish', '')}** - {d.get('description', '')}"),
                                       ST["bullet"], bulletText="•" if FONT_OK else "-"))
        story.append(P("Recommended places", "h2"))
        story.append(table(
            ["Place", "Cuisine / type", "Matches", "Must try", "Per person"],
            [[Paragraph(inline(f"**{r['name']}**<br/>{r.get('area', '')}".replace("<br/>", " | ")), ST["cell"]),
              f"{r.get('cuisine', '')} ({r.get('type', '')})", ", ".join(r["matches"]),
              ", ".join(r["must_try"]), m(r["price_per_person"])] for r in fo["restaurants"]],
            [0.22, 0.2, 0.18, 0.28, 0.12],
        ))
        if fo.get("tips"):
            story.append(Spacer(1, 3))
            story.append(P("Tip: " + fo["tips"], "small"))
    else:
        story.append(P(fo.get("error", "Food data not available.")))

    # ---- weather
    w = state.get("weather", {})
    story += section("Weather")
    if w.get("days"):
        src_txt = ("Live forecast" if w["mode"] == "forecast"
                   else f"Typical weather based on {w['reference_year']} data for the same dates")
        story.append(P(f"{w['location']}  |  {src_txt}", "small"))
        story.append(P(f"Average high {w['avg_max_c']} °C, average low {w['avg_min_c']} °C, "
                       f"{w['rainy_days']} rainy day(s), {w['total_rain_mm']} mm total rain."))
        story.append(Spacer(1, 4))
        story.append(table(
            ["Date", "Condition", "High", "Low", "Rain"],
            [[d["date"], d["condition"], f"{d['max_c']} °C", f"{d['min_c']} °C", f"{d['rain_mm']} mm"]
             for d in w["days"]],
            [0.2, 0.34, 0.15, 0.15, 0.16],
        ))
        if w.get("advice"):
            story.append(Spacer(1, 4))
            story += md_to_flow(w["advice"])
    else:
        story.append(P(w.get("error", "Weather data not available.")))

    # ---- attractions
    at = state.get("attractions", {})
    story += section(f"Top {len(at.get('items', [])) or 20} places to visit")
    if at.get("items"):
        story.append(table(
            ["#", "Place", "Area", "Best time / duration", "Entry"],
            [[str(a["rank"]),
              Paragraph(inline(f"**{a['name']}** ({a.get('category', '')})<br/>"
                               .replace("<br/>", " - ") + a.get("description", "")), ST["cell"]),
              a.get("area", ""), f"{a.get('best_time', '-')}, ~{a.get('avg_time_hours', '-')}h",
              str(a.get("entry_fee", "-"))] for a in at["items"]],
            [0.05, 0.5, 0.15, 0.18, 0.12],
        ))
    else:
        story.append(P(at.get("error", "Attractions not available.")))

    # ---- disclaimer
    story.append(Spacer(1, 12))
    story.append(highlight([(
        "Important: flight, hotel, transport and food prices are AI-generated estimates, not live "
        "fares. Weather is from Open-Meteo. Please verify prices, timings and opening hours "
        "before booking.", "small")], AMBER_BG, colors.HexColor("#E09F1F")))

    # ---- render
    buf = io.BytesIO()
    doc = BaseDocTemplate(buf, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN,
                          topMargin=MARGIN, bottomMargin=18 * mm,
                          title=clean(f"Trip plan: {src} to {dst}"), author="AI Travel Planner")
    frame = Frame(MARGIN, 18 * mm, CONTENT_W, PAGE_H - MARGIN - 18 * mm, id="main",
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame], onPage=_decorate(src, dst))])
    doc.build(story)
    return buf.getvalue()
