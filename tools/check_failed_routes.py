import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ROUTE_FILE = BASE_DIR / "data" / "route_matrix.json"

with open(ROUTE_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

routes = data.get("routes", {})

failed = []

for origin, destinations in routes.items():

    if not isinstance(destinations, dict):
        continue

    for destination, route in destinations.items():

        # 同じ地点 -> 同じ地点は除外
        if origin == destination:
            continue

        if not isinstance(route, dict):
            continue

        if route.get("available") is False:
            failed.append(
                (origin, destination, route)
            )


print()
print("================================")
print("失敗ルート一覧")
print("================================")
print()

for i, (origin, destination, route) in enumerate(
    failed,
    start=1
):
    print(
        f"{i:02d}. "
        f"{origin} -> {destination}"
    )

print()
print("================================")
print(f"地点数: {data.get('location_count')}")
print(f"対象区間: {data.get('pair_count')}")
print(f"成功区間: {data.get('available_pair_count')}")
print(f"失敗区間: {len(failed)}")
print("================================")
print()
print("================================")
print("失敗地点の道路ノード確認")
print("================================")

locations = data.get("locations", {})

for i, (origin, destination, route) in enumerate(failed, start=1):

    origin_info = locations.get(origin, {})
    destination_info = locations.get(destination, {})

    origin_node = origin_info.get("node_id")
    destination_node = destination_info.get("node_id")

    same_node = origin_node == destination_node

    print(
        f"{i:02d}. {origin} -> {destination}"
    )
    print(
        f"    出発ノード: {origin_node}"
    )
    print(
        f"    到着ノード: {destination_node}"
    )
    print(
        f"    同一ノード: {same_node}"
    )