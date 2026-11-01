from config import DIET_TYPES
from llm import ask_json
from utils import safe_float

SYSTEM = """[task:food]
You are a local food expert. Recommend where and what to eat in the destination city,
STRICTLY following the traveler's food preferences.
Rules:
- Diet preferences (Vegetarian, Vegan, Jain, Halal, Eggetarian, Non-Vegetarian) are hard
  constraints. If the traveler chose Vegetarian/Vegan/Jain, never suggest meat or fish dishes
  or non-veg places as a match.
- Cuisine preferences (Chinese, Italian, South Indian ...) decide the type of restaurants.
- Give 2-3 real, well-known places PER selected preference (max 12 restaurants total; a place
  can match several preferences, list them in "matches").
- Also list 5 must-try local dishes that comply with the diet preferences.
- Prices in the requested currency, per person for a typical meal.
Return JSON: {"daily_food_cost_per_person": number, "tips": str,
"local_dishes": [{"dish": str, "description": str, "diet": str}],
"restaurants": [{"name": str, "area": str, "cuisine": str, "type": "restaurant|street food|cafe|fine dining",
"matches": [str], "must_try": [str], "price_per_person": number, "why": str}]}"""


def make_food_agent(llm):
    def food_agent(state):
        prefs = state.get("food_preferences") or ["Local Specialties"]
        try:
            diets = [p for p in prefs if p in DIET_TYPES]
            cuisines = [p for p in prefs if p not in DIET_TYPES]
            data = ask_json(
                llm,
                SYSTEM,
                f"City: {state['destination']}\nDiet preferences: {diets or 'none'}\n"
                f"Cuisine preferences: {cuisines or 'any local food'}\n"
                f"Travelers: {state['travelers']}, days: {state['num_days']}. "
                f"Currency: {state['currency']}.",
            )
            restaurants = []
            for r in data.get("restaurants", []):
                if not r.get("name"):
                    continue
                r["price_per_person"] = safe_float(r.get("price_per_person"))
                r["matches"] = r.get("matches") or []
                r["must_try"] = r.get("must_try") or []
                restaurants.append(r)
            if not restaurants:
                raise ValueError("No food places returned")
            return {
                "food": {
                    "preferences": prefs,
                    "restaurants": restaurants,
                    "local_dishes": data.get("local_dishes", []),
                    "daily_food_cost_per_person": safe_float(data.get("daily_food_cost_per_person")),
                    "tips": data.get("tips", ""),
                },
                "logs": [f"Food agent: {len(restaurants)} places for {', '.join(prefs)}"],
            }
        except Exception as exc:  # noqa: BLE001
            return {"food": {"error": str(exc)}, "errors": [f"Food agent failed: {exc}"]}

    return food_agent
