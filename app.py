from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlencode
import hashlib
import itertools
import urllib.error
import urllib.request
import json
import os
import random
import re
import time

try:
    import psycopg
except ImportError:
    psycopg = None

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

ARRIVAL_METHOD_LABELS = {
    "花園IC": "車（関越道・花園IC）",
    "芦ヶ久保駅": "車（国道299号・芦ヶ久保）"
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESTAURANT_FILE = os.path.join(BASE_DIR, "data", "restaurants.json")
FACILITY_MASTER_FILE = os.path.join(BASE_DIR, "data", "facilities_master.json")
ROUTE_LOCATION_FILE = os.path.join(BASE_DIR, "data", "route_locations.json")
ROUTE_MATRIX_FILE = os.path.join(BASE_DIR, "data", "route_matrix.json")

KAWAGOE_RESTAURANT_FILE = os.path.join(BASE_DIR, "data", "kawagoe_restaurants.json")
KAWAGOE_FACILITY_MASTER_FILE = os.path.join(BASE_DIR, "data", "kawagoe_facilities_master.json")
KAWAGOE_ROUTE_LOCATION_FILE = os.path.join(BASE_DIR, "data", "kawagoe_route_locations.json")
KAWAGOE_ROUTE_MATRIX_FILE = os.path.join(BASE_DIR, "data", "kawagoe_route_matrix.json")

ACTIVE_REGION_CODE = "chichibu"
ACTIVE_REGION_NAME = "秩父"
ACTIVE_REGION_NAME_EN = "CHICHIBU"
ACTIVE_WEATHER_LATITUDE = 35.991681
ACTIVE_WEATHER_LONGITUDE = 139.085475


# =========================================================
# 車用ローカル事前計算ルート
# =========================================================

try:
    with open(
        ROUTE_MATRIX_FILE,
        "r",
        encoding="utf-8"
    ) as f:
        route_matrix_data = json.load(f)

    route_matrix_routes = route_matrix_data.get(
        "routes",
        {}
    )

    if not isinstance(route_matrix_routes, dict):
        route_matrix_routes = {}

    print(
        "[LOCAL ROUTE MATRIX]",
        "locations =",
        route_matrix_data.get("location_count"),
        "| pairs =",
        route_matrix_data.get("pair_count"),
        "| available =",
        route_matrix_data.get("available_pair_count")
    )

except (
    OSError,
    json.JSONDecodeError,
    TypeError
) as exc:
    print(
        "[LOCAL ROUTE MATRIX ERROR]",
        exc
    )
    route_matrix_data = {}
    route_matrix_routes = {}


with open(RESTAURANT_FILE, "r", encoding="utf-8") as f:
    restaurant_data = json.load(f)

restaurants = restaurant_data.get("restaurants", [])


# 41施設マスターは推薦条件（特に季節情報）の参照専用に利用する。
# 既存の30観光スポット＋11宿泊施設のハードコードデータ自体は削除・置換しない。
try:

    with open(
        FACILITY_MASTER_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        facility_master_data = json.load(f)

    facility_master = {

        item.get("name", ""):
            item

        for item in
            facility_master_data.get(
                "facilities",
                []
            )

        if item.get("name")

    }

except (
    OSError,
    json.JSONDecodeError,
    TypeError
):

    facility_master = {}


# =========================================================
# ルート計算専用の到着地点データ
# =========================================================

try:
    with open(
        ROUTE_LOCATION_FILE,
        "r",
        encoding="utf-8"
    ) as f:
        route_location_data = json.load(f)

    route_locations = route_location_data.get(
        "route_locations",
        {}
    )

    if not isinstance(route_locations, dict):
        route_locations = {}

except (
    OSError,
    json.JSONDecodeError,
    TypeError
):
    route_locations = {}



# =========================================================
# 観光スポットデータ（既存30件を維持）
# =========================================================

spots = [

    {
        'name': '長瀞・岩畳',
        'tags': [
            '自然',
            'デート',
            '家族',
            '友人',
            'グルメ'
        ],
        'car': False,
        'time': 3,
        'area': '長瀞',
        'type': 'nature',
        'description':
            '荒川沿いに広がる国の名勝・天然記念物の岩畳。'
            '散策や長瀞観光の中心として楽しめます。',
        'difficulty': 'easy',
        'url':
            'https://www.nagatoro.gr.jp/'
    },

    {
        'name':
            '長瀞ラインくだり',

        'tags': [
            '自然',
            'デート',
            '家族',
            '友人'
        ],

        'car':
            False,

        'time':
            2,

        'area':
            '長瀞',

        'type':
            'nature',

        'description':
            '荒川の渓谷を和舟で下る'
            '長瀞の代表的なアクティビティです。',

        'difficulty':
            'easy',

        'url':
            'https://www.chichibu-railway.co.jp/nagatoro/'
    },


    {
        'name':
            '宝登山',

        'tags': [
            '自然',
            'デート',
            '家族',
            '友人'
        ],

        'car':
            True,

        'time':
            3,

        'area':
            '長瀞',

        'type':
            'nature',

        'description':
            '山頂から長瀞・秩父の山々を望める人気の山。'
            'ロープウェイでも登れます。',

        'difficulty':
            'medium',

        'url':
            'https://www.chichibuji.gr.jp/spot/spot-syousai02/'
    },


    {
        'name':
            '寶登山神社',

        'tags': [
            '歴史',
            'デート',
            '家族',
            '友人'
        ],

        'car':
            True,

        'time':
            2,

        'area':
            '長瀞',

        'type':
            'history',

        'description':
            '秩父三社の一つ。'
            '宝登山の麓に鎮座する歴史ある神社です。',

        'difficulty':
            'easy',

        'url':
            'https://www.hodosan-jinja.or.jp/'
    },


    {
        'name':
            '宝登山ロープウェイ',

        'tags': [
            '自然',
            'デート',
            '家族',
            '友人'
        ],

        'car':
            True,

        'time':
            2,

        'area':
            '長瀞',

        'type':
            'nature',

        'description':
            '宝登山の山麓と山頂を結ぶロープウェイ。'
            '山頂観光へのアクセスにも便利です。',

        'difficulty':
            'easy',

        'url':
            'https://hodosan-ropeway.co.jp/'
    },


    {
        'name':
            '埼玉県立自然の博物館',

        'tags': [
            '自然',
            '家族',
            '友人',
            '歴史'
        ],

        'car':
            True,

        'time':
            2,

        'area':
            '長瀞',

        'type':
            'history',

        'description':
            '埼玉県の自然や地質、'
            '生き物について学べる博物館です。',

        'difficulty':
            'easy',

        'url':
            'https://shizen.spec.ed.jp/'
    },


    {
        'name':
            '月の石もみじ公園',

        'tags': [
            '自然',
            'デート',
            '家族'
        ],

        'car':
            True,

        'time':
            2,

        'area':
            '長瀞',

        'type':
            'nature',

        'description':
            '紅葉の名所として知られる長瀞の公園。'
            '季節の景観を楽しめます。',

        'difficulty':
            'easy',

        'url':
            'https://www.nagatoro.gr.jp/'
    },


    {
        'name':
            '金石水管橋',

        'tags': [
            '自然',
            'デート',
            '友人'
        ],

        'car':
            True,

        'time':
            1,

        'area':
            '長瀞',

        'type':
            'nature',

        'description':
            '荒川を渡る橋の上から'
            '渓谷や周辺の景色を楽しめるスポットです。',

        'difficulty':
            'easy',

        'url':
            'https://www.nagatoro.gr.jp/'
    },


    {
        'name':
            '秩父神社',

        'tags': [
            '歴史',
            'デート',
            '家族',
            '友人',
            'グルメ'
        ],

        'car':
            False,

        'time':
            2,

        'area':
            '秩父市街',

        'type':
            'history',

        'description':
            '秩父地方の総社。'
            '社殿の彫刻や門前の街歩きも楽しめます。',

        'difficulty':
            'easy',

        'url':
            'https://www.chichibuji.gr.jp/spot/spot-syousai01/'
    },


    {
        'name':
            '三峯神社',

        'tags': [
            '自然',
            '歴史',
            'デート',
            '家族'
        ],

        'car':
            True,

        'time':
            5,

        'area':
            '奥秩父',

        'type':
            'nature',

        'description':
            '標高約1100mの三峰山に鎮座する秩父三社の一つ。'
            '豊かな山の自然も魅力です。',

        'difficulty':
            'hard',

        'url':
            'https://www.chichibuji.gr.jp/spot/spot-syousai03/'
    },


    {
        'name':
            '羊山公園',

        'tags': [
            '自然',
            'デート',
            '家族'
        ],

        'car':
            True,

        'time':
            2,

        'area':
            '秩父市街',

        'type':
            'nature',

        'description':
            '芝桜の丘や見晴らしの丘などがあり、'
            '季節の花と秩父の景色を楽しめます。',

        'difficulty':
            'easy',

        'url':
            'https://www.chichibuji.gr.jp/spot/spot-syousai10/'
    },


    {
        'name':
            '秩父ミューズパーク',

        'tags': [
            '自然',
            '家族',
            '友人',
            'デート'
        ],

        'car':
            True,

        'time':
            3,

        'area':
            '秩父',

        'type':
            'nature',

        'description':
            '秩父市と小鹿野町にまたがる広大な公園。'
            '展望台や遊具、季節の花などを楽しめます。',

        'difficulty':
            'easy',

        'url':
            'https://www.chichibuji.gr.jp/spot/spot-syousai11/'
    },


    {
        'name':
            '旅立ちの丘',

        'tags': [
            '自然',
            'デート',
            '家族',
            '友人'
        ],

        'car':
            True,

        'time':
            1,

        'area':
            '秩父ミューズパーク',

        'type':
            'nature',

        'description':
            '「旅立ちの日に」を記念した展望スポット。'
            '秩父の景色を眺められます。',

        'difficulty':
            'easy',

        'url':
            'https://navi.city.chichibu.lg.jp/p_sightseeingr/884/'
    },


    {
        'name':
            '美の山公園',

        'tags': [
            '自然',
            'デート',
            '家族',
            '友人'
        ],

        'car':
            True,

        'time':
            2,

        'area':
            '皆野・秩父',

        'type':
            'nature',

        'description':
            '蓑山山頂周辺に広がる公園。'
            '桜や雲海、秩父盆地の眺望で知られます。',

        'difficulty':
            'medium',

        'url':
            'https://www.chichibuji.gr.jp/spot/spot-syousai12/'
    },


    {
        'name':
            '橋立鍾乳洞',

        'tags': [
            '自然',
            '家族',
            '友人'
        ],

        'car':
            True,

        'time':
            2,

        'area':
            '影森',

        'type':
            'nature',

        'description':
            '武甲山の麓にある鍾乳洞。'
            '自然の地形を体験できる観光スポットです。',

        'difficulty':
            'medium',

        'url':
            'https://www.chichibuji.gr.jp/spot/'
    },


    {
        'name':
            '聖神社',

        'tags': [
            '歴史',
            'デート',
            '家族',
            '友人'
        ],

        'car':
            True,

        'time':
            1,

        'area':
            '黒谷',

        'type':
            'history',

        'description':
            '和銅ゆかりの神社で、'
            '金運の神様・銭神様として親しまれています。',

        'difficulty':
            'easy',

        'url':
            'https://www.chichibuji.gr.jp/spot/spot-syousai95/'
    },


    {
        'name':
            '秩父まつり会館',

        'tags': [
            '歴史',
            '家族',
            '友人',
            'グルメ'
        ],

        'car':
            False,

        'time':
            2,

        'area':
            '秩父市街',

        'type':
            'history',

        'description':
            '秩父夜祭の屋台・笠鉾などを展示し、'
            '秩父の祭り文化を体感できる施設です。',

        'difficulty':
            'easy',

        'url':
            'https://www.chichibu-matsuri.jp/'
    },


    {
        'name':
            'ほっとすぽっと秩父館',

        'tags': [
            '歴史',
            'デート',
            '家族',
            '友人',
            'グルメ'
        ],

        'car':
            False,

        'time':
            1,

        'area':
            '秩父市街',

        'type':
            'history',

        'description':
            '明治時代初期の商人宿を活用した、'
            '街歩きの立ち寄りスポットです。',

        'difficulty':
            'easy',

        'url':
            'https://navi.city.chichibu.lg.jp/p_sightseeingr/861/'
    },


    {
        'name':
            'ちちぶ銘仙館',

        'tags': [
            '歴史',
            '家族',
            '友人'
        ],

        'car':
            False,

        'time':
            2,

        'area':
            '秩父市街',

        'type':
            'history',

        'description':
            '秩父銘仙の歴史や染織を紹介し、'
            '織物文化に触れられる施設です。',

        'difficulty':
            'easy',

        'url':
            'https://www.meisenkan.com/'
    },


    {
        'name':
            '武甲山資料館',

        'tags': [
            '自然',
            '歴史',
            '家族',
            '友人'
        ],

        'car':
            True,

        'time':
            1,

        'area':
            '羊山公園',

        'type':
            'history',

        'description':
            '秩父のシンボル武甲山の地質や植物、'
            '歴史について学べる資料館です。',

        'difficulty':
            'easy',

        'url':
            'https://www.bukohzan.jp/'
    },


    {
        'name':
            '秩父ふるさと館',

        'tags': [
            '歴史',
            'グルメ',
            'デート',
            '友人'
        ],

        'car':
            False,

        'time':
            1,

        'area':
            '秩父市街',

        'type':
            'history',

        'description':
            '大正時代の銘仙問屋の主屋を活用した観光拠点。'
            '物産や郷土料理も楽しめます。',

        'difficulty':
            'easy',

        'url':
            'https://navi.city.chichibu.lg.jp/spot/'
    },


    {
        'name':
            '和銅遺跡',

        'tags': [
            '歴史',
            '自然',
            '家族',
            '友人'
        ],

        'car':
            True,

        'time':
            2,

        'area':
            '黒谷',

        'type':
            'history',

        'description':
            '日本最初の流通貨幣とされる'
            '和同開珎にゆかりのある歴史スポットです。',

        'difficulty':
            'medium',

        'url':
            'https://navi.city.chichibu.lg.jp/spot/'
    },


    {
        'name':
            '清雲寺',

        'tags': [
            '自然',
            '歴史',
            'デート',
            '家族'
        ],

        'car':
            True,

        'time':
            1,

        'area':
            '荒川',

        'type':
            'history',

        'description':
            'しだれ桜で知られる荒川地区の寺院。'
            '春の花の名所としても親しまれています。',

        'difficulty':
            'easy',

        'url':
            'https://navi.city.chichibu.lg.jp/spot/'
    },


    {
        'name':
            '秩父華厳の滝',

        'tags': [
            '自然',
            'デート',
            '家族',
            '友人'
        ],

        'car':
            True,

        'time':
            2,

        'area':
            '皆野',

        'type':
            'nature',

        'description':
            '秩父郡皆野町にある滝。'
            '周囲の自然とあわせて楽しめる景勝地です。',

        'difficulty':
            'medium',

        'url':
            'https://www.chichibuji.gr.jp/spot/'
    },


    {
        'name':
            '三十槌の氷柱',

        'tags': [
            '自然',
            'デート',
            '家族',
            '友人'
        ],

        'car':
            True,

        'time':
            2,

        'area':
            '大滝',

        'type':
            'nature',

        'description':
            '岩清水が凍ってできる冬の名所。'
            '毎年1月上旬から2月下旬頃に公開される'
            '季節限定スポットです。',

        'difficulty':
            'medium',

        'url':
            'https://navi.city.chichibu.lg.jp/p_flower/1403/'
    },


    {
        'name':
            '小松沢レジャー農園',

        'tags': [
            '自然',
            '家族',
            '友人',
            'グルメ'
        ],

        'car':
            True,

        'time':
            3,

        'area':
            '横瀬',

        'type':
            'nature',

        'description':
            'いちご狩り、ぶどう狩り、'
            'しいたけ狩りなどを楽しめる観光農園です。',

        'difficulty':
            'easy',

        'url':
            'https://www.chichibuji.gr.jp/spot/spot-syousai46/'
    },


    {
        'name':
            '秩父フルーツファーム',

        'tags': [
            '自然',
            '家族',
            '友人',
            'グルメ'
        ],

        'car':
            True,

        'time':
            2,

        'area':
            '秩父',

        'type':
            'nature',

        'description':
            'いちご狩りやぶどう狩りなど、'
            '季節の果物を楽しめる観光農園です。',

        'difficulty':
            'easy',

        'url':
            'https://www.chichibuji.gr.jp/spot/spot-syousai48/'
    },


    {
        'name':
            '道の駅ちちぶ',

        'tags': [
            'グルメ',
            '家族',
            '友人'
        ],

        'car':
            True,

        'time':
            1,

        'area':
            '秩父市街',

        'type':
            'nature',

        'description':
            '秩父のお土産や特産品を探せる道の駅。'
            '旅行中の休憩にも便利です。',

        'difficulty':
            'easy',

        'url':
            'https://www.chichibuji.gr.jp/spot/spot-syousai100/'
    },


    {
        'name':
            '秩父温泉 満願の湯',

        'tags': [
            '温泉',
            'デート',
            '家族',
            '友人'
        ],

        'car':
            True,

        'time':
            3,

        'area':
            '皆野',

        'type':
            'nature',

        'description':
            '秩父温泉を楽しめる日帰り温泉施設。'
            '自然の中でゆっくり過ごせます。',

        'difficulty':
            'easy',

        'url':
            'https://www.chichibuji.gr.jp/spot/spot-syousai116/'
    },


    {
        'name':
            '大滝温泉',

        'tags': [
            '温泉',
            '自然',
            '家族',
            '友人'
        ],

        'car':
            True,

        'time':
            2,

        'area':
            '大滝',

        'type':
            'nature',

        'description':
            '道の駅大滝温泉内にある日帰り温泉。'
            '奥秩父観光と組み合わせやすい施設です。',

        'difficulty':
            'easy',

        'url':
            'https://navi.city.chichibu.lg.jp/spot/'
    }

]


# =========================================================
# 宿泊施設データ（既存11件を維持）
# =========================================================

hotels = [

    {
        'name':
            '和銅鉱泉 ゆの宿 和どう',

        'tags': [
            '温泉',
            'デート',
            '家族',
            '自然',
            '歴史'
        ],

        'price':
            18000,

        'type':
            'onsen',

        'description':
            '和銅鉱泉の温泉を楽しめる歴史ある宿。'
            'ゆっくり過ごしたい旅行におすすめです。',

        'quality':
            5,

        'url':
            'https://www.wadoh.co.jp/',

        'lat':
            35.999,

        'lng':
            139.027
    },


    {
        'name':
            '新木鉱泉旅館',

        'tags': [
            '温泉',
            'デート',
            '家族',
            '自然'
        ],

        'price':
            16000,

        'type':
            'onsen',

        'description':
            '江戸時代から続く秩父の温泉旅館。'
            '落ち着いた雰囲気で温泉旅行を楽しめます。',

        'quality':
            5,

        'url':
            'https://www.onsen-yado.net/',

        'lat':
            35.9827,

        'lng':
            139.0515
    },


    {
        'name':
            'NIPPONIA 秩父 門前町',

        'tags': [
            '歴史',
            'デート',
            'グルメ',
            '友人'
        ],

        'price':
            20000,

        'type':
            'city',

        'description':
            '秩父の歴史的な街並みを活かした分散型ホテル。'
            '街歩きやグルメとの相性が良い宿です。',

        'quality':
            5,

        'url':
            'https://nipponia-chichibu.jp/',

        'lat':
            35.9968,

        'lng':
            139.0858
    },


    {
        'name':
            'ホテルルートインGrand秩父',

        'tags': [
            '温泉',
            '友人',
            '家族',
            'グルメ'
        ],

        'price':
            12000,

        'type':
            'city',

        'description':
            '秩父市街での観光拠点として利用しやすいホテル。'
            '大浴場もあります。',

        'quality':
            4,

        'url':
            'https://www.route-inn.co.jp/hotel_list/saitama/index_hotel_id_714/',

        'lat':
            35.9997,

        'lng':
            139.086
    },


    {
        'name':
            'ホテルルートイン西武秩父駅前',

        'tags': [
            '友人',
            '家族',
            'グルメ',
            '歴史'
        ],

        'price':
            11000,

        'type':
            'city',

        'description':
            '西武秩父駅から近く、'
            '秩父市街の観光拠点として便利なホテルです。',

        'quality':
            4,

        'url':
            'https://www.route-inn.co.jp/hotel_list/saitama/index_hotel_id_60/',

        'lat':
            35.9897,

        'lng':
            139.084
    },


    {
        'name':
            'アパホテル〈埼玉秩父駅前〉',

        'tags': [
            '友人',
            'グルメ',
            '歴史'
        ],

        'price':
            10000,

        'type':
            'city',

        'description':
            '秩父駅周辺での観光や市街地散策に便利なホテルです。',

        'quality':
            4,

        'url':
            'https://www.apahotel.com/hotel/syutoken/saitama/saitama-chichibu-ekimae/',

        'lat':
            35.9977,

        'lng':
            139.0862
    },


    {
        'name':
            'ホテル美やま',

        'tags': [
            '温泉',
            '自然',
            '家族',
            'デート'
        ],

        'price':
            15000,

        'type':
            'onsen',

        'description':
            '秩父の自然を感じながら温泉を楽しめる宿。'
            'ゆったりした旅行に向いています。',

        'quality':
            5,

        'url':
            'https://www.miyama-onsen.com/',

        'lat':
            35.9904,

        'lng':
            139.0342
    },


    {
        'name':
            '旅館 比与志',

        'tags': [
            '温泉',
            'デート',
            '歴史',
            '自然'
        ],

        'price':
            15000,

        'type':
            'onsen',

        'description':
            '西武秩父駅から徒歩圏内。'
            '落ち着いた雰囲気で秩父観光を楽しめる旅館です。',

        'quality':
            5,

        'url':
            'http://www.hiyoshi-ryokan.com/',

        'lat':
            35.9869,

        'lng':
            139.0794
    },


    {
        'name':
            'ちちぶ温泉 はなのや',

        'tags': [
            '温泉',
            'デート',
            '家族',
            '自然'
        ],

        'price':
            17000,

        'type':
            'onsen',

        'description':
            '秩父の自然に囲まれた温泉宿。'
            '温泉を中心にゆっくり過ごしたい人におすすめです。',

        'quality':
            5,

        'url':
            'https://chichibu-resort.com/hananoya/',

        'lat':
            35.985,

        'lng':
            139.0
    },


    {
        'name':
            'PICA秩父',

        'tags': [
            '自然',
            '家族',
            '友人',
            'デート'
        ],

        'price':
            13000,

        'type':
            'nature',

        'description':
            '秩父ミューズパーク内にあるアウトドア宿泊施設。'
            '自然を満喫したい旅行におすすめです。',

        'quality':
            4,

        'url':
            'https://www.pica-resort.jp/chichibu/',

        'lat':
            35.991,

        'lng':
            139.019
    },


    {
        'name':
            '御宿 竹取物語',

        'tags': [
            '温泉',
            'デート',
            '自然'
        ],

        'price':
            22000,

        'type':
            'onsen',

        'description':
            '自然に囲まれた落ち着いた宿。'
            '特別感のある旅行や温泉旅行に向いています。',

        'quality':
            5,

        'url':
            'https://www.oyadotaketori.com/',

        'lat':
            35.983,

        'lng':
            139.017
    }

]


# =========================================================
# 旅行タイプ判定
# =========================================================



def format_parking_for_display(value):
    """
    駐車場情報を必ず人間向け文字列へ変換する。

    dict:
      {"available": True, "capacity": "50台", "fee": "無料", "notes": ""}
      -> "あり／50台／無料"

    「公式情報なし」が複数項目に重複する場合は1回だけ表示。
    """
    if value is None:
        return "情報なし"

    if isinstance(value, str):
        text = value.strip()
        return text if text else "情報なし"

    if isinstance(value, bool):
        return "あり" if value else "なし"

    if isinstance(value, dict):
        parts = []

        available = value.get("available")
        capacity = value.get("capacity")
        fee = value.get("fee")
        notes = value.get("notes")

        def add_text(raw):
            if raw is None:
                return

            if isinstance(raw, bool):
                text = "あり" if raw else "なし"
            else:
                text = str(raw).strip()

            if not text:
                return

            # Python辞書文字列の混入を防ぐ
            if text.startswith("{") and text.endswith("}"):
                return

            if text not in parts:
                parts.append(text)

        add_text(available)
        add_text(capacity)
        add_text(fee)
        add_text(notes)

        # 「あり／公式情報なし」のような不自然表示を整理
        if "公式情報なし" in parts:
            useful = [
                p for p in parts
                if p not in {
                    "公式情報なし",
                    "情報なし"
                }
            ]

            if useful == ["あり"]:
                return "あり（詳細情報なし）"

            if useful:
                return "／".join(useful)

            return "公式情報なし"

        if parts:
            return "／".join(parts)

        return "情報なし"

    if isinstance(value, (list, tuple, set)):
        parts = []
        for raw in value:
            text = str(raw).strip()
            if text and text not in parts:
                parts.append(text)

        return "／".join(parts) if parts else "情報なし"

    text = str(value).strip()
    return text if text else "情報なし"


def normalize_place_for_display(item):
    """
    結果表示に使う施設dictを正規化。
    parkingは必ず文字列になる。
    """
    if not isinstance(item, dict):
        return item

    normalized = dict(item)

    normalized["parking"] = (
        format_parking_for_display(
            normalized.get("parking")
        )
    )

    return normalized


def get_trip_style(member, purpose, age):
    purpose_set = set(
        purpose
        or []
    )

    if ACTIVE_REGION_CODE == "kawagoe":

        if member == "一人":
            if "小江戸・町並み" in purpose_set:
                return "ひとりで巡る小江戸街歩き"
            if "歴史・文化" in purpose_set:
                return "ひとりでじっくり巡る歴史文化旅"
            if "食べ歩き・グルメ" in purpose_set:
                return "ひとり川越食べ歩き旅"
            if "自然・散策" in purpose_set:
                return "のんびり川越散策旅"
            return "自分のペースで楽しむ川越旅"

        if member == "デート":
            if "小江戸・町並み" in purpose_set:
                return "小江戸の町並みを巡る川越デート"
            if "食べ歩き・グルメ" in purpose_set:
                return "食べ歩きも楽しむ川越デート"
            if "歴史・文化" in purpose_set:
                return "歴史と文化を巡る川越デート"
            if "自然・散策" in purpose_set:
                return "のんびり歩く川越デート"
            return "小江戸を楽しむ川越デート"

        if member == "家族":
            if "歴史・文化" in purpose_set:
                return "家族で学んで楽しむ川越歴史旅"
            if "食べ歩き・グルメ" in purpose_set:
                return "家族で楽しむ川越グルメ旅"
            if "小江戸・町並み" in purpose_set:
                return "家族で巡る小江戸川越旅"
            if "自然・散策" in purpose_set:
                return "家族でのんびり川越散策"
            return "家族みんなで楽しむ川越旅"

        if member == "友人":
            if "食べ歩き・グルメ" in purpose_set:
                return "友達と楽しむ川越食べ歩き旅"
            if "小江戸・町並み" in purpose_set:
                return "友達と巡る小江戸街歩き"
            if "歴史・文化" in purpose_set:
                return "友達と巡る川越歴史文化旅"
            if "自然・散策" in purpose_set:
                return "友達とのんびり川越散策"
            return "友達と楽しむ川越満喫旅"

        if age <= 20:
            return "学生向け小江戸川越旅"
        if age <= 30:
            return "街歩きで楽しむ川越旅"
        if age <= 40:
            return "大人の小江戸川越旅"

        return "ゆったり楽しむ川越旅"

    # 秩父は既存仕様を維持
    if member == "一人":
        if "自然" in purpose_set:
            return "ひとりで楽しむ自然旅"
        if "温泉" in purpose_set:
            return "ひとり温泉旅"
        if "グルメ" in purpose_set:
            return "ひとりグルメ旅"
        if "歴史" in purpose_set:
            return "ひとり歴史旅"
        return "自分のペースで楽しむ秩父旅"

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
    既存の推薦用データを壊さず、
    41施設マスターの季節情報を付加する。

    地図処理でもマスターの住所・座標を
    参照できるようにする。

    マスターに値がない項目は空のままとし、
    推測で補完しない。
    """

    enriched = []

    for item in items:

        copied = item.copy()

        master = facility_master.get(
            copied.get("name", ""),
            {}
        )

        if not isinstance(master, dict):
            master = {}

        copied["season"] = (
            master.get("season")
        )

        copied["best_season"] = (
            master.get("best_season")
        )

        copied["seasonal_operation"] = (
            master.get("seasonal_operation")
        )

        copied["master_closed"] = (
            master.get("closed")
        )

        copied["master_status"] = (
            master.get("status")
        )

        copied["master_address"] = (
            master.get("address")
            or
            (master.get("basic") or {}).get(
                "address"
            )
        )

        copied["master_latitude"] = (
            master.get("latitude")
        )

        copied["master_longitude"] = (
            master.get("longitude")
        )

        copied["walking_difficulty"] = (
            copied.get("walking_difficulty")
            or
            master.get("walking_difficulty")
        )

        copied["car_free_score"] = (
            copied.get("car_free_score")
            if copied.get("car_free_score") is not None
            else master.get("car_free_score")
        )

        copied["parking"] = (
            copied.get("parking")
            or
            master.get("parking")
        )

        copied["access"] = (
            copied.get("access")
            or
            master.get("access")
        )

        enriched.append(
            copied
        )

    return enriched


spots = attach_master_season_data(
    spots
)

hotels = attach_master_season_data(
    hotels
)


# =========================================================
# 地域切替（秩父 / 川越）
# =========================================================

CHICHIBU_DATASET = {
    "spots": spots,
    "hotels": hotels,
    "restaurants": restaurants,
    "facility_master": facility_master,
    "route_locations": route_locations,
    "route_matrix_data": route_matrix_data,
    "route_matrix_routes": route_matrix_routes,
}


def _safe_load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            value = json.load(f)
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        print("[REGION DATA ERROR]", path, exc)
        return {}


KAWAGOE_SPOT_RECOMMENDATION_TAGS = {
    "時の鐘": [
        "小江戸・町並み", "歴史・文化",
        "デート", "家族", "友人"
    ],
    "蔵造りの町並み": [
        "小江戸・町並み", "歴史・文化",
        "デート", "家族", "友人"
    ],
    "菓子屋横丁": [
        "小江戸・町並み", "食べ歩き・グルメ",
        "デート", "家族", "友人"
    ],
    "川越まつり会館": [
        "歴史・文化",
        "家族", "友人", "デート"
    ],
    "旧山崎家別邸": [
        "小江戸・町並み", "歴史・文化", "自然・散策",
        "デート", "家族", "友人"
    ],
    "小江戸蔵里": [
        "小江戸・町並み", "歴史・文化", "食べ歩き・グルメ",
        "デート", "家族", "友人"
    ],
    "蓮馨寺": [
        "歴史・文化", "小江戸・町並み",
        "デート", "家族", "友人"
    ],
    "大正浪漫夢通り": [
        "小江戸・町並み", "食べ歩き・グルメ",
        "デート", "家族", "友人"
    ],
    "川越熊野神社": [
        "歴史・文化", "小江戸・町並み",
        "デート", "家族", "友人"
    ],
    "川越城本丸御殿": [
        "歴史・文化",
        "家族", "友人", "デート"
    ],
    "川越市立博物館": [
        "歴史・文化",
        "家族", "友人"
    ],
    "川越市立美術館": [
        "歴史・文化",
        "デート", "家族", "友人"
    ],
    "三芳野神社": [
        "歴史・文化",
        "家族", "友人", "デート"
    ],
    "川越氷川神社": [
        "歴史・文化",
        "デート", "家族", "友人"
    ],
    "川越城中ノ門堀跡": [
        "歴史・文化",
        "家族", "友人"
    ],
    "喜多院": [
        "歴史・文化", "自然・散策",
        "デート", "家族", "友人"
    ],
    "仙波東照宮": [
        "歴史・文化", "自然・散策",
        "デート", "家族", "友人"
    ],
    "中院": [
        "歴史・文化", "自然・散策",
        "デート", "家族", "友人"
    ],
    "成田山川越別院": [
        "歴史・文化",
        "家族", "友人"
    ],
    "川越八幡宮": [
        "歴史・文化",
        "デート", "家族", "友人"
    ],
    "伊佐沼": [
        "自然・散策",
        "デート", "家族", "友人"
    ],
    "国指定史跡 河越館跡": [
        "歴史・文化", "自然・散策",
        "家族", "友人"
    ],
}



# =========================================================
# 秩父30観光地 100点満点の推薦評価基準
#
# 川越と同じ6項目・100点満点へ統一する。
#
# 旅行目的             30点
# 旅行メンバー         20点
# 秩父らしさ           20点
# アクセス             10点
# 旅行日程への適合     10点
# 季節・旅行時期       10点
# 合計                100点
#
# 「施設そのものの価値」ではなく、
# 今回の旅行条件との相性を表す。
# =========================================================

CHICHIBU_LOCALNESS_SCORE = {
    "長瀞・岩畳": 20,
    "長瀞ラインくだり": 20,
    "宝登山": 18,
    "寶登山神社": 18,
    "宝登山ロープウェイ": 17,
    "埼玉県立自然の博物館": 14,
    "月の石もみじ公園": 16,
    "金石水管橋": 12,
    "秩父神社": 20,
    "三峯神社": 20,
    "羊山公園": 20,
    "秩父ミューズパーク": 18,
    "旅立ちの丘": 15,
    "美の山公園": 17,
    "橋立鍾乳洞": 17,
    "聖神社": 16,
    "秩父まつり会館": 19,
    "ほっとすぽっと秩父館": 15,
    "ちちぶ銘仙館": 18,
    "武甲山資料館": 17,
    "秩父ふるさと館": 17,
    "和銅遺跡": 18,
    "清雲寺": 17,
    "秩父華厳の滝": 17,
    "三十槌の氷柱": 20,
    "小松沢レジャー農園": 15,
    "秩父フルーツファーム": 15,
    "道の駅ちちぶ": 18,
    "秩父温泉 満願の湯": 18,
    "大滝温泉": 18,
}


def _chichibu_purpose_score(
    spot,
    purpose
):
    tags = set(
        spot.get(
            "tags",
            []
        )
        or []
    )

    selected = [
        str(value).strip()
        for value in (purpose or [])
        if str(value).strip()
    ]

    if not selected:
        return (
            15,
            "旅行目的はおまかせのため中間点"
        )

    matched = [
        value
        for value in selected
        if value in tags
    ]

    if matched:
        if len(matched) >= 2:
            return (
                30,
                "選択した複数の旅行目的と一致"
            )

        return (
            27,
            f"選択した「{matched[0]}」と高い相性"
        )

    # 直接一致しない場合もマイナス点にはしない。
    # 施設種別が自然/歴史なら関連性のある最低点を与える。
    spot_type = str(
        spot.get(
            "type",
            ""
        )
    ).lower()

    if (
        "自然" in selected
        and spot_type == "nature"
    ):
        return (
            18,
            "自然系施設として旅行目的と一定の相性"
        )

    if (
        "歴史" in selected
        and spot_type == "history"
    ):
        return (
            18,
            "歴史系施設として旅行目的と一定の相性"
        )

    return (
        5,
        "選択した旅行目的との直接的な一致は少ない"
    )


def _chichibu_member_score(
    spot,
    member
):
    tags = set(
        spot.get(
            "tags",
            []
        )
        or []
    )

    if member == "一人":
        if spot.get("time", 1) <= 2:
            return (
                18,
                "1人でも自分のペースで立ち寄りやすい"
            )

        return (
            15,
            "1人でも利用できるが滞在時間はやや長め"
        )

    if member in tags:
        return (
            19,
            f"{member}旅行との相性が高い"
        )

    return (
        12,
        f"{member}旅行でも利用できる"
    )


def _chichibu_access_score(
    spot
):
    if spot.get("car") is True:
        return (
            10,
            "車で立ち寄りやすく現在の旅行条件と相性が良い"
        )

    return (
        7,
        "車利用でも訪問可能だが専用駐車場等の条件は限定的"
    )


def _chichibu_itinerary_score(
    spot,
    days
):
    try:
        stay_hours = float(
            spot.get(
                "time",
                1
            )
            or 1
        )
    except (
        TypeError,
        ValueError
    ):
        stay_hours = 1.0

    if days == "1泊2日":
        if stay_hours <= 1:
            return (
                10,
                "短時間で立ち寄りやすく1泊2日に組み込みやすい"
            )
        if stay_hours <= 2:
            return (
                9,
                "1泊2日でも組み込みやすい滞在時間"
            )
        if stay_hours <= 3:
            return (
                7,
                "半日程度を確保すれば1泊2日でも組み込み可能"
            )
        return (
            5,
            "滞在時間が長く1泊2日では時間確保が必要"
        )

    # 2泊3日
    if stay_hours <= 2:
        return (
            10,
            "2泊3日の旅程に非常に組み込みやすい"
        )
    if stay_hours <= 3:
        return (
            9,
            "2泊3日なら余裕をもって組み込みやすい"
        )

    return (
        8,
        "2泊3日なら時間を確保して組み込みやすい"
    )


def _chichibu_season_score(
    spot,
    season,
    travel_date
):
    (
        raw_score,
        raw_reasons,
        unavailable
    ) = calculate_season_effect(
        spot,
        season,
        travel_date
    )

    if unavailable:
        return (
            0,
            "旅行予定日が営業条件に合っていません",
            True
        )

    if not travel_date:
        return (
            5,
            "旅行日未指定のため季節評価は中間点",
            False
        )

    if raw_score > 0:
        reason = (
            "旅行時期と施設の季節情報の相性が良い"
        )

        if raw_reasons:
            normalized_reasons = [
                str(value)
                for value in raw_reasons
                if str(value).strip()
            ]

            if normalized_reasons:
                reason = "・".join(
                    normalized_reasons
                )

        return (
            10,
            reason,
            False
        )

    if raw_score < 0:
        return (
            4,
            "旅行時期との相性はやや低め",
            False
        )

    return (
        7,
        "通年利用または季節による大きな差がない",
        False
    )


def calculate_chichibu_spot_score(
    spot,
    member,
    purpose,
    car,
    age,
    people,
    days,
    budget,
    gender,
    walking_amount="普通",
    travel_pace="普通",
    season=None,
    travel_date=""
):
    name = str(
        spot.get(
            "name",
            ""
        )
    ).strip()

    (
        purpose_score,
        purpose_reason
    ) = _chichibu_purpose_score(
        spot,
        purpose
    )

    (
        member_score,
        member_reason
    ) = _chichibu_member_score(
        spot,
        member
    )

    chichibu_score = int(
        CHICHIBU_LOCALNESS_SCORE.get(
            name,
            14
        )
    )

    if chichibu_score >= 19:
        chichibu_reason = (
            "秩父を代表する観光資源として地域性が非常に強い"
        )
    elif chichibu_score >= 16:
        chichibu_reason = (
            "秩父らしい自然・文化・観光資源を感じやすい"
        )
    else:
        chichibu_reason = (
            "秩父旅行の一要素として組み込みやすい"
        )

    (
        access_score,
        access_reason
    ) = _chichibu_access_score(
        spot
    )

    (
        itinerary_score,
        itinerary_reason
    ) = _chichibu_itinerary_score(
        spot,
        days
    )

    (
        season_score,
        season_reason,
        unavailable
    ) = _chichibu_season_score(
        spot,
        season,
        travel_date
    )

    if unavailable:
        return (
            -900,
            [
                "旅行予定日の営業条件に合わない"
            ],
            [
                _score_item_with_max(
                    "season",
                    "季節・旅行時期",
                    0,
                    10,
                    season_reason
                )
            ]
        )

    breakdown = [
        _score_item_with_max(
            "purpose",
            "旅行目的との相性",
            purpose_score,
            30,
            purpose_reason
        ),
        _score_item_with_max(
            "member",
            "旅行メンバーとの相性",
            member_score,
            20,
            member_reason
        ),
        _score_item_with_max(
            "chichibu",
            "秩父らしさ",
            chichibu_score,
            20,
            chichibu_reason
        ),
        _score_item_with_max(
            "access",
            "アクセス・移動",
            access_score,
            10,
            access_reason
        ),
        _score_item_with_max(
            "days",
            "旅行日程への組み込みやすさ",
            itinerary_score,
            10,
            itinerary_reason
        ),
        _score_item_with_max(
            "season",
            "季節・旅行時期",
            season_score,
            10,
            season_reason
        ),
    ]

    total_score = sum(
        int(
            item.get(
                "score",
                0
            )
        )
        for item in breakdown
    )

    total_score = max(
        0,
        min(
            100,
            total_score
        )
    )

    reasons = []

    if purpose_score >= 25:
        reasons.append(
            "旅行目的との相性が高い"
        )

    if member_score >= 18:
        reasons.append(
            f"{member}旅行に向いている"
        )

    if chichibu_score >= 19:
        reasons.append(
            "秩父らしさを強く感じられる"
        )

    if access_score >= 9:
        reasons.append(
            "車で立ち寄りやすい"
        )

    # 既存関数との互換用。100点評価には直接使わない。
    _ = car
    _ = age
    _ = people
    _ = budget
    _ = gender
    _ = walking_amount
    _ = travel_pace

    return (
        total_score,
        reasons,
        breakdown
    )


# =========================================================
# 川越22観光地 100点満点の推薦評価基準
#
# 旅行目的             30点
# 旅行メンバー         20点
# 川越らしさ           20点
# アクセス             10点
# 旅行日程への適合     10点
# 季節・旅行時期       10点
# 合計                100点
#
# 数値は「施設の優劣」ではなく、
# 今回の旅行条件との相性を比較するための
# システム内評価値として扱う。
# =========================================================

KAWAGOE_SPOT_SCORE_PROFILES = {
    "時の鐘": {
        "purpose": {
            "小江戸・町並み": 30,
            "歴史・文化": 25,
            "食べ歩き・グルメ": 8,
            "自然・散策": 5,
        },
        "member": {
            "一人": 18, "デート": 19, "家族": 18, "友人": 18,
        },
        "kawagoe": 20,
        "access": 8,
    },
    "蔵造りの町並み": {
        "purpose": {
            "小江戸・町並み": 30,
            "歴史・文化": 25,
            "食べ歩き・グルメ": 15,
            "自然・散策": 8,
        },
        "member": {
            "一人": 18, "デート": 20, "家族": 18, "友人": 20,
        },
        "kawagoe": 20,
        "access": 8,
    },
    "菓子屋横丁": {
        "purpose": {
            "小江戸・町並み": 24,
            "歴史・文化": 10,
            "食べ歩き・グルメ": 30,
            "自然・散策": 5,
        },
        "member": {
            "一人": 15, "デート": 19, "家族": 20, "友人": 20,
        },
        "kawagoe": 20,
        "access": 8,
    },
    "川越まつり会館": {
        "purpose": {
            "小江戸・町並み": 18,
            "歴史・文化": 30,
            "食べ歩き・グルメ": 4,
            "自然・散策": 3,
        },
        "member": {
            "一人": 17, "デート": 15, "家族": 19, "友人": 17,
        },
        "kawagoe": 19,
        "access": 8,
    },
    "旧山崎家別邸": {
        "purpose": {
            "小江戸・町並み": 24,
            "歴史・文化": 28,
            "食べ歩き・グルメ": 3,
            "自然・散策": 18,
        },
        "member": {
            "一人": 18, "デート": 20, "家族": 16, "友人": 16,
        },
        "kawagoe": 18,
        "access": 8,
    },
    "小江戸蔵里": {
        "purpose": {
            "小江戸・町並み": 24,
            "歴史・文化": 20,
            "食べ歩き・グルメ": 28,
            "自然・散策": 4,
        },
        "member": {
            "一人": 17, "デート": 18, "家族": 19, "友人": 20,
        },
        "kawagoe": 18,
        "access": 9,
    },
    "蓮馨寺": {
        "purpose": {
            "小江戸・町並み": 20,
            "歴史・文化": 27,
            "食べ歩き・グルメ": 5,
            "自然・散策": 8,
        },
        "member": {
            "一人": 18, "デート": 16, "家族": 17, "友人": 16,
        },
        "kawagoe": 16,
        "access": 9,
    },
    "大正浪漫夢通り": {
        "purpose": {
            "小江戸・町並み": 28,
            "歴史・文化": 15,
            "食べ歩き・グルメ": 22,
            "自然・散策": 8,
        },
        "member": {
            "一人": 17, "デート": 20, "家族": 17, "友人": 20,
        },
        "kawagoe": 18,
        "access": 9,
    },
    "川越熊野神社": {
        "purpose": {
            "小江戸・町並み": 20,
            "歴史・文化": 27,
            "食べ歩き・グルメ": 4,
            "自然・散策": 8,
        },
        "member": {
            "一人": 18, "デート": 18, "家族": 18, "友人": 17,
        },
        "kawagoe": 16,
        "access": 9,
    },
    "川越城本丸御殿": {
        "purpose": {
            "小江戸・町並み": 12,
            "歴史・文化": 30,
            "食べ歩き・グルメ": 2,
            "自然・散策": 7,
        },
        "member": {
            "一人": 18, "デート": 14, "家族": 19, "友人": 17,
        },
        "kawagoe": 19,
        "access": 8,
    },
    "川越市立博物館": {
        "purpose": {
            "小江戸・町並み": 10,
            "歴史・文化": 30,
            "食べ歩き・グルメ": 1,
            "自然・散策": 3,
        },
        "member": {
            "一人": 18, "デート": 12, "家族": 20, "友人": 15,
        },
        "kawagoe": 16,
        "access": 8,
    },
    "川越市立美術館": {
        "purpose": {
            "小江戸・町並み": 8,
            "歴史・文化": 27,
            "食べ歩き・グルメ": 1,
            "自然・散策": 4,
        },
        "member": {
            "一人": 18, "デート": 18, "家族": 16, "友人": 16,
        },
        "kawagoe": 14,
        "access": 8,
    },
    "三芳野神社": {
        "purpose": {
            "小江戸・町並み": 10,
            "歴史・文化": 27,
            "食べ歩き・グルメ": 1,
            "自然・散策": 10,
        },
        "member": {
            "一人": 18, "デート": 15, "家族": 17, "友人": 16,
        },
        "kawagoe": 15,
        "access": 8,
    },
    "川越氷川神社": {
        "purpose": {
            "小江戸・町並み": 16,
            "歴史・文化": 28,
            "食べ歩き・グルメ": 3,
            "自然・散策": 12,
        },
        "member": {
            "一人": 17, "デート": 20, "家族": 19, "友人": 18,
        },
        "kawagoe": 19,
        "access": 8,
    },
    "川越城中ノ門堀跡": {
        "purpose": {
            "小江戸・町並み": 8,
            "歴史・文化": 28,
            "食べ歩き・グルメ": 0,
            "自然・散策": 10,
        },
        "member": {
            "一人": 17, "デート": 11, "家族": 16, "友人": 14,
        },
        "kawagoe": 14,
        "access": 8,
    },
    "喜多院": {
        "purpose": {
            "小江戸・町並み": 14,
            "歴史・文化": 30,
            "食べ歩き・グルメ": 2,
            "自然・散策": 18,
        },
        "member": {
            "一人": 19, "デート": 18, "家族": 20, "友人": 18,
        },
        "kawagoe": 19,
        "access": 9,
    },
    "仙波東照宮": {
        "purpose": {
            "小江戸・町並み": 10,
            "歴史・文化": 30,
            "食べ歩き・グルメ": 0,
            "自然・散策": 16,
        },
        "member": {
            "一人": 18, "デート": 16, "家族": 17, "友人": 16,
        },
        "kawagoe": 17,
        "access": 9,
    },
    "中院": {
        "purpose": {
            "小江戸・町並み": 10,
            "歴史・文化": 26,
            "食べ歩き・グルメ": 0,
            "自然・散策": 20,
        },
        "member": {
            "一人": 19, "デート": 19, "家族": 16, "友人": 15,
        },
        "kawagoe": 15,
        "access": 9,
    },
    "成田山川越別院": {
        "purpose": {
            "小江戸・町並み": 8,
            "歴史・文化": 25,
            "食べ歩き・グルメ": 0,
            "自然・散策": 7,
        },
        "member": {
            "一人": 18, "デート": 13, "家族": 17, "友人": 15,
        },
        "kawagoe": 13,
        "access": 9,
    },
    "川越八幡宮": {
        "purpose": {
            "小江戸・町並み": 10,
            "歴史・文化": 25,
            "食べ歩き・グルメ": 1,
            "自然・散策": 8,
        },
        "member": {
            "一人": 18, "デート": 18, "家族": 18, "友人": 17,
        },
        "kawagoe": 14,
        "access": 10,
    },
    "伊佐沼": {
        "purpose": {
            "小江戸・町並み": 0,
            "歴史・文化": 4,
            "食べ歩き・グルメ": 0,
            "自然・散策": 30,
        },
        "member": {
            "一人": 17, "デート": 19, "家族": 20, "友人": 18,
        },
        "kawagoe": 14,
        "access": 8,
    },
    "国指定史跡 河越館跡": {
        "purpose": {
            "小江戸・町並み": 5,
            "歴史・文化": 30,
            "食べ歩き・グルメ": 0,
            "自然・散策": 16,
        },
        "member": {
            "一人": 18, "デート": 11, "家族": 17, "友人": 15,
        },
        "kawagoe": 16,
        "access": 7,
    },
}


def _score_item_with_max(
    key,
    label,
    score,
    max_score,
    reason=""
):
    return {
        "key": str(key),
        "label": str(label),
        "score": int(max(0, min(score, max_score))),
        "max_score": int(max_score),
        "reason": str(reason or ""),
    }


def _kawagoe_purpose_score(
    profile,
    purpose
):
    purpose_scores = profile.get(
        "purpose",
        {}
    )

    selected = [
        str(value).strip()
        for value in (purpose or [])
        if str(value).strip()
    ]

    if not selected:
        return (
            15,
            "旅行目的はおまかせのため中間点"
        )

    matched = [
        (
            name,
            int(
                purpose_scores.get(
                    name,
                    0
                )
                or 0
            )
        )
        for name in selected
    ]

    best_name, best_score = max(
        matched,
        key=lambda item: item[1]
    )

    if best_score >= 25:
        reason = (
            f"選択した「{best_name}」と非常に相性が良い"
        )
    elif best_score >= 15:
        reason = (
            f"選択した「{best_name}」と相性が良い"
        )
    elif best_score > 0:
        reason = (
            f"選択した「{best_name}」と一部相性がある"
        )
    else:
        reason = (
            "選択した旅行目的との直接的な一致は少ない"
        )

    return (
        best_score,
        reason
    )


def _kawagoe_member_score(
    profile,
    member
):
    member_scores = profile.get(
        "member",
        {}
    )

    score = int(
        member_scores.get(
            member,
            12
        )
        or 0
    )

    if score >= 18:
        reason = (
            f"{member}旅行と特に相性が良い"
        )
    elif score >= 14:
        reason = (
            f"{member}旅行に組み込みやすい"
        )
    elif score > 0:
        reason = (
            f"{member}旅行でも利用可能"
        )
    else:
        reason = (
            f"{member}旅行との相性は低め"
        )

    return (
        score,
        reason
    )


def _kawagoe_itinerary_score(
    spot,
    days
):
    try:
        stay_hours = float(
            spot.get(
                "time",
                1
            )
            or 1
        )
    except (
        TypeError,
        ValueError
    ):
        stay_hours = 1.0

    if days == "1泊2日":
        if stay_hours <= 1:
            return (
                10,
                "短時間で立ち寄りやすく1泊2日に組み込みやすい"
            )
        if stay_hours <= 2:
            return (
                8,
                "1泊2日でも無理なく組み込みやすい"
            )
        return (
            6,
            "滞在時間が長めのため日程に余裕が必要"
        )

    if stay_hours <= 2:
        return (
            10,
            "2泊3日の旅程に十分組み込みやすい"
        )

    return (
        8,
        "2泊3日なら時間を確保して組み込みやすい"
    )


def _kawagoe_season_score(
    spot,
    season,
    travel_date
):
    (
        raw_score,
        raw_reasons,
        unavailable
    ) = calculate_season_effect(
        spot,
        season,
        travel_date
    )

    if unavailable:
        return (
            0,
            "旅行予定日が営業条件に合っていません",
            True
        )

    if not travel_date:
        return (
            5,
            "旅行日未指定のため季節評価は中間点",
            False
        )

    if raw_score > 0:
        reason = (
            "旅行時期と施設の季節情報の相性が良い"
        )
        if raw_reasons:
            reason = "・".join(
                str(x)
                for x in raw_reasons
                if str(x).strip()
            ) or reason

        return (
            10,
            reason,
            False
        )

    if raw_score < 0:
        return (
            4,
            "旅行時期との相性はやや低め",
            False
        )

    return (
        7,
        "通年利用または季節による大きな差がない",
        False
    )


def calculate_kawagoe_spot_score(
    spot,
    member,
    purpose,
    car,
    age,
    people,
    days,
    budget,
    gender,
    walking_amount="普通",
    travel_pace="普通",
    season=None,
    travel_date=""
):
    name = str(
        spot.get(
            "name",
            ""
        )
    ).strip()

    profile = (
        KAWAGOE_SPOT_SCORE_PROFILES.get(
            name,
            {}
        )
    )

    if not profile:
        # 未登録施設が混ざった場合も100点制を壊さない。
        profile = {
            "purpose": {},
            "member": {
                "一人": 12,
                "デート": 12,
                "家族": 12,
                "友人": 12,
            },
            "kawagoe": 10,
            "access": 5,
        }

    purpose_score, purpose_reason = (
        _kawagoe_purpose_score(
            profile,
            purpose
        )
    )

    member_score, member_reason = (
        _kawagoe_member_score(
            profile,
            member
        )
    )

    kawagoe_score = int(
        profile.get(
            "kawagoe",
            10
        )
        or 0
    )

    if kawagoe_score >= 18:
        kawagoe_reason = (
            "川越を代表する観光資源としての特色が強い"
        )
    elif kawagoe_score >= 14:
        kawagoe_reason = (
            "川越の歴史・文化・景観を感じやすい"
        )
    else:
        kawagoe_reason = (
            "川越観光の一要素として組み込みやすい"
        )

    access_score = int(
        profile.get(
            "access",
            5
        )
        or 0
    )

    if access_score >= 9:
        access_reason = (
            "市街地や主要ルートから立ち寄りやすい"
        )
    elif access_score >= 7:
        access_reason = (
            "車移動の旅程に組み込みやすい"
        )
    else:
        access_reason = (
            "移動にはやや時間の確保が必要"
        )

    itinerary_score, itinerary_reason = (
        _kawagoe_itinerary_score(
            spot,
            days
        )
    )

    (
        season_score,
        season_reason,
        unavailable
    ) = _kawagoe_season_score(
        spot,
        season,
        travel_date
    )

    if unavailable:
        return (
            -900,
            [
                "旅行予定日の営業条件に合わない"
            ],
            [
                _score_item_with_max(
                    "season",
                    "季節・旅行時期",
                    0,
                    10,
                    season_reason
                )
            ]
        )

    breakdown = [
        _score_item_with_max(
            "purpose",
            "旅行目的との相性",
            purpose_score,
            30,
            purpose_reason
        ),
        _score_item_with_max(
            "member",
            "旅行メンバーとの相性",
            member_score,
            20,
            member_reason
        ),
        _score_item_with_max(
            "kawagoe",
            "川越らしさ",
            kawagoe_score,
            20,
            kawagoe_reason
        ),
        _score_item_with_max(
            "access",
            "アクセス・移動",
            access_score,
            10,
            access_reason
        ),
        _score_item_with_max(
            "days",
            "旅行日程への組み込みやすさ",
            itinerary_score,
            10,
            itinerary_reason
        ),
        _score_item_with_max(
            "season",
            "季節・旅行時期",
            season_score,
            10,
            season_reason
        ),
    ]

    total_score = sum(
        int(
            item.get(
                "score",
                0
            )
        )
        for item in breakdown
    )

    total_score = max(
        0,
        min(
            100,
            total_score
        )
    )

    reasons = []

    if purpose_score >= 25:
        reasons.append(
            "旅行目的との相性が高い"
        )

    if member_score >= 18:
        reasons.append(
            f"{member}旅行に向いている"
        )

    if kawagoe_score >= 18:
        reasons.append(
            "川越らしさを強く感じられる"
        )

    if access_score >= 9:
        reasons.append(
            "旅程に組み込みやすい立地"
        )

    # 既存関数との互換用。評価には使わない。
    _ = car
    _ = age
    _ = people
    _ = budget
    _ = gender
    _ = walking_amount
    _ = travel_pace

    return (
        total_score,
        reasons,
        breakdown
    )


KAWAGOE_HOTEL_RECOMMENDATION_TAGS = {
    "松村屋旅館": [
        "小江戸・町並み", "歴史・文化",
        "デート", "家族", "友人"
    ],
    "川越ビジネスホテル": [
        "友人"
    ],
    "川越東武ホテル": [
        "デート", "家族", "友人"
    ],
    "川越第一ホテル": [
        "友人"
    ],
    "川越プリンスホテル": [
        "デート", "家族", "友人"
    ],
    "川越湯遊ランド・ホテル三光": [
        "デート", "家族", "友人"
    ],
    "デイリーホテル小江戸川越店": [
        "小江戸・町並み",
        "家族", "友人"
    ],
    "UTILITY HOTEL cooju": [
        "デート", "友人"
    ],
    "スーパーホテル埼玉・川越": [
        "家族", "友人"
    ],
    "旅籠 小江戸や": [
        "小江戸・町並み",
        "家族", "友人"
    ],
    "泊まれるリラクゼーションサロン ゆきき": [
        "デート", "家族"
    ],
    "ちゃぶだい Guesthouse, Cafe&Bar": [
        "小江戸・町並み", "歴史・文化",
        "デート", "友人"
    ],
    "小江戸川越おもてなしの家": [
        "家族", "友人"
    ],
    "月の宿 KAGUYA": [
        "デート", "友人"
    ],
    "WE HOME STAY 川越・的場": [
        "歴史・文化",
        "家族", "友人"
    ],
    "結家 -MUSUBIYA-": [
        "歴史・文化",
        "デート", "家族", "友人"
    ],
    "丹徳庭園": [
        "歴史・文化", "自然・散策",
        "デート", "家族"
    ],
    "ゲストハウスくく 川越店": [
        "友人"
    ],
}


def _kawagoe_objective_tags(facility):
    """
    川越22観光地の推薦タグ。
    施設マスターの種別・説明と川越観光の性格に合わせて、
    施設ごとに明示的に定義する。
    """
    name = str(facility.get("name") or "").strip()

    return list(
        KAWAGOE_SPOT_RECOMMENDATION_TAGS.get(
            name,
            []
        )
    )


def _kawagoe_standard_stay_hours(facility):
    """
    公式値ではなく、旅程作成のためのシステム内標準滞在時間。
    詳細マスターに公式値がある場合はそちらを優先する。
    """
    basic = facility.get("basic") if isinstance(facility.get("basic"), dict) else {}
    raw = basic.get("stay_time_hours")
    try:
        if raw is not None:
            return float(raw)
    except (TypeError, ValueError):
        pass

    text = " ".join([
        str(facility.get("name") or ""),
        str(basic.get("type") or ""),
    ])

    if any(word in text for word in ("博物館", "美術館", "町並み", "横丁", "伊佐沼", "河越館跡")):
        return 2
    return 1


def _kawagoe_facility_to_spot(facility):
    basic = facility.get("basic") if isinstance(facility.get("basic"), dict) else {}
    access = facility.get("access") if isinstance(facility.get("access"), dict) else {}

    car_text = " ".join([
        str(access.get("car") or ""),
        str(facility.get("parking") or ""),
    ])
    has_confirmed_parking = (
        "駐車" in car_text
        and "確認できず" not in car_text
        and "なし" not in car_text
    )

    return {
        "name": str(facility.get("name") or ""),
        "tags": _kawagoe_objective_tags(facility),
        "car": bool(has_confirmed_parking),
        "time": _kawagoe_standard_stay_hours(facility),
        "area": str(basic.get("area") or "川越"),
        "type": str(basic.get("type") or "観光"),
        "description": str(facility.get("description") or facility.get("notes") or ""),
        "difficulty": facility.get("walking_difficulty"),
        "url": facility.get("official_url") or facility.get("source") or "",
        "address": basic.get("address") or facility.get("address"),
        "phone": basic.get("phone") or facility.get("phone"),
        "season": facility.get("season"),
        "best_season": facility.get("best_season"),
        "seasonal_operation": facility.get("seasonal_operation"),
        "closed": facility.get("closed"),
        "status": facility.get("status"),
        "planning_time_note": "滞在時間は旅程作成用のシステム内標準値",
    }


def _kawagoe_facility_to_hotel(facility):
    basic = facility.get("basic") if isinstance(facility.get("basic"), dict) else {}
    contact = facility.get("contact") if isinstance(facility.get("contact"), dict) else {}

    name = str(
        facility.get("name")
        or ""
    ).strip()

    tags = list(
        KAWAGOE_HOTEL_RECOMMENDATION_TAGS.get(
            name,
            []
        )
    )

    return {
        "name": name,
        "tags": tags,
        "price": None,
        "quality": None,
        "type": str(basic.get("type") or "宿泊施設"),
        "description": str(facility.get("description") or facility.get("notes") or ""),
        "url": facility.get("official_url") or facility.get("source") or "",
        "address": basic.get("address") or contact.get("address") or facility.get("address"),
        "phone": basic.get("phone") or contact.get("phone") or facility.get("phone"),
        "season": facility.get("season"),
        "best_season": facility.get("best_season"),
        "seasonal_operation": facility.get("seasonal_operation"),
        "closed": facility.get("closed"),
        "status": facility.get("status"),
        "price_note": "宿泊料金は日付・人数・部屋・プランで変動するため予約時確認",
    }


def _load_kawagoe_dataset():
    master_data = _safe_load_json(KAWAGOE_FACILITY_MASTER_FILE)
    restaurant_data_local = _safe_load_json(KAWAGOE_RESTAURANT_FILE)
    route_location_data_local = _safe_load_json(KAWAGOE_ROUTE_LOCATION_FILE)
    route_matrix_data_local = _safe_load_json(KAWAGOE_ROUTE_MATRIX_FILE)

    facilities = master_data.get("facilities", [])
    if not isinstance(facilities, list):
        facilities = []

    kawagoe_spots = [
        _kawagoe_facility_to_spot(item)
        for item in facilities
        if isinstance(item, dict) and item.get("category") == "観光スポット"
    ]

    kawagoe_hotels = [
        _kawagoe_facility_to_hotel(item)
        for item in facilities
        if isinstance(item, dict) and item.get("category") == "宿泊施設"
    ]

    kawagoe_restaurants = restaurant_data_local.get("restaurants", [])
    if not isinstance(kawagoe_restaurants, list):
        kawagoe_restaurants = []

    # raw masterも名称辞書にして、既存の地図・季節処理と互換化
    kawagoe_master = {}
    for item in facilities:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue

        copied = dict(item)
        basic = copied.get("basic") if isinstance(copied.get("basic"), dict) else {}
        contact = copied.get("contact") if isinstance(copied.get("contact"), dict) else {}

        copied["address"] = (
            basic.get("address")
            or contact.get("address")
            or copied.get("address")
        )
        copied["phone"] = (
            basic.get("phone")
            or contact.get("phone")
            or copied.get("phone")
        )
        copied["type"] = basic.get("type") or copied.get("type")
        copied["area"] = basic.get("area") or copied.get("area")

        kawagoe_master[name] = copied

    local_routes = route_matrix_data_local.get("routes", {})
    if not isinstance(local_routes, dict):
        local_routes = {}

    local_locations = route_location_data_local.get("route_locations")
    if not isinstance(local_locations, dict):
        local_locations = (
            route_location_data_local.get("locations")
            if isinstance(route_location_data_local.get("locations"), dict)
            else {}
        )

    return {
        "spots": kawagoe_spots,
        "hotels": kawagoe_hotels,
        "restaurants": kawagoe_restaurants,
        "facility_master": kawagoe_master,
        "route_locations": local_locations,
        "route_matrix_data": route_matrix_data_local,
        "route_matrix_routes": local_routes,
    }


KAWAGOE_DATASET = _load_kawagoe_dataset()


REGION_CONFIG = {
    "chichibu": {
        "name": "秩父",
        "name_en": "CHICHIBU",
        "weather_lat": 35.991681,
        "weather_lon": 139.085475,
        "arrival_labels": {
            "花園IC": "関越道方面から（花園IC）",
            "芦ヶ久保駅": "飯能方面から（国道299号・芦ヶ久保）",
        },
        "default_arrival": "花園IC",
        "purpose_options": [
            {"value": "自然", "label": "自然"},
            {"value": "温泉", "label": "温泉"},
            {"value": "グルメ", "label": "グルメ"},
            {"value": "歴史", "label": "歴史"},
        ],
        "dataset": CHICHIBU_DATASET,
    },
    "kawagoe": {
        "name": "川越",
        "name_en": "KAWAGOE",
        # 川越市中心部付近を7日間天気予報の代表座標として使用。
        "weather_lat": 35.9251,
        "weather_lon": 139.4858,
        "arrival_labels": {
            "川越IC": "関越道方面から（川越IC）",
            "川越駅": "市街地方面から（川越駅周辺）",
        },
        "default_arrival": "川越IC",
        "purpose_options": [
            {
                "value": "小江戸・町並み",
                "label": "小江戸・町並み"
            },
            {
                "value": "歴史・文化",
                "label": "歴史・文化"
            },
            {
                "value": "食べ歩き・グルメ",
                "label": "食べ歩き・グルメ"
            },
            {
                "value": "自然・散策",
                "label": "自然・散策"
            },
        ],
        "dataset": KAWAGOE_DATASET,
    },
}


def activate_region(region_code):
    global ACTIVE_REGION_CODE
    global ACTIVE_REGION_NAME
    global ACTIVE_REGION_NAME_EN
    global ACTIVE_WEATHER_LATITUDE
    global ACTIVE_WEATHER_LONGITUDE
    global ARRIVAL_METHOD_LABELS
    global START_POINT_OPTIONS
    global spots
    global hotels
    global restaurants
    global facility_master
    global route_locations
    global route_matrix_data
    global route_matrix_routes
    global _ROUTE_CACHE

    config = REGION_CONFIG.get(region_code)
    if not config:
        config = REGION_CONFIG["chichibu"]
        region_code = "chichibu"

    data = config["dataset"]

    ACTIVE_REGION_CODE = region_code
    ACTIVE_REGION_NAME = config["name"]
    ACTIVE_REGION_NAME_EN = config["name_en"]
    ACTIVE_WEATHER_LATITUDE = config["weather_lat"]
    ACTIVE_WEATHER_LONGITUDE = config["weather_lon"]
    ARRIVAL_METHOD_LABELS = dict(config["arrival_labels"])
    START_POINT_OPTIONS = set(ARRIVAL_METHOD_LABELS.keys())

    spots = data["spots"]
    hotels = data["hotels"]
    restaurants = data["restaurants"]
    facility_master = data["facility_master"]
    route_locations = data["route_locations"]
    route_matrix_data = data["route_matrix_data"]
    route_matrix_routes = data["route_matrix_routes"]

    _ROUTE_CACHE = {}

    return config


# =========================================================
# 共通ヘルパー
# =========================================================

def _valid_coordinate(value):
    """
    数値として安全に扱える緯度・経度だけを採用する。
    """

    if value is None or value == "":
        return None

    try:
        return float(value)

    except (
        TypeError,
        ValueError
    ):
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

    name = str(
        item.get("name") or ""
    ).strip()

    area = str(
        item.get("area") or ""
    ).strip()


    lat = _valid_coordinate(
        item.get("latitude")
    )

    lng = _valid_coordinate(
        item.get("longitude")
    )


    if lat is None:

        lat = _valid_coordinate(
            item.get("lat")
        )


    if lng is None:

        lng = _valid_coordinate(
            item.get("lng")
        )


    if lat is None:

        lat = _valid_coordinate(
            item.get(
                "master_latitude"
            )
        )


    if lng is None:

        lng = _valid_coordinate(
            item.get(
                "master_longitude"
            )
        )


    address = (
        item.get("address")
        or
        item.get("master_address")
    )


    if isinstance(
        address,
        dict
    ):

        address = (
            address.get("full")
            or
            address.get("text")
        )


    address = (
        str(address).strip()
        if address
        else ""
    )


    if (
        lat is not None
        and
        lng is not None
    ):

        query = (
            f"{lat:.7f},{lng:.7f}"
        )

        source = "coordinates"


    elif address and name:

        query = (
            f"{name} {address}"
        ).strip()

        source = "address"


    elif address:

        query = address

        source = "address"


    elif name:

        parts = [
            name
        ]

        if area:
            parts.append(
                area
            )

        parts.extend(
            [
                "秩父",
                "埼玉県",
                "日本"
            ]
        )

        query = " ".join(
            parts
        )

        source = "name_fallback"


    else:

        query = ""

        source = None


    return (
        query,
        source
    )


def build_map_url(item):
    """
    Google Maps外部リンクと埋め込みURLを
    同じ検索条件から生成する。
    """

    query, source = (
        _map_context(
            item
        )
    )


    if not query:

        return (
            None,
            None,
            None,
            source
        )


    encoded = quote(
        query,
        safe=""
    )


    external_url = (
        "https://www.google.com/maps/search/"
        "?api=1&query="
        +
        encoded
    )


    embed_url = (
        "https://www.google.com/maps?q="
        +
        encoded
        +
        "&output=embed"
    )


    return (
        external_url,
        embed_url,
        query,
        source
    )


def attach_map_data(item):
    """
    既存データを変更せず、
    結果画面用の地図情報だけを追加する。
    """

    copied = item.copy()


    (
        map_url,
        embed_url,
        query,
        source

    ) = build_map_url(
        copied
    )


    copied["map_url"] = (
        map_url
    )

    copied["map_embed_url"] = (
        embed_url
    )

    copied["map_query"] = (
        query
    )

    copied["map_source"] = (
        source
    )

    copied["map_available"] = (
        bool(query)
    )


    return copied


def _route_coordinates_from_item(item):
    """
    施設の座標を取得する。

    優先順位:
    1. latitude / longitude
    2. lat / lng
    3. master_latitude / master_longitude

    座標は [経度, 緯度] の順で返す。
    """

    if not isinstance(item, dict):
        return None

    lat = _valid_coordinate(
        item.get("latitude")
    )

    lng = _valid_coordinate(
        item.get("longitude")
    )

    if lat is None:
        lat = _valid_coordinate(
            item.get("lat")
        )

    if lng is None:
        lng = _valid_coordinate(
            item.get("lng")
        )

    if lat is None:
        lat = _valid_coordinate(
            item.get("master_latitude")
        )

    if lng is None:
        lng = _valid_coordinate(
            item.get("master_longitude")
        )

    if (
        lat is None
        or
        lng is None
    ):
        return None

    return [
        float(lng),
        float(lat)
    ]


def _route_coordinates(place):
    """
    登録済み地点の固定座標だけを取得する。

    外部ジオコーディングは行わない。
    route_locations.json または既存施設データに
    座標がない場合は None を返す。
    """

    if isinstance(place, str):
        name = str(place or "").strip()

        matrix_location = (
            route_matrix_data
            .get("locations", {})
            .get(name, {})
        )

        if isinstance(matrix_location, dict):
            lat = _valid_coordinate(
                matrix_location.get("latitude")
            )
            lng = _valid_coordinate(
                matrix_location.get("longitude")
            )

            if lat is not None and lng is not None:
                return [float(lng), float(lat)]

        route_record = route_locations.get(name, {})

        if isinstance(route_record, dict):
            lat = _valid_coordinate(
                route_record.get("latitude")
            )
            lng = _valid_coordinate(
                route_record.get("longitude")
            )

            if lat is not None and lng is not None:
                return [float(lng), float(lat)]

        return None

    if not isinstance(place, dict):
        return None

    name = str(
        place.get("name")
        or ""
    ).strip()

    if name:
        matrix_location = (
            route_matrix_data
            .get("locations", {})
            .get(name, {})
        )

        if isinstance(matrix_location, dict):
            lat = _valid_coordinate(
                matrix_location.get("latitude")
            )
            lng = _valid_coordinate(
                matrix_location.get("longitude")
            )

            if lat is not None and lng is not None:
                return [float(lng), float(lat)]

        route_record = route_locations.get(name, {})

        if isinstance(route_record, dict):
            lat = _valid_coordinate(
                route_record.get("latitude")
            )
            lng = _valid_coordinate(
                route_record.get("longitude")
            )

            if lat is not None and lng is not None:
                return [float(lng), float(lat)]

    return _route_coordinates_from_item(place)


def audit_route_location_coordinates():
    """
    観光地30件 + 宿泊11件の座標解決状況を確認する。
    """

    items = list(spots) + list(hotels)

    ok = []
    missing = []

    for item in items:

        name = str(
            item.get("name")
            or ""
        ).strip()

        coordinates = _route_coordinates(
            item
        )

        record = {
            "name": name,
            "coordinates": coordinates
        }

        if coordinates:
            ok.append(record)
        else:
            missing.append(record)

    return {
        "ok": ok,
        "missing": missing
    }


def _format_distance(
    meters
):
    """
    距離を表示用文字列へ変換する。
    """

    if meters is None:
        return None

    try:
        meters = int(
            round(
                float(meters)
            )
        )

    except (
        ValueError,
        TypeError
    ):
        return None

    if meters < 1000:
        return (
            f"{meters}m"
        )

    return (
        f"{meters / 1000:.1f}km"
    )


def _format_duration(
    seconds
):
    """
    秒を表示用の所要時間へ変換する。
    """

    if seconds is None:
        return None

    try:
        seconds = max(
            0,
            int(
                round(
                    float(seconds)
                )
            )
        )

    except (
        ValueError,
        TypeError
    ):
        return None

    minutes = int(
        round(
            seconds
            /
            60
        )
    )

    if minutes < 60:
        return (
            f"約{minutes}分"
        )

    hours = (
        minutes
        //
        60
    )

    remaining = (
        minutes
        %
        60
    )

    if remaining == 0:
        return (
            f"約{hours}時間"
        )

    return (
        f"約{hours}時間{remaining}分"
    )


def _route_mode_label(
    profile
):
    """車専用システムの移動手段表示。"""
    _ = profile
    return "車"


def _google_maps_directions_url(
    origin_text,
    destination_text,
    profile="driving-car"
):
    """
    利用者が外部地図で確認できるよう、
    Google Mapsの車ルート確認リンクを作る。

    Google Maps APIキーは不要。
    """

    params = {
        "api": "1",
        "origin": origin_text,
        "destination": destination_text,
        "travelmode": "driving"
    }

    return (
        "https://www.google.com/maps/dir/?"
        +
        urlencode(params)
    )


def _route_display_text(
    place
):
    """
    外部地図リンク表示用の地点名を作る。
    """

    if isinstance(
        place,
        str
    ):
        return place

    if not isinstance(
        place,
        dict
    ):
        return ""

    name = str(
        place.get("name")
        or ""
    ).strip()

    address = (
        place.get("address")
        or
        place.get("master_address")
    )

    if isinstance(
        address,
        dict
    ):
        address = (
            address.get("full")
            or
            address.get("text")
            or
            ""
        )

    address = str(
        address
        or ""
    ).strip()

    if name and address:
        return (
            f"{name} {address}"
        )

    return (
        name
        or
        address
    )


_ROUTE_CACHE = {}


# =========================================================
# 観光プラン用 車移動時間補正
# =========================================================
#
# OpenStreetMap / OSMnx の道路 travel_time は
# 道路ネットワーク上の走行時間としては有用だが、
# 観光時の信号待ち・市街地走行・駐車場への出入りなどを
# 十分に表現しない区間がある。
#
# そこで表示・旅程計算では、
#   1) 元のOSMnx所要時間
#   2) 地域別の平均旅行速度から求める時間 + 2分
# の長い方を採用する。
#
# 川越 : 25 km/h
#   市街地・交差点が多い観光エリアを考慮。
#
# 秩父 : 30 km/h
#   郊外・山間部を含むため川越より高めに設定。
#
# +2分 :
#   駐車場・施設入口への進入、発進、乗降等の
#   観光移動時の余裕時間。
#
# リアルタイム渋滞予測ではなく、
# 旅行プラン作成用の安全側の目安。
# =========================================================

TOUR_DRIVING_SPEED_KMH = {
    "chichibu": 30.0,
    "kawagoe": 25.0,
}

TOUR_DRIVING_ACCESS_BUFFER_SECONDS = 120


def _realistic_driving_duration_seconds(
    distance_meters,
    raw_duration_seconds
):
    """
    観光プラン用に車移動時間を現実寄りへ補正する。

    補正時間 =
        距離 ÷ 地域別平均旅行速度
        + 2分

    元のOSMnx時間より短くしない。
    最終的に1分単位で切り上げる。
    """
    try:
        distance_meters = max(
            0.0,
            float(distance_meters)
        )

        raw_duration_seconds = max(
            0.0,
            float(raw_duration_seconds)
        )

    except (
        TypeError,
        ValueError
    ):
        return raw_duration_seconds

    if distance_meters <= 0:
        return int(
            round(
                raw_duration_seconds
            )
        )

    average_speed_kmh = (
        TOUR_DRIVING_SPEED_KMH.get(
            ACTIVE_REGION_CODE,
            30.0
        )
    )

    speed_based_seconds = (
        (
            distance_meters
            /
            1000.0
        )
        /
        average_speed_kmh
        *
        3600.0
    )

    corrected_seconds = max(
        raw_duration_seconds,
        (
            speed_based_seconds
            +
            TOUR_DRIVING_ACCESS_BUFFER_SECONDS
        )
    )

    # 表示が「約0分」にならないよう、
    # 観光用の補正時間は1分単位で切り上げる。
    corrected_seconds = int(
        (
            int(
                corrected_seconds
            )
            +
            59
        )
        //
        60
        *
        60
    )

    return corrected_seconds


def calculate_route_between(
    origin,
    destination,
    car,
    walking_amount
):
    """
    2地点間の車ルートを
    data/route_matrix.json から取得する。

    システム実行中に外部ルートAPIへは接続しない。
    """

    origin_name = _segment_name(origin)
    destination_name = _segment_name(destination)

    if not origin_name or not destination_name:
        return None

    # 同一地点は移動なしとして扱う。
    if origin_name == destination_name:
        return {
            "available": True,
            "distance_meters": 0,
            "distance_km": 0.0,
            "distance_text": "0 m",
            "duration_seconds": 0,
            "duration_minutes": 0.0,
            "duration_text": "0分",
            "source": "OpenStreetMap + OSMnx local route matrix",
            "calculation_method": "same_location",
            "is_estimate": False,
            "maps_url": _google_maps_directions_url(
                _route_display_text(origin),
                _route_display_text(destination),
                "driving-car"
            )
        }

    origin_routes = route_matrix_routes.get(
        origin_name
    )

    if not isinstance(origin_routes, dict):
        print(
            "[LOCAL ROUTE ORIGIN NOT FOUND]",
            origin_name
        )
        return None

    matrix_route = origin_routes.get(
        destination_name
    )

    if not isinstance(matrix_route, dict):
        print(
            "[LOCAL ROUTE DESTINATION NOT FOUND]",
            origin_name,
            "->",
            destination_name
        )
        return None

    if matrix_route.get("available") is not True:
        print(
            "[LOCAL ROUTE UNAVAILABLE]",
            origin_name,
            "->",
            destination_name
        )
        return None

    try:
        distance_meters = int(
            round(
                float(
                    matrix_route.get(
                        "distance_meters",
                        0
                    )
                )
            )
        )

        raw_duration_seconds = int(
            round(
                float(
                    matrix_route.get(
                        "duration_seconds",
                        0
                    )
                )
            )
        )

        duration_seconds = (
            _realistic_driving_duration_seconds(
                distance_meters,
                raw_duration_seconds
            )
        )

    except (TypeError, ValueError):
        return None

    route_data = {
        "available": True,
        "distance_meters": distance_meters,
        "distance_km": round(
            distance_meters / 1000,
            2
        ),
        "distance_text": _format_distance(
            distance_meters
        ),
        "duration_seconds": duration_seconds,
        "raw_duration_seconds": raw_duration_seconds,
        "duration_adjusted": (
            duration_seconds
            >
            raw_duration_seconds
        ),
        "duration_adjustment_method": (
            "tourism_realistic_driving_time"
        ),
        "duration_minutes": round(
            duration_seconds / 60,
            1
        ),
        "duration_text": _format_duration(
            duration_seconds
        ),
        "source": "OpenStreetMap + OSMnx local route matrix",
        "calculation_method": matrix_route.get(
            "calculation_method",
            "road_network"
        ),
        "is_estimate": False,
        "maps_url": _google_maps_directions_url(
            _route_display_text(origin),
            _route_display_text(destination),
            "driving-car"
        )
    }

    print(
        "[LOCAL ROUTE]",
        origin_name,
        "->",
        destination_name,
        "|",
        route_data["distance_text"],
        "|",
        route_data["duration_text"]
    )

    # 現在は車ルート固定。既存関数シグネチャ維持のため受け取る。
    _ = car
    _ = walking_amount

    return route_data


def _segment_name(
    place
):
    if isinstance(
        place,
        str
    ):
        return place

    if isinstance(
        place,
        dict
    ):
        return str(
            place.get(
                "name",
                ""
            )
        )

    return ""


def build_route_segment(
    origin,
    destination,
    car,
    walking_amount
):
    """
    結果画面・履歴保存用の1区間データを作る。
    """

    route = (
        calculate_route_between(
            origin,
            destination,
            car,
            walking_amount
        )
    )

    segment = {
        "origin":
            _segment_name(
                origin
            ),
        "destination":
            _segment_name(
                destination
            ),
        "available":
            bool(route)
    }

    if not route:
        return segment

    segment.update(
        route
    )

    return segment


def _route_total_seconds(
    segments
):
    total = 0

    for segment in (
        segments
        or
        []
    ):
        seconds = (
            segment.get(
                "duration_seconds"
            )
        )

        if isinstance(
            seconds,
            int
        ):
            total += seconds

    return total


def _route_total_distance(
    segments
):
    total = 0

    for segment in (
        segments
        or
        []
    ):
        meters = (
            segment.get(
                "distance_meters"
            )
        )

        if isinstance(
            meters,
            int
        ):
            total += meters

    return total


def _route_candidate_segments(
    origin,
    spots_for_day,
    destination,
    car,
    walking_amount
):
    """
    1日の観光地順序候補から移動区間を作る。
    """

    segments = []

    current = origin

    for spot in (
        spots_for_day
        or
        []
    ):
        segments.append(
            build_route_segment(
                current,
                spot,
                car,
                walking_amount
            )
        )

        current = spot

    if destination is not None:
        segments.append(
            build_route_segment(
                current,
                destination,
                car,
                walking_amount
            )
        )

    return segments


def _s1_stay_minutes(spot):
    """
    S1で使う観光地の滞在時間（分）。
    現段階では既存の time（時間）を利用する。
    S11導入後は plan_extra.json の stay_hours を優先する。
    """
    master_stay_hours = None

    spot_name = str(
        spot.get(
            "name",
            ""
        )
        or ""
    )

    master = (
        facility_master.get(
            spot_name,
            {}
        )
        if spot_name
        else {}
    )

    if isinstance(
        master,
        dict
    ):

        basic = (
            master.get(
                "basic"
            )
            if isinstance(
                master.get(
                    "basic"
                ),
                dict
            )
            else {}
        )

        master_stay_hours = (
            master.get(
                "stay_hours"
            )
            or
            basic.get(
                "stay_time_hours"
            )
        )

    raw_hours = (
        master_stay_hours
        if master_stay_hours
        is not None
        else
        spot.get(
            "time",
            1.5
        )
    )

    try:
        hours = float(
            raw_hours
            or 1.5
        )
    except (
        TypeError,
        ValueError
    ):
        hours = 1.5

    hours = max(
        0.5,
        hours
    )

    return int(
        round(
            hours * 60
        )
    )


def _s1_day_settings(
    days,
    age
):
    """
    解決策S1の時間上限・件数上限。
    """
    try:
        age_value = int(age)
    except (
        TypeError,
        ValueError
    ):
        age_value = 20

    age_reduction = (
        60
        if age_value >= 50
        else 0
    )

    if days == "1泊2日":

        base = [
            {
                "minutes": 360,
                "max_spots": 2
            },
            {
                "minutes": 330,
                "max_spots": 2
            }
        ]

    else:

        base = [
            {
                "minutes": 360,
                "max_spots": 2
            },
            {
                "minutes": 480,
                "max_spots": 3
            },
            {
                "minutes": 330,
                "max_spots": 2
            }
        ]

    return [
        {
            "minutes":
                max(
                    180,
                    item["minutes"]
                    -
                    age_reduction
                ),
            "max_spots":
                item["max_spots"]
        }
        for item in base
    ]



def _fast_distance_km_between(
    origin,
    destination
):
    """
    候補比較専用の高速距離推定。
    ORSには通信せず、登録済み座標の直線距離を使う。
    """
    origin_coordinates = (
        _route_coordinates(
            origin
        )
    )

    destination_coordinates = (
        _route_coordinates(
            destination
        )
    )

    if (
        not origin_coordinates
        or
        not destination_coordinates
    ):
        return None

    try:
        origin_lng = float(
            origin_coordinates[0]
        )
        origin_lat = float(
            origin_coordinates[1]
        )
        destination_lng = float(
            destination_coordinates[0]
        )
        destination_lat = float(
            destination_coordinates[1]
        )
    except (
        TypeError,
        ValueError,
        IndexError
    ):
        return None

    # Haversine
    lat1 = math.radians(
        origin_lat
    )
    lat2 = math.radians(
        destination_lat
    )

    delta_lat = math.radians(
        destination_lat
        -
        origin_lat
    )

    delta_lng = math.radians(
        destination_lng
        -
        origin_lng
    )

    a = (
        math.sin(
            delta_lat / 2
        )
        ** 2
        +
        math.cos(
            lat1
        )
        *
        math.cos(
            lat2
        )
        *
        math.sin(
            delta_lng / 2
        )
        ** 2
    )

    c = (
        2
        *
        math.atan2(
            math.sqrt(
                a
            ),
            math.sqrt(
                max(
                    0,
                    1 - a
                )
            )
        )
    )

    return (
        6371.0
        *
        c
    )


def _fast_route_seconds_between(
    origin,
    destination
):
    """
    S1/S13候補比較専用の高速所要時間推定。

    直線距離×1.30で道路距離を近似し、
    最終表示と同じ地域別平均旅行速度を利用する。

    川越 : 25 km/h
    秩父 : 30 km/h

    さらに観光移動の余裕として2分を加える。
    """
    distance_km = (
        _fast_distance_km_between(
            origin,
            destination
        )
    )

    if distance_km is None:
        return None

    estimated_road_km = (
        distance_km
        *
        1.30
    )

    average_speed_kmh = (
        TOUR_DRIVING_SPEED_KMH.get(
            ACTIVE_REGION_CODE,
            30.0
        )
    )

    estimated_seconds = (
        estimated_road_km
        /
        average_speed_kmh
        *
        3600.0
        +
        TOUR_DRIVING_ACCESS_BUFFER_SECONDS
    )

    estimated_seconds = max(
        60,
        int(
            (
                int(
                    estimated_seconds
                )
                +
                59
            )
            //
            60
            *
            60
        )
    )

    return estimated_seconds


def _fast_candidate_segments(
    origin,
    spots_for_day,
    destination
):
    """
    S1比較用の擬似セグメント。
    API通信を行わない。
    """
    points = [
        origin
    ]

    points.extend(
        list(
            spots_for_day
            or []
        )
    )

    if destination is not None:
        points.append(
            destination
        )

    segments = []

    for index in range(
        len(points) - 1
    ):

        seconds = (
            _fast_route_seconds_between(
                points[index],
                points[index + 1]
            )
        )

        if seconds is None:

            segments.append({
                "available":
                    False,
                "duration_seconds":
                    None
            })

        else:

            segments.append({
                "available":
                    True,
                "duration_seconds":
                    seconds
            })

    return segments


def _s1_shortest_day_route(
    origin,
    spots_for_day,
    destination,
    car,
    walking_amount
):
    """
    1日3件までを全順列で比較し、
    実ルート所要時間が最短の順番を返す。
    """
    spots_for_day = list(
        spots_for_day
        or []
    )

    if not spots_for_day:

        segments = []

        if destination is not None:

            segments = (
                _route_candidate_segments(
                    origin,
                    [],
                    destination,
                    car,
                    walking_amount
                )
            )

        available = all(
            segment.get(
                "available"
            )
            for segment in segments
        )

        return (
            [],
            segments,
            (
                _route_total_seconds(
                    segments
                )
                if available
                else None
            )
        )

    best_order = None
    best_segments = None
    best_seconds = None

    for order_tuple in itertools.permutations(
        spots_for_day
    ):

        order = list(
            order_tuple
        )

        segments = (
            _route_candidate_segments(
                origin,
                order,
                destination,
                car,
                walking_amount
            )
        )

        if not segments:
            continue

        if not all(
            segment.get(
                "available"
            )
            for segment in segments
        ):
            continue

        seconds = (
            _route_total_seconds(
                segments
            )
        )

        if (
            best_seconds is None
            or
            seconds < best_seconds
        ):

            best_order = order
            best_segments = segments
            best_seconds = seconds

    if best_order is None:

        fallback_order = spots_for_day

        fallback_segments = (
            _route_candidate_segments(
                origin,
                fallback_order,
                destination,
                car,
                walking_amount
            )
        )

        return (
            fallback_order,
            fallback_segments,
            None
        )

    return (
        best_order,
        best_segments,
        best_seconds
    )



def _s1_day_total_minutes(
    spots_for_day,
    route_seconds
):
    """
    移動 + 滞在 + 昼食60分。
    """
    stay_minutes = sum(
        _s1_stay_minutes(
            spot
        )
        for spot in (
            spots_for_day
            or []
        )
    )

    travel_minutes = (
        int(
            round(
                route_seconds
                /
                60
            )
        )
        if route_seconds
        is not None
        else 0
    )

    lunch_minutes = (
        60
        if spots_for_day
        else 0
    )

    return (
        travel_minutes
        +
        stay_minutes
        +
        lunch_minutes
    )


def build_s1_route_aware_spot_plan(
    spot_score_items,
    recommended_hotel,
    days,
    age,
    start_point,
    car,
    walking_amount,
    must_visit_names=None
):
    """
    S1前半。

    行きたい場所を先に配置し、
    残りは 推薦点 - 0.3×追加移動時間 で決める。
    """
    must_visit_names = list(
        must_visit_names
        or []
    )

    day_settings = (
        _s1_day_settings(
            days,
            age
        )
    )

    day_count = len(
        day_settings
    )

    day_spots = [
        []
        for _ in range(
            day_count
        )
    ]

    score_by_name = {
        str(
            item.get(
                "name",
                ""
            )
        ):
            item
        for item in (
            spot_score_items
            or []
        )
    }

    ranked_items = sorted(
        spot_score_items
        or [],
        key=lambda item:
            item.get(
                "score",
                0
            ),
        reverse=True
    )

    # リアルタイム応答を優先し、通常候補は上位8件まで。
    # 行きたい場所は順位に関係なく必ず追加する。
    # 最終候補だけ実道路ルートで比較することで、
    # ORSへの大量リクエストを防ぐ。
    candidate_items = list(
        ranked_items[:8]
    )

    candidate_names = {
        item.get(
            "name",
            ""
        )
        for item in
        candidate_items
    }

    for must_name in must_visit_names:

        item = score_by_name.get(
            must_name
        )

        if (
            item
            and
            must_name
            not in candidate_names
        ):

            candidate_items.append(
                item
            )

            candidate_names.add(
                must_name
            )

    used_names = set()
    unavailable_must_visit = []

    def day_origin_destination(
        day_index
    ):

        origin = (
            start_point
            if day_index == 0
            else recommended_hotel
        )

        destination = (
            start_point
            if day_index
            ==
            day_count - 1
            else recommended_hotel
        )

        return (
            origin,
            destination
        )

    def evaluate_day(
        day_index,
        candidate_spots
    ):

        (
            origin,
            destination
        ) = day_origin_destination(
            day_index
        )

        (
            order,
            segments,
            route_seconds
        ) = _s1_shortest_day_route(
            origin,
            candidate_spots,
            destination,
            car,
            walking_amount
        )

        if route_seconds is None:
            return None

        total_minutes = (
            _s1_day_total_minutes(
                order,
                route_seconds
            )
        )

        return {
            "order":
                order,
            "segments":
                segments,
            "route_seconds":
                route_seconds,
            "total_minutes":
                total_minutes
        }

    # 行きたい場所を先に配置
    for must_name in must_visit_names:

        item = score_by_name.get(
            must_name
        )

        if not item:

            unavailable_must_visit.append(
                must_name
            )
            continue

        spot = item.get(
            "spot"
        )

        best_choice = None

        for day_index in range(
            day_count
        ):

            setting = (
                day_settings[
                    day_index
                ]
            )

            if (
                len(
                    day_spots[
                        day_index
                    ]
                )
                >=
                setting[
                    "max_spots"
                ]
            ):
                continue

            evaluation = (
                evaluate_day(
                    day_index,
                    day_spots[
                        day_index
                    ]
                    +
                    [
                        spot
                    ]
                )
            )

            if not evaluation:
                continue

            if (
                evaluation[
                    "total_minutes"
                ]
                >
                setting[
                    "minutes"
                ]
            ):
                continue

            choice_key = (
                evaluation[
                    "total_minutes"
                ],
                evaluation[
                    "route_seconds"
                ]
            )

            if (
                best_choice is None
                or
                choice_key
                <
                best_choice[
                    "choice_key"
                ]
            ):

                best_choice = {
                    "day_index":
                        day_index,
                    "evaluation":
                        evaluation,
                    "choice_key":
                        choice_key
                }

        if best_choice is None:

            unavailable_must_visit.append(
                must_name
            )
            continue

        target_day = (
            best_choice[
                "day_index"
            ]
        )

        day_spots[
            target_day
        ] = (
            best_choice[
                "evaluation"
            ][
                "order"
            ]
        )

        used_names.add(
            must_name
        )

    # 残り時間を推薦点と追加移動時間で埋める
    day_first_candidate_value = [
        None
        for _ in range(
            day_count
        )
    ]

    for day_index in range(
        day_count
    ):

        setting = (
            day_settings[
                day_index
            ]
        )

        while (
            len(
                day_spots[
                    day_index
                ]
            )
            <
            setting[
                "max_spots"
            ]
        ):

            current_eval = (
                evaluate_day(
                    day_index,
                    day_spots[
                        day_index
                    ]
                )
            )

            current_route_minutes = (
                (
                    current_eval[
                        "route_seconds"
                    ]
                    /
                    60
                )
                if current_eval
                else 0
            )

            best_candidate = None

            for item in candidate_items:

                name = str(
                    item.get(
                        "name",
                        ""
                    )
                )

                if (
                    not name
                    or
                    name in used_names
                ):
                    continue

                spot = item.get(
                    "spot"
                )

                evaluation = (
                    evaluate_day(
                        day_index,
                        day_spots[
                            day_index
                        ]
                        +
                        [
                            spot
                        ]
                    )
                )

                if not evaluation:
                    continue

                if (
                    evaluation[
                        "total_minutes"
                    ]
                    >
                    setting[
                        "minutes"
                    ]
                ):
                    continue

                new_route_minutes = (
                    evaluation[
                        "route_seconds"
                    ]
                    /
                    60
                )

                added_travel_minutes = max(
                    0,
                    new_route_minutes
                    -
                    current_route_minutes
                )

                candidate_value = (
                    float(
                        item.get(
                            "score",
                            0
                        )
                    )
                    -
                    0.3
                    *
                    added_travel_minutes
                )

                first_value = (
                    day_first_candidate_value[
                        day_index
                    ]
                )

                if (
                    first_value is not None
                    and
                    candidate_value
                    <
                    first_value
                    *
                    0.9
                ):
                    continue

                if (
                    best_candidate is None
                    or
                    candidate_value
                    >
                    best_candidate[
                        "candidate_value"
                    ]
                ):

                    best_candidate = {
                        "item":
                            item,
                        "evaluation":
                            evaluation,
                        "candidate_value":
                            candidate_value
                    }

            if best_candidate is None:
                break

            selected_item = (
                best_candidate[
                    "item"
                ]
            )

            selected_name = str(
                selected_item.get(
                    "name",
                    ""
                )
            )

            if (
                day_first_candidate_value[
                    day_index
                ]
                is None
            ):

                day_first_candidate_value[
                    day_index
                ] = (
                    best_candidate[
                        "candidate_value"
                    ]
                )

            day_spots[
                day_index
            ] = (
                best_candidate[
                    "evaluation"
                ][
                    "order"
                ]
            )

            used_names.add(
                selected_name
            )

    planned_names = [
        str(
            spot.get(
                "name",
                ""
            )
        )
        for day in day_spots
        for spot in day
    ]

    selected_score_items = [
        score_by_name[
            name
        ]
        for name in planned_names
        if name in score_by_name
    ]

    return {
        "day_spots":
            day_spots,
        "selected_score_items":
            selected_score_items,
        "unavailable_must_visit":
            unavailable_must_visit,
        "day_settings":
            day_settings
    }



def _s1_plan_travel_minutes(
    plan,
    hotel,
    start_point,
    car,
    walking_amount
):
    """S1旅程全体の純粋な移動時間（分）。"""
    if not plan:
        return None

    day_spots = list(
        plan.get("day_spots")
        or []
    )

    total_seconds = 0

    for day_index, spots_for_day in enumerate(day_spots):

        origin = (
            start_point
            if day_index == 0
            else hotel
        )

        destination = (
            start_point
            if day_index == len(day_spots) - 1
            else hotel
        )

        (
            _order,
            _segments,
            route_seconds
        ) = _s1_shortest_day_route(
            origin,
            spots_for_day,
            destination,
            car,
            walking_amount
        )

        if route_seconds is None:
            return None

        total_seconds += route_seconds

    return int(
        round(
            total_seconds / 60
        )
    )


def build_s1_best_hotel_plan(
    hotel_score_items,
    spot_score_items,
    days,
    age,
    start_point,
    car,
    walking_amount,
    must_visit_names=None,
    max_hotels=5
):
    """
    S1後半。

    宿上位5軒ごとにS1旅程を作り、
    観光地点数合計 - 0.3×移動時間 + 宿点数
    が最大の旅行全体を採用する。

    上位5軒のどれでも必須観光地を入れられない場合は、
    残りの宿も試す。
    """
    ranked_hotels = sorted(
        hotel_score_items or [],
        key=lambda item:
            float(
                item.get(
                    "score",
                    0
                )
                or 0
            ),
        reverse=True
    )

    if not ranked_hotels:
        return None

    must_visit_names = list(
        must_visit_names
        or []
    )

    initial_candidates = (
        ranked_hotels[
            :max_hotels
        ]
    )

    remaining_candidates = (
        ranked_hotels[
            max_hotels:
        ]
    )

    def evaluate_candidates(
        candidates
    ):

        evaluations = []

        for hotel_item in candidates:

            hotel = (
                hotel_item.get(
                    "hotel"
                )
            )

            if not isinstance(
                hotel,
                dict
            ):
                continue

            plan = (
                build_s1_route_aware_spot_plan(

                    spot_score_items=
                        spot_score_items,

                    recommended_hotel=
                        hotel,

                    days=
                        days,

                    age=
                        age,

                    start_point=
                        start_point,

                    car=
                        car,

                    walking_amount=
                        walking_amount,

                    must_visit_names=
                        must_visit_names

                )
            )

            if not plan:
                continue

            unavailable = list(
                plan.get(
                    "unavailable_must_visit"
                )
                or []
            )

            selected_items = list(
                plan.get(
                    "selected_score_items"
                )
                or []
            )

            travel_minutes = (
                _s1_plan_travel_minutes(

                    plan,
                    hotel,
                    start_point,
                    car,
                    walking_amount

                )
            )

            if travel_minutes is None:
                continue

            spot_score_total = sum(
                float(
                    item.get(
                        "score",
                        0
                    )
                    or 0
                )
                for item in
                selected_items
            )

            hotel_score = float(
                hotel_item.get(
                    "score",
                    0
                )
                or 0
            )

            total_value = (
                spot_score_total
                -
                0.3
                *
                travel_minutes
                +
                hotel_score
            )

            # 必須観光地を入れられない案は優先しない。
            total_value -= (
                1000
                *
                len(
                    unavailable
                )
            )

            evaluations.append({

                "hotel_item":
                    hotel_item,

                "plan":
                    plan,

                "travel_minutes":
                    travel_minutes,

                "spot_score_total":
                    spot_score_total,

                "hotel_score":
                    hotel_score,

                "total_value":
                    total_value,

                "unavailable_must_visit":
                    unavailable

            })

        return evaluations

    evaluations = (
        evaluate_candidates(
            initial_candidates
        )
    )

    # 上位5軒で必須観光地を満たせない場合のみ、
    # 残りの宿も追加で比較する。
    if (
        must_visit_names
        and
        (
            not evaluations
            or
            all(
                item.get(
                    "unavailable_must_visit"
                )
                for item in
                evaluations
            )
        )
        and
        remaining_candidates
    ):

        evaluations.extend(
            evaluate_candidates(
                remaining_candidates
            )
        )

    if not evaluations:
        return None

    evaluations.sort(
        key=lambda item: (
            len(
                item.get(
                    "unavailable_must_visit",
                    []
                )
            ),
            -float(
                item.get(
                    "total_value",
                    -10**9
                )
            )
        )
    )

    best = evaluations[0]

    return {
        **best,
        "evaluated_hotel_count":
            len(
                evaluations
            )
    }


def _decorate_hotel_from_score_item(
    hotel_item,
    age,
    people,
    member,
    car,
    days,
    budget,
    purpose,
    travel_date,
    season
):
    """hotel_scoresの項目を表示用宿データへ変換する。"""
    hotel = (
        attach_map_data(
            hotel_item[
                "hotel"
            ]
        )
    )

    hotel[
        "score"
    ] = hotel_item[
        "score"
    ]

    hotel[
        "reasons"
    ] = hotel_item[
        "reasons"
    ]

    hotel = (
        attach_score_visualization(

            hotel,

            hotel_item[
                "breakdown"
            ]

        )
    )

    hotel[
        "recommendation_reason"
    ] = (

        build_recommendation_reason(

            hotel,

            hotel_item[
                "reasons"
            ],

            age,
            people,
            member,
            car,
            days,
            budget,
            purpose,
            travel_date,
            season,

            category=
                "hotel"

        )

    )

    return normalize_place_for_display(hotel)
def _decorate_restaurant_from_score_item(
    restaurant_item
):
    """restaurant_scoresの項目を表示用飲食店データへ変換する。"""
    restaurant = (
        attach_map_data(
            restaurant_item[
                "restaurant"
            ]
        )
    )

    restaurant[
        "score"
    ] = restaurant_item[
        "score"
    ]

    restaurant[
        "reasons"
    ] = restaurant_item[
        "reasons"
    ]

    restaurant = (
        attach_score_visualization(

            restaurant,

            restaurant_item[
                "breakdown"
            ]

        )
    )

    return normalize_place_for_display(restaurant)
def _route_minutes_between_places(
    origin,
    destination,
    car,
    walking_amount
):
    """2地点間のルート時間（分）。取得できない場合はNone。"""
    if (
        origin is None
        or
        destination is None
    ):
        return None

    route = (
        calculate_route_between(

            origin,
            destination,
            car,
            walking_amount

        )
    )

    if not route:
        return None

    try:

        return (
            float(
                route.get(
                    "duration_seconds",
                    0
                )
            )
            /
            60
        )

    except (
        TypeError,
        ValueError
    ):

        return None



def _hotel_dinner_available(
    hotel
):
    """
    S13の夕食判定。
    plan_extra.jsonをまだ直接読んでいない環境でも、
    既存フィールドと確認済み宿名で判定する。
    """
    if not isinstance(
        hotel,
        dict
    ):
        return False

    dinner = hotel.get(
        "dinner"
    )

    if isinstance(
        dinner,
        bool
    ):
        return dinner

    dinner_text = str(
        dinner
        or ""
    ).strip().lower()

    if dinner_text in {
        "あり",
        "有",
        "true",
        "yes",
        "1",
        "夕食あり",
        "夕朝食あり"
    }:
        return True

    if dinner_text in {
        "なし",
        "無",
        "false",
        "no",
        "0",
        "夕食なし"
    }:
        return False

    name = str(
        hotel.get(
            "name"
        )
        or ""
    )

    confirmed_with_dinner = {
        "和どう",
        "新木鉱泉",
        "NIPPONIA 秩父 門前町",
        "NIPPONIA秩父 門前町",
        "ホテルルートインGrand秩父",
        "ホテル美やま",
        "はなのや",
        "PICA秩父",
        "御宿 竹取物語"
    }

    return any(
        key in name
        for key in
        confirmed_with_dinner
    )


def _s13_best_restaurant_between(
    restaurant_score_items,
    previous_place,
    next_place,
    used_names,
    car,
    walking_amount,
    candidate_limit=4
):
    """
    前地点→店→次地点の寄り道が少ない昼食店を選ぶ。
    店の値 = S6点数 - 0.3×寄り道時間。
    """
    direct_minutes = (
        _route_minutes_between_places(

            previous_place,
            next_place,
            car,
            walking_amount

        )
    )

    best = None

    for item in sorted(
        restaurant_score_items or [],
        key=lambda x:
            float(
                x.get(
                    "score",
                    0
                )
                or 0
            ),
        reverse=True
    )[:candidate_limit]:

        restaurant = (
            item.get(
                "restaurant"
            )
        )

        if not isinstance(
            restaurant,
            dict
        ):
            continue

        name = str(
            restaurant.get(
                "name"
            )
            or ""
        )

        if (
            not name
            or
            name in used_names
        ):
            continue

        first_minutes = (
            _route_minutes_between_places(

                previous_place,
                restaurant,
                car,
                walking_amount

            )
        )

        second_minutes = (
            _route_minutes_between_places(

                restaurant,
                next_place,
                car,
                walking_amount

            )
        )

        if (
            first_minutes is None
            or
            second_minutes is None
        ):
            continue

        if direct_minutes is None:

            detour_minutes = (
                first_minutes
                +
                second_minutes
            )

        else:

            detour_minutes = max(
                0,
                first_minutes
                +
                second_minutes
                -
                direct_minutes
            )

        value = (
            float(
                item.get(
                    "score",
                    0
                )
                or 0
            )
            -
            0.3
            *
            detour_minutes
        )

        if (
            best is None
            or
            value
            >
            best[
                "value"
            ]
        ):

            best = {

                "item":
                    item,

                "detour_minutes":
                    round(
                        detour_minutes,
                        1
                    ),

                "value":
                    value

            }

    return best



def _s13_best_restaurant_near_hotel(
    restaurant_score_items,
    hotel,
    used_names,
    car,
    walking_amount,
    candidate_limit=4
):
    """夕食なし宿の場合に、宿から近い店を選ぶ。"""
    best = None

    for item in sorted(
        restaurant_score_items or [],
        key=lambda x:
            float(
                x.get(
                    "score",
                    0
                )
                or 0
            ),
        reverse=True
    )[:candidate_limit]:

        restaurant = (
            item.get(
                "restaurant"
            )
        )

        if not isinstance(
            restaurant,
            dict
        ):
            continue

        name = str(
            restaurant.get(
                "name"
            )
            or ""
        )

        if (
            not name
            or
            name in used_names
        ):
            continue

        minutes = (
            _route_minutes_between_places(

                hotel,
                restaurant,
                car,
                walking_amount

            )
        )

        if minutes is None:
            continue

        value = (
            float(
                item.get(
                    "score",
                    0
                )
                or 0
            )
            -
            0.3
            *
            minutes
        )

        if (
            best is None
            or
            value
            >
            best[
                "value"
            ]
        ):

            best = {

                "item":
                    item,

                "distance_minutes":
                    round(
                        minutes,
                        1
                    ),

                "value":
                    value

            }

    return best



def build_s13_meal_schedule(
    restaurant_score_items,
    day_spots,
    hotel,
    start_point,
    car,
    walking_amount
):
    """
    S13 食事組み込み。

    ・昼食は1件目の観光地と次地点の間
    ・夕食なし宿の宿泊日のみ夕食候補
    ・同じ飲食店は重複させない
    """
    day_spots = list(
        day_spots
        or []
    )

    used_names = set()
    meals = []
    day_count = len(
        day_spots
    )

    for day_index, spots_for_day in enumerate(
        day_spots
    ):

        spots_for_day = list(
            spots_for_day
            or []
        )

        if not spots_for_day:
            continue

        previous_place = (
            spots_for_day[
                0
            ]
        )

        if len(
            spots_for_day
        ) >= 2:

            next_place = (
                spots_for_day[
                    1
                ]
            )

        else:

            next_place = (
                start_point
                if day_index
                ==
                day_count - 1
                else hotel
            )

        lunch = (
            _s13_best_restaurant_between(

                restaurant_score_items,
                previous_place,
                next_place,
                used_names,
                car,
                walking_amount

            )
        )

        if lunch:

            item = lunch[
                "item"
            ]

            name = str(
                item.get(
                    "name"
                )
                or ""
            )

            used_names.add(
                name
            )

            meals.append({

                "day":
                    day_index + 1,

                "meal_type":
                    "昼食",

                "restaurant_item":
                    item,

                "detour_minutes":
                    lunch.get(
                        "detour_minutes"
                    ),

                "distance_minutes":
                    None,

                "note":
                    "観光ルート途中で寄り道が少ない店を優先"

            })

        # 最終日は宿泊しないため夕食を組まない。
        if (
            day_index
            >=
            day_count - 1
        ):
            continue

        # 宿で夕食が出る場合は外食夕食を出さない。
        if _hotel_dinner_available(
            hotel
        ):
            continue

        dinner = (
            _s13_best_restaurant_near_hotel(

                restaurant_score_items,
                hotel,
                used_names,
                car,
                walking_amount

            )
        )

        if dinner:

            item = dinner[
                "item"
            ]

            name = str(
                item.get(
                    "name"
                )
                or ""
            )

            used_names.add(
                name
            )

            meals.append({

                "day":
                    day_index + 1,

                "meal_type":
                    "夕食",

                "restaurant_item":
                    item,

                "detour_minutes":
                    None,

                "distance_minutes":
                    dinner.get(
                        "distance_minutes"
                    ),

                "note":
                    "夕食なしの宿のため、宿から近い店を優先"

            })

    return meals


def optimize_day_route(
    origin,
    spots_for_day,
    destination,
    car,
    walking_amount
):
    """
    1日最大3件までの観光地順序を全通り比較し、
    実ルート時間が最短の順番を採用する。
    """
    spots_for_day = list(
        spots_for_day
        or []
    )

    if len(spots_for_day) <= 3:

        (
            order,
            segments,
            _
        ) = _s1_shortest_day_route(
            origin,
            spots_for_day,
            destination,
            car,
            walking_amount
        )

        return (
            order,
            segments
        )

    segments = (
        _route_candidate_segments(
            origin,
            spots_for_day,
            destination,
            car,
            walking_amount
        )
    )

    return (
        spots_for_day,
        segments
    )



def distribute_spots_by_days(
    recommended_spots,
    days
):
    """
    旅行ペースで件数が変わっても、
    日ごとの件数が極端にならないよう均等に配分する。
    """

    spots_copy = list(
        recommended_spots
        or
        []
    )

    day_count = (
        2
        if days == "1泊2日"
        else 3
    )

    result = [
        []
        for _ in range(
            day_count
        )
    ]

    for index, spot in enumerate(
        spots_copy
    ):
        result[
            index
            %
            day_count
        ].append(
            spot
        )

    return result


def build_trip_routes(
    recommended_spots,
    recommended_hotel,
    days,
    start_point,
    car,
    walking_amount,
    preplanned_days=None
):
    """
    旅行全体の移動区間を作る。

    1日目:
      開始地点 → 観光地 → 宿

    中日:
      宿 → 観光地 → 宿

    最終日:
      宿 → 観光地 → 開始地点

    S1の日割りがある場合は維持し、
    各日の最大3施設について最短順を再確認する。
    """


    # 車専用システムのため、常にローカル車ルートを作成する。
    if preplanned_days is not None:

        distributed = [
            list(
                day
                or []
            )
            for day in
            preplanned_days
        ]

    else:

        distributed = (
            distribute_spots_by_days(
                recommended_spots,
                days
            )
        )

    optimized_days = []
    route_days = []

    for index, day_spots in enumerate(
        distributed
    ):

        is_first_day = (
            index == 0
        )

        is_last_day = (
            index
            ==
            len(distributed)
            -
            1
        )

        origin = (
            start_point
            if is_first_day
            else recommended_hotel
        )

        destination = (
            start_point
            if is_last_day
            else recommended_hotel
        )

        (
            optimized_spots,
            segments

        ) = optimize_day_route(

            origin,
            day_spots,
            destination,
            car,
            walking_amount

        )

        optimized_days.append(
            optimized_spots
        )

        route_days.append({
            "day":
                index + 1,
            "segments":
                segments,
            "total_duration_seconds":
                _route_total_seconds(
                    segments
                ),
            "total_duration_text":
                (
                    _format_duration(
                        _route_total_seconds(
                            segments
                        )
                    )
                    if any(
                        segment.get(
                            "available"
                        )
                        for segment in
                        segments
                    )
                    else None
                ),
            "total_distance_meters":
                (
                    _route_total_distance(
                        segments
                    )
                    if any(
                        segment.get(
                            "available"
                        )
                        for segment in
                        segments
                    )
                    else None
                ),
            "total_distance_text":
                (
                    _format_distance(
                        _route_total_distance(
                            segments
                        )
                    )
                    if any(
                        segment.get(
                            "available"
                        )
                        for segment in
                        segments
                    )
                    else None
                ),
            "all_routes_available":
                all(
                    segment.get(
                        "available"
                    )
                    for segment in
                    segments
                )
                if segments
                else True
        })

    while len(optimized_days) < 3:
        optimized_days.append(
            []
        )

    all_segments = [
        segment

        for route_day in route_days

        for segment in
            route_day.get(
                "segments",
                []
            )
    ]

    available_segments = [
        segment

        for segment in all_segments

        if segment.get(
            "available"
        )
    ]

    total_seconds = (
        _route_total_seconds(
            available_segments
        )
    )

    total_distance = (
        _route_total_distance(
            available_segments
        )
    )

    summary = {
        "enabled":
            bool(
                route_matrix_routes
            ),
        "provider":
            (
                "OpenStreetMap + OSMnx local route matrix"
                if route_matrix_routes
                else None
            ),
        "total_duration_seconds":
            total_seconds,
        "total_duration_text":
            (
                _format_duration(
                    total_seconds
                )
                if available_segments
                else None
            ),
        "total_distance_meters":
            total_distance,
        "total_distance_text":
            (
                _format_distance(
                    total_distance
                )
                if available_segments
                else None
            ),
        "segment_count":
            len(
                all_segments
            ),
        "available_segment_count":
            len(
                available_segments
            ),
        "complete":
            (
                len(
                    all_segments
                )
                ==
                len(
                    available_segments
                )
            )
            if all_segments
            else True,
        "note":
            (
                "OpenStreetMap道路データを基に事前計算した車ルート値"
                if route_matrix_routes
                else
                "ローカルルートデータを読み込めませんでした"
            )
    }

    return (
        optimized_days[0],
        optimized_days[1],
        optimized_days[2],
        route_days,
        summary
    )


def _favorite_catalog_item(
    item,
    category
):

    """
    お気に入り専用画面向けに、
    既存データから詳細表示用の情報をまとめる。

    新しい情報は推測せず、
    既存データまたは41施設マスターの値だけを利用する。
    """

    copied = item.copy()


    if category in (
        "観光地",
        "宿泊施設"
    ):

        master = facility_master.get(
            copied.get("name", ""),
            {}
        )


        if not isinstance(
            master,
            dict
        ):
            master = {}


        basic = (
            master.get("basic")

            if isinstance(
                master.get("basic"),
                dict
            )

            else {}
        )


        master_access = (
            master.get("access")

            if isinstance(
                master.get("access"),
                dict
            )

            else {}
        )


        copied["area"] = (
            copied.get("area")
            or
            basic.get("area")
        )


        copied["type"] = (
            copied.get("type")
            or
            basic.get("type")
        )


        copied["time"] = (

            copied.get("time")

            if copied.get("time")
            is not None

            else basic.get(
                "stay_time_hours"
            )

        )


        copied["description"] = (
            copied.get("description")
            or
            master.get("description")
        )


        copied["address"] = (
            copied.get("address")
            or
            master.get("address")
            or
            basic.get("address")
        )


        copied["phone"] = (
            copied.get("phone")
            or
            master.get("phone")
        )


        copied["hours"] = (
            copied.get("hours")
            or
            master.get("hours")
        )


        copied["price"] = (
            copied.get("price")
            or
            master.get("price")
        )


        copied["closed"] = (
            copied.get("closed")
            or
            master.get("closed")
        )


        copied["parking"] = (
            copied.get("parking")
            or
            master.get("parking")
        )


        copied["season"] = (
            copied.get("season")
            or
            master.get("season")
        )


        copied["notes"] = (
            copied.get("notes")
            or
            master.get("notes")
        )


        copied["car_free"] = (
            copied.get("car_free")
            or
            master.get("car_free")
        )


        copied["required_reservation"] = (
            copied.get(
                "required_reservation"
            )
            or
            master.get(
                "required_reservation"
            )
        )


        copied["access"] = (
            copied.get("access")
            or
            master_access
        )


        copied["url"] = (
            copied.get("url")
            or
            master.get("official_url")
            or
            master.get("source")
        )


    if category == "飲食店":

        copied["url"] = (
            copied.get(
                "official_url"
            )
            or
            copied.get("url")
            or
            ""
        )


    copied = attach_map_data(
        copied
    )


    copied["favorite_type"] = (
        category
    )


    return {

        "type":
            category,

        "name":
            copied.get(
                "name",
                ""
            ),

        "address":
            copied.get(
                "address"
            ) or "",

        "area":
            copied.get(
                "area"
            ) or "",

        "category_detail":
            copied.get(
                "type"
            ) or "",

        "description":
            copied.get(
                "description"
            ) or "",

        "time":
            copied.get(
                "time"
            ),

        "phone":
            copied.get(
                "phone"
            ) or "",

        "hours":
            copied.get(
                "hours"
            ) or "",

        "price":
            copied.get(
                "price"
            ) or "",

        "closed":
            copied.get(
                "closed"
            ) or "",

        "parking":
            copied.get(
                "parking"
            ) or "",

        "season":
            copied.get(
                "season"
            ) or "",

        "notes":
            copied.get(
                "notes"
            ) or "",

        "car_free":
            copied.get(
                "car_free"
            ) or "",

        "required_reservation":
            copied.get(
                "required_reservation"
            ) or "",

        "access":
            (
                copied.get("access")

                if isinstance(
                    copied.get("access"),
                    dict
                )

                else {}
            ),

        "url":
            (
                copied.get("url")
                or
                copied.get(
                    "official_url"
                )
                or
                ""
            ),

        "map_url":
            copied.get(
                "map_url"
            ) or ""

    }


def build_favorite_catalog():

    """
    観光地・飲食店・宿泊施設の既存データから
    お気に入り画面用カタログを作る。
    """

    catalog = {

        "観光地": [

            _favorite_catalog_item(
                item,
                "観光地"
            )

            for item in spots

        ],


        "飲食店": [

            _favorite_catalog_item(
                item,
                "飲食店"
            )

            for item in restaurants

        ],


        "宿泊施設": [

            _favorite_catalog_item(
                item,
                "宿泊施設"
            )

            for item in hotels

        ]

    }


    return catalog


def normalize_list(value):

    if value is None:
        return []

    if isinstance(
        value,
        list
    ):
        return value

    return [
        value
    ]


def price_number(price_text):

    if not price_text:
        return None


    numbers = re.findall(
        r"\d[\d,]*",
        str(price_text)
    )


    if not numbers:
        return None


    try:

        return int(
            numbers[0].replace(
                ",",
                ""
            )
        )


    except (
        ValueError,
        TypeError
    ):

        return None


# =========================================================
# 季節判定
# =========================================================

def get_season_from_date(
    travel_date
):

    """
    旅行予定日から基本の四季を判定する。

    12～2月：冬
    3～5月：春
    6～8月：夏
    9～11月：秋
    """

    if not travel_date:
        return None


    try:

        month = datetime.strptime(
            travel_date,
            "%Y-%m-%d"
        ).month


    except (
        ValueError,
        TypeError
    ):

        return None


    if month in (
        12,
        1,
        2
    ):
        return "冬"


    if month in (
        3,
        4,
        5
    ):
        return "春"


    if month in (
        6,
        7,
        8
    ):
        return "夏"


    return "秋"


# =========================================================
# 移動・旅行ペース設定（第1段階）
# =========================================================

WALKING_AMOUNT_OPTIONS = {
    "少なめ",
    "普通",
    "多め"
}

TRAVEL_PACE_OPTIONS = {
    "ゆっくり",
    "普通",
    "たくさん回りたい"
}

START_POINT_OPTIONS = {
    "花園IC",
    "芦ヶ久保駅"
}


def normalize_travel_preferences(
    walking_amount,
    travel_pace,
    start_point
):
    """
    新しい移動条件を安全な値に整える。

    第1段階では推薦点数そのものはまだ変更せず、
    後の距離・移動時間評価で利用する入力値として保持する。
    """

    walking_amount = str(
        walking_amount or "普通"
    ).strip()

    travel_pace = str(
        travel_pace or "普通"
    ).strip()

    default_start = (
        REGION_CONFIG
        .get(ACTIVE_REGION_CODE, REGION_CONFIG["chichibu"])
        .get("default_arrival", "花園IC")
    )

    start_point = str(
        start_point or default_start
    ).strip()

    if walking_amount not in WALKING_AMOUNT_OPTIONS:
        walking_amount = "普通"

    if travel_pace not in TRAVEL_PACE_OPTIONS:
        travel_pace = "普通"

    if start_point not in START_POINT_OPTIONS:
        start_point = default_start

    return (
        walking_amount,
        travel_pace,
        start_point
    )


def normalize_walking_difficulty(value):
    """
    施設ごとに表現が異なる歩行負担を
    low / medium / high の3段階へ正規化する。

    情報がない場合は None とし、推測で補完しない。
    """

    if value is None:
        return None

    text = str(value).strip().lower()

    low_values = {
        "low",
        "easy",
        "低",
        "少",
        "少ない",
        "低い",
        "軽い",
        "容易"
    }

    medium_values = {
        "medium",
        "normal",
        "中",
        "普通",
        "中程度",
        "標準"
    }

    high_values = {
        "high",
        "hard",
        "高",
        "多",
        "多い",
        "高い",
        "重い",
        "困難"
    }

    if text in low_values:
        return "low"

    if text in medium_values:
        return "medium"

    if text in high_values:
        return "high"

    return None


def calculate_walking_preference_effect(
    walking_amount,
    difficulty_value
):
    """
    利用者が自分で選んだ「歩く量」と、
    施設側の歩行負担の組み合わせだけを評価する。

    年齢から体力を推測しない。
    施設側の歩行負担情報が不明な場合は0点とする。
    """

    difficulty = normalize_walking_difficulty(
        difficulty_value
    )

    if difficulty is None:
        return (
            0,
            "歩行負担データがないため加減点なし"
        )

    score_table = {
        "少なめ": {
            "low": 18,
            "medium": -8,
            "high": -22
        },
        "普通": {
            "low": 10,
            "medium": 8,
            "high": -8
        },
        "多め": {
            "low": 4,
            "medium": 12,
            "high": 15
        }
    }

    reason_table = {
        "少なめ": {
            "low": "歩く量を少なめにした希望と合う",
            "medium": "希望より歩行負担がやや大きい",
            "high": "歩く量を少なめにした希望に対して負担が大きい"
        },
        "普通": {
            "low": "無理なく立ち寄りやすい",
            "medium": "標準的な歩行量の希望と合う",
            "high": "標準的な希望より歩行負担が大きい"
        },
        "多め": {
            "low": "歩行負担は小さい",
            "medium": "歩くことを楽しみたい希望と合う",
            "high": "歩く量を多めにした希望と合う"
        }
    }

    selected = (
        walking_amount
        if walking_amount in score_table
        else "普通"
    )

    return (
        score_table[selected][difficulty],
        reason_table[selected][difficulty]
    )


def get_spot_target_count(
    days,
    travel_pace
):
    """
    旅行ペースは施設単体の好みではなく、
    1日にどれくらい立ち寄るかへ反映する。

    1泊2日:
      ゆっくり 2件 / 普通 3件 / たくさん 4件

    2泊3日:
      ゆっくり 4件 / 普通 5件 / たくさん 6件
    """

    pace = (
        travel_pace
        if travel_pace in TRAVEL_PACE_OPTIONS
        else "普通"
    )

    if days == "1泊2日":
        return {
            "ゆっくり": 2,
            "普通": 3,
            "たくさん回りたい": 4
        }[pace]

    return {
        "ゆっくり": 4,
        "普通": 5,
        "たくさん回りたい": 6
    }[pace]


def make_recommendation_seed(
    age,
    gender,
    people,
    member,
    car,
    days,
    budget,
    purpose,
    travel_date="",
    walking_amount="普通",
    travel_pace="普通",
    start_point="西武秩父駅"
):

    purpose_text = (

        "|".join(
            sorted(
                purpose
            )
        )

        if isinstance(
            purpose,
            list
        )

        else str(
            purpose
        )

    )


    source = (
        f"{age}|"
        f"{gender}|"
        f"{people}|"
        f"{member}|"
        f"{car}|"
        f"{days}|"
        f"{budget}|"
        f"{purpose_text}|"
        f"{travel_date}|"
        f"{walking_amount}|"
        f"{travel_pace}|"
        f"{start_point}"
    )


    digest = hashlib.sha256(
        source.encode(
            "utf-8"
        )
    ).hexdigest()


    return int(
        digest[:16],
        16
    )


SEASON_MONTHS = {

    "冬":
        {
            12,
            1,
            2
        },

    "春":
        {
            3,
            4,
            5
        },

    "夏":
        {
            6,
            7,
            8
        },

    "秋":
        {
            9,
            10,
            11
        }

}


def _season_text(*values):

    return " ".join(

        str(v)

        for v in values

        if v

    )


def _month_in_closed_range(
    travel_date,
    text
):

    """
    明示された月範囲だけを確認する。
    推測で範囲を作らない。
    """

    if (
        not travel_date
        or
        not text
    ):

        return None


    try:

        dt = datetime.strptime(
            travel_date,
            "%Y-%m-%d"
        )


    except (
        ValueError,
        TypeError
    ):

        return None


    ranges = re.findall(

        r"(\d{1,2})月"
        r"(?:\d{1,2}日)?"
        r"[^〜～\-]*"
        r"(?:〜|～|\-)"
        r"[^0-9]*"
        r"(\d{1,2})月",

        str(text)

    )


    if not ranges:

        return None


    month = dt.month


    for (
        start_month,
        end_month
    ) in ranges:

        start_month = int(
            start_month
        )

        end_month = int(
            end_month
        )


        if (
            start_month
            <=
            end_month
        ):

            return (
                start_month
                <=
                month
                <=
                end_month
            )


        return (
            month
            >=
            start_month
            or
            month
            <=
            end_month
        )


    return None


def calculate_season_effect(
    item,
    season,
    travel_date
):

    """
    41施設マスターの
    season / best_season / seasonal_operation
    を根拠に季節スコアを計算する。
    """

    if not season:

        return (
            0,
            [],
            False
        )


    season_value = str(
        item.get(
            "season"
        ) or ""
    )


    best_value = str(
        item.get(
            "best_season"
        ) or ""
    )


    operation_value = str(
        item.get(
            "seasonal_operation"
        ) or ""
    )


    closed_value = str(
        item.get(
            "master_closed"
        ) or ""
    )


    combined = _season_text(

        season_value,
        best_value,
        operation_value

    )


    reasons = []

    score = 0

    unavailable = False


    closed_range = (
        _month_in_closed_range(
            travel_date,
            closed_value
        )
    )


    if (
        closed_range is False
        and
        (
            "のみ営業"
            in closed_value
            or
            (
                "営業"
                in closed_value
                and
                "～"
                in closed_value
            )
        )
    ):

        unavailable = True

        reasons.append(
            "旅行予定日が明示された営業期間外"
        )

        return (
            -1000,
            reasons,
            unavailable
        )


    if (
        season == "冬"
        and
        (
            "冬季休業"
            in closed_value
            or
            "冬季休業"
            in combined
        )
    ):

        unavailable = True

        reasons.append(
            "冬季休業の時期に該当"
        )

        return (
            -1000,
            reasons,
            unavailable
        )


    if travel_date:

        try:

            dt = datetime.strptime(
                travel_date,
                "%Y-%m-%d"
            )

        except (
            ValueError,
            TypeError
        ):

            dt = None


        if (
            dt
            and
            str(
                dt.year
            )
            in
            closed_value
        ):

            m = re.search(

                r"(\d{1,2})"
                r"[月/]?"
                r"(\d{1,2})?"
                r"日?"
                r"(?:で)?終了",

                closed_value

            )


            if m:

                end_month = int(
                    m.group(1)
                )

                end_day = int(
                    m.group(2)
                    or
                    1
                )


                if (
                    dt.month,
                    dt.day
                ) > (
                    end_month,
                    end_day
                ):

                    unavailable = True

                    reasons.append(
                        "マスターに記載された今年の営業終了日を過ぎている"
                    )

                    return (
                        -1000,
                        reasons,
                        unavailable
                    )


    if not combined:

        return (
            0,
            reasons,
            unavailable
        )


    if season in best_value:

        score += 30

        reasons.append(
            f"{season}が見頃・適季節として登録されている"
        )


    elif season in operation_value:

        score += 28

        reasons.append(
            f"{season}の季節営業・運用情報がある"
        )


    else:

        month_ranges = re.findall(

            r"(\d{1,2})月"
            r"(?:[^〜～\-]*)"
            r"(?:〜|～|\-)"
            r"[^0-9]*"
            r"(\d{1,2})月",

            season_value

        )


        month_matched = False

        month_known = False


        if (
            month_ranges
            and
            travel_date
        ):

            try:

                dt = datetime.strptime(
                    travel_date,
                    "%Y-%m-%d"
                )

                current_month = (
                    dt.month
                )


                for (
                    start_month,
                    end_month
                ) in month_ranges:

                    start_month = int(
                        start_month
                    )

                    end_month = int(
                        end_month
                    )

                    month_known = True


                    if (
                        start_month
                        <=
                        end_month
                    ):

                        if (
                            start_month
                            <=
                            current_month
                            <=
                            end_month
                        ):

                            month_matched = True
                            break


                    else:

                        if (
                            current_month
                            >=
                            start_month
                            or
                            current_month
                            <=
                            end_month
                        ):

                            month_matched = True
                            break


            except (
                ValueError,
                TypeError
            ):

                pass


        if (
            month_matched
            and
            any(

                word
                in
                season_value

                for word in
                [
                    "見頃",
                    "中心",
                    "営業",
                    "公開"
                ]

            )
        ):

            score += 30

            reasons.append(
                f"旅行予定月が{season_value}に記載された時期と一致する"
            )


        elif (
            month_known
            and
            any(

                word
                in
                season_value

                for word in
                [
                    "見頃",
                    "中心",
                    "営業",
                    "公開"
                ]

            )
        ):

            score -= 10


        if season in season_value:

            score += 20

            reasons.append(
                f"{season}の季節情報が登録されている"
            )


        elif (
            "春～秋"
            in season_value
            or
            "春から秋"
            in season_value
        ):

            if season in {
                "春",
                "夏",
                "秋"
            }:

                score += 16

                reasons.append(
                    "春～秋に適した季節情報が登録されている"
                )

            else:

                score -= 12


        elif (
            "冬～早春"
            in season_value
            or
            "冬から早春"
            in season_value
        ):

            if season == "冬":

                score += 18

                reasons.append(
                    "冬～早春の季節情報が登録されている"
                )

            else:

                score -= 8


        elif "年間" in combined:

            pass


    return (
        score,
        reasons,
        unavailable
    )


# =========================================================
# 条件に合う候補からバランスよく選ぶ
# =========================================================

def diverse_select(
    items,
    target_count,
    seed,
    key_name,
    group_names=None,
    request_nonce=0
):

    if (
        not items
        or
        target_count <= 0
    ):

        return []


    rng = random.Random(

        (
            seed
            ^
            request_nonce
        )
        &
        (
            (1 << 64)
            -
            1
        )

    )


    ranked = []


    for item in items:

        copied = (
            item.copy()
        )


        copied[
            "selection_score"
        ] = (

            item["score"]
            +
            rng.uniform(
                0,
                8
            )

        )


        ranked.append(
            copied
        )


    ranked.sort(

        key=lambda x:
            x[
                "selection_score"
            ],

        reverse=True

    )


    top_score = (
        ranked[0][
            "score"
        ]
    )


    pool = [

        item

        for item in ranked

        if (
            item["score"]
            >=
            top_score - 35
        )

    ]


    minimum_pool = min(

        len(ranked),

        max(
            target_count * 4,
            10
        )

    )


    if len(pool) < minimum_pool:

        pool = (
            ranked[
                :minimum_pool
            ]
        )


    selected = []

    used_keys = set()


    used_groups = {

        name: {}

        for name in
        (
            group_names
            or
            []
        )

    }


    while (
        pool
        and
        len(selected)
        <
        target_count
    ):

        scored_candidates = []


        for item in pool:

            item_key = (
                item.get(
                    key_name
                )
            )


            if item_key in used_keys:
                continue


            value = (
                item[
                    "selection_score"
                ]
            )


            for group_name in (
                group_names
                or
                []
            ):

                group_value = (
                    item.get(
                        group_name
                    )
                )


                if isinstance(
                    group_value,
                    list
                ):

                    group_values = (
                        group_value
                    )

                else:

                    group_values = [
                        group_value
                    ]


                for gv in group_values:

                    if (
                        gv is None
                        or
                        gv == ""
                    ):

                        continue


                    count = (
                        used_groups[
                            group_name
                        ].get(
                            gv,
                            0
                        )
                    )


                    if count >= 2:

                        value -= 25


                    elif count == 1:

                        value -= 10


            value += (
                rng.uniform(
                    0,
                    2
                )
            )


            scored_candidates.append(
                (
                    value,
                    item
                )
            )


        if not scored_candidates:

            break


        scored_candidates.sort(

            key=lambda x:
                x[0],

            reverse=True

        )


        top_candidates = (

            scored_candidates[
                :min(
                    5,
                    len(
                        scored_candidates
                    )
                )
            ]

        )


        weights = []


        max_value = (
            top_candidates[
                0
            ][0]
        )


        for (
            value,
            _item
        ) in top_candidates:

            diff = (
                max_value
                -
                value
            )


            weight = max(
                0.15,
                1.0
                -
                (
                    diff
                    /
                    30.0
                )
            )


            weights.append(
                weight
            )


        total_weight = sum(
            weights
        )


        pick = rng.uniform(
            0,
            total_weight
        )


        chosen = (
            top_candidates[
                -1
            ][1]
        )


        running = 0


        for (
            (
                value,
                item
            ),
            weight
        ) in zip(
            top_candidates,
            weights
        ):

            running += weight


            if pick <= running:

                chosen = item

                break


        selected.append(
            chosen
        )


        used_keys.add(
            chosen.get(
                key_name
            )
        )


        for group_name in (
            group_names
            or
            []
        ):

            group_value = (
                chosen.get(
                    group_name
                )
            )


            if isinstance(
                group_value,
                list
            ):

                group_values = (
                    group_value
                )

            else:

                group_values = [
                    group_value
                ]


            for gv in group_values:

                if (
                    gv is None
                    or
                    gv == ""
                ):

                    continue


                used_groups[
                    group_name
                ][gv] = (

                    used_groups[
                        group_name
                    ].get(
                        gv,
                        0
                    )
                    +
                    1

                )


        pool.remove(
            chosen
        )


    return selected


# =========================================================
# 推薦理由
# =========================================================

def _unique_reason_parts(
    reasons
):

    parts = []


    for reason in (
        reasons
        or
        []
    ):

        text = str(
            reason
        ).strip()


        if (
            text
            and
            text not in parts
        ):

            parts.append(
                text
            )


    return parts


def build_recommendation_reason(
    item,
    reasons,
    age,
    people,
    member,
    car,
    days,
    budget,
    purpose,
    travel_date,
    season,
    category="spot"
):

    """
    施設データと実際の推薦理由だけを材料に、
    100～200字程度の説明文を作る。
    """

    reasons = (
        _unique_reason_parts(
            reasons
        )
    )


    name = str(
        item.get(
            "name",
            "この施設"
        )
    )


    description = str(
        item.get(
            "description",
            ""
        )
    ).strip()


    reason_text = "、".join(
        reasons[:4]
    )


    paragraphs = []


    if travel_date:

        try:

            dt = datetime.strptime(
                travel_date,
                "%Y-%m-%d"
            )


            date_text = (
                f"{dt.year}年"
                f"{dt.month}月"
                f"{dt.day}日"
            )


            if season:

                paragraphs.append(
                    f"{date_text}の{season}旅行"
                )


        except (
            ValueError,
            TypeError
        ):

            date_text = ""


    else:

        date_text = ""


    if (
        season
        and
        not travel_date
    ):

        paragraphs.append(
            f"今回の{season}旅行"
        )


    if description:

        paragraphs.append(
            f"{name}は{description}"
        )


    if reason_text:

        paragraphs.append(
            f"今回の条件では、"
            f"{reason_text}"
            f"と判断できる点を推薦理由として評価しています"
        )


    matched_purposes = [

        p

        for p in purpose

        if p in str(
            item.get(
                "tags",
                []
            )
        )

    ]


    if matched_purposes:

        purpose_text = (
            "・".join(
                matched_purposes
            )
        )


        paragraphs.append(
            f"旅行目的の「{purpose_text}」とも合っています"
        )


    if any(
        (
            "車" in r
            or
            "駐車" in r
        )
        for r in reasons
    ):

        paragraphs.append(
            "車を利用する条件との相性も推薦時に考慮しています"
        )


    if (
        people >= 5
        and
        any(
            "大人数"
            in r
            for r in reasons
        )
    ):

        paragraphs.append(
            f"{people}人の旅行でも利用条件に合うことを考慮しています"
        )


    elif (
        people >= 2
        and
        any(
            (
                "2人"
                in r
                or
                "少人数"
                in r
            )
            for r in reasons
        )
    ):

        paragraphs.append(
            f"{people}人での旅行条件との相性も評価しています"
        )


    if (
        days == "1泊2日"
        and
        any(
            "1泊2日"
            in r
            for r in reasons
        )
    ):

        paragraphs.append(
            "1泊2日の限られた日程にも組み込みやすい点を評価しています"
        )


    elif (
        days == "2泊3日"
        and
        any(
            "2泊3日"
            in r
            for r in reasons
        )
    ):

        paragraphs.append(
            "2泊3日の旅程に組み込みやすい点も考慮しています"
        )


    if category == "hotel":

        price_value = (
            item.get(
                "price"
            )
        )


        if isinstance(
            price_value,
            (
                int,
                float
            )
        ):

            if (
                price_value
                <=
                budget
            ):

                paragraphs.append(
                    f"宿の参考予算は1人{price_value:,}円で、"
                    f"設定した1人あたり予算{budget:,}円以内です"
                )


            else:

                paragraphs.append(
                    f"宿の参考予算は1人{price_value:,}円で、"
                    f"設定した1人あたり予算との差も確認しています"
                )


    def compose(parts):

        value = "。".join(

            x.rstrip("。")

            for x in parts

            if x

        )


        if (
            value
            and
            not value.endswith("。")
        ):

            value += "。"


        return value


    text = compose(
        paragraphs
    )


    if (
        len(text) > 200
        and
        len(reasons) > 3
    ):

        reduced_paragraphs = []


        for paragraph in paragraphs:

            if (
                reason_text
                and
                paragraph.startswith(
                    "今回の条件では、"
                )
            ):

                reduced_reason_text = (
                    "、".join(
                        reasons[:3]
                    )
                )


                reduced_paragraphs.append(

                    f"今回の条件では、"
                    f"{reduced_reason_text}"
                    f"と判断できる点を推薦理由として評価しています"

                )


            else:

                reduced_paragraphs.append(
                    paragraph
                )


        text = compose(
            reduced_paragraphs
        )


    if len(text) > 200:

        short_description = (

            description[
                :65
            ].rstrip("。")

            if description

            else ""

        )


        shortened = []


        for paragraph in paragraphs:

            if (
                description
                and
                paragraph
                ==
                f"{name}は{description}"
                and
                short_description
            ):

                shortened.append(
                    f"{name}は{short_description}"
                )


            else:

                shortened.append(
                    paragraph
                )


        text = compose(
            shortened
        )


    if len(text) < 100:

        condition_summary = (

            f"{age}代・"
            f"{people}人・"
            f"{member}・"
            f"車{car}・"
            f"{days}・"
            f"予算{budget:,}円/人"

        )


        text += (

            f"入力条件（{condition_summary}）をもとに、"
            f"施設データに確認できる特徴だけを"
            f"組み合わせて選定しています。"

        )


    return (

        text[:200]

        if len(text) > 200

        else text

    )


# =========================================================
# TRIP SUMMARY用ヘルパー
# =========================================================

def _summary_purpose_text(
    purpose
):

    purpose = [
        str(p).strip()
        for p in (purpose or [])
        if str(p).strip()
    ]

    if not purpose:
        return (
            "川越らしい観光"
            if ACTIVE_REGION_CODE == "kawagoe"
            else "秩父観光"
        )

    if ACTIVE_REGION_CODE == "kawagoe":
        mapping = {
            "小江戸・町並み": "小江戸の町並み",
            "歴史・文化": "歴史・文化",
            "食べ歩き・グルメ": "食べ歩き・グルメ",
            "自然・散策": "自然・散策",
        }
    else:
        mapping = {
            "自然": "自然",
            "温泉": "温泉",
            "グルメ": "グルメ",
            "歴史": "歴史・文化",
        }

    return "・".join(
        mapping.get(p, p)
        for p in purpose
    )


def _build_summary_concept(
    purpose
):

    purpose_set = set(
        purpose
        or []
    )

    if ACTIVE_REGION_CODE == "kawagoe":

        if {
            "小江戸・町並み",
            "食べ歩き・グルメ"
        }.issubset(purpose_set):
            return (
                "蔵造りの町並みを歩きながら"
                "川越らしい食べ歩きも楽しむ"
            )

        if {
            "小江戸・町並み",
            "歴史・文化"
        }.issubset(purpose_set):
            return (
                "小江戸の町並みと"
                "川越の歴史・文化をじっくり巡る"
            )

        if {
            "歴史・文化",
            "自然・散策"
        }.issubset(purpose_set):
            return (
                "寺社や史跡と"
                "落ち着いた散策を組み合わせて楽しむ"
            )

        if {
            "食べ歩き・グルメ",
            "歴史・文化"
        }.issubset(purpose_set):
            return (
                "川越の歴史文化に触れながら"
                "名物や食べ歩きも楽しむ"
            )

        if len(purpose_set) >= 3:
            return (
                f"{_summary_purpose_text(purpose)}"
                f"をバランスよく楽しむ"
            )

        return (
            f"{_summary_purpose_text(purpose)}"
            f"を中心に楽しむ"
        )

    if {
        "自然",
        "温泉"
    }.issubset(purpose_set):
        return "自然と温泉を楽しみながら"

    if {
        "自然",
        "グルメ"
    }.issubset(purpose_set):
        return "自然と秩父グルメを楽しみながら"

    if {
        "歴史",
        "グルメ"
    }.issubset(purpose_set):
        return "歴史や文化に触れながら秩父グルメも楽しむ"

    if {
        "歴史",
        "温泉"
    }.issubset(purpose_set):
        return "歴史や文化と温泉を楽しむ"

    if len(purpose_set) >= 3:
        return (
            f"{_summary_purpose_text(purpose)}"
            f"をバランスよく楽しむ"
        )

    return (
        f"{_summary_purpose_text(purpose)}"
        f"を中心に楽しむ"
    )


def _format_summary_areas(
    recommended_spots
):

    areas = []

    for spot in (
        recommended_spots
        or []
    ):
        area = str(
            spot.get(
                "area",
                ""
            )
        ).strip()

        if area and area not in areas:
            areas.append(area)

    if not areas:
        return f"{ACTIVE_REGION_NAME}周辺"

    if len(areas) == 1:
        return f"{areas[0]}エリア"

    if ACTIVE_REGION_CODE == "chichibu":
        if (
            "秩父" in areas
            and "秩父市街" in areas
        ):
            areas = [
                area
                for area in areas
                if area != "秩父"
            ]

    shown = areas[:3]

    return (
        "・".join(shown)
        +
        (
            "など"
            if len(areas) > 3
            else ""
        )
    )


# =========================================================
# TRIP SUMMARY
# =========================================================

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
    day1=None,
    day2=None,
    day3=None,
    meal_schedule=None,
):
    """
    旅行結果に合わせて400～500字前後のTRIP SUMMARYを生成する。

    固定文を長くするのではなく、
    ・地域
    ・旅行目的
    ・同行者
    ・実際に選ばれた観光地
    ・日別の流れ
    ・飲食店
    ・宿泊施設
    ・移動方法
    ・季節
    ・予算
    を使って内容を変える。
    """

    purpose = purpose or []
    recommended_spots = recommended_spots or []
    recommended_restaurants = recommended_restaurants or []
    meal_schedule = meal_schedule or []

    day1 = day1 or []
    day2 = day2 or []
    day3 = day3 or []

    areas = _format_summary_areas(
        recommended_spots
    )

    spot_count = len(
        recommended_spots
    )

    hotel = (
        recommended_hotel
        if isinstance(
            recommended_hotel,
            dict
        )
        else {}
    )

    hotel_name = str(
        hotel.get(
            "name",
            "宿泊施設"
        )
        or
        "宿泊施設"
    ).strip()

    date_text = ""

    if travel_date:
        try:
            dt = datetime.strptime(
                travel_date,
                "%Y-%m-%d"
            )

            date_text = (
                f"{dt.year}年"
                f"{dt.month}月"
                f"{dt.day}日"
            )

        except (
            ValueError,
            TypeError
        ):
            date_text = ""

    concept = _build_summary_concept(
        purpose
    )

    season_prefix = (
        f"{season}の"
        if season
        else ""
    )

    if member == "デート":
        group_phrase = (
            f"{people}人でのデート旅行"
        )
    elif member == "家族":
        group_phrase = (
            f"家族{people}人での旅行"
        )
    elif member == "友人":
        group_phrase = (
            f"友人{people}人での旅行"
        )
    elif member == "一人":
        group_phrase = (
            "1人での旅行"
        )
    else:
        group_phrase = (
            f"{people}人での旅行"
        )

    def _place_names(
        places,
        limit=3
    ):
        names = []

        for place in (
            places
            or []
        ):
            if not isinstance(
                place,
                dict
            ):
                continue

            name = str(
                place.get(
                    "name",
                    ""
                )
                or ""
            ).strip()

            if (
                name
                and
                name not in names
            ):
                names.append(
                    name
                )

            if len(names) >= limit:
                break

        return names

    def _join_names(
        names
    ):
        names = [
            str(name).strip()
            for name in (
                names
                or []
            )
            if str(name).strip()
        ]

        if not names:
            return ""

        if len(names) == 1:
            return names[0]

        if len(names) == 2:
            return (
                f"{names[0]}と{names[1]}"
            )

        return (
            "、".join(
                names[:-1]
            )
            +
            f"、{names[-1]}"
        )

    spot_names = _place_names(
        recommended_spots,
        4
    )

    day1_names = _place_names(
        day1,
        3
    )

    day2_names = _place_names(
        day2,
        3
    )

    day3_names = _place_names(
        day3,
        3
    )

    restaurant_names = _place_names(
        recommended_restaurants,
        2
    )

    # meal_schedule側に実際の日程採用店があれば優先する。
    scheduled_restaurant_names = []

    for meal in meal_schedule:
        if not isinstance(
            meal,
            dict
        ):
            continue

        restaurant = meal.get(
            "restaurant"
        )

        if isinstance(
            restaurant,
            dict
        ):
            name = str(
                restaurant.get(
                    "name",
                    ""
                )
                or ""
            ).strip()

            if (
                name
                and
                name not in scheduled_restaurant_names
            ):
                scheduled_restaurant_names.append(
                    name
                )

    if scheduled_restaurant_names:
        restaurant_names = (
            scheduled_restaurant_names[:2]
        )

    first = (
        f"今回は、"
        f"{season_prefix}{ACTIVE_REGION_NAME}で"
        f"{concept}{days}の旅行プランです。"
        f"{group_phrase}という条件をもとに、"
        f"{areas}を中心として"
        f"{spot_count}か所の観光スポットを組み合わせています。"
    )

    if spot_names:
        second = (
            f"観光地は"
            f"{_join_names(spot_names)}"
            f"などを選び、"
        )
    else:
        second = (
            "観光地は入力条件との相性を比較して選び、"
        )

    if ACTIVE_REGION_CODE == "kawagoe":
        second += (
            "小江戸らしい町並みや歴史文化、"
            "街歩きの楽しさを感じられるように構成しています。"
        )
    else:
        second += (
            "自然・歴史・市街地観光など、"
            "秩父らしい魅力を感じられるように構成しています。"
        )

    day_sentences = []

    if day1_names:
        day_sentences.append(
            "1日目は"
            +
            _join_names(
                day1_names
            )
            +
            "を中心に巡ります"
        )

    if day2_names:
        day_sentences.append(
            "2日目は"
            +
            _join_names(
                day2_names
            )
            +
            "を組み合わせています"
        )

    if (
        days == "2泊3日"
        and
        day3_names
    ):
        day_sentences.append(
            "3日目は"
            +
            _join_names(
                day3_names
            )
            +
            "を巡る流れです"
        )

    if day_sentences:
        third = (
            "。".join(
                day_sentences
            )
            +
            "。"
        )
    else:
        third = (
            f"約{sightseeing_time}時間の観光時間を目安に、"
            "滞在時間と移動時間のバランスを見ながら日程を組んでいます。"
        )

    if car:
        if ACTIVE_REGION_CODE == "kawagoe":
            fourth = (
                "車移動では川越IC・川越駅周辺を入口として、"
                "完成済みの道路ルートデータを使い、"
                "信号待ちや施設への出入りを考慮した補正時間も含めて"
                "無理のない順番になるよう調整しています。"
            )
        else:
            fourth = (
                "車移動では完成済みの秩父道路ルートデータを使い、"
                "信号待ちや施設への出入りを考慮した補正時間も含めて、"
                "観光地同士を効率よく巡れる順番になるよう調整しています。"
            )
    else:
        fourth = (
            "移動条件を踏まえ、"
            "観光地同士の位置関係と滞在時間を考慮して順番を調整しています。"
        )

    if date_text and season:
        fifth = (
            f"旅行日は{date_text}で、"
            f"{season}の旅行として各施設の季節情報も確認し、"
            "旅行時期との相性を推薦結果へ反映しています。"
        )
    elif season:
        fifth = (
            f"{season}という旅行時期も考慮し、"
            "季節との相性を推薦結果へ反映しています。"
        )
    else:
        fifth = (
            "旅行日が未指定のため、"
            "季節条件による強い加減点は行わずに候補を選んでいます。"
        )

    food_sentence = ""

    if restaurant_names:
        if ACTIVE_REGION_CODE == "kawagoe":
            food_sentence = (
                f"食事では{_join_names(restaurant_names)}などを候補にし、"
                "うなぎ・和食・甘味・軽食など、"
                "川越の食文化や選択した旅行目的との相性も考えています。"
            )
        else:
            food_sentence = (
                f"食事では{_join_names(restaurant_names)}などを候補にし、"
                "秩父名物や店舗ジャンル、"
                "旅行目的との相性も考えています。"
            )

    hotel_price = hotel.get(
        "price"
    )

    if isinstance(
        hotel_price,
        (
            int,
            float
        )
    ):
        hotel_sentence = (
            f"宿泊には{hotel_name}を組み合わせ、"
            f"1人あたり{budget:,}円の設定予算に対して"
            f"参考宿泊費{int(hotel_price):,}円も確認しています。"
        )
    else:
        hotel_sentence = (
            f"宿泊には{hotel_name}を組み合わせています。"
            "宿泊料金は日付・人数・客室・プランで変動するため"
            "固定額を推測せず、"
            f"1人あたり{budget:,}円の設定予算を旅行条件として扱っています。"
        )

    if ACTIVE_REGION_CODE == "kawagoe":
        if "食べ歩き・グルメ" in purpose:
            closing = (
                "観光だけでなく食事や街歩きまで含めて、"
                "小江戸川越らしさを1泊ごとの流れの中で楽しめるプランです。"
            )
        elif "歴史・文化" in purpose:
            closing = (
                "寺社や史跡、歴史的な町並みをつなぎ、"
                "城下町としての川越を感じやすいプランにしています。"
            )
        elif "自然・散策" in purpose:
            closing = (
                "市街地だけに偏らず、"
                "散策や落ち着いて過ごせる場所も組み合わせたプランです。"
            )
        else:
            closing = (
                "町並み・歴史・食・散策のバランスを取りながら、"
                "川越らしさを感じられる旅行プランにしています。"
            )
    else:
        if "自然" in purpose:
            closing = (
                "自然景観と市街地観光のバランスを取り、"
                "秩父らしい風景を楽しめる旅行プランにしています。"
            )
        elif "温泉" in purpose:
            closing = (
                "観光と休息のメリハリをつけ、"
                "温泉も含めてゆったり過ごせる旅行プランにしています。"
            )
        elif "グルメ" in purpose:
            closing = (
                "観光だけでなく秩父の食も楽しめるよう、"
                "食事の立ち寄りまで含めて構成したプランです。"
            )
        elif "歴史" in purpose:
            closing = (
                "自然だけでなく寺社や文化施設も組み合わせ、"
                "秩父の歴史に触れられる旅行プランにしています。"
            )
        else:
            closing = (
                "観光・移動・食事・宿泊をまとめて考え、"
                "限られた日程でも秩父を楽しみやすい旅行プランにしています。"
            )

    candidates = [
        first,
        second,
        third,
        fourth,
        fifth,
        food_sentence,
        hotel_sentence,
        closing,
    ]

    selected = []

    for sentence in candidates:
        if not sentence:
            continue

        candidate = "".join(
            selected
            +
            [sentence]
        )

        if len(candidate) <= 500:
            selected.append(
                sentence
            )

    text = "".join(
        selected
    )

    # 400字未満の場合は、日程全体の説明を追加する。
    if len(text) < 400:
        extra_candidates = [
            (
                f"今回のプランでは総観光時間を約{sightseeing_time}時間の目安とし、"
                "1か所に滞在しすぎないようにしながら、"
                "移動時間も含めて現実的に回れる構成を意識しています。"
            ),
            (
                "おすすめ度だけで決めるのではなく、"
                "上位候補の中からエリアや施設の種類が偏りすぎないように調整しています。"
            ),
        ]

        for sentence in extra_candidates:
            if (
                len(text)
                +
                len(sentence)
                <=
                500
            ):
                text += sentence

            if len(text) >= 400:
                break

    # 最後の保険。500字を超えた場合は文単位に近い位置で切る。
    if len(text) > 500:
        shortened = text[:497]

        last_period = shortened.rfind(
            "。"
        )

        if last_period >= 380:
            shortened = (
                shortened[
                    :last_period + 1
                ]
            )
        else:
            shortened = (
                shortened.rstrip(
                    "、"
                )
                +
                "。"
            )

        text = shortened

    return text


# =========================================================
# おすすめアルゴリズム見える化
# =========================================================

def _score_item(
    key,
    label,
    score,
    reason=""
):

    """
    結果画面へ渡す
    スコア内訳1項目を作る。
    """

    return {

        "key":
            key,

        "label":
            label,

        "score":
            int(score),

        "reason":
            str(
                reason
                or
                ""
            )

    }


def _score_total_positive(
    breakdown
):

    """
    グラフ表示用に、
    正の点数合計を取得する。
    """

    return sum(

        max(
            0,
            int(
                item.get(
                    "score",
                    0
                )
            )
        )

        for item in (
            breakdown
            or
            []
        )

    )


def attach_score_visualization(
    item,
    breakdown
):

    """
    施設データに結果画面用の
    スコア表示情報を追加する。
    """

    copied = item.copy()


    cleaned = []

    for entry in (
        breakdown
        or
        []
    ):

        if not isinstance(
            entry,
            dict
        ):

            continue


        score_value = int(
            entry.get(
                "score",
                0
            )
        )


        cleaned_entry = {

            "key":
                entry.get(
                    "key",
                    ""
                ),

            "label":
                entry.get(
                    "label",
                    ""
                ),

            "score":
                score_value,

            "reason":
                entry.get(
                    "reason",
                    ""
                )

        }

        if entry.get("max_score") is not None:
            try:
                cleaned_entry["max_score"] = int(
                    entry.get("max_score")
                )
            except (
                TypeError,
                ValueError
            ):
                pass

        cleaned.append(
            cleaned_entry
        )


    positive_total = (
        _score_total_positive(
            cleaned
        )
    )


    for entry in cleaned:

        if positive_total > 0:

            entry["bar_percent"] = round(

                (
                    max(
                        0,
                        entry["score"]
                    )
                    /
                    positive_total
                )
                *
                100

            )

        else:

            entry["bar_percent"] = 0


    copied["score_breakdown"] = (
        cleaned
    )


    copied["positive_score_total"] = (
        positive_total
    )

    max_scores = [
        int(entry.get("max_score"))
        for entry in cleaned
        if entry.get("max_score") is not None
    ]

    if (
        max_scores
        and
        len(max_scores) == len(cleaned)
    ):
        copied["score_max"] = sum(
            max_scores
        )

    return copied


# =========================================================
# 観光地スコアリング
# =========================================================

def calculate_spot_score(
    spot,
    member,
    purpose,
    car,
    age,
    people,
    days,
    budget,
    gender,
    walking_amount="普通",
    travel_pace="普通",
    season=None,
    travel_date=""
):

    if ACTIVE_REGION_CODE == "kawagoe":
        return calculate_kawagoe_spot_score(
            spot=spot,
            member=member,
            purpose=purpose,
            car=car,
            age=age,
            people=people,
            days=days,
            budget=budget,
            gender=gender,
            walking_amount=walking_amount,
            travel_pace=travel_pace,
            season=season,
            travel_date=travel_date
        )

    if ACTIVE_REGION_CODE == "chichibu":
        return calculate_chichibu_spot_score(
            spot=spot,
            member=member,
            purpose=purpose,
            car=car,
            age=age,
            people=people,
            days=days,
            budget=budget,
            gender=gender,
            walking_amount=walking_amount,
            travel_pace=travel_pace,
            season=season,
            travel_date=travel_date
        )

    difficulty = normalize_walking_difficulty(
        spot.get("difficulty")
    )

    score = 0

    reasons = []

    breakdown = []


    # -----------------------------------------------------
    # 季節
    # -----------------------------------------------------

    (
        season_score,
        season_reasons,
        unavailable

    ) = calculate_season_effect(

        spot,
        season,
        travel_date

    )


    if unavailable:

        breakdown.append(

            _score_item(

                "season",
                "季節・営業条件",
                season_score,
                "旅行予定日が営業条件に合っていません"

            )

        )


        return (
            season_score,
            season_reasons,
            breakdown
        )


    score += season_score

    reasons.extend(
        season_reasons
    )


    if season_score != 0:

        breakdown.append(

            _score_item(

                "season",
                "季節",
                season_score,
                (
                    "・".join(
                        season_reasons
                    )
                    if season_reasons
                    else
                    "旅行時期との相性"
                )

            )

        )


    # -----------------------------------------------------
    # 旅行目的
    # -----------------------------------------------------

    purpose_score = 0


    purpose_match = sum(

        1

        for p in purpose

        if p in spot[
            "tags"
        ]

    )


    matched_purpose_names = [

        p

        for p in purpose

        if p in spot[
            "tags"
        ]

    ]


    if purpose_match:

        purpose_score += (
            40
            *
            purpose_match
        )


        for p in purpose:

            if p in spot[
                "tags"
            ]:

                reasons.append(
                    f"{p}を楽しめる"
                )


    else:

        purpose_score -= 20


    if purpose_match >= 2:

        purpose_score += 12

        reasons.append(
            "複数の旅行目的に合う"
        )


    score += purpose_score


    if matched_purpose_names:

        purpose_reason = (

            "旅行目的「"
            +
            "・".join(
                matched_purpose_names
            )
            +
            "」と一致"

        )


    else:

        purpose_reason = (
            "選択した旅行目的との一致なし"
        )


    breakdown.append(

        _score_item(

            "purpose",
            "旅行目的",
            purpose_score,
            purpose_reason

        )

    )


    # -----------------------------------------------------
    # 同行者
    # -----------------------------------------------------

    member_score = 0


    if member == "一人":

        member_reason = (
            "1人旅のため同行者タグによる加減点なし"
        )


    elif not any(
        tag in spot.get("tags", [])
        for tag in ("デート", "家族", "友人")
    ):

        member_reason = (
            "同行者向けデータ未設定のため加減点なし"
        )

    elif member in spot[
        "tags"
    ]:

        member_score += 30

        reasons.append(
            f"{member}旅行に向いている"
        )

        member_reason = (
            f"{member}向けの施設タグと一致"
        )


    else:

        member_score -= 10

        member_reason = (
            f"{member}向けタグとの一致なし"
        )


    score += member_score


    breakdown.append(

        _score_item(

            "member",
            "旅行メンバー",
            member_score,
            member_reason

        )

    )


    # -----------------------------------------------------
    # 車
    # -----------------------------------------------------

    car_score = 0


    if spot[
        "car"
    ]:

        car_score += 25

        reasons.append(
            "車でアクセスしやすい"
        )

        car_reason = (
            "車を利用する条件と施設特性が一致"
        )


    else:

        car_score += 4

        car_reason = (
            "車利用でも訪問可能"
        )


    score += car_score


    breakdown.append(

        _score_item(

            "car",
            "移動手段",
            car_score,
            car_reason

        )

    )


    # 年齢から歩行能力を推測する評価は行わない。
    _ = age
    _ = travel_pace


    # -----------------------------------------------------
    # 人数
    # -----------------------------------------------------

    people_score = 0

    people_reason = (
        "人数による追加補正なし"
    )


    if people >= 5:

        if member in [
            "家族",
            "友人"
        ]:

            people_score += 12

            reasons.append(
                "大人数でも楽しみやすい"
            )

            people_reason = (
                "大人数で楽しみやすい条件"
            )


    elif (
        people <= 2
        and
        member == "デート"
        and
        "デート"
        in spot[
            "tags"
        ]
    ):

        people_score += 14

        reasons.append(
            "2人で楽しみやすい"
        )

        people_reason = (
            "2人での旅行と相性が良い"
        )


    elif people == 1:

        if difficulty == "easy":

            people_score += 5

            people_reason = (
                "1人でも巡りやすい"
            )


    score += people_score


    breakdown.append(

        _score_item(

            "people",
            "人数",
            people_score,
            people_reason

        )

    )


    # -----------------------------------------------------
    # 旅行日数
    # -----------------------------------------------------

    days_score = 0


    if days == "1泊2日":

        if spot[
            "time"
        ] <= 2:

            days_score += 10

            reasons.append(
                "1泊2日でも組み込みやすい"
            )

            days_reason = (
                "短い日程にも組み込みやすい"
            )


        elif spot[
            "time"
        ] >= 4:

            days_score -= 8

            days_reason = (
                "滞在時間が長く1泊2日では負担"
            )


        else:

            days_reason = (
                "1泊2日の旅程に組み込み可能"
            )


    else:

        if spot[
            "time"
        ] >= 3:

            days_score += 8

            reasons.append(
                "2泊3日の旅程に組み込みやすい"
            )

            days_reason = (
                "2泊3日の余裕ある旅程と相性が良い"
            )


        else:

            days_reason = (
                "2泊3日の旅程に組み込み可能"
            )



    score += days_score


    breakdown.append(

        _score_item(

            "days",
            "旅行日数・滞在時間",
            days_score,
            days_reason

        )

    )


    # 観光地には現時点で
    # 入場料金を推薦用の共通数値として持っていないため、
    # 予算による推測加点はしない。
    _ = budget

    # 性別による固定的な推薦は行わない。
    _ = gender


    return (
        score,
        reasons,
        breakdown
    )


# =========================================================
# グルメスコアリング
# =========================================================

def calculate_restaurant_score(
    restaurant,
    member,
    purpose,
    car,
    people,
    budget,
    age,
    days,
    gender,
    walking_amount="普通",
    travel_pace="普通"
):

    """
    飲食店の推薦点（S6対応）。

    最大80点:
    ・秩父らしさ 30点
    ・ジャンル相性 25点
    ・行きやすさ 25点
    """

    score = 0
    reasons = []
    breakdown = []

    specialties = normalize_list(
        restaurant.get("specialties")
    )

    genres = normalize_list(
        restaurant.get("genre")
    )

    # -----------------------------------------------------
    # 地域らしさ
    # -----------------------------------------------------

    local_text = " ".join(
        str(value)
        for value in (specialties + genres)
    )

    local_score = 0

    if ACTIVE_REGION_CODE == "chichibu":

        local_keywords = [
            "豚みそ丼", "豚味噌", "わらじかつ", "わらじカツ",
            "秩父そば", "みそポテト", "味噌ポテト",
            "郷土料理", "ホルモン"
        ]

        if any(keyword in local_text for keyword in local_keywords):
            local_score = 30
            local_reason = "秩父名物・郷土料理に該当"
            reasons.append("秩父ならではの料理を楽しめる")
        else:
            local_reason = "秩父名物・郷土料理による加点なし"

    else:
        kawagoe_keywords = [
            "うなぎ",
            "鰻",
            "さつまいも",
            "さつま芋",
            "芋",
            "焼き芋",
            "だんご",
            "団子",
            "せんべい",
            "駄菓子",
            "川越",
            "小江戸",
            "郷土料理"
        ]

        if any(
            keyword in local_text
            for keyword in kawagoe_keywords
        ):
            local_score = 30
            local_reason = (
                "川越の名物・食文化と関連する料理に該当"
            )
            reasons.append(
                "川越らしい食を楽しめる"
            )
        else:
            local_reason = (
                "川越の名物・食文化による加点なし"
            )

    score += local_score

    breakdown.append(
        _score_item(
            "local",
            "地域らしさ",
            local_score,
            local_reason
        )
    )


    # -----------------------------------------------------
    # ジャンル相性 25点
    # -----------------------------------------------------

    genre_text = " ".join(
        str(value)
        for value in (
            genres
            +
            specialties
        )
    )

    selected_purpose = set(
        str(value).strip()
        for value in (purpose or [])
        if str(value).strip()
    )

    genre_score = 0
    genre_reasons = []

    if ACTIVE_REGION_CODE == "kawagoe":

        # 川越は「食べ歩き・グルメ」を旅行目的として
        # 明示的に選べるため、同行者だけでなく旅行目的を主軸に評価する。
        if "食べ歩き・グルメ" in selected_purpose:
            genre_score += 12
            genre_reasons.append(
                "食べ歩き・グルメ目的と一致"
            )

        kawagoe_food_groups = {
            "川越らしい和食": [
                "うなぎ",
                "鰻",
                "和食",
                "日本料理",
                "割烹",
                "懐石",
                "郷土料理"
            ],
            "甘味・軽食": [
                "甘味",
                "和菓子",
                "団子",
                "だんご",
                "芋",
                "さつまいも",
                "軽食",
                "茶房",
                "ティー",
                "TEA"
            ],
            "カフェ・パン": [
                "カフェ",
                "珈琲",
                "コーヒー",
                "ベーカリー",
                "パン"
            ],
            "麺・気軽な食事": [
                "そば",
                "蕎麦",
                "うどん",
                "ラーメン",
                "定食"
            ],
            "洋食・特別な食事": [
                "洋食",
                "フレンチ",
                "イタリアン",
                "スペイン",
                "鉄板",
                "ステーキ"
            ],
        }

        matched_group = None

        for group_name, keywords in kawagoe_food_groups.items():
            if any(
                keyword.lower() in genre_text.lower()
                for keyword in keywords
            ):
                matched_group = group_name
                break

        if matched_group:
            genre_score += 8
            genre_reasons.append(
                f"{matched_group}として楽しみやすい"
            )

        # 同行者との相性は補助評価に留める。
        if member == "デート":
            if any(
                keyword.lower() in genre_text.lower()
                for keyword in [
                    "カフェ",
                    "甘味",
                    "茶房",
                    "フレンチ",
                    "洋食",
                    "日本料理",
                    "うなぎ",
                    "鰻"
                ]
            ):
                genre_score += 5
                genre_reasons.append(
                    "デートでも選びやすいジャンル"
                )

        elif member == "家族":
            if any(
                keyword.lower() in genre_text.lower()
                for keyword in [
                    "和食",
                    "うなぎ",
                    "鰻",
                    "そば",
                    "うどん",
                    "定食",
                    "甘味",
                    "軽食"
                ]
            ):
                genre_score += 5
                genre_reasons.append(
                    "家族旅行でも選びやすいジャンル"
                )

        elif member == "友人":
            # 友人旅行では特定ジャンルに限定しすぎない。
            genre_score += 4
            genre_reasons.append(
                "友人旅行で利用しやすい"
            )

        elif member == "一人":
            genre_score += 3
            genre_reasons.append(
                "一人旅でも立ち寄りやすい"
            )

    else:

        # 秩父も「同行者に特定ジャンルが完全一致したときだけ25点」
        # という旧方式をやめ、旅行目的と実際の料理ジャンルを合わせて評価する。
        if "グルメ" in selected_purpose:
            genre_score += 12
            genre_reasons.append(
                "グルメ目的と一致"
            )

        if any(
            keyword in genre_text
            for keyword in [
                "そば",
                "蕎麦",
                "うどん",
                "定食",
                "和食",
                "豚みそ",
                "豚味噌",
                "わらじ",
                "ホルモン",
                "郷土料理"
            ]
        ):
            genre_score += 8
            genre_reasons.append(
                "秩父旅行で選びやすい食事ジャンル"
            )

        if member == "デート":
            if any(
                keyword in genre_text
                for keyword in [
                    "カフェ",
                    "洋食",
                    "イタリアン",
                    "甘味"
                ]
            ):
                genre_score += 5
                genre_reasons.append(
                    "デートで選びやすい"
                )

        elif member == "家族":
            if any(
                keyword in genre_text
                for keyword in [
                    "そば",
                    "うどん",
                    "定食",
                    "和食"
                ]
            ):
                genre_score += 5
                genre_reasons.append(
                    "家族旅行で選びやすい"
                )

        elif member == "友人":
            genre_score += 4
            genre_reasons.append(
                "友人旅行で利用しやすい"
            )

        elif member == "一人":
            genre_score += 3
            genre_reasons.append(
                "一人旅でも利用しやすい"
            )

    genre_score = min(
        25,
        genre_score
    )

    if genre_score > 0:
        genre_reason = "・".join(
            genre_reasons
        )
        reasons.append(
            "旅行条件と店舗ジャンルの相性が良い"
        )
    else:
        genre_reason = (
            "今回の旅行条件との強いジャンル一致はなし"
        )

    score += genre_score

    breakdown.append(
        _score_item(
            "genre",
            "店舗ジャンル",
            genre_score,
            genre_reason
        )
    )

    # -----------------------------------------------------
    # 行きやすさ 25点
    # -----------------------------------------------------

    access_score = 0

    parking = restaurant.get(
        "parking",
        {}
    )

    if (
        isinstance(
            parking,
            dict
        )
        and
        parking.get("available") is True
    ):

        access_score = 25
        access_reason = "駐車場あり"
        reasons.append(
            "車で立ち寄りやすい"
        )

    else:

        access_score = 10
        access_reason = "駐車場情報未確認のため標準点"

    score += access_score

    breakdown.append(
        _score_item(
            "access",
            "行きやすさ",
            access_score,
            access_reason
        )
    )

    # S6では以下は飲食店の順位付けに使わない。
    _ = purpose
    _ = people
    _ = budget
    _ = age
    _ = days
    _ = gender
    _ = walking_amount
    _ = travel_pace

    return (
        score,
        reasons,
        breakdown
    )


# =========================================================
# 宿泊施設スコアリング
# =========================================================

def calculate_hotel_score(
    hotel,
    member,
    purpose,
    budget,
    people,
    age,
    car,
    days,
    gender,
    walking_amount="普通",
    travel_pace="普通",
    season=None,
    travel_date=""
):

    score = 0

    reasons = []

    breakdown = []


    # -----------------------------------------------------
    # 季節
    # -----------------------------------------------------

    (
        season_score,
        season_reasons,
        unavailable

    ) = calculate_season_effect(

        hotel,
        season,
        travel_date

    )


    if unavailable:

        breakdown.append(

            _score_item(

                "season",
                "季節・営業条件",
                season_score,
                "旅行予定日が営業条件に合っていません"

            )

        )


        return (
            season_score,
            season_reasons,
            breakdown
        )


    score += season_score

    reasons.extend(
        season_reasons
    )


    if season_score != 0:

        breakdown.append(

            _score_item(

                "season",
                "季節",
                season_score,
                (
                    "・".join(
                        season_reasons
                    )
                    if season_reasons
                    else
                    "旅行時期との相性"
                )

            )

        )


    # -----------------------------------------------------
    # 同行者
    # -----------------------------------------------------

    member_score = 0


    if member == "一人":

        member_reason = (
            "1人旅のため同行者タグによる加減点なし"
        )


    elif not any(
        tag in hotel.get("tags", [])
        for tag in ("デート", "家族", "友人")
    ):

        member_reason = (
            "同行者向けデータ未設定のため加減点なし"
        )

    elif member in hotel[
        "tags"
    ]:

        member_score += 35

        reasons.append(
            f"{member}旅行と相性が良い"
        )

        member_reason = (
            f"{member}向けタグと一致"
        )


    else:

        member_score -= 5

        member_reason = (
            f"{member}向けタグとの一致なし"
        )


    score += member_score


    breakdown.append(

        _score_item(

            "member",
            "旅行メンバー",
            member_score,
            member_reason

        )

    )


    # -----------------------------------------------------
    # 旅行目的
    # -----------------------------------------------------

    purpose_score = 0

    purpose_match = 0

    matched_purposes = []


    for p in purpose:

        if p in hotel[
            "tags"
        ]:

            purpose_score += 28

            purpose_match += 1

            matched_purposes.append(
                p
            )

            reasons.append(
                f"{p}を楽しみやすい"
            )


    if purpose_match == 0:

        purpose_score -= 12


    score += purpose_score


    breakdown.append(

        _score_item(

            "purpose",
            "旅行目的",
            purpose_score,
            (
                "「"
                +
                "・".join(
                    matched_purposes
                )
                +
                "」と一致"
                if matched_purposes
                else
                "旅行目的との一致なし"
            )

        )

    )


    # -----------------------------------------------------
    # 予算
    # -----------------------------------------------------

    budget_score = 0

    hotel_price = hotel.get("price")

    if isinstance(hotel_price, (int, float)):

        if hotel_price <= budget:

            budget_score += 45
            reasons.append("予算内に収まりやすい宿")

            if budget - hotel_price >= 5000:
                budget_score += 5

            budget_reason = (
                f"参考宿泊費{int(hotel_price):,}円が設定予算内"
            )

        else:

            over = int(hotel_price - budget)
            budget_score -= min(50, over // 500)
            budget_reason = (
                f"設定予算より{over:,}円高い"
            )

    else:
        budget_reason = (
            "宿泊料金は変動制のため予約時確認。予算による加減点なし"
        )

    score += budget_score

    breakdown.append(
        _score_item(
            "budget",
            "宿泊予算",
            budget_score,
            budget_reason
        )
    )


    # -----------------------------------------------------
    # 人数
    # -----------------------------------------------------

    people_score = 0

    people_reason = (
        "人数による追加補正なし"
    )


    if (
        people >= 5
        and
        member in [
            "家族",
            "友人"
        ]
    ):

        people_score += 12

        reasons.append(
            "複数人での旅行と相性が良い"
        )

        people_reason = (
            "大人数旅行と相性が良い"
        )


    elif (
        people <= 2
        and
        member == "デート"
        and
        "デート"
        in hotel[
            "tags"
        ]
    ):

        people_score += 12

        reasons.append(
            "2人の旅行と相性が良い"
        )

        people_reason = (
            "2人旅行と相性が良い"
        )


    score += people_score


    breakdown.append(

        _score_item(

            "people",
            "人数",
            people_score,
            people_reason

        )

    )


    # 年齢から宿の向き不向きを決める評価は行わない。
    _ = age
    _ = travel_pace


    # -----------------------------------------------------
    # 旅行日数
    # -----------------------------------------------------

    days_score = 0
    hotel_quality = hotel.get("quality")

    if (
        days == "2泊3日"
        and isinstance(hotel_quality, (int, float))
        and hotel_quality >= 5
    ):
        days_score += 5
        days_reason = "連泊でも過ごしやすい高品質宿"
    else:
        days_reason = "旅行日数による追加補正なし"

    score += days_score

    breakdown.append(
        _score_item(
            "days",
            "旅行日数",
            days_score,
            days_reason
        )
    )


    # -----------------------------------------------------
    # 宿の品質
    # -----------------------------------------------------

    quality_score = 0

    if isinstance(hotel_quality, (int, float)):
        quality_score = hotel_quality * 2
        quality_reason = f"品質評価 {hotel_quality}/5"
    else:
        quality_reason = "共通基準の品質評価は未設定のため加減点なし"

    score += quality_score

    breakdown.append(
        _score_item(
            "quality",
            "宿の品質",
            quality_score,
            quality_reason
        )
    )


    # 現在の宿データには
    # 十分な駐車場詳細がないため推測加点しない。
    _ = car

    _ = gender


    return (
        score,
        reasons,
        breakdown
    )


# =========================================================
# 天気予報（秩父 / 川越・7日間）
# =========================================================

CHICHIBU_LATITUDE = 35.991681
CHICHIBU_LONGITUDE = 139.085475

OPEN_METEO_FORECAST_URL = (
    "https://api.open-meteo.com/v1/forecast"
)

# Open-Meteoが一時的に利用できない場合のバックアップ。
# APIキー不要。利用規約に従い識別可能なUser-Agentを送信する。
MET_NORWAY_FORECAST_URL = (
    "https://api.met.no/weatherapi/locationforecast/2.0/compact"
)

WEATHER_TIMEZONE = "Asia/Tokyo"
WEATHER_CACHE_TTL = timedelta(minutes=30)
WEATHER_HTTP_TIMEOUT = 12
WEATHER_RETRY_COUNT = 2

WEATHER_CACHE_DIR = os.path.join(
    BASE_DIR,
    "cache"
)

try:
    os.makedirs(
        WEATHER_CACHE_DIR,
        exist_ok=True
    )
except OSError:
    pass

_weather_cache = {
    "region_code": None,
    "data": None,
    "expires_at": None,
}

JST = timezone(
    timedelta(hours=9)
)

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
    return datetime.now(JST).date().isoformat()


def _weather_cache_path(region_code=None):
    code = str(
        region_code
        or ACTIVE_REGION_CODE
        or "default"
    ).strip()

    safe_code = re.sub(
        r"[^A-Za-z0-9_-]+",
        "_",
        code
    )

    return os.path.join(
        WEATHER_CACHE_DIR,
        f"weather_{safe_code}.json"
    )


def _save_weather_file_cache(data):
    if not isinstance(data, dict):
        return

    path = _weather_cache_path()
    temp_path = path + ".tmp"

    payload = {
        "saved_at": datetime.now(JST).isoformat(),
        "region_code": ACTIVE_REGION_CODE,
        "data": data,
    }

    try:
        with open(
            temp_path,
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                payload,
                f,
                ensure_ascii=False,
                indent=2
            )

        os.replace(
            temp_path,
            path
        )

    except OSError as exc:
        print(
            "[WEATHER CACHE] save failed",
            repr(exc)
        )

        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except OSError:
            pass


def _load_weather_file_cache():
    path = _weather_cache_path()

    try:
        with open(
            path,
            "r",
            encoding="utf-8"
        ) as f:
            payload = json.load(f)

        if not isinstance(payload, dict):
            return None

        data = payload.get("data")

        if not isinstance(data, dict):
            return None

        forecasts = data.get("forecasts")

        if not isinstance(forecasts, list) or not forecasts:
            return None

        return data

    except (
        OSError,
        json.JSONDecodeError,
        TypeError
    ):
        return None


def _http_get_json(
    url,
    provider_label,
    headers=None
):
    """
    外部天気APIのJSONを安全に取得する共通処理。

    1. requests + certifi
    2. urllib + certifi
    3. urllib標準SSL

    の順で試す。SSL検証は無効化しない。
    """
    merged_headers = {
        "User-Agent": (
            "SaitamaSouthwestTourismPlanner/1.1 "
            "(university project; weather forecast)"
        ),
        "Accept": "application/json",
        "Connection": "close",
    }

    if isinstance(headers, dict):
        merged_headers.update(headers)

    last_error = None

    # -----------------------------------------------------
    # 1. requests + certifi
    # -----------------------------------------------------
    try:
        import requests

        verify_value = True

        try:
            import certifi
            verify_value = certifi.where()
        except (ImportError, OSError):
            verify_value = True

        for attempt in range(1, WEATHER_RETRY_COUNT + 1):
            try:
                response = requests.get(
                    url,
                    headers=merged_headers,
                    timeout=(5, WEATHER_HTTP_TIMEOUT),
                    verify=verify_value
                )
                response.raise_for_status()
                data = response.json()

                if (
                    isinstance(data, dict)
                    and data.get("error") is True
                ):
                    raise RuntimeError(
                        str(
                            data.get("reason")
                            or f"{provider_label} API error"
                        )
                    )

                print(
                    "[WEATHER FETCH]",
                    provider_label,
                    "requests",
                    f"attempt={attempt}",
                    "SUCCESS"
                )

                return data

            except Exception as exc:
                last_error = exc
                print(
                    "[WEATHER FETCH]",
                    provider_label,
                    "requests",
                    f"attempt={attempt}/{WEATHER_RETRY_COUNT}",
                    "FAILED",
                    repr(exc)
                )

                if attempt < WEATHER_RETRY_COUNT:
                    time.sleep(0.6)

    except Exception as exc:
        last_error = exc
        print(
            "[WEATHER FETCH]",
            provider_label,
            "requests setup FAILED",
            repr(exc)
        )

    # -----------------------------------------------------
    # 2. urllib + certifi
    # -----------------------------------------------------
    try:
        import ssl

        ssl_context = ssl.create_default_context()

        try:
            import certifi
            ssl_context = ssl.create_default_context(
                cafile=certifi.where()
            )
        except (ImportError, OSError):
            pass

        request_obj = urllib.request.Request(
            url,
            headers=merged_headers
        )

        with urllib.request.urlopen(
            request_obj,
            timeout=WEATHER_HTTP_TIMEOUT,
            context=ssl_context
        ) as response:
            status = getattr(
                response,
                "status",
                200
            )

            if status != 200:
                raise RuntimeError(
                    f"{provider_label} HTTP status: {status}"
                )

            payload = response.read().decode("utf-8")

        data = json.loads(payload)

        if (
            isinstance(data, dict)
            and data.get("error") is True
        ):
            raise RuntimeError(
                str(
                    data.get("reason")
                    or f"{provider_label} API error"
                )
            )

        print(
            "[WEATHER FETCH]",
            provider_label,
            "urllib/certifi",
            "SUCCESS"
        )

        return data

    except Exception as exc:
        last_error = exc
        print(
            "[WEATHER FETCH]",
            provider_label,
            "urllib/certifi",
            "FAILED",
            repr(exc)
        )

    # -----------------------------------------------------
    # 3. urllib標準SSL
    # -----------------------------------------------------
    try:
        request_obj = urllib.request.Request(
            url,
            headers=merged_headers
        )

        with urllib.request.urlopen(
            request_obj,
            timeout=WEATHER_HTTP_TIMEOUT
        ) as response:
            status = getattr(response, "status", 200)

            if status != 200:
                raise RuntimeError(
                    f"{provider_label} HTTP status: {status}"
                )

            payload = response.read().decode("utf-8")

        data = json.loads(payload)

        print(
            "[WEATHER FETCH]",
            provider_label,
            "urllib/default",
            "SUCCESS"
        )

        return data

    except Exception as exc:
        last_error = exc
        print(
            "[WEATHER FETCH]",
            provider_label,
            "urllib/default",
            "FAILED",
            repr(exc)
        )

    raise RuntimeError(
        f"{provider_label} request failed with all secure methods"
    ) from last_error


def _build_weather_url(model=None):
    params = {
        "latitude": ACTIVE_WEATHER_LATITUDE,
        "longitude": ACTIVE_WEATHER_LONGITUDE,
        "daily": (
            "weather_code,"
            "temperature_2m_max,"
            "temperature_2m_min,"
            "precipitation_probability_max"
        ),
        "timezone": WEATHER_TIMEZONE,
        "forecast_days": 7,
        "temperature_unit": "celsius",
    }

    if model:
        params["models"] = model

    return (
        OPEN_METEO_FORECAST_URL
        + "?"
        + urlencode(params)
    )


def _build_met_norway_url():
    params = {
        "lat": f"{float(ACTIVE_WEATHER_LATITUDE):.6f}",
        "lon": f"{float(ACTIVE_WEATHER_LONGITUDE):.6f}",
    }

    return (
        MET_NORWAY_FORECAST_URL
        + "?"
        + urlencode(params)
    )


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
        return ("情報なし", "☁️")

    return WMO_WEATHER.get(
        normalized,
        ("情報なし", "☁️")
    )


def _normalize_weather_response(data, model_label):
    daily = data.get("daily")

    if not isinstance(daily, dict):
        raise RuntimeError(
            "Open-Meteo response does not contain daily data"
        )

    dates = daily.get("time")

    if not isinstance(dates, list) or not dates:
        raise RuntimeError(
            "Open-Meteo response does not contain daily dates"
        )

    weather_codes = daily.get("weather_code") or []
    max_temps = daily.get("temperature_2m_max") or []
    min_temps = daily.get("temperature_2m_min") or []
    rain_probs = daily.get("precipitation_probability_max") or []

    forecasts = []

    for index, iso_date in enumerate(dates[:7]):
        try:
            current_date = datetime.strptime(
                str(iso_date),
                "%Y-%m-%d"
            ).date()
        except (ValueError, TypeError):
            continue

        weather_name, icon = _weather_code_info(
            weather_codes[index]
            if index < len(weather_codes)
            else None
        )

        forecasts.append({
            "date": current_date.isoformat(),
            "date_label": (
                f"{current_date.month}/{current_date.day}"
            ),
            "weekday": WEEKDAYS_JA[current_date.weekday()],
            "weather": weather_name,
            "icon": icon,
            "max_temperature": _format_weather_value(
                max_temps[index]
                if index < len(max_temps)
                else None,
                "℃"
            ),
            "min_temperature": _format_weather_value(
                min_temps[index]
                if index < len(min_temps)
                else None,
                "℃"
            ),
            "precipitation_probability": _format_weather_value(
                rain_probs[index]
                if index < len(rain_probs)
                else None,
                "%"
            ),
        })

    if not forecasts:
        raise RuntimeError(
            "No usable Open-Meteo daily forecast data"
        )

    return {
        "forecasts": forecasts,
        "model": model_label,
        "provider": "Open-Meteo",
        "latitude": ACTIVE_WEATHER_LATITUDE,
        "longitude": ACTIVE_WEATHER_LONGITUDE,
        "updated_at": datetime.now(JST).strftime(
            "%Y-%m-%d %H:%M"
        ),
    }


_MET_SYMBOL_INFO = {
    "clearsky": ("晴れ", "☀️"),
    "fair": ("晴れ", "🌤️"),
    "partlycloudy": ("一部曇り", "⛅"),
    "cloudy": ("曇り", "☁️"),
    "fog": ("霧", "🌫️"),
    "lightrain": ("弱い雨", "🌦️"),
    "rain": ("雨", "🌧️"),
    "heavyrain": ("強い雨", "🌧️"),
    "lightsnow": ("弱い雪", "🌨️"),
    "snow": ("雪", "❄️"),
    "heavysnow": ("強い雪", "❄️"),
    "sleet": ("みぞれ", "🌨️"),
    "rainshowers": ("にわか雨", "🌦️"),
    "heavyrainshowers": ("強いにわか雨", "🌧️"),
    "snowshowers": ("にわか雪", "🌨️"),
    "thunder": ("雷雨", "⛈️"),
}


def _met_symbol_info(symbol_code):
    raw = str(symbol_code or "").strip().lower()

    # clearsky_day / rainshowersandthunder_night などの
    # day/night/polartwilight接尾辞を除く。
    for suffix in (
        "_day",
        "_night",
        "_polartwilight"
    ):
        if raw.endswith(suffix):
            raw = raw[:-len(suffix)]
            break

    # 雷を含む場合は雷雨として扱う。
    if "thunder" in raw:
        return ("雷雨", "⛈️")

    # より具体的な語を先に判定。
    checks = (
        "heavyrainshowers",
        "rainshowers",
        "heavyrain",
        "lightrain",
        "rain",
        "heavysnow",
        "snowshowers",
        "lightsnow",
        "snow",
        "sleet",
        "partlycloudy",
        "clearsky",
        "cloudy",
        "fair",
        "fog",
    )

    for key in checks:
        if key in raw:
            return _MET_SYMBOL_INFO.get(
                key,
                ("情報なし", "☁️")
            )

    return ("情報なし", "☁️")


def _parse_iso_datetime(value):
    text = str(value or "").strip()

    if not text:
        return None

    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"

        parsed = datetime.fromisoformat(text)

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed.astimezone(JST)

    except ValueError:
        return None


def _normalize_met_norway_response(data):
    properties = (
        data.get("properties")
        if isinstance(data, dict)
        else None
    )

    timeseries = (
        properties.get("timeseries")
        if isinstance(properties, dict)
        else None
    )

    if not isinstance(timeseries, list) or not timeseries:
        raise RuntimeError(
            "MET Norway response does not contain timeseries"
        )

    grouped = {}

    for entry in timeseries:
        if not isinstance(entry, dict):
            continue

        local_dt = _parse_iso_datetime(
            entry.get("time")
        )

        if local_dt is None:
            continue

        day_key = local_dt.date().isoformat()
        bucket = grouped.setdefault(
            day_key,
            {
                "temps": [],
                "symbols": [],
                "precipitation": [],
            }
        )

        entry_data = entry.get("data") or {}
        instant = entry_data.get("instant") or {}
        details = instant.get("details") or {}

        temperature = details.get("air_temperature")

        try:
            if temperature is not None:
                bucket["temps"].append(
                    float(temperature)
                )
        except (TypeError, ValueError):
            pass

        symbol_code = None
        precipitation_amount = None

        for period_key in (
            "next_1_hours",
            "next_6_hours",
            "next_12_hours"
        ):
            period = entry_data.get(period_key)

            if not isinstance(period, dict):
                continue

            summary = period.get("summary") or {}
            details_period = period.get("details") or {}

            if symbol_code is None:
                symbol_code = summary.get("symbol_code")

            if precipitation_amount is None:
                precipitation_amount = details_period.get(
                    "precipitation_amount"
                )

        if symbol_code:
            # 昼頃の情報を優先するため時刻も保持。
            bucket["symbols"].append(
                (
                    abs(local_dt.hour - 12),
                    str(symbol_code)
                )
            )

        try:
            if precipitation_amount is not None:
                bucket["precipitation"].append(
                    float(precipitation_amount)
                )
        except (TypeError, ValueError):
            pass

    forecasts = []
    today = datetime.now(JST).date()

    for offset in range(7):
        current_date = today + timedelta(days=offset)
        key = current_date.isoformat()
        bucket = grouped.get(key)

        if not bucket:
            continue

        temps = bucket.get("temps") or []
        symbols = bucket.get("symbols") or []

        if symbols:
            symbols.sort(key=lambda item: item[0])
            weather_name, icon = _met_symbol_info(
                symbols[0][1]
            )
        else:
            weather_name, icon = ("情報なし", "☁️")

        max_temp = max(temps) if temps else None
        min_temp = min(temps) if temps else None

        forecasts.append({
            "date": key,
            "date_label": (
                f"{current_date.month}/{current_date.day}"
            ),
            "weekday": WEEKDAYS_JA[current_date.weekday()],
            "weather": weather_name,
            "icon": icon,
            "max_temperature": _format_weather_value(
                max_temp,
                "℃"
            ),
            "min_temperature": _format_weather_value(
                min_temp,
                "℃"
            ),
            # MET Norway compact APIにはOpen-Meteoと同じ形式の
            # 日最大降水確率がないため、推測せず「情報なし」。
            "precipitation_probability": "情報なし",
        })

    if not forecasts:
        raise RuntimeError(
            "No usable MET Norway daily forecast data"
        )

    return {
        "forecasts": forecasts,
        "model": "MET Norway Locationforecast（予備）",
        "provider": "MET Norway",
        "latitude": ACTIVE_WEATHER_LATITUDE,
        "longitude": ACTIVE_WEATHER_LONGITUDE,
        "updated_at": datetime.now(JST).strftime(
            "%Y-%m-%d %H:%M"
        ),
    }


def get_weather_forecast():
    """
    現在選択中の地域の7日間天気予報を取得する。

    取得優先順位:
      1. 30分以内のメモリキャッシュ
      2. Open-Meteo
      3. MET Norway（自動バックアップ）
      4. 保存済みファイルキャッシュ

    外部APIの一時障害だけで天気欄が空にならないようにする。
    """
    now = datetime.now(JST)

    if _weather_cache.get("region_code") != ACTIVE_REGION_CODE:
        _weather_cache["region_code"] = ACTIVE_REGION_CODE
        _weather_cache["data"] = None
        _weather_cache["expires_at"] = None

    cached_data = _weather_cache.get("data")
    expires_at = _weather_cache.get("expires_at")

    if (
        cached_data is not None
        and expires_at is not None
        and now < expires_at
    ):
        print(
            "[WEATHER]",
            ACTIVE_REGION_NAME,
            "| memory cache HIT"
        )
        return (cached_data, None)

    errors = []

    # -----------------------------------------------------
    # 1. Open-Meteo
    # -----------------------------------------------------
    try:
        weather_data = _http_get_json(
            _build_weather_url(),
            "Open-Meteo"
        )

        normalized = _normalize_weather_response(
            weather_data,
            "Open-Meteo Best Match"
        )

        _weather_cache["region_code"] = ACTIVE_REGION_CODE
        _weather_cache["data"] = normalized
        _weather_cache["expires_at"] = (
            now + WEATHER_CACHE_TTL
        )

        _save_weather_file_cache(
            normalized
        )

        print(
            "[WEATHER]",
            ACTIVE_REGION_NAME,
            "| provider = Open-Meteo",
            "| lat =",
            ACTIVE_WEATHER_LATITUDE,
            "| lon =",
            ACTIVE_WEATHER_LONGITUDE
        )

        return (normalized, None)

    except Exception as exc:
        errors.append(
            f"Open-Meteo: {repr(exc)}"
        )
        print(
            "[WEATHER ERROR]",
            ACTIVE_REGION_NAME,
            "| Open-Meteo |",
            repr(exc)
        )

    # -----------------------------------------------------
    # 2. MET Norway backup
    # -----------------------------------------------------
    try:
        backup_data = _http_get_json(
            _build_met_norway_url(),
            "MET Norway"
        )

        normalized = _normalize_met_norway_response(
            backup_data
        )

        _weather_cache["region_code"] = ACTIVE_REGION_CODE
        _weather_cache["data"] = normalized
        _weather_cache["expires_at"] = (
            now + WEATHER_CACHE_TTL
        )

        _save_weather_file_cache(
            normalized
        )

        print(
            "[WEATHER]",
            ACTIVE_REGION_NAME,
            "| provider = MET Norway backup",
            "| lat =",
            ACTIVE_WEATHER_LATITUDE,
            "| lon =",
            ACTIVE_WEATHER_LONGITUDE
        )

        # 予備APIでも画面自体は正常表示させる。
        return (normalized, None)

    except Exception as exc:
        errors.append(
            f"MET Norway: {repr(exc)}"
        )
        print(
            "[WEATHER ERROR]",
            ACTIVE_REGION_NAME,
            "| MET Norway |",
            repr(exc)
        )

    # -----------------------------------------------------
    # 3. 期限切れメモリキャッシュ
    # -----------------------------------------------------
    if cached_data is not None:
        print(
            "[WEATHER]",
            ACTIVE_REGION_NAME,
            "| using stale memory cache"
        )
        return (cached_data, None)

    # -----------------------------------------------------
    # 4. 保存済みファイルキャッシュ
    # -----------------------------------------------------
    file_cached = _load_weather_file_cache()

    if file_cached is not None:
        _weather_cache["region_code"] = ACTIVE_REGION_CODE
        _weather_cache["data"] = file_cached
        _weather_cache["expires_at"] = (
            now + timedelta(minutes=10)
        )

        print(
            "[WEATHER]",
            ACTIVE_REGION_NAME,
            "| using file cache"
        )

        return (file_cached, None)

    # どの取得元も失敗し、キャッシュもない場合だけエラー表示。
    print(
        "[WEATHER FATAL]",
        ACTIVE_REGION_NAME,
        "|",
        " || ".join(errors)
    )

    return (
        None,
        (
            "現在、天気予報を取得できません。"
            "数分後にページを再読み込みしてください。"
        )
    )


# =========================================================
# 施設レビュー機能（PostgreSQL）
# =========================================================

REVIEW_FACILITY_TYPES = {
    "観光地",
    "飲食店",
    "宿泊施設",
}


def _review_database_ready():
    """レビューDBを利用できる状態か確認する。"""
    return bool(DATABASE_URL and psycopg is not None)


def _ensure_review_table():
    """reviewsテーブルが無ければ作成する。"""
    if not _review_database_ready():
        return False

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS reviews (
                    id BIGSERIAL PRIMARY KEY,
                    facility_type TEXT NOT NULL,
                    facility_name TEXT NOT NULL,
                    rating SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
                    nickname VARCHAR(40) NOT NULL,
                    comment VARCHAR(500) NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS reviews_facility_idx
                ON reviews (facility_type, facility_name, created_at DESC)
                """
            )
        conn.commit()

    return True


def _review_facility_exists(facility_type, facility_name):
    """投稿先がサイトに登録済みの施設か確認する。"""
    if facility_type not in REVIEW_FACILITY_TYPES:
        return False

    catalog = build_favorite_catalog()
    rows = catalog.get(facility_type, [])

    return any(
        str(item.get("name") or "").strip() == facility_name
        for item in rows
        if isinstance(item, dict)
    )


@app.route("/api/reviews", methods=["GET"])
def get_reviews():
    facility_type = str(
        request.args.get("facility_type") or ""
    ).strip()
    facility_name = str(
        request.args.get("facility_name") or ""
    ).strip()

    if not facility_type or not facility_name:
        return jsonify({
            "ok": False,
            "error": "施設の種類と施設名を指定してください。",
        }), 400

    if facility_type not in REVIEW_FACILITY_TYPES:
        return jsonify({
            "ok": False,
            "error": "施設の種類が正しくありません。",
        }), 400

    if not _review_database_ready():
        return jsonify({
            "ok": False,
            "error": "レビュー用データベースに接続できません。",
        }), 503

    try:
        _ensure_review_table()

        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, rating, nickname, comment, created_at
                    FROM reviews
                    WHERE facility_type = %s
                      AND facility_name = %s
                    ORDER BY created_at DESC, id DESC
                    LIMIT 100
                    """,
                    (facility_type, facility_name),
                )
                rows = cur.fetchall()

                cur.execute(
                    """
                    SELECT COUNT(*), COALESCE(AVG(rating), 0)
                    FROM reviews
                    WHERE facility_type = %s
                      AND facility_name = %s
                    """,
                    (facility_type, facility_name),
                )
                count, average = cur.fetchone()

    except Exception as exc:
        print("Review GET error:", exc)
        return jsonify({
            "ok": False,
            "error": "レビューを取得できませんでした。",
        }), 500

    reviews = []
    for row in rows:
        created_at = row[4]
        reviews.append({
            "id": row[0],
            "rating": row[1],
            "nickname": row[2],
            "comment": row[3],
            "created_at": (
                created_at.isoformat()
                if hasattr(created_at, "isoformat")
                else str(created_at)
            ),
        })

    return jsonify({
        "ok": True,
        "facility_type": facility_type,
        "facility_name": facility_name,
        "count": int(count or 0),
        "average_rating": round(float(average or 0), 1),
        "reviews": reviews,
    })


@app.route("/api/reviews", methods=["POST"])
def post_review():
    body = request.get_json(silent=True) or {}

    facility_type = str(
        body.get("facility_type") or ""
    ).strip()
    facility_name = str(
        body.get("facility_name") or ""
    ).strip()
    nickname = str(
        body.get("nickname") or ""
    ).strip()
    comment = str(
        body.get("comment") or ""
    ).strip()

    try:
        rating = int(body.get("rating"))
    except (TypeError, ValueError):
        rating = 0

    if facility_type not in REVIEW_FACILITY_TYPES:
        return jsonify({
            "ok": False,
            "error": "施設の種類が正しくありません。",
        }), 400

    if not facility_name or len(facility_name) > 150:
        return jsonify({
            "ok": False,
            "error": "施設名が正しくありません。",
        }), 400

    if not _review_facility_exists(facility_type, facility_name):
        return jsonify({
            "ok": False,
            "error": "登録されていない施設には投稿できません。",
        }), 400

    if rating < 1 or rating > 5:
        return jsonify({
            "ok": False,
            "error": "星評価は1〜5で選んでください。",
        }), 400

    if not nickname:
        return jsonify({
            "ok": False,
            "error": "ニックネームを入力してください。",
        }), 400

    if len(nickname) > 40:
        return jsonify({
            "ok": False,
            "error": "ニックネームは40文字以内にしてください。",
        }), 400

    if not comment:
        return jsonify({
            "ok": False,
            "error": "コメントを入力してください。",
        }), 400

    if len(comment) > 500:
        return jsonify({
            "ok": False,
            "error": "コメントは500文字以内にしてください。",
        }), 400

    if not _review_database_ready():
        return jsonify({
            "ok": False,
            "error": "レビュー用データベースに接続できません。",
        }), 503

    try:
        _ensure_review_table()

        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO reviews (
                        facility_type,
                        facility_name,
                        rating,
                        nickname,
                        comment
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id, created_at
                    """,
                    (
                        facility_type,
                        facility_name,
                        rating,
                        nickname,
                        comment,
                    ),
                )
                review_id, created_at = cur.fetchone()
            conn.commit()

    except Exception as exc:
        print("Review POST error:", exc)
        return jsonify({
            "ok": False,
            "error": "レビューを保存できませんでした。",
        }), 500

    return jsonify({
        "ok": True,
        "message": "レビューを投稿しました。",
        "review": {
            "id": review_id,
            "facility_type": facility_type,
            "facility_name": facility_name,
            "rating": rating,
            "nickname": nickname,
            "comment": comment,
            "created_at": (
                created_at.isoformat()
                if hasattr(created_at, "isoformat")
                else str(created_at)
            ),
        },
    }), 201


