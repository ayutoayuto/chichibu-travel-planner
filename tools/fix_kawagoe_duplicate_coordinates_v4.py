from __future__ import annotations

import json
import math
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

ROUTE_FILE = DATA_DIR / "kawagoe_route_locations.json"
BACKUP_FILE = DATA_DIR / "kawagoe_route_locations_before_v4.json"
REVIEW_FILE = DATA_DIR / "kawagoe_route_locations_v4_review.json"

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "SaitamaSouthwestTourismPlanner/4.0 (academic project)"

KAWAGOE_CENTER_LAT = 35.9251
KAWAGOE_CENTER_LON = 139.4858

TARGETS = {
    "松村屋旅館": {
        "address": "埼玉県川越市元町1-1-11",
        "queries": [
            "松村屋旅館, 埼玉県川越市元町1-1-11, 日本",
            "Matsumuraya, 1-1-11 Motomachi, Kawagoe, Saitama, Japan",
        ],
        "name_tokens": ["松村屋", "Matsumuraya"],
    },
    "glin coffee 元町1号店": {
        "address": "埼玉県川越市元町1-1-20",
        "queries": [
            "glin coffee 元町1号店, 埼玉県川越市元町1-1-20, 日本",
            "glin coffee, 1-1-20 Motomachi, Kawagoe, Saitama, Japan",
        ],
        "name_tokens": ["glin", "グリン"],
    },
    "寿庵 蔵のまち店": {
        "address": "埼玉県川越市幸町3-18",
        "queries": [
            "寿庵 蔵のまち店, 埼玉県川越市幸町3-18, 日本",
            "Kotobukian Kuranomachi, 3-18 Saiwaicho, Kawagoe, Saitama, Japan",
        ],
        "name_tokens": ["寿庵", "Kotobukian"],
    },
    "une brise": {
        "address": "埼玉県川越市幸町3-8",
        "queries": [
            "une brise, 埼玉県川越市幸町3-8, 日本",
            "ユヌブリーズ, 埼玉県川越市幸町3-8, 日本",
        ],
        "name_tokens": ["une", "ユヌ"],
    },
    "海鮮料理 近長魚店": {
        "address": "埼玉県川越市幸町6-11",
        "queries": [
            "海鮮料理 近長魚店, 埼玉県川越市幸町6-11, 日本",
            "近長魚店, 埼玉県川越市幸町6-11, 日本",
            "Kincho Seafoods, 6-11 Saiwaicho, Kawagoe, Saitama, Japan",
        ],
        "name_tokens": ["近長", "Kincho"],
    },
    "甘味茶房 かすが": {
        "address": "埼玉県川越市幸町6-1",
        "queries": [
            "甘味茶房 かすが, 埼玉県川越市幸町6-1, 日本",
            "かすが, 埼玉県川越市幸町6-1, 日本",
            "Kanmi Sabo Kasuga, 6-1 Saiwaicho, Kawagoe, Saitama, Japan",
        ],
        "name_tokens": ["かすが", "Kasuga"],
    },
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8") as f:
        value = json.load(f)
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} の形式が不正です。")
    return value


def save_json(path: Path, value: Any) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)


def normalize(value: Any) -> str:
    return re.sub(r"[\s　〒\-‐－ー・.,，。()（）]", "", str(value or "")).lower()


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def safe(lat: float, lon: float) -> bool:
    if not (35.82 <= lat <= 36.02 and 139.36 <= lon <= 139.58):
        return False
    return haversine_km(KAWAGOE_CENTER_LAT, KAWAGOE_CENTER_LON, lat, lon) <= 12.0


