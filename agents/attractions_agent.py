from llm import ask_json

SYSTEM = """[task:attractions]
You are a local tourism expert. List the top tourist destinations/attractions in the given
city, ranked by popularity and must-see value, mixing landmarks, culture, nature, food
and local experiences. Return JSON: {"attractions": [{"name": str, "category": str,
"area": str, "description": str (max 25 words), "best_time": str, "avg_time_hours": number,
"entry_fee": str}]}"""

TARGET = 20


def make_attractions_agent(llm):
    def attractions_agent(state):
        try:
            city = state["destination"]
            items, seen = [], set()
            for _ in range(3):
                need = TARGET - len(items)
                if need <= 0:
                    break
                exclude = f"\nDo NOT repeat: {[i['name'] for i in items]}" if items else ""
                data = ask_json(
                    llm,
                    SYSTEM,
                    f"City: {city}. Give exactly {need} attractions.{exclude}\n"
                    f"Entry fee in {state['currency']} where applicable.",
                )
                for a in data.get("attractions", []):
                    key = str(a.get("name", "")).strip().lower()
                    if key and key not in seen:
                        seen.add(key)
                        items.append(a)
            items = items[:TARGET]
            for i, a in enumerate(items, 1):
                a["rank"] = i
            return {
                "attractions": {"items": items},
                "logs": [f"Attractions agent: {len(items)} places"],
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "attractions": {"error": str(exc)},
                "errors": [f"Attractions agent failed: {exc}"],
            }

    return attractions_agent