# =========================================================
# AI旅行アシスタント
# =========================================================

def _extract_openai_text(
    response_data
):

    if not isinstance(
        response_data,
        dict
    ):

        return ""


    direct = (
        response_data.get(
            "output_text"
        )
    )


    if (
        isinstance(
            direct,
            str
        )
        and
        direct.strip()
    ):

        return direct.strip()


    texts = []


    for output_item in (
        response_data.get(
            "output",
            []
        )
        or
        []
    ):

        if not isinstance(
            output_item,
            dict
        ):

            continue


        for content in (
            output_item.get(
                "content",
                []
            )
            or
            []
        ):

            if not isinstance(
                content,
                dict
            ):

                continue


            text_value = (
                content.get(
                    "text"
                )
            )


            if (
                isinstance(
                    text_value,
                    str
                )
                and
                text_value.strip()
            ):

                texts.append(
                    text_value.strip()
                )


    return "\n".join(
        texts
    ).strip()


def _compact_ai_plan(
    plan
):

    if not isinstance(
        plan,
        dict
    ):

        return {}


    def compact_place(
        item
    ):

        if not isinstance(
            item,
            dict
        ):

            return None


        return {

            "name":
                item.get(
                    "name"
                ),

            "area":
                item.get(
                    "area"
                ),

            "description":
                item.get(
                    "description"
                ),

            "time":
                item.get(
                    "time"
                ),

            "address":
                item.get(
                    "address"
                ),

            "hours":
                item.get(
                    "hours"
                ),

            "closed":
                item.get(
                    "closed"
                ),

            "price":
                item.get(
                    "price"
                ),

            "car_free":
                item.get(
                    "car_free"
                ),

            "recommendation_reason":
                item.get(
                    "recommendation_reason"
                )

        }


    def compact_list(
        items,
        limit=8
    ):

        result = []


        for item in (
            items
            or
            []
        )[:limit]:

            compacted = (
                compact_place(
                    item
                )
            )


            if compacted:

                result.append(
                    compacted
                )


        return result


    return {

        "travel_date":
            plan.get(
                "travel_date"
            ),

        "season":
            plan.get(
                "season"
            ),

        "age":
            plan.get(
                "age"
            ),

        "people":
            plan.get(
                "people"
            ),

        "member":
            plan.get(
                "member"
            ),

        "car":
            plan.get(
                "car"
            ),

        "days":
            plan.get(
                "days"
            ),

        "budget":
            plan.get(
                "budget"
            ),

        "purpose":
            plan.get(
                "purpose"
            ),

        "trip_style":
            plan.get(
                "trip_style"
            ),

        "trip_summary":
            plan.get(
                "trip_summary"
            ),

        "day1":
            compact_list(
                plan.get(
                    "day1"
                )
            ),

        "day2":
            compact_list(
                plan.get(
                    "day2"
                )
            ),

        "day3":
            compact_list(
                plan.get(
                    "day3"
                )
            ),

        "restaurants":
            compact_list(

                plan.get(
                    "recommended_restaurants"
                ),

                6

            ),

        "hotel":
            compact_place(
                plan.get(
                    "hotel"
                )
            ),

        "other_hotels":
            compact_list(

                plan.get(
                    "other_hotels"
                ),

                5

            )

    }


