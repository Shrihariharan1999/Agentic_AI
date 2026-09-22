import os
from calendar import month_name
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

import requests
from dotenv import load_dotenv
from langchain_core.tools import tool

from typing import Any
import os
import requests
from langchain_core.tools import tool


load_dotenv()

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
HISTORICAL_URL = "https://archive-api.open-meteo.com/v1/archive"
ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
SERPAPI_URL = "https://serpapi.com/search.json"


def get_coordinates(city: str) -> dict[str, Any]:
    response = requests.get(GEOCODING_URL, params={"name": city, "count": 1, "language": "en", "format": "json"}, timeout=20)
    response.raise_for_status()
    results = response.json().get("results", [])
    if not results:
        raise ValueError(f"Location not found: {city}")
    location = results[0]
    return {"name": location["name"], "country": location.get("country"), "latitude": location["latitude"], "longitude": location["longitude"], "timezone": location.get("timezone")}


def get_weather_forecast(city: str, start_date: str, end_date: str) -> dict[str, Any]:
    location = get_coordinates(city)
    response = requests.get(FORECAST_URL, params={"latitude": location["latitude"], "longitude": location["longitude"], "start_date": start_date, "end_date": end_date, "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,weather_code", "timezone": "auto"}, timeout=20)
    response.raise_for_status()
    return {"type": "forecast", "location": {"name": location["name"], "country": location["country"], "timezone": location["timezone"]}, "start_date": start_date, "end_date": end_date, "daily": response.json().get("daily", {})}


def get_historical_weather(city: str, start_date: str, end_date: str, years: int = 5) -> dict[str, Any]:
    location = get_coordinates(city)
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    current_year = date.today().year
    records = []

    for year in range(current_year - years, current_year):
        try:
            historical_start = start.replace(year=year)
            historical_end = end.replace(year=year)
        except ValueError:
            historical_start = start.replace(year=year, day=28)
            historical_end = end.replace(year=year, day=28)

        response = requests.get(HISTORICAL_URL, params={"latitude": location["latitude"], "longitude": location["longitude"], "start_date": historical_start.isoformat(), "end_date": historical_end.isoformat(), "daily": "temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum,rain_sum,precipitation_hours,wind_speed_10m_max", "timezone": "auto"}, timeout=30)
        response.raise_for_status()
        daily = response.json().get("daily", {})
        dates = daily.get("time", [])
        for i, historical_date in enumerate(dates):
            records.append({"date": historical_date, "year": year, "temp_max": daily.get("temperature_2m_max", [None])[i], "temp_min": daily.get("temperature_2m_min", [None])[i], "temp_mean": daily.get("temperature_2m_mean", [None])[i], "precipitation": daily.get("precipitation_sum", [None])[i], "rain": daily.get("rain_sum", [None])[i], "precipitation_hours": daily.get("precipitation_hours", [None])[i], "wind_speed_max": daily.get("wind_speed_10m_max", [None])[i]})

    return {"location": location, "records": records, "years_analyzed": years}


def analyze_historical_weather(data: dict[str, Any]) -> dict[str, Any]:
    records = data["records"]
    if not records:
        return {"error": "No historical weather data found."}

    def avg(field: str):
        values = [r[field] for r in records if r[field] is not None]
        return round(sum(values) / len(values), 2) if values else None

    rainy_days = sum(1 for r in records if r["rain"] is not None and r["rain"] > 1)
    return {"average_max_temperature": avg("temp_max"), "average_min_temperature": avg("temp_min"), "average_mean_temperature": avg("temp_mean"), "average_precipitation_mm": avg("precipitation"), "average_rain_mm": avg("rain"), "average_precipitation_hours": avg("precipitation_hours"), "average_wind_kmh": avg("wind_speed_max"), "rainy_day_ratio": round(rainy_days / len(records), 2), "days_analyzed": len(records), "years_analyzed": data["years_analyzed"]}


