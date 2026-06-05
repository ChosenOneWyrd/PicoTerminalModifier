#!/usr/bin/env python3
"""
make_digimon_analyzer_v27.py

Run:
    python make_digimon_analyzer_v27.py "Imperialdramon Paladin Mode" --template Digimon_analyzer_blank.jpg --debug
    # For taking profile data from sd/profile folder instead of Wikimon, use:
    python make_digimon_analyzer_v27.py "Imperialdramon Paladin Mode" --template Digimon_analyzer_blank.jpg --debug --data-source terminal
    To try all at once: python make_digimon_analyzer_v27.py --all-digi-api --debug
    or:                 python make_digimon_analyzer_v27.py --all-profile-bin --debug
"""

from __future__ import annotations
import argparse
import io
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from urllib.parse import quote, unquote, urljoin
import requests
from bs4 import BeautifulSoup, Tag
from PIL import Image, ImageDraw, ImageFont
import traceback
import contextlib

WIKIMON_BASE = "https://wikimon.net/"
WIKIMON_API = "https://wikimon.net/api.php"
PROFILE_ROOT = Path("sd/profile")

CENTER_NAME_FONT_SIZE = 30
CENTER_NAME_Y_OFFSET = -1
RIGHT_NAME_START_FONT_SIZE = 17
INFO_FONT_SIZE = 16
SPECIAL_TITLE_FONT_SIZE = 15
SPECIAL_MOVE_NAME_FONT_SIZE = 20

ANIME_IMAGE_KEYWORD_RULES = [
    ("contains", "Imperialdramon_positron_laser"),
    ("contains", "Yukidarumona"),
    ("contains", "DA-41_Angemon"),
    ("contains", "M03_Rapidmon_armor"),
    ("contains", "400px-Darktyranomon"),
    ("contains", "M03_Cherubimon_vice"),
    ("contains", "Diablomon_OWG"),
    ("contains", "Agumonx2"),
    ("contains", "Taichi_Yagami_with_Agumon_-Yuki_no_Kizuna"),
    ("contains", "M09_Algomon_perfect"),
    ("contains", "400px-Ancientbeatmon"),
    ("contains", "Ancientmegatheriumon_collectors"),
    ("contains", "ZT24_Stingmon"),
    ("contains", "TigerVespamon_ReArise"),
    ("contains", "Dracomon_XW31"),
    ("contains", "GG62_Clavisangemon"),
    ("contains", "DA2020_God_Fist1"),
    ("contains", "Ukkomon2"),
    ("contains", "Ulforce_V-dramon_DMO_3"),
    ("contains", "DORUguremon_XE"),
    ("contains", "Omegamon_M04"),
    ("contains", "DA20_Metalgreymon"),
    ("contains", "TRI02_Vikemon"),
    ("contains", "Meikuumon_tri2."),
    ("contains", "XW45_Apollomon"),
    ("contains", "DF13_Arbormon"),
    ("contains", "Barbamon7"),
    ("contains", "M07_Bearmon"),
    ("contains", "Beelstarmon_new_century"),
    ("contains", "Blitzmon_2"),
    ("contains", "M05_Bluemeramon"),
    ("contains", "Bokomon_DF"),
    ("contains", "Bulkmon_Digimon_Project_2021"),
    ("contains", "Bulcomon_encounters2"),
    ("contains", "DF15_cap"),
    ("contains", "Choromon_Tamers"),
    ("contains", "Clockmon_analyzer_Ghost_Game"),
    ("contains", "XW27_Coronamon_3"),
    ("contains", "Cryspaledramon_encounters"),
    ("contains", "Cyberdramon_2010_2"),
    ("contains", "XW73_Dagomon"),
    ("contains", "Death-X-DORUgoramon_XE"),
    ("contains", "DT50_cap"),
    ("contains", "Dukemon_DS41"),
    ("contains", "Eldoradimon_Adv2020"),
    ("contains", "Adv02"),
    ("contains", "ZT"),
    ("regex", r"EP\d+"),
    ("regex", r"ep\d+"),
    ("regex", r"DA\d+"),
    ("contains", "_DA"),
    ("contains", "-DA"),
    ("regex", r"DT\d+"),
    ("contains", "_DT"),
    ("contains", "-DT"),
    ("contains", "Adventure"),
    ("contains", "adventure"),
    ("contains", "tamers"),
    ("contains", "Tamers"),
    ("contains", "M03_Cherubimon_vice"),
    ("contains", "Unimon3"),
    ("contains", "DAtri5_Alphamon_ouryuken_jesmon"),
    ("contains", "Agumon_and_Masaru"),
    ("contains", "DF42_Agnimon2"),
    ("regex", r"DS\d+"),
    ("contains", "_DS"),
    ("contains", "-DS"),
    ("contains", "savers"),
    ("contains", "XW"),
    ("contains", "anime"),
    ("regex", r"XW\d+"),
    ("regex", r"DB\d+"),
    ("regex", r"(?<!DA)tri"),
    ("regex", r"(?<!DA)TRI"),
    ("contains", "Ghost_Game"),
    ("contains", "ghost_game"),
    ("contains", "Close-up"),
    ("contains", "Miyako_and_Poromon"),
    ("contains", "YoleiandHawkmon"),
    ("contains", "Iori_and_Upamon"),
    ("contains", "M03_Andiramon"),
    ("contains", "GG"),
    ("contains", "DF"),
    ("contains", "movie"),
    ("contains", "Movie"),
    ("contains", "OWG"),
    ("regex", r"M0?1"),
    ("regex", r"M0?2"),
    ("regex", r"M0?3"),
    ("regex", r"M0?4"),
    ("regex", r"M0?5"),
    ("regex", r"M0?6"),
    ("regex", r"M0?7"),
    ("regex", r"M0?8"),
    ("regex", r"M0?9"),
    ("contains", "Kizuna"),
    ("contains", "SS8"),
    ("contains", "Top_Gun"),
    ("contains", "DHTSETGD"),
    ("contains", "Tortomon2"),
    ("contains", "Survive"),
    ("contains", "survive"),
    ("contains", "Encounter"),
    ("contains", "new_century"),
    ("contains", "crusader"),
    ("contains", "px-Rukamon"),
    ("contains", "Flarelizarmon")
]

# Images whose filenames/titles contain these words are completely ignored.
# They are skipped before API imageinfo resolving and before downloading.
SKIP_IMAGE_KEYWORDS = {"card", "DM0", "battle", "PSP", "psp", "shikishi", "fantasy", "Examon_2", 
                       "Spr", "jintrix", "DSAM", "DSR", "XWM", "XW03_Lilithmon", 
                       "reference", "ZT01_cap", "art_board", "tamers_bluray", 
                       "tamers_plushes", "Tamers25thanniversary", "early_concept", "DA2020_Drimogemon",
                       "XW58_Xros_Loader_Collection", "DA-47_Gaossmon_tyranomon", "illustration", "Model_Adventure",
                       "Stats", "600px-XW15_Heaven_Zone_Digimon", "American_Chosen_Children", "digimonweb", "poster",
                       "_head", "EP78_Imperialdramon", "M03_Rapidmon_armor_magnamon", "ZT09_Airdramon", "lineart",
                       "Darktyranomon_new_century", "Bo-79", "Hangyomon_DSTS", "Dcg-BT1-019", "Dcg-EX", "St-181", "St-338", 
                       "St-502", "darktyranomon_kamemon", "On_drb", "ZT28_Archnemon", "Dcg-BT", "Rikollection", "promotion", "Promotion",
                       "DA-01_Algomon_baby1", "Bx-41", "Sx-54", "_ex12", "St-0", "St-1", "St-2", "St-3", "St-4", "St-5", "St-6", 
                       "St-7", "St-8", "St-9", "collectors", "DF13_Ancientwisemon", "Bo-", "illustcon", "Digimon_Get_Back_", 
                       "DA-05_Clavisangemon_slashangemon_rasielmon", "Dcg-ST", "visual", "_art", "Digimon_Ghost_Game_ED2", "GG_end",
                       "Bx-6", "Da-4", "Da-0", "XW42_Anubimon_gravimon", "Ariemon_Tips", "SXW_Armamon", "DA-58_Baluchimon", "Ballistamon_DFF", "Virusbusters_pendulumz",
                       "Dcg-RB", "Pulsemon_bulkmon_boutmon", "V-Tamer", "Cannondramon_crusader", "Cargodramon_seekers_trailer", "Seekers_1-15_Cargodramon",
                       "Bx-139", "Digimon_Seekers_Nightmare_2_-_Slaughter_Blade", "Bx-3", "promoart", "Barbamon_X_and_DarkKnightmon_X_Chronicle_X",
                       "Vortex-Spear", "Bx-", "Da-347", "Da-542", "Sx-", "Dcg-", "Bo-3", "DCG_D", "Enmamon_Shambala"}

# -----------------------------
# GENERATED ANALYZER CACHE
# -----------------------------
GENERATED_IMAGES_DIR = Path("generated_images")

# Put names here when you want to force regeneration.
# Matching ignores spaces, hyphens, underscores, parentheses, etc.
REGENERATE = []

# 640x480 uploaded blank template coordinates.
CENTER_NAME_BOX = (204, 85, 436, 108)
RIGHT_NAME_BOX  = (372, 130, 604, 173)
INFO_BOX        = (371, 184, 605, 285)
MOVES_BOX       = (370, 293, 605, 446)

# White Digimon picture area. Slightly inset so it does not cover the brown border.
DIGIMON_IMAGE_BOX = (28, 132, 354, 376)

# -----------------------------
# HARD-CODED SETTINGS
# -----------------------------
AUTO_ADD_DIGIMON_IMAGE = True
SAVE_DOWNLOADED_DIGIMON_IMAGE = False

# If True, image priority is:
#   1) Anime/screenshot/game images with filename keywords in ANIME_IMAGE_KEYWORD_RULES order
#   2) TCG/game/scenery-like images with multicolor backgrounds
#   3) Reference images with white/transparent/single-color backgrounds
PREFER_SCENE_IMAGE_OVER_REFERENCE = True
MAX_IMAGE_CANDIDATES_TO_TEST = 10

# Avoid downloading the same selected/tested image twice.
_IMAGE_CACHE: Dict[str, Image.Image] = {}

# Tall portrait anime screenshots often crop badly if centered vertically.
# Example: a full-body vertical screenshot may show only the waist/legs.
# If the source image height/width is above this threshold, crop from the top.
TALL_IMAGE_TOP_CROP = True
TALL_IMAGE_HEIGHT_WIDTH_THRESHOLD = 1.45
# 0.00 = top aligned, 0.50 = center, 1.00 = bottom.
# For tall screenshots, top aligned usually preserves the face/upper body.
TALL_IMAGE_VERTICAL_CROP_ANCHOR = 0.00

TEXT_BLACK = (0, 0, 0)
TEXT_WHITE = (255, 255, 255)

HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 DigimonAnalyzerScript/27.0"}
REQUEST_TIMEOUT = 180
IMAGE_DOWNLOAD_TIMEOUT = 180

