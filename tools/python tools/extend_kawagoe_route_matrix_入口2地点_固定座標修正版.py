from __future__ import annotations

import json
import math
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np
import osmnx as ox

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

GRAPH_FILE = DATA_DIR / "kawagoe_drive_verified_v1.graphml"
MATRIX_FILE = DATA_DIR / "kawagoe_route_matrix.json"
BACKUP_FILE = DATA_DIR / "kawagoe_route_matrix_before_entry_points.json"

GSI_URL = "https://msearch.gsi.go.jp/address-search/AddressSearch"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "SaitamaSouthwestTourismPlanner/entry-points-1.0 (academic project)"

ENTRY_POINTS = {
    "川越IC": {
        "kind": "fixed",
        "latitude": 35.895874,
        "longitude": 139.457613,
        "query": "川越インターチェンジ",
        "display_label": "関越道方面から（川越IC）",
        "address": "埼玉県川越市・関越自動車道 川越IC",
    },
    "川越駅": {
        "kind": "gsi_address",
        "query": "埼玉県川越市脇田町24-9",
        "display_label": "市街地方面から（川越駅周辺）",
        "address": "埼玉県川越市脇田町24-9",
    },
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"必要ファイルがありません: {path}")
    with path.open("r", encoding="utf-8") as f:
        value = json.load(f)
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} の形式が不正です。")
    return value


def save_json(path: Path, value: Any) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)


def haversine_distance_m(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    r = 6371000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    a = (
        math.sin(dp / 2.0) ** 2
        + math.cos(p1)
        * math.cos(p2)
        * math.sin(dl / 2.0) ** 2
    )

    return 2.0 * r * math.asin(math.sqrt(a))


def gsi_address(query: str) -> tuple[float, float, str]:
    params = urllib.parse.urlencode({"q": query})
    req = urllib.request.Request(
        f"{GSI_URL}?{params}",
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )

    with urllib.request.urlopen(req, timeout=30) as response:
        results = json.loads(response.read().decode("utf-8"))

    if not isinstance(results, list) or not results:
        raise RuntimeError(f"国土地理院住所検索で取得できません: {query}")

    for item in results:
        geometry = item.get("geometry")
        props = item.get("properties")

        if not isinstance(geometry, dict):
            continue

        coords = geometry.get("coordinates")
        if not isinstance(coords, list) or len(coords) < 2:
            continue

        lon = float(coords[0])
        lat = float(coords[1])

        if 35.82 <= lat <= 36.02 and 139.36 <= lon <= 139.58:
            title = ""
            if isinstance(props, dict):
                title = str(props.get("title") or "")
            return lat, lon, title

    raise RuntimeError(f"川越範囲内の住所候補がありません: {query}")


def nominatim_name(query: str) -> tuple[float, float, str]:
    params = urllib.parse.urlencode(
        {
            "q": query,
            "format": "jsonv2",
            "limit": 10,
            "countrycodes": "jp",
            "addressdetails": 1,
            "namedetails": 1,
        }
    )

    req = urllib.request.Request(
        f"{NOMINATIM_URL}?{params}",
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Accept-Language": "ja",
        },
    )

    with urllib.request.urlopen(req, timeout=30) as response:
        results = json.loads(response.read().decode("utf-8"))

    if not isinstance(results, list):
        results = []

    for item in results:
        display = str(item.get("display_name") or "")

        try:
            lat = float(item["lat"])
            lon = float(item["lon"])
        except (KeyError, TypeError, ValueError):
            continue

        if not (
            35.82 <= lat <= 36.02
            and 139.36 <= lon <= 139.58
        ):
            continue

        normalized = re.sub(r"\s+", "", display)

        if (
            "川越" in normalized
            and (
                "インターチェンジ" in normalized
                or "川越IC" in normalized
                or "Kawagoe" in display
            )
        ):
            return lat, lon, display

    raise RuntimeError(f"川越ICを安全に特定できません: {query}")