@tool
def get_weather(city: str, start_date: str, end_date: str) -> dict[str, Any]:
    """Get weather for a destination and date range.
     It provides either a real forecast (if within 16 days) or a historical/seasonal estimate (if beyond 16 days)."""
    print(f"Fetching weather for {city} from {start_date} to {end_date}")
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    today = date.today()
    forecast_limit = today + timedelta(days=16)

    if start >= today and end <= forecast_limit:
        return get_weather_forecast(city, start_date, end_date)

    historical = get_historical_weather(city, start_date, end_date)
    return {"type": "historical_estimate", "location": {"name": historical["location"]["name"], "country": historical["location"]["country"], "timezone": historical["location"]["timezone"]}, "start_date": start_date, "end_date": end_date, "analysis": analyze_historical_weather(historical), "disclaimer": "Historical/seasonal estimate, not an exact future forecast."}


def calculate_budget(budget: float, days: int, travelers: int) -> dict[str, Any]:
    allocation = {"transport": round(budget * 0.30, 2), "hotel": round(budget * 0.30, 2), "food": round(budget * 0.20, 2), "activities": round(budget * 0.15, 2), "buffer": round(budget * 0.05, 2)}
    return {"total_budget": budget, "days": days, "travelers": travelers, "per_day_budget": round(budget / days, 2), "allocation": allocation}


@tool
def search_google_places(query: str, city: str, limit: int = 5) -> dict[str, Any]:
    """Search Google Places and return compact place details.
    query: search term (e.g., museum, restaurant, park,food, attractions, etc.)
    city: city name for location context (city or the location of the trip)
    food, attractions and other places can be searched."""

    print(f"Searching Google Places for '{query}' in {city} (limit {limit})")
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_PLACES_API_KEY is not set")

    response = requests.post("https://places.googleapis.com/v1/places:searchText", headers={"Content-Type": "application/json", "X-Goog-Api-Key": api_key, "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.rating,places.userRatingCount,places.location"}, json={"textQuery": f"{query} in {city}", "maxResultCount": min(limit, 10)}, timeout=20)
    if response.status_code != 200:
        return {"error": True, "status_code": response.status_code, "message": response.text}

    places = []
    for place in response.json().get("places", []):
        name = place.get("displayName", {}).get("text")
        if not name:
            continue
        location = place.get("location", {})
        place_id = place.get("id")
        places.append({"name": name, "address": place.get("formattedAddress"), "rating": place.get("rating"), "rating_count": place.get("userRatingCount"), "google_maps_url": f"https://www.google.com/maps/search/?api=1&query=Google&query_place_id={place_id}", "latitude": location.get("latitude"), "longitude": location.get("longitude")})

    return {"query": query, "city": city, "results": places}


@tool
def analyze_seasonal_weather(city: str, years: int = 5) -> dict[str, Any]:
    """Analyze historical weather patterns by month for a city.
       It provides average temperatures, precipitation, wind speed, and rainy day ratios over the past specified years."""
    
    print(f"Analyzing seasonal weather for {city} over the past {years} years")
    if not 1 <= years <= 20:
        raise ValueError("years must be between 1 and 20")

    location = get_coordinates(city)
    end_date = date.today() - timedelta(days=1)
    start_date = date(end_date.year - years, end_date.month, end_date.day)

    response = requests.get(HISTORICAL_URL, params={"latitude": location["latitude"], "longitude": location["longitude"], "start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,rain_sum,wind_speed_10m_max", "timezone": "auto"}, timeout=60)
    response.raise_for_status()
    daily = response.json().get("daily", {})
    dates = daily.get("time", [])
    if not dates:
        return {"city": city, "error": "No historical weather data found."}

    monthly = defaultdict(list)
    for i, value in enumerate(dates):
        month = int(value.split("-")[1])
        monthly[month].append({"temp_max": daily.get("temperature_2m_max", [None])[i], "temp_min": daily.get("temperature_2m_min", [None])[i], "precipitation": daily.get("precipitation_sum", [None])[i], "rain": daily.get("rain_sum", [None])[i], "wind_speed": daily.get("wind_speed_10m_max", [None])[i]})

    def average(records, field):
        values = [r[field] for r in records if r[field] is not None]
        return round(sum(values) / len(values), 2) if values else None

    monthly_analysis = {}
    for month in range(1, 13):
        records = monthly.get(month, [])
        if not records:
            continue
        rainy_days = sum(1 for r in records if r["rain"] is not None and r["rain"] > 1)
        monthly_analysis[month_name[month]] = {"average_max_temperature": average(records, "temp_max"), "average_min_temperature": average(records, "temp_min"), "average_precipitation_mm": average(records, "precipitation"), "average_wind_kmh": average(records, "wind_speed"), "rainy_day_ratio": round(rainy_days / len(records), 2)}

    return {"type": "seasonal_historical_analysis", "city": city, "years_analyzed": years, "monthly_analysis": monthly_analysis, "disclaimer": "Historical seasonal analysis, not an exact future forecast."}


