"""Streamlit UI for the multi-agent travel planner."""
from datetime import date, timedelta

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from config import CURRENCY_SYMBOLS, FOOD_OPTIONS, MAX_TRIP_DAYS, MODEL
from graph import NODE_LABELS, build_graph
from llm import get_api_key, get_llm
from utils import fmt_money

load_dotenv()
st.set_page_config(page_title="AI Travel Planner", page_icon="✈️", layout="wide")

MODE_ICONS = {"cab": "🚕", "metro": "🚇", "bus": "🚌"}

st.title("✈️ AI Multi-Agent Travel Planner")
st.caption(
    f"Orchestrator + specialist agents built with LangGraph "
    "Flight, hotel, fare and food prices are AI estimates — verify before booking."
)

api_key = get_api_key()
if not api_key:
    st.error("GROQ_API_KEY not found. Create a `.env` file next to app.py with "
             "`GROQ_API_KEY=your_key` and restart the app.")

# --------------------------------------------------------------------- form
with st.form("trip_form"):
    c1, c2 = st.columns(2)
    source = c1.text_input("From (source city)", "Jaipur")
    destination = c2.text_input("To (destination city)", "Goa")

    c3, c4, c5 = st.columns(3)
    start = c3.date_input("Start date", date.today() + timedelta(days=14), min_value=date.today())
    end = c4.date_input("End date", date.today() + timedelta(days=18), min_value=date.today())
    travelers = c5.number_input("Travelers", 1, 10, 2)

    c6, c7, c8 = st.columns([2, 1, 3])
    budget = c6.number_input("Max total budget", min_value=1000, value=60000, step=1000)
    currency = c7.selectbox("Currency", list(CURRENCY_SYMBOLS))
    modes = c8.multiselect(
        "In-city transport options", ["cab", "metro", "bus"], default=["cab", "metro", "bus"]
    )

    c9, c10 = st.columns(2)
    stars = c9.select_slider(
        "Hotel type (star rating)", options=[1, 2, 3, 4, 5], value=(3, 4),
        format_func=lambda s: f"{s} ★",
        help="Drag both ends. Choose the same value on both ends for exactly that star class.",
    )
    food_prefs = c10.multiselect(
        "Food preferences (scroll & select multiple)", FOOD_OPTIONS, default=["Local Specialties"],
        help="Diet types (Vegetarian, Vegan, Jain, Halal…) are treated as strict rules; "
             "cuisines pick the type of restaurants.",
    )
    submitted = st.form_submit_button("🚀 Plan my trip", type="primary", use_container_width=True)


# ------------------------------------------------------------------ run graph
def run_graph(inputs):
    graph = build_graph(get_llm(api_key))
    final = dict(inputs, logs=[], errors=[])
    with st.status("🤖 Agents are working…", expanded=True) as status:
        st.write("🧭 Orchestrator is planning…")
        for update in graph.stream(inputs, stream_mode="updates"):
            for node, out in update.items():
                for k, v in (out or {}).items():
                    if k in ("logs", "errors"):
                        final[k].extend(v)
                    else:
                        final[k] = v
                st.write("✅ " + NODE_LABELS.get(node, node))
        status.update(label="✅ Trip plan ready!", state="complete", expanded=False)
    return final


if submitted:
    if not api_key:
        st.error("Add GROQ_API_KEY to your .env file first.")
    elif not source.strip() or not destination.strip():
        st.error("Please enter source and destination.")
    elif source.strip().lower() == destination.strip().lower():
        st.error("Source and destination must be different.")
    elif end < start:
        st.error("End date must be on or after the start date.")
    elif (end - start).days + 1 > MAX_TRIP_DAYS:
        st.error(f"Please keep the trip within {MAX_TRIP_DAYS} days.")
    else:
        try:
            st.session_state["result"] = run_graph(
                {
                    "source": source.strip(),
                    "destination": destination.strip(),
                    "start_date": start.isoformat(),
                    "end_date": end.isoformat(),
                    "max_budget": float(budget),
                    "currency": currency,
                    "travelers": int(travelers),
                    "transport_modes": modes,
                    "hotel_stars": list(stars),
                    "food_preferences": food_prefs,
                }
            )
        except Exception as exc:  # noqa: BLE001
            st.error(f"Planning failed: {exc}")


