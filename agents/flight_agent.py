from llm import ask_json
from utils import safe_float

SYSTEM = """[task:flights]
You are a flight-search specialist. You have NO live fare feed, so produce 5 realistic
ESTIMATED round-trip options from typical market fares for this route and season.
If a city has no airport, use the nearest airport and mention it in "notes".
Include a mix of cheap/slow and fast/expensive options, using real airlines that fly the route.
Return JSON: {"origin_airport": str, "destination_airport": str, "notes": str,
"options": [{"airline": str, "outbound_departure": "HH:MM", "outbound_arrival": "HH:MM",
"return_departure": "HH:MM", "return_arrival": "HH:MM", "duration_minutes": int,
"stops": int, "price_per_person_roundtrip": number, "booking_tip": str}]}"""


def make_flight_agent(llm):
    def flight_agent(state):
        try:
            travelers = state["travelers"]
            budget = state["budget_split"]["flights"]
            data = ask_json(
                llm,
                SYSTEM,
                f"Route: {state['source']} -> {state['destination']}\n"
                f"Depart: {state['start_date']}  Return: {state['end_date']}\n"
                f"Travelers: {travelers}. Flight budget for whole group: {budget:,.0f} "
                f"{state['currency']}. Prices must be in {state['currency']} per person.",
            )
            options = []
            for o in data.get("options", []):
                pp = safe_float(o.get("price_per_person_roundtrip"))
                if pp <= 0:
                    continue
                o["price_per_person_roundtrip"] = pp
                o["total_price"] = pp * travelers
                o["duration_minutes"] = int(safe_float(o.get("duration_minutes")))
                o["stops"] = int(safe_float(o.get("stops")))
                options.append(o)
            if not options:
                raise ValueError("No flight options returned")

            affordable = [o for o in options if o["total_price"] <= budget]
            pool = affordable or options
            prices = [o["total_price"] for o in pool]
            durs = [o["duration_minutes"] for o in pool]

            def norm(v, lo, hi):
                return (v - lo) / (hi - lo) if hi > lo else 0

            def score(o):  # lower is better
                return (
                    0.5 * norm(o["total_price"], min(prices), max(prices))
                    + 0.3 * norm(o["duration_minutes"], min(durs), max(durs))
                    + 0.2 * min(o["stops"], 2) / 2
                )

            best = min(pool, key=score)
            best["is_best"] = True
            options.sort(key=lambda o: o["total_price"])
            return {
                "flights": {
                    "best": best,
                    "options": options,
                    "budget": budget,
                    "within_budget": bool(affordable),
                    "origin_airport": data.get("origin_airport", ""),
                    "destination_airport": data.get("destination_airport", ""),
                    "notes": data.get("notes", ""),
                },
                "logs": [f"Flight agent: {len(options)} options, best = {best.get('airline')}"],
            }
        except Exception as exc:  # noqa: BLE001
            return {"flights": {"error": str(exc)}, "errors": [f"Flight agent failed: {exc}"]}

    return flight_agent
