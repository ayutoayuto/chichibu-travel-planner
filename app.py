from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlencode
import hashlib
import urllib.error
import urllib.request
import json
import os
import random
import re

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESTAURANT_FILE = os.path.join(BASE_DIR, "data", "restaurants.json")
FACILITY_MASTER_FILE = os.path.join(BASE_DIR, "data", "facilities_master.json")


with open(RESTAURANT_FILE, "r", encoding="utf-8") as f:
    restaurant_data = json.load(f)

restaurants = restaurant_data.get("restaurants", [])

# 41施設マスターは推薦条件（特に季節情報）の参照専用に利用する。
# 既存の30観光スポット＋11宿泊施設のハードコードデータ自体は削除・置換しない。
try:
    with open(FACILITY_MASTER_FILE, "r", encoding="utf-8") as f:
        facility_master_data = json.load(f)
    facility_master = {
        item.get("name", ""): item
        for item in facility_master_data.get("facilities", [])
        if item.get("name")
    }
except (OSError, json.JSONDecodeError, TypeError):
    facility_master = {}


# =========================================================
# 観光スポットデータ（既存30件を維持）
# =========================================================

spots = [{'name': '長瀞・岩畳',
  'tags': ['自然', 'デート', '家族', '友人', 'グルメ'],
  'car': False,
  'time': 3,
  'area': '長瀞',
  'type': 'nature',
  'description': '荒川沿いに広がる国の名勝・天然記念物の岩畳。散策や長瀞観光の中心として楽しめます。',
  'difficulty': 'easy',
  'url': 'https://www.nagatoro.gr.jp/'},
 {'name': '長瀞ラインくだり',
  'tags': ['自然', 'デート', '家族', '友人'],
  'car': False,
  'time': 2,
  'area': '長瀞',
  'type': 'nature',
  'description': '荒川の渓谷を和舟で下る長瀞の代表的なアクティビティです。',
  'difficulty': 'easy',
  'url': 'https://www.chichibu-railway.co.jp/nagatoro/'},
 {'name': '宝登山',
  'tags': ['自然', 'デート', '家族', '友人'],
  'car': True,
  'time': 3,
  'area': '長瀞',
  'type': 'nature',
  'description': '山頂から長瀞・秩父の山々を望める人気の山。ロープウェイでも登れます。',
  'difficulty': 'medium',
  'url': 'https://www.chichibuji.gr.jp/spot/spot-syousai02/'},
 {'name': '寶登山神社',
  'tags': ['歴史', 'デート', '家族', '友人'],
  'car': True,
  'time': 2,
  'area': '長瀞',
  'type': 'history',
  'description': '秩父三社の一つ。宝登山の麓に鎮座する歴史ある神社です。',
  'difficulty': 'easy',
  'url': 'https://www.hodosan-jinja.or.jp/'},
 {'name': '宝登山ロープウェイ',
  'tags': ['自然', 'デート', '家族', '友人'],
  'car': True,
  'time': 2,
  'area': '長瀞',
  'type': 'nature',
  'description': '宝登山の山麓と山頂を結ぶロープウェイ。山頂観光へのアクセスにも便利です。',
  'difficulty': 'easy',
  'url': 'https://hodosan-ropeway.co.jp/'},
 {'name': '埼玉県立自然の博物館',
  'tags': ['自然', '家族', '友人', '歴史'],
  'car': True,
  'time': 2,
  'area': '長瀞',
  'type': 'history',
  'description': '埼玉県の自然や地質、生き物について学べる博物館です。',
  'difficulty': 'easy',
  'url': 'https://shizen.spec.ed.jp/'},
 {'name': '月の石もみじ公園',
  'tags': ['自然', 'デート', '家族'],
  'car': True,
  'time': 2,
  'area': '長瀞',
  'type': 'nature',
  'description': '紅葉の名所として知られる長瀞の公園。季節の景観を楽しめます。',
  'difficulty': 'easy',
  'url': 'https://www.nagatoro.gr.jp/'},
 {'name': '金石水管橋',
  'tags': ['自然', 'デート', '友人'],
  'car': True,
  'time': 1,
  'area': '長瀞',
  'type': 'nature',
  'description': '荒川を渡る橋の上から渓谷や周辺の景色を楽しめるスポットです。',
  'difficulty': 'easy',
  'url': 'https://www.nagatoro.gr.jp/'},
 {'name': '秩父神社',
  'tags': ['歴史', 'デート', '家族', '友人', 'グルメ'],
  'car': False,
  'time': 2,
  'area': '秩父市街',
  'type': 'history',
  'description': '秩父地方の総社。社殿の彫刻や門前の街歩きも楽しめます。',
  'difficulty': 'easy',
  'url': 'https://www.chichibuji.gr.jp/spot/spot-syousai01/'},
 {'name': '三峯神社',
  'tags': ['自然', '歴史', 'デート', '家族'],
  'car': True,
  'time': 5,
  'area': '奥秩父',
  'type': 'nature',
  'description': '標高約1100mの三峰山に鎮座する秩父三社の一つ。豊かな山の自然も魅力です。',
  'difficulty': 'hard',
  'url': 'https://www.chichibuji.gr.jp/spot/spot-syousai03/'},
 {'name': '羊山公園',
  'tags': ['自然', 'デート', '家族'],
  'car': True,
  'time': 2,
  'area': '秩父市街',
  'type': 'nature',
  'description': '芝桜の丘や見晴らしの丘などがあり、季節の花と秩父の景色を楽しめます。',
  'difficulty': 'easy',
  'url': 'https://www.chichibuji.gr.jp/spot/spot-syousai10/'},
 {'name': '秩父ミューズパーク',
  'tags': ['自然', '家族', '友人', 'デート'],
  'car': True,
  'time': 3,
  'area': '秩父',
  'type': 'nature',
  'description': '秩父市と小鹿野町にまたがる広大な公園。展望台や遊具、季節の花などを楽しめます。',
  'difficulty': 'easy',
  'url': 'https://www.chichibuji.gr.jp/spot/spot-syousai11/'},
 {'name': '旅立ちの丘',
  'tags': ['自然', 'デート', '家族', '友人'],
  'car': True,
  'time': 1,
  'area': '秩父ミューズパーク',
  'type': 'nature',
  'description': '『旅立ちの日に』を記念した展望スポット。秩父の景色を眺められます。',
  'difficulty': 'easy',
  'url': 'https://navi.city.chichibu.lg.jp/p_sightseeingr/884/'},
 {'name': '美の山公園',
  'tags': ['自然', 'デート', '家族', '友人'],
  'car': True,
  'time': 2,
  'area': '皆野・秩父',
  'type': 'nature',
  'description': '蓑山山頂周辺に広がる公園。桜や雲海、秩父盆地の眺望で知られます。',
  'difficulty': 'medium',
  'url': 'https://www.chichibuji.gr.jp/spot/spot-syousai12/'},
 {'name': '橋立鍾乳洞',
  'tags': ['自然', '家族', '友人'],
  'car': True,
  'time': 2,
  'area': '影森',
  'type': 'nature',
  'description': '武甲山の麓にある鍾乳洞。自然の地形を体験できる観光スポットです。',
  'difficulty': 'medium',
  'url': 'https://www.chichibuji.gr.jp/spot/'},
 {'name': '聖神社',
  'tags': ['歴史', 'デート', '家族', '友人'],
  'car': True,
  'time': 1,
  'area': '黒谷',
  'type': 'history',
  'description': '和銅ゆかりの神社で、金運の神様・銭神様として親しまれています。',
  'difficulty': 'easy',
  'url': 'https://www.chichibuji.gr.jp/spot/spot-syousai95/'},
 {'name': '秩父まつり会館',
  'tags': ['歴史', '家族', '友人', 'グルメ'],
  'car': False,
  'time': 2,
  'area': '秩父市街',
  'type': 'history',
  'description': '秩父夜祭の屋台・笠鉾などを展示し、秩父の祭り文化を体感できる施設です。',
  'difficulty': 'easy',
  'url': 'https://www.chichibu-matsuri.jp/'},
 {'name': 'ほっとすぽっと秩父館',
  'tags': ['歴史', 'デート', '家族', '友人', 'グルメ'],
  'car': False,
  'time': 1,
  'area': '秩父市街',
  'type': 'history',
  'description': '明治時代初期の商人宿を活用した、街歩きの立ち寄りスポットです。',
  'difficulty': 'easy',
  'url': 'https://navi.city.chichibu.lg.jp/p_sightseeingr/861/'},
 {'name': 'ちちぶ銘仙館',
  'tags': ['歴史', '家族', '友人'],
  'car': False,
  'time': 2,
  'area': '秩父市街',
  'type': 'history',
  'description': '秩父銘仙の歴史や染織を紹介し、織物文化に触れられる施設です。',
  'difficulty': 'easy',
  'url': 'https://www.meisenkan.com/'},
 {'name': '武甲山資料館',
  'tags': ['自然', '歴史', '家族', '友人'],
  'car': True,
  'time': 1,
  'area': '羊山公園',
  'type': 'history',
  'description': '秩父のシンボル武甲山の地質や植物、歴史について学べる資料館です。',
  'difficulty': 'easy',
  'url': 'https://www.bukohzan.jp/'},
 {'name': '秩父ふるさと館',
  'tags': ['歴史', 'グルメ', 'デート', '友人'],
  'car': False,
  'time': 1,
  'area': '秩父市街',
  'type': 'history',
  'description': '大正時代の銘仙問屋の主屋を活用した観光拠点。物産や郷土料理も楽しめます。',
  'difficulty': 'easy',
  'url': 'https://navi.city.chichibu.lg.jp/spot/'},
 {'name': '和銅遺跡',
  'tags': ['歴史', '自然', '家族', '友人'],
  'car': True,
  'time': 2,
  'area': '黒谷',
  'type': 'history',
  'description': '日本最初の流通貨幣とされる和同開珎にゆかりのある歴史スポットです。',
  'difficulty': 'medium',
  'url': 'https://navi.city.chichibu.lg.jp/spot/'},
 {'name': '清雲寺',
  'tags': ['自然', '歴史', 'デート', '家族'],
  'car': True,
  'time': 1,
  'area': '荒川',
  'type': 'history',
  'description': 'しだれ桜で知られる荒川地区の寺院。春の花の名所としても親しまれています。',
  'difficulty': 'easy',
  'url': 'https://navi.city.chichibu.lg.jp/spot/'},
 {'name': '秩父華厳の滝',
  'tags': ['自然', 'デート', '家族', '友人'],
  'car': True,
  'time': 2,
  'area': '皆野',
  'type': 'nature',
  'description': '秩父郡皆野町にある滝。周囲の自然とあわせて楽しめる景勝地です。',
  'difficulty': 'medium',
  'url': 'https://www.chichibuji.gr.jp/spot/'},
 {'name': '三十槌の氷柱',
  'tags': ['自然', 'デート', '家族', '友人'],
  'car': True,
  'time': 2,
  'area': '大滝',
  'type': 'nature',
  'description': '岩清水が凍ってできる冬の名所。毎年1月上旬から2月下旬頃に公開される季節限定スポットです。',
  'difficulty': 'medium',
  'url': 'https://navi.city.chichibu.lg.jp/p_flower/1403/'},
 {'name': '小松沢レジャー農園',
  'tags': ['自然', '家族', '友人', 'グルメ'],
  'car': True,
  'time': 3,
  'area': '横瀬',
  'type': 'nature',
  'description': 'いちご狩り、ぶどう狩り、しいたけ狩りなどを楽しめる観光農園です。',
  'difficulty': 'easy',
  'url': 'https://www.chichibuji.gr.jp/spot/spot-syousai46/'},
 {'name': '秩父フルーツファーム',
  'tags': ['自然', '家族', '友人', 'グルメ'],
  'car': True,
  'time': 2,
  'area': '秩父',
  'type': 'nature',
  'description': 'いちご狩りやぶどう狩りなど、季節の果物を楽しめる観光農園です。',
  'difficulty': 'easy',
  'url': 'https://www.chichibuji.gr.jp/spot/spot-syousai48/'},
 {'name': '道の駅ちちぶ',
  'tags': ['グルメ', '家族', '友人'],
  'car': True,
  'time': 1,
  'area': '秩父市街',
  'type': 'nature',
  'description': '秩父のお土産や特産品を探せる道の駅。旅行中の休憩にも便利です。',
  'difficulty': 'easy',
  'url': 'https://www.chichibuji.gr.jp/spot/spot-syousai100/'},
 {'name': '秩父温泉 満願の湯',
  'tags': ['温泉', 'デート', '家族', '友人'],
  'car': True,
  'time': 3,
  'area': '皆野',
  'type': 'nature',
  'description': '秩父温泉を楽しめる日帰り温泉施設。自然の中でゆっくり過ごせます。',
  'difficulty': 'easy',
  'url': 'https://www.chichibuji.gr.jp/spot/spot-syousai116/'},
 {'name': '大滝温泉',
  'tags': ['温泉', '自然', '家族', '友人'],
  'car': True,
  'time': 2,
  'area': '大滝',
  'type': 'nature',
  'description': '道の駅大滝温泉内にある日帰り温泉。奥秩父観光と組み合わせやすい施設です。',
  'difficulty': 'easy',
  'url': 'https://navi.city.chichibu.lg.jp/spot/'}]


