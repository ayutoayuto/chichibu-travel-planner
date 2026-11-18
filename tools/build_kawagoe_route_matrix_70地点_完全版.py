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

ROUTE_LOCATION_FILE = DATA_DIR / "kawagoe_route_locations.json"

VALIDATED_LOCATION_FILE = DATA_DIR / "kawagoe_validated_route_locations.json"
GRAPH_FILE = DATA_DIR / "kawagoe_drive_verified_v1.graphml"
ROUTE_MATRIX_FILE = DATA_DIR / "kawagoe_route_matrix.json"

EXPECTED_LOCATION_COUNT = 70

# 取得範囲は、70地点の外周からこの分だけ余裕を持たせる。
GRAPH_MARGIN_DEGREES = 0.03

# 川越データとして許容する絶対安全範囲。
SAFE_LAT_MIN = 35.82
SAFE_LAT_MAX = 36.02
SAFE_LON_MIN = 139.36
SAFE_LON_MAX = 139.58

ox.settings.use_cache = True
ox.settings.log_console = True
ox.settings.requests_timeout = 180


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"必要ファイルがありません: {path}")

    with path.open("r", encoding="utf-8") as f:
        value = json.load(f)

    if not isinstance(value, dict):
        raise ValueError(f"{path.name} の形式が不正です。")

    return value


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(
            value,
            f,
            ensure_ascii=False,
            indent=2,
        )


def as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(number):
        return None

    return number


def is_safe_coordinate(lat: float, lon: float) -> bool:
    return (
        SAFE_LAT_MIN <= lat <= SAFE_LAT_MAX
        and SAFE_LON_MIN <= lon <= SAFE_LON_MAX
    )


def load_and_validate_points() -> list[dict[str, Any]]:
    """
    v3/v4までで固定した川越70地点だけを使用する。

    この工程では:
    - Nominatimを呼ばない
    - 国土地理院住所検索を呼ばない
    - facilities_masterから座標を再生成しない

    kawagoe_route_locations.json を唯一の座標ソースとする。
    """
    data = load_json(ROUTE_LOCATION_FILE)

    route_locations = data.get("route_locations")

    if not isinstance(route_locations, dict):
        raise ValueError(
            "kawagoe_route_locations.json の route_locations がdictではありません。"
        )

    if len(route_locations) != EXPECTED_LOCATION_COUNT:
        raise RuntimeError(
            "川越地点数が70ではありません。"
            f"現在 {len(route_locations)} 地点です。"
        )

    points: list[dict[str, Any]] = []
    missing: list[str] = []
    outside: list[tuple[str, float, float]] = []

    for name, item in route_locations.items():
        if not isinstance(item, dict):
            missing.append(str(name))
            continue

        lat = as_float(item.get("latitude"))
        lon = as_float(item.get("longitude"))

        if lat is None or lon is None:
            missing.append(str(name))
            continue

        if not is_safe_coordinate(lat, lon):
            outside.append((str(name), lat, lon))
            continue

        points.append(
            {
                "name": str(name),
                "category": item.get("category"),
                "address": item.get("address"),
                "latitude": lat,
                "longitude": lon,
                "coordinate_source": item.get("coordinate_source"),
                "verification_method": item.get("verification_method"),
            }
        )

    if missing or outside:
        print("\n=== 川越座標検証NG ===")

        if missing:
            print("\n座標未登録:")
            for name in missing:
                print("  -", name)

        if outside:
            print("\n安全範囲外:")
            for name, lat, lon in outside:
                print(f"  - {name}: {lat}, {lon}")

        raise RuntimeError(
            "座標が完全ではないため、川越route matrixは生成しません。"
        )

    if len(points) != EXPECTED_LOCATION_COUNT:
        raise RuntimeError(
            f"検証済み地点数が70ではありません: {len(points)}"
        )

    # 名称はroute_locations側の順番を維持する。
    save_json(
        VALIDATED_LOCATION_FILE,
        {
            "schema_version": 1,
            "region": "川越",
            "location_count": len(points),
            "coordinate_source_file": ROUTE_LOCATION_FILE.name,
            "locations": {
                item["name"]: {
                    "category": item.get("category"),
                    "address": item.get("address"),
                    "latitude": item["latitude"],
                    "longitude": item["longitude"],
                    "coordinate_source": item.get("coordinate_source"),
                    "verification_method": item.get("verification_method"),
                }
                for item in points
            },
        },
    )

    return points


