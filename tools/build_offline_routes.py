from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import osmnx as ox
import networkx as nx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

FACILITY_MASTER_FILE = DATA_DIR / "facilities_master.json"
RESTAURANT_FILE = DATA_DIR / "restaurants.json"
ROUTE_LOCATION_FILE = DATA_DIR / "route_locations.json"
VERIFIED_LOCATION_FILE = DATA_DIR / "verified_route_locations.json"

ROUTE_MATRIX_FILE = DATA_DIR / "route_matrix.json"
GRAPH_FILE = DATA_DIR / "chichibu_drive_verified_v3.graphml"
VALIDATED_LOCATION_FILE = DATA_DIR / "validated_route_locations.json"

# 秩父・長瀞・横瀬・皆野・小鹿野〜花園ICまでを含む固定範囲。
SAFE_LAT_MIN = 35.80
SAFE_LAT_MAX = 36.24
SAFE_LON_MIN = 138.78
SAFE_LON_MAX = 139.30

GRAPH_BBOX = (
    SAFE_LON_MIN,
    SAFE_LAT_MIN,
    SAFE_LON_MAX,
    SAFE_LAT_MAX,
)

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
        json.dump(value, f, ensure_ascii=False, indent=2)


def as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def extract_coords(item: dict[str, Any]) -> tuple[float | None, float | None]:
    lat = as_float(item.get("latitude"))
    lon = as_float(item.get("longitude"))

    if lat is None:
        lat = as_float(item.get("lat"))
    if lon is None:
        lon = as_float(item.get("lng"))

    basic = item.get("basic")
    if isinstance(basic, dict):
        if lat is None:
            lat = as_float(basic.get("latitude"))
        if lon is None:
            lon = as_float(basic.get("longitude"))

    return lat, lon


def extract_address(item: dict[str, Any]) -> str:
    address = item.get("address")

    if isinstance(address, dict):
        address = address.get("full") or address.get("text")

    if not address:
        basic = item.get("basic")
        if isinstance(basic, dict):
            address = basic.get("address")

    return str(address or "").strip()


def is_safe(lat: float, lon: float) -> bool:
    return (
        SAFE_LAT_MIN <= lat <= SAFE_LAT_MAX
        and SAFE_LON_MIN <= lon <= SAFE_LON_MAX
    )


def collect_catalog() -> dict[str, dict[str, Any]]:
    """
    座標の採用優先順位:
      1. verified_route_locations.json
      2. route_locations.json
      3. facilities_master / restaurants 内の既存座標

    旧 offline_route_locations.json は一切読み込まない。
    Nominatim等の自動ジオコードも一切行わない。
    """

    facilities_data = load_json(FACILITY_MASTER_FILE)
    restaurant_data = load_json(RESTAURANT_FILE)
    route_location_data = load_json(ROUTE_LOCATION_FILE)
    verified_data = load_json(VERIFIED_LOCATION_FILE)

    facilities = facilities_data.get("facilities", [])
    restaurants = restaurant_data.get("restaurants", [])
    route_locations = route_location_data.get("route_locations", {})
    verified_locations = verified_data.get("locations", {})

    if not isinstance(facilities, list):
        raise ValueError("facilities_master.json の facilities がlistではありません。")
    if not isinstance(restaurants, list):
        raise ValueError("restaurants.json の restaurants がlistではありません。")
    if not isinstance(route_locations, dict):
        raise ValueError("route_locations.json の route_locations がdictではありません。")
    if not isinstance(verified_locations, dict):
        raise ValueError("verified_route_locations.json の locations がdictではありません。")

    catalog: dict[str, dict[str, Any]] = {}

    def ensure(name: str, category: str = "location") -> dict[str, Any]:
        if name not in catalog:
            catalog[name] = {
                "name": name,
                "category": category,
                "address": "",
                "latitude": None,
                "longitude": None,
                "coordinate_source": None,
            }
        return catalog[name]

    # まず施設と飲食店の全名称を登録。
    for item in facilities:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("official_name") or "").strip()
        if not name:
            continue
        current = ensure(name, str(item.get("category") or "facility"))
        if not current["address"]:
            current["address"] = extract_address(item)
        lat, lon = extract_coords(item)
        if lat is not None and lon is not None:
            current["latitude"] = lat
            current["longitude"] = lon
            current["coordinate_source"] = "facilities_master.json"

    for item in restaurants:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("official_name") or "").strip()
        if not name:
            continue
        current = ensure(name, str(item.get("category") or "restaurant"))
        if not current["address"]:
            current["address"] = extract_address(item)
        lat, lon = extract_coords(item)
        if lat is not None and lon is not None:
            current["latitude"] = lat
            current["longitude"] = lon
            current["coordinate_source"] = "restaurants.json"

    # route_locations は既存確認済みデータとして上書き。
    for name, item in route_locations.items():
        if not isinstance(item, dict):
            continue
        name = str(name).strip()
        if not name:
            continue
        current = ensure(name, str(item.get("route_point_type") or "route_location"))
        address = extract_address(item)
        if address:
            current["address"] = address
        lat, lon = extract_coords(item)
        if lat is not None and lon is not None:
            current["latitude"] = lat
            current["longitude"] = lon
            current["coordinate_source"] = "route_locations.json"

    # 最後に今回の検証済み固定値で必ず上書き。
    for name, item in verified_locations.items():
        if not isinstance(item, dict):
            continue
        name = str(name).strip()
        current = ensure(name, "verified_location")
        lat, lon = extract_coords(item)

        if lat is None or lon is None:
            raise ValueError(f"検証済みファイルの座標が欠けています: {name}")

        current["latitude"] = lat
        current["longitude"] = lon
        current["address"] = str(item.get("address") or current.get("address") or "")
        current["coordinate_source"] = "verified_route_locations.json"
        current["verification_method"] = item.get("verification_method")
        current["verification_level"] = item.get("verification_level")

    return catalog