def nearest_node_without_sklearn(
    graph,
    lat: float,
    lon: float,
) -> tuple[int, float]:
    node_ids = []
    lats = []
    lons = []

    for node_id, data in graph.nodes(data=True):
        try:
            node_lat = float(data["y"])
            node_lon = float(data["x"])
        except (KeyError, TypeError, ValueError):
            continue

        node_ids.append(int(node_id))
        lats.append(node_lat)
        lons.append(node_lon)

    if not node_ids:
        raise RuntimeError("道路ノードを取得できません。")

    lat_array = np.asarray(lats, dtype=float)
    lon_array = np.asarray(lons, dtype=float)
    id_array = np.asarray(node_ids, dtype=np.int64)

    cos_lat = math.cos(math.radians(lat))

    squared = (
        (lat_array - lat) ** 2
        + ((lon_array - lon) * cos_lat) ** 2
    )

    idx = int(np.argmin(squared))

    node_id = int(id_array[idx])

    distance = haversine_distance_m(
        lat,
        lon,
        float(lat_array[idx]),
        float(lon_array[idx]),
    )

    return node_id, distance


def route_metrics(
    graph,
    origin_node: int,
    destination_node: int,
    origin_lat: float,
    origin_lon: float,
    destination_lat: float,
    destination_lon: float,
) -> dict[str, Any] | None:
    if origin_node == destination_node:
        distance_m = haversine_distance_m(
            origin_lat,
            origin_lon,
            destination_lat,
            destination_lon,
        )

        duration_minutes = max(
            (distance_m / 1000.0) / 15.0 * 60.0,
            0.5,
        )

        return {
            "available": True,
            "distance_meters": round(distance_m, 1),
            "distance_km": round(distance_m / 1000.0, 2),
            "duration_seconds": round(duration_minutes * 60.0, 1),
            "duration_minutes": round(duration_minutes, 1),
            "calculation_method": "same_node_nearby_estimate",
        }

    route = ox.routing.shortest_path(
        graph,
        origin_node,
        destination_node,
        weight="travel_time",
    )

    if not route:
        return None

    route_gdf = ox.routing.route_to_gdf(
        graph,
        route,
        weight="travel_time",
    )

    distance_m = float(route_gdf["length"].sum())
    duration_s = float(route_gdf["travel_time"].sum())

    return {
        "available": True,
        "distance_meters": round(distance_m, 1),
        "distance_km": round(distance_m / 1000.0, 2),
        "duration_seconds": round(duration_s, 1),
        "duration_minutes": round(duration_s / 60.0, 1),
        "calculation_method": "road_network",
    }


def resolve_entry_points() -> dict[str, dict[str, Any]]:
    resolved = {}

    for name, spec in ENTRY_POINTS.items():
        print(f"[ENTRY] {name} を確認中...")

        if spec["kind"] == "fixed":
            lat = float(spec["latitude"])
            lon = float(spec["longitude"])
            source_name = spec["query"]
            source = "Fixed verified coordinate"

        elif spec["kind"] == "gsi_address":
            lat, lon, source_name = gsi_address(spec["query"])
            source = "Geospatial Information Authority of Japan AddressSearch"

        elif spec["kind"] == "nominatim_name":
            lat, lon, source_name = nominatim_name(spec["query"])
            source = "OpenStreetMap Nominatim exact entry point"
            time.sleep(1.1)

        else:
            raise RuntimeError(f"未知のentry kind: {spec['kind']}")

        resolved[name] = {
            "name": name,
            "category": "route_entry",
            "address": spec["address"],
            "latitude": round(lat, 8),
            "longitude": round(lon, 8),
            "display_label": spec["display_label"],
            "coordinate_source": source,
            "geocode_display_name": source_name,
        }

        print(
            f"  -> {resolved[name]['latitude']}, "
            f"{resolved[name]['longitude']}"
        )

    return resolved