@tool
def get_route(origin: str, destination: str, travel_mode: str = "DRIVE") -> dict[str, Any]:
    """Get distance and travel time between two locations.
    It provides distance in kilometers and estimated duration in minutes based on the specified travel mode.
    origin: starting location (address or place name)
    destination: ending location (address or place name)
    travel_mode: one of DRIVE, WALK, BICYCLE, TRANSIT (default DRIVE)


    travel_mode must be one of:
    DRIVE, WALK, BICYCLE, TRANSIT.
    """
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_PLACES_API_KEY is not set")

    mode_map = {"driving": "DRIVE", "drive": "DRIVE", "walking": "WALK", "walk": "WALK", "bicycling": "BICYCLE", "bicycle": "BICYCLE", "cycling": "BICYCLE", "transit": "TRANSIT"}
    travel_mode = mode_map.get(travel_mode.lower(), travel_mode.upper())
    if travel_mode not in {"DRIVE", "WALK", "BICYCLE", "TRANSIT"}:
        raise ValueError("travel_mode must be DRIVE, WALK, BICYCLE, or TRANSIT")

    print(f"Getting route from {origin} to {destination} by {travel_mode}")
    response = requests.post(ROUTES_URL, headers={"Content-Type": "application/json", "X-Goog-Api-Key": api_key, "X-Goog-FieldMask": "routes.duration,routes.distanceMeters"}, json={"origin": {"address": origin}, "destination": {"address": destination}, "travelMode": travel_mode, "languageCode": "en-US", "units": "METRIC"}, timeout=20)
    if response.status_code != 200:
        return {"error": True, "status_code": response.status_code, "message": response.text}

    routes = response.json().get("routes", [])
    if not routes:
        return {"error": True, "message": "No route found."}

    route = routes[0]
    distance_m = route.get("distanceMeters")
    seconds = int(route.get("duration", "0s").rstrip("s"))
    return {"origin": origin, "destination": destination, "travel_mode": travel_mode, "distance_km": round(distance_m / 1000, 2) if distance_m else None, "duration_minutes": round(seconds / 60)}

def _parse_flight(flight: dict[str, Any]) -> dict[str, Any]:
    segments = flight.get("flights", [])
    if not segments: return {}
    return {"price": flight.get("price"), "airline": segments[0].get("airline"), "flight_numbers": [s.get("flight_number") for s in segments], "from": segments[0].get("departure_airport", {}).get("id"), "to": segments[-1].get("arrival_airport", {}).get("id"), "departure": segments[0].get("departure_airport", {}).get("time"), "arrival": segments[-1].get("arrival_airport", {}).get("time"), "duration_minutes": flight.get("total_duration"), "stops": len(flight.get("layovers", []))}


def _format_flight(flight: dict[str, Any]) -> dict[str, Any]:
    if not flight: return {}
    return {"airline": flight.get("airline"), "flight": ", ".join(flight.get("flight_numbers", [])), "route": f"{flight.get('from')} → {flight.get('to')}", "departure": flight.get("departure"), "arrival": flight.get("arrival"), "duration_minutes": flight.get("duration_minutes"), "stops": flight.get("stops"), "price_inr": flight.get("price")}