# ------------------------------------------------------------------ renderers
def hhmm(minutes):
    return f"{int(minutes) // 60}h {int(minutes) % 60:02d}m"


def download_button(r, key):
    if r.get("pdf_bytes"):
        name = f"trip_plan_{r['source']}_to_{r['destination']}.pdf".replace(" ", "_")
        st.download_button("📄 Download trip plan (PDF)", r["pdf_bytes"], file_name=name,
                           mime="application/pdf", type="primary", key=key,
                           use_container_width=True)
    else:
        st.warning("PDF could not be generated (see messages above).")


def render_summary(r):
    cur = r["currency"]
    costs = r["final"]["costs"]
    st.subheader(f"{r['source']} ➜ {r['destination']}  |  {r['start_date']} → {r['end_date']}")
    m = st.columns(6)
    m[0].metric("Flights", fmt_money(costs["flights"], cur))
    m[1].metric("Hotel", fmt_money(costs["hotels"], cur))
    m[2].metric("Local transport", fmt_money(costs["local_transport"], cur))
    m[3].metric("Booked subtotal", fmt_money(costs["subtotal"], cur))
    m[4].metric("Est. food", fmt_money(costs["food_estimate"], cur))
    m[5].metric(
        "Left for activities", fmt_money(costs["left_after_food"], cur),
        delta="within budget" if costs["within_budget"] else "OVER budget",
        delta_color="normal" if costs["within_budget"] else "inverse",
    )
    st.progress(min(max(costs["subtotal"] / costs["budget"], 0.0), 1.0),
                text=f"{fmt_money(costs['subtotal'], cur)} of {fmt_money(costs['budget'], cur)} budget booked")
    if r.get("budget_notes"):
        st.info(f"🧭 Orchestrator: {r['budget_notes']}")
    st.markdown("### 🗓️ Suggested itinerary")
    st.markdown(r["final"]["itinerary_md"])


def render_flights(r):
    f, cur = r["flights"], r["currency"]
    if "error" in f:
        return st.error(f["error"])
    b = f["best"]
    st.success(f"⭐ Best flight: **{b.get('airline')}**")
    c = st.columns(4)
    c[0].metric("Total price", fmt_money(b["total_price"], cur))
    c[1].metric("Per person", fmt_money(b["price_per_person_roundtrip"], cur))
    c[2].metric("Duration", hhmm(b["duration_minutes"]))
    c[3].metric("Stops", b["stops"])
    st.write(
        f"🛫 Out: {b.get('outbound_departure')} → {b.get('outbound_arrival')}   |   "
        f"🛬 Return: {b.get('return_departure')} → {b.get('return_arrival')}"
    )
    if f.get("origin_airport") or f.get("destination_airport"):
        st.write(f"Airports: **{f.get('origin_airport')}** → **{f.get('destination_airport')}**")
    if b.get("booking_tip"):
        st.caption(f"💡 {b['booking_tip']}")
    if not f["within_budget"]:
        st.warning(f"No option fits the flight budget of {fmt_money(f['budget'], cur)}; showing closest.")
    st.markdown("**All options (cheapest first)**")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Airline": o.get("airline"),
                    "Out": f"{o.get('outbound_departure')}→{o.get('outbound_arrival')}",
                    "Return": f"{o.get('return_departure')}→{o.get('return_arrival')}",
                    "Duration": hhmm(o["duration_minutes"]),
                    "Stops": o["stops"],
                    "Per person": fmt_money(o["price_per_person_roundtrip"], cur),
                    "Total": fmt_money(o["total_price"], cur),
                    "Best": "⭐" if o.get("is_best") else "",
                }
                for o in f["options"]
            ]
        ),
        hide_index=True, use_container_width=True,
    )
    if f.get("notes"):
        st.caption(f["notes"])