@app.route(
    "/api/ai-chat",
    methods=[
        "POST"
    ]
)
def ai_chat():

    api_key = (
        os.environ.get(
            "OPENAI_API_KEY",
            ""
        ).strip()
    )


    if not api_key:

        return jsonify({

            "ok":
                False,

            "error":
                (
                    "AI機能を使うには、"
                    "サーバー側にOPENAI_API_KEYを"
                    "設定してください。"
                )

        }), 503


    body = (
        request.get_json(
            silent=True
        )
        or
        {}
    )


    message = str(
        body.get(
            "message"
        )
        or
        ""
    ).strip()


    if not message:

        return jsonify({

            "ok":
                False,

            "error":
                "相談内容を入力してください。"

        }), 400


    if len(message) > 800:

        return jsonify({

            "ok":
                False,

            "error":
                "相談内容は800文字以内にしてください。"

        }), 400


    plan = (
        _compact_ai_plan(
            body.get(
                "plan"
            )
        )
    )


    conversation = (

        body.get(
            "conversation"
        )

        if isinstance(
            body.get(
                "conversation"
            ),
            list
        )

        else []

    )


    recent = []


    for item in conversation[-6:]:

        if not isinstance(
            item,
            dict
        ):

            continue


        role = (

            "user"

            if item.get(
                "role"
            )
            ==
            "user"

            else
            "assistant"

        )


        text_value = str(
            item.get(
                "text"
            )
            or
            ""
        ).strip()


        if text_value:

            recent.append({

                "role":
                    role,

                "text":
                    text_value[:600]

            })


    plan_json = json.dumps(
        plan,
        ensure_ascii=False,
        separators=(
            ",",
            ":"
        )
    )


    recent_json = json.dumps(
        recent,
        ensure_ascii=False,
        separators=(
            ",",
            ":"
        )
    )


    instructions = (

        "あなたは秩父旅行プランナーの"
        "AI旅行アシスタントです。"
        "回答は日本語で、短く分かりやすく、"
        "旅行者が次に何をすればよいか分かる形にしてください。"
        "必ず与えられた旅行プランの内容を優先し、"
        "存在しない営業時間、料金、混雑、運休、天気、"
        "移動時間などを推測しないでください。"
        "プラン内に根拠がない最新情報を尋ねられた場合は、"
        "確認が必要だと明記してください。"

    )


    user_input = (

        "現在の旅行プラン:\n"
        +
        plan_json
        +
        "\n\n直近の会話:\n"
        +
        recent_json
        +
        "\n\n今回の相談:\n"
        +
        message

    )


    model = (

        os.environ.get(
            "OPENAI_MODEL",
            "gpt-5.6-luna"
        ).strip()

        or
        "gpt-5.6-luna"

    )


    payload = json.dumps({

        "model":
            model,

        "instructions":
            instructions,

        "input":
            user_input,

        "max_output_tokens":
            700

    },
        ensure_ascii=False
    ).encode(
        "utf-8"
    )


    req = urllib.request.Request(

        "https://api.openai.com/v1/responses",

        data=payload,

        headers={

            "Authorization":
                f"Bearer {api_key}",

            "Content-Type":
                "application/json"

        },

        method="POST"

    )


    try:

        with urllib.request.urlopen(
            req,
            timeout=25
        ) as response:

            response_data = json.loads(

                response
                .read()
                .decode(
                    "utf-8"
                )

            )


    except urllib.error.HTTPError as exc:

        print(
            "OpenAI API HTTP error:",
            exc.code
        )


        return jsonify({

            "ok":
                False,

            "error":
                (
                    "AIから回答を取得できませんでした。"
                    "少し待ってからもう一度試してください。"
                )

        }), 502


    except (
        urllib.error.URLError,
        TimeoutError,
        json.JSONDecodeError
    ) as exc:

        print(
            "OpenAI API connection error:",
            exc
        )


        return jsonify({

            "ok":
                False,

            "error":
                (
                    "AIへの接続に失敗しました。"
                    "ネットワークを確認してください。"
                )

        }), 502


    answer = (
        _extract_openai_text(
            response_data
        )
    )


    if not answer:

        return jsonify({

            "ok":
                False,

            "error":
                "AIの回答を読み取れませんでした。"

        }), 502


    return jsonify({

        "ok":
            True,

        "answer":
            answer

    })


