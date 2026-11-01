from llm import ask_text
from tools.weather import get_weather
from utils import parse_date


def make_weather_agent(llm):
    def weather_agent(state):
        try:
            w = get_weather(
                state["destination"],
                parse_date(state["start_date"]),
                parse_date(state["end_date"]),
            )
            kind = (
                "real forecast"
                if w["mode"] == "forecast"
                else f"typical weather based on {w['reference_year']} data for the same dates"
            )
            try:
                w["advice"] = ask_text(
                    llm,
                    "[task:weather_advice] You are a travel weather advisor. In 3-4 short "
                    "bullet points give packing tips and the best/worst days for outdoor plans.",
                    f"City: {w['location']} ({kind}). Avg max {w['avg_max_c']}C, avg min "
                    f"{w['avg_min_c']}C, rainy days {w['rainy_days']}, total rain "
                    f"{w['total_rain_mm']}mm.\nDaily: {w['days']}",
                )
            except Exception:  # noqa: BLE001
                w["advice"] = ""
            return {"weather": w, "logs": [f"Weather agent: {kind}"]}
        except Exception as exc:  # noqa: BLE001
            return {
                "weather": {"error": str(exc)},
                "errors": [f"Weather agent failed: {exc}"],
            }

    return weather_agent
