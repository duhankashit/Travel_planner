import math

from llm import ask_json
from utils import safe_float

SYSTEM = """[task:local_transport]
You are an in-city transport specialist. For the destination city, assess ONLY the requested
modes (cab, metro, bus). If a mode does not exist or is impractical there, set
"available": false. Use realistic local fares.
Cost rules: cab -> "daily_cost" is per VEHICLE (4 seats) for typical sightseeing use;
metro and bus -> "daily_cost" is PER PERSON per day (consider day passes/cards).
"airport_transfer_estimate" = round-trip airport<->hotel cost for the whole group by the
most sensible mode.
Return JSON: {"airport_transfer_estimate": number, "airport_transfer_tip": str,
"modes": {"<mode>": {"available": bool, "daily_cost": number, "convenience_score": 1-10,
"coverage": str, "pros": [str], "cons": [str], "tips": str,
"apps_or_cards": [str]}}}"""


def make_transport_agent(llm):
    def transport_agent(state):
        modes = state.get("transport_modes") or []
        if not modes:
            return {
                "local_transport": {"skipped": True, "reason": "No transport mode selected."},
                "logs": ["Transport agent: skipped"],
            }
        try:
            travelers, days = state["travelers"], state["num_days"]
            budget = state["budget_split"]["local_transport"]
            data = ask_json(
                llm,
                SYSTEM,
                f"City: {state['destination']}\nRequested modes: {modes}\n"
                f"Travelers: {travelers}, days: {days}. Prices in {state['currency']}.",
            )
            result = {}
            for mode in modes:
                m = (data.get("modes") or {}).get(mode)
                if not m:
                    continue
                daily = safe_float(m.get("daily_cost"))
                m["available"] = bool(m.get("available", True))
                m["convenience_score"] = safe_float(m.get("convenience_score"), 5)
                if mode == "cab":
                    m["total_cost"] = daily * math.ceil(travelers / 4) * days
                else:
                    m["total_cost"] = daily * travelers * days
                m["daily_cost"] = daily
                result[mode] = m

            usable = {k: v for k, v in result.items() if v["available"]}
            best_mode = None
            if usable:
                best_mode = max(
                    usable,
                    key=lambda k: usable[k]["convenience_score"]
                    - 4 * min(usable[k]["total_cost"] / max(budget, 1), 3),
                )
            transfer = safe_float(data.get("airport_transfer_estimate"))
            return {
                "local_transport": {
                    "modes": result,
                    "best_mode": best_mode,
                    "budget": budget,
                    "airport_transfer_estimate": transfer,
                    "airport_transfer_tip": data.get("airport_transfer_tip", ""),
                    "best_total": (usable[best_mode]["total_cost"] if best_mode else 0)
                    + transfer,
                },
                "logs": [f"Transport agent: best mode = {best_mode}"],
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "local_transport": {"error": str(exc)},
                "errors": [f"Transport agent failed: {exc}"],
            }

    return transport_agent