def search(query: str) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode(
        {
            "q": query,
            "format": "jsonv2",
            "limit": 10,
            "countrycodes": "jp",
            "addressdetails": 1,
            "namedetails": 1,
            "dedupe": 0,
        }
    )
    req = urllib.request.Request(
        f"{NOMINATIM_URL}?{params}",
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Accept-Language": "ja,en",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))
    return data if isinstance(data, list) else []


def choose_poi(name: str, spec: dict[str, Any]) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []

    for query in spec["queries"]:
        try:
            results = search(query)
        except Exception as exc:
            print("    API ERROR:", repr(exc))
            time.sleep(1.2)
            continue

        time.sleep(1.2)

        for item in results:
            try:
                lat = float(item["lat"])
                lon = float(item["lon"])
            except (KeyError, TypeError, ValueError):
                continue

            if not safe(lat, lon):
                continue

            display = str(item.get("display_name") or "")
            namedetails = item.get("namedetails")
            if not isinstance(namedetails, dict):
                namedetails = {}

            haystack = normalize(
                display
                + " "
                + " ".join(str(v) for v in namedetails.values())
            )

            token_match = any(
                normalize(token) in haystack
                for token in spec["name_tokens"]
            )

            # 店名POIが確認できない住所点は採用しない。
            if not token_match:
                continue

            score = 0
            if "川越" in display:
                score += 100
            if token_match:
                score += 200

            osm_type = str(item.get("type") or "")
            osm_class = str(item.get("class") or "")
            if osm_class in {"amenity", "tourism", "shop", "building"}:
                score += 30
            if osm_type not in {"administrative", "city", "town"}:
                score += 20

            candidates.append(
                {
                    "score": score,
                    "latitude": lat,
                    "longitude": lon,
                    "display_name": display,
                    "osm_type": osm_type,
                    "osm_class": osm_class,
                    "query": query,
                }
            )

    if not candidates:
        return None

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[0]


def duplicate_groups(locations: dict[str, Any]) -> dict[str, list[str]]:
    groups: dict[tuple[float, float], list[str]] = {}

    for name, item in locations.items():
        try:
            lat = round(float(item["latitude"]), 8)
            lon = round(float(item["longitude"]), 8)
        except (KeyError, TypeError, ValueError):
            continue
        groups.setdefault((lat, lon), []).append(name)

    return {
        f"{lat},{lon}": names
        for (lat, lon), names in groups.items()
        if len(names) > 1
    }


def main() -> None:
    data = load_json(ROUTE_FILE)
    locations = data.get("route_locations")

    if not isinstance(locations, dict):
        raise ValueError("route_locations がdictではありません。")

    if len(locations) != 70:
        raise RuntimeError(f"v3が70地点ではありません: {len(locations)}")

    save_json(BACKUP_FILE, data)

    before = duplicate_groups(locations)

    print("=" * 72)
    print("川越 重複座標修正 v4")
    print("=" * 72)
    print("修正前の重複座標グループ:", len(before))
    print()

    review: dict[str, Any] = {}

    for index, (name, spec) in enumerate(TARGETS.items(), start=1):
        print(f"[{index:02d}/06] {name}")

        old = locations.get(name)
        if not isinstance(old, dict):
            review[name] = {"status": "missing_from_route_locations"}
            print("  -> ERROR: v3に地点がありません")
            continue

        old_lat = old.get("latitude")
        old_lon = old.get("longitude")

        best = choose_poi(name, spec)

        if best is None:
            review[name] = {
                "status": "poi_not_found",
                "address": spec["address"],
                "old_coordinate": [old_lat, old_lon],
                "note": "店名が一致するPOI座標を取得できなかったため、v3座標を保持。",
            }
            print("  -> POI未取得。v3座標を保持")
            continue

        new_lat = round(float(best["latitude"]), 8)
        new_lon = round(float(best["longitude"]), 8)

        locations[name] = {
            **old,
            "address": spec["address"],
            "latitude": new_lat,
            "longitude": new_lon,
            "coordinate_source": "OpenStreetMap Nominatim exact POI v4",
            "verification_method": "exact_name_and_official_address_poi_match",
            "geocode_query": best["query"],
            "geocode_display_name": best["display_name"],
            "verified_at": "2026-11-18",
        }

        print(
            f"  -> POI FIXED {new_lat}, {new_lon}"
            f" | {best['display_name']}"
        )

    after = duplicate_groups(locations)

    data["meta"]["schema_version"] = 4
    data["meta"]["generated_at"] = "2026-11-18"
    data["meta"]["resolved_count"] = len(locations)
    data["meta"]["manual_review_count"] = len(
        [x for x in review.values() if x.get("status") == "poi_not_found"]
    )
    data["meta"]["v4_note"] = (
        "v3で国土地理院住所検索が同一点を返した近接別番地3組について、"
        "店名＋公式住所でOSM POIを再検索。POI名一致時のみ座標を置換。"
        "POI未取得時は座標を推測せずv3値を保持。"
    )

    save_json(ROUTE_FILE, data)

    save_json(
        REVIEW_FILE,
        {
            "meta": {
                "region": "川越",
                "schema_version": 4,
                "generated_at": "2026-11-18",
            },
            "duplicate_groups_before": before,
            "duplicate_groups_after": after,
            "review": review,
        },
    )

    print()
    print("=" * 72)
    print("v4 完了")
    print("=" * 72)
    print("地点数:", len(locations), "/ 70")
    print("修正前の重複座標グループ:", len(before))
    print("修正後の重複座標グループ:", len(after))
    print("POI未取得:", sum(1 for x in review.values() if x.get("status") == "poi_not_found"))
    print("バックアップ:", BACKUP_FILE)
    print("出力:", ROUTE_FILE)
    print("確認用:", REVIEW_FILE)

    if len(locations) == 70 and len(after) == 0:
        print("[KAWAGOE ROUTE LOCATIONS V4] 70 / 70 | DUPLICATES 0 | COMPLETE")
    else:
        print("[KAWAGOE ROUTE LOCATIONS V4] 追加確認が必要です。")
        if after:
            print("残存重複:")
            for coord, names in after.items():
                print(" ", coord, "=>", " / ".join(names))


if __name__ == "__main__":
    main()
