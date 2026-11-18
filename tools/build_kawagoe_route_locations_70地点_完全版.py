from __future__ import annotations

import json
import math
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

FACILITY_FILE = DATA_DIR / "kawagoe_facilities_master.json"
RESTAURANT_FILE = DATA_DIR / "kawagoe_restaurants.json"

OUTPUT_FILE = DATA_DIR / "kawagoe_route_locations.json"
REVIEW_FILE = DATA_DIR / "kawagoe_route_locations_review.json"

# 川越市＋市境付近を十分含む安全範囲。
# この範囲外の自動取得結果は採用しない。
SAFE_LAT_MIN = 35.80
SAFE_LAT_MAX = 36.05
SAFE_LON_MIN = 139.35
SAFE_LON_MAX = 139.60

USER_AGENT = "SaitamaSouthwestTourismPlanner/1.0 (academic project)"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# 「住所が一点ではない」「住所が省略されている」場所だけ検索語を固定する。
# 数値座標を手入力せず、OpenStreetMap上の実体を名前で検索する。
SEARCH_OVERRIDES: dict[str, list[str]] = {
    "蔵造りの町並み": [
        "蔵造りの町並み, 川越市, 埼玉県, 日本",
        "一番街, 川越市, 埼玉県, 日本",
    ],
    "大正浪漫夢通り": [
        "大正浪漫夢通り, 川越市, 埼玉県, 日本",
    ],
    "伊佐沼": [
        "伊佐沼, 川越市, 埼玉県, 日本",
    ],
    "成田山川越別院": [
        "成田山川越別院, 川越市, 埼玉県, 日本",
    ],
    "Te’PAN Le OMUS": [
        "Te'PAN Le OMUS, 川越市, 埼玉県, 日本",
        "Te’PAN Le OMUS, 川越市, 埼玉県, 日本",
    ],
}

# 同名・曖昧名称の補助。
NAME_QUERY_SUFFIX = ", 川越市, 埼玉県, 日本"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"必要ファイルがありません: {path}")

    with path.open("r", encoding="utf-8") as f:
        value = json.load(f)

    if not isinstance(value, dict):
        raise ValueError(f"{path.name} のJSON形式が不正です。")

    return value


def normalize_address(value: Any) -> str:
    text = str(value or "").strip()
    text = text.replace("〒", "")
    return " ".join(text.split())


def extract_facility_address(item: dict[str, Any]) -> str:
    basic = item.get("basic")
    if isinstance(basic, dict):
        address = basic.get("address")
        if address:
            return normalize_address(address)

    contact = item.get("contact")
    if isinstance(contact, dict):
        address = contact.get("address")
        if address:
            return normalize_address(address)

    address = item.get("address")
    return normalize_address(address)


def extract_restaurant_address(item: dict[str, Any]) -> str:
    return normalize_address(item.get("address"))


def is_safe(lat: float, lon: float) -> bool:
    return (
        math.isfinite(lat)
        and math.isfinite(lon)
        and SAFE_LAT_MIN <= lat <= SAFE_LAT_MAX
        and SAFE_LON_MIN <= lon <= SAFE_LON_MAX
    )


def geocode_one(query: str) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode(
        {
            "q": query,
            "format": "jsonv2",
            "limit": 5,
            "countrycodes": "jp",
            "addressdetails": 1,
        }
    )

    req = urllib.request.Request(
        f"{NOMINATIM_URL}?{params}",
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )

    with urllib.request.urlopen(req, timeout=30) as response:
        raw = response.read().decode("utf-8")

    result = json.loads(raw)

    if not isinstance(result, list):
        return []

    return result


