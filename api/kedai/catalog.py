"""Demo shop: Ah Tan Provision Shop, a fictional heartland shop in Toa Payoh.

Each product carries shop-facing names in the four official languages, a short
packaging description that helps Gemini recognise it on a shelf photo, and the
demand profile the seed generator uses. Translations should be reviewed by
native speakers before a real launch.
"""

from dataclasses import dataclass, field

LANGUAGES = ("en", "zh", "ms", "ta")


@dataclass(frozen=True)
class Supplier:
    id: str
    name: str
    lead_time_days: int
    whatsapp: str | None = None
    language: str = "en"


@dataclass(frozen=True)
class Item:
    sku: str
    names: dict[str, str]
    category: str
    unit: str
    price: float
    supplier: str
    demand: float  # typical units sold per day
    cover_days: int  # days of stock on the shelf at seed time
    looks: str  # packaging description for shelf recognition
    season: str | None = None
    case_pack: int = 6
    margin: float = 0.25
    aliases: tuple[str, ...] = field(default_factory=tuple)


SHOP = {
    "name": "Ah Tan Provision Shop",
    "owner": "Uncle Tan",
    "area": "Toa Payoh Lorong 8",
    "currency": "SGD",
    "timezone": "Asia/Singapore",
    "default_language": "zh",
}

SUPPLIERS = (
    Supplier("huat", "Ah Huat Trading", 2, language="zh"),
    Supplier("kampong", "Kampong Fresh Supplies", 1, language="en"),
    Supplier("murugan", "Sri Murugan Wholesale", 3, language="ta"),
    Supplier("lucky", "Lucky Star Sundries", 4, language="zh"),
)


def n(en: str, zh: str, ms: str, ta: str) -> dict[str, str]:
    return {"en": en, "zh": zh, "ms": ms, "ta": ta}


