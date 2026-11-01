"""Compiler: merges all agent outputs, checks the budget, writes the itinerary."""
from llm import ask_text

SYSTEM = """[task:itinerary]
You are a senior travel planner. Using ONLY the data given, write a concise day-by-day
itinerary in Markdown. Rules: one '### Day N - date' heading per day; group nearby
attractions (same area) on the same day; put indoor places on rainy days; keep arrival
and departure days light; for each day suggest a lunch/dinner place from the provided food
list that matches the traveler's food preferences; mention the best hotel area and the
recommended local transport mode. Use only attractions and restaurants from the provided
lists. Plain Markdown only (headings, '- ' bullets, **bold**), no emojis, no tables.
Max ~650 words."""


def make_compiler(llm):
    def compiler(state):
        flights = state.get("flights", {})
        hotels = state.get("hotels", {})
        transport = state.get("local_transport", {})
        weather = state.get("weather", {})
        attractions = state.get("attractions", {})
        food = state.get("food", {})

        flight_cost = flights.get("best", {}).get("total_price", 0)
        hotel_cost = hotels.get("best", {}).get("total_price", 0)
        transport_cost = transport.get("best_total", 0)
        spent = flight_cost + hotel_cost + transport_cost
        budget = state["max_budget"]
        left = budget - spent
        food_est = (
            food.get("daily_food_cost_per_person", 0) * state["travelers"] * state["num_days"]
        )

        costs = {
            "flights": flight_cost,
            "hotels": hotel_cost,
            "local_transport": transport_cost,
            "subtotal": spent,
            "budget": budget,
            "left_for_food_activities": left,
            "food_estimate": food_est,
            "left_after_food": left - food_est,
            "within_budget": left >= 0,
        }

        try:
            places = [
                f"{a['name']} ({a.get('area', '')}, ~{a.get('avg_time_hours', 2)}h)"
                for a in attractions.get("items", [])
            ]
            eats = [
                f"{r['name']} ({r.get('cuisine', '')}, {r.get('area', '')}, matches: {r.get('matches')})"
                for r in food.get("restaurants", [])
            ]
            itinerary = ask_text(
                llm,
                SYSTEM,
                f"Trip: {state['source']} -> {state['destination']}, {state['start_date']} to "
                f"{state['end_date']} ({state['num_days']} days), {state['travelers']} traveler(s).\n"
                f"Food preferences: {state.get('food_preferences')}\n"
                f"Best hotel: {hotels.get('best', {}).get('name', 'n/a')} "
                f"({hotels.get('best', {}).get('area', '')})\n"
                f"Best local transport: {transport.get('best_mode', 'n/a')}\n"
                f"Weather by day: {weather.get('days', 'n/a')}\n"
                f"Attractions: {places}\nRestaurants: {eats}",
            )
        except Exception as exc:  # noqa: BLE001
            itinerary = f"_Itinerary could not be generated: {exc}_"

        return {
            "final": {"costs": costs, "itinerary_md": itinerary},
            "logs": ["Compiler: merged results and built itinerary"],
        }

    return compiler