@tool
def search_flights(origin: str, destination: str, departure_date: str, return_date: str | None = None, adults: int = 1, travel_class: int = 1, max_results: int = 5) -> dict[str, Any]:
    """Search live Google Flights and return compact flight options.
    origin: 3-letter IATA airport code.
    destination: 3-letter IATA airport code.
    departure_date: YYYY-MM-DD.
    return_date: YYYY-MM-DD for round trip; omit for one-way.
    adults: number of passengers.
    travel_class: 1 Economy, 2 Premium Economy, 3 Business, 4 First.
    max_results: maximum flight options.
    """
    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key: raise ValueError("SERPAPI_API_KEY is not set")

    origin, destination = origin.upper(), destination.upper()
    params = {"engine": "google_flights", "departure_id": origin, "arrival_id": destination, "outbound_date": departure_date, "type": "1" if return_date else "2", "currency": "INR", "hl": "en", "gl": "in", "adults": adults, "travel_class": travel_class, "api_key": api_key}
    if return_date: params["return_date"] = return_date

    print(f"Searching flights from {origin} to {destination} departing on {departure_date}" + (f" and returning on {return_date}" if return_date else ""))

    response = requests.get(SERPAPI_URL, params=params, timeout=30)
    if response.status_code != 200: return {"error": True, "status_code": response.status_code, "message": response.text}

    data = response.json()
    outbound_raw = (data.get("best_flights", []) + data.get("other_flights", []))[:max_results]

    if not return_date:
        options = [_format_flight(_parse_flight(f)) for f in outbound_raw if _parse_flight(f)]
        return {"type": "one_way", "route": f"{origin} → {destination}", "departure_date": departure_date, "options": options}

    options = []

    for outbound in outbound_raw:
        outbound_parsed = _parse_flight(outbound)
        departure_token = outbound.get("departure_token")
        if not outbound_parsed or not departure_token: continue

        return_response = requests.get(SERPAPI_URL, params={**params, "departure_token": departure_token}, timeout=30)
        if return_response.status_code != 200: continue

        return_data = return_response.json()
        return_raw = (return_data.get("best_flights", []) + return_data.get("other_flights", []))[:max_results]

        for return_flight in return_raw:
            formatted_return = _format_flight(_parse_flight(return_flight))
            if formatted_return: options.append({"outbound": _format_flight(outbound_parsed), "return": formatted_return})

    return {"type": "round_trip", "route": f"{origin} → {destination}", "departure_date": departure_date, "return_date": return_date, "options": options[:max_results]}


@tool
def google_web_search(query: str, num_results: int = 5) -> dict[str, Any]:
    """Search the web using Google Serper.
    query: search term.
    num_results: number of results to return (max 10).
    It returns a list of top search results with title, URL, and snippet.
    use this tool for general web searches, research, and information gathering."""

    api_key = os.getenv("SERPER_API_KEY")
    if not api_key: raise ValueError("SERPER_API_KEY is not set")

    print(f"Web search: {query}, retrieving top {num_results} results")

    response = requests.post(
        "https://google.serper.dev/search",
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        json={"q": query, "num": num_results},
        timeout=20,
    )

    if response.status_code != 200:
        return {"error": True, "status_code": response.status_code, "message": response.text}

    data = response.json()

    results = [
        {
            "title": r.get("title"),
            "url": r.get("link"),
            "snippet": r.get("snippet"),
        }
        for r in data.get("organic", [])
    ]

    return {"query": query, "results": results}