# =========================================================
# 宿泊施設データ（既存11件を維持）
# =========================================================

hotels = [{'name': '和銅鉱泉 ゆの宿 和どう',
  'tags': ['温泉', 'デート', '家族', '自然', '歴史'],
  'price': 18000,
  'type': 'onsen',
  'description': '和銅鉱泉の温泉を楽しめる歴史ある宿。ゆっくり過ごしたい旅行におすすめです。',
  'quality': 5,
  'url': 'https://www.wadoh.co.jp/',
  'lat': 35.999,
  'lng': 139.027},
 {'name': '新木鉱泉旅館',
  'tags': ['温泉', 'デート', '家族', '自然'],
  'price': 16000,
  'type': 'onsen',
  'description': '江戸時代から続く秩父の温泉旅館。落ち着いた雰囲気で温泉旅行を楽しめます。',
  'quality': 5,
  'url': 'https://www.onsen-yado.net/',
  'lat': 35.9827,
  'lng': 139.0515},
 {'name': 'NIPPONIA 秩父 門前町',
  'tags': ['歴史', 'デート', 'グルメ', '友人'],
  'price': 20000,
  'type': 'city',
  'description': '秩父の歴史的な街並みを活かした分散型ホテル。街歩きやグルメとの相性が良い宿です。',
  'quality': 5,
  'url': 'https://nipponia-chichibu.jp/',
  'lat': 35.9968,
  'lng': 139.0858},
 {'name': 'ホテルルートインGrand秩父',
  'tags': ['温泉', '友人', '家族', 'グルメ'],
  'price': 12000,
  'type': 'city',
  'description': '秩父市街での観光拠点として利用しやすいホテル。大浴場もあります。',
  'quality': 4,
  'url': 'https://www.route-inn.co.jp/hotel_list/saitama/index_hotel_id_714/',
  'lat': 35.9997,
  'lng': 139.086},
 {'name': 'ホテルルートイン西武秩父駅前',
  'tags': ['友人', '家族', 'グルメ', '歴史'],
  'price': 11000,
  'type': 'city',
  'description': '西武秩父駅から近く、公共交通機関を利用した旅行に便利なホテルです。',
  'quality': 4,
  'url': 'https://www.route-inn.co.jp/hotel_list/saitama/index_hotel_id_60/',
  'lat': 35.9897,
  'lng': 139.084},
 {'name': 'アパホテル〈埼玉秩父駅前〉',
  'tags': ['友人', 'グルメ', '歴史'],
  'price': 10000,
  'type': 'city',
  'description': '秩父駅周辺での観光や市街地散策に便利なホテルです。',
  'quality': 4,
  'url': 'https://www.apahotel.com/hotel/syutoken/saitama/saitama-chichibu-ekimae/',
  'lat': 35.9977,
  'lng': 139.0862},
 {'name': 'ホテル美やま',
  'tags': ['温泉', '自然', '家族', 'デート'],
  'price': 15000,
  'type': 'onsen',
  'description': '秩父の自然を感じながら温泉を楽しめる宿。ゆったりした旅行に向いています。',
  'quality': 5,
  'url': 'https://www.miyama-onsen.com/',
  'lat': 35.9904,
  'lng': 139.0342},
 {'name': '旅館 比与志',
  'tags': ['温泉', 'デート', '歴史', '自然'],
  'price': 15000,
  'type': 'onsen',
  'description': '西武秩父駅から徒歩圏内。落ち着いた雰囲気で秩父観光を楽しめる旅館です。',
  'quality': 5,
  'url': 'http://www.hiyoshi-ryokan.com/',
  'lat': 35.9869,
  'lng': 139.0794},
 {'name': 'ちちぶ温泉 はなのや',
  'tags': ['温泉', 'デート', '家族', '自然'],
  'price': 17000,
  'type': 'onsen',
  'description': '秩父の自然に囲まれた温泉宿。温泉を中心にゆっくり過ごしたい人におすすめです。',
  'quality': 5,
  'url': 'https://chichibu-resort.com/hananoya/',
  'lat': 35.985,
  'lng': 139.0},
 {'name': 'PICA秩父',
  'tags': ['自然', '家族', '友人', 'デート'],
  'price': 13000,
  'type': 'nature',
  'description': '秩父ミューズパーク内にあるアウトドア宿泊施設。自然を満喫したい旅行におすすめです。',
  'quality': 4,
  'url': 'https://www.pica-resort.jp/chichibu/',
  'lat': 35.991,
  'lng': 139.019},
 {'name': '御宿 竹取物語',
  'tags': ['温泉', 'デート', '自然'],
  'price': 22000,
  'type': 'onsen',
  'description': '自然に囲まれた落ち着いた宿。特別感のある旅行や温泉旅行に向いています。',
  'quality': 5,
  'url': 'https://www.oyadotaketori.com/',
  'lat': 35.983,
  'lng': 139.017}]


# =========================================================
# 旅行タイプ判定
# =========================================================

def get_trip_style(member, purpose, age):
    purpose_set = set(purpose)

    if member == "デート":
        if "温泉" in purpose_set:
            return "癒やしの温泉デート"
        if "自然" in purpose_set:
            return "絶景・自然デート"
        if "グルメ" in purpose_set:
            return "食べ歩きグルメ旅"
        if "歴史" in purpose_set:
            return "歴史と街並みを楽しむデート"
        return "ゆったり秩父デート"

    if member == "家族":
        if "自然" in purpose_set:
            return "家族で楽しむ自然満喫旅"
        if "温泉" in purpose_set:
            return "家族で楽しむ温泉旅"
        if "グルメ" in purpose_set:
            return "家族で楽しむ秩父グルメ旅"
        if "歴史" in purpose_set:
            return "親子で楽しむ歴史旅"
        return "家族みんなで楽しむ秩父旅"

    if member == "友人":
        if "グルメ" in purpose_set:
            return "友達と楽しむグルメ旅"
        if "自然" in purpose_set:
            return "友達と楽しむアクティブ旅"
        if "温泉" in purpose_set:
            return "友達と楽しむ温泉旅"
        if "歴史" in purpose_set:
            return "友達と巡る秩父歴史旅"
        return "友達と楽しむ秩父満喫旅"

    if age <= 20:
        return "学生向け秩父旅"
    if age <= 30:
        return "若者向け秩父旅"
    if age <= 40:
        return "大人の秩父旅"
    return "ゆったり楽しむ秩父旅"


# =========================================================
# 41施設マスターから季節情報を参照して既存データへ付加
# =========================================================

def attach_master_season_data(items):
    """
    既存の推薦用データを壊さず、41施設マスターの季節情報を付加する。
    地図処理でもマスターの住所・座標を参照できるようにする。
    マスターに値がない項目は空のままとし、推測で補完しない。
    """
    enriched = []
    for item in items:
        copied = item.copy()
        master = facility_master.get(copied.get("name", ""), {})
        if not isinstance(master, dict):
            master = {}
        copied["season"] = master.get("season")
        copied["best_season"] = master.get("best_season")
        copied["seasonal_operation"] = master.get("seasonal_operation")
        copied["master_closed"] = master.get("closed")
        copied["master_status"] = master.get("status")
        copied["master_address"] = master.get("address") or (master.get("basic") or {}).get("address")
        copied["master_latitude"] = master.get("latitude")
        copied["master_longitude"] = master.get("longitude")
        enriched.append(copied)
    return enriched


