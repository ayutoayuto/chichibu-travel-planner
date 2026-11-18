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

FACILITY_FILE = DATA_DIR / "kawagoe_facilities_master.json"
RESTAURANT_FILE = DATA_DIR / "kawagoe_restaurants.json"

OUTPUT_FILE = DATA_DIR / "kawagoe_route_locations.json"
REVIEW_FILE = DATA_DIR / "kawagoe_route_locations_review.json"

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "SaitamaSouthwestTourismPlanner/2.0 (academic project)"

# 川越中心部
KAWAGOE_CENTER_LAT = 35.9251
KAWAGOE_CENTER_LON = 139.4858

# 今回登録している川越観光・宿泊・飲食地点は中心から概ね10km圏内。
# 誤ヒット防止のため12kmを超えるものは自動採用しない。
MAX_DISTANCE_FROM_CENTER_KM = 12.0

# 埼玉県・川越周辺の絶対安全範囲
SAFE_LAT_MIN = 35.82
SAFE_LAT_MAX = 36.02
SAFE_LON_MIN = 139.36
SAFE_LON_MAX = 139.58

SEARCH_OVERRIDES: dict[str, list[str]] = {
    "蔵造りの町並み": [
        "蔵造りの町並み 川越市",
        "川越一番街 川越市",
    ],
    "大正浪漫夢通り": [
        "大正浪漫夢通り 川越市",
    ],
    "伊佐沼": [
        "伊佐沼 川越市",
    ],
    "成田山川越別院": [
        "成田山川越別院 川越市",
    ],
    "国指定史跡 河越館跡": [
        "河越館跡 川越市上戸192-1",
        "史跡河越館跡 川越市",
    ],
    "川越熊野神社": [
        "川越熊野神社 川越市連雀町17-1",
    ],
    "Te’PAN Le OMUS": [
        "Te'PAN Le OMUS 川越市幸町",
        "Te’PAN Le OMUS 川越市幸町",
    ],
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"必要ファイルがありません: {path}")
    with path.open("r", encoding="utf-8") as f:
        value = json.load(f)
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} の形式が不正です。")
    return value


def normalize_text(value: Any) -> str:
    text = str(value or "").strip()
    text = text.replace("〒", "")
    text = re.sub(r"\s+", "", text)
    return text


def normalize_address(value: Any) -> str:
    text = str(value or "").strip()
    text = text.replace("〒", "")
    text = re.sub(r"\s+", " ", text)
    return text


def postal_code_from(address: str) -> str:
    m = re.search(r"(\d{3})-?(\d{4})", address)
    if not m:
        return ""
    return f"{m.group(1)}-{m.group(2)}"


def address_tokens(address: str) -> list[str]:
    """
    町名・丁目・番地のうち判定に使いやすい部分を抽出。
    """
    compact = normalize_text(address)

    tokens: list[str] = []

    # 市名
    if "川越市" in compact:
        tokens.append("川越市")

    # 川越市以降から数字の前までを町名候補として取る
    m = re.search(r"川越市([^0-9０-９,\s]+)", compact)
    if m:
        town = m.group(1)
        if len(town) >= 2:
            tokens.append(town)

    # よく使う町名を追加
    known = [
        "元町", "幸町", "仲町", "連雀町", "松江町", "郭町", "宮下町",
        "久保町", "南通町", "小仙波町", "西小仙波町", "新富町",
        "脇田町", "脇田本町", "菅原町", "富士見町", "三久保町",
        "六軒町", "石原町", "藤間", "今成", "大手町", "八ツ島",
        "的場", "上戸", "西小仙波町", "新宿町"
    ]
    for token in known:
        if token in compact and token not in tokens:
            tokens.append(token)

    return tokens


def extract_facility_address(item: dict[str, Any]) -> str:
    basic = item.get("basic")
    if isinstance(basic, dict) and basic.get("address"):
        return normalize_address(basic["address"])

    contact = item.get("contact")
    if isinstance(contact, dict) and contact.get("address"):
        return normalize_address(contact["address"])

    return normalize_address(item.get("address"))


def extract_restaurant_address(item: dict[str, Any]) -> str:
    return normalize_address(item.get("address"))


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = (
        math.sin(dp / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(a))


def geographically_safe(lat: float, lon: float) -> bool:
    if not (
        math.isfinite(lat)
        and math.isfinite(lon)
        and SAFE_LAT_MIN <= lat <= SAFE_LAT_MAX
        and SAFE_LON_MIN <= lon <= SAFE_LON_MAX
    ):
        return False

    distance = haversine_km(
        KAWAGOE_CENTER_LAT,
        KAWAGOE_CENTER_LON,
        lat,
        lon,
    )
    return distance <= MAX_DISTANCE_FROM_CENTER_KM


def geocode(query: str) -> list[dict[str, Any]]:
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
            "Accept-Language": "ja",
        },
    )

    with urllib.request.urlopen(req, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))

    return data if isinstance(data, list) else []


