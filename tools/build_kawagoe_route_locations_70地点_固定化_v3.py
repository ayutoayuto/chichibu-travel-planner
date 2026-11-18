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

# v2で作った38件入りのファイルを読み込み、残りだけ補完する。
ROUTE_FILE = DATA_DIR / "kawagoe_route_locations.json"
REVIEW_FILE = DATA_DIR / "kawagoe_route_locations_review.json"

BACKUP_FILE = DATA_DIR / "kawagoe_route_locations_before_v3.json"
FINAL_REVIEW_FILE = DATA_DIR / "kawagoe_route_locations_v3_review.json"

GSI_URL = "https://msearch.gsi.go.jp/address-search/AddressSearch"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "SaitamaSouthwestTourismPlanner/3.0 (academic project)"

KAWAGOE_CENTER_LAT = 35.9251
KAWAGOE_CENTER_LON = 139.4858
MAX_DISTANCE_FROM_CENTER_KM = 12.0

SAFE_LAT_MIN = 35.82
SAFE_LAT_MAX = 36.02
SAFE_LON_MIN = 139.36
SAFE_LON_MAX = 139.58

# v2で未確定になった32地点。
EXPECTED_UNRESOLVED = [
    "蔵造りの町並み",
    "川越熊野神社",
    "国指定史跡 河越館跡",
    "松村屋旅館",
    "川越ビジネスホテル",
    "川越東武ホテル",
    "川越湯遊ランド・ホテル三光",
    "UTILITY HOTEL cooju",
    "旅籠 小江戸や",
    "泊まれるリラクゼーションサロン ゆきき",
    "ちゃぶだい Guesthouse, Cafe&Bar",
    "小江戸川越おもてなしの家",
    "月の宿 KAGUYA",
    "WE HOME STAY 川越・的場",
    "結家 -MUSUBIYA-",
    "ゲストハウスくく 川越店",
    "林屋",
    "ぽんぽこ亭",
    "寿庵 蔵のまち店",
    "十限無",
    "料亭 山屋",
    "頑者 本店",
    "ミオ・カザロ 川越 蔵のまち店",
    "glin coffee 元町1号店",
    "une brise",
    "1901 TEA SALON",
    "うんとん処 春夏秋冬",
    "海鮮料理 近長魚店",
    "甘味茶房 かすが",
    "Te’PAN Le OMUS",
    "日本料理 美鈴",
    "和創菜と四季のすし 風凛",
]

# 公式・観光協会・自治体情報で確認した住所。
# master側に旧住所や曖昧住所があるものはここを必ず優先する。
OFFICIAL_ADDRESS_OVERRIDES: dict[str, str] = {
    "川越熊野神社": "埼玉県川越市連雀町17-1",
    "国指定史跡 河越館跡": "埼玉県川越市上戸195-1",
    "松村屋旅館": "埼玉県川越市元町1-1-11",
    "川越ビジネスホテル": "埼玉県川越市富士見町12-2",
    "川越東武ホテル": "埼玉県川越市脇田本町8-1",
    "川越湯遊ランド・ホテル三光": "埼玉県川越市新富町1-9-1",
    "UTILITY HOTEL cooju": "埼玉県川越市脇田町17-4",
    "旅籠 小江戸や": "埼玉県川越市連雀町8-1",
    "ちゃぶだい Guesthouse, Cafe&Bar": "埼玉県川越市三久保町1-14",
    "月の宿 KAGUYA": "埼玉県川越市八ツ島52-1",
    "WE HOME STAY 川越・的場": "埼玉県川越市的場1891-1",
    "結家 -MUSUBIYA-": "埼玉県川越市石原町1-6-7",
    "ゲストハウスくく 川越店": "埼玉県川越市大手町1-8",

    "林屋": "埼玉県川越市仲町2-4",
    "ぽんぽこ亭": "埼玉県川越市藤間151-7",
    "寿庵 蔵のまち店": "埼玉県川越市幸町3-18",
    "十限無": "埼玉県川越市久保町6-6",
    "料亭 山屋": "埼玉県川越市幸町11-2",
    "頑者 本店": "埼玉県川越市新富町1-1-8",
    "ミオ・カザロ 川越 蔵のまち店": "埼玉県川越市元町1-15-3",
    "glin coffee 元町1号店": "埼玉県川越市元町1-1-20",
    "une brise": "埼玉県川越市幸町3-8",
    "1901 TEA SALON": "埼玉県川越市連雀町13-4",
    "うんとん処 春夏秋冬": "埼玉県川越市幸町10-5",
    "海鮮料理 近長魚店": "埼玉県川越市幸町6-11",
    "甘味茶房 かすが": "埼玉県川越市幸町6-1",
    "Te’PAN Le OMUS": "埼玉県川越市幸町8-11",
    "日本料理 美鈴": "埼玉県川越市仲町5-2",
    "和創菜と四季のすし 風凛": "埼玉県川越市仲町6-4",
}