spots = attach_master_season_data(spots)
hotels = attach_master_season_data(hotels)


# =========================================================
# 共通ヘルパー
# =========================================================

def _valid_coordinate(value):
    """数値として安全に扱える緯度・経度だけを採用する。"""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _map_context(item):
    """
    地図情報の優先順位を統一する。
    1. itemのlatitude/longitude
    2. legacyのlat/lng
    3. 41施設マスターのlatitude/longitude
    4. itemのaddress
    5. 41施設マスターのaddress
    6. 施設名 + エリア + Chichibu Saitama Japan
    """
    name = str(item.get("name") or "").strip()
    area = str(item.get("area") or "").strip()

    lat = _valid_coordinate(item.get("latitude"))
    lng = _valid_coordinate(item.get("longitude"))
    if lat is None:
        lat = _valid_coordinate(item.get("lat"))
    if lng is None:
        lng = _valid_coordinate(item.get("lng"))
    if lat is None:
        lat = _valid_coordinate(item.get("master_latitude"))
    if lng is None:
        lng = _valid_coordinate(item.get("master_longitude"))

    address = item.get("address") or item.get("master_address")
    if isinstance(address, dict):
        address = address.get("full") or address.get("text")
    address = str(address).strip() if address else ""

    if lat is not None and lng is not None:
        query = f"{lat:.7f},{lng:.7f}"
        source = "coordinates"
    elif address and name:
        query = f"{name} {address}".strip()
        source = "address"
    elif address:
        query = address
        source = "address"
    elif name:
        parts = [name]
        if area:
            parts.append(area)
        parts.extend(["秩父", "埼玉県", "日本"])
        query = " ".join(parts)
        source = "name_fallback"
    else:
        query = ""
        source = None

    return query, source


def build_map_url(item):
    """Google Maps外部リンクと埋め込みURLを同じ検索条件から生成する。"""
    query, source = _map_context(item)
    if not query:
        return None, None, None, source
    encoded = quote(query, safe="")
    external_url = "https://www.google.com/maps/search/?api=1&query=" + encoded
    embed_url = "https://www.google.com/maps?q=" + encoded + "&output=embed"
    return external_url, embed_url, query, source


def attach_map_data(item):
    """既存データを変更せず、結果画面用の地図情報だけを追加する。"""
    copied = item.copy()
    map_url, embed_url, query, source = build_map_url(copied)
    copied["map_url"] = map_url
    copied["map_embed_url"] = embed_url
    copied["map_query"] = query
    copied["map_source"] = source
    copied["map_available"] = bool(query)
    return copied


def _favorite_catalog_item(item, category):
    """お気に入り専用画面向けに、既存データから詳細表示用の情報をまとめる。
    新しい情報は推測せず、既存データまたは41施設マスターの値だけを利用する。
    """
    copied = item.copy()

    if category in ("観光地", "宿泊施設"):
        master = facility_master.get(copied.get("name", ""), {})
        if not isinstance(master, dict):
            master = {}
        basic = master.get("basic") if isinstance(master.get("basic"), dict) else {}
        master_access = master.get("access") if isinstance(master.get("access"), dict) else {}

        copied["area"] = copied.get("area") or basic.get("area")
        copied["type"] = copied.get("type") or basic.get("type")
        copied["time"] = copied.get("time") if copied.get("time") is not None else basic.get("stay_time_hours")
        copied["description"] = copied.get("description") or master.get("description")
        copied["address"] = copied.get("address") or master.get("address") or basic.get("address")
        copied["phone"] = copied.get("phone") or master.get("phone")
        copied["hours"] = copied.get("hours") or master.get("hours")
        copied["price"] = copied.get("price") or master.get("price")
        copied["closed"] = copied.get("closed") or master.get("closed")
        copied["parking"] = copied.get("parking") or master.get("parking")
        copied["season"] = copied.get("season") or master.get("season")
        copied["notes"] = copied.get("notes") or master.get("notes")
        copied["car_free"] = copied.get("car_free") or master.get("car_free")
        copied["required_reservation"] = copied.get("required_reservation") or master.get("required_reservation")
        copied["access"] = copied.get("access") or master_access
        copied["url"] = copied.get("url") or master.get("official_url") or master.get("source")

    if category == "飲食店":
        copied["url"] = copied.get("official_url") or copied.get("url") or ""

    copied = attach_map_data(copied)
    copied["favorite_type"] = category

    # JavaScriptへ渡すデータは必要な項目に絞り、HTML内の巨大化を防ぐ。
    return {
        "type": category,
        "name": copied.get("name", ""),
        "address": copied.get("address") or "",
        "area": copied.get("area") or "",
        "category_detail": copied.get("type") or "",
        "description": copied.get("description") or "",
        "time": copied.get("time"),
        "phone": copied.get("phone") or "",
        "hours": copied.get("hours") or "",
        "price": copied.get("price") or "",
        "closed": copied.get("closed") or "",
        "parking": copied.get("parking") or "",
        "season": copied.get("season") or "",
        "notes": copied.get("notes") or "",
        "car_free": copied.get("car_free") or "",
        "required_reservation": copied.get("required_reservation") or "",
        "access": copied.get("access") if isinstance(copied.get("access"), dict) else {},
        "url": copied.get("url") or copied.get("official_url") or "",
        "map_url": copied.get("map_url") or "",
    }


def build_favorite_catalog():
    """観光地・飲食店・宿泊施設の既存データからお気に入り画面用カタログを作る。"""
    catalog = {
        "観光地": [_favorite_catalog_item(item, "観光地") for item in spots],
        "飲食店": [_favorite_catalog_item(item, "飲食店") for item in restaurants],
        "宿泊施設": [_favorite_catalog_item(item, "宿泊施設") for item in hotels],
    }
    return catalog


def normalize_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def price_number(price_text):
    if not price_text:
        return None
    numbers = re.findall(r"\d[\d,]*", str(price_text))
    if not numbers:
        return None
    try:
        return int(numbers[0].replace(",", ""))
    except (ValueError, TypeError):
        return None


def get_season_from_date(travel_date):
    """
    旅行予定日から基本の四季を判定する。
    未入力・不正な日付の場合はNoneを返し、既存推薦をそのまま利用できるようにする。
    12～2月: 冬 / 3～5月: 春 / 6～8月: 夏 / 9～11月: 秋
    """
    if not travel_date:
        return None

    try:
        month = datetime.strptime(travel_date, "%Y-%m-%d").month
    except (ValueError, TypeError):
        return None

    if month in (12, 1, 2):
        return "冬"
    if month in (3, 4, 5):
        return "春"
    if month in (6, 7, 8):
        return "夏"
    return "秋"


def make_recommendation_seed(age, gender, people, member, car, days, budget, purpose, travel_date=""):
    purpose_text = "|".join(sorted(purpose)) if isinstance(purpose, list) else str(purpose)
    source = f"{age}|{gender}|{people}|{member}|{car}|{days}|{budget}|{purpose_text}|{travel_date}"
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


SEASON_MONTHS = {
    "冬": {12, 1, 2},
    "春": {3, 4, 5},
    "夏": {6, 7, 8},
    "秋": {9, 10, 11},
}


def _season_text(*values):
    return " ".join(str(v) for v in values if v)