def result_score(
    result: dict[str, Any],
    name: str,
    address: str,
    query_kind: str,
) -> tuple[int, list[str]]:
    reasons: list[str] = []

    try:
        lat = float(result["lat"])
        lon = float(result["lon"])
    except (KeyError, TypeError, ValueError):
        return -9999, ["座標不正"]

    if not geographically_safe(lat, lon):
        return -9999, ["川越登録範囲外"]

    display = str(result.get("display_name") or "")
    display_compact = normalize_text(display)
    name_compact = normalize_text(name)

    address_detail = result.get("address")
    if not isinstance(address_detail, dict):
        address_detail = {}

    score = 0

    # 行政区域
    if "川越市" in display_compact:
        score += 120
        reasons.append("川越市一致")

    city_fields = " ".join(
        str(address_detail.get(k) or "")
        for k in ("city", "town", "municipality", "county")
    )
    if "川越" in city_fields:
        score += 80
        reasons.append("addressdetails川越一致")

    # 施設名
    if name_compact and name_compact in display_compact:
        score += 100
        reasons.append("施設名完全包含")
    else:
        simplified = (
            name_compact
            .replace("川越", "")
            .replace("店", "")
            .replace("本店", "")
        )
        if len(simplified) >= 3 and simplified in display_compact:
            score += 45
            reasons.append("施設名部分一致")

    # 町名
    for token in address_tokens(address):
        if normalize_text(token) in display_compact:
            score += 40
            reasons.append(f"住所一致:{token}")

    # 郵便番号
    postal = postal_code_from(address)
    result_postcode = str(address_detail.get("postcode") or "")
    if postal and result_postcode:
        if postal == result_postcode:
            score += 60
            reasons.append("郵便番号一致")
        elif postal[:3] == result_postcode[:3]:
            score += 10

    # 住所検索で得た結果は、名称POIが無くても番地位置として利用可能。
    if query_kind == "address":
        score += 25
        reasons.append("正式住所検索")

        # 川越市＋町名一致まで取れれば住所座標として高信頼
        if "川越市" in display_compact and any(
            normalize_text(t) in display_compact
            for t in address_tokens(address)
            if t != "川越市"
        ):
            score += 80
            reasons.append("住所位置高信頼")

    distance = haversine_km(
        KAWAGOE_CENTER_LAT,
        KAWAGOE_CENTER_LON,
        lat,
        lon,
    )

    # 中心から極端に遠い候補を少し減点
    if distance > 8:
        score -= 40
        reasons.append(f"中心から{distance:.1f}km")
    elif distance <= 5:
        score += 15

    return score, reasons