# masterの住所をそのまま使えるが、今回公式確認まではしていない地点。
# v3はmasterの登録住所を読み込んで住所検索する。
MASTER_ADDRESS_ALLOWED = {
    "泊まれるリラクゼーションサロン ゆきき",
    "小江戸川越おもてなしの家",
}

# 面として広がる観光スポット。
# 「施設の一点座標」ではなく、ルート計算用の代表地点として明示して固定する。
REPRESENTATIVE_POINTS: dict[str, dict[str, Any]] = {
    "蔵造りの町並み": {
        "address": "埼玉県川越市幸町・元町周辺",
        "latitude": 35.9235447,
        "longitude": 139.4829264,
        "coordinate_source": "representative_route_point",
        "verification_note": (
            "蔵造りの町並みは線・面状の観光エリアのため、"
            "一番街中心部の代表地点をルート計算用に固定。"
        ),
    },
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"必要ファイルがありません: {path}")
    with path.open("r", encoding="utf-8") as f:
        value = json.load(f)
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} のJSON形式が不正です。")
    return value


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)


def normalize_address(value: Any) -> str:
    text = str(value or "").strip()
    text = text.replace("〒", "")
    text = re.sub(r"\b\d{3}-\d{4}\b", "", text)
    text = text.replace("ほか", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def compact(value: Any) -> str:
    return re.sub(r"[\s　〒\-‐－ー]", "", str(value or ""))


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + (
        math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(a))


def coordinate_safe(lat: float, lon: float) -> bool:
    if not (
        math.isfinite(lat)
        and math.isfinite(lon)
        and SAFE_LAT_MIN <= lat <= SAFE_LAT_MAX
        and SAFE_LON_MIN <= lon <= SAFE_LON_MAX
    ):
        return False

    return (
        haversine_km(
            KAWAGOE_CENTER_LAT,
            KAWAGOE_CENTER_LON,
            lat,
            lon,
        )
        <= MAX_DISTANCE_FROM_CENTER_KM
    )


def extract_master_address(
    name: str,
    facilities: list[dict[str, Any]],
    restaurants: list[dict[str, Any]],
) -> str:
    for item in facilities:
        if str(item.get("name") or "").strip() != name:
            continue

        basic = item.get("basic")
        if isinstance(basic, dict) and basic.get("address"):
            return normalize_address(basic["address"])

        contact = item.get("contact")
        if isinstance(contact, dict) and contact.get("address"):
            return normalize_address(contact["address"])

        if item.get("address"):
            return normalize_address(item["address"])

    for item in restaurants:
        if str(item.get("name") or "").strip() != name:
            continue
        if item.get("address"):
            return normalize_address(item["address"])

    return ""


def get_fixed_address(
    name: str,
    facilities: list[dict[str, Any]],
    restaurants: list[dict[str, Any]],
) -> str:
    if name in OFFICIAL_ADDRESS_OVERRIDES:
        return OFFICIAL_ADDRESS_OVERRIDES[name]

    if name in MASTER_ADDRESS_ALLOWED:
        return extract_master_address(name, facilities, restaurants)

    return extract_master_address(name, facilities, restaurants)


def gsi_search(address: str) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"q": address})
    req = urllib.request.Request(
        f"{GSI_URL}?{params}",
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )

    with urllib.request.urlopen(req, timeout=30) as response:
        value = json.loads(response.read().decode("utf-8"))

    return value if isinstance(value, list) else []


def gsi_best(address: str) -> dict[str, Any] | None:
    results = gsi_search(address)
    if not results:
        return None

    scored: list[tuple[int, dict[str, Any]]] = []
    target = compact(address)

    for item in results:
        geometry = item.get("geometry")
        props = item.get("properties")
        if not isinstance(geometry, dict) or not isinstance(props, dict):
            continue

        coords = geometry.get("coordinates")
        if not (
            isinstance(coords, list)
            and len(coords) >= 2
        ):
            continue

        try:
            lon = float(coords[0])
            lat = float(coords[1])
        except (TypeError, ValueError):
            continue

        if not coordinate_safe(lat, lon):
            continue

        title = str(props.get("title") or "")
        t = compact(title)

        score = 0

        if "埼玉県" in title:
            score += 40
        if "川越市" in title:
            score += 100

        # 住所の末尾をなるべく一致させる
        for token in re.findall(r"[一-龥ぁ-んァ-ンA-Za-z0-9]+", address):
            c = compact(token)
            if len(c) >= 2 and c in t:
                score += 8

        if target and target in t:
            score += 100

        distance = haversine_km(
            KAWAGOE_CENTER_LAT,
            KAWAGOE_CENTER_LON,
            lat,
            lon,
        )
        if distance <= 5:
            score += 15

        scored.append(
            (
                score,
                {
                    "latitude": lat,
                    "longitude": lon,
                    "title": title,
                    "score": score,
                },
            )
        )

    if not scored:
        return None

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