@tool
def search_hotels(city: str, check_in_date: str, check_out_date: str, adults: int = 1, rooms: int = 1, max_results: int = 5, min_price: int | None = None, max_price: int | None = None, min_rating: float | None = None) -> dict[str, Any]:
    """Search Google Hotels and return structured accommodation options.
    city: city name for location context.
    check_in_date: YYYY-MM-DD.
    check_out_date: YYYY-MM-DD.
    adults: number of guests.
    rooms: number of rooms.
    max_results: maximum number of hotel options to return.
    min_price: minimum price filter in INR.
    max_price: maximum price filter in INR.
    min_rating: minimum rating filter (3.5, 4.0, 4.5).
    It returns a list of hotels with name, rating, address, price, amenities, and booking link.
    Use this tool for finding hotels, accommodations, and lodging options."""
    
    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key: raise ValueError("SERPAPI_API_KEY is not set")

    print(f"Searching hotels in {city} from {check_in_date} to {check_out_date} for {adults} adults and {rooms} rooms (limit {max_results})")

    params = {"engine": "google_hotels", "q": city, "check_in_date": check_in_date, "check_out_date": check_out_date, "adults": adults, "rooms": rooms, "currency": "INR", "gl": "in", "hl": "en", "api_key": api_key}
    if min_price is not None: params["min_price"] = min_price
    if max_price is not None: params["max_price"] = max_price
    if min_rating is not None: params["rating"] = {3.5: 7, 4.0: 8, 4.5: 9}.get(min_rating)

    response = requests.get(SERPAPI_URL, params=params, timeout=30)
    if response.status_code != 200: return {"error": True, "status_code": response.status_code, "message": response.text}

    properties = response.json().get("properties", [])[:max_results]
    results = []

    for hotel in properties:
        rate = hotel.get("rate_per_night", {})
        total = hotel.get("total_rate", {})
        results.append({
            "name": hotel.get("name"),
            "rating": hotel.get("overall_rating"),
            "reviews": hotel.get("reviews"),
            "address": hotel.get("address"),
            "price_per_night": rate.get("extracted_lowest"),
            "total_price": total.get("extracted_lowest"),
            "currency": "INR",
            "amenities": hotel.get("amenities", [])[:10],
            "check_in": hotel.get("check_in_time"),
            "check_out": hotel.get("check_out_time"),
            "latitude": hotel.get("gps_coordinates", {}).get("latitude"),
            "longitude": hotel.get("gps_coordinates", {}).get("longitude"),
            "booking_url": hotel.get("link"),
        })

    return {
        "city": city,
        "check_in": check_in_date,
        "check_out": check_out_date,
        "adults": adults,
        "rooms": rooms,
        "hotels": results,
    }

RAILRADAR_URL = "https://api.railradar.in/v1"


def _rail_headers():
    api_key = os.getenv("RAILRADAR_API_KEY")
    if not api_key:
        raise ValueError("RAILRADAR_API_KEY is not set")
    return {"Authorization": f"Bearer {api_key}"}


# ============================================================
# STATION FINDER
# ============================================================

@tool
def search_train_stations(query: str, limit: int = 5) -> dict[str, Any]:
    """Find Indian railway stations by name or station code.
    query: station name or code (e.g., 'NDLS' for New Delhi).
    limit: maximum number of stations to return (default 5, max 50).
    It returns a list of stations with code, name, and city.
    Use this tool to resolve station names or codes for train searches and availability checks.
    """
    print(f"Searching railway stations for '{query}', limit {limit}")

    response = requests.get(
        f"{RAILRADAR_URL}/lookup/search/stations",
        headers=_rail_headers(),
        params={"q": query, "limit": min(limit, 50)},
        timeout=20,
    )

    if response.status_code != 200:
        return {
            "error": True,
            "status_code": response.status_code,
            "message": response.text,
        }

    data = response.json().get("data", [])

    return {
        "query": query,
        "stations": [
            {
                "code": s.get("code"),
                "name": s.get("name"),
                "city": s.get("city"),
            }
            for s in data[:limit]
        ],
    }


# ============================================================
# INTERNAL AVAILABILITY CHECK
# ============================================================

def _check_train_seat_availability(train_number: str, source: str, destination: str, journey_date: str, class_code: str = "3A", quota_code: str = "GN") -> dict[str, Any]:
    source, destination = source.upper(), destination.upper()
    class_code, quota_code = class_code.upper(), quota_code.upper()

    print(f"Checking ticket availability for train {train_number} from {source} to {destination} on {journey_date} | {class_code}/{quota_code}")

    response = requests.get(
        f"{RAILRADAR_URL}/trains/{train_number}/seats",
        headers=_rail_headers(),
        params={
            "source": source,
            "destination": destination,
            "journeyDate": journey_date,
            "classCode": class_code,
            "quotaCode": quota_code,
        },
        timeout=20,
    )

    if response.status_code == 503:
        return {
            "ticket_status": "AVAILABILITY DATA UNAVAILABLE",
            "message": "Railway ticket availability service is temporarily unavailable.",
        }

    if response.status_code != 200:
        return {
            "ticket_status": "AVAILABILITY DATA UNAVAILABLE",
            "message": response.text,
        }

    data = response.json().get("data", {})
    calendar = data.get("calendar", [])
    requested = next((x for x in calendar if x.get("date") == journey_date), None)

    if not requested:
        return {
            "ticket_status": "AVAILABILITY DATA UNAVAILABLE",
            "message": "No availability data returned for the requested date.",
        }

    status_code = str(requested.get("statusCode") or "").upper()

    if status_code == "AVAILABLE":
        ticket_status = "AVAILABLE"
    elif status_code == "RAC":
        ticket_status = "RAC"
    elif status_code == "WAITLIST":
        ticket_status = "WAITLIST"
    else:
        ticket_status = "AVAILABILITY DATA UNAVAILABLE"

    alternatives = [
        {
            "date": x.get("date"),
            "status": x.get("status"),
            "available_seats": x.get("availableSeats"),
        }
        for x in calendar
        if x.get("isAvailable") and x.get("date") != journey_date
    ][:3]

    return {
        "ticket_status": ticket_status,
        "available_seats": requested.get("availableSeats"),
        "waitlist_number": requested.get("waitlistNumber"),
        "status_text": requested.get("status"),
        "alternative_dates": alternatives,
    }