def candidate_score(
    result: dict[str, Any],
    name: str,
    address: str,
) -> int:
    display_name = str(result.get("display_name") or "")
    score = 0

    # 川越・埼玉を含む結果を強く優先
    if "川越" in display_name:
        score += 100
    if "埼玉" in display_name:
        score += 30

    # 名称一致
    compact_name = name.replace(" ", "").replace("　", "")
    compact_display = display_name.replace(" ", "").replace("　", "")
    if compact_name and compact_name in compact_display:
        score += 60

    # 住所の町名・番地断片の一致を補助
    for token in (
        "幸町", "元町", "仲町", "連雀町", "松江町", "郭町",
        "宮下町", "久保町", "南通町", "小仙波町", "西小仙波町",
        "新富町", "脇田町", "脇田本町", "菅原町", "富士見町",
        "三久保町", "六軒町", "石原町", "藤間", "今成", "大手町",
        "八ツ島", "的場", "上戸"
    ):
        if token in address and token in display_name:
            score += 15

    return score


def build_queries(name: str, address: str) -> list[str]:
    queries: list[str] = []

    # 公式住所を最優先
    if address:
        queries.append(f"{address}, 日本")

    # エリア型スポットなどは専用検索
    for q in SEARCH_OVERRIDES.get(name, []):
        if q not in queries:
            queries.append(q)

    # 最後に名称検索
    q = f"{name}{NAME_QUERY_SUFFIX}"
    if q not in queries:
        queries.append(q)

    return queries


def choose_result(
    name: str,
    address: str,
    results: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, str | None]:
    candidates: list[tuple[int, dict[str, Any]]] = []

    for result in results:
        try:
            lat = float(result.get("lat"))
            lon = float(result.get("lon"))
        except (TypeError, ValueError):
            continue

        if not is_safe(lat, lon):
            continue

        score = candidate_score(result, name, address)
        candidates.append((score, result))

    if not candidates:
        return None, None

    candidates.sort(key=lambda x: x[0], reverse=True)

    best_score, best = candidates[0]

    # 川越市内と判定できない低スコア結果は自動採用しない。
    if best_score < 100:
        return None, "low_confidence"

    return best, None


def collect_catalog() -> list[dict[str, Any]]:
    facilities_data = load_json(FACILITY_FILE)
    restaurants_data = load_json(RESTAURANT_FILE)

    facilities = facilities_data.get("facilities", [])
    restaurants = restaurants_data.get("restaurants", [])

    if not isinstance(facilities, list):
        raise ValueError("kawagoe_facilities_master.json の facilities がlistではありません。")

    if not isinstance(restaurants, list):
        raise ValueError("kawagoe_restaurants.json の restaurants がlistではありません。")

    catalog: list[dict[str, Any]] = []

    for item in facilities:
        if not isinstance(item, dict):
            continue

        name = str(item.get("name") or "").strip()
        if not name:
            continue

        catalog.append(
            {
                "name": name,
                "category": str(item.get("category") or "facility"),
                "address": extract_facility_address(item),
            }
        )

    for item in restaurants:
        if not isinstance(item, dict):
            continue

        name = str(item.get("name") or "").strip()
        if not name:
            continue

        catalog.append(
            {
                "name": name,
                "category": "gourmet",
                "address": extract_restaurant_address(item),
            }
        )

    return catalog