def validate_catalog(catalog: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    missing = []
    outside = []
    usable = []

    for name, item in catalog.items():
        lat = as_float(item.get("latitude"))
        lon = as_float(item.get("longitude"))

        if lat is None or lon is None:
            missing.append(name)
            continue

        if not is_safe(lat, lon):
            outside.append((name, lat, lon))
            continue

        copied = dict(item)
        copied["latitude"] = lat
        copied["longitude"] = lon
        usable.append(copied)

    if missing or outside:
        print("\n=== 座標検証NG ===")
        if missing:
            print("\n座標未登録:")
            for name in missing:
                print(f"  - {name}")

        if outside:
            print("\n対象範囲外:")
            for name, lat, lon in outside:
                print(f"  - {name}: {lat}, {lon}")

        raise RuntimeError(
            "座標が完全ではないため、route_matrix.json は生成しません。"
        )

    # 同一名称重複はdictで排除済み。
    # 同一座標は同一建物内店舗等があるためエラーにはしない。
    usable.sort(key=lambda x: x["name"])

    save_json(
        VALIDATED_LOCATION_FILE,
        {
            "schema_version": 3,
            "location_count": len(usable),
            "locations": {
                item["name"]: {
                    "category": item.get("category"),
                    "address": item.get("address"),
                    "latitude": item["latitude"],
                    "longitude": item["longitude"],
                    "coordinate_source": item.get("coordinate_source"),
                    "verification_method": item.get("verification_method"),
                    "verification_level": item.get("verification_level"),
                }
                for item in usable
            },
        },
    )

    return usable


def split_bbox(
    bbox: tuple[float, float, float, float],
    rows: int = 4,
    cols: int = 4,
    overlap: float = 0.003,
) -> list[tuple[float, float, float, float]]:
    """大きな取得範囲を小さいbboxへ分割する。"""
    left, bottom, right, top = bbox
    width = (right - left) / cols
    height = (top - bottom) / rows

    tiles: list[tuple[float, float, float, float]] = []

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

            tiles.append(
                (tile_left, tile_bottom, tile_right, tile_top)
            )

    return tiles


def download_graph_tile(
    bbox: tuple[float, float, float, float],
    tile_no: int,
    total_tiles: int,
):
    """1区画の道路データを複数のOverpass候補から取得する。"""

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


def build_or_load_graph():
    if GRAPH_FILE.exists():
        print(f"既存の検証済み道路グラフを読み込み: {GRAPH_FILE}")
        return ox.io.load_graphml(GRAPH_FILE)

    print("OpenStreetMap道路データを分割取得します（初回のみ）。")
    print("全体bbox =", GRAPH_BBOX)

    tiles = split_bbox(
        GRAPH_BBOX,
        rows=4,
        cols=4,
        overlap=0.003,
    )

    print(f"取得区画数: {len(tiles)}")

    tile_graphs = []

    for index, bbox in enumerate(tiles, start=1):
        graph = download_graph_tile(
            bbox,
            tile_no=index,
            total_tiles=len(tiles),
        )
        tile_graphs.append(graph)

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

    ox.io.save_graphml(graph, GRAPH_FILE)

    print(f"道路グラフ保存: {GRAPH_FILE}")
    print(
        f"最終道路グラフ: nodes={len(graph.nodes):,}, "
        f"edges={len(graph.edges):,}"
    )

    return graph


def nearest_nodes(graph, points: list[dict[str, Any]]) -> dict[str, int]:
    names = [item["name"] for item in points]
    xs = [float(item["longitude"]) for item in points]
    ys = [float(item["latitude"]) for item in points]

    nodes = ox.distance.nearest_nodes(graph, X=xs, Y=ys)

    return {
        name: int(node)
        for name, node in zip(names, nodes)
    }


def haversine_distance_m(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """2地点間の直線距離をメートルで計算する。"""
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


def route_metrics(
    graph,
    origin_node: int,
    destination_node: int,
    origin: dict[str, Any],
    destination: dict[str, Any],
) -> dict[str, Any] | None:
    # 同じ道路ノードに割り当てられた近距離施設は、
    # route_to_gdf に渡すと "Graph contains no edges" になるため補正する。
    if origin_node == destination_node:
        distance_m = haversine_distance_m(
            float(origin["latitude"]),
            float(origin["longitude"]),
            float(destination["latitude"]),
            float(destination["longitude"]),
        )

        # 同一道路ノードに吸着した施設間のみの近距離補正。
        # 施設周辺の低速移動として15km/h相当で所要時間を推定する。
        speed_kmh = 15.0
        duration_minutes = (distance_m / 1000.0) / speed_kmh * 60.0
        duration_minutes = max(duration_minutes, 0.5)
        duration_s = duration_minutes * 60.0

        return {
            "available": True,
            "distance_meters": round(distance_m, 1),
            "distance_km": round(distance_m / 1000.0, 2),
            "duration_seconds": round(duration_s, 1),
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


def build_route_matrix() -> None:
    print("=== 1. 最新データ読込 ===")
    catalog = collect_catalog()
    print(f"登録地点総数: {len(catalog)}")

    print("\n=== 2. 固定座標の完全検証 ===")
    points = validate_catalog(catalog)
    print(f"座標検証OK: {len(points)}地点")
    print("旧 offline_route_locations.json は使用していません。")
    print("Nominatimも使用していません。")

    print("\n=== 3. 道路ネットワーク準備 ===")
    graph = build_or_load_graph()

    print("\n=== 4. 各地点を道路ノードへ対応 ===")
    node_map = nearest_nodes(graph, points)

    print("\n=== 5. 全地点間ルート事前計算 ===")
    matrix: dict[str, dict[str, Any]] = {}
    total_pairs = len(points) * (len(points) - 1)
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
                print(f"ルート失敗: {origin_name} -> {destination_name} / {exc}")

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

            if completed % 100 == 0 or completed == total_pairs:
                print(
                    f"{completed}/{total_pairs} 完了 "
                    f"(成功 {available_count})"
                )

    payload = {
        "schema_version": 3,
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
        "locations": {
            item["name"]: {
                "category": item.get("category"),
                "address": item.get("address"),
                "latitude": item["latitude"],
                "longitude": item["longitude"],
                "node_id": node_map[item["name"]],
                "coordinate_source": item.get("coordinate_source"),
            }
            for item in points
        },
        "routes": matrix,
    }

    save_json(ROUTE_MATRIX_FILE, payload)

    print("\n=== 完了 ===")
    print(f"出力: {ROUTE_MATRIX_FILE}")
    print(f"地点数: {len(points)}")
    print(f"対象区間: {total_pairs}")
    print(f"取得成功: {available_count}")
    print(f"取得失敗: {total_pairs - available_count}")
    print("実行時の外部ルートAPI: 使用しない")


if __name__ == "__main__":
    build_route_matrix()