CATALOG: tuple[Item, ...] = (
    # Drinks
    Item(
        "MILO-1KG",
        n("Milo refill pack 1kg", "美禄补充装 1公斤", "Milo pek isi semula 1kg", "மைலோ 1 கி.கி"),
        "Drinks",
        "pack",
        15.90,
        "huat",
        2.0,
        6,
        "green foil refill bag with MILO logo",
        "rain-mild",
        6,
        aliases=("milo",),
    ),
    Item(
        "KOPI-O-500",
        n("Kopi-O powder 500g", "咖啡乌粉 500克", "Serbuk kopi-O 500g", "கோப்பி-ஓ தூள் 500கி"),
        "Drinks",
        "bag",
        6.50,
        "huat",
        2.5,
        20,
        "brown paper coffee bag",
        None,
        10,
    ),
    Item(
        "TEH-3IN1",
        n(
            "Teh tarik 3-in-1 (15 sachets)",
            "拉茶三合一 (15包)",
            "Teh tarik 3-dalam-1 (15 paket)",
            "டே தாரிக் 3-இன்-1 (15)",
        ),
        "Drinks",
        "box",
        5.20,
        "huat",
        2.0,
        18,
        "orange box of tea sachets",
        None,
        12,
    ),
    Item(
        "100PLUS-6",
        n("100PLUS 6 × 325ml", "100号运动饮料 6罐", "100PLUS 6 tin", "100PLUS 6 டின்"),
        "Drinks",
        "6-pack",
        6.80,
        "huat",
        3.0,
        14,
        "blue and white cans in a 6-pack",
        None,
        4,
    ),
    Item(
        "CHRYS-6",
        n("Chrysanthemum tea 6 × 300ml", "菊花茶 6盒", "Teh bunga kekwa 6 kotak", "கிரிசாந்திமம் தேநீர் 6"),
        "Drinks",
        "6-pack",
        5.40,
        "huat",
        2.2,
        16,
        "yellow drink cartons, 6-pack",
        None,
        4,
    ),
    # Staples
    Item(
        "RICE-5KG",
        n("Thai jasmine rice 5kg", "泰国香米 5公斤", "Beras wangi Thai 5kg", "தாய் மல்லிகை அரிசி 5 கி.கி"),
        "Staples",
        "bag",
        13.50,
        "huat",
        1.6,
        15,
        "white woven rice bag with green print",
        None,
        4,
    ),
    Item(
        "NOODLE-CURRY",
        n("Curry instant noodles 5-pack", "咖喱快熟面 5包装", "Mi segera kari 5 paket", "கறி உடனடி நூடுல்ஸ் 5"),
        "Staples",
        "pack",
        4.60,
        "huat",
        3.5,
        10,
        "yellow multipack of noodle packets",
        "rain-mild",
        10,
    ),
    Item(
        "NOODLE-GORENG",
        n("Mi goreng instant noodles 5-pack", "印尼炒面 5包装", "Mi goreng segera 5 paket", "மீ கோரெங் 5"),
        "Staples",
        "pack",
        3.90,
        "huat",
        3.0,
        12,
        "white and red multipack of noodle packets",
        "rain-mild",
        10,
    ),
    Item(
        "OIL-2L",
        n("Cooking oil 2L", "食用油 2公升", "Minyak masak 2L", "சமையல் எண்ணெய் 2லி"),
        "Staples",
        "bottle",
        7.20,
        "huat",
        1.4,
        16,
        "clear plastic bottle of yellow oil",
        "deepavali-mild",
        6,
    ),
    Item(
        "SUGAR-2KG",
        n("White sugar 2kg", "白糖 2公斤", "Gula pasir 2kg", "வெள்ளை சர்க்கரை 2 கி.கி"),
        "Staples",
        "bag",
        3.80,
        "huat",
        1.6,
        14,
        "clear plastic bag of white sugar",
        "deepavali-mild",
        10,
    ),
    Item(
        "CONDENSED",
        n("Sweetened condensed milk 390g", "炼奶 390克", "Susu pekat manis 390g", "இனிப்பு கண்டென்ஸ்டு பால் 390கி"),
        "Staples",
        "can",
        2.30,
        "huat",
        2.4,
        12,
        "small can with blue and white label",
        "deepavali-mild",
        12,
    ),
    Item(
        "EVAP",
        n("Evaporated milk 390g", "淡奶 390克", "Susu cair 390g", "ஆவியாக்கிய பால் 390கி"),
        "Staples",
        "can",
        2.10,
        "huat",
        2.0,
        18,
        "small can with red label",
        None,
        12,
    ),
    Item(
        "KAYA",
        n("Kaya spread 400g", "咖椰 400克", "Seri kaya 400g", "கயா 400கி"),
        "Staples",
        "jar",
        4.20,
        "huat",
        0.9,
        22,
        "glass jar of brown-green kaya",
        None,
        6,
    ),
    Item(
        "COCONUT-MILK",
        n("Coconut milk 400ml", "椰浆 400毫升", "Santan 400ml", "தேங்காய்ப் பால் 400மி.லி"),
        "Staples",
        "can",
        2.20,
        "murugan",
        2.0,
        10,
        "can with green coconut label",
        "deepavali",
        12,
    ),
    # Fresh
    Item(
        "EGGS-30",
        n("Fresh eggs (tray of 30)", "鸡蛋 (30粒)", "Telur segar (30 biji)", "முட்டை (30)"),
        "Fresh",
        "tray",
        8.90,
        "kampong",
        4.0,
        3,
        "pulp egg tray",
        None,
        5,
        0.18,
    ),
    Item(
        "BREAD-WHITE",
        n("White bread 600g", "白面包 600克", "Roti putih 600g", "வெள்ளை ரொட்டி 600கி"),
        "Fresh",
        "loaf",
        2.95,
        "kampong",
        6.0,
        2,
        "sliced loaf in a printed plastic bag",
        None,
        10,
        0.2,
    ),
    # Snacks
    Item(
        "BISCUIT-TIN",
        n(
            "Assorted biscuits tin 600g",
            "什锦饼干罐 600克",
            "Biskut campur tin 600g",
            "கலப்பு பிஸ்கட் டின் 600கி",
        ),
        "Snacks",
        "tin",
        9.90,
        "huat",
        0.8,
        25,
        "round red biscuit tin",
        "deepavali-mild",
        6,
    ),
    Item(
        "CHIPS",
        n("Potato chips 160g", "薯片 160克", "Kerepek kentang 160g", "உருளைக்கிழங்கு சிப்ஸ் 160கி"),
        "Snacks",
        "bag",
        3.20,
        "huat",
        2.5,
        15,
        "foil snack bag",
        None,
        12,
    ),
    Item(
        "MURUKKU",
        n("Murukku 200g", "姆鲁古脆饼 200克", "Murukku 200g", "முறுக்கு 200கி"),
        "Snacks",
        "pack",
        3.50,
        "murugan",
        1.2,
        9,
        "clear pack of spiral murukku",
        "deepavali",
        12,
    ),
    # Indian groceries (Deepavali, 8 Nov 2026)
    Item(
        "GHEE-800",
        n("Pure ghee 800g", "酥油 800克", "Minyak sapi (ghee) 800g", "நெய் 800கி"),
        "Indian groceries",
        "tin",
        16.90,
        "murugan",
        0.9,
        6,
        "gold tin of ghee",
        "deepavali",
        6,
    ),
    Item(
        "ATTA-5KG",
        n("Chakki atta flour 5kg", "全麦面粉 5公斤", "Tepung atta 5kg", "ஆட்டா மாவு 5 கி.கி"),
        "Indian groceries",
        "bag",
        11.50,
        "murugan",
        0.8,
        6,
        "large printed flour bag",
        "deepavali",
        4,
    ),
    Item(
        "RICEFLOUR-1KG",
        n("Rice flour 1kg", "米粉 1公斤", "Tepung beras 1kg", "அரிசி மாவு 1 கி.கி"),
        "Indian groceries",
        "bag",
        2.40,
        "murugan",
        1.0,
        7,
        "small white flour packet",
        "deepavali",
        10,
    ),
    Item(
        "BASMATI-5KG",
        n("Basmati rice 5kg", "印度香米 5公斤", "Beras basmati 5kg", "பாஸ்மதி அரிசி 5 கி.கி"),
        "Indian groceries",
        "bag",
        18.90,
        "murugan",
        0.6,
        12,
        "red and gold rice bag",
        "deepavali",
        4,
    ),
    Item(
        "LAMP-WICKS",
        n("Oil lamp wicks (100)", "油灯灯芯 (100条)", "Sumbu pelita (100)", "விளக்குத் திரி (100)"),
        "Indian groceries",
        "pack",
        2.00,
        "murugan",
        0.5,
        10,
        "small pack of cotton wicks",
        "deepavali",
        20,
    ),
    # Household
    Item(
        "UMBRELLA",
        n("Compact umbrella", "折叠雨伞", "Payung lipat", "மடக்கு குடை"),
        "Household",
        "piece",
        9.90,
        "lucky",
        0.8,
        5,
        "folded umbrellas in sleeves",
        "rain",
        6,
        0.4,
    ),
    Item(
        "PONCHO",
        n("Raincoat poncho", "雨衣", "Baju hujan ponco", "மழைக்கோட்டு"),
        "Household",
        "piece",
        4.90,
        "lucky",
        0.7,
        6,
        "folded plastic poncho in a pouch",
        "rain",
        10,
        0.45,
    ),
    Item(
        "MOSQ-COIL",
        n("Mosquito coils (10)", "蚊香 (10片)", "Ubat nyamuk lingkar (10)", "கொசுவர்த்தி (10)"),
        "Household",
        "box",
        3.60,
        "lucky",
        1.2,
        9,
        "green box of mosquito coils",
        "rain",
        12,
    ),
    Item(
        "CANDLE",
        n("Candles (6)", "蜡烛 (6支)", "Lilin (6 batang)", "மெழுகுவர்த்தி (6)"),
        "Household",
        "pack",
        2.50,
        "lucky",
        0.4,
        20,
        "pack of white candles",
        "rain-mild",
        12,
    ),
    Item(
        "DETERGENT-3KG",
        n("Laundry detergent 3kg", "洗衣粉 3公斤", "Serbuk pencuci 3kg", "சலவைத் தூள் 3 கி.கி"),
        "Household",
        "box",
        12.90,
        "lucky",
        0.7,
        25,
        "large detergent box",
        None,
        4,
    ),
    Item(
        "TISSUE-10",
        n("Toilet tissue 10 rolls", "卫生纸 10卷", "Tisu tandas 10 gulung", "டிஷ்யூ 10 ரோல்"),
        "Household",
        "pack",
        7.50,
        "lucky",
        1.5,
        20,
        "plastic-wrapped pack of 10 rolls",
        None,
        6,
    ),
    Item(
        "DISHSOAP",
        n(
            "Dishwashing liquid 900ml",
            "洗洁精 900毫升",
            "Sabun pinggan 900ml",
            "பாத்திரம் கழுவும் திரவம் 900மி.லி",
        ),
        "Household",
        "bottle",
        3.40,
        "lucky",
        1.0,
        22,
        "green squeeze bottle",
        None,
        12,
    ),
    Item(
        "BATTERY-AA",
        n("AA batteries 4-pack", "5号电池 4粒", "Bateri AA 4 biji", "AA பேட்டரி 4"),
        "Household",
        "pack",
        4.80,
        "lucky",
        0.6,
        30,
        "blister pack of AA batteries",
        None,
        12,
    ),
)

