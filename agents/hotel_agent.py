import math

from llm import ask_json
from utils import safe_float

SYSTEM = """[task:hotels]
You are a hotel specialist. You have NO live inventory, so propose 6 realistic hotels
(real, well-known properties where possible) in the destination with ESTIMATED nightly
rates for the given dates. EVERY hotel MUST have a star_rating (integer) inside the
requested star range - never outside it. If the range has several levels, mix them.
Include at least 2 hotels whose nightly rate is within the stated per-room cap if that is
realistic for the star level. Prefer central, well-connected areas.
Return JSON: {"notes": str, "hotels": [{"name": str, "star_rating": int, "area": str,
"rating": number (guest rating out of 5), "price_per_night_per_room": number,
"amenities": [str], "why": str, "distance_to_center_km": number}]}"""


def make_hotel_agent(llm):
    def hotel_agent(state):
        nights = state["num_nights"]
        if nights == 0:
            return {
                "hotels": {"skipped": True, "reason": "Same-day trip, no hotel needed."},
                "logs": ["Hotel agent: skipped (day trip)"],
            }
        try:
            lo, hi = sorted(state.get("hotel_stars") or [3, 4])
            travelers = state["travelers"]
            rooms = math.ceil(travelers / 2)
            budget = state["budget_split"]["hotels"]
            cap = budget / nights / rooms
            star_txt = f"{lo}-star" if lo == hi else f"{lo} to {hi} stars"
            data = ask_json(
                llm,
                SYSTEM,
                f"Destination: {state['destination']}\nRequired hotel class: {star_txt} "
                f"(star_rating between {lo} and {hi})\n"
                f"Check-in {state['start_date']}, check-out {state['end_date']} ({nights} nights)\n"
                f"Travelers: {travelers} -> {rooms} room(s). Per-room nightly cap: "
                f"{cap:,.0f} {state['currency']}. Prices in {state['currency']}.",
            )
            hotels = []
            for h in data.get("hotels", []):
                price = safe_float(h.get("price_per_night_per_room"))
                stars = int(safe_float(h.get("star_rating"), 0))
                if price <= 0 or not (lo <= stars <= hi):
                    continue  # enforce the user's star filter in code
                h["star_rating"] = stars
                h["price_per_night_per_room"] = price
                h["rating"] = safe_float(h.get("rating"), 3.5)
                h["total_price"] = price * nights * rooms
                hotels.append(h)
            if not hotels:
                raise ValueError(f"No {star_txt} hotels were returned. Try again or widen the star range.")

            affordable = [h for h in hotels if h["total_price"] <= budget]
            pool = affordable or hotels
            best = max(pool, key=lambda h: (h["rating"] + 0.3 * h["star_rating"])
                       / (h["price_per_night_per_room"] ** 0.5))
            best["is_best"] = True
            hotels.sort(key=lambda h: h["total_price"])
            return {
                "hotels": {
                    "best": best,
                    "options": hotels,
                    "rooms": rooms,
                    "nights": nights,
                    "stars": [lo, hi],
                    "budget": budget,
                    "within_budget": bool(affordable),
                    "notes": data.get("notes", ""),
                },
                "logs": [f"Hotel agent: {len(hotels)} {star_txt} options, best = {best.get('name')}"],
            }
        except Exception as exc:  # noqa: BLE001
            return {"hotels": {"error": str(exc)}, "errors": [f"Hotel agent failed: {exc}"]}

    return hotel_agent
