# ✈️ AI Multi-Agent Travel Planner (LangGraph + Groq + Streamlit)

An orchestrator coordinates six specialist agents that run **in parallel**; a compiler
merges the results and a report agent produces a downloadable **PDF**.
The app always uses Groq's **`openai/gpt-oss-120b`** model.

```
                  ┌──► Weather agent (Open-Meteo, live) ─┐
                  ├──► Flight agent ─────────────────────┤
START ─► Orchestrator ─► Hotel agent (1-5 star filter) ──┤
                  ├──► Local transport (cab/metro/bus) ──┼─► Compiler ─► PDF report ─► END
                  ├──► Top-20 attractions agent ─────────┤
                  └──► Food agent (diet + cuisine) ──────┘
```

## Inputs
Source, destination, start/end date, travelers, max budget (+currency), in-city transport
modes, **hotel star range (1★–5★)** and **food preferences** (scrollable multi-select:
Vegetarian, Non-Veg, Vegan, Jain, Halal, Chinese, Italian, South Indian, Street Food, …).

## Setup
```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # put your GROQ_API_KEY inside
streamlit run app.py
```
The key is read from `.env` (or the `GROQ_API_KEY` environment variable / Streamlit secrets).
There is no key or model field in the UI.

Test without any API key / internet:  `python -m tests.test_offline`
(also writes a sample PDF to `/tmp/test_trip.pdf`).

## Output
Tabs: Summary (budget + itinerary), Flights, Local transport, Hotels, Food, Weather,
Top 20 places — plus a **Download trip plan (PDF)** button at the top and bottom.

## Data accuracy
* **Weather** is real data (Open-Meteo, no key needed).
* **Flights, hotels, fares, food and attractions come from the LLM** — realistic *estimates*,
  not live prices. Verify before booking.
* For live prices, swap `agents/flight_agent.py` / `agents/hotel_agent.py` for a real API
  (Amadeus, Booking, …) and keep the same return shape.

## Notes
* Groq's free tier has token-per-minute limits; six agents run at once, so a request can
  occasionally pause while the client auto-retries. If you see rate-limit errors, wait a minute
  and retry, or upgrade your Groq tier.
* The PDF uses the bundled DejaVu fonts in `fonts/` so the ₹ symbol renders correctly.

## Layout
```
app.py  graph.py  state.py  llm.py  config.py  utils.py  pdf_report.py
agents/  orchestrator, weather, flight, hotel, transport, attractions, food, compiler, report
tools/weather.py     Open-Meteo geocoding / forecast / archive
fonts/               DejaVu fonts for the PDF
tests/test_offline.py
```