# ============================================================
# INTERNAL STATION RESOLVER
# ============================================================

def _resolve_station(value: str) -> dict[str, Any] | None:
    value = value.strip()

    if len(value) <= 5 and value.isalnum() and value.upper() == value:
        return {"code": value, "name": value, "city": None}

    result = search_train_stations.invoke({
        "query": value,
        "limit": 5,
    })

    if result.get("error"):
        return None

    stations = result.get("stations", [])

    if not stations:
        return None

    station = stations[0]

    return {
        "code": station.get("code"),
        "name": station.get("name"),
        "city": station.get("city"),
    }


# ============================================================
# INTERNAL TRAIN SEARCH
# ============================================================

def _search_train_route(from_code: str, to_code: str, journey_date: str | None = None) -> dict[str, Any]:
    from_station, to_station = from_code.upper(), to_code.upper()

    print(
        f"Searching trains from {from_station} to {to_station}"
        + (f" on {journey_date}" if journey_date else "")
    )

    params = {"byCity": "false", "live": "false"}

    if journey_date:
        params["date"] = journey_date

    response = requests.get(
        f"{RAILRADAR_URL}/trains/between/{from_station}/{to_station}",
        headers=_rail_headers(),
        params=params,
        timeout=20,
    )

    if response.status_code != 200:
        return {
            "error": True,
            "status_code": response.status_code,
            "message": response.text,
            "trains": [],
        }

    data = response.json().get("data", {})
    trains = []

    for item in data.get("trains", []):
        train = item.get("train", {})
        source = item.get("from", {})
        destination = item.get("to", {})
        live_data = item.get("live") or {}

        trains.append({
            "train_number": train.get("number"),
            "train_name": train.get("name"),
            "type": train.get("type"),
            "departure": source.get("departure"),
            "arrival": destination.get("arrival"),
            "departure_day": source.get("day"),
            "arrival_day": destination.get("day"),
            "duration_minutes": item.get("duration"),
            "distance_km": item.get("distance"),
            "halts": item.get("totalHaltsBetween"),
            "live_status": live_data.get("type"),
            "delay_minutes": live_data.get("delayMinutes"),
            "platform": live_data.get("platform"),
        })

    return {
        "from": data.get("from"),
        "to": data.get("to"),
        "date": journey_date,
        "count": len(trains),
        "trains": trains,
    }


# ============================================================
# DYNAMIC NEARBY STATION DISCOVERY
# ============================================================

def _find_nearby_stations(station: dict[str, Any], exclude_code: str) -> list[dict[str, Any]]:
    query = station.get("city") or station.get("name")

    if not query:
        return []

    result = search_train_stations.invoke({
        "query": query,
        "limit": 5,
    })

    if result.get("error"):
        return []

    return [
        s
        for s in result.get("stations", [])
        if s.get("code") and s.get("code") != exclude_code
    ][:3]


def _find_fallback_routes(source: dict[str, Any], destination: dict[str, Any]) -> list[dict[str, Any]]:
    source_alternatives = _find_nearby_stations(source, destination["code"])
    destination_alternatives = _find_nearby_stations(destination, source["code"])

    routes = []

    for station in source_alternatives:
        routes.append({
            "from": station,
            "to": destination,
            "reason": f"Alternative origin station near {source.get('name')}",
        })

    for station in destination_alternatives:
        routes.append({
            "from": source,
            "to": station,
            "reason": f"Alternative destination station near {destination.get('name')}",
        })

    return routes[:4]