# =========================================================
# 各ページ
# =========================================================

@app.route(
    "/trip-book"
)
def trip_book():

    return render_template(
        "trip_book.html"
    )


@app.route(
    "/history"
)
def history():

    return render_template(
        "history.html"
    )


@app.route(
    "/favorites"
)
def favorites():

    return render_template(

        "favorites.html",

        favorite_catalog=
            build_favorite_catalog()

    )


@app.route("/")
def start():

    return render_template(
        "area_select.html"
    )


@app.route(
    "/areas"
)
def area_select():

    return render_template(
        "area_select.html"
    )


def _render_region_input(region_code):
    config = activate_region(region_code)

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
        region_code=region_code,
        region_name=config["name"],
        region_name_en=config["name_en"],
        purpose_options=config.get("purpose_options", []),
        arrival_options=[
            {
                "value": value,
                "label": label,
                "selected": value == config["default_arrival"],
            }
            for value, label in config["arrival_labels"].items()
        ],
        weather_forecast=weather_forecast,
        weather_error=weather_error,
        weather_model=weather_model,
        today_jst=_weather_jst_today(),
        spot_options=[
            {
                "name": spot.get("name", ""),
                "area": spot.get("area", "")
            }
            for spot in spots
            if spot.get("name")
        ]
    )


