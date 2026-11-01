"""Central configuration."""

# The app ALWAYS uses this model.
MODEL = "openai/gpt-oss-120b"

CURRENCY_SYMBOLS = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£", "AED": "AED "}

# Default share of the total budget given to each agent (percent).
DEFAULT_BUDGET_SPLIT = {
    "flights": 35,
    "hotels": 35,
    "local_transport": 10,
    "food_activities": 20,
}

MAX_TRIP_DAYS = 14
FORECAST_HORIZON_DAYS = 15  # Open-Meteo forecast limit

# Scrollable food preference list (diet types + cuisines)
FOOD_OPTIONS = [
    "Vegetarian", "Non-Vegetarian", "Vegan", "Jain", "Halal", "Eggetarian",
    "Local Specialties", "Street Food", "North Indian", "South Indian",
    "Rajasthani", "Gujarati", "Bengali", "Punjabi", "Biryani",
    "Chinese", "Italian", "Continental", "Mexican", "Thai", "Japanese",
    "Korean", "Mediterranean", "Middle Eastern", "Seafood", "BBQ & Grills",
    "Fast Food", "Desserts & Sweets", "Cafes & Bakery",
]
DIET_TYPES = {"Vegetarian", "Non-Vegetarian", "Vegan", "Jain", "Halal", "Eggetarian"}