# ============================================================
# TRAIN RANKING
# ============================================================

def _train_rank_key(train: dict[str, Any]):
    priority = {
        "AVAILABLE": 0,
        "RAC": 1,
        "WAITLIST": 2,
        "AVAILABILITY DATA UNAVAILABLE": 3,
    }

    status = train.get("ticket_status", "AVAILABILITY DATA UNAVAILABLE")

    if status == "AVAILABLE":
        value = -(train.get("available_seats") or 0)
    else:
        value = train.get("waitlist_number") or 999999

    return priority.get(status, 3), value


# ============================================================
# MAIN TRAIN ABSTRACTION
# ============================================================

@tool
def search_trains(from_station: str, to_station: str, start_date: str, end_date: str | None = None, class_code: str = "3A", quota_code: str = "GN") -> dict[str, Any]:
    """Search trains between station codes and return top options ranked by ticket availability.
    from_station: 2-5 letter station code or station name.
    to_station: 2-5 letter station code or station name.
    start_date: YYYY-MM-DD.
    end_date: YYYY-MM-DD for return trip; omit for one-way.
    class_code: 2-letter class code (e.g., 3A, SL, CC).
    quota_code: 2-letter quota code (e.g., GN, LD, TQ) 
    - For round trips, always call search_trains once with both start_date and end_date."""

    from_station = from_station.upper().strip()
    to_station = to_station.upper().strip()
    class_code = class_code.upper().strip()
    quota_code = quota_code.upper().strip()
    print(f"Searching trains from {from_station} to {to_station} on {start_date}" + (f" and returning on {end_date}" if end_date else "") + f" | Class: {class_code}, Quota: {quota_code}")

    def search_direction(source: str, destination: str, journey_date: str):
        print(f"Searching trains from {source} to {destination} on {journey_date}")

        response = requests.get(
            f"{RAILRADAR_URL}/trains/between/{source}/{destination}",
            headers=_rail_headers(),
            params={"byCity": "false", "live": "false", "date": journey_date},
            timeout=20,
        )

        if response.status_code != 200:
            return {
                "status": "TRAIN_DATA_UNAVAILABLE",
                "message": response.text,
                "route": f"{source} → {destination}",
                "date": journey_date,
                "trains": [],
            }

        data = response.json().get("data", {})
        trains = []

        for item in data.get("trains", []):
            train = item.get("train", {})
            source_data = item.get("from", {})
            destination_data = item.get("to", {})
            live_data = item.get("live") or {}

            trains.append({
                "train_number": train.get("number"),
                "train_name": train.get("name"),
                "type": train.get("type"),
                "departure": source_data.get("departure"),
                "arrival": destination_data.get("arrival"),
                "departure_day": source_data.get("day"),
                "arrival_day": destination_data.get("day"),
                "duration_minutes": item.get("duration"),
                "distance_km": item.get("distance"),
                "halts": item.get("totalHaltsBetween"),
                "live_status": live_data.get("type"),
                "delay_minutes": live_data.get("delayMinutes"),
                "platform": live_data.get("platform"),
            })

        results = []

        for train in trains[:4]:
            availability = _check_train_seat_availability(
                train_number=train["train_number"],
                source=source,
                destination=destination,
                journey_date=journey_date,
                class_code=class_code,
                quota_code=quota_code,
            )

            results.append({
                **train,
                "class": class_code,
                "quota": quota_code,
                "ticket_status": availability.get("ticket_status"),
                "available_seats": availability.get("available_seats"),
                "waitlist_number": availability.get("waitlist_number"),
                "alternative_dates": availability.get("alternative_dates", []),
            })

        results.sort(key=_train_rank_key)

        return {
            "route": f"{source} → {destination}",
            "date": journey_date,
            "count": len(results),
            "trains": results[:4],
        }

    result = {
        "type": "train_search",
        "class": class_code,
        "quota": quota_code,
        "onward": search_direction(from_station, to_station, start_date),
    }

    if end_date:
        result["return"] = search_direction(
            to_station,
            from_station,
            end_date,
        )

    return result

if __name__ == "__main__":
    print(get_weather("Tokyo", "2026-09-15", "2026-09-20"))