def calculate_graph_bbox(
    points: list[dict[str, Any]],
) -> tuple[float, float, float, float]:
    """
    OSMnx 2.x graph_from_bbox に渡す
    (left, bottom, right, top) を作る。
    """
    lats = [float(x["latitude"]) for x in points]
    lons = [float(x["longitude"]) for x in points]

    left = max(
        SAFE_LON_MIN,
        min(lons) - GRAPH_MARGIN_DEGREES,
    )
    right = min(
        SAFE_LON_MAX,
        max(lons) + GRAPH_MARGIN_DEGREES,
    )
    bottom = max(
        SAFE_LAT_MIN,
        min(lats) - GRAPH_MARGIN_DEGREES,
    )
    top = min(
        SAFE_LAT_MAX,
        max(lats) + GRAPH_MARGIN_DEGREES,
    )

    if left >= right or bottom >= top:
        raise RuntimeError("道路取得bboxの計算に失敗しました。")

    return (
        left,
        bottom,
        right,
        top,
    )


def split_bbox(
    bbox: tuple[float, float, float, float],
    rows: int = 3,
    cols: int = 3,
    overlap: float = 0.0025,
) -> list[tuple[float, float, float, float]]:
    """
    大きなOverpassリクエストを避けるため3x3へ分割。
    """
    left, bottom, right, top = bbox

    width = (right - left) / cols
    height = (top - bottom) / rows

    result: list[tuple[float, float, float, float]] = []

    for row in range(rows):
        for col in range(cols):
            tile_left = left + col * width
            tile_right = left + (col + 1) * width
            tile_bottom = bottom + row * height
            tile_top = bottom + (row + 1) * height

            if col > 0:
                tile_left -= overlap
            if col < cols - 1:
                tile_right += overlap
            if row > 0:
                tile_bottom -= overlap
            if row < rows - 1:
                tile_top += overlap

            result.append(
                (
                    tile_left,
                    tile_bottom,
                    tile_right,
                    tile_top,
                )
            )

    return result


def download_graph_tile(
    bbox: tuple[float, float, float, float],
    tile_no: int,
    total_tiles: int,
):
    endpoints = [
        "https://overpass.private.coffee/api",
        "https://maps.mail.ru/osm/tools/overpass/api",
        "https://overpass-api.de/api",
    ]

    last_error: Exception | None = None

    for endpoint in endpoints:
        ox.settings.overpass_url = endpoint
        ox.settings.overpass_rate_limit = False
        ox.settings.requests_timeout = 180

        print(
            f"[道路 {tile_no}/{total_tiles}] "
            f"{endpoint} から取得中..."
        )

        try:
            graph = ox.graph.graph_from_bbox(
                bbox,
                network_type="drive",
                simplify=True,
                retain_all=True,
                truncate_by_edge=True,
            )

            print(
                f"[道路 {tile_no}/{total_tiles}] 取得OK "
                f"(nodes={len(graph.nodes):,}, "
                f"edges={len(graph.edges):,})"
            )

            return graph

        except Exception as exc:
            last_error = exc

            print(
                f"[道路 {tile_no}/{total_tiles}] "
                f"取得失敗: {type(exc).__name__}: {exc}"
            )

            print("次のOverpassサーバーを試します。")

    raise RuntimeError(
        f"道路区画 {tile_no}/{total_tiles} を取得できませんでした。"
    ) from last_error


