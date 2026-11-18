from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np
import osmnx as ox

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

GRAPH_FILE = DATA_DIR / "kawagoe_drive_verified_v1.graphml"
MATRIX_FILE = DATA_DIR / "kawagoe_route_matrix.json"
BACKUP_FILE = DATA_DIR / "kawagoe_route_matrix_before_entry_node_fix.json"

ENTRY_NAMES = ["川越IC", "川越駅"]


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        value = json.load(f)
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} の形式が不正です。")
    return value


def save_json(path: Path, value: Any) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)


def haversine_distance_m(lat1, lon1, lat2, lon2):
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


def nearest_node_from_allowed(
    graph,
    allowed_nodes,
    lat,
    lon,
):
    ids = []
    lats = []
    lons = []

    for node_id in allowed_nodes:
        data = graph.nodes[node_id]

        try:
            node_lat = float(data["y"])
            node_lon = float(data["x"])
        except (KeyError, TypeError, ValueError):
            continue

        ids.append(node_id)
        lats.append(node_lat)
        lons.append(node_lon)

    if not ids:
        raise RuntimeError("候補道路ノードがありません。")

    lat_array = np.asarray(lats, dtype=float)
    lon_array = np.asarray(lons, dtype=float)

    cos_lat = math.cos(math.radians(lat))

    squared = (
        (lat_array - lat) ** 2
        + ((lon_array - lon) * cos_lat) ** 2
    )

    idx = int(np.argmin(squared))

    node_id = ids[idx]
    distance = haversine_distance_m(
        lat,
        lon,
        float(lat_array[idx]),
        float(lon_array[idx]),
    )

    return node_id, distance


def route_metrics(
    graph,
    origin_node,
    destination_node,
    origin_lat,
    origin_lon,
    destination_lat,
    destination_lon,
):
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

    gdf = ox.routing.route_to_gdf(
        graph,
        route,
        weight="travel_time",
    )

    distance_m = float(gdf["length"].sum())
    duration_s = float(gdf["travel_time"].sum())

    return {
        "available": True,
        "distance_meters": round(distance_m, 1),
        "distance_km": round(distance_m / 1000.0, 2),
        "duration_seconds": round(duration_s, 1),
        "duration_minutes": round(duration_s / 60.0, 1),
        "calculation_method": "road_network",
    }