def _month_in_closed_range(travel_date, text):
    """明示された月範囲だけを確認する。推測で範囲を作らない。"""
    if not travel_date or not text:
        return None

    try:
        dt = datetime.strptime(travel_date, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None

    # 例: 「3月1日～12月上旬のみ営業」
    ranges = re.findall(r"(\d{1,2})月(?:\d{1,2}日)?[^〜～\-]*(?:〜|～|\-)[^0-9]*(\d{1,2})月", str(text))
    if not ranges:
        return None

    month = dt.month
    for start_month, end_month in ranges:
        start_month = int(start_month)
        end_month = int(end_month)
        if start_month <= end_month:
            return start_month <= month <= end_month
        return month >= start_month or month <= end_month
    return None


def calculate_season_effect(item, season, travel_date):
    """
    41施設マスターの season / best_season / seasonal_operation を根拠に
    季節スコアと説明理由を返す。

    明示された営業期間外だけ除外し、それ以外は季節情報が足りなければ
    推測で減点・除外しない。
    """
    if not season:
        return 0, [], False

    season_value = str(item.get("season") or "")
    best_value = str(item.get("best_season") or "")
    operation_value = str(item.get("seasonal_operation") or "")
    closed_value = str(item.get("master_closed") or "")
    combined = _season_text(season_value, best_value, operation_value)

    reasons = []
    score = 0
    unavailable = False

    # 明示的な季節営業・休業情報を最優先。
    closed_range = _month_in_closed_range(travel_date, closed_value)
    if closed_range is False and ("のみ営業" in closed_value or "営業" in closed_value and "～" in closed_value):
        unavailable = True
        reasons.append("旅行予定日が明示された営業期間外")
        return -1000, reasons, unavailable

    if season == "冬" and ("冬季休業" in closed_value or "冬季休業" in combined):
        unavailable = True
        reasons.append("冬季休業の時期に該当")
        return -1000, reasons, unavailable

    # 2026年の終了日など、マスターに明示された日付だけを利用。
    if travel_date:
        try:
            dt = datetime.strptime(travel_date, "%Y-%m-%d")
        except (ValueError, TypeError):
            dt = None
        if dt and str(dt.year) in closed_value:
            m = re.search(r"(\d{1,2})[月/]?(\d{1,2})?日?(?:で)?終了", closed_value)
            if m:
                end_month = int(m.group(1))
                end_day = int(m.group(2) or 1)
                if (dt.month, dt.day) > (end_month, end_day):
                    unavailable = True
                    reasons.append("マスターに記載された今年の営業終了日を過ぎている")
                    return -1000, reasons, unavailable

    if not combined:
        return 0, reasons, unavailable

    # best_season / seasonal_operation が具体的に入っている場合を最優先。
    if season in best_value:
        score += 30
        reasons.append(f"{season}が見頃・適季節として登録されている")
    elif season in operation_value:
        score += 28
        reasons.append(f"{season}の季節営業・運用情報がある")
    else:
        # 「1月中旬～2月中旬が見頃」のように、季節名ではなく
        # 月範囲だけで記録されているデータにも対応する。
        month_ranges = re.findall(
            r"(\d{1,2})月(?:[^〜～\-]*)(?:〜|～|\-)[^0-9]*(\d{1,2})月",
            season_value
        )
        month_matched = False
        month_known = False
        if month_ranges and travel_date:
            try:
                dt = datetime.strptime(travel_date, "%Y-%m-%d")
                current_month = dt.month
                for start_month, end_month in month_ranges:
                    start_month = int(start_month)
                    end_month = int(end_month)
                    month_known = True
                    if start_month <= end_month:
                        if start_month <= current_month <= end_month:
                            month_matched = True
                            break
                    else:
                        if current_month >= start_month or current_month <= end_month:
                            month_matched = True
                            break
            except (ValueError, TypeError):
                pass

        if month_matched and any(word in season_value for word in ["見頃", "中心", "営業", "公開"]):
            score += 30
            reasons.append(f"旅行予定月が{season_value}に記載された時期と一致する")
        elif month_known and any(word in season_value for word in ["見頃", "中心", "営業", "公開"]):
            score -= 10

        if season in season_value:
            score += 20
            reasons.append(f"{season}の季節情報が登録されている")
        elif "春～秋" in season_value or "春から秋" in season_value:
            if season in {"春", "夏", "秋"}:
                score += 16
                reasons.append("春～秋に適した季節情報が登録されている")
            else:
                score -= 12
        elif "冬～早春" in season_value or "冬から早春" in season_value:
            if season == "冬":
                score += 18
                reasons.append("冬～早春の季節情報が登録されている")
            else:
                score -= 8
        elif "年間" in combined:
            # 通年施設は季節だけで余計な加点をしない。
            pass

    # 旅行月が明示された季節情報と一致しない場合でも、
    # データが十分でない限り勝手に季節外と断定しない。
    return score, reasons, unavailable


def diverse_select(items, target_count, seed, key_name, group_names=None, request_nonce=0):
    """
    スコア上位だけをそのまま固定表示せず、
    条件に合う上位候補の中から、スコアを大きく落とさない範囲で
    エリア・ジャンルなどの偏りを抑えながら選ぶ。

    seedには年齢・性別・人数・同行者・車・日数・予算・目的・旅行日を
    含め、さらにリクエストごとの非決定的なnonceを加えることで、
    同じ条件でも候補プール内から組み合わせを変えられる。
    ただし、選択対象はスコア上位の条件適合候補に限定する。
    """

    if not items or target_count <= 0:
        return []

    rng = random.Random((seed ^ request_nonce) & ((1 << 64) - 1))

    ranked = []
    for item in items:
        copied = item.copy()
        copied["selection_score"] = item["score"] + rng.uniform(0, 8)
        ranked.append(copied)

    ranked.sort(
        key=lambda x: x["selection_score"],
        reverse=True
    )

    # 上位だけでなく、ある程度点数の近い候補も候補プールへ入れる
    top_score = ranked[0]["score"]
    pool = [
        item for item in ranked
        if item["score"] >= top_score - 35
    ]

    minimum_pool = min(
        len(ranked),
        max(target_count * 4, 10)
    )

    if len(pool) < minimum_pool:
        pool = ranked[:minimum_pool]

    selected = []
    used_keys = set()
    used_groups = {
        name: {}
        for name in (group_names or [])
    }

    # 同じエリア・同じジャンルが続きすぎないようにする
    while pool and len(selected) < target_count:
        scored_candidates = []

        for item in pool:
            item_key = item.get(key_name)
            if item_key in used_keys:
                continue

            value = item["selection_score"]

            for group_name in (group_names or []):
                group_value = item.get(group_name)

                if isinstance(group_value, list):
                    group_values = group_value
                else:
                    group_values = [group_value]

                for gv in group_values:
                    if gv is None or gv == "":
                        continue
                    count = used_groups[group_name].get(gv, 0)

                    if count >= 2:
                        value -= 25
                    elif count == 1:
                        value -= 10

            # 同点付近の候補を少し動かす
            value += rng.uniform(0, 2)
            scored_candidates.append((value, item))

        if not scored_candidates:
            break

        scored_candidates.sort(
            key=lambda x: x[0],
            reverse=True
        )

        # 常に1位固定ではなく、上位候補から条件に応じたseedで選ぶ
        top_candidates = scored_candidates[:min(5, len(scored_candidates))]

        weights = []
        max_value = top_candidates[0][0]

        for value, _item in top_candidates:
            # 最高候補を優先しつつ、近い候補も選択対象にする
            diff = max_value - value
            weight = max(0.15, 1.0 - (diff / 30.0))
            weights.append(weight)

        total_weight = sum(weights)
        pick = rng.uniform(0, total_weight)

        chosen = top_candidates[-1][1]
        running = 0

        for (value, item), weight in zip(top_candidates, weights):
            running += weight
            if pick <= running:
                chosen = item
                break

        selected.append(chosen)
        used_keys.add(chosen.get(key_name))

        for group_name in (group_names or []):
            group_value = chosen.get(group_name)

            if isinstance(group_value, list):
                group_values = group_value
            else:
                group_values = [group_value]

            for gv in group_values:
                if gv is None or gv == "":
                    continue
                used_groups[group_name][gv] = (
                    used_groups[group_name].get(gv, 0) + 1
                )

        pool.remove(chosen)

    return selected


def _unique_reason_parts(reasons):
    parts = []
    for reason in reasons or []:
        text = str(reason).strip()
        if text and text not in parts:
            parts.append(text)
    return parts


def build_recommendation_reason(item, reasons, age, people, member, car, days, budget, purpose, travel_date, season, category="spot"):
    """施設データと実際の推薦理由だけを材料に、100～200字程度の説明文を作る。"""
    reasons = _unique_reason_parts(reasons)
    name = str(item.get("name", "この施設"))
    description = str(item.get("description", "")).strip()
    reason_text = "、".join(reasons[:4])

    paragraphs = []

    if travel_date:
        try:
            dt = datetime.strptime(travel_date, "%Y-%m-%d")
            date_text = f"{dt.year}年{dt.month}月{dt.day}日"
            if season:
                paragraphs.append(f"{date_text}の{season}旅行")
        except (ValueError, TypeError):
            date_text = ""
    else:
        date_text = ""

    if season and not travel_date:
        paragraphs.append(f"今回の{season}旅行")

    if description:
        paragraphs.append(f"{name}は{description}")

    if reason_text:
        paragraphs.append(f"今回の条件では、{reason_text}と判断できる点を推薦理由として評価しています")

    # 実際にスコアリングに使った条件だけを文章化する。
    matched_purposes = [p for p in purpose if p in str(item.get("tags", []))]
    if matched_purposes:
        purpose_text = "・".join(matched_purposes)
        paragraphs.append(f"旅行目的の「{purpose_text}」とも合っています")

    if car == "なし" and any("車なし" in r or "公共交通" in r for r in reasons):
        paragraphs.append("車を使わない今回の旅行条件にも合わせやすい点を考慮しています")
    elif car == "あり" and any("車" in r or "駐車" in r for r in reasons):
        paragraphs.append("車を利用する条件との相性も推薦時に考慮しています")

    if people >= 5 and any("大人数" in r for r in reasons):
        paragraphs.append(f"{people}人の旅行でも利用条件に合うことを考慮しています")
    elif people >= 2 and any("2人" in r or "少人数" in r for r in reasons):
        paragraphs.append(f"{people}人での旅行条件との相性も評価しています")

    if days == "1泊2日" and any("1泊2日" in r for r in reasons):
        paragraphs.append("1泊2日の限られた日程にも組み込みやすい点を評価しています")
    elif days == "2泊3日" and any("2泊3日" in r for r in reasons):
        paragraphs.append("2泊3日の旅程に組み込みやすい点も考慮しています")

    if category == "hotel":
        price_value = item.get("price")
        if isinstance(price_value, (int, float)):
            if price_value <= budget:
                paragraphs.append(f"宿の参考予算は1人{price_value:,}円で、設定した1人あたり予算{budget:,}円以内です")
            else:
                paragraphs.append(f"宿の参考予算は1人{price_value:,}円で、設定した1人あたり予算との差も確認しています")

    def compose(parts):
        value = "。".join(x.rstrip("。") for x in parts if x)
        if value and not value.endswith("。"):
            value += "。"
        return value

    text = compose(paragraphs)

    # 情報量が多すぎる場合は、根拠の弱い補足から削り、200字前後に収める。
    if len(text) > 200 and len(reasons) > 3:
        reduced_paragraphs = []
        for paragraph in paragraphs:
            if reason_text and paragraph.startswith("今回の条件では、"):
                reduced_reason_text = "、".join(reasons[:3])
                reduced_paragraphs.append(
                    f"今回の条件では、{reduced_reason_text}と判断できる点を推薦理由として評価しています"
                )
            else:
                reduced_paragraphs.append(paragraph)
        text = compose(reduced_paragraphs)

    if len(text) > 200:
        # 施設説明が長い場合のみ、説明部分を根拠を失わない範囲で短くする。
        short_description = description[:65].rstrip("。") if description else ""
        shortened = []
        for paragraph in paragraphs:
            if description and paragraph == f"{name}は{description}" and short_description:
                shortened.append(f"{name}は{short_description}")
            else:
                shortened.append(paragraph)
        text = compose(shortened)

    # 短すぎる場合は、実際の入力条件を補足して説明を具体化する。
    if len(text) < 100:
        condition_summary = f"{age}代・{people}人・{member}・車{car}・{days}・予算{budget:,}円/人"
        text += f"入力条件（{condition_summary}）をもとに、施設データに確認できる特徴だけを組み合わせて選定しています。"

    return text[:200] if len(text) > 200 else text


# =========================================================
# 観光地スコアリング
# =========================================================


def _summary_purpose_text(purpose):
    """旅行目的を自然な日本語にまとめる。"""
    purpose = [str(p).strip() for p in (purpose or []) if str(p).strip()]
    if not purpose:
        return "秩父観光"
    if len(purpose) == 1:
        mapping = {
            "自然": "自然",
            "温泉": "温泉での癒やし",
            "グルメ": "食",
            "歴史": "歴史や文化",
        }
        return mapping.get(purpose[0], purpose[0])
    mapping = {
        "自然": "自然",
        "温泉": "温泉",
        "グルメ": "グルメ",
        "歴史": "歴史・文化",
    }
    return "・".join(mapping.get(p, p) for p in purpose)


def _build_summary_concept(purpose):
    purpose_set = set(purpose or [])
    if {"自然", "温泉"}.issubset(purpose_set):
        return "自然と温泉を楽しみながら"
    if {"自然", "グルメ"}.issubset(purpose_set):
        return "自然と秩父グルメを楽しみながら"
    if {"歴史", "グルメ"}.issubset(purpose_set):
        return "歴史や文化に触れながら秩父グルメも楽しむ"
    if {"歴史", "温泉"}.issubset(purpose_set):
        return "歴史や文化と温泉を楽しむ"
    if len(purpose_set) >= 3:
        return f"{_summary_purpose_text(purpose)}をバランスよく楽しむ"
    return f"{_summary_purpose_text(purpose)}を中心に楽しむ"


def _format_summary_areas(recommended_spots):
    areas = []
    for spot in recommended_spots or []:
        area = str(spot.get("area", "")).strip()
        if area and area not in areas:
            areas.append(area)
    if not areas:
        return "秩父周辺"
    if len(areas) == 1:
        return f"{areas[0]}エリア"
    # 「秩父」と「秩父市街」が同時に入った場合は重複を避ける。
    if "秩父" in areas and "秩父市街" in areas:
        areas = [area for area in areas if area != "秩父"]
    shown = areas[:3]
    return "・".join(shown) + ("など" if len(areas) > 3 else "")


def _build_trip_summary(
    age,
    people,
    member,
    car,
    days,
    budget,
    purpose,
    travel_date,
    season,
    recommended_spots,
    recommended_hotel,
    recommended_restaurants,
    sightseeing_time,
):
    """TRIP SUMMARY用の150～250文字程度の旅行コンセプトを生成する。

    推薦順位そのものは決めず、すでに選ばれた施設と入力条件だけを文章化する。
    """
    purpose = purpose or []
    areas = _format_summary_areas(recommended_spots)
    spot_count = len(recommended_spots or [])
    hotel_name = str((recommended_hotel or {}).get("name", "宿泊施設"))

    date_text = ""
    if travel_date:
        try:
            dt = datetime.strptime(travel_date, "%Y-%m-%d")
            date_text = f"{dt.year}年{dt.month}月{dt.day}日"
        except (ValueError, TypeError):
            date_text = ""

    # 目的＋日数を冒頭で明確化
    concept = _build_summary_concept(purpose)
    season_prefix = f"{season}の" if season else ""
    first = (
        f"今回は、{season_prefix}秩父で{concept}、"
        f"{days}の旅行プランです。"
    )

    # 人数・同行者は入力値をそのまま自然な文へ反映
    if member == "デート":
        group_phrase = f"{people}人でのデート旅行"
    elif member == "家族":
        group_phrase = f"家族{people}人での旅行"
    elif member == "友人":
        group_phrase = f"友人{people}人での旅行"
    else:
        group_phrase = f"{people}人での旅行"

    second = (
        f"{group_phrase}という条件を踏まえ、{areas}にある"
        f"{spot_count}か所のスポットを組み合わせ、観光と移動のバランスを考えています。"
    )

    # 旅行日・季節は、具体的な日付がある場合のみ自然に言及
    if date_text and season:
        seasonal_match = 0
        for spot in recommended_spots or []:
            season_text = " ".join(
                str(spot.get(key, ""))
                for key in ("season", "best_season", "seasonal_operation")
                if spot.get(key)
            )
            if season in season_text:
                seasonal_match += 1
        if seasonal_match > 0:
            third = (
                f"{date_text}の{season}旅行という時期も考慮し、"
                f"選ばれた施設の季節情報を確認したうえで候補を組み込んでいます。"
            )
        else:
            third = (
                f"{date_text}の{season}旅行という時期も条件に含め、"
                f"旅行日に合わせて施設を選んでいます。"
            )
    elif season:
        third = f"今回の{season}旅行という季節条件も推薦結果に反映しています。"
    else:
        third = "旅行予定日が未入力のため、季節条件は使わずにプランを構成しています。"

    # 車の有無は推薦条件に基づいて記述
    if car == "なし":
        fourth = (
            "車を使わない条件を踏まえ、公共交通機関で訪れやすい施設を評価し、"
            "無理なく巡れるようにしています。"
        )
    elif car == "あり":
        fourth = (
            "車を利用できる条件を活かし、移動の自由度を考慮しながら"
            "複数のスポットを組み合わせています。"
        )
    else:
        fourth = "移動条件も考慮し、観光スポットを無理なく組み合わせています。"

    # 予算は実際に宿の参考予算を比較した結果から、言い過ぎない形で記述
    hotel_price = (recommended_hotel or {}).get("price")
    if isinstance(hotel_price, (int, float)):
        if hotel_price <= budget:
            budget_sentence = (
                f"宿泊には{hotel_name}を組み合わせ、1人あたり{budget:,}円の設定予算を基準に、"
                f"参考宿泊費{hotel_price:,}円も確認しています。"
            )
        else:
            budget_sentence = (
                f"宿泊には{hotel_name}を組み合わせ、1人あたり{budget:,}円の設定予算と"
                f"参考宿泊費{hotel_price:,}円との差も確認しています。"
            )
    else:
        budget_sentence = f"設定した1人あたり{budget:,}円の予算も条件の一つとしてプランに反映しています。"

    # 年齢については、現在の推薦ロジックで歩きやすさ・難易度が実際に効いている場合だけ触れる
    age_reason_text = " ".join(
        str(reason)
        for spot in (recommended_spots or [])
        for reason in spot.get("reasons", [])
    )
    age_sentence = ""
    if any(word in age_reason_text for word in ("比較的歩きやすい", "移動負担が大きくなりやすい", "若い世代でも動きやすい", "アクティブに楽しめる")):
        age_sentence = (
            f"{age}代という年齢条件も踏まえ、移動の負担やアクティブさとのバランスも考慮しています。"
        )

    # 最後は旅行全体のまとめ。目的に応じて自然な締め方を変える
    if "グルメ" in purpose:
        final = "観光だけで終わらず、秩父の食も合わせて楽しめる、旅行全体のバランスを意識した内容です。"
    elif "温泉" in purpose:
        final = "観光と休息のメリハリをつけながら、秩父での滞在をゆったり楽しめる内容です。"
    elif "自然" in purpose:
        final = "観光地を巡るだけでなく、秩父らしい自然を感じながら過ごせる内容です。"
    elif "歴史" in purpose:
        final = "観光とあわせて秩父の歴史や文化にも触れられる、まとまりのある内容です。"
    else:
        final = "観光・食事・宿泊を組み合わせ、限られた日程の中でも楽しみやすい内容です。"

    # 150～250字を目標に、情報の優先度が高い文から組み立てる。
    candidates = [first, second, third, fourth, budget_sentence, final]
    if age_sentence:
        candidates.insert(4, age_sentence)

    selected = []
    for sentence in candidates:
        candidate = "".join(selected + [sentence])
        if len(candidate) <= 250:
            selected.append(sentence)

    # 250字を超えてしまった場合は、任意の長文説明を削って調整
    text = "".join(selected)
    if len(text) < 150:
        # 最低限の補足は、実際の数値・条件だけで構成する。
        fallback = (
            f"今回のプランでは、{spot_count}か所の観光スポットを{days}の日程に組み込み、"
            f"総観光時間の目安を約{sightseeing_time}時間としています。"
        )
        if len(text) + len(fallback) <= 250:
            text += fallback

    # それでも長い場合は、文単位で150字以上をなるべく維持しながら末尾を削る。
    if len(text) > 250:
        text = text[:247].rsplit("。", 1)[0] + "。"

    return text


def calculate_spot_score(spot, member, purpose, car, age, people, days, budget, gender, season=None, travel_date=""):
    score = 0
    reasons = []

    season_score, season_reasons, unavailable = calculate_season_effect(spot, season, travel_date)
    if unavailable:
        return season_score, season_reasons
    score += season_score
    reasons.extend(season_reasons)

    # 目的を最重要条件として反映
    purpose_match = sum(1 for p in purpose if p in spot["tags"])
    if purpose_match:
        score += 40 * purpose_match
        for p in purpose:
            if p in spot["tags"]:
                reasons.append(f"{p}を楽しめる")
    else:
        score -= 20

    if purpose_match >= 2:
        score += 12
        reasons.append("複数の旅行目的に合う")

    # 同行者
    if member in spot["tags"]:
        score += 30
        reasons.append(f"{member}旅行に向いている")
    else:
        score -= 10

    # 車
    if car == "あり":
        if spot["car"]:
            score += 25
            reasons.append("車でアクセスしやすい")
        else:
            score += 4
    else:
        if not spot["car"]:
            score += 30
            reasons.append("車なしでも訪れやすい")
        else:
            score -= 18

    # 年齢
    if age <= 20:
        if spot["difficulty"] == "easy":
            score += 7
        elif spot["difficulty"] == "medium":
            score += 12
            reasons.append("若い世代でも動きやすい")
        else:
            score += 8
            reasons.append("アクティブに楽しめる")
    elif age <= 30:
        if spot["difficulty"] == "easy":
            score += 8
        elif spot["difficulty"] == "medium":
            score += 7
        else:
            score += 3
    elif age <= 40:
        if spot["difficulty"] == "easy":
            score += 8
        elif spot["difficulty"] == "medium":
            score += 5
    else:
        if spot["difficulty"] == "easy":
            score += 18
            reasons.append("比較的歩きやすい")
        elif spot["difficulty"] == "medium":
            score += 5
        else:
            score -= 18
            reasons.append("移動負担が大きくなりやすい")

    # 人数
    if people >= 5:
        if member in ["家族", "友人"]:
            score += 12
            reasons.append("大人数でも楽しみやすい")
    elif people <= 2 and member == "デート" and "デート" in spot["tags"]:
        score += 14
        reasons.append("2人で楽しみやすい")
    elif people == 1:
        if spot["difficulty"] == "easy":
            score += 5

    # 日数
    if days == "1泊2日":
        if spot["time"] <= 2:
            score += 10
            reasons.append("1泊2日でも組み込みやすい")
        elif spot["time"] >= 4:
            score -= 8
    else:
        if spot["time"] >= 3:
            score += 8
            reasons.append("2泊3日の旅程に組み込みやすい")

    # 長時間移動
    if spot["time"] >= 4 and car == "なし":
        score -= 12

    # このデータには観光地価格情報がないため budget は直接使わない
    _ = budget

    # 性別は店舗・施設適性データがないため、固定的な男女別推薦はしない。
    # gender は推薦シードに含め、同点候補の決定性に利用する。
    _ = gender

    return score, reasons


# =========================================================
# グルメスコアリング
# =========================================================

def calculate_restaurant_score(restaurant, member, purpose, car, people, budget, age, days, gender):
    score = 0
    reasons = []

    if "グルメ" in purpose:
        score += 55
        reasons.append("旅行目的に合う")

    if member == "デート":
        if restaurant.get("date_type_friendly") is True:
            score += 35
            reasons.append("デート利用に向いている")
        else:
            score -= 8
    elif member == "家族":
        if restaurant.get("family_friendly") is True:
            score += 35
            reasons.append("家族で利用しやすい")
        else:
            score -= 8
    elif member == "友人":
        if restaurant.get("group_friendly") is True:
            score += 35
            reasons.append("友人・グループで利用しやすい")
        else:
            score -= 5

    if people <= 2:
        if member == "デート" and restaurant.get("date_type_friendly") is True:
            score += 18
            reasons.append("少人数で利用しやすい")
    elif people <= 4:
        if restaurant.get("family_friendly") or restaurant.get("group_friendly"):
            score += 8
    else:
        if restaurant.get("group_friendly") is True:
            score += 28
            reasons.append("大人数で利用しやすい")
        else:
            score -= 12

    if car == "なし":
        try:
            car_free = float(restaurant.get("car_free_score", 0))
        except (ValueError, TypeError):
            car_free = 0
        score += car_free * 8
        if car_free >= 4:
            reasons.append("車なしでも利用しやすい")
        elif car_free <= 2:
            score -= 6
    else:
        parking = restaurant.get("parking", {})
        if isinstance(parking, dict) and parking.get("available") is True:
            score += 28
            reasons.append("駐車場を利用しやすい")
        else:
            score -= 5

    if restaurant.get("lunch") is True:
        score += 8
    if restaurant.get("dinner") is True:
        score += 8

    if days == "2泊3日" and restaurant.get("lunch") and restaurant.get("dinner"):
        score += 6

    restaurant_price = price_number(restaurant.get("price"))
    if restaurant_price is not None:
        if restaurant_price <= budget:
            score += 25
            reasons.append("予算内で利用しやすい")
        elif restaurant_price <= budget * 1.15:
            score += 5
        else:
            score -= 25

    specialties = normalize_list(restaurant.get("specialties"))
    chichibu_keywords = ["豚みそ丼", "わらじかつ", "秩父そば", "みそポテト", "郷土料理", "ホルモン"]
    if any(any(word in str(item) for word in chichibu_keywords) for item in specialties):
        score += 18
        reasons.append("秩父ならではの料理を楽しめる")

    genres = normalize_list(restaurant.get("genre"))
    genre_text = " ".join(str(g) for g in genres)

    if member == "デート" and any(word in genre_text for word in ["イタリアン", "洋食", "カフェ"]):
        score += 15
        reasons.append("デートで選びやすいジャンル")

    if member == "友人" and people >= 4 and any(word in genre_text for word in ["焼肉", "ホルモン", "居酒屋", "定食"]):
        score += 15
        reasons.append("友人同士で楽しみやすいジャンル")

    if member == "家族" and any(word in genre_text for word in ["そば", "うどん", "定食", "和食"]):
        score += 12
        reasons.append("家族で選びやすいジャンル")

    # 年齢は歩行負担データがある店だけ補助的に利用
    walking = str(restaurant.get("walking_difficulty", ""))
    if age >= 50 and walking in ["低", "少", "少ない"]:
        score += 12
        reasons.append("移動負担が少ない")
    elif age <= 30 and walking in ["低", "少", "少ない"]:
        score += 5

    # 性別は適性データがないため直接判定しない
    _ = gender

    return score, reasons


# =========================================================
# 宿泊施設スコアリング
# =========================================================

def calculate_hotel_score(hotel, member, purpose, budget, people, age, car, days, gender, season=None, travel_date=""):
    score = 0
    reasons = []

    season_score, season_reasons, unavailable = calculate_season_effect(hotel, season, travel_date)
    if unavailable:
        return season_score, season_reasons
    score += season_score
    reasons.extend(season_reasons)

    if member in hotel["tags"]:
        score += 35
        reasons.append(f"{member}旅行と相性が良い")
    else:
        score -= 5

    purpose_match = 0
    for p in purpose:
        if p in hotel["tags"]:
            score += 28
            purpose_match += 1
            reasons.append(f"{p}を楽しみやすい")

    if purpose_match == 0:
        score -= 12

    if hotel["price"] <= budget:
        score += 45
        reasons.append("予算内に収まりやすい宿")
        if budget - hotel["price"] >= 5000:
            score += 5
    else:
        over = hotel["price"] - budget
        score -= min(50, over // 500)

    if people >= 5 and member in ["家族", "友人"]:
        score += 12
        reasons.append("複数人での旅行と相性が良い")
    elif people <= 2 and member == "デート" and "デート" in hotel["tags"]:
        score += 12
        reasons.append("2人の旅行と相性が良い")

    if age >= 50 and hotel["quality"] >= 5:
        score += 8
        reasons.append("落ち着いて過ごしやすい宿")
    elif age <= 30 and hotel["type"] in ["city", "nature"]:
        score += 5

    if days == "2泊3日" and hotel["quality"] >= 5:
        score += 5

    # 現在の宿データには駐車場の詳細がないため、推測で加点しない
    _ = car
    _ = gender

    score += hotel["quality"] * 2
    return score, reasons


# =========================================================
# 天気予報（秩父市・7日間）
# =========================================================

# Open-Meteoで使用する秩父市の代表点。
# デジタル庁アドレス・ベース・レジストリに基づく秩父市の代表点を使用。
CHICHIBU_LATITUDE = 35.991681
CHICHIBU_LONGITUDE = 139.085475

OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
WEATHER_TIMEZONE = "Asia/Tokyo"
WEATHER_CACHE_TTL = timedelta(minutes=30)

# プロセス内キャッシュ。30分以内は同じ予報を再利用してAPIへの過剰アクセスを防ぐ。
_weather_cache = {
    "data": None,
    "expires_at": None,
}

JST = timezone(timedelta(hours=9))

# Open-Meteoが参照するWMO Weather interpretation codesに対応。
WMO_WEATHER = {
    0: ("晴れ", "☀️"),
    1: ("主に晴れ", "🌤️"),
    2: ("一部曇り", "⛅"),
    3: ("曇り", "☁️"),
    45: ("霧", "🌫️"),
    48: ("着氷性の霧", "🌫️"),
    51: ("弱い霧雨", "🌦️"),
    53: ("中程度の霧雨", "🌦️"),
    55: ("強い霧雨", "🌧️"),
    56: ("弱い着氷性の霧雨", "🌧️"),
    57: ("強い着氷性の霧雨", "🌧️"),
    61: ("弱い雨", "🌧️"),
    63: ("中程度の雨", "🌧️"),
    65: ("強い雨", "🌧️"),
    66: ("弱い着氷性の雨", "🌧️"),
    67: ("強い着氷性の雨", "🌧️"),
    71: ("弱い雪", "🌨️"),
    73: ("中程度の雪", "❄️"),
    75: ("強い雪", "❄️"),
    77: ("雪あられ", "🌨️"),
    80: ("弱いにわか雨", "🌦️"),
    81: ("中程度のにわか雨", "🌧️"),
    82: ("激しいにわか雨", "⛈️"),
    85: ("弱いにわか雪", "🌨️"),
    86: ("激しいにわか雪", "❄️"),
    95: ("雷雨", "⛈️"),
    96: ("雷雨・弱いひょう", "⛈️"),
    99: ("雷雨・強いひょう", "⛈️"),
}

WEEKDAYS_JA = "月火水木金土日"


def _weather_jst_today():
    """日本時間の今日をISO形式で返す。"""
    return datetime.now(JST).date().isoformat()


def _fetch_open_meteo(url):
    """Open-MeteoからJSONを取得し、HTTP/API異常は例外として扱う。"""
    request_obj = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ChichibuTravelPlanner/1.0",
            "Accept": "application/json",
        },
    )

    with urllib.request.urlopen(request_obj, timeout=8) as response:
        if getattr(response, "status", 200) != 200:
            raise RuntimeError(f"Open-Meteo HTTP status: {response.status}")
        payload = response.read().decode("utf-8")

    data = json.loads(payload)
    if isinstance(data, dict) and data.get("error") is True:
        raise RuntimeError(str(data.get("reason") or "Open-Meteo API error"))

    return data