def build_or_load_graph(
    points: list[dict[str, Any]],
):
    if GRAPH_FILE.exists():
        print(
            "既存の川越道路グラフを読み込み:",
            GRAPH_FILE,
        )
        graph = ox.io.load_graphml(GRAPH_FILE)

        # 既存ファイルにもtravel_timeがあることを保証。
        edge_values = [
            data.get("travel_time")
            for _, _, _, data in graph.edges(
                keys=True,
                data=True,
            )
        ]

        if not edge_values or any(
            value in (None, "")
            for value in edge_values
        ):
            print("既存道路グラフにtravel_timeを追加します。")
            graph = ox.routing.add_edge_speeds(graph)
            graph = ox.routing.add_edge_travel_times(graph)
            ox.io.save_graphml(graph, GRAPH_FILE)

        return graph

    bbox = calculate_graph_bbox(points)

    print("OpenStreetMap川越道路データを分割取得します（初回のみ）。")
    print("全体bbox =", bbox)

    tiles = split_bbox(
        bbox,
        rows=3,
        cols=3,
        overlap=0.0025,
    )

    print("取得区画数:", len(tiles))

    tile_graphs = []

    for index, tile_bbox in enumerate(
        tiles,
        start=1,
    ):
        tile_graphs.append(
            download_graph_tile(
                tile_bbox,
                index,
                len(tiles),
            )
        )

    print("\n=== 道路区画を結合 ===")

    graph = nx.compose_all(tile_graphs)

    print(
        f"結合直後: nodes={len(graph.nodes):,}, "
        f"edges={len(graph.edges):,}"
    )

    print("最大の道路連結成分を抽出します。")

    graph = ox.truncate.largest_component(
        graph,
        strongly=False,
    )

    print("道路速度を推定します。")
    graph = ox.routing.add_edge_speeds(graph)

    print("道路所要時間を計算します。")
    graph = ox.routing.add_edge_travel_times(graph)

    ox.io.save_graphml(
        graph,
        GRAPH_FILE,
    )

    print("道路グラフ保存:", GRAPH_FILE)

    print(
        f"最終道路グラフ: nodes={len(graph.nodes):,}, "
        f"edges={len(graph.edges):,}"
    )

    return graph


def haversine_distance_m(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    earth_radius = 6371000.0

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)

    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2.0) ** 2
        + math.cos(lat1_rad)
        * math.cos(lat2_rad)
        * math.sin(delta_lon / 2.0) ** 2
    )

    c = 2.0 * math.atan2(
        math.sqrt(a),
        math.sqrt(1.0 - a),
    )

    return earth_radius * c


def nearest_nodes_without_sklearn(
    graph,
    points: list[dict[str, Any]],
) -> tuple[dict[str, int], dict[str, float]]:
    """
    OSMnx nearest_nodes(unprojected) は環境によってscikit-learnを要求する。
    その依存を避けるため、道路ノードのlon/latをNumPy配列化し、
    各地点との近似地表距離で最寄りノードを直接選ぶ。

    川越程度の狭い範囲では、この方法で十分高精度。
    """
    node_ids: list[int] = []
    node_lats: list[float] = []
    node_lons: list[float] = []

    for node_id, data in graph.nodes(data=True):
        lat = as_float(data.get("y"))
        lon = as_float(data.get("x"))

        if lat is None or lon is None:
            continue

        node_ids.append(int(node_id))
        node_lats.append(lat)
        node_lons.append(lon)

    if not node_ids:
        raise RuntimeError(
            "道路グラフから緯度経度付きノードを取得できません。"
        )

    lat_array = np.asarray(
        node_lats,
        dtype=float,
    )
    lon_array = np.asarray(
        node_lons,
        dtype=float,
    )
    id_array = np.asarray(
        node_ids,
        dtype=np.int64,
    )

    node_map: dict[str, int] = {}
    snap_distance_map: dict[str, float] = {}

    for index, point in enumerate(
        points,
        start=1,
    ):
        name = point["name"]
        lat = float(point["latitude"])
        lon = float(point["longitude"])

        # lon方向を緯度補正。
        cos_lat = math.cos(math.radians(lat))

        delta_lat = lat_array - lat
        delta_lon = (lon_array - lon) * cos_lat

        squared = (
            delta_lat * delta_lat
            + delta_lon * delta_lon
        )

        nearest_index = int(np.argmin(squared))
        nearest_node = int(id_array[nearest_index])

        node_lat = float(lat_array[nearest_index])
        node_lon = float(lon_array[nearest_index])

        snap_distance = haversine_distance_m(
            lat,
            lon,
            node_lat,
            node_lon,
        )

        node_map[name] = nearest_node
        snap_distance_map[name] = round(
            snap_distance,
            1,
        )

        print(
            f"[NODE {index:02d}/70] "
            f"{name} -> {nearest_node} "
            f"(道路まで約{snap_distance:.1f}m)"
        )

    return (
        node_map,
        snap_distance_map,
    )


