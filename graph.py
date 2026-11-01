"""LangGraph wiring.

                  ┌──► weather ───────┐
                  ├──► flights ───────┤
START ─► orchestrator ─► hotels ──────┤
                  ├──► transport ─────┼─► compiler ─► report (PDF) ─► END
                  ├──► attractions ───┤
                  └──► food ──────────┘
"""
from langgraph.graph import END, START, StateGraph

from agents.attractions_agent import make_attractions_agent
from agents.compiler_agent import make_compiler
from agents.flight_agent import make_flight_agent
from agents.food_agent import make_food_agent
from agents.hotel_agent import make_hotel_agent
from agents.orchestrator import make_orchestrator
from agents.report_agent import make_report_agent
from agents.transport_agent import make_transport_agent
from agents.weather_agent import make_weather_agent
from state import TravelState

NODE_LABELS = {
    "orchestrator": "🧭 Orchestrator planned the trip & budget",
    "weather": "🌦️ Weather agent finished",
    "flights": "✈️ Flight agent finished",
    "hotels": "🏨 Hotel agent finished",
    "transport": "🚕 Local transport agent finished",
    "attractions": "📍 Attractions agent finished",
    "food": "🍽️ Food agent finished",
    "compiler": "📋 Compiler built the itinerary",
    "report": "📄 PDF report generated",
}

SPECIALISTS = ["weather", "flights", "hotels", "transport", "attractions", "food"]


def build_graph(llm):
    g = StateGraph(TravelState)
    g.add_node("orchestrator", make_orchestrator(llm))
    g.add_node("weather", make_weather_agent(llm))
    g.add_node("flights", make_flight_agent(llm))
    g.add_node("hotels", make_hotel_agent(llm))
    g.add_node("transport", make_transport_agent(llm))
    g.add_node("attractions", make_attractions_agent(llm))
    g.add_node("food", make_food_agent(llm))
    g.add_node("compiler", make_compiler(llm))
    g.add_node("report", make_report_agent())

    g.add_edge(START, "orchestrator")
    for node in SPECIALISTS:             # fan-out (parallel)
        g.add_edge("orchestrator", node)
    g.add_edge(SPECIALISTS, "compiler")  # fan-in (waits for all six)
    g.add_edge("compiler", "report")
    g.add_edge("report", END)
    return g.compile()
