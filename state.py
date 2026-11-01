"""Shared LangGraph state."""
import operator
from typing import Annotated, Any, Dict, List, TypedDict


class TravelState(TypedDict, total=False):
    # ---- user input ----
    source: str
    destination: str
    start_date: str          # ISO yyyy-mm-dd
    end_date: str
    max_budget: float        # total trip budget
    currency: str
    travelers: int
    transport_modes: List[str]   # subset of cab / metro / bus
    hotel_stars: List[int]       # [min_star, max_star]
    food_preferences: List[str]  # diets + cuisines

    # ---- orchestrator output ----
    num_days: int
    num_nights: int
    budget_split: Dict[str, float]   # absolute amounts per category
    budget_notes: str

    # ---- specialist agent outputs (each agent writes ONLY its own key) ----
    weather: Dict[str, Any]
    flights: Dict[str, Any]
    local_transport: Dict[str, Any]
    hotels: Dict[str, Any]
    attractions: Dict[str, Any]
    food: Dict[str, Any]

    # ---- compiler / report output ----
    final: Dict[str, Any]
    pdf_bytes: bytes

    # ---- trace (merged across parallel branches) ----
    logs: Annotated[List[str], operator.add]
    errors: Annotated[List[str], operator.add]
