import os
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from deepagents import create_deep_agent
from langchain.agents.middleware import ToolCallLimitMiddleware
from langgraph.checkpoint.memory import MemorySaver

from .tools import (
    get_weather,
    analyze_seasonal_weather,
    search_google_places,
    get_route,
    search_flights,
    google_web_search,
    search_hotels,
    search_train_stations,
    search_trains,
)

load_dotenv()

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
model = ChatGoogleGenerativeAI(model=MODEL_NAME)


def now():
    return datetime.now(
        ZoneInfo("Asia/Kolkata")
    ).strftime("%Y-%m-%d %H:%M:%S %Z")


def log(message):
    print(f"[TourPlanner] {message}")


def get_text(result):
    messages = result.get("messages", [])
    if not messages:
        return str(result)

    content = getattr(messages[-1], "content", "")

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        return "\n".join(
            x.get("text", "")
            for x in content
            if isinstance(x, dict) and x.get("type") == "text"
        ).strip()

    return str(content)


# ============================================================
# WEATHER AGENT
# ============================================================

def build_weather_agent(max_tool_calls=3):
    return create_deep_agent(
        model=model,
        tools=[get_weather, analyze_seasonal_weather],
        middleware=[
            ToolCallLimitMiddleware(
                run_limit=max_tool_calls,
                exit_behavior="end",
            )
        ],
        system_prompt=f"""
You are the Weather Agent. Current time: {now()}.

ROLE
Provide factual weather information to the Main Agent.
You do NOT plan the trip.

TOOLS
- get_weather → current/exact-date weather
- analyze_seasonal_weather → historical/seasonal conditions

RULES
- Use the appropriate weather tool based on the information available.
- Exact user dates are fixed and must never be changed.
- If only a month is provided, provide seasonal weather facts.
- If no dates/month are provided, provide seasonal weather facts.
- Never choose the travel month.
- Never choose exact travel dates.
- Never choose destinations, attractions, restaurants, routes, flights, hotels or itinerary.
- Never make travel decisions.
- Never invent weather data.
- Report temperature, rainfall, risks and outdoor suitability when available.
- Return only concise, decision-useful weather information.
""",
        name="weather_agent",
    )


# ============================================================
# MAIN AGENT
# ============================================================

def build_main_agent(max_tool_calls=10):
    weather_agent = build_weather_agent(min(max_tool_calls, 3))

    return create_deep_agent(
        model=model,
        tools=[
            search_google_places,
            get_route,
            search_flights,
            search_hotels,
            get_weather,
            google_web_search,
            search_train_stations,
            search_trains,
        ],
        subagents=[
            {
                "name": "weather_agent",
                "description": (
                    "Provides factual current, exact-date and seasonal weather "
                    "information using weather tools. Never makes travel decisions."
                ),
                "runnable": weather_agent,
            },
        ],
        middleware=[
            ToolCallLimitMiddleware(
                run_limit=max_tool_calls,
                exit_behavior="end",
            )
        ],
        checkpointer=MemorySaver(),
        system_prompt = f"""
You are the Main AI Tour Planner. Current time: {now()}.

- Check weather first before planning anything.
- Understand the user's dates, duration, destination, origin, budget, transport and preferences.
- Use only the tools needed for the request and use dedicated travel tools for real data.
- Never invent, assume, or hallucinate travel information.

- Once travel dates are established, treat them as fixed.
- Use those exact dates consistently for trains, flights, hotels, routes and activities.
- Never search earlier/later dates or extend the trip to make an option work.
- If dates are missing or flexible, use weather and the trip requirements to choose a suitable period.

- If tickets are unavailable, transport is impractical, or a time constraint prevents the requested plan, report the actual result and STOP.
- Ask the user what they want to change. Do not decide, silently modify constraints, or continue searching alternatives yourself.

- For trains, use your knowledge to choose the practical rail gateway.
- Use search_train_stations only when the station code is unknown or ambiguous.
- If a direct train is unavailable, consider one practical major/nearby railway gateway based on geography.
- Do not repeatedly search station/date combinations or consume tool calls trying to force a train option.
-For Train codes use your knowledge and search_train_stations only when the station code is unknown or ambiguous.

- Use places and route tools for real locations, travel times and geographical proximity.
- Plan nearby places together and consider proximity when selecting activities, restaurants and hotels.

- For hotels and restaurants, provide 2 or more suitable options when available, with actual prices and URLs returned by the tools.
- Use booking/search tools to verify current information rather than inventing prices or availability.

- Use web search only when dedicated tools cannot provide the required information.
- Use returned URLs, map links, prices, schedules and availability where available.
- Markdown, links and emojis may be used when useful.

- Distribute tool usage across the trip. Do not spend most tool calls searching one category or exploring alternatives.
- Stop using tools once sufficient reliable information is available.
- If an important choice requires the user's preference, stop and ask.
- For round trips, always call search_trains once with both start_date and end_date.
- Never make separate train searches for outbound and return when both dates are known.

PLACES & ROUTES
- Use search_google_places to find real attractions and restaurants.
- Include the returned google_maps_url whenever available.
- Use get_route to calculate actual distance and travel time to know about the distance or proximity.
- include the returned distance and travel time whenever available or necessary.
- Group nearby places into the same day to reduce unnecessary travel.
- A route is directional; use the actual origin and destination for each required movement.
- Reuse already retrieved place information when it can answer another part of the plan. Do not repeat the same search unnecessarily.
- For food recommendations, use search_google_places and provide real returned places, prices and Google Maps URLs when available.

HOTELS
- Search hotels for the actual stay dates only.
- Provide 2 or more suitable options when available.
- Include returned price, hotel details and booking URL when available.
- Consider the hotel's geographical proximity to the planned activities and routes.

TOOL RESULTS
- Treat dedicated travel tools as the source of truth.
- Preserve returned URLs, prices, distances, travel times, schedules and availability exactly.
- Never create or modify URLs or factual values.

IMPORTANT NOTE: if you are unable to find a suitable option for a specific requirement, do not invent or assume. Instead, report the actual result and ask the user what they would like to change. Do not silently modify constraints or continue searching alternatives yourself.
""",
        name="tour_planner",
    )


# ============================================================
# PUBLIC RUNNER
# ============================================================

def run_tour_agent(message, chat_history=None, thread_id="default", max_tool_calls=15):
    history = chat_history or []

    log("=" * 70)
    log("NEW USER REQUEST")
    log(message)
    log(f"MAX TOOL CALLS: {max_tool_calls}")
    log("=" * 70)

    agent = build_main_agent(max_tool_calls)

    result = agent.invoke(
        {
            "messages": history + [
                {"role": "user", "content": message}
            ]
        },
        config={"configurable": {"thread_id": thread_id}},
    )

    log("REQUEST COMPLETED")
    log("=" * 70)

    return {
        "response": get_text(result),
        "messages": result.get("messages", []),
    }

# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    result = run_tour_agent(
        message="Plan a 4-day trip from Bengaluru to Jaipur from 12 November to 15 November 2026. I want to travel by train, explore forts, palaces, local markets and authentic Rajasthani food, stay in budget hotels, and keep daily travel within reasonable limits. Include train availability, nearby railway gateways if needed, hotel options, routes and a day-by-day itinerary.",
        max_tool_calls=20,
    )

    print("\n" + "=" * 70)
    print("AI TOUR PLANNER")
    print("=" * 70)
    print(result["response"])
    print("=" * 70)