STOP_MOVE_WORDS = {
    "profile", "evolution", "evolves", "evolves from", "evolves to", "appearances",
    "anime", "manga", "video games", "virtual pets", "tcg", "card game",
    "notes and references", "design", "name used", "attack techniques",
    "official romanization", "dub", "contents", "digimon reference book", "reference book",
    "kanji/kana", "romanization", "translation", "description", "name", "image",
    "english", "japanese", "references", "notes", "digimon profile", "special move",
    "special moves", "skill", "skills", "field", "fields", "attribute", "type", "level",
    "redirected", "redirected from", "from wikimon", "atho", "rené", "rene", "por",
}

SECTION_STOP_WORDS = {
    "evolution", "evolves from", "evolves to", "appearances", "anime", "manga", "video games",
    "virtual pets", "tcg", "card game", "notes and references", "references", "design",
    "name etymology", "subspecies/variations", "other forms", "profile", "contents",
}

# Some Wikimon pages list helper names or multiple attack rows before the move users expect
# for the Digimon Analyzer display. These preferences are ONLY used if the exact move
# is found on that Digimon's Wikimon page/Attack Techniques table.
PREFERRED_WIKIMON_MOVE_BY_PAGE = {
    "jesmon": "Schwertgeist",
}

BAD_IMAGE_WORDS = {
    "emblem", "flag", "icon", "digimoji", "test", "wiki", "wikimon", "banner",
    "logo", "symbol", "button", "edit", "external", "language", "chinese", "english",
    "japanese", "korean", "contents", "title",
}

ANALYZER_TRACE_LOG_PATH = Path("analyzer_trace.log")
ANALYZER_ERROR_LOG_PATH = Path("analyzer_error.log")
class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for stream in self.streams:
            stream.write(data)
            stream.flush()

    def flush(self):
        for stream in self.streams:
            stream.flush()


def log_analyzer_error(message="", exc=None):
    with open(ANALYZER_ERROR_LOG_PATH, "a", encoding="utf-8") as f:
        if message:
            f.write(message + "\n")

        if exc is not None:
            traceback.print_exception(type(exc), exc, exc.__traceback__, file=f)

        f.write("\n")

def clean_text(s: object) -> str:
    s = re.sub(r"\[[^\]]*\]", "", str(s))
    s = s.replace("\xa0", " ")
    s = s.replace("\u200b", "")
    s = s.replace("\ufeff", "")
    s = re.sub(r"\s+", " ", s)
    return s.strip(" \t\r\n:;|•*")


def display_name(name: str) -> str:
    return clean_text(name).upper()

def normalize_lookup_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", clean_text(name).lower())

def analyzer_cache_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", clean_text(name).lower())


