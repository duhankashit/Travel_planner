"""Orchestrator: validates input, plans trip length, splits the budget."""
from config import DEFAULT_BUDGET_SPLIT
from llm import ask_json
from utils import parse_date, safe_float

SYSTEM = """[task:budget_split]
You are the orchestrator of a travel-planning team. Split the user's TOTAL trip budget
into percentages for: flights, hotels, local_transport, food_activities.
Consider route distance, trip length, number of travelers and how expensive the
destination is. Percentages must be integers summing to 100.
Return JSON: {"flights": int, "hotels": int, "local_transport": int,
"food_activities": int, "notes": "one or two sentences explaining the split"}"""


def make_orchestrator(llm):
    def orchestrator(state):
        start, end = parse_date(state["start_date"]), parse_date(state["end_date"])
        if end < start:
            raise ValueError("End date must be on/after start date")
        if state["source"].strip().lower() == state["destination"].strip().lower():
            raise ValueError("Source and destination must be different")

        nights = (end - start).days
        num_days = nights + 1
        budget = float(state["max_budget"])

        split_pct, notes = dict(DEFAULT_BUDGET_SPLIT), "Default budget split used."
        try:
            data = ask_json(
                llm,
                SYSTEM,
                f"Route: {state['source']} -> {state['destination']}\n"
                f"Days: {num_days} ({nights} nights), travelers: {state['travelers']}\n"
                f"Hotel star preference: {state.get('hotel_stars', [3, 4])}\n"
                f"Total budget: {budget:,.0f} {state['currency']}",
            )
            parsed = {k: safe_float(data.get(k), -1) for k in DEFAULT_BUDGET_SPLIT}
            if all(v > 0 for v in parsed.values()):
                total = sum(parsed.values())
                split_pct = {k: v * 100 / total for k, v in parsed.items()}
                notes = data.get("notes", "")
        except Exception as exc:  # noqa: BLE001
            notes = f"Default split used (orchestrator LLM error: {exc})"

        if nights == 0:  # day trip: no hotel needed, redistribute
            extra = split_pct["hotels"]
            split_pct["hotels"] = 0
            split_pct["flights"] += extra * 0.6
            split_pct["food_activities"] += extra * 0.4

        return {
            "num_days": num_days,
            "num_nights": nights,
            "budget_split": {k: round(budget * v / 100) for k, v in split_pct.items()},
            "budget_notes": notes,
            "logs": ["Orchestrator: validated input, split budget, dispatching agents"],
        }

    return orchestrator