def build_queries(name: str, address: str) -> list[tuple[str, str]]:
    queries: list[tuple[str, str]] = []

    # 施設名 + 正式住所
    if address:
        queries.append(
            (
                f"{name}, {address}, 日本",
                "name_address",
            )
        )

        # 正式住所のみ
        queries.append(
            (
                f"{address}, 日本",
                "address",
            )
        )

    # 個別補助
    for q in SEARCH_OVERRIDES.get(name, []):
        queries.append((q, "override"))

    # 名称単独
    queries.append(
        (
            f"{name}, 川越市, 埼玉県, 日本",
            "name",
        )
    )

    # 重複排除
    seen: set[str] = set()
    output: list[tuple[str, str]] = []
    for q, kind in queries:
        if q not in seen:
            seen.add(q)
            output.append((q, kind))
    return output


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

    if len(catalog) != 70:
        raise RuntimeError(
            f"川越地点数が70ではありません。現在 {len(catalog)} 地点です。"
        )

    names = [x["name"] for x in catalog]
    if len(names) != len(set(names)):
        raise RuntimeError("地点名に重複があります。")

    resolved: dict[str, dict[str, Any]] = {}
    review: dict[str, Any] = {}

    print("=" * 72)
    print("川越70地点 座標精密再検証 v2")
    print("=" * 72)

    for index, item in enumerate(catalog, start=1):
        name = item["name"]
        address = item["address"]
        category = item["category"]

        print(f"[{index:02d}/70] {name}")

        candidates: list[dict[str, Any]] = []

        for query, query_kind in build_queries(name, address):
            try:
                results = geocode(query)
            except Exception as exc:
                print("  API ERROR:", repr(exc))
                time.sleep(1.2)
                continue

            time.sleep(1.2)

            for result in results:
                score, reasons = result_score(
                    result,
                    name,
                    address,
                    query_kind,
                )

                if score <= -9000:
                    continue

                candidates.append(
                    {
                        "score": score,
                        "reasons": reasons,
                        "query": query,
                        "query_kind": query_kind,
                        "result": result,
                    }
                )

        candidates.sort(
            key=lambda x: x["score"],
            reverse=True,
        )

        if not candidates:
            review[name] = {
                "category": category,
                "address": address,
                "status": "manual_review_required",
                "reason": "川越範囲内の候補なし",
            }
            print("  -> 要確認（候補なし）")
            continue

        best = candidates[0]
        best_result = best["result"]

        try:
            lat = round(float(best_result["lat"]), 8)
            lon = round(float(best_result["lon"]), 8)
        except (KeyError, TypeError, ValueError):
            review[name] = {
                "category": category,
                "address": address,
                "status": "manual_review_required",
                "reason": "最上位候補の座標不正",
            }
            print("  -> 要確認（座標不正）")
            continue

        # 採用基準
        # 260以上: 自動採用
        # 180～259: 住所検索かつ川越市＋町名一致なら採用
        auto_accept = best["score"] >= 260

        if (
            not auto_accept
            and best["score"] >= 180
            and best["query_kind"] == "address"
            and "川越市一致" in best["reasons"]
            and any(x.startswith("住所一致:") for x in best["reasons"])
        ):
            auto_accept = True

        if not auto_accept:
            review[name] = {
                "category": category,
                "address": address,
                "status": "manual_review_required",
                "reason": "信頼度不足",
                "best_score": best["score"],
                "best_reasons": best["reasons"],
                "best_candidate": {
                    "display_name": str(best_result.get("display_name") or ""),
                    "lat": lat,
                    "lon": lon,
                },
                "top_candidates": [
                    {
                        "score": c["score"],
                        "query_kind": c["query_kind"],
                        "display_name": str(c["result"].get("display_name") or ""),
                        "lat": c["result"].get("lat"),
                        "lon": c["result"].get("lon"),
                        "reasons": c["reasons"],
                    }
                    for c in candidates[:5]
                ],
            }
            print(
                f"  -> 要確認 score={best['score']} "
                f"candidate={lat}, {lon}"
            )
            continue

        distance = haversine_km(
            KAWAGOE_CENTER_LAT,
            KAWAGOE_CENTER_LON,
            lat,
            lon,
        )

        resolved[name] = {
            "category": category,
            "address": address,
            "latitude": lat,
            "longitude": lon,
            "coordinate_source": "OpenStreetMap Nominatim verified v2",
            "verification_score": best["score"],
            "verification_reasons": best["reasons"],
            "geocode_query": best["query"],
            "geocode_display_name": str(best_result.get("display_name") or ""),
            "distance_from_kawagoe_center_km": round(distance, 3),
            "verified_at": "2026-11-18",
        }

        print(
            f"  -> OK score={best['score']} "
            f"{lat}, {lon} "
            f"({distance:.2f}km)"
        )

    # 完全重複座標
    coordinate_groups: dict[tuple[float, float], list[str]] = {}
    for name, item in resolved.items():
        key = (
            float(item["latitude"]),
            float(item["longitude"]),
        )
        coordinate_groups.setdefault(key, []).append(name)

    duplicates = {
        f"{lat},{lon}": group
        for (lat, lon), group in coordinate_groups.items()
        if len(group) > 1
    }

    if duplicates:
        review["_duplicate_coordinates"] = {
            "status": "manual_review_required",
            "groups": duplicates,
        }

    output = {
        "meta": {
            "schema_version": 2,
            "region": "川越",
            "generated_at": "2026-11-18",
            "expected_location_count": 70,
            "resolved_count": len(resolved),
            "manual_review_count": len(
                [k for k in review if not k.startswith("_")]
            ),
            "coordinate_provider": "OpenStreetMap Nominatim",
            "runtime_geocoding": False,
            "max_distance_from_kawagoe_center_km": MAX_DISTANCE_FROM_CENTER_KM,
            "note": (
                "公式住所・施設名・町名・郵便番号・川越中心距離を用いた"
                "事前検証済み固定座標。Web実行時にはジオコードしない。"
            ),
        },
        "route_locations": resolved,
    }

    review_output = {
        "meta": {
            "schema_version": 2,
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
    print("=" * 72)
    print("精密再検証 完了")
    print("=" * 72)
    print("解決:", len(resolved), "/ 70")
    print(
        "要確認:",
        len([k for k in review if not k.startswith("_")]),
    )
    print("完全重複座標:", len(duplicates))
    print("出力:", OUTPUT_FILE)
    print("確認用:", REVIEW_FILE)

    if len(resolved) == 70 and not duplicates:
        print("[KAWAGOE ROUTE LOCATIONS V2] 70 / 70 OK")
    else:
        print(
            "[KAWAGOE ROUTE LOCATIONS V2] "
            "review JSONに未確定地点があります。"
        )


if __name__ == "__main__":
    main()
