from pprint import pprint
from tools import search_train_stations, search_trains, check_train_seat_availability


print("\n=== SEARCH TRAIN STATIONS ===")
stations = search_train_stations.invoke({"query": "Delhi", "limit": 5})
pprint(stations, sort_dicts=False)


print("\n=== SEARCH TRAINS ===")
trains = search_trains.invoke({"from_station": "NDLS", "to_station": "MMCT", "journey_date": "2026-09-20"})
pprint(trains, sort_dicts=False)


print("\n=== CHECK SEAT AVAILABILITY ===")
seats = check_train_seat_availability.invoke({
    "train_number": "12952",
    "source": "NDLS",
    "destination": "MMCT",
    "journey_date": "2026-09-20",
    "class_code": "3A",
    "quota_code": "GN"
})
pprint(seats, sort_dicts=False)