def main():
    print("=" * 76)
    print("川越入口2地点 双方向接続修正")
    print("=" * 76)

    if not GRAPH_FILE.exists():
        raise FileNotFoundError(GRAPH_FILE)

    if not MATRIX_FILE.exists():
        raise FileNotFoundError(MATRIX_FILE)

    matrix = load_json(MATRIX_FILE)

    locations = matrix.get("locations")
    routes = matrix.get("routes")

    if not isinstance(locations, dict):
        raise ValueError("locations が不正です。")
    if not isinstance(routes, dict):
        raise ValueError("routes が不正です。")

    if len(locations) != 72:
        raise RuntimeError(
            f"現在の地点数が72ではありません: {len(locations)}"
        )

    for name in ENTRY_NAMES:
        if name not in locations:
            raise RuntimeError(f"入口地点がありません: {name}")

    save_json(BACKUP_FILE, matrix)

    graph = ox.io.load_graphml(GRAPH_FILE)

    # 既存70地点のうち、node_idを持つ最初の1地点をアンカーにする。
    anchor_name = None
    anchor_node = None

    for name, info in locations.items():
        if name in ENTRY_NAMES:
            continue

        if not isinstance(info, dict):
            continue

        node_id = info.get("node_id")

        if node_id is None:
            continue

        # GraphML読込後はnode idの型が変わる場合があるので照合する。
        candidates = [node_id, str(node_id)]

        for candidate in candidates:
            if candidate in graph:
                anchor_name = name
                anchor_node = candidate
                break

        if anchor_node is not None:
            break

    if anchor_node is None:
        raise RuntimeError(
            "既存70地点からアンカー道路ノードを取得できません。"
        )

    print(f"[ANCHOR] {anchor_name} -> {anchor_node}")

    # アンカーと相互到達可能な強連結成分だけを使用する。
    core_nodes = None

    for component in nx.strongly_connected_components(graph):
        if anchor_node in component:
            core_nodes = component
            break

    if not core_nodes:
        raise RuntimeError(
            "アンカーを含む強連結成分を取得できません。"
        )

    print(
        f"[STRONGLY CONNECTED CORE] nodes = {len(core_nodes)}"
    )

    # 念のため既存70地点がこの強連結成分に入っているか確認。
    outside_existing = []

    for name, info in locations.items():
        if name in ENTRY_NAMES or not isinstance(info, dict):
            continue

        node_id = info.get("node_id")

        if node_id in core_nodes:
            continue

        if str(node_id) in core_nodes:
            continue

        outside_existing.append(name)

    if outside_existing:
        print(
            "[WARNING] 既存地点の一部がアンカー強連結成分外:",
            outside_existing[:10],
        )
        print(
            "既存4830区間は成功済みのため、"
            "入口地点だけこの強連結成分へ付け直します。"
        )

    # 入口2地点を強連結成分内の最寄りノードへ付け直す。
    for name in ENTRY_NAMES:
        info = locations[name]

        lat = float(info["latitude"])
        lon = float(info["longitude"])

        node_id, snap_distance = nearest_node_from_allowed(
            graph,
            core_nodes,
            lat,
            lon,
        )

        info["node_id"] = node_id
        info["snap_distance_meters"] = round(
            snap_distance,
            1,
        )
        info["node_selection"] = (
            "nearest_node_in_anchor_strongly_connected_component"
        )

        print(
            f"[RESNAP] {name} -> {node_id} "
            f"(約{snap_distance:.1f}m)"
        )

        if snap_distance > 500:
            raise RuntimeError(
                f"{name} の再接続距離が500mを超えました: "
                f"{snap_distance:.1f}m"
            )

    all_names = list(locations.keys())

    # 入口2地点に関係する282方向区間だけ上書き再計算。
    total = 0
    success = 0
    failed = []

    for origin_name in all_names:
        routes.setdefault(origin_name, {})

        for destination_name in all_names:
            if origin_name == destination_name:
                continue

            if (
                origin_name not in ENTRY_NAMES
                and destination_name not in ENTRY_NAMES
            ):
                continue

            total += 1

            origin = locations[origin_name]
            destination = locations[destination_name]

            origin_node = origin["node_id"]
            destination_node = destination["node_id"]

            if origin_node not in graph and str(origin_node) in graph:
                origin_node = str(origin_node)

            if destination_node not in graph and str(destination_node) in graph:
                destination_node = str(destination_node)

            metrics = route_metrics(
                graph,
                origin_node,
                destination_node,
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
                failed.append(
                    f"{origin_name} -> {destination_name}"
                )
            else:
                routes[origin_name][destination_name] = metrics
                success += 1

            if total % 25 == 0:
                print(
                    f"[ROUTE] {total}/282 "
                    f"(成功 {success})"
                )

    pair_count = 72 * 71

    available_count = 0

    for origin_name, dest_map in routes.items():
        if not isinstance(dest_map, dict):
            continue

        for destination_name, result in dest_map.items():
            if origin_name == destination_name:
                continue

            if (
                isinstance(result, dict)
                and result.get("available") is True
            ):
                available_count += 1

    matrix["location_count"] = 72
    matrix["pair_count"] = pair_count
    matrix["available_pair_count"] = available_count

    save_json(MATRIX_FILE, matrix)

    print()
    print("=" * 76)
    print("川越入口2地点 修正完了")
    print("=" * 76)
    print("今回再計算:", total)
    print("今回成功:", success)
    print("今回失敗:", len(failed))
    print("地点数:", 72)
    print("対象区間:", pair_count)
    print("取得成功:", available_count)
    print("取得失敗:", pair_count - available_count)

    if failed:
        print()
        print("失敗例:")
        for item in failed[:20]:
            print(" -", item)

    if (
        total == 282
        and success == 282
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
