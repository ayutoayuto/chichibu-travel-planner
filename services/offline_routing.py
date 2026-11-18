from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
ROUTE_MATRIX_FILE = BASE_DIR / "data" / "route_matrix.json"

_ROUTE_MATRIX_CACHE: dict[str, Any] | None = None


def _load_route_matrix() -> dict[str, Any]:
    global _ROUTE_MATRIX_CACHE

    if _ROUTE_MATRIX_CACHE is not None:
        return _ROUTE_MATRIX_CACHE

    if not ROUTE_MATRIX_FILE.exists():
        raise FileNotFoundError(
            "data/route_matrix.json がありません。"
            "先に `python tools/build_offline_routes.py` を実行してください。"
        )

    with ROUTE_MATRIX_FILE.open("r", encoding="utf-8") as f:
        value = json.load(f)

    if not isinstance(value, dict):
        raise ValueError("route_matrix.json の形式が不正です。")

    routes = value.get("routes")
    if not isinstance(routes, dict):
        raise ValueError("route_matrix.json に routes がありません。")

    _ROUTE_MATRIX_CACHE = value
    return value


def clear_route_matrix_cache() -> None:
    global _ROUTE_MATRIX_CACHE
    _ROUTE_MATRIX_CACHE = None


def get_route_between_names(
    origin_name: str,
    destination_name: str,
) -> dict[str, Any] | None:
    """
    事前計算済みの道路距離・所要時間を返す。
    実行時の外部ルートAPI呼び出しは行わない。
    """

    origin_name = str(origin_name or "").strip()
    destination_name = str(destination_name or "").strip()

    if not origin_name or not destination_name:
        return None

    data = _load_route_matrix()
    routes = data["routes"]

    origin_routes = routes.get(origin_name)
    if not isinstance(origin_routes, dict):
        return None

    route = origin_routes.get(destination_name)
    if not isinstance(route, dict):
        return None

    if route.get("available") is not True:
        return None

    return {
        "available": True,
        "provider": "OpenStreetMap + OSMnx / local route matrix",
        "origin_name": origin_name,
        "destination_name": destination_name,
        "distance_meters": route.get("distance_meters"),
        "distance_km": route.get("distance_km"),
        "duration_seconds": route.get("duration_seconds"),
        "duration_minutes": route.get("duration_minutes"),
        "runtime_external_api": False,
    }


def has_route_matrix() -> bool:
    try:
        _load_route_matrix()
        return True
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def get_route_matrix_summary() -> dict[str, Any]:
    data = _load_route_matrix()

    return {
        "provider": data.get("provider"),
        "runtime_external_route_api": data.get("runtime_external_route_api"),
        "location_count": data.get("location_count"),
        "pair_count": data.get("pair_count"),
        "available_pair_count": data.get("available_pair_count"),
    }