@app.route(
    "/chichibu"
)
def chichibu():
    return _render_region_input("chichibu")


@app.route(
    "/kawagoe"
)
def kawagoe():
    return _render_region_input("kawagoe")


@app.route(
    "/hanno"
)
def hanno():
    return render_template(
        "regional_input.html",
        region_name="飯能",
        region_name_en="HANNO",
        region_code="hanno",
        available=False,
        intro="森林・湖・アウトドアなど、自然を楽しむ旅行プランへ対応予定です。",
        feature_tags=[
            "森林",
            "アウトドア",
            "自然",
            "宿泊"
        ]
    )


@app.route(
    "/recommend"
)
def index():
    return _render_region_input("chichibu")


@app.route(
    "/manual-plan"
)
def manual_plan():

    return render_template(

        "manual_plan.html",

        manual_catalog=
            build_favorite_catalog(),

        today_jst=
            _weather_jst_today()

    )


@app.route(
    "/manual-plan/view"
)
def manual_plan_view():

    return render_template(
        "manual_plan_view.html"
    )


# =========================================================
# 結果ページ
# =========================================================

@app.route(
    "/result",
    methods=[
        "POST"
    ]
)
def result():

    region_code = str(
        request.form.get("region_code") or "chichibu"
    ).strip()

    if region_code not in REGION_CONFIG:
        return (
            "地域指定に問題があります。"
            "最初からやり直してください。",
            400
        )

    region_config = activate_region(region_code)

    try:

        age = int(
            request.form.get(
                "age",
                20
            )
        )


        # 性別は推薦に利用していないため入力項目から削除。
        # 既存処理との互換性のため内部では固定値を保持する。
        gender = "未使用"


        people = int(
            request.form.get(
                "people",
                2
            )
        )


        member = request.form.get(
            "member",
            "友人"
        )


        # システム全体を車移動に固定する。
        # フォームから異なる値が送信されても車扱いにする。
        car = "あり"


        purpose = request.form.getlist(
            "purpose"
        )


        must_visit_names = [
            str(name).strip()
            for name
            in request.form.getlist(
                "must_visit_spots"
            )
            if str(name).strip()
        ]


        budget = int(
            request.form.get(
                "budget",
                20000
            )
        )


        days = request.form.get(
            "days",
            "1泊2日"
        )


        travel_date = (
            request.form.get(
                "travel_date",
                ""
            )
            .strip()
        )


        # 「観光中の歩く量」は入力項目から廃止。
        # 既存関数との互換性のため内部値だけ固定する。
        walking_amount = "普通"


        travel_pace = request.form.get(
            "travel_pace",
            "普通"
        )


        # 移動は車に統一。
        travel_mode = "車"

        arrival_detail = request.form.get(
            "arrival_detail",
            region_config["default_arrival"]
        ).strip()

        if arrival_detail not in set(
            region_config["arrival_labels"].keys()
        ):
            arrival_detail = region_config["default_arrival"]

        start_point = arrival_detail

        (
            walking_amount,
            travel_pace,
            start_point
        ) = normalize_travel_preferences(
            walking_amount,
            travel_pace,
            start_point
        )


    except (
        ValueError,
        TypeError
    ):

        return (
            "入力内容に問題があります。"
            "最初からやり直してください。"
        )


    valid_spot_names = {
        str(spot.get("name") or "").strip()
        for spot in spots
        if str(spot.get("name") or "").strip()
    }

    invalid_must_visit_names = [
        name
        for name in must_visit_names
        if name not in valid_spot_names
    ]

    if invalid_must_visit_names:

        return (
            "行きたい場所の指定に問題があります。"
            "画面を再読み込みして選び直してください。",
            400
        )

    # 現行の1泊2日/2泊3日の旅程構成では、
    # 6件以上を必須にすると表示・移動計算が過密になるため、
    # S1の時間制約対応までは最大5件とする。
    if len(must_visit_names) > 5:

        return (
            "行きたい場所は現在5か所まで指定できます。"
            "S1の時間制約対応後に上限を見直します。",
            400
        )


    # =====================================================
    # 人数と旅行メンバーの整合性
    # =====================================================

    if people == 1:

        member = "一人"


    elif member == "一人":

        return (

            "入力内容に矛盾があります。"
            "2人以上の場合は旅行メンバーを"
            "選び直してください。",

            400

        )


    # 目的未選択は「おまかせ」として扱う。
    # 特定の目的に勝手に固定しない。
    if not purpose:

        purpose = []


    # =====================================================
    # 車移動に統一
    # =====================================================

    travel_mode = "車"

    route_start_point = start_point
    start_point_display = start_point

    arrival_method_label = (
        ARRIVAL_METHOD_LABELS.get(
            start_point,
            start_point
        )
    )


    today_jst = (
        _weather_jst_today()
    )


    if (
        travel_date
        and
        travel_date < today_jst
    ):

        travel_date = ""


    season = (
        get_season_from_date(
            travel_date
        )
    )


    recommendation_seed = (
        make_recommendation_seed(

            age,
            gender,
            people,
            member,
            car,
            days,
            budget,
            purpose,
            travel_date,
            walking_amount,
            travel_pace,
            start_point

        )
    )


    request_nonce = int.from_bytes(

        os.urandom(
            8
        ),

        "big"

    )


    trip_style = (
        get_trip_style(
            member,
            purpose,
            age
        )
    )

    if ACTIVE_REGION_NAME != "秩父":
        trip_style = str(trip_style).replace(
            "秩父",
            ACTIVE_REGION_NAME
        )


    # =====================================================
    # グルメ推薦
    # =====================================================

    restaurant_scores = []


    for restaurant in restaurants:

        (
            score,
            reasons,
            breakdown

        ) = calculate_restaurant_score(

            restaurant,
            member,
            purpose,
            car,
            people,
            budget,
            age,
            days,
            gender,
            walking_amount,
            travel_pace

        )


        restaurant_scores.append({

            "score":
                score,

            "restaurant":
                restaurant,

            "reasons":
                reasons,

            "breakdown":
                breakdown,

            "name":
                restaurant.get(
                    "name",
                    ""
                ),

            "area":
                restaurant.get(
                    "area",
                    ""
                ),

            "genre":
                restaurant.get(
                    "genre",
                    []
                )

        })


    restaurant_scores.sort(

        key=lambda x:
            x["score"],

        reverse=True

    )


    recommended_restaurants = []


    restaurant_target = (

        4

        if days
        ==
        "1泊2日"

        else
        6

    )


    selected_restaurants = (
        diverse_select(

            restaurant_scores,

            restaurant_target,

            recommendation_seed
            +
            101,

            key_name="name",

            group_names=[
                "area",
                "genre"
            ],

            request_nonce=
                request_nonce

        )
    )


    for item in selected_restaurants:

        restaurant = (
            attach_map_data(
                item[
                    "restaurant"
                ]
            )
        )


        restaurant[
            "score"
        ] = item[
            "score"
        ]


        restaurant[
            "reasons"
        ] = item[
            "reasons"
        ]


        restaurant = (
            attach_score_visualization(

                restaurant,

                item[
                    "breakdown"
                ]

            )
        )


        recommended_restaurants.append(
            restaurant
        )


    # =====================================================
    # 観光地推薦
    # =====================================================

    spot_scores = []


    for spot in spots:

        (
            score,
            reasons,
            breakdown

        ) = calculate_spot_score(

            spot,
            member,
            purpose,
            car,
            age,
            people,
            days,
            budget,
            gender,
            walking_amount,
            travel_pace,

            season=
                season,

            travel_date=
                travel_date

        )


        # 明確に営業期間外と判定された施設は、
        # 推薦候補そのものから除外する。
        if score <= -900:

            continue


        spot_scores.append({

            "score":
                score,

            "spot":
                spot,

            "reasons":
                reasons,

            "breakdown":
                breakdown,

            "name":
                spot.get(
                    "name",
                    ""
                ),

            "area":
                spot.get(
                    "area",
                    ""
                ),

            "type":
                spot.get(
                    "type",
                    ""
                ),

            "season":
                spot.get(
                    "season"
                ),

            "best_season":
                spot.get(
                    "best_season"
                ),

            "seasonal_operation":
                spot.get(
                    "seasonal_operation"
                )

        })


    spot_scores.sort(

        key=lambda x:
            x[
                "score"
            ],

        reverse=True

    )


    spot_target = (
        get_spot_target_count(
            days,
            travel_pace
        )
    )


    selected_spots = (
        diverse_select(

            spot_scores,

            max(
                spot_target,
                len(must_visit_names)
            ),

            recommendation_seed
            +
            202,

            key_name=
                "name",

            group_names=[
                "area",
                "type"
            ],

            request_nonce=
                request_nonce

        )
    )


    # =====================================================
    # S21 行きたい場所を必ずプランに残す
    # =====================================================

    if must_visit_names:

        spot_score_by_name = {
            item.get("name", ""):
                item
            for item in spot_scores
        }

        forced_items = []

        for must_name in must_visit_names:

            source_item = (
                spot_score_by_name.get(
                    must_name
                )
            )

            if not source_item:
                continue

            forced_item = dict(
                source_item
            )

            forced_reasons = list(
                forced_item.get(
                    "reasons",
                    []
                )
            )

            forced_reasons.insert(
                0,
                "行きたい場所として指定"
            )

            forced_item[
                "reasons"
            ] = forced_reasons

            forced_items.append(
                forced_item
            )

        forced_names = {
            item.get("name", "")
            for item in forced_items
        }

        remaining_items = [
            item
            for item in selected_spots
            if item.get("name", "")
            not in forced_names
        ]

        selected_spots = (
            forced_items
            +
            remaining_items
        )[
            :max(
                spot_target,
                len(forced_items)
            )
        ]


    recommended_spots = []


    for item in selected_spots:

        spot = (
            attach_map_data(
                item[
                    "spot"
                ]
            )
        )


        spot[
            "score"
        ] = item[
            "score"
        ]


        spot[
            "reasons"
        ] = item[
            "reasons"
        ]


        spot = (
            attach_score_visualization(

                spot,

                item[
                    "breakdown"
                ]

            )
        )


        spot[
            "recommendation_reason"
        ] = (

            build_recommendation_reason(

                spot,

                item[
                    "reasons"
                ],

                age,
                people,
                member,
                car,
                days,
                budget,
                purpose,
                travel_date,
                season,

                category=
                    "spot"

            )

        )


        recommended_spots.append(
            spot
        )


    # =====================================================
    # 宿泊施設推薦
    # =====================================================

    hotel_scores = []


    for hotel in hotels:

        (
            score,
            reasons,
            breakdown

        ) = calculate_hotel_score(

            hotel,
            member,
            purpose,
            budget,
            people,
            age,
            car,
            days,
            gender,
            walking_amount,
            travel_pace,

            season=
                season,

            travel_date=
                travel_date

        )


        hotel_scores.append({

            "score":
                score,

            "hotel":
                hotel,

            "reasons":
                reasons,

            "breakdown":
                breakdown,

            "name":
                hotel.get(
                    "name",
                    ""
                ),

            "type":
                hotel.get(
                    "type",
                    ""
                )

        })


    # =====================================================
    # S1完成：宿を複数試して旅行全体で最良を選ぶ
    # =====================================================

    s1_best = (
        build_s1_best_hotel_plan(

            hotel_score_items=
                hotel_scores,

            spot_score_items=
                spot_scores,

            days=
                days,

            age=
                age,

            start_point=
                route_start_point,

            car=
                car,

            walking_amount=
                walking_amount,

            must_visit_names=
                must_visit_names,

            # ライブ画面では上位2軒を高速比較。
            # 行きたい場所が入らない場合だけ残りも追加比較する。
            max_hotels=
                3

        )
    )


    if s1_best:

        chosen_hotel_item = (
            s1_best[
                "hotel_item"
            ]
        )

        s1_plan = (
            s1_best[
                "plan"
            ]
        )

    else:

        # ルート最適化候補が作れない場合は、推薦点の高い宿を採用する。
        ranked_hotel_items = sorted(

            hotel_scores,

            key=lambda x:
                x[
                    "score"
                ],

            reverse=True

        )

        chosen_hotel_item = (
            ranked_hotel_items[
                0
            ]
        )

        s1_plan = None


    recommended_hotel = (
        _decorate_hotel_from_score_item(

            chosen_hotel_item,

            age=
                age,

            people=
                people,

            member=
                member,

            car=
                car,

            days=
                days,

            budget=
                budget,

            purpose=
                purpose,

            travel_date=
                travel_date,

            season=
                season

        )
    )


    s1_unavailable_must_visit = []

    preplanned_days = None


    if s1_plan:

        selected_spots = (
            s1_plan.get(
                "selected_score_items"
            )
            or []
        )

        s1_unavailable_must_visit = (
            s1_plan.get(
                "unavailable_must_visit"
            )
            or []
        )

        recommended_spots = []


        for item in selected_spots:

            spot = (
                attach_map_data(
                    item[
                        "spot"
                    ]
                )
            )


            spot[
                "score"
            ] = item[
                "score"
            ]


            spot[
                "reasons"
            ] = item[
                "reasons"
            ]


            spot = (
                attach_score_visualization(

                    spot,

                    item[
                        "breakdown"
                    ]

                )
            )

            spot = (
                normalize_place_for_display(
                    spot
                )
            )


            spot[
                "recommendation_reason"
            ] = (

                build_recommendation_reason(

                    spot,

                    item[
                        "reasons"
                    ],

                    age,
                    people,
                    member,
                    car,
                    days,
                    budget,
                    purpose,
                    travel_date,
                    season,

                    category=
                        "spot"

                )

            )


            spot = (
                normalize_place_for_display(
                    spot
                )
            )

            recommended_spots.append(
                spot
            )


        display_spot_by_name = {
            spot.get(
                "name",
                ""
            ):
                spot
            for spot in
            recommended_spots
        }


        preplanned_days = []


        for raw_day in (
            s1_plan.get(
                "day_spots"
            )
            or []
        ):

            display_day = []


            for raw_spot in raw_day:

                display_spot = (
                    display_spot_by_name.get(
                        raw_spot.get(
                            "name",
                            ""
                        )
                    )
                )


                if display_spot:

                    display_day.append(
                        display_spot
                    )


            preplanned_days.append(
                display_day
            )


    other_hotels = []


    for item in sorted(

        hotel_scores,

        key=lambda x:
            x[
                "score"
            ],

        reverse=True

    ):

        if (
            item[
                "hotel"
            ].get(
                "name"
            )
            ==
            recommended_hotel.get(
                "name"
            )
        ):

            continue


        hotel_item = (
            attach_map_data(
                item[
                    "hotel"
                ]
            )
        )


        hotel_item[
            "score"
        ] = (
            item[
                "score"
            ]
        )


        hotel_item[
            "reasons"
        ] = (
            item[
                "reasons"
            ]
        )


        hotel_item = (
            attach_score_visualization(

                hotel_item,

                item[
                    "breakdown"
                ]

            )
        )


        other_hotels.append(
            hotel_item
        )


    # =====================================================
    # 日程作成・実ルート計算
    # =====================================================

    (
        day1,
        day2,
        day3,
        route_days,
        route_summary

    ) = build_trip_routes(

        recommended_spots=
            recommended_spots,

        recommended_hotel=
            recommended_hotel,

        days=
            days,

        start_point=
            route_start_point,

        car=
            car,

        walking_amount=
            walking_amount,

        preplanned_days=
            preplanned_days

    )


    # ルート最適化後の日程順におすすめ観光地も更新する。
    recommended_spots = (
        day1
        +
        day2
        +
        day3
    )


    # =====================================================
    # S13：食事を旅行日程へ組み込む
    # =====================================================

    meal_schedule_raw = (
        build_s13_meal_schedule(

            restaurant_score_items=
                restaurant_scores,

            day_spots=
                [
                    day1,
                    day2
                ]
                +
                (
                    [
                        day3
                    ]
                    if days
                    ==
                    "2泊3日"
                    else []
                ),

            hotel=
                recommended_hotel,

            start_point=
                route_start_point,

            car=
                car,

            walking_amount=
                walking_amount

        )
    )


    meal_schedule = []


    for meal in meal_schedule_raw:

        restaurant_item = (
            meal.get(
                "restaurant_item"
            )
        )


        if not restaurant_item:
            continue


        display_meal = dict(
            meal
        )

        display_meal[
            "restaurant"
        ] = (
            _decorate_restaurant_from_score_item(
                restaurant_item
            )
        )

        display_meal.pop(
            "restaurant_item",
            None
        )

        meal_schedule.append(
            display_meal
        )


    # 日程に採用された飲食店をおすすめグルメの先頭へ。
    if meal_schedule:

        scheduled_names = []
        scheduled_restaurants = []


        for meal in meal_schedule:

            restaurant = (
                meal.get(
                    "restaurant"
                )
            )

            if not restaurant:
                continue

            name = (
                restaurant.get(
                    "name",
                    ""
                )
            )

            if (
                name
                and
                name
                not in scheduled_names
            ):

                scheduled_names.append(
                    name
                )

                scheduled_restaurants.append(
                    restaurant
                )


        remaining_restaurants = [
            restaurant
            for restaurant in
            recommended_restaurants
            if restaurant.get(
                "name",
                ""
            )
            not in scheduled_names
        ]


        recommended_restaurants = (
            scheduled_restaurants
            +
            remaining_restaurants
        )[
            :restaurant_target
        ]


    sightseeing_time = sum(

        spot.get(
            "time",
            0
        )

        for spot in
        recommended_spots

    )


    # =====================================================
    # 宿泊費・予算
    # =====================================================

    nights = (

        1

        if days
        ==
        "1泊2日"

        else
        2

    )


    hotel_price = (
        recommended_hotel.get(
            "price"
        )
        if isinstance(
            recommended_hotel,
            dict
        )
        else None
    )


    total_budget = (

        budget
        *
        people

    )


    if isinstance(
        hotel_price,
        (
            int,
            float
        )
    ):

        total_hotel_price = (
            hotel_price
            *
            people
            *
            nights
        )


        if total_budget > 0:

            budget_ratio = round(

                (
                    total_hotel_price
                    /
                    total_budget
                )
                *
                100

            )

        else:

            budget_ratio = 0


        if hotel_price <= budget:

            budget_status = (
                "予算内に収まりやすい宿です"
            )

        else:

            budget_status = (
                "予算を少し超える可能性があります"
            )


    else:

        # 川越など宿泊料金を固定値として確認していない場合は、
        # 推測料金を作らず結果画面でも「予約時確認」とする。
        total_hotel_price = None
        budget_ratio = None
        budget_status = (
            "宿泊料金は日付・人数・客室・プランで変動するため予約時に確認してください"
        )


    # =====================================================
    # 旅行の特徴
    # =====================================================

    feature_text = []

    if ACTIVE_REGION_CODE == "kawagoe":

        if "小江戸・町並み" in purpose:
            feature_text.append(
                "小江戸の町並みを満喫"
            )

        if "歴史・文化" in purpose:
            feature_text.append(
                "寺社・史跡・文化を巡る"
            )

        if "食べ歩き・グルメ" in purpose:
            feature_text.append(
                "川越グルメと食べ歩きを楽しむ"
            )

        if "自然・散策" in purpose:
            feature_text.append(
                "庭園や伊佐沼などをのんびり散策"
            )

    else:

        if "自然" in purpose:
            feature_text.append(
                f"{ACTIVE_REGION_NAME}の自然を満喫"
            )

        if "温泉" in purpose:
            feature_text.append(
                "温泉でゆったり"
            )

        if "グルメ" in purpose:
            feature_text.append(
                f"{ACTIVE_REGION_NAME}のグルメを堪能"
            )

        if "歴史" in purpose:
            feature_text.append(
                "歴史・文化を体験"
            )

    if must_visit_names:
        feature_text.append(
            "行きたい場所を優先"
        )

    feature_text.append(
        "車移動で効率よく観光"
    )

    if s1_plan:
        feature_text.append(
            "移動時間と滞在時間を考慮"
        )

    if s1_best:
        feature_text.append(
            "宿の位置まで比較して最適化"
        )

    if meal_schedule:
        feature_text.append(
            "食事の寄り道も考慮"
        )


    # =====================================================
    # TRIP SUMMARY
    # =====================================================

    trip_summary = (

        _build_trip_summary(

            age=
                age,

            people=
                people,

            member=
                member,

            car=
                car,

            days=
                days,

            budget=
                budget,

            purpose=
                purpose,

            travel_date=
                travel_date,

            season=
                season,

            recommended_spots=
                recommended_spots,

            recommended_hotel=
                recommended_hotel,

            recommended_restaurants=
                recommended_restaurants,

            sightseeing_time=
                sightseeing_time,

            day1=
                day1,

            day2=
                day2,

            day3=
                day3,

            meal_schedule=
                meal_schedule,

        )

    )


    # =====================================================
    # アルゴリズム見える化用まとめ
    # =====================================================

    score_summary = {

        "spots": [

            {

                "name":
                    spot.get(
                        "name",
                        ""
                    ),

                "score":
                    spot.get(
                        "score",
                        0
                    ),

                "score_breakdown":
                    spot.get(
                        "score_breakdown",
                        []
                    )

            }

            for spot in
            recommended_spots

        ],


        "restaurants": [

            {

                "name":
                    restaurant.get(
                        "name",
                        ""
                    ),

                "score":
                    restaurant.get(
                        "score",
                        0
                    ),

                "score_breakdown":
                    restaurant.get(
                        "score_breakdown",
                        []
                    )

            }

            for restaurant in
            recommended_restaurants

        ],


        "hotel": {

            "name":
                recommended_hotel.get(
                    "name",
                    ""
                ),

            "score":
                recommended_hotel.get(
                    "score",
                    0
                ),

            "score_breakdown":
                recommended_hotel.get(
                    "score_breakdown",
                    []
                )

        }

    }


    # =====================================================
    # 履歴保存用データ
    # =====================================================

    safe_route_days_for_history = (
        json.loads(
            json.dumps(
                route_days,
                ensure_ascii=False
            )
        )
    )


    history_payload = {

        "schemaVersion":
            3,

        "region_code":
            ACTIVE_REGION_CODE,

        "region_name":
            ACTIVE_REGION_NAME,

        "region_name_en":
            ACTIVE_REGION_NAME_EN,

        "age":
            age,

        "gender":
            gender,

        "people":
            people,

        "member":
            member,

        "car":
            car,

        "purpose":
            purpose,

        "budget":
            budget,

        "days":
            days,

        "travel_date":
            travel_date,

        "season":
            season,

        "trip_style":
            trip_style,

        "feature_text":
            feature_text,

        "day1":
            day1,

        "day2":
            day2,

        "day3":
            day3,

        "recommended_spots":
            recommended_spots,

        "recommended_restaurants":
            recommended_restaurants,

        "meal_schedule":
            meal_schedule,

        "s1_optimization":
            (
                {
                    "evaluated_hotel_count":
                        s1_best.get(
                            "evaluated_hotel_count",
                            0
                        ),
                    "travel_minutes":
                        s1_best.get(
                            "travel_minutes"
                        ),
                    "spot_score_total":
                        s1_best.get(
                            "spot_score_total"
                        ),
                    "hotel_score":
                        s1_best.get(
                            "hotel_score"
                        ),
                    "total_value":
                        round(
                            float(
                                s1_best.get(
                                    "total_value",
                                    0
                                )
                            ),
                            1
                        )
                }
                if s1_best
                else None
            ),

        "hotel":
            recommended_hotel,

        "other_hotels":
            other_hotels,

        "total_price":
            total_hotel_price,

        "total_budget":
            total_budget,

        "budget_ratio":
            budget_ratio,

        "budget_status":
            budget_status,

        "sightseeing_time":
            sightseeing_time,

        "trip_summary":
            trip_summary,

        "score_summary":
            score_summary,

        "route_days":
            safe_route_days_for_history,

        "route_summary":
            route_summary,

        "walking_amount":
            walking_amount,

        "travel_pace":
            travel_pace,

        "start_point":
            start_point_display,

        "travel_mode":
            travel_mode,

        "arrival_detail":
            arrival_detail,

        "arrival_method_label":
            arrival_method_label,

        "must_visit_spots":
            must_visit_names,


    }


    # =====================================================
    # Google Maps用URL
    # =====================================================

    map_query = (
        recommended_hotel.get(
            "map_query",
            ""
        )
    )


    # =====================================================
    # 結果ページ表示
    # =====================================================


    # =====================================================
    # 結果画面用の表示データを最終正規化
    # parking辞書がそのままHTMLへ出るのを完全に防ぐ
    # =====================================================

    recommended_spots = [
        normalize_place_for_display(
            item
        )
        for item in
        (
            recommended_spots
            or []
        )
    ]

    recommended_hotel = (
        normalize_place_for_display(
            recommended_hotel
        )
        if recommended_hotel
        else recommended_hotel
    )

    recommended_restaurants = [
        normalize_place_for_display(
            item
        )
        for item in
        (
            recommended_restaurants
            or []
        )
    ]

    other_hotels = [
        normalize_place_for_display(
            item
        )
        for item in
        (
            other_hotels
            or []
        )
    ]

    if meal_schedule:

        normalized_meals = []

        for meal in meal_schedule:

            meal_copy = dict(
                meal
            )

            if meal_copy.get(
                "restaurant"
            ):

                meal_copy[
                    "restaurant"
                ] = (
                    normalize_place_for_display(
                        meal_copy[
                            "restaurant"
                        ]
                    )
                )

            normalized_meals.append(
                meal_copy
            )

        meal_schedule = (
            normalized_meals
        )


    return render_template(

        "result.html",

        region_code=
            ACTIVE_REGION_CODE,

        region_name=
            ACTIVE_REGION_NAME,

        region_name_en=
            ACTIVE_REGION_NAME_EN,

        age=
            age,

        gender=
            gender,

        people=
            people,

        member=
            member,

        car=
            car,

        purpose=
            purpose,

        budget=
            budget,

        days=
            days,

        travel_date=
            travel_date,

        walking_amount=
            walking_amount,

        travel_pace=
            travel_pace,

        start_point=
            start_point_display,

        travel_mode=
            travel_mode,

        arrival_detail=
            arrival_detail,

        arrival_method_label=
            arrival_method_label,

        must_visit_spots=
            must_visit_names,

        # 旧テンプレート互換用。自宅・任意住所機能は廃止済み。
        custom_start_used=False,
        home_route_option_label=None,
        route_accuracy_notice=None,

        season=
            season,

        day1=
            day1,

        day2=
            day2,

        day3=
            day3,

        hotel=
            recommended_hotel,

        other_hotels=
            other_hotels,

        total_price=
            total_hotel_price,

        trip_style=
            trip_style,

        trip_summary=
            trip_summary,

        sightseeing_time=
            sightseeing_time,

        total_budget=
            total_budget,

        budget_ratio=
            budget_ratio,

        budget_status=
            budget_status,

        feature_text=
            feature_text,

        recommended_spots=
            recommended_spots,

        recommended_restaurants=
            recommended_restaurants,

        meal_schedule=
            meal_schedule,

        s1_optimization=
            (
                {
                    "evaluated_hotel_count":
                        s1_best.get(
                            "evaluated_hotel_count",
                            0
                        ),
                    "travel_minutes":
                        s1_best.get(
                            "travel_minutes"
                        ),
                    "total_value":
                        round(
                            float(
                                s1_best.get(
                                    "total_value",
                                    0
                                )
                            ),
                            1
                        )
                }
                if s1_best
                else None
            ),

        score_summary=
            score_summary,

        map_query=
            map_query,

        history_payload=
            history_payload,

        route_days=
            route_days,

        route_summary=
            route_summary,

        s1_unavailable_must_visit=
            s1_unavailable_must_visit,

        routing_enabled=
            bool(
                route_matrix_routes
            )

    )


print(
    "[KAWAGOE REGION DATA]",
    "spots =", len(KAWAGOE_DATASET.get("spots", [])),
    "| hotels =", len(KAWAGOE_DATASET.get("hotels", [])),
    "| restaurants =", len(KAWAGOE_DATASET.get("restaurants", [])),
    "| route locations =", KAWAGOE_DATASET.get("route_matrix_data", {}).get("location_count"),
    "| route pairs =", KAWAGOE_DATASET.get("route_matrix_data", {}).get("available_pair_count")
)


print(
    "[TOUR DRIVING TIME]",
    "Chichibu = 30 km/h + 2 min",
    "| Kawagoe = 25 km/h + 2 min",
    "| raw OSM time is kept when longer"
)


print(
    "[SPOT SCORE]",
    "Chichibu = 100 points",
    "| Kawagoe = 100 points",
    "| purpose 30 + member 20 + localness 20 + access 10 + itinerary 10 + season 10"
)


# =========================================================
# Flask起動
# =========================================================

if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5001,
        debug=True
    )