def nominatim_address_fallback(address: str) -> dict[str, Any] | None:
    params = urllib.parse.urlencode(
        {
            "q": f"{address}, 日本",
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
            "Accept-Language": "ja",
        },
    )

    with urllib.request.urlopen(req, timeout=30) as response:
        results = json.loads(response.read().decode("utf-8"))

    if not isinstance(results, list):
        return None

    for item in results:
        display = str(item.get("display_name") or "")
        if "川越" not in display:
            continue

        try:
            lat = float(item["lat"])
            lon = float(item["lon"])
        except (KeyError, TypeError, ValueError):
            continue

        if not coordinate_safe(lat, lon):
            continue

        return {
            "latitude": lat,
            "longitude": lon,
            "title": display,
        }

    return None


def category_map(
    facilities: list[dict[str, Any]],
    restaurants: list[dict[str, Any]],
) -> dict[str, str]:
    result: dict[str, str] = {}

    for item in facilities:
        name = str(item.get("name") or "").strip()
        if name:
            result[name] = str(item.get("category") or "facility")

    for item in restaurants:
        name = str(item.get("name") or "").strip()
        if name:
            result[name] = "gourmet"

    return result


def main() -> None:
    facilities_data = load_json(FACILITY_FILE)
    restaurants_data = load_json(RESTAURANT_FILE)
    route_data = load_json(ROUTE_FILE)

    facilities = facilities_data.get("facilities", [])
    restaurants = restaurants_data.get("restaurants", [])
    existing = route_data.get("route_locations", {})

    if not isinstance(facilities, list):
        raise ValueError("kawagoe_facilities_master.json の facilities がlistではありません。")
    if not isinstance(restaurants, list):
        raise ValueError("kawagoe_restaurants.json の restaurants がlistではありません。")
    if not isinstance(existing, dict):
        raise ValueError("kawagoe_route_locations.json の route_locations がdictではありません。")

    # v2の状態を必ずバックアップ
    save_json(BACKUP_FILE, route_data)

    categories = category_map(facilities, restaurants)

    # v2で採用済みの38件を安全チェックして保持。
    final_locations: dict[str, dict[str, Any]] = {}

    for name, item in existing.items():
        if not isinstance(item, dict):
            continue

        try:
            lat = float(item["latitude"])
            lon = float(item["longitude"])
        except (KeyError, TypeError, ValueError):
            continue

        if not coordinate_safe(lat, lon):
            continue

        final_locations[name] = dict(item)

    print("=" * 74)
    print("川越70地点 固定化 v3")
    print("=" * 74)
    print("v2から保持:", len(final_locations), "件")
    print()

    review: dict[str, Any] = {}

    for index, name in enumerate(EXPECTED_UNRESOLVED, start=1):
        print(f"[{index:02d}/32] {name}")

        if name in final_locations:
            print("  -> すでにv2で確定済みのため保持")
            continue

        if name in REPRESENTATIVE_POINTS:
            p = REPRESENTATIVE_POINTS[name]
            lat = float(p["latitude"])
            lon = float(p["longitude"])

            if not coordinate_safe(lat, lon):
                raise RuntimeError(f"{name} の代表地点が川越範囲外です。")

            final_locations[name] = {
                "category": categories.get(name, "location"),
                "address": p["address"],
                "latitude": lat,
                "longitude": lon,
                "coordinate_source": p["coordinate_source"],
                "verification_note": p["verification_note"],
                "verified_at": "2026-11-18",
            }
            print(f"  -> 代表地点固定 {lat}, {lon}")
            continue

        address = get_fixed_address(
            name,
            facilities,
            restaurants,
        )

        if not address:
            review[name] = {
                "status": "manual_review_required",
                "reason": "住所なし",
            }
            print("  -> 要確認（住所なし）")
            continue

        print("  住所:", address)

        result = None
        source = None

        # 1) 国土地理院
        try:
            result = gsi_best(address)
        except Exception as exc:
            print("  GSI ERROR:", repr(exc))

        if result is not None:
            source = "Geospatial Information Authority of Japan AddressSearch"
        else:
            # 2) OSM/Nominatimを住所だけで再試行
            try:
                time.sleep(1.1)
                result = nominatim_address_fallback(address)
            except Exception as exc:
                print("  NOMINATIM ERROR:", repr(exc))

            if result is not None:
                source = "OpenStreetMap Nominatim address fallback"

        if result is None:
            review[name] = {
                "status": "manual_review_required",
                "reason": "住所検索で安全な候補なし",
                "address": address,
            }
            print("  -> 要確認（住所検索失敗）")
            continue

        lat = round(float(result["latitude"]), 8)
        lon = round(float(result["longitude"]), 8)

        if not coordinate_safe(lat, lon):
            review[name] = {
                "status": "manual_review_required",
                "reason": "取得座標が川越安全範囲外",
                "address": address,
                "candidate": {
                    "latitude": lat,
                    "longitude": lon,
                },
            }
            print("  -> 要確認（範囲外）")
            continue

        final_locations[name] = {
            "category": categories.get(name, "location"),
            "address": address,
            "latitude": lat,
            "longitude": lon,
            "coordinate_source": source,
            "geocode_display_name": str(result.get("title") or ""),
            "verification_method": "official_or_master_address_to_fixed_coordinate",
            "verified_at": "2026-11-18",
        }

        print(f"  -> FIXED {lat}, {lon}")

        # GSIに過剰アクセスしない
        time.sleep(0.2)

    # 70件の期待名称をmasterから作る
    expected_names: list[str] = []

    for item in facilities:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
            if name:
                expected_names.append(name)

    for item in restaurants:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
            if name:
                expected_names.append(name)

    if len(expected_names) != 70:
        raise RuntimeError(
            f"master側の地点数が70ではありません: {len(expected_names)}"
        )

    missing = [
        name
        for name in expected_names
        if name not in final_locations
    ]

    extra = [
        name
        for name in final_locations
        if name not in set(expected_names)
    ]

    # 正確な同一座標は、同一建物・同一区画の場合はあり得るため
    # エラーにせず確認情報として記録する。
    coord_groups: dict[tuple[float, float], list[str]] = {}
    for name, item in final_locations.items():
        key = (
            round(float(item["latitude"]), 8),
            round(float(item["longitude"]), 8),
        )
        coord_groups.setdefault(key, []).append(name)

    duplicate_groups = {
        f"{lat},{lon}": names
        for (lat, lon), names in coord_groups.items()
        if len(names) > 1
    }

    review["_summary"] = {
        "expected_count": 70,
        "resolved_count": len(final_locations),
        "missing": missing,
        "extra": extra,
        "duplicate_coordinate_groups": duplicate_groups,
    }

    output = {
        "meta": {
            "schema_version": 3,
            "region": "川越",
            "generated_at": "2026-11-18",
            "expected_location_count": 70,
            "resolved_count": len(final_locations),
            "manual_review_count": len(missing),
            "runtime_geocoding": False,
            "coordinate_policy": (
                "v2高信頼座標を保持し、未確定地点は公式/マスター住所から"
                "国土地理院AddressSearchで事前固定。面状観光地は代表ルート地点を明示。"
            ),
            "note": (
                "このJSON生成後、Webアプリ実行時に外部ジオコードは行わない。"
                "道路ルート行列作成時に最寄りdriveノードへスナップする。"
            ),
        },
        "route_locations": {
            name: final_locations[name]
            for name in sorted(
                final_locations,
                key=lambda n: expected_names.index(n)
                if n in expected_names else 9999
            )
        },
    }

    save_json(ROUTE_FILE, output)
    save_json(
        FINAL_REVIEW_FILE,
        {
            "meta": {
                "schema_version": 3,
                "region": "川越",
                "generated_at": "2026-11-18",
            },
            "review": review,
        },
    )

    print()
    print("=" * 74)
    print("川越70地点 固定化 v3 完了")
    print("=" * 74)
    print("解決:", len(final_locations), "/ 70")
    print("未解決:", len(missing))
    print("重複座標グループ:", len(duplicate_groups))
    print("バックアップ:", BACKUP_FILE)
    print("最終候補:", ROUTE_FILE)
    print("確認用:", FINAL_REVIEW_FILE)

    if len(final_locations) == 70 and not missing and not extra:
        print("[KAWAGOE ROUTE LOCATIONS V3] 70 / 70 COMPLETE")
    else:
        print("[KAWAGOE ROUTE LOCATIONS V3] 未解決地点があります。")
        if missing:
            print("未解決:")
            for name in missing:
                print(" -", name)


if __name__ == "__main__":
    main()