def render_transport(r):
    t, cur = r["local_transport"], r["currency"]
    if "error" in t:
        return st.error(t["error"])
    if t.get("skipped"):
        return st.info(t["reason"])
    if t["best_mode"]:
        st.success(f"⭐ Best in-city option: **{MODE_ICONS.get(t['best_mode'], '')} {t['best_mode'].title()}**")
    else:
        st.warning("None of the selected modes is practical in this city.")
    cols = st.columns(len(t["modes"]) or 1)
    for col, (mode, m) in zip(cols, t["modes"].items()):
        with col, st.container(border=True):
            st.markdown(f"### {MODE_ICONS.get(mode, '')} {mode.title()}" + (" ⭐" if mode == t["best_mode"] else ""))
            if not m["available"]:
                st.error("Not available / impractical here")
            st.metric("Trip total", fmt_money(m["total_cost"], cur))
            st.caption(f"Convenience: {m['convenience_score']:.0f}/10 · "
                       f"~{fmt_money(m['daily_cost'], cur)}/day {'per cab' if mode == 'cab' else 'per person'}")
            if m.get("coverage"):
                st.write(m["coverage"])
            st.markdown("**Pros**\n" + "\n".join(f"- {p}" for p in m.get("pros", [])))
            st.markdown("**Cons**\n" + "\n".join(f"- {p}" for p in m.get("cons", [])))
            if m.get("tips"):
                st.caption(f"💡 {m['tips']}")
            if m.get("apps_or_cards"):
                st.caption("Apps/cards: " + ", ".join(m["apps_or_cards"]))
    if t.get("airport_transfer_estimate"):
        st.info(f"🛬 Airport transfer (round trip, group): ~{fmt_money(t['airport_transfer_estimate'], cur)}. "
                f"{t.get('airport_transfer_tip', '')}")


def render_hotels(r):
    h, cur = r["hotels"], r["currency"]
    if "error" in h:
        return st.error(h["error"])
    if h.get("skipped"):
        return st.info(h["reason"])
    b = h["best"]
    lo, hi = h["stars"]
    st.caption(f"Showing {lo}★ hotels only" if lo == hi else f"Showing {lo}★ to {hi}★ hotels")
    st.success(f"⭐ Best hotel: **{b['name']}** ({'★' * b['star_rating']}) — {b.get('area', '')}")
    c = st.columns(4)
    c[0].metric("Total stay", fmt_money(b["total_price"], cur))
    c[1].metric("Per night / room", fmt_money(b["price_per_night_per_room"], cur))
    c[2].metric("Guest rating", f"{b['rating']:.1f} / 5")
    c[3].metric("Rooms × nights", f"{h['rooms']} × {h['nights']}")
    st.write(b.get("why", ""))
    if b.get("amenities"):
        st.caption("Amenities: " + ", ".join(b["amenities"]))
    if not h["within_budget"]:
        st.warning(f"No hotel fits the hotel budget of {fmt_money(h['budget'], cur)}; showing closest.")
    st.markdown("**All options**")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Hotel": x["name"], "Class": "★" * x["star_rating"], "Area": x.get("area"),
                    "Guest rating": x["rating"],
                    "Per night/room": fmt_money(x["price_per_night_per_room"], cur),
                    "Total stay": fmt_money(x["total_price"], cur),
                    "To centre (km)": x.get("distance_to_center_km"),
                    "Best": "⭐" if x.get("is_best") else "",
                }
                for x in h["options"]
            ]
        ),
        hide_index=True, use_container_width=True,
    )