# Regular customers the shopkeeper knows by name: (id, name, usual SKUs, typical days between visits).
REGULARS = (
    ("lim", "Mdm Lim", ("BREAD-WHITE", "KOPI-O-500", "EGGS-30"), 2),
    ("rajan", "Mr Rajan", ("GHEE-800", "ATTA-5KG", "COCONUT-MILK"), 7),
    ("siti", "Cik Siti", ("RICE-5KG", "COCONUT-MILK", "NOODLE-GORENG"), 5),
    ("ah-seng", "Ah Seng", ("100PLUS-6", "CHIPS", "NOODLE-CURRY"), 3),
    ("devi", "Mrs Devi", ("MURUKKU", "SUGAR-2KG", "CONDENSED"), 6),
    ("wong", "Mr Wong", ("TEH-3IN1", "BREAD-WHITE", "KAYA"), 2),
    ("farah", "Farah", ("EGGS-30", "OIL-2L", "DISHSOAP"), 7),
    ("ravi-uncle", "Ravi uncle", ("KOPI-O-500", "CONDENSED", "BISCUIT-TIN"), 4),
)
# Days since the last visit at seed time; Mdm Lim and Mr Rajan have gone quiet.
REGULAR_LAST_SEEN = {
    "lim": 19,
    "rajan": 24,
    "siti": 3,
    "ah-seng": 1,
    "devi": 4,
    "wong": 0,
    "farah": 5,
    "ravi-uncle": 2,
}

# Perishables are never ordered beyond what sells before it spoils.
SHELF_LIFE_DAYS = {"BREAD-WHITE": 3, "EGGS-30": 10}

BY_SKU = {item.sku: item for item in CATALOG}
SUPPLIERS_BY_ID = {supplier.id: supplier for supplier in SUPPLIERS}