def analyzer_cache_path(name: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", clean_text(name))
    return GENERATED_IMAGES_DIR / f"{safe}_analyzer.jpg"

def should_regenerate(name: str) -> bool:
    key = analyzer_cache_key(name)
    regen_keys = {analyzer_cache_key(x) for x in REGENERATE}
    return key in regen_keys

def terminal_profile_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", clean_text(name).lower())


def find_terminal_profile_bin(name: str, profile_root: Path) -> Path:
    key = terminal_profile_key(name)

    for path in profile_root.rglob("*.bin"):
        if path.name.startswith("._"):
            continue

        stem_key = terminal_profile_key(path.stem)
        if stem_key == key:
            return path

    raise RuntimeError(f"Could not find terminal profile bin for {name!r} in {profile_root}")

def list_profile_bins(profile_root: Path) -> List[Path]:
    if not profile_root.exists():
        raise RuntimeError(f"Profile root does not exist: {profile_root}")

    bins = []
    for path in profile_root.rglob("*.bin"):
        if path.name.startswith("._"):
            continue
        bins.append(path)

    return sorted(bins, key=lambda p: str(p).lower())

def ocr_profile_page(img: Image.Image) -> str:
    try:
        import pytesseract
    except ImportError:
        raise RuntimeError(
            "pytesseract is required for --data-source terminal.\n"
            "Install with:\n"
            "  pip install pytesseract\n"
            "  brew install tesseract"
        )

    img = img.convert("L")
    img = img.resize((img.width * 4, img.height * 4), Image.Resampling.NEAREST)

    # black/white cleanup
    img = img.point(lambda p: 255 if p > 128 else 0)

    return pytesseract.image_to_string(img, config="--psm 6")


def clean_terminal_value(value: str) -> str:
    value = clean_text(value)

    # Remove OCR junk/icons often read after labels.
    value = re.sub(r"^[^\w]+", "", value)
    value = re.sub(r"^[Cc\*\-•]+\s+", "", value)

    return value.strip()


def is_profile_header_ocr(line: str) -> bool:
    key = re.sub(r"[^a-z]", "", line.lower())
    return key in {
        "profile",
        "protfile",
        "protile",
        "profle",
        "proflle",
        "profiie",
    }


def read_terminal_profile_data(digimon_name: str, profile_root: Path, debug: bool = False) -> Dict[str, str]:
    bin_path = find_terminal_profile_bin(digimon_name, profile_root)
    data = bin_path.read_bytes()

    if data[:2] != b"BM":
        raise RuntimeError(f"{bin_path} does not start with BMP magic.")

    page_size = int.from_bytes(data[2:6], "little")
    english_page_index = 2

    start = english_page_index * page_size
    end = start + page_size

    img = Image.open(io.BytesIO(data[start:end])).convert("RGB")
    text = ocr_profile_page(img)

    if debug:
        print(f"Terminal profile bin: {bin_path}")
        print("OCR text:")
        print(text)

    lines = [x.strip() for x in text.splitlines() if x.strip()]

    level = "Unknown"
    dtype = "Unknown"
    attribute = "Unknown"
    skills = []

    collecting_skills = False

    for line in lines:
        raw = line.strip()
        low = raw.lower()

        if is_profile_header_ocr(raw):
            collecting_skills = False
            continue

        if low.startswith("level"):
            value = re.sub(r"^level\s*:?", "", raw, flags=re.I)
            level = clean_terminal_value(value)
            collecting_skills = False
            continue

        if low.startswith("type"):
            value = re.sub(r"^type\s*:?", "", raw, flags=re.I)
            dtype = clean_terminal_value(value)
            collecting_skills = False
            continue

        if low.startswith(("attri", "attribute")):
            value = re.sub(r"^(attri|attribute)\s*:?", "", raw, flags=re.I)
            attribute = clean_terminal_value(value)
            collecting_skills = False
            continue

        if low.startswith("skill"):
            value = re.sub(r"^skill\s*:?", "", raw, flags=re.I)
            first_skill = clean_terminal_value(value)

            if first_skill and not is_profile_header_ocr(first_skill):
                skills.append(first_skill)

            collecting_skills = True
            continue

        if collecting_skills:
            skill_line = clean_terminal_value(raw)

            if not skill_line:
                continue

            if is_profile_header_ocr(skill_line):
                collecting_skills = False
                continue

            if skill_line.lower().startswith(("level", "type", "attri", "attribute")):
                collecting_skills = False
                continue

            skills.append(skill_line)

            # Terminal profile has max 2 skills.
            if len(skills) >= 2:
                collecting_skills = False

    skills = skills[:2]
    special_move = "\n\n".join(skills) if skills else "Unknown"

    return {
        "level": level,
        "type": dtype,
        "attribute": attribute,
        "special_move": special_move,
        "source": str(bin_path),
    }

def wikimon_title_candidates(name: str) -> List[str]:
    raw = clean_text(name)
    candidates: List[str] = []

    def add(title: str):
        title = clean_text(title).replace(" ", "_")
        if title and title not in candidates:
            candidates.append(title)

    add(raw)

    mode_suffixes = [
        "Paladin Mode", "Fighter Mode", "Dragon Mode", "Burst Mode", "Falldown Mode",
        "Crimson Mode", "Blast Mode", "Ruin Mode", "Superior Mode", "X-Antibody",
        "Ouryuken", "Ouryuuken", "Merciful Mode", "Alter-S", "Alter-B",
    ]
    for suffix in mode_suffixes:
        if raw.lower().endswith(suffix.lower()):
            base = raw[: -len(suffix)].strip()
            if base:
                add(f"{base}: {suffix}")

    parenthetical_suffixes = [
        "Blue", "Green", "Red", "Black", "White", "Orange", "Yellow", "Purple",
        "Silver", "Gold", "Brown", "X-Antibody", "2006 Anime Version",
    ]
    for suffix in parenthetical_suffixes:
        if raw.lower().endswith((" " + suffix).lower()):
            base = raw[: -(len(suffix) + 1)].strip()
            if base:
                add(f"{base} ({suffix})")

    add(raw.replace(": ", ":_"))
    return candidates


def get_soup_for_name(name: str) -> Tuple[BeautifulSoup, str]:
    errors: List[str] = []

    for title in wikimon_title_candidates(name):
        url = WIKIMON_BASE + quote(title.replace(" ", "_"), safe="_():-")
        try:
            r = requests.get(url, headers=HTTP_HEADERS, timeout=REQUEST_TIMEOUT)
            if r.status_code == 200 and "There is currently no text in this page" not in r.text:
                soup = BeautifulSoup(r.text, "html.parser")
                h1 = soup.find("h1")
                page_title = clean_text(h1.get_text(" ")) if h1 else ""
                if page_title and "not found" not in page_title.lower():
                    return soup, r.url
            errors.append(f"{url}: HTTP {r.status_code}")
        except Exception as e:
            errors.append(f"{url}: {e}")

    try:
        params = {"action": "opensearch", "search": name, "limit": 8, "namespace": 0, "format": "json"}
        r = requests.get(WIKIMON_API, params=params, headers=HTTP_HEADERS, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        results = r.json()
        titles = results[1] if len(results) > 1 else []
        for title in titles:
            url = WIKIMON_BASE + quote(title.replace(" ", "_"), safe="_():-")
            rr = requests.get(url, headers=HTTP_HEADERS, timeout=REQUEST_TIMEOUT)
            if rr.status_code == 200:
                return BeautifulSoup(rr.text, "html.parser"), rr.url
    except Exception as e:
        errors.append(f"opensearch failed: {e}")

    raise RuntimeError("Could not find a Wikimon page for this Digimon.\nTried:\n" + "\n".join(errors))


def strip_wikimon_noise(soup: BeautifulSoup) -> BeautifulSoup:
    soup = BeautifulSoup(str(soup), "html.parser")
    for bad in soup(["script", "style", "noscript"]):
        bad.decompose()
    for selector in [
        "#contentSub", ".redirectMsg", ".mw-redirectedfrom", ".printfooter",
        "#catlinks", "#toc", ".toc", ".mw-editsection", ".navbox",
        ".metadata", ".ambox", ".noprint",
    ]:
        for tag in soup.select(selector):
            tag.decompose()
    return soup


def soup_lines(soup: BeautifulSoup) -> List[str]:
    soup = strip_wikimon_noise(soup)
    lines = [clean_text(x) for x in soup.get_text("\n").splitlines()]
    cleaned = []
    for x in lines:
        if not x:
            continue
        low = x.lower()
        if low.startswith("redirected from") or low == "from wikimon":
            continue
        cleaned.append(x)
    return cleaned


def norm_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def wanted_page_name_variants(page_title: str, user_name: str) -> List[str]:
    vals = [page_title, user_name]
    vals += [v.replace(":", "") for v in vals]
    vals += [v.replace("(", "").replace(")", "") for v in vals]
    out: List[str] = []
    for v in vals:
        v = display_name(v)
        if v and v not in out:
            out.append(v)
    return out


def first_profile_block(lines: List[str], page_title: str, user_name: str) -> List[str]:
    names = wanted_page_name_variants(page_title, user_name)
    name_norms = {norm_key(n) for n in names}

    start = None
    for i, line in enumerate(lines):
        if norm_key(line) in name_norms:
            nearby = "\n".join(lines[i:i + 14]).lower()
            if "level" in nearby and "type" in nearby and "attribute" in nearby:
                start = i
                break

    if start is None:
        for i, line in enumerate(lines[:300]):
            nearby = "\n".join(lines[i:i + 14]).lower()
            if line.lower() == "level" and "type" in nearby and "attribute" in nearby:
                start = max(0, i - 2)
                break

    if start is None:
        return lines[:300]

    end = min(len(lines), start + 80)
    stop_words = {"subspecies/variations", "contents", "attack techniques", "evolution", "appearances", "name etymology"}
    for j in range(start + 1, min(len(lines), start + 100)):
        if lines[j].lower() in stop_words or lines[j].startswith("## Contents"):
            end = j
            break

    return lines[start:end]


def read_value_after_label(block: List[str], label: str) -> str:
    lab = label.lower()
    for i, line in enumerate(block):
        low = line.lower()
        if low.startswith(lab + " "):
            val = clean_text(line[len(label):])
            if val:
                return val
        if low == lab:
            for nxt in block[i + 1:i + 8]:
                nlow = nxt.lower()
                if nlow in {"level", "type", "attribute", "field", "fields"}:
                    continue
                if "image:" in nlow or nlow.endswith("emblem.png"):
                    continue
                if nxt:
                    return clean_text(nxt)
        m = re.match(rf"^{re.escape(label)}\s+(.+)$", line, flags=re.I)
        if m:
            return clean_text(m.group(1))
    return "Unknown"


def extract_profile_info(soup: BeautifulSoup, page_title: str, user_name: str) -> Dict[str, str]:
    lines = soup_lines(soup)
    block = first_profile_block(lines, page_title, user_name)
    return {
        "level": read_value_after_label(block, "Level"),
        "type": read_value_after_label(block, "Type"),
        "attribute": read_value_after_label(block, "Attribute"),
    }


def is_probably_move_name(cand: str) -> bool:
    cand = clean_text(cand)
    low = cand.lower()

    if not cand or low in STOP_MOVE_WORDS:
        return False
    if len(cand) < 2 or len(cand) > 55:
        return False
    if cand in {".", ")", "(", "-", "—", "–"}:
        return False

    # Reject description fragments like:
    # "blue", "stabbing the opponent...", "firing super-massive..."
    if cand[0].islower():
        return False
    if re.search(r"\b(stabbing|firing|shooting|launching|charging|striking|attacking|opponent|enemy|foe|with|from|into|using)\b", low):
        return False

    if low.startswith(("digimon reference", "reference book", "level", "type", "attribute", "field", "redirected from")):
        return False
    if re.search(r"\b(profile|evolves|appears|anime|manga|virtual pet|card game|damage|power|target|critical|increased|redirected)\b", low):
        return False
    if any(ch.isdigit() for ch in cand) and not re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]", cand):
        return False
    if len(cand.split()) > 6:
        return False

    return bool(re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]", cand))


def clean_move_candidate(raw: str) -> str:
    raw = clean_text(raw)
    raw = re.sub(r"\[[^\]]*\]", "", raw)
    raw = raw.strip("()[]{}.,; ")

    raw = re.sub(r"^Redirected from .*$", "", raw, flags=re.I)

    # If table cell has "Move Name Description...", keep only bold/italic name earlier if possible.
    raw = re.split(r"\s{2,}|[:：]", raw, maxsplit=1)[0]
    raw = raw.strip("()[]{}.,; ")
    return clean_text(raw)

def extract_css_selector_special_move(soup: BeautifulSoup) -> str:
    """
    Direct Wikimon table selector fallback requested by user.
    This is brittle, but useful for old Wikimon layout pages.
    """
    selectors = [
        "table:nth-child(6) > tbody > tr:nth-child(2) > td:nth-child(1) > i > b",
        "table:nth-child(6) > tr:nth-child(2) > td:nth-child(1) > i > b",
    ]

    for sel in selectors:
        tag = soup.select_one(sel)
        if tag:
            cand = clean_move_candidate(tag.get_text(" "))
            if is_probably_move_name(cand):
                return cand

    return ""




def extract_parenthesized_moves(text: str) -> List[str]:
    moves: List[str] = []
    for cand in re.findall(r"\(([A-Za-zÀ-ÖØ-öø-ÿ0-9][A-Za-zÀ-ÖØ-öø-ÿ0-9 '\-:]+?)\)", text):
        cand = clean_move_candidate(cand)
        if is_probably_move_name(cand) and cand not in moves:
            moves.append(cand)
    return moves


def extract_quoted_moves(text: str) -> List[str]:
    moves: List[str] = []
    for cand in re.findall(r"[\"“”'‘’]([A-Za-zÀ-ÖØ-öø-ÿ0-9][A-Za-zÀ-ÖØ-öø-ÿ0-9 '\-:]+?)[\"“”'‘’]", text):
        cand = clean_move_candidate(cand)
        if is_probably_move_name(cand) and cand not in moves:
            moves.append(cand)
    return moves


def extract_profile_paragraph_text(lines: List[str]) -> str:
    end = min(len(lines), 140)
    for stop in ["Name Etymology", "Contents", "Attack Techniques"]:
        if stop in lines:
            end = min(end, lines.index(stop))
    return clean_text(" ".join(lines[:end]))


def choose_one_move_from_candidates(candidates: List[str], prefer_last: bool = False) -> str:
    cleaned: List[str] = []
    for cand in candidates:
        cand = clean_move_candidate(cand)
        if is_probably_move_name(cand) and cand not in cleaned:
            cleaned.append(cand)
    if not cleaned:
        return ""
    return cleaned[-1] if prefer_last and len(cleaned) > 1 else cleaned[0]


def split_special_sentence_parts(sent: str) -> List[str]:
    sent = clean_text(sent)
    parts = re.split(r"\s*,\s+and\s+|\s+and\s+(?=an?\s|the\s|a\s|[A-Z])", sent)
    return [clean_text(p) for p in parts if clean_text(p)]


def move_from_profile_sentence(lines: List[str]) -> str:
    txt = extract_profile_paragraph_text(lines)

    for line in lines[:180]:
        mline = re.match(r"^Special Moves?\s*[:：]\s*(.+)$", line, flags=re.I)
        if not mline:
            continue
        sent = clean_text(mline.group(1))
        is_plural = bool(re.match(r"^Special Moves", line, flags=re.I))
        parens = extract_parenthesized_moves(sent)
        if parens:
            return choose_one_move_from_candidates(parens, prefer_last=is_plural)
        quotes = extract_quoted_moves(sent)
        if quotes:
            return choose_one_move_from_candidates(quotes, prefer_last=is_plural)
        first = re.split(r",| and |\. |;", sent, maxsplit=1)[0]
        first = clean_move_candidate(first)
        if is_probably_move_name(first):
            return first

    patterns = [
        (r"Its Special Move is (.*?)(?: Digimon Reference Book| This profile| Name Etymology| Attack Techniques| Contents|$)", False),
        (r"Its Special Moves are (.*?)(?: Digimon Reference Book| This profile| Name Etymology| Attack Techniques| Contents|$)", True),
        (r"Special Move[:：]\s*(.*?)(?: Digimon Reference Book| This profile| Name Etymology| Attack Techniques| Contents|$)", False),
        (r"Special Moves[:：]\s*(.*?)(?: Digimon Reference Book| This profile| Name Etymology| Attack Techniques| Contents|$)", True),
        (r"Signature move is (.*?)(?: Digimon Reference Book| This profile| Name Etymology| Attack Techniques| Contents|$)", False),
        (r"Signature moves are (.*?)(?: Digimon Reference Book| This profile| Name Etymology| Attack Techniques| Contents|$)", True),
        (r"Signature skill is (.*?)(?: Digimon Reference Book| This profile| Name Etymology| Attack Techniques| Contents|$)", False),
        (r"Signature skills are (.*?)(?: Digimon Reference Book| This profile| Name Etymology| Attack Techniques| Contents|$)", True),
    ]

    for pat, is_plural in patterns:
        m = re.search(pat, txt, flags=re.I)
        if not m:
            continue
        sent = clean_text(m.group(1))
        parens = extract_parenthesized_moves(sent)
        if parens:
            return choose_one_move_from_candidates(parens, prefer_last=is_plural)
        parts = split_special_sentence_parts(sent)
        part_candidates: List[str] = []
        for part in parts:
            part_candidates.extend(extract_quoted_moves(part))
        if part_candidates:
            return choose_one_move_from_candidates(part_candidates, prefer_last=is_plural)
        quotes = extract_quoted_moves(sent)
        if quotes:
            return choose_one_move_from_candidates(quotes, prefer_last=is_plural)
        first = re.split(r",| and |\. |;", sent, maxsplit=1)[0]
        first = clean_move_candidate(first)
        if is_probably_move_name(first):
            return first
    return ""


def heading_text(tag: Tag) -> str:
    return clean_text(tag.get_text(" ")).lower()


def find_attack_heading(soup: BeautifulSoup) -> Optional[Tag]:
    for tag in soup.find_all(["h2", "h3", "h4", "div", "span"]):
        txt = heading_text(tag)
        tag_id = clean_text(tag.get("id", "")).lower().replace("_", " ")
        if "attack techniques" in txt or "attack techniques" in tag_id or txt == "techniques" or tag_id == "techniques":
            if tag.name == "span" and tag.parent and isinstance(tag.parent, Tag):
                return tag.parent
            return tag
    return None


def next_section_nodes(heading: Tag) -> List[Tag]:
    nodes: List[Tag] = []
    cur = heading.find_next_sibling()
    while cur is not None:
        if isinstance(cur, Tag):
            txt = heading_text(cur)
            if cur.name in {"h2", "h3"} or (cur.name == "div" and "mw-heading" in cur.get("class", [])):
                if txt and (txt in SECTION_STOP_WORDS or "edit" in txt or len(nodes) > 0):
                    break
            nodes.append(cur)
        cur = cur.find_next_sibling()
    return nodes


def table_header_indices(table: Tag) -> Tuple[int, int, int]:
    rows = table.find_all("tr")
    if not rows:
        return 0, -1, -1
    headers = [clean_text(c.get_text(" ")).lower() for c in rows[0].find_all(["th", "td"])]
    name_col, roman_col, trans_col = 0, -1, -1
    for i, h in enumerate(headers):
        if h == "name" or "name" in h:
            name_col = i
        if "romanization" in h or "romanisation" in h:
            roman_col = i
        if "translation" in h:
            trans_col = i
    return name_col, roman_col, trans_col


def preferred_move_for_page(user_name: str = "", page_title: str = "") -> str:
    keys = [normalize_lookup_name(user_name), normalize_lookup_name(page_title)]
    for key in keys:
        if key in PREFERRED_WIKIMON_MOVE_BY_PAGE:
            return PREFERRED_WIKIMON_MOVE_BY_PAGE[key]
    return ""


def extract_attack_table_candidates(soup: BeautifulSoup) -> List[str]:
    found: List[str] = []

    def add(raw: str):
        cand = clean_move_candidate(raw)
        if is_probably_move_name(cand) and cand not in found:
            found.append(cand)

    # Most reliable: Attack Techniques tables, first column, bold/italic name.
    heading = find_attack_heading(soup)
    search_root = next_section_nodes(heading) if heading else soup.find_all("table")

    tables = []
    for node in search_root:
        if not isinstance(node, Tag):
            continue
        if node.name == "table":
            tables.append(node)
        tables.extend(node.find_all("table"))

    for table in tables:
        rows = table.find_all("tr")
        for tr in rows[1:]:
            cells = tr.find_all(["td", "th"])
            if not cells:
                continue

            first = cells[0]

            # This catches Wikimon's actual move-name cell:
            # td:nth-child(1) > i > b
            for tag in first.select("i > b, b, i, a"):
                add(tag.get_text(" "))

            # Fallback: first cell text only, never description cells first.
            add(first.get_text(" "))

    return found

def choose_attack_table_candidate(candidates: List[str], preferred: str = "") -> str:
    if preferred:
        pref_norm = normalize_lookup_name(preferred)
        for cand in candidates:
            if normalize_lookup_name(cand) == pref_norm:
                return cand
    return candidates[0] if candidates else ""


def extract_move_from_attack_tables(soup: BeautifulSoup, preferred: str = "") -> str:
    return choose_attack_table_candidate(extract_attack_table_candidates(soup), preferred=preferred)

def extract_attack_technique_first(lines: List[str]) -> str:
    start = None
    for i, line in enumerate(lines):
        if "attack techniques" in line.lower() or line.lower() == "techniques":
            start = i
            break
    if start is None:
        return ""
    for line in lines[start + 1:start + 90]:
        low = line.lower()
        if low in SECTION_STOP_WORDS or any(low.startswith(s + " ") for s in SECTION_STOP_WORDS):
            break
        if low in STOP_MOVE_WORDS:
            continue
        cand = clean_move_candidate(line)
        if is_probably_move_name(cand):
            return cand
    return ""

def extract_special_move(soup: BeautifulSoup, user_name: str = "", page_title: str = "") -> str:
    clean_soup = strip_wikimon_noise(soup)
    lines = soup_lines(clean_soup)
    preferred = preferred_move_for_page(user_name, page_title)

    # 1. Preferred override.
    if preferred:
        move = extract_move_from_attack_tables(clean_soup, preferred=preferred)
        if move:
            return move

    # 2. Attack Techniques table MUST come before profile sentence.
    move = extract_move_from_attack_tables(clean_soup)
    if move:
        return move

    # 3. Only then use profile text.
    move = move_from_profile_sentence(lines)
    if move:
        return move

    move = extract_attack_technique_first(lines)
    if move:
        return move

    return "Unknown"


# -----------------------------
# Wikimon image lookup
# -----------------------------

def filename_from_url_or_title(s: str) -> str:
    s = unquote(str(s))
    s = s.split("?")[0].split("#")[0]
    s = s.rstrip("/")
    return s.rsplit("/", 1)[-1].replace("File:", "").replace("Image:", "")


def image_tokens(page_title: str, user_name: str) -> List[str]:
    text = f"{page_title} {user_name}"
    text = text.replace(":", " ").replace("(", " ").replace(")", " ").replace("-", " ")
    raw = re.findall(r"[A-Za-z0-9]+", text.lower())
    stop = {"mode", "form", "the", "digimon"}
    tokens = []
    for t in raw:
        if len(t) >= 3 and t not in stop and t not in tokens:
            tokens.append(t)
    return tokens


def is_skipped_image_name(name: str) -> bool:
    low = filename_from_url_or_title(name).lower()
    # Skip before resolving/downloading. User requested keyword "card" to be
    # completely ignored, so substring matching is intentional.
    return any(skip.lower() in low for skip in SKIP_IMAGE_KEYWORDS)


def is_bad_image_name(name: str) -> bool:
    low = filename_from_url_or_title(name).lower()
    if is_skipped_image_name(low):
        return True
    if not re.search(r"\.(png|jpg|jpeg|webp|gif)$", low):
        return True
    return any(bad in low for bad in BAD_IMAGE_WORDS)


def score_image_name(name: str, page_title: str, user_name: str) -> int:
    fname = filename_from_url_or_title(name).lower()
    if is_bad_image_name(fname):
        return -9999
    score = 0
    tokens = image_tokens(page_title, user_name)
    for t in tokens:
        if t in fname:
            score += 20
    # Prefer non-reference scene sources when filenames reveal them.
    if fname.endswith((".jpg", ".jpeg")):
        score += 8
    if fname.endswith(".png"):
        score += 5
    if any(w in fname for w in ["anime", "game", "screenshot", "battle", "movie", "tri", "adventure", "xros", "sav", "frontier", "tamers"]):
        score += 12
    if any(w in fname for w in ["bo-", "st-", "promo", "bt", "ex", "rb"]):
        score += 7
    if any(w in fname for w in ["reference", "drb", "art"]):
        score -= 5
    if "sprite" in fname or "dot" in fname:
        score -= 8
    return score


def api_image_url_for_file(file_title: str) -> str:
    if is_skipped_image_name(file_title):
        return ""
    if not file_title.lower().startswith("file:"):
        file_title = "File:" + filename_from_url_or_title(file_title)
    params = {
        "action": "query",
        "titles": file_title,
        "prop": "imageinfo",
        "iiprop": "url",
        "format": "json",
    }
    try:
        r = requests.get(WIKIMON_API, params=params, headers=HTTP_HEADERS, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        pages = r.json().get("query", {}).get("pages", {})
        for page in pages.values():
            infos = page.get("imageinfo", [])
            if infos and infos[0].get("url"):
                return infos[0]["url"]
    except Exception:
        pass
    return ""


def wikimon_api_image_candidates(page_title: str, user_name: str) -> List[str]:
    candidates: List[str] = []
    titles_to_try = []
    for t in wikimon_title_candidates(page_title or user_name):
        titles_to_try.append(t.replace("_", " "))
    if user_name:
        titles_to_try.append(user_name)
    if page_title:
        titles_to_try.append(page_title)

    for title in titles_to_try:
        params = {
            "action": "query",
            "titles": title,
            "redirects": 1,
            "prop": "images|pageimages",
            "imlimit": "max",
            "piprop": "original|thumbnail|name",
            "pithumbsize": 700,
            "format": "json",
        }
        try:
            r = requests.get(WIKIMON_API, params=params, headers=HTTP_HEADERS, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            pages = r.json().get("query", {}).get("pages", {})
            for page in pages.values():
                original = page.get("original", {})
                thumb = page.get("thumbnail", {})
                for url in [original.get("source"), thumb.get("source")]:
                    if url and url not in candidates:
                        candidates.append(url)
                for img in page.get("images", []):
                    img_title = img.get("title", "")
                    if img_title and img_title not in candidates:
                        candidates.append(img_title)
        except Exception:
            continue
    return candidates


def scrape_image_candidates(soup: BeautifulSoup) -> List[str]:
    candidates: List[str] = []
    clean_soup = strip_wikimon_noise(soup)

    # First collect linked File/Image pages.
    for a in clean_soup.select("a.image, a[href*='/File:'], a[href*='/Image:']"):
        href = a.get("href", "")
        title = a.get("title", "")
        if href:
            if "/File:" in href or "/Image:" in href:
                candidates.append(filename_from_url_or_title(href))
        if title:
            candidates.append(title)
        img = a.find("img")
        if img:
            for attr in ["src", "data-src"]:
                src = img.get(attr)
                if src:
                    candidates.append(urljoin(WIKIMON_BASE, src))
            for attr in ["alt", "title"]:
                val = img.get(attr)
                if val:
                    candidates.append(val)

    # Then collect regular content imgs as fallback.
    for img in clean_soup.find_all("img"):
        for attr in ["src", "data-src"]:
            src = img.get(attr)
            if src:
                candidates.append(urljoin(WIKIMON_BASE, src))
        for attr in ["alt", "title"]:
            val = img.get(attr)
            if val:
                candidates.append(val)

    deduped: List[str] = []
    for c in candidates:
        c = clean_text(c)
        if c and c not in deduped:
            deduped.append(c)
    return deduped


def resolve_image_candidate(candidate: str) -> str:
    candidate = clean_text(candidate)
    if not candidate:
        return ""
    if is_skipped_image_name(candidate):
        return ""
    if candidate.startswith("//"):
        return "https:" + candidate
    if candidate.startswith("http://") or candidate.startswith("https://"):
        return candidate
    fname = filename_from_url_or_title(candidate)
    if fname.lower().startswith(("file:", "image:")):
        return api_image_url_for_file(fname)
    if re.search(r"\.(png|jpg|jpeg|webp|gif)$", fname, flags=re.I):
        return api_image_url_for_file("File:" + fname)
    return ""



def color_bin(pixel: Tuple[int, int, int]) -> Tuple[int, int, int]:
    r, g, b = pixel[:3]
    return (r // 32, g // 32, b // 32)


def looks_reference_like_image(im: Image.Image, debug_label: str = "") -> bool:
    """Heuristic: True for transparent/white/single-color-background reference art.

    Anime/game/TCG/scenery images usually have many colors around the image edges.
    Reference art often has transparency, white, or a flat single-color background.
    """
    if im is None:
        return True

    rgba = im.convert("RGBA")
    w, h = rgba.size
    if w < 10 or h < 10:
        return True

    # Transparent-background PNG/reference art.
    alpha = rgba.getchannel("A")
    alpha_small = alpha.resize((80, 80), Image.Resampling.NEAREST)
    alpha_vals = list(alpha_small.getdata())
    transparent_ratio = sum(1 for a in alpha_vals if a < 24) / max(1, len(alpha_vals))
    if transparent_ratio > 0.08:
        return True

    # Analyze only border pixels. Background is usually visible at the edges.
    rgb = rgba.convert("RGB").resize((120, 120), Image.Resampling.LANCZOS)
    bw, bh = rgb.size
    border = []
    edge = 10
    pix = rgb.load()
    for y in range(bh):
        for x in range(bw):
            if x < edge or x >= bw - edge or y < edge or y >= bh - edge:
                border.append(pix[x, y])

    if not border:
        return True

    bins: Dict[Tuple[int, int, int], int] = {}
    whiteish = 0
    low_sat_light = 0
    for r, g, b in border:
        bins[color_bin((r, g, b))] = bins.get(color_bin((r, g, b)), 0) + 1
        mx, mn = max(r, g, b), min(r, g, b)
        if r > 235 and g > 235 and b > 235:
            whiteish += 1
        if mx > 210 and (mx - mn) < 25:
            low_sat_light += 1

    total = len(border)
    dominant_ratio = max(bins.values()) / total
    white_ratio = whiteish / total
    low_sat_light_ratio = low_sat_light / total

    # White/near-white background.
    if white_ratio > 0.45 or low_sat_light_ratio > 0.60:
        return True

    # Mostly one flat color background, even if not white.
    if dominant_ratio > 0.55:
        return True

    return False



def anime_keyword_rank(url_or_name: str) -> int:
    """Return ordered anime keyword rank. 0 is best. Large number means no match."""
    fname = filename_from_url_or_title(url_or_name)
    for rank, (kind, pattern) in enumerate(ANIME_IMAGE_KEYWORD_RULES):
        if kind == "exact":
            if fname == pattern or fname.endswith(pattern):
                return rank
        elif kind == "contains":
            if pattern in fname:
                return rank
        elif kind == "regex":
            if re.search(pattern, fname):
                return rank
    return 9999


def filename_scene_hint_score(url_or_name: str) -> int:
    name = filename_from_url_or_title(url_or_name).lower()
    score = 0

    # Strong bonus for anime/game/screenshot keywords.
    anime_rank = anime_keyword_rank(url_or_name)
    if anime_rank < 9999:
        score += 1000 - anime_rank

    # TCG-like images are still preferred over reference art, but below anime.
    # Plain "card" filenames are skipped entirely by SKIP_IMAGE_KEYWORDS.
    if any(w in name for w in ["bo-", "st-", "promo", "bt", "ex", "rb"]):
        score += 120

    # General scene/game hints.
    if any(w in name for w in ["game", "screenshot", "battle"]):
        score += 80

    # Reference hints.
    if any(w in name for w in ["reference", "drb", "art"]):
        score -= 40

    return score


def image_priority_tuple(score: int, url: str, cand: str, im: Optional[Image.Image], debug: bool = False) -> Tuple[int, int, int]:
    """Return sortable priority tuple.

    Lower is better:
      category 0 = anime filename keyword match
      category 1 = non-reference / multicolor background image, treated as TCG/game/scenery
      category 2 = reference-like image
      category 3 = image could not be downloaded/tested
    """
    anime_rank = min(anime_keyword_rank(cand), anime_keyword_rank(url))

    if anime_rank < 9999:
        category = 0
        reference_like = False
    elif im is None:
        category = 3
        reference_like = True
    else:
        reference_like = looks_reference_like_image(im, debug_label=cand)
        category = 2 if reference_like else 1

    # Within category:
    # - anime: lower anime_rank wins.
    # - TCG/non-reference/reference: higher filename/image score wins, so use negative.
    hint = filename_scene_hint_score(cand) + filename_scene_hint_score(url) + score

    if debug:
        label = ["anime", "tcg_or_scene", "reference", "untested"][category]
        print(f"  tested image: category={label} anime_rank={anime_rank} reference_like={reference_like} score={hint} url={url}")

    return (category, anime_rank, -hint)


def find_wikimon_image_url(soup: BeautifulSoup, page_title: str, user_name: str, debug: bool = False) -> str:
    """Choose the best Wikimon image quickly.

    Faster priority order:
      1) Compare filenames/titles first. If an anime keyword matches, return the
         best matching image immediately without downloading/testing backgrounds.
      2) If no anime-keyword image exists, resolve candidates and download/test
         one image at a time until a multicolor/non-reference image is found.
      3) If all tested images are reference-like, fall back to the best reference.

    This avoids the old slow behavior where every resolved image was downloaded
    before choosing.
    """
    raw_candidates = wikimon_api_image_candidates(page_title, user_name) + scrape_image_candidates(soup)

    scored: List[Tuple[int, str]] = []
    seen = set()
    for c in raw_candidates:
        key = clean_text(c)
        if not key or key in seen:
            continue
        if is_skipped_image_name(key):
            if debug:
                print(f"  skipped image candidate by keyword: {key}")
            continue
        seen.add(key)
        score = score_image_name(key, page_title, user_name)
        if score > -1000:
            scored.append((score, key))

    # Sort by anime keyword rank first, then normal filename score.
    scored.sort(key=lambda x: (anime_keyword_rank(x[1]), -(x[0] + filename_scene_hint_score(x[1]))))

    if debug:
        print("Image candidates, title-ranked:")
        for score, cand in scored[:24]:
            ar = anime_keyword_rank(cand)
            ar_txt = ar if ar < 9999 else "-"
            print(f"  {score:4d}  anime_rank={ar_txt}  {cand}")

    # Step 1: anime keyword title wins immediately. Do NOT download all images.
    # Encounter/new_century are included in ANIME_IMAGE_KEYWORD_RULES, so they
    # intentionally bypass reference-background detection too.
    anime_title_matches: List[Tuple[int, int, str]] = []
    for score, cand in scored:
        rank = anime_keyword_rank(cand)
        if rank < 9999:
            anime_title_matches.append((rank, -score, cand))

    anime_title_matches.sort()
    for rank, neg_score, cand in anime_title_matches:
        url = resolve_image_candidate(cand)
        if url and not is_bad_image_name(url):
            if debug:
                print(f"  chosen by anime title keyword: rank={rank} cand={cand}")
                print(f"  chosen image category=anime url={url}")
            return url

    # Step 2: no anime title match. Now check candidates one at a time.
    # This is where we download, because multicolor TCG/game/scenery vs reference
    # can only be detected from pixels when the filename does not say it clearly.
    scored.sort(reverse=True, key=lambda x: (x[0] + filename_scene_hint_score(x[1])))

    best_reference_url = ""
    best_reference_score = -999999
    tested_count = 0
    seen_urls = set()

    for score, cand in scored:
        if tested_count >= MAX_IMAGE_CANDIDATES_TO_TEST:
            break

        url = resolve_image_candidate(cand)
        if not url or is_bad_image_name(url) or url in seen_urls:
            continue
        seen_urls.add(url)

        # Download only this candidate now; stop as soon as we find a scene/TCG-like image.
        im = download_image(url)
        tested_count += 1

        if im is None:
            if debug:
                print(f"  tested image: download_failed cand={cand} url={url}")
            continue

        reference_like = looks_reference_like_image(im, debug_label=cand)
        final_score = score + filename_scene_hint_score(cand) + filename_scene_hint_score(url)

        if debug:
            label = "reference" if reference_like else "tcg_or_scene"
            print(f"  tested image: category={label} reference_like={reference_like} score={final_score} cand={cand}")
            print(f"    url={url}")

        if not PREFER_SCENE_IMAGE_OVER_REFERENCE:
            return url

        if not reference_like:
            if debug:
                print(f"  chosen image category=tcg_or_scene url={url}")
            return url

        if final_score > best_reference_score:
            best_reference_url = url
            best_reference_score = final_score

    # Step 3: no multicolor image found, use best reference fallback.
    if best_reference_url:
        if debug:
            print(f"  no anime/title or scene-like image found; falling back to reference url={best_reference_url}")
        return best_reference_url

    # Last fallback: resolve first valid candidate, without background checking.
    for score, cand in scored:
        url = resolve_image_candidate(cand)
        if url and not is_bad_image_name(url):
            if debug:
                print(f"  fallback first valid image url={url}")
            return url

    return ""

def download_image(url: str) -> Optional[Image.Image]:
    if not url or is_skipped_image_name(url):
        return None

    # Cache avoids downloading the chosen image twice: once during background
    # testing and again when pasting into the template.
    if url in _IMAGE_CACHE:
        return _IMAGE_CACHE[url].copy()

    try:
        r = requests.get(url, headers=HTTP_HEADERS, timeout=IMAGE_DOWNLOAD_TIMEOUT)
        r.raise_for_status()
        im = Image.open(io.BytesIO(r.content))
        im.load()
        im = im.convert("RGBA")
        _IMAGE_CACHE[url] = im.copy()
        return im
    except Exception:
        return None

def paste_fit_image(base: Image.Image, digimon_img: Image.Image, box: Tuple[int, int, int, int]) -> None:
    """Paste the Digimon image so it completely fills the white image box.

    Normal behavior is CSS-like "cover" fit:
    - scale up/down until the whole box is covered
    - crop overflow
    - paste the final crop exactly into DIGIMON_IMAGE_BOX

    v25 improvement:
    - very tall portrait images are cropped from the top instead of center-cropped
      vertically, so the face / upper body remains visible.
    """
    x1, y1, x2, y2 = box
    bw, bh = x2 - x1, y2 - y1

    iw, ih = digimon_img.size
    if iw <= 0 or ih <= 0 or bw <= 0 or bh <= 0:
        return

    # COVER mode: use max(), not min().
    # min() = contain/letterbox; max() = fill/crop.
    scale = max(bw / iw, bh / ih)
    nw, nh = max(1, int(round(iw * scale))), max(1, int(round(ih * scale)))

    resized = digimon_img.resize((nw, nh), Image.Resampling.LANCZOS).convert("RGBA")

    # Horizontal crop stays centered.
    left = max(0, (nw - bw) // 2)

    # Vertical crop:
    # - normal images: center crop
    # - very tall images: anchor toward the top so the head/upper body survives
    source_height_width_ratio = ih / max(1, iw)
    if (
        TALL_IMAGE_TOP_CROP
        and nh > bh
        and source_height_width_ratio >= TALL_IMAGE_HEIGHT_WIDTH_THRESHOLD
    ):
        overflow_y = nh - bh
        top = int(round(overflow_y * TALL_IMAGE_VERTICAL_CROP_ANCHOR))
        top = max(0, min(top, overflow_y))
    else:
        top = max(0, (nh - bh) // 2)

    cropped = resized.crop((left, top, left + bw, top + bh))

    # Composite onto white first so transparent PNGs do not reveal the old white box
    # unevenly around non-transparent areas.
    background = Image.new("RGBA", (bw, bh), (255, 255, 255, 255))
    background.alpha_composite(cropped)

    base.paste(background.convert("RGB"), (x1, y1))

DIGI_API_LIST_URL = "https://digi-api.com/api/v1/digimon?pageSize=3000"
_DIGI_API_LIST_CACHE: Optional[List[Dict[str, object]]] = None
MANUAL_NAME_FIXES = {
    "holsmom": "Holsmon",
    "rapidmongold": "Rapidmon Armor",
    "rapidmonarmor": "Rapidmon Armor",
    "cherubimonvice": "Cherubimon_(Vice)",
    "scumon": "Scumon",
    "okuwamon": "Okuwamon",
    "fujitsumon": "Octmon",
    "agumon2006": "Agumon_(2006_Anime_Version)",
    "agumonbx": "Agumon_(Black)_(X-Antibody)",
    "agumonblack": "Agumon_(Black)",
    "agumonx": "Agumon_(X-Antibody)",
    "agumonhakase": "Agumon_Hakase",
    "algomonlv1": "Algomon_(Baby_I)",
    "algomonlv2": "Algomon_(Baby_II)",
    "algomonlv3": "Algomon_(Child)",
    "algomonlv4": "Algomon_(Adult)",
    "algomonultimate": "Algomon_(Ultimate)",
    "allomonx": "Allomon_(X-Antibody)",
    "ancientbeatmon": "Ancient_Beatmon",
    "ancienttroiamon": "Ancient_Troiamon",
    "ancientsphinkmon": "Ancient_Sphinxmon",
    "ancientwisetmon": "Ancient_Wisemon",
    "andiramon": "Andiramon_(Deva)",
    "andiramon2": "Andiramon",
    "angewomonx": "Angewomon_(X-Antibody)",
    "anomalocarimonx": "Anomalocarimon_(X-Antibody)",
    "apollomonwhispered": "Apollomon:_Whispered",
    "arkhaiangemon": "Arkhai_Angemon",
    "armamonburstmode": "Armamon:_Burst_Mode",
    "arresterdramonsuperior": "Arresterdramon:_Superior_Mode",
    "arresterdramonsuperior2": "Arresterdramon:_Superior_Mode_(Brave_Snatcher)",
    "atlurballistamon": "Atlur_Ballistamon",
    "atlurkabuterimonblue": "Atlur_Kabuterimon_(Blue)",
    "atlurkabuterimon": "Atlur_Kabuterimon_(Red)",
    "bancholeomon": "Bancho_Leomon",
    "bancholilimon": "Bancho_Lilimon",
    "banchomamemon": "Bancho_Mamemon",
    "banchostingmon": "Bancho_Stingmon",
    "baohuckmon": "Bao_Hackmon",
    "barbamonx": "Barbamon_(X-Antibody)",
    "baristamon": "ballistamon",
    "beelstarmon": "Beel_Starmon",
    "beelstarmonx": "Beel_Starmon_(X-Antibody)",
    "beelzebumonx": "Beelzebumon_(X-Antibody)",
    "beelzebumonxwars": "Beelzebumon_(2010_Anime_Version)",
    "beelzebumonblastmode": "Beelzebumon:_Blast_Mode",
    "belphemonx": "Belphemon_(X-Antibody)",
    "belphemonragemode": "Belphemon:_Rage_Mode",
    "betelgammamon": "Betel_Gammamon",
    "bigukkomon": "Big_Ukkomon",
    "blacktailmonuver": "Black_Tailmon_Uver.",
    "blackwargreymonx": "Black_War_Greymon_(X-Antibody)",
    "capromon": "Caprimon",
    "cerberumonx": "Cerberumon_(X-Antibody)",
    "chaosdramonx": "Chaosdramon_(X-Antibody)",
    "cherubimonx": "Cherubimon_(Virtue)_(X-Antibody)",
    "cherubimondarkx": "Cherubimon_(Vice)_(X-Antibody)",
    "coredramonb": "Coredramon_(Blue)",
    "coredramong": "Coredramon_(Green)",
    "craniummonx": "Craniummon_(X-Antibody)",
    "cyberdramonx": "Cyberdramon_(X-Antibody)",
    "cyberdramonxwars": "Cyberdramon_(Xros_Wars)",
    "darkknightmon": "Dark_Knightmon",
    "darkknightmonx": "Dark_Knightmon_(X-Antibody)",
    "darknessbagramon": "Darkness_Bagramon",
    "darktyranomonx": "Dark_Tyranomon_(X-Antibody)",
    "deathxdorugamon": "Death-X-DORUgamon",
    "deathxdorugoramon": "Death-X-DORUgoramon",
    "deathxdoruguremon": "Death-X-DORUguremon",
    "deathmonblack": "Deathmon_(Black)",
    "deckergreymon": "Decker_Greymon",
    "demonxantibody": "Demon_(X-Antibody)",
    "demonx": "Demon_(X-Antibody)",
    "diablomonx": "Diablomon_(X-Antibody)",
    "donedevimon": "Done_Devimon",
    "dorugreymon": "DORUguremon",
    "dracomonx": "Dracomon_(X-Antibody)",
    "duftmonx": "Duftmon_(X-Antibody)",
    "dukemonx": "Dukemon_(X-Antibody)",
    "dukemoncrimsonmode": "Dukemon:_Crimson_Mode",
    "dynasmonx": "Dynasmon_(X-Antibody)",
    "earovdramon": "Aero_V-dramon",
    "ebemonx": "Ebemon_(X-Antibody)",
    "eosmonlv4": "Eosmon_(Adult)",
    "eosmonlv5": "Eosmon_(Perfect)",
    "eosmonlv6": "Eosmon_(Ultimate)",
    "erlangmonblast": "Erlangmon:_Blast_Mode",
    "extyranomon": "Ex_Tyranomon",
    "examonx": "Examon_(X-Antibody)",
    "falcomon2006": "Falcomon_(2006_Anime_Version)",
    "fenriloogamontakemikazuchi": "Fenriloogamon:_Takemikazuchi",
    "frosvelgrmon": "Fros_Velgrmon",
    "gabumonblack": "Gabumon_(Black)",
    "gabumonkizuna": "Gabumon_-Yujo_no_Kizuna-",
    "gabumonx": "Gabumon_(X-Antibody)",
    "gankoomonx": "Gankoomon_(X-Antibody)",
    "garudamonx": "Garudamon_(X-Antibody)",
    "garurumonblack": "Garurumon_(Black)",
    "goddramonx": "Goddramon_(X-Antibody)",
    "goldvdramon": "Gold_V-dramon",
    "gomamonx": "Gomamon_(X-Antibody)",
    "gracenovamon": "Grace_Novamon",
    "granddracumon": "Grand_Dracumon",
    "grandgalemon": "Grand_Galemon",
    "greyknightsmon": "Grey_Knightsmon",
    "greymonblue": "Greymon_(Blue)",
    "greymonfirst": "Greymon",
    "growmonorange": "Growmon_(Orange)",
    "growmonx": "Growmon_(X-Antibody)",
    "gulusgammamon": "Gulus_Gammamon",
    "heavyleomon": "Heavy_Leomon",
    "hicommandramon": "Hi-Commandramon",
    "hiandromon": "Hi_Andromon",
    "holydramonx": "Holydramon_(X-Antibody)",
    "hououmonx": "Hououmon_(X-Antibody)",
    "hoverespimon": "Hoverespimon",
    "imperialdramondragonmode": "Imperialdramon:_Dragon_Mode",
    "imperialdramonfightermode": "Imperialdramon:_Fighter_Mode",
    "imperialdramonpaladinmode": "Imperialdramon:_Paladin_Mode",
    "impmonx": "Impmon_(X-Antibody)",
    "jesmonx": "Jesmon_(X-Antibody)",
    "jesmongx": "JESmon_GX",
    "justimonblitzarm": "Justimon:_Blitz_Arm",
    "justimoncriticalarm": "Justimon:_Critical_Arm",
    "justimonaccelarm": "Justimon:_Accel_Arm",
    "justimonx": "Justimon_(X-Antibody)",
    "kausgammamon": "Kaus_Gammamon",
    "keramonx": "Keramon_(X-Antibody)",
    "kokuwamonx": "Kokuwamon_(X-Antibody)",
    "kuwagamonx": "Kuwagamon_(X-Antibody)",
    "kuzuhamonmiko": "Kuzuhamon:_Miko_Mode",
    "ladydevimonx": "Lady_Devimon_(X-Antibody)",
    "leomonx": "Leomon_(X-Antibody)",
    "leviamonx": "Leviamon_(X-Antibody)",
    "lilimonx": "Lilimon_(X-Antibody)",
    "lilithmonx": "Lilithmon_(X-Antibody)",
    "lopmonx": "Lopmon_(X-Antibody)",
    "lucemonx": "Lucemon_(X-Antibody)",
    "lordknightmonx": "Lord_Knightmon_(X-Antibody)",
    "lucemonsatanmode": "Lucemon:_Satan_Mode",
    "magnamonx": "Magnamon_(X-Antibody)",
    "mailbirdramon": "Mail_Birdramon",
    "mamemonx": "Mamemon_(X-Antibody)",
    "mammonx": "Mammon_(X-Antibody)",
    "mantaraymonx": "Mantaraymon_(X-Antibody)",
    "marinbullmon": "Marin_Bullmon",
    "marinchimairamon": "Marin_Chimairamon",
    "megalograwmonorange": "Megalo_Growmon_(Orange)",
    "megalogrowmonx": "Megalo_Growmon_(X-Antibody)",
    "megaseadramonx": "Mega_Seadramon_(X-Antibody)",
    "megidramonx": "Megidramon_(X-Antibody)",
    "meicrackmonv": "Meicrackmon:_Vicious_Mode",
    "mephismonx": "Mephismon_(X-Antibody)",
    "metalgarurumonblack": "Metal_Garurumon_(Black)",
    "metalgarurumonx": "Metal_Garurumon_(X-Antibody)",
    "metalgreymonalter": "Metal_Greymon:_Alterous_Mode",
    "metalgreymonv": "Metal_Greymon_(Virus)",
    "metalgreymonvax": "Metal_Greymon_(X-Antibody)",
    "metalgreymonvix": "Metal_Greymon_(Virus)_(X-Antibody)",
    "metalgreymonweb": "Metal_Greymon_(Virus)",
    "metallifekuwagamon": "Metallife_Kuwagamon",
    "metaltyranomonx": "Metal_Tyranomon_(X-Antibody)",
    "agumonkizuna": "Agumon_-Yuki_no_Kizuna-",
    "miragegaogamonburstmode": "Mirage_Gaogamon:_Burst_Mode",
    "monzaemonx": "Monzaemon_(X-Antibody)",
    "nazhamoncrimson": "Nezhamon:_Crimson_Mode",
    "nefertimonx": "Nefertimon_(X-Antibody)",
    "neovamdemon": "Neo_Vamdemon",
    "noblepumpmon": "Noble_Pumpmon",
    "numemonx": "Numemon_(X-Antibody)",
    "ofanimonx": "Ofanimon_(X-Antibody)",
    "ofanimonfalldownmode": "Ofanimon:_Falldown_Mode",
    "ofanimonfdmx": "Ofanimon:_Falldown_Mode_(X-Antibody)",
    "ogudomonx": "Ogudomon_(X-Antibody)",
    "okuwamonx": "Okuwamon_(X-Antibody)",
    "omegamonalters": "Omegamon_Alter-S",
    "omegamonx": "Omegamon_(X-Antibody)",
    "omegashoutmonx": "Omega_Shoutmon_(X-Antibody)",
    "orgemonx": "Orgemon_(X-Antibody)",
    "otamamonx": "Otamamon_(X-Antibody)",
    "palmonx": "Palmon_(X-Antibody)",
    "panjyamonx": "Panjyamon_(X-Antibody)",
    "paunchessmonwhite": "Pawn_Chessmon_(White)",
    "pegasmonx": "Pegasmon_(X-Antibody)",
    "plesiomonx": "Plesiomon_(X-Antibody)",
    "plotmonx": "Plotmon_(X-Antibody)",
    "princemamemonx": "Prince_Mamemon_(X-Antibody)",
    "pteranomonx": "Pteranomon_(X-Antibody)",
    "pucchiemongreen": "Pucchiemon_(Green)",
    "rapidmonx": "Rapidmon_(X-Antibody)",
    "raptorsparrowmon": "Raptor_Sparrowmon",
    "rareraremon": "Rare_Raremon",
    "rasenmonf": "Rasenmon_FM",
    "ravmonburstmode": "Ravmon:_Burst_Mode",
    "redvegimon": "Red_Vegimon",
    "renamonx": "Renamon_(X-Antibody)",
    "hoverespimon": "Hover_Espimon",
    "karatukinumemon": "Karatuki_Numemon",
    "kingwhamon": "King_Whamon",
    "meramonx": "Meramon_(X-Antibody)",
    "rhinomonx": "Rhinomon_(X-Antibody)",
    "rosemonx": "Rosemon_(X-Antibody)",
    "rosemonburstmode": "Rosemon:_Burst_Mode",
    "rucemonfalldownmode": "Lucemon:_Falldown_Mode",
    "rusttyranomon": "Rust_Tyranomon",
    "sakuyamonmikomode": "Sakuyamon:_Miko_Mode",
    "sakuyamonx": "Sakuyamon_(X-Antibody)",
    "saviorhuckmon": "Savior_Hackmon",
    "seadramonx": "Seadramon_(X-Antibody)",
    "seitengokuwmon": "Seiten_Gokuwmon",
    "shakomonx": "Shakomon_(X-Antibody)",
    "shinegreymonburstmode": "Shine_Greymon:_Burst_Mode",
    "minervamonx": "Minervamon_(X-Antibody)",
    "rizegreymonx": "Rize_Greymon_(X-Antibody)",
    "shinmonzaemon": "Shin_Monzaemon",
    "shootingstarmon": "Shooting_Starmon",
    "shoutmonex6": "Shoutmon_EX6",
    "shoutmonking": "Shoutmon_(King_Ver.)",
    "shoutmondx": "Shoutmon_DX",
    "shoutmonx2": "Shoutmon_X2",
    "shoutmonx3": "Shoutmon_X3",
    "shoutmonx4": "Shoutmon_X4",
    "shoutmonx5": "Shoutmon_X5",
    "shoutmonx6": "Shoutmon_X6",
    "shoutmonx7": "Shoutmon_X7",
    "shoutmonx3gm": "Shoutmon_X3GM",
    "shoutmonx3sd": "Shoutmon_X3SD",
    "shoutmonx4b": "Shoutmon_X4B",
    "shoutmonx4k": "Shoutmon_X4K",
    "shoutmonx4s": "Shoutmon_X4S",
    "shoutmonx5b": "Shoutmon_X5B",
    "shoutmonx5s": "Shoutmon_X5S",
    "shoutmonx7superior": "Shoutmon_X7:_Superior_Mode",
    "siesamonx": "Siesamon_(X-Antibody)",
    "sistermonciel": "Sistermon_Ciel",
    "sistermonblanc": "Sistermon_Blanc",
    "sistermonnoir": "Sistermon_Noir",
    "skullknightmon": "Skull_Knightmon",
    "skullmammonx": "Skull_Mammon_(X-Antibody)",
    "sleipmonx": "Sleipmon_(X-Antibody)",
    "snowgoburimon": "Snow_Goburimon",
    "splashmon2": "Splashmon",
    "tailmonx": "Tailmon_(X-Antibody)",
    "takutoumonwrath": "Takutoumon:_Wrath_Mode",
    "taowumon": "Taomon",
    "terriermonx": "Terriermon_(X-Antibody)",
    "teslajellymon": "Tesla_Jellymon",
    "togemonx": "Togemon_(X-Antibody)",
    "triceramonx": "Triceramon_(X-Antibody)",
    "tylomonx": "Tylomon_(X-Antibody)",
    "tyranomonx": "Tyranomon_(X-Antibody)",
    "ulforcevdramonx": "Ulforce_V-dramon_(X-Antibody)",
    "ulforceveedramonfuturemode": "Ulforce_Veedramon_Future_Mode",
    "ultimatebrakimon": "Ultimate_Brachimon",
    "vdramon": "V-dramon",
    "vamdemonx": "Vamdemon_(X-Antibody)",
    "waregarurumonsagittarius": "Were_Garurumon:_Sagittarius_Mode",
    "wargreymonx": "War_Greymon_(X-Antibody)",
    "weregarrumon": "Were_Garurumon",
    "weregarurumonblack": "Were_Garurumon_(Black)",
    "weregarurumonx": "Were_Garurumon_(X-Antibody)",
    "wezengammamon": "Wezen_Gammamon",
    "wizarmonx": "Wizarmon_(X-Antibody)",
    "xvmon": "XV-mon",
    "yaegerdorurumon": "Yaeger_Dorulumon",
    "yunimon": "unimon",
    "zekegreymon": "Zeke_Greymon",
    "omegamonzwart": "Omegamon_Zwart",
    "symbareangoramon": "Symbare_Angoramon",
    "tokomonx": "Tokomon_(X-Antibody)",
}

def digi_api_name_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", clean_text(s).lower())

def resolve_analyzer_search_name(raw_name: str) -> str:
    original = clean_text(raw_name)

    manual_key = digi_api_name_key(original)
    if manual_key in MANUAL_NAME_FIXES:
        return MANUAL_NAME_FIXES[manual_key]

    return original

def get_digi_api_list() -> List[Dict[str, object]]:
    global _DIGI_API_LIST_CACHE
    if _DIGI_API_LIST_CACHE is not None:
        return _DIGI_API_LIST_CACHE

    try:
        r = requests.get(DIGI_API_LIST_URL, headers=HTTP_HEADERS, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        _DIGI_API_LIST_CACHE = data.get("content", [])
        return _DIGI_API_LIST_CACHE
    except Exception:
        _DIGI_API_LIST_CACHE = []
        return []


def find_digi_api_match(user_name: str) -> Optional[Dict[str, object]]:
    target = digi_api_name_key(user_name)
    if not target:
        return None

    rows = get_digi_api_list()
    best = None
    best_score = -1

    for row in rows:
        api_name = str(row.get("name", ""))
        api_key = digi_api_name_key(api_name)

        if not api_key:
            continue

        score = -1

        if api_key == target:
            score = 10000
        elif target in api_key:
            score = 8000 + len(target)
        elif api_key in target:
            score = 7000 + len(api_key)

        if score > best_score:
            best_score = score
            best = row

    return best if best_score >= 0 else None


def fetch_digi_api_data(user_name: str, debug: bool = False) -> Optional[Dict[str, str]]:
    match = find_digi_api_match(user_name)
    if not match:
        return None

    href = str(match.get("href", ""))
    if not href:
        digimon_id = match.get("id")
        href = f"https://digi-api.com/api/v1/digimon/{digimon_id}"

    try:
        r = requests.get(href, headers=HTTP_HEADERS, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return None

    level = data.get("levels", [{}])[0].get("level", "Unknown") if data.get("levels") else "Unknown"
    dtype = data.get("types", [{}])[0].get("type", "Unknown") if data.get("types") else "Unknown"
    attribute = data.get("attributes", [{}])[0].get("attribute", "Unknown") if data.get("attributes") else "Unknown"
    skills = data.get("skills", [])

    skill_names = []
    for skill in skills[:2]:
        name = clean_text(skill.get("skill", ""))
        if name and name not in skill_names:
            skill_names.append(name)

    if skill_names:
        special_move = "\n\n".join(skill_names)
    else:
        special_move = "Unknown"

    if debug:
        print("Digi-API match:")
        print(f"  input: {user_name}")
        print(f"  matched_name: {data.get('name')}")
        print(f"  id: {data.get('id')}")
        print(f"  url: {href}")

    return {
        "level": clean_text(level),
        "type": clean_text(dtype),
        "attribute": clean_text(attribute),

        # Do NOT use clean_text() here, because it destroys "\n"
        "special_move": special_move,

        "digi_api_source": href,
    }

def fetch_digimon_data(name: str, debug: bool = False, data_source: str = "wikimon", profile_root: Path = PROFILE_ROOT) -> Dict[str, object]:
    # Always load Wikimon for image lookup.
    soup, url = get_soup_for_name(name)
    h1 = soup.find("h1")
    page_title = clean_text(h1.get_text(" ")) if h1 else name

    # Prefer Digi-API for level/type/attribute/special move.
    if data_source == "terminal":
        terminal_data = read_terminal_profile_data(name, profile_root, debug=debug)

        level = terminal_data["level"]
        dtype = terminal_data["type"]
        attribute = terminal_data["attribute"]
        move = terminal_data["special_move"]
        data_source_used = terminal_data["source"]

    else:
        digi_data = fetch_digi_api_data(name, debug=debug)

        if digi_data:
            level = digi_data["level"]
            dtype = digi_data["type"]
            attribute = digi_data["attribute"]
            move = digi_data["special_move"]
            data_source_used = digi_data["digi_api_source"]
        else:
            info = extract_profile_info(soup, page_title, name)
            level = info.get("level", "Unknown")
            dtype = info.get("type", "Unknown")
            attribute = info.get("attribute", "Unknown")
            move = extract_special_move(soup, name, page_title)
            data_source_used = url

    # Images still always come from Wikimon.
    image_url = find_wikimon_image_url(soup, page_title, name, debug=debug) if AUTO_ADD_DIGIMON_IMAGE else ""

    return {
        "name": display_name(name),
        "level": level,
        "type": dtype,
        "attribute": attribute,
        "special_move": move,
        "image_url": image_url,
        "source": data_source_used,
        "wikimon_source": url,
    }


def load_font(size: int, bold: bool = False):
    candidates = []
    if bold:
        candidates += [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/Library/Fonts/Arial Bold.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
    candidates += [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size=size)
    return ImageFont.load_default()


def text_size(draw: ImageDraw.ImageDraw, text: str, font) -> Tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def fit_font(draw: ImageDraw.ImageDraw, text: str, max_w: int, max_h: int, start_size: int, bold=False):
    for size in range(start_size, 7, -1):
        f = load_font(size, bold=bold)
        tw, th = text_size(draw, text, f)
        if tw <= max_w and th <= max_h:
            return f
    return load_font(8, bold=bold)


def draw_centered(draw, box, text, font, fill, y_offset=0):
    x1, y1, x2, y2 = box
    tw, th = text_size(draw, text, font)
    x = x1 + (x2 - x1 - tw) // 2
    y = y1 + (y2 - y1 - th) // 2 + y_offset
    draw.text((x, y), text, fill=fill, font=font)


def wrap_text(draw, text: str, font, max_width: int) -> List[str]:
    words = str(text).split()
    lines: List[str] = []
    cur = ""
    for w in words:
        trial = (cur + " " + w).strip()
        if text_size(draw, trial, font)[0] <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def draw_label_value(draw, x, y, label, value, font_label, font_value, max_width):
    label_text = f"{label}: "
    draw.text((x, y), label_text, fill=TEXT_BLACK, font=font_label)
    label_w = text_size(draw, label_text, font_label)[0]
    lines = wrap_text(draw, value, font_value, max_width - label_w)
    if not lines:
        lines = [""]
    draw.text((x + label_w, y), lines[0], fill=TEXT_BLACK, font=font_value)
    line_h = max(text_size(draw, "Ag", font_value)[1], 12)
    yy = y + line_h + 2
    for line in lines[1:]:
        draw.text((x + label_w, yy), line, fill=TEXT_BLACK, font=font_value)
        yy += line_h + 2
    return yy


def make_card(template_path: str, digimon_name: str, output_path: str, debug: bool = False, data_source: str = "wikimon", profile_root: Path = PROFILE_ROOT):
    GENERATED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    cache_path = analyzer_cache_path(digimon_name)
    output_path = Path(output_path)

    if cache_path.exists() and not should_regenerate(digimon_name):
        cached = Image.open(cache_path).convert("RGB")
        cached.save(output_path, quality=95)
        print(f"Used cached analyzer: {cache_path}")
        print(f"Saved: {output_path}")
        return

    data = fetch_digimon_data(
        digimon_name,
        debug=debug,
        data_source=data_source,
        profile_root=profile_root,
    )

    img = Image.open(template_path).convert("RGB")
    if img.size != (640, 480):
        img = img.resize((640, 480), Image.Resampling.LANCZOS)

    # Add Digimon image before drawing text.
    if AUTO_ADD_DIGIMON_IMAGE and data.get("image_url"):
        dimg = download_image(str(data["image_url"]))
        if dimg is not None:
            paste_fit_image(img, dimg, DIGIMON_IMAGE_BOX)
            if SAVE_DOWNLOADED_DIGIMON_IMAGE:
                safe = re.sub(r"[^A-Za-z0-9_-]+", "_", digimon_name.strip())
                dimg.save(f"{safe}_wikimon_image.png")
        elif debug:
            print("Could not download image_url:", data.get("image_url"))

    draw = ImageDraw.Draw(img)

    center_font = load_font(CENTER_NAME_FONT_SIZE, bold=True)
    right_font = fit_font(
        draw,
        str(data["name"]),
        RIGHT_NAME_BOX[2] - RIGHT_NAME_BOX[0] - 12,
        RIGHT_NAME_BOX[3] - RIGHT_NAME_BOX[1] - 8,
        RIGHT_NAME_START_FONT_SIZE,
        bold=True,
    )

    info_label_font = load_font(INFO_FONT_SIZE, bold=True)
    info_value_font = load_font(INFO_FONT_SIZE, bold=False)
    title_font = load_font(SPECIAL_TITLE_FONT_SIZE, bold=True)
    move_font = load_font(SPECIAL_MOVE_NAME_FONT_SIZE, bold=False)

    for dx, dy in [(1, 1), (-1, 1), (1, -1), (-1, -1)]:
        shifted = (
            CENTER_NAME_BOX[0] + dx,
            CENTER_NAME_BOX[1] + dy,
            CENTER_NAME_BOX[2] + dx,
            CENTER_NAME_BOX[3] + dy,
        )
        draw_centered(draw, shifted, str(data["name"]), center_font, TEXT_BLACK, y_offset=CENTER_NAME_Y_OFFSET)
    draw_centered(draw, CENTER_NAME_BOX, str(data["name"]), center_font, TEXT_WHITE, y_offset=CENTER_NAME_Y_OFFSET)

    draw_centered(draw, RIGHT_NAME_BOX, str(data["name"]), right_font, TEXT_WHITE, y_offset=-1)

    x = INFO_BOX[0] + 10
    y = INFO_BOX[1] + 11
    max_w = INFO_BOX[2] - INFO_BOX[0] - 20
    for label, key in [("LEVEL", "level"), ("TYPE", "type"), ("ATTRIBUTE", "attribute")]:
        y = draw_label_value(draw, x, y, label, str(data[key]), info_label_font, info_value_font, max_w)
        y += 10

    draw_centered(
        draw,
        (MOVES_BOX[0] + 8, MOVES_BOX[1] + 8, MOVES_BOX[2] - 8, MOVES_BOX[1] + 34),
        "SPECIAL MOVE",
        title_font,
        TEXT_BLACK,
        y_offset=-1,
    )

    move_x = MOVES_BOX[0] + 16
    move_y = MOVES_BOX[1] + 50
    move_max_w = MOVES_BOX[2] - MOVES_BOX[0] - 28

    line_gap = 20
    skill_gap = 14

    # IMPORTANT:
    # splitlines() properly handles actual newline characters.
    skills_to_draw = str(data["special_move"]).splitlines()

    for skill_index, skill_text in enumerate(skills_to_draw):
        skill_text = skill_text.strip()

        if not skill_text:
            continue

        wrapped_lines = wrap_text(draw, skill_text, move_font, move_max_w)

        for line in wrapped_lines:
            draw.text((move_x, move_y), line, fill=TEXT_BLACK, font=move_font)
            move_y += line_gap

        # Extra spacing between different skills.
        if skill_index < len(skills_to_draw) - 1:
            move_y += skill_gap

    img.save(output_path, quality=95)
    img.save(cache_path, quality=95)

    if debug:
        print("Extracted data from Wikimon:")
        for k, v in data.items():
            print(f"  {k}: {v}")
        print()
        print("Settings:")
        print(f"  CENTER_NAME_FONT_SIZE = {CENTER_NAME_FONT_SIZE}")
        print(f"  CENTER_NAME_Y_OFFSET = {CENTER_NAME_Y_OFFSET}")
        print(f"  SPECIAL_MOVE_NAME_FONT_SIZE = {SPECIAL_MOVE_NAME_FONT_SIZE}")
        print(f"  AUTO_ADD_DIGIMON_IMAGE = {AUTO_ADD_DIGIMON_IMAGE}")
        print(f"  PREFER_SCENE_IMAGE_OVER_REFERENCE = {PREFER_SCENE_IMAGE_OVER_REFERENCE}")
        print(f"  MAX_IMAGE_CANDIDATES_TO_TEST = {MAX_IMAGE_CANDIDATES_TO_TEST}")
        print(f"  SKIP_IMAGE_KEYWORDS = {sorted(SKIP_IMAGE_KEYWORDS)}")
        print(f"  TALL_IMAGE_TOP_CROP = {TALL_IMAGE_TOP_CROP}")
        print(f"  TALL_IMAGE_HEIGHT_WIDTH_THRESHOLD = {TALL_IMAGE_HEIGHT_WIDTH_THRESHOLD}")
        print(f"  TALL_IMAGE_VERTICAL_CROP_ANCHOR = {TALL_IMAGE_VERTICAL_CROP_ANCHOR}")
        print(f"  DIGIMON_IMAGE_BOX = {DIGIMON_IMAGE_BOX}")
    print(f"Saved: {output_path}")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "name",
        nargs="?",
        default=None,
        help='Example: "Paildramon", "Imperialdramon Paladin Mode", "Coredramon Blue"'
    )

    parser.add_argument("--template", default="Digimon_analyzer_blank.jpg")
    parser.add_argument("--output", default=None)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--data-source", choices=["wikimon", "terminal"], default="wikimon")
    parser.add_argument("--profile-root", default="sd/profile")

    parser.add_argument(
        "--all-digi-api",
        action="store_true",
        help="Generate analyzer images for ALL Digimon from Digi-API pageSize=3000 list"
    )

    parser.add_argument(
        "--all-profile-bin",
        action="store_true",
        help="Generate analyzer images for every .bin file under --profile-root"
    )

    args = parser.parse_args()

    # ---------------------------------------------------------
    # BULK GENERATION MODE
    # ---------------------------------------------------------
    if args.all_digi_api:
        rows = get_digi_api_list()

        if not rows:
            raise RuntimeError("Could not load Digi-API Digimon list.")

        total = len(rows)

        print(f"Loaded {total} Digimon entries from Digi-API.")
        print()

        GENERATED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

        success_count = 0
        fail_count = 0

        for index, row in enumerate(rows, start=1):
            name = clean_text(row.get("name", ""))
            search_name = resolve_analyzer_search_name(name)

            if not name:
                continue

            safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", name)
            output = GENERATED_IMAGES_DIR / f"{safe_name}_analyzer.jpg"

            print(f"[{index}/{total}] Generating: {name} -> {search_name}")

            try:
                make_card(
                    args.template,
                    search_name,
                    str(output),
                    debug=args.debug,
                    data_source=args.data_source,
                    profile_root=Path(args.profile_root),
                )

                success_count += 1

            except Exception as e:
                fail_count += 1

                print(f"FAILED: {name}")
                print(e)

                log_analyzer_error(
                    f"FAILED BULK GENERATION FOR: {name}",
                    e
                )

            print()

        print("--------------------------------------------------")
        print("BULK GENERATION COMPLETE")
        print(f"Success: {success_count}")
        print(f"Failed : {fail_count}")
        print("--------------------------------------------------")

        return
    
    # ---------------------------------------------------------
    # BULK PROFILE BIN MODE
    # ---------------------------------------------------------
    if args.all_profile_bin:
        profile_root = Path(args.profile_root)
        bins = list_profile_bins(profile_root)

        if not bins:
            raise RuntimeError(f"No .bin files found under {profile_root}")

        total = len(bins)

        print(f"Loaded {total} profile .bin files from {profile_root}.")
        print()

        GENERATED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

        success_count = 0
        fail_count = 0

        for index, bin_path in enumerate(bins, start=1):
            raw_name = bin_path.stem
            search_name = resolve_analyzer_search_name(raw_name)

            safe_output_name = re.sub(r"[^A-Za-z0-9_-]+", "_", raw_name)
            output = GENERATED_IMAGES_DIR / f"{safe_output_name}_analyzer.jpg"

            print(f"[{index}/{total}] Generating: {raw_name} -> {search_name}")
            print(f"  Profile bin: {bin_path}")

            try:
                make_card(
                    args.template,
                    search_name,
                    str(output),
                    debug=args.debug,
                    data_source=args.data_source,
                    profile_root=profile_root,
                )

                success_count += 1

            except Exception as e:
                fail_count += 1

                print(f"FAILED: {raw_name}")
                print(e)

                log_analyzer_error(
                    f"FAILED PROFILE BIN GENERATION FOR: {raw_name}\nBIN: {bin_path}",
                    e
                )

            print()

        print("--------------------------------------------------")
        print("PROFILE BIN BULK GENERATION COMPLETE")
        print(f"Success: {success_count}")
        print(f"Failed : {fail_count}")
        print("--------------------------------------------------")

        return

    # ---------------------------------------------------------
    # NORMAL SINGLE DIGIMON MODE
    # ---------------------------------------------------------
    if not args.name:
        parser.error("name is required unless --all-digi-api or --all-profile-bin is used")

    search_name = resolve_analyzer_search_name(args.name)

    output = args.output or f"{args.name.strip().replace(' ', '_')}_analyzer.jpg"

    make_card(
        args.template,
        search_name,
        output,
        debug=args.debug,
        data_source=args.data_source,
        profile_root=Path(args.profile_root),
    )


if __name__ == "__main__":
    ANALYZER_TRACE_LOG_PATH.write_text("", encoding="utf-8")
    ANALYZER_ERROR_LOG_PATH.write_text("", encoding="utf-8")

    with open(ANALYZER_TRACE_LOG_PATH, "a", encoding="utf-8") as trace_file:
        tee_stdout = Tee(sys.__stdout__, trace_file)
        tee_stderr = Tee(sys.__stderr__, trace_file)

        try:
            with contextlib.redirect_stdout(tee_stdout), contextlib.redirect_stderr(tee_stderr):
                main()
        except Exception as e:
            log_analyzer_error("FATAL ERROR", e)
            raise