def render_food(r):
    f, cur = r["food"], r["currency"]
    if "error" in f:
        return st.error(f["error"])
    st.caption("Your preferences: " + ", ".join(f["preferences"]))
    st.info(f"🍴 Estimated food cost: ~{fmt_money(f['daily_food_cost_per_person'], cur)} per person per day")
    if f["local_dishes"]:
        st.markdown("### 🥘 Must-try dishes")
        for d in f["local_dishes"]:
            st.markdown(f"- **{d.get('dish', '')}** — {d.get('description', '')} _({d.get('diet', '')})_")

    def card(rest):
        with st.container(border=True):
            st.markdown(f"**{rest['name']}** · _{rest.get('cuisine', '')}_ · {rest.get('type', '')}")
            st.caption(f"📌 {rest.get('area', '')}  ·  💰 ~{fmt_money(rest['price_per_person'], cur)} per person")
            if rest["must_try"]:
                st.write("Must try: " + ", ".join(rest["must_try"]))
            st.write(rest.get("why", ""))

    shown = set()
    for pref in f["preferences"]:
        items = [x for x in f["restaurants"] if pref.lower() in [m.lower() for m in x["matches"]]]
        if not items:
            continue
        st.markdown(f"### 🍽️ {pref}")
        cols = st.columns(2)
        for i, rest in enumerate(items):
            shown.add(rest["name"])
            with cols[i % 2]:
                card(rest)
    others = [x for x in f["restaurants"] if x["name"] not in shown]
    if others:
        st.markdown("### ⭐ More recommendations")
        cols = st.columns(2)
        for i, rest in enumerate(others):
            with cols[i % 2]:
                card(rest)
    if f.get("tips"):
        st.caption("💡 " + f["tips"])


def render_weather(r):
    w = r["weather"]
    if "error" in w:
        return st.error(w["error"])
    if w["mode"] == "forecast":
        st.success(f"Live forecast for {w['location']}")
    else:
        st.info(f"Typical weather for {w['location']} (based on {w['reference_year']} data for the same dates)")
    c = st.columns(4)
    c[0].metric("Avg high", f"{w['avg_max_c']}°C")
    c[1].metric("Avg low", f"{w['avg_min_c']}°C")
    c[2].metric("Rainy days", w["rainy_days"])
    c[3].metric("Total rain", f"{w['total_rain_mm']} mm")
    df = pd.DataFrame(w["days"])
    st.line_chart(df.set_index("date")[["max_c", "min_c"]], height=240)
    st.dataframe(
        df.rename(columns={"date": "Date", "max_c": "High °C", "min_c": "Low °C",
                           "rain_mm": "Rain mm", "condition": "Condition"}),
        hide_index=True, use_container_width=True,
    )
    if w.get("advice"):
        st.markdown("**🧳 Advice**\n\n" + w["advice"])


def render_attractions(r):
    a = r["attractions"]
    if "error" in a:
        return st.error(a["error"])
    items = a["items"]
    st.subheader(f"📍 Top {len(items)} places in {r['destination']}")
    for i in range(0, len(items), 2):
        cols = st.columns(2)
        for col, it in zip(cols, items[i : i + 2]):
            with col, st.container(border=True):
                st.markdown(f"**#{it['rank']} {it['name']}**  ·  _{it.get('category', '')}_")
                st.write(it.get("description", ""))
                st.caption(
                    f"📌 {it.get('area', '')}  ·  🕒 best: {it.get('best_time', '-')}  ·  "
                    f"⏱️ ~{it.get('avg_time_hours', '-')}h  ·  🎟️ {it.get('entry_fee', '-')}"
                )


# --------------------------------------------------------------------- output
result = st.session_state.get("result")
if result:
    for e in result.get("errors", []):
        st.warning(e)
    if "final" in result:
        download_button(result, "dl_top")
        tabs = st.tabs(["📋 Summary", "✈️ Flights", "🚕 Local transport", "🏨 Hotels",
                        "🍽️ Food", "🌦️ Weather", "📍 Top 20 places"])
        with tabs[0]:
            render_summary(result)
        with tabs[1]:
            render_flights(result)
        with tabs[2]:
            render_transport(result)
        with tabs[3]:
            render_hotels(result)
        with tabs[4]:
            render_food(result)
        with tabs[5]:
            render_weather(result)
        with tabs[6]:
            render_attractions(result)
        st.divider()
        st.markdown("### 📄 Your trip plan is ready")
        download_button(result, "dl_bottom")
        with st.expander("🔍 Agent trace"):
            for line in result.get("logs", []):
                st.write("•", line)