def _build_weather_url(model=None):
    params = {
        "latitude": CHICHIBU_LATITUDE,
        "longitude": CHICHIBU_LONGITUDE,
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "timezone": WEATHER_TIMEZONE,
        "forecast_days": 7,
        "temperature_unit": "celsius",
    }
    if model:
        params["models"] = model
    return OPEN_METEO_FORECAST_URL + "?" + urlencode(params)


def _format_weather_value(value, suffix=""):
    if value is None:
        return "情報なし"
    try:
        number = float(value)
        if number.is_integer():
            return f"{int(number)}{suffix}"
        return f"{number:.1f}{suffix}"
    except (TypeError, ValueError):
        return "情報なし"


def _weather_code_info(code):
    try:
        normalized = int(code)
    except (TypeError, ValueError):
        return "情報なし", "☁️"
    return WMO_WEATHER.get(normalized, ("情報なし", "☁️"))


def _normalize_weather_response(data, model_label):
    daily = data.get("daily")
    if not isinstance(daily, dict):
        raise RuntimeError("Open-Meteo response does not contain daily data")

    dates = daily.get("time")
    if not isinstance(dates, list) or not dates:
        raise RuntimeError("Open-Meteo response does not contain daily dates")

    weather_codes = daily.get("weather_code") or []
    max_temps = daily.get("temperature_2m_max") or []
    min_temps = daily.get("temperature_2m_min") or []
    rain_probs = daily.get("precipitation_probability_max") or []

    forecasts = []

    # APIが返した日付だけを使用し、足りない日を架空の値で補完しない。
    for index, iso_date in enumerate(dates[:7]):
        try:
            current_date = datetime.strptime(str(iso_date), "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue

        weather_name, icon = _weather_code_info(
            weather_codes[index] if index < len(weather_codes) else None
        )

        forecasts.append(
            {
                "date": current_date.isoformat(),
                "date_label": f"{current_date.month}/{current_date.day}",
                "weekday": WEEKDAYS_JA[current_date.weekday()],
                "weather": weather_name,
                "icon": icon,
                "max_temperature": _format_weather_value(
                    max_temps[index] if index < len(max_temps) else None, "℃"
                ),
                "min_temperature": _format_weather_value(
                    min_temps[index] if index < len(min_temps) else None, "℃"
                ),
                "precipitation_probability": _format_weather_value(
                    rain_probs[index] if index < len(rain_probs) else None, "%"
                ),
            }
        )

    if not forecasts:
        raise RuntimeError("No usable daily forecast data")

    return {
        "forecasts": forecasts,
        "model": model_label,
        "latitude": CHICHIBU_LATITUDE,
        "longitude": CHICHIBU_LONGITUDE,
        "updated_at": datetime.now(JST).strftime("%Y-%m-%d %H:%M"),
    }


def get_weather_forecast():
    """
    秩父市の今日を含む7日間予報を取得する独立処理。

    優先:
      1. Open-Meteo Weather Forecast API + JMA Seamless
      2. JMAモデルが利用できない場合はOpen-Meteo Best Match

    どちらも失敗した場合は例外を投げず、呼び出し側でエラー表示できるよう
    (None, error_message) を返す。
    """
    now = datetime.now(JST)
    cached_data = _weather_cache.get("data")
    expires_at = _weather_cache.get("expires_at")

    if cached_data is not None and expires_at is not None and now < expires_at:
        return cached_data, None

    # JMAを優先。JMAで変数取得ができない場合だけBest Matchへフォールバック。
    try:
        jma_data = _fetch_open_meteo(_build_weather_url("jma_seamless"))
        normalized = _normalize_weather_response(jma_data, "JMA Seamless")
        _weather_cache["data"] = normalized
        _weather_cache["expires_at"] = now + WEATHER_CACHE_TTL
        return normalized, None
    except Exception as jma_error:
        last_error = jma_error

    try:
        fallback_data = _fetch_open_meteo(_build_weather_url("best_match"))
        normalized = _normalize_weather_response(fallback_data, "Open-Meteo Best Match")
        _weather_cache["data"] = normalized
        _weather_cache["expires_at"] = now + WEATHER_CACHE_TTL
        return normalized, None
    except Exception as fallback_error:
        # 外部APIのエラー内容を画面にそのまま出さず、安全なメッセージにする。
        _ = last_error
        _ = fallback_error
        return None, "現在、天気予報を取得できません。時間をおいて再度お試しください。"


# =========================================================
# メインページ
# =========================================================



# =========================================================
# AI旅行アシスタント
# =========================================================

def _extract_openai_text(response_data):
    """Responses API の返却値から本文だけを安全に取り出す。"""
    if not isinstance(response_data, dict):
        return ""

    # SDKの output_text 相当がレスポンスに含まれる場合に備える。
    direct = response_data.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    texts = []
    for output_item in response_data.get("output", []) or []:
        if not isinstance(output_item, dict):
            continue
        for content in output_item.get("content", []) or []:
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str) and text.strip():
                texts.append(text.strip())

    return "\n".join(texts).strip()


