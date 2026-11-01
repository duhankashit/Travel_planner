"""Offline smoke test: fake LLM + fake weather, no network or API key needed.
Run:  python -m tests.test_offline
"""
import json
from types import SimpleNamespace
from unittest.mock import patch

from graph import build_graph


class FakeLLM:
    def invoke(self, messages):
        sys_prompt, user = messages[0].content, messages[1].content
        if "[task:budget_split]" in sys_prompt:
            out = {"flights": 30, "hotels": 40, "local_transport": 10, "food_activities": 20, "notes": "ok"}
        elif "[task:flights]" in sys_prompt:
            out = {"origin_airport": "JAI", "destination_airport": "GOI", "notes": "",
                   "options": [
                       {"airline": "IndiGo", "outbound_departure": "06:00", "outbound_arrival": "09:00",
                        "return_departure": "18:00", "return_arrival": "21:00", "duration_minutes": 180,
                        "stops": 0, "price_per_person_roundtrip": "₹9,000", "booking_tip": "book early"},
                       {"airline": "Air India", "outbound_departure": "10:00", "outbound_arrival": "16:00",
                        "return_departure": "10:00", "return_arrival": "16:00", "duration_minutes": 360,
                        "stops": 1, "price_per_person_roundtrip": 7000, "booking_tip": ""}]}
        elif "[task:hotels]" in sys_prompt:
            out = {"notes": "", "hotels": [
                {"name": "Hotel A", "star_rating": 4, "area": "Calangute", "rating": 4.2,
                 "price_per_night_per_room": 3500, "amenities": ["Pool"], "why": "x", "distance_to_center_km": 2},
                {"name": "Hotel B", "star_rating": 5, "area": "Panjim", "rating": 4.8,
                 "price_per_night_per_room": 12000, "amenities": [], "why": "y", "distance_to_center_km": 1},
                {"name": "Hotel C (wrong class)", "star_rating": 2, "area": "Z", "rating": 3.0,
                 "price_per_night_per_room": 900, "amenities": [], "why": "z", "distance_to_center_km": 5}]}
        elif "[task:local_transport]" in sys_prompt:
            out = {"airport_transfer_estimate": 2000, "airport_transfer_tip": "prepaid taxi",
                   "modes": {
                       "cab": {"available": True, "daily_cost": 2000, "convenience_score": 9, "pros": ["a"], "cons": ["b"]},
                       "metro": {"available": False, "daily_cost": 0, "convenience_score": 1},
                       "bus": {"available": True, "daily_cost": 100, "convenience_score": 5}}}
        elif "[task:food]" in sys_prompt:
            out = {"daily_food_cost_per_person": 1200, "tips": "Eat early",
                   "local_dishes": [{"dish": "Veg Xacuti", "description": "spicy", "diet": "Vegetarian"}],
                   "restaurants": [{"name": "Veg Place", "area": "Panjim", "cuisine": "Goan", "type": "restaurant",
                                    "matches": ["Vegetarian"], "must_try": ["Thali"], "price_per_person": 500, "why": "pure veg"},
                                   {"name": "Pasta House", "area": "Candolim", "cuisine": "Italian", "type": "cafe",
                                    "matches": ["Italian", "Vegetarian"], "must_try": ["Penne"], "price_per_person": 700, "why": "x"}]}
        elif "[task:attractions]" in sys_prompt:
            n = int(user.split("exactly ")[1].split(" ")[0])
            start = 0 if "Do NOT repeat" not in user else 15
            out = {"attractions": [{"name": f"Place {start + i}", "category": "x", "area": "A",
                                    "description": "d", "best_time": "morning", "avg_time_hours": 2,
                                    "entry_fee": "free"} for i in range(n - (5 if start == 0 else 0))]}
        else:  # plain text calls
            return SimpleNamespace(content="### Day 1\n- stuff")
        return SimpleNamespace(content=json.dumps(out))


FAKE_WEATHER = {"location": "Goa, India", "mode": "historical", "reference_year": 2025,
                "days": [{"date": "2026-11-15", "max_c": 32, "min_c": 24, "rain_mm": 0, "condition": "☀️ Clear"}],
                "avg_max_c": 32, "avg_min_c": 24, "total_rain_mm": 0, "rainy_days": 0}


def main():
    with patch("agents.weather_agent.get_weather", return_value=dict(FAKE_WEATHER)):
        graph = build_graph(FakeLLM())
        result = graph.invoke({
            "source": "Jaipur", "destination": "Goa", "start_date": "2026-11-15",
            "end_date": "2026-11-19", "max_budget": 60000, "currency": "INR",
            "travelers": 2, "transport_modes": ["cab", "metro", "bus"],
            "hotel_stars": [4, 5], "food_preferences": ["Vegetarian", "Italian"],
        })
    assert result["flights"]["best"]["airline"], "flight missing"
    assert result["hotels"]["best"]["name"], "hotel missing"
    assert result["local_transport"]["best_mode"] in ("cab", "bus")
    assert len(result["attractions"]["items"]) == 20, len(result["attractions"]["items"])
    assert result["weather"]["avg_max_c"] == 32
    assert "costs" in result["final"]
    names = [h["name"] for h in result["hotels"]["options"]]
    assert all("wrong class" not in n for n in names), names   # star filter enforced
    assert len(result["food"]["restaurants"]) == 2
    pdf = result.get("pdf_bytes", b"")
    assert pdf[:4] == b"%PDF" and len(pdf) > 5000, "pdf missing"
    open("/tmp/test_trip.pdf", "wb").write(pdf)
    print("PDF bytes   :", len(pdf), "(saved /tmp/test_trip.pdf)")
    print("Budget split:", result["budget_split"])
    print("Best flight :", result["flights"]["best"]["airline"], result["flights"]["best"]["total_price"])
    print("Best hotel  :", result["hotels"]["best"]["name"], result["hotels"]["best"]["total_price"])
    print("Best transp.:", result["local_transport"]["best_mode"])
    print("Costs       :", result["final"]["costs"])
    print("Logs        :", *result["logs"], sep="\n  ")
    print("\nALL OFFLINE CHECKS PASSED ✅")


if __name__ == "__main__":
    main()