def validate_snap_distances(
    snap_distance_map: dict[str, float],
) -> None:
    """
    ルート用地点が道路から極端に離れていないか確認。
    500m超は自動停止。
    200m超は警告だけ出す。
    """
    warnings = []
    failures = []

    for name, distance_m in snap_distance_map.items():
        if distance_m > 500.0:
            failures.append(
                (name, distance_m)
            )
        elif distance_m > 200.0:
            warnings.append(
                (name, distance_m)
            )

    if warnings:
        print("\n=== 道路スナップ警告 ===")
        for name, distance_m in warnings:
            print(
                f"  - {name}: "
                f"最寄りdriveノードまで {distance_m:.1f}m"
            )

    if failures:
        print("\n=== 道路スナップNG ===")
        for name, distance_m in failures:
            print(
                f"  - {name}: "
                f"最寄りdriveノードまで {distance_m:.1f}m"
            )

        raise RuntimeError(
            "道路から500m以上離れた地点があるため、"
            "route matrixは生成しません。"
        )


def route_metrics(
    graph,
    origin_node: int,
    destination_node: int,
    origin: dict[str, Any],
    destination: dict[str, Any],
) -> dict[str, Any] | None:
    # 同じ道路ノードへ吸着した近距離施設。
    if origin_node == destination_node:
        distance_m = haversine_distance_m(
            float(origin["latitude"]),
            float(origin["longitude"]),
            float(destination["latitude"]),
            float(destination["longitude"]),
        )

        # 完全に同じ座標の別施設は、0mのまま扱う。
        # 住所ジオコーダーの代表点が同じ場合があるため、
        # 人工的に距離を増やさない。
        if distance_m <= 0.1:
            return {
                "available": True,
                "distance_meters": 0.0,
                "distance_km": 0.0,
                "duration_seconds": 30.0,
                "duration_minutes": 0.5,
                "calculation_method": "same_coordinate_same_node",
            }

        # 秩父版と同じ近距離補正。
        speed_kmh = 15.0

        duration_minutes = (
            (distance_m / 1000.0)
            / speed_kmh
            * 60.0
        )

        duration_minutes = max(
            duration_minutes,
            0.5,
        )

        duration_seconds = (
            duration_minutes
            * 60.0
        )

        return {
            "available": True,
            "distance_meters": round(
                distance_m,
                1,
            ),
            "distance_km": round(
                distance_m / 1000.0,
                2,
            ),
            "duration_seconds": round(
                duration_seconds,
                1,
            ),
            "duration_minutes": round(
                duration_minutes,
                1,
            ),
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

    distance_m = float(
        route_gdf["length"].sum()
    )

    duration_s = float(
        route_gdf["travel_time"].sum()
    )

    return {
        "available": True,
        "distance_meters": round(
            distance_m,
            1,
        ),
        "distance_km": round(
            distance_m / 1000.0,
            2,
        ),
        "duration_seconds": round(
            duration_s,
            1,
        ),
        "duration_minutes": round(
            duration_s / 60.0,
            1,
        ),
        "calculation_method": "road_network",
    }


def build_route_matrix() -> None:
    print("=" * 76)
    print("川越70地点 ローカル車ルート行列作成")
    print("=" * 76)

    print("\n=== 1. 川越固定座標読込 ===")

    points = load_and_validate_points()

    print(
        f"座標検証OK: "
        f"{len(points)} / {EXPECTED_LOCATION_COUNT}"
    )

    print(
        "外部ジオコード: 使用しません。"
    )

    print("\n=== 2. 川越道路ネットワーク準備 ===")

    graph = build_or_load_graph(
        points,
    )

    print("\n=== 3. 70地点を最寄りdriveノードへ接続 ===")

    (
        node_map,
        snap_distance_map,
    ) = nearest_nodes_without_sklearn(
        graph,
        points,
    )

    validate_snap_distances(
        snap_distance_map,
    )

    print("\n=== 4. 全地点間ルート事前計算 ===")

    matrix: dict[str, dict[str, Any]] = {}

    total_pairs = (
        len(points)
        * (len(points) - 1)
    )

    completed = 0
    available_count = 0

    for origin in points:
        origin_name = origin["name"]

        matrix[origin_name] = {}

        for destination in points:
            destination_name = destination["name"]

            if origin_name == destination_name:
                matrix[origin_name][destination_name] = {
                    "available": True,
                    "distance_meters": 0.0,
                    "distance_km": 0.0,
                    "duration_seconds": 0.0,
                    "duration_minutes": 0.0,
                }
                continue

            completed += 1

            try:
                metrics = route_metrics(
                    graph,
                    node_map[origin_name],
                    node_map[destination_name],
                    origin,
                    destination,
                )

            except Exception as exc:
                metrics = None

                print(
                    f"ルート失敗: "
                    f"{origin_name} -> "
                    f"{destination_name} / "
                    f"{type(exc).__name__}: {exc}"
                )

            if metrics is None:
                matrix[origin_name][destination_name] = {
                    "available": False,
                    "distance_meters": None,
                    "distance_km": None,
                    "duration_seconds": None,
                    "duration_minutes": None,
                }

            else:
                matrix[origin_name][destination_name] = metrics
                available_count += 1

            if (
                completed % 100 == 0
                or completed == total_pairs
            ):
                print(
                    f"{completed}/{total_pairs} 完了 "
                    f"(成功 {available_count})"
                )

    payload = {
        "schema_version": 3,
        "region": "川越",
        "provider": "OpenStreetMap + OSMnx local precomputed matrix",
        "runtime_external_route_api": False,
        "runtime_geocoding": False,
        "network_type": "drive",
        "route_weight": "travel_time",
        "travel_time_note": (
            "OpenStreetMap道路属性とOSMnx推定速度から算出した事前計算値。"
            "Google Mapsのリアルタイム交通情報ではない。"
        ),
        "location_count": len(points),
        "pair_count": total_pairs,
        "available_pair_count": available_count,
        "graph_file": GRAPH_FILE.name,
        "locations": {
            item["name"]: {
                "category": item.get("category"),
                "address": item.get("address"),
                "latitude": item["latitude"],
                "longitude": item["longitude"],
                "node_id": node_map[item["name"]],
                "snap_distance_meters": snap_distance_map[item["name"]],
                "coordinate_source": item.get("coordinate_source"),
            }
            for item in points
        },
        "routes": matrix,
    }

    save_json(
        ROUTE_MATRIX_FILE,
        payload,
    )

    print("\n" + "=" * 76)
    print("川越ルート行列 作成完了")
    print("=" * 76)

    print(
        "出力:",
        ROUTE_MATRIX_FILE,
    )
    print(
        "道路グラフ:",
        GRAPH_FILE,
    )
    print(
        "地点数:",
        len(points),
    )
    print(
        "対象区間:",
        total_pairs,
    )
    print(
        "取得成功:",
        available_count,
    )
    print(
        "取得失敗:",
        total_pairs - available_count,
    )
    print(
        "実行時の外部ルートAPI: 使用しない"
    )

    if (
        len(points) == 70
        and total_pairs == 4830
        and available_count == 4830
    ):
        print(
            "[KAWAGOE LOCAL ROUTE MATRIX] "
            "locations = 70 | "
            "pairs = 4830 | "
            "available = 4830 | COMPLETE"
        )

    else:
        print(
            "[KAWAGOE LOCAL ROUTE MATRIX] "
            f"locations = {len(points)} | "
            f"pairs = {total_pairs} | "
            f"available = {available_count} | "
            "CHECK REQUIRED"
        )


if __name__ == "__main__":
    build_route_matrix()