def _compact_ai_plan(plan):
    """AIへ渡す旅行プランを必要な範囲に絞る。"""
    if not isinstance(plan, dict):
        return {}

    def compact_place(item):
        if not isinstance(item, dict):
            return None
        return {
            "name": item.get("name"),
            "area": item.get("area"),
            "description": item.get("description"),
            "time": item.get("time"),
            "address": item.get("address"),
            "hours": item.get("hours"),
            "closed": item.get("closed"),
            "price": item.get("price"),
            "car_free": item.get("car_free"),
            "recommendation_reason": item.get("recommendation_reason"),
        }

    def compact_list(items, limit=8):
        result = []
        for item in (items or [])[:limit]:
            compacted = compact_place(item)
            if compacted:
                result.append(compacted)
        return result

    return {
        "travel_date": plan.get("travel_date"),
        "season": plan.get("season"),
        "age": plan.get("age"),
        "people": plan.get("people"),
        "member": plan.get("member"),
        "car": plan.get("car"),
        "days": plan.get("days"),
        "budget": plan.get("budget"),
        "purpose": plan.get("purpose"),
        "trip_style": plan.get("trip_style"),
        "trip_summary": plan.get("trip_summary"),
        "day1": compact_list(plan.get("day1")),
        "day2": compact_list(plan.get("day2")),
        "day3": compact_list(plan.get("day3")),
        "restaurants": compact_list(plan.get("recommended_restaurants"), 6),
        "hotel": compact_place(plan.get("hotel")),
        "other_hotels": compact_list(plan.get("other_hotels"), 5),
    }