def main() -> None:
    print("=" * 76)
    print("川越ルート行列 入口地点追加")
    print("=" * 76)

    matrix = load_json(MATRIX_FILE)

    locations = matrix.get("locations")
    routes = matrix.get("routes")

    if not isinstance(locations, dict):
        raise ValueError("kawagoe_route_matrix.json の locations が不正です。")
    if not isinstance(routes, dict):
        raise ValueError("kawagoe_route_matrix.json の routes が不正です。")

    if len(locations) != 70:
        raise RuntimeError(
            f"追加前の地点数が70ではありません: {len(locations)}"
        )

    if int(matrix.get("available_pair_count") or 0) != 4830:
        raise RuntimeError(
            "既存川越ルート行列が4830/4830ではありません。"
        )

    save_json(BACKUP_FILE, matrix)

    graph = ox.io.load_graphml(GRAPH_FILE)

    entry_points = resolve_entry_points()

    for entry in entry_points.values():
        node_id, snap_distance = nearest_node_without_sklearn(
            graph,
            float(entry["latitude"]),
            float(entry["longitude"]),
        )

        if snap_distance > 500:
            raise RuntimeError(
                f"{entry['name']} がdriveノードから離れすぎています: "
                f"{snap_distance:.1f}m"
            )

        entry["node_id"] = node_id
        entry["snap_distance_meters"] = round(snap_distance, 1)

        print(
            f"[NODE] {entry['name']} -> {node_id} "
            f"(約{snap_distance:.1f}m)"
        )

    # 既存70地点へ追加
    for name, entry in entry_points.items():
        locations[name] = {
            "category": entry["category"],
            "address": entry["address"],
            "latitude": entry["latitude"],
            "longitude": entry["longitude"],
            "node_id": entry["node_id"],
            "snap_distance_meters": entry["snap_distance_meters"],
            "coordinate_source": entry["coordinate_source"],
            "display_label": entry["display_label"],
        }

    all_names = list(locations.keys())

    # 新しい入口をoriginとして全地点へ
    # 既存地点をoriginとして新しい入口へ
    # 入口同士も計算
    for origin_name in all_names:
        routes.setdefault(origin_name, {})

    new_names = list(entry_points.keys())

    calculation_count = 0
    success_count = 0

    for origin_name in all_names:
        for destination_name in all_names:
            if origin_name == destination_name:
                routes[origin_name][destination_name] = {
                    "available": True,
                    "distance_meters": 0.0,
                    "distance_km": 0.0,
                    "duration_seconds": 0.0,
                    "duration_minutes": 0.0,
                }
                continue

            # 既存70→既存70は完成済みなので再計算しない
            if (
                origin_name not in new_names
                and destination_name not in new_names
            ):
                continue

            calculation_count += 1

            origin = locations[origin_name]
            destination = locations[destination_name]

            metrics = route_metrics(
                graph,
                int(origin["node_id"]),
                int(destination["node_id"]),
                float(origin["latitude"]),
                float(origin["longitude"]),
                float(destination["latitude"]),
                float(destination["longitude"]),
            )

            if metrics is None:
                routes[origin_name][destination_name] = {
                    "available": False,
                    "distance_meters": None,
                    "distance_km": None,
                    "duration_seconds": None,
                    "duration_minutes": None,
                }
            else:
                routes[origin_name][destination_name] = metrics
                success_count += 1

            if calculation_count % 25 == 0:
                print(
                    f"[ROUTE] {calculation_count}/282 "
                    f"(成功 {success_count})"
                )

    location_count = len(locations)
    pair_count = location_count * (location_count - 1)

    available_count = 0

    for origin_name, destination_map in routes.items():
        if not isinstance(destination_map, dict):
            continue

        for destination_name, result in destination_map.items():
            if origin_name == destination_name:
                continue

            if (
                isinstance(result, dict)
                and result.get("available") is True
            ):
                available_count += 1

    matrix["schema_version"] = 3
    matrix["region"] = "川越"
    matrix["location_count"] = location_count
    matrix["pair_count"] = pair_count
    matrix["available_pair_count"] = available_count
    matrix["entry_points"] = {
        name: {
            "display_label": entry["display_label"],
            "address": entry["address"],
            "latitude": entry["latitude"],
            "longitude": entry["longitude"],
        }
        for name, entry in entry_points.items()
    }

    save_json(MATRIX_FILE, matrix)

    print()
    print("=" * 76)
    print("入口地点追加 完了")
    print("=" * 76)
    print("地点数:", location_count)
    print("対象区間:", pair_count)
    print("取得成功:", available_count)
    print("取得失敗:", pair_count - available_count)
    print("今回追加計算:", calculation_count)
    print("今回追加成功:", success_count)

    if (
        location_count == 72
        and pair_count == 5112
        and available_count == 5112
    ):
        print(
            "[KAWAGOE ROUTE MATRIX + ENTRY] "
            "locations = 72 | pairs = 5112 | "
            "available = 5112 | COMPLETE"
        )
    else:
        print(
            "[KAWAGOE ROUTE MATRIX + ENTRY] CHECK REQUIRED"
        )


if __name__ == "__main__":
    main()