def main() -> None:
    catalog = collect_catalog()

    # 現在の川越データ仕様では 40施設 + 30飲食店 = 70地点。
    if len(catalog) != 70:
        raise RuntimeError(
            f"川越地点数が70ではありません。現在 {len(catalog)} 地点です。"
        )

    names = [x["name"] for x in catalog]
    if len(names) != len(set(names)):
        duplicates = sorted({x for x in names if names.count(x) > 1})
        raise RuntimeError(f"施設名が重複しています: {duplicates}")

    route_locations: dict[str, dict[str, Any]] = {}
    review: dict[str, dict[str, Any]] = {}

    print("=" * 70)
    print("川越70地点 座標取得開始")
    print("=" * 70)

    for index, item in enumerate(catalog, start=1):
        name = item["name"]
        address = item["address"]
        category = item["category"]

        print(f"[{index:02d}/70] {name}")

        queries = build_queries(name, address)
        all_results: list[dict[str, Any]] = []
        used_query = None

        for query in queries:
            try:
                results = geocode_one(query)
            except Exception as exc:
                print("  GEOCODE ERROR:", repr(exc))
                time.sleep(1.2)
                continue

            # Nominatim利用ポリシーに配慮して間隔を空ける
            time.sleep(1.2)

            if results:
                all_results.extend(results)
                used_query = query

            best, reason = choose_result(name, address, all_results)
            if best is not None:
                break

        best, reason = choose_result(name, address, all_results)

        if best is None:
            review[name] = {
                "category": category,
                "address": address,
                "status": "manual_review_required",
                "reason": reason or "no_safe_result",
                "queries": queries,
                "returned_candidates": [
                    {
                        "display_name": str(x.get("display_name") or ""),
                        "lat": x.get("lat"),
                        "lon": x.get("lon"),
                        "type": x.get("type"),
                    }
                    for x in all_results[:10]
                ],
            }
            print("  -> 要確認")
            continue

        lat = round(float(best["lat"]), 8)
        lon = round(float(best["lon"]), 8)

        route_locations[name] = {
            "category": category,
            "address": address,
            "latitude": lat,
            "longitude": lon,
            "coordinate_source": "OpenStreetMap Nominatim",
            "geocode_query": used_query,
            "geocode_display_name": str(best.get("display_name") or ""),
            "verified_at": "2026-11-18",
        }

        print(f"  -> {lat}, {lon}")

    # 異常な完全重複座標を検出。
    coord_to_names: dict[tuple[float, float], list[str]] = {}

    for name, item in route_locations.items():
        key = (
            float(item["latitude"]),
            float(item["longitude"]),
        )
        coord_to_names.setdefault(key, []).append(name)

    duplicate_coords = {
        f"{lat},{lon}": names
        for (lat, lon), names in coord_to_names.items()
        if len(names) >= 2
    }

    # 近接施設が同じOSMノード・建物中心点になる場合もあるので
    # 自動削除はせず review に記録する。
    if duplicate_coords:
        review["_duplicate_coordinates"] = {
            "status": "manual_review_required",
            "groups": duplicate_coords,
        }

    output = {
        "meta": {
            "schema_version": 1,
            "region": "川越",
            "generated_at": "2026-11-18",
            "expected_location_count": 70,
            "resolved_count": len(route_locations),
            "manual_review_count": len(
                [k for k in review.keys() if not k.startswith("_")]
            ),
            "coordinate_provider": "OpenStreetMap Nominatim",
            "runtime_geocoding": False,
            "safe_bounds": {
                "lat_min": SAFE_LAT_MIN,
                "lat_max": SAFE_LAT_MAX,
                "lon_min": SAFE_LON_MIN,
                "lon_max": SAFE_LON_MAX,
            },
            "note": (
                "このJSONはルート行列作成前の固定座標DB。"
                "Webアプリ実行時にジオコードは行わない。"
            ),
        },
        "route_locations": route_locations,
    }

    review_output = {
        "meta": {
            "region": "川越",
            "generated_at": "2026-11-18",
            "review_required": bool(review),
        },
        "review": review,
    }

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    with REVIEW_FILE.open("w", encoding="utf-8") as f:
        json.dump(review_output, f, ensure_ascii=False, indent=2)

    print()
    print("=" * 70)
    print("完了")
    print("=" * 70)
    print("解決:", len(route_locations), "/ 70")
    print(
        "要確認:",
        len([k for k in review.keys() if not k.startswith("_")]),
    )
    print("出力:", OUTPUT_FILE)
    print("確認用:", REVIEW_FILE)

    if len(route_locations) == 70 and not duplicate_coords:
        print("[KAWAGOE ROUTE LOCATIONS] 70 / 70 OK")
    else:
        print(
            "[KAWAGOE ROUTE LOCATIONS] "
            "未確定地点があります。review JSONを確認してください。"
        )


if __name__ == "__main__":
    main()