@app.route("/api/ai-chat", methods=["POST"])
def ai_chat():
    """結果画面の旅行プランを前提にしたAI相談API。APIキーはサーバー側だけで保持する。"""
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return jsonify({
            "ok": False,
            "error": "AI機能を使うには、サーバー側にOPENAI_API_KEYを設定してください。"
        }), 503

    body = request.get_json(silent=True) or {}
    message = str(body.get("message") or "").strip()
    if not message:
        return jsonify({"ok": False, "error": "相談内容を入力してください。"}), 400
    if len(message) > 800:
        return jsonify({"ok": False, "error": "相談内容は800文字以内にしてください。"}), 400

    plan = _compact_ai_plan(body.get("plan"))
    conversation = body.get("conversation") if isinstance(body.get("conversation"), list) else []
    recent = []
    for item in conversation[-6:]:
        if not isinstance(item, dict):
            continue
        role = "user" if item.get("role") == "user" else "assistant"
        text = str(item.get("text") or "").strip()
        if text:
            recent.append({"role": role, "text": text[:600]})

    plan_json = json.dumps(plan, ensure_ascii=False, separators=(",", ":"))
    recent_json = json.dumps(recent, ensure_ascii=False, separators=(",", ":"))

    instructions = (
        "あなたは秩父旅行プランナーのAI旅行アシスタントです。"
        "回答は日本語で、短く分かりやすく、旅行者が次に何をすればよいか分かる形にしてください。"
        "必ず与えられた旅行プランの内容を優先し、存在しない営業時間、料金、混雑、運休、天気、移動時間などを推測しないでください。"
        "プラン内に根拠がない最新情報を尋ねられた場合は、確認が必要だと明記してください。"
        "ユーザーが『ここだけ変えたい』と相談した場合は、変更案を提案しても構いませんが、"
        "現在のサイト上のプラン自体を変更したとは言わないでください。"
        "通常は200〜350文字程度、長くても600文字以内を目安にしてください。"
    )

    user_input = (
        "現在の旅行プラン:\n" + plan_json +
        "\n\n直近の会話:\n" + recent_json +
        "\n\n今回の相談:\n" + message
    )

    model = os.environ.get("OPENAI_MODEL", "gpt-5.6-luna").strip() or "gpt-5.6-luna"
    payload = json.dumps({
        "model": model,
        "instructions": instructions,
        "input": user_input,
        "max_output_tokens": 700,
    }, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            error_body = json.loads(exc.read().decode("utf-8"))
            api_message = error_body.get("error", {}).get("message", "")
        except Exception:
            api_message = ""
        print("OpenAI API HTTP error:", exc.code, api_message)
        if exc.code == 401:
            message_text = "APIキーを確認してください。"
        elif exc.code == 429:
            message_text = "AI APIの利用上限またはレート制限に達しました。少し待ってから試してください。"
        else:
            message_text = "AIから回答を取得できませんでした。少し待ってからもう一度試してください。"
        return jsonify({"ok": False, "error": message_text}), 502
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print("OpenAI API connection error:", exc)
        return jsonify({
            "ok": False,
            "error": "AIへの接続に失敗しました。ネットワークを確認してもう一度試してください。"
        }), 502

    answer = _extract_openai_text(response_data)
    if not answer:
        return jsonify({
            "ok": False,
            "error": "AIの回答を読み取れませんでした。もう一度試してください。"
        }), 502

    return jsonify({"ok": True, "answer": answer})


# =========================================================
# TRIP BOOK
# =========================================================

@app.route("/trip-book")
def trip_book():
    return render_template("trip_book.html")


@app.route("/history")
def history():
    return render_template("history.html")

@app.route("/favorites")
def favorites():
    return render_template(
        "favorites.html",
        favorite_catalog=build_favorite_catalog(),
    )


# =========================================================
# スタートページ
# =========================================================

@app.route("/")
def start():
    return render_template(
        "start.html"
    )


# =========================================================
# おすすめプラン入力ページ
# =========================================================

@app.route("/recommend")
def index():
    weather_data, weather_error = get_weather_forecast()

    weather_forecast = (
        weather_data.get("forecasts", [])
        if weather_data
        else []
    )

    weather_model = (
        weather_data.get("model", "")
        if weather_data
        else ""
    )

    return render_template(
        "index.html",
        weather_forecast=weather_forecast,
        weather_error=weather_error,
        weather_model=weather_model,
        today_jst=_weather_jst_today(),
    )


# =========================================================
# 自分で旅行プランを作る
# =========================================================

@app.route("/manual-plan")
def manual_plan():

    return render_template(
        "manual_plan.html",

        manual_catalog=
            build_favorite_catalog(),

        today_jst=
            _weather_jst_today(),
    )


# =========================================================
# 自分で作った旅行プランの確認画面
# =========================================================

@app.route("/manual-plan/view")
def manual_plan_view():
    return render_template(
        "manual_plan_view.html"
    )

# =========================================================
# 結果ページ
# =========================================================

@app.route("/result", methods=["POST"])
def result():
    try:
        age = int(request.form.get("age", 20))
        gender = request.form.get("gender", "その他")
        people = int(request.form.get("people", 2))
        member = request.form.get("member", "友人")
        car = request.form.get("car", "なし")
        purpose = request.form.getlist("purpose")
        budget = int(request.form.get("budget", 20000))
        days = request.form.get("days", "1泊2日")
        travel_date = request.form.get("travel_date", "").strip()
    except (ValueError, TypeError):
        return "入力内容に問題があります。最初からやり直してください。"

    if not purpose:
        purpose = ["自然"]

    # HTMLのmin属性だけに依存せず、サーバー側でも過去の日付を旅行日として扱わない。
    # 7日先などの上限は設けず、未来の日付はすべて受け付ける。
    today_jst = _weather_jst_today()
    if travel_date and travel_date < today_jst:
        travel_date = ""

    # Step 2: 旅行予定日から季節だけを判定する。
    # この段階ではまだ推薦スコアには反映せず、Step 3で利用する。
    season = get_season_from_date(travel_date)

    recommendation_seed = make_recommendation_seed(
        age, gender, people, member, car, days, budget, purpose, travel_date
    )

    # 条件から作る推薦スコアは維持したまま、同一条件での再検索時だけ
    # 候補プール内の選択を変えるためのリクエスト単位nonce。
    # 条件に合わない施設をランダムで混ぜる用途には使わない。
    request_nonce = int.from_bytes(os.urandom(8), "big")

    trip_style = get_trip_style(member, purpose, age)

    # =====================================================
    # グルメ推薦
    # =====================================================

    restaurant_scores = []

    for restaurant in restaurants:
        score, reasons = calculate_restaurant_score(
            restaurant, member, purpose, car, people, budget, age, days, gender
        )
        restaurant_scores.append({
            "score": score,
            "restaurant": restaurant,
            "reasons": reasons,
            "name": restaurant.get("name", ""),
            "area": restaurant.get("area", ""),
            "genre": restaurant.get("genre", [])
        })

    restaurant_scores.sort(key=lambda x: x["score"], reverse=True)

    recommended_restaurants = []

    # 旅行の目的に関係なく、旅程中の食事候補は必ず提示する。
    # 「グルメ」を選んだ場合はスコアが大きく上がるため、
    # よりグルメ重視の店舗が選ばれる。
    restaurant_target = 4 if days == "1泊2日" else 6

    selected_restaurants = diverse_select(
        restaurant_scores,
        restaurant_target,
        recommendation_seed + 101,
        key_name="name",
        group_names=["area", "genre"],
        request_nonce=request_nonce
    )

    for item in selected_restaurants:
        restaurant = attach_map_data(item["restaurant"])
        restaurant["score"] = item["score"]
        restaurant["reasons"] = item["reasons"]
        recommended_restaurants.append(restaurant)

    # =====================================================
    # 観光地推薦
    # =====================================================

    spot_scores = []

    for spot in spots:
        score, reasons = calculate_spot_score(
            spot, member, purpose, car, age, people, days, budget, gender,
            season=season, travel_date=travel_date
        )
        spot_scores.append({
            "score": score,
            "spot": spot,
            "reasons": reasons,
            "name": spot.get("name", ""),
            "area": spot.get("area", ""),
            "type": spot.get("type", ""),
            "season": spot.get("season"),
            "best_season": spot.get("best_season"),
            "seasonal_operation": spot.get("seasonal_operation")
        })

    spot_scores.sort(key=lambda x: x["score"], reverse=True)

    spot_target = 3 if days == "1泊2日" else 5

    selected_spots = diverse_select(
        spot_scores,
        spot_target,
        recommendation_seed + 202,
        key_name="name",
        group_names=["area", "type"],
        request_nonce=request_nonce
    )

    recommended_spots = []

    for item in selected_spots:
        spot = attach_map_data(item["spot"])
        spot["score"] = item["score"]
        spot["reasons"] = item["reasons"]
        spot["recommendation_reason"] = build_recommendation_reason(
            spot, item["reasons"], age, people, member, car, days, budget, purpose,
            travel_date, season, category="spot"
        )
        recommended_spots.append(spot)

    # =====================================================
    # 宿泊施設推薦
    # =====================================================

    hotel_scores = []

    for hotel in hotels:
        score, reasons = calculate_hotel_score(
            hotel, member, purpose, budget, people, age, car, days, gender,
            season=season, travel_date=travel_date
        )
        hotel_scores.append({
            "score": score,
            "hotel": hotel,
            "reasons": reasons,
            "name": hotel.get("name", ""),
            "type": hotel.get("type", "")
        })

    # 宿泊も「最高点の1件を固定」ではなく、十分に条件に合う候補の中から
    # リクエストごとに1件を選ぶ。スコア差が大きい宿は候補から外す。
    selected_hotels = diverse_select(
        hotel_scores,
        1,
        recommendation_seed + 303,
        key_name="name",
        group_names=["type"],
        request_nonce=request_nonce
    )

    if not selected_hotels:
        selected_hotels = sorted(hotel_scores, key=lambda x: x["score"], reverse=True)[:1]

    chosen_hotel_item = selected_hotels[0]
    recommended_hotel = attach_map_data(chosen_hotel_item["hotel"])
    recommended_hotel["reasons"] = chosen_hotel_item["reasons"]
    recommended_hotel["recommendation_reason"] = build_recommendation_reason(
        recommended_hotel, chosen_hotel_item["reasons"], age, people, member, car, days,
        budget, purpose, travel_date, season, category="hotel"
    )

    # 結果画面の「その他の宿」は、選ばれた宿を除いた残りをスコア順で表示。
    other_hotels = [
        attach_map_data(item["hotel"]) for item in sorted(
            hotel_scores,
            key=lambda x: x["score"],
            reverse=True
        )
        if item["hotel"].get("name") != recommended_hotel.get("name")
    ]

    # =====================================================
    # 日程作成
    # =====================================================

    if days == "1泊2日":
        day1 = recommended_spots[:2]
        day2 = recommended_spots[2:]
        day3 = []
    else:
        day1 = recommended_spots[:2]
        day2 = recommended_spots[2:4]
        day3 = recommended_spots[4:]

    sightseeing_time = sum(spot["time"] for spot in recommended_spots)

    nights = 1 if days == "1泊2日" else 2
    total_hotel_price = recommended_hotel["price"] * people * nights
    total_budget = budget * people

    if total_budget > 0:
        budget_ratio = round(total_hotel_price / total_budget * 100)
    else:
        budget_ratio = 0

    if recommended_hotel["price"] <= budget:
        budget_status = "予算内に収まりやすい宿です"
    else:
        budget_status = "予算を少し超える可能性があります"

    # =====================================================
    # 旅行の特徴
    # =====================================================

    feature_text = []

    if "自然" in purpose:
        feature_text.append("秩父の自然を満喫")
    if "温泉" in purpose:
        feature_text.append("温泉でゆったり")
    if "グルメ" in purpose:
        feature_text.append("秩父グルメを堪能")
    if "歴史" in purpose:
        feature_text.append("歴史・文化を体験")

    if car == "なし":
        feature_text.append("公共交通機関を活用")
    else:
        feature_text.append("車移動で効率よく観光")

    # =====================================================
    # TRIP SUMMARY
    # =====================================================

    trip_summary = _build_trip_summary(
        age=age,
        people=people,
        member=member,
        car=car,
        days=days,
        budget=budget,
        purpose=purpose,
        travel_date=travel_date,
        season=season,
        recommended_spots=recommended_spots,
        recommended_hotel=recommended_hotel,
        recommended_restaurants=recommended_restaurants,
        sightseeing_time=sightseeing_time,
    )


    # 保存した時点の完成プランをそのまま再現できるよう、
    # 結果画面で使ったデータをクライアントへ渡す。
    history_payload = {
        "schemaVersion": 1,
        "age": age,
        "gender": gender,
        "people": people,
        "member": member,
        "car": car,
        "purpose": purpose,
        "budget": budget,
        "days": days,
        "travel_date": travel_date,
        "season": season,
        "trip_style": trip_style,
        "feature_text": feature_text,
        "day1": day1,
        "day2": day2,
        "day3": day3,
        "recommended_restaurants": recommended_restaurants,
        "hotel": recommended_hotel,
        "other_hotels": other_hotels,
        "total_price": total_hotel_price,
        "total_budget": total_budget,
        "budget_ratio": budget_ratio,
        "budget_status": budget_status,
        "sightseeing_time": sightseeing_time,
        "trip_summary": trip_summary,
    }

    # =====================================================
    # Google Maps用URL
    # =====================================================

    map_query = recommended_hotel.get("map_query", "")

    return render_template(
        "result.html",
        age=age,
        gender=gender,
        people=people,
        member=member,
        car=car,
        purpose=purpose,
        budget=budget,
        days=days,
        travel_date=travel_date,
        season=season,
        day1=day1,
        day2=day2,
        day3=day3,
        hotel=recommended_hotel,
        other_hotels=other_hotels,
        total_price=total_hotel_price,
        trip_style=trip_style,
        trip_summary=trip_summary,
        sightseeing_time=sightseeing_time,
        total_budget=total_budget,
        budget_ratio=budget_ratio,
        budget_status=budget_status,
        feature_text=feature_text,
        recommended_spots=recommended_spots,
        recommended_restaurants=recommended_restaurants,
        map_query=map_query,
        history_payload=history_payload
    )


# =========================================================
# Flask起動
# =========================================================

if __name__ == "__main__":
    app.run(debug=True)
