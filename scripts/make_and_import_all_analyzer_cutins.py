#!/usr/bin/env python3
# Needs full sd folder to be pasted
# Usage: python scripts/make_and_import_all_analyzer_cutins.py
# For properly sized crops for pico terminal, use: python scripts/make_and_import_all_analyzer_cutins.py --fit crop
# For taking profile data from sd/profile folder instead of Wikimon, use:
# python scripts/make_and_import_all_analyzer_cutins.py --fit crop --data-source terminal
from pathlib import Path
import argparse
import csv
import re
import subprocess
import sys
from PIL import Image
import requests
import traceback
import contextlib
import os

def configure_windows_utf8_stdio():
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


configure_windows_utf8_stdio()

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).resolve().parent

COLS = [
    "katakana",
    "link",
    "name_web",
    "name_en",
    "skill",
    "type",
    "level",
    "attribute",
    "power",
    "attack1",
    "attack2",
    "info",
]

CUTIN_SIZE = 0xE536
BMP_MAGIC = b"BM"

# -----------------------------
# CONFIGURABLE IMAGE SETTINGS
# -----------------------------
ANALYZER_INPUT_WIDTH = 640
ANALYZER_INPUT_HEIGHT = 480

CUTIN_OUTPUT_WIDTH = 240
CUTIN_OUTPUT_HEIGHT = 240
CROP_ZOOM = 0.83

CUTIN_BACKGROUND_COLOR = (0, 0, 0)  # black

# For D3C 240x240 8-bit BMPs this should stay 0xE536.
# If you change CUTIN_OUTPUT_WIDTH/HEIGHT, the BMP size will probably change.
EXPECTED_CUTIN_SIZE = CUTIN_SIZE

DIGI_API_LIST_URL = "https://digi-api.com/api/v1/digimon?pageSize=3000"
_DIGI_API_ROWS = None
MANUAL_NAME_FIXES = {
    "holsmom": "Holsmon",
    "rapidmongold": "Rapidmon Armor",
    "rapidmonarmor": "Rapidmon Armor",
    "cherubimonvice": "Cherubimon_(Vice)",
    "cherubimonevil": "Cherubimon_(Vice)",
    "cherubimonvirtue": "Cherubimon_(Virtue)",
    "cherubimongood": "Cherubimon_(Virtue)",
    "cherubimon": "Cherubimon_(Virtue)",
    "scumon": "Scumon",
    "oukuwamon": "Okuwamon",
    "ageisdramon": "Aegisdramon",
    "fujitsumon": "Octmon",
    "agumon2006": "Agumon_(2006_Anime_Version)",
    "agumonbx": "Agumon_(Black)_(X-Antibody)",
    "agumonblack": "Agumon_(Black)",
    "agumonx": "Agumon_(X-Antibody)",
    "agumonhakase": "Agumon_Hakase",
    "algomonlv1": "Algomon_(Baby_I)",
    "algomonlv2": "Algomon_(Baby_II)",
    "ALGOMON_IN-TRAININGⅡ": "Algomon_(Baby_II)",
    "algomonlv3": "Algomon_(Child)",
    "ALGOMON_ROOKIE": "Algomon_(Child)",
    "algomonlv4": "Algomon_(Adult)",
    "ALGOMON_CHAMPION": "Algomon_(Adult)",
    "algomonultimate": "Algomon_(Ultimate)",
    "ALGOMON_MEGA": "Algomon_(Ultimate)",
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
    "aerovdramon": "Aero_V-dramon",
    "aerov-dramon": "Aero_V-dramon",
    "atlurballistamon": "Atlur_Ballistamon",
    "atlurkabuterimonblue": "Atlur_Kabuterimon_(Blue)",
    "atlurkabuterimon": "Atlur_Kabuterimon_(Red)",
    "alphamon(ouryuken)": "Alphamon:_Ouryuken",
    "alphamon ouryuken": "Alphamon:_Ouryuken",
    "agumon(burst_mode)": "Agumon:_Burst_Mode",
    "agumon burst mode": "Agumon:_Burst_Mode",
    "agunimon": "Agnimon",
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
    "belphemon(sleep_mode)": "Beelzebumon:_Sleep_Mode",
    "belphemon sleep mode": "Beelzebumon:_Sleep_Mode",
    "beelzebumon_(starmons)": "Beelzebumon_+_Starmons",
    "beelzebumon starmons": "Beelzebumon_+_Starmons",
    "beelzebumon + starmons": "Beelzebumon_+_Starmons",
    "dorulumon_(starmons)": "Dorulumon_+_Starmons",
    "dorulumon starmons": "Dorulumon_+_Starmons",
    "dorulumon + starmons": "Dorulumon_+_Starmons",
    "mail_birdramon_(golemon)": "Mail_Birdramon_+_Golemon",
    "mail birdramon golemon": "Mail_Birdramon_+_Golemon",
    "mailbirdramon golemon": "Mail_Birdramon_+_Golemon",
    "mail birdramon + golemon": "Mail_Birdramon_+_Golemon",
    "mailbirdramon + golemon": "Mail_Birdramon_+_Golemon",
    "metal_greymon_(cyber_lancher)": "Metal_Greymon_+_Cyber_Launcher",
    "metal greymon cyber lancher": "Metal_Greymon_+_Cyber_Launcher",
    "metalgreymon cyber lancher": "Metal_Greymon_+_Cyber_Launcher",
    "metal greymon + cyber lancher": "Metal_Greymon_+_Cyber_Launcher",
    "metalgreymon + cyber lancher": "Metal_Greymon_+_Cyber_Launcher",
    "shoutmon_(dorulu_cannon)": "Shoutmon_+_Dorulu_Cannon",
    "shoutmon dorulu cannon": "Shoutmon_+_Dorulu_Cannon",
    "shoutmon + dorulu cannon": "Shoutmon_+_Dorulu_Cannon",
    "shoutmon_(jet_sparrow)": "Shoutmon_+_Jet_Sparrow",
    "shoutmon jet sparrow": "Shoutmon_+_Jet_Sparrow",
    "shoutmon + jet sparrow": "Shoutmon_+_Jet_Sparrow",
    "shoutmon_(star_sword)": "Shoutmon_+_Star_Sword",
    "shoutmon star sword": "Shoutmon_+_Star_Sword",
    "shoutmon + star sword": "Shoutmon_+_Star_Sword",
    "beelzebumon_(revolmon)": "Beelzebumon_+_Revolmon",
    "beelzebumon_revolmon": "Beelzebumon_+_Revolmon",
    "beelzebumon + revolmon": "Beelzebumon_+_Revolmon",
    "bancho_leomon(burst_mode)": "Bancho_Leomon:_Burst_Mode",
    "bancho leomon burst mode": "Bancho_Leomon:_Burst_Mode",
    "belphemonx": "Belphemon_(X-Antibody)",
    "belphemonragemode": "Belphemon:_Rage_Mode",
    "betelgammamon": "Betel_Gammamon",
    "bigukkomon": "Big_Ukkomon",
    "blacktailmonuver": "Black_Tailmon_Uver.",
    "blackwargreymonx": "Black_War_Greymon_(X-Antibody)",
    "burninggreymon": "Vritramon",
    "Brakimon": "Brachimon",
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
    "cyberdramon2010": "Cyberdramon_(Xros_Wars)",
    "darkknightmon": "Dark_Knightmon",
    "darkknightmonx": "Dark_Knightmon_(X-Antibody)",
    "darknessbagramon": "Darkness_Bagramon",
    "darktyranomonx": "Dark_Tyranomon_(X-Antibody)",
    "deathxdorugamon": "Death-X-DORUgamon",
    "deathxdorugoramon": "Death-X-DORUgoramon",
    "deathxdoruguremon": "Death-X-DORUguremon",
    "deathmonblack": "Deathmon_(Black)",
    "deadlytuwarmon": "Deadly_Tuwarmon",
    "deckergreymon": "Decker_Greymon",
    "demonxantibody": "Demon_(X-Antibody)",
    "demonx": "Demon_(X-Antibody)",
    "diablomonx": "Diablomon_(X-Antibody)",
    "donedevimon": "Done_Devimon",
    "dorugreymon": "DORUguremon",
    "dracomonx": "Dracomon_(X-Antibody)",
    "dracomon_(cyberdramon)": "Dracomon_+_Cyberdramon",
    "dracomon cyberdramon": "Dracomon_+_Cyberdramon",
    "dracomon + cyberdramon": "Dracomon_+_Cyberdramon",
    "cyberdracomon": "Dracomon_+_Cyberdramon",
    "duftmonx": "Duftmon_(X-Antibody)",
    "dukemonx": "Dukemon_(X-Antibody)",
    "dukemoncrimsonmode": "Dukemon:_Crimson_Mode",
    "duftmon(leopard_mode)": "Duftmon:_Leopard_Mode",
    "duftmon leopard mode": "Duftmon:_Leopard_Mode",
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
    "gabumonyukinokizuna": "Gabumon_-Yujo_no_Kizuna-",
    "gabumonbondoffriendship": "Gabumon_-Yujo_no_Kizuna-",
    "gabumonx": "Gabumon_(X-Antibody)",
    "gankoomonx": "Gankoomon_(X-Antibody)",
    "garudamonx": "Garudamon_(X-Antibody)",
    "garurumonblack": "Garurumon_(Black)",
    "guilmonx": "Guilmon_(X-Antibody)",
    "kendogarurummon": "Garummon",
    "gizmon(at)": "Gizmon:_AT",
    "gizmon at": "Gizmon:_AT",
    "gizmon(xt)": "Gizmon:_XT",
    "gizmon xt": "Gizmon:_XT",
    "goddramonx": "Goddramon_(X-Antibody)",
    "goldvdramon": "Gold_V-dramon",
    "gomamonx": "Gomamon_(X-Antibody)",
    "gracenovamon": "Grace_Novamon",
    "granddracumon": "Grand_Dracumon",
    "grandgalemon": "Grand_Galemon",
    "great_king_sukamon": "Great_King_Scumon",
    "great king sukamon": "Great_King_Scumon",
    "greatkingsukamon": "Great_King_Scumon",
    "greyknightsmon": "Grey_Knightsmon",
    "greymonblue": "Greymon_(Blue)",
    "greymonfirst": "Greymon",
    "greymon2010": "Greymon_(2010_Anime_Version)",
    "greymon2010anime": "Greymon_(2010_Anime_Version)",
    "greymon2010animeversion": "Greymon_(2010_Anime_Version)",
    "greymonxwars": "Greymon_(2010_Anime_Version)",
    "greymonxroswars": "Greymon_(2010_Anime_Version)",
    "growmonorange": "Growmon_(Orange)",
    "growmonx": "Growmon_(X-Antibody)",
    "gulusgammamon": "Gulus_Gammamon",
    "heavyleomon": "Heavy_Leomon",
    "hicommandramon": "Hi-Commandramon",
    "hiandromon": "Hi_Andromon",
    "holydramonx": "Holydramon_(X-Antibody)",
    "holy angemon(priest mode)": "Holy_Angemon:_Priest_Mode",
    "holy angemon priest mode": "Holy_Angemon:_Priest_Mode",
    "lucemon(falldown_mode)": "Lucemon:_Falldown_Mode",
    "lucemon falldown mode": "Lucemon:_Falldown_Mode",
    "lucemon(larva)": "Lucemon:_Larva",
    "lucemon larva": "Lucemon:_Larva",
    "hououmonx": "Hououmon_(X-Antibody)",
    "hoverespimon": "Hoverespimon",
    "imperialdramondragonmode": "Imperialdramon:_Dragon_Mode",
    "imperialdramon(dragon_mode_(black))": "Imperialdramon:_Dragon_Mode_(Black)",
    "imperialdramonfightermode": "Imperialdramon:_Fighter_Mode",
    "imperialdramon(fighter_mode_(black))": "Imperialdramon:_Fighter_Mode_(Black)",
    "imperialdramonpaladinmode": "Imperialdramon:_Paladin_Mode",
    "impmonx": "Impmon_(X-Antibody)",
    "jesmonx": "Jesmon_(X-Antibody)",
    "jesmongx": "JESmon_GX",
    "justimon": "Justimon:_Blitz_Arm",
    "justimonblitzarm": "Justimon:_Blitz_Arm",
    "justimoncriticalarm": "Justimon:_Critical_Arm",
    "justimonaccelarm": "Justimon:_Accel_Arm",
    "justimonx": "Justimon_(X-Antibody)",
    "jagerloweemon": "kaiserleomon",
    "kausgammamon": "Kaus_Gammamon",
    "keramonx": "Keramon_(X-Antibody)",
    "kokuwamonx": "Kokuwamon_(X-Antibody)",
    "kodokugumon": "Kodokugumon_Child",
    "kuwagamonx": "Kuwagamon_(X-Antibody)",
    "kuzuhamonmiko": "Kuzuhamon:_Miko_Mode",
    "ladydevimonx": "Lady_Devimon_(X-Antibody)",
    "leomonx": "Leomon_(X-Antibody)",
    "LOADERLIOMON": "Loader_Leomon",
    "loaderliomon": "Loader_Leomon",
    "loaderleomon": "Loader_Leomon",
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
    "metalgreymonx": "Metal_Greymon_(X-Antibody)",
    "metalmamemonx": "Metal_Mamemon_(X-Antibody)",
    "metalgreymonvix": "Metal_Greymon_(Virus)_(X-Antibody)",
    "metalgreymonweb": "Metal_Greymon_(Virus)",
    "metallifekuwagamon": "Metallife_Kuwagamon",
    "metaltyranomonx": "Metal_Tyranomon_(X-Antibody)",
    "agumonkizuna": "Agumon_-Yuki_no_Kizuna-",
    "agumon_yuki_no_kizuna": "Agumon_-Yuki_no_Kizuna-",
    "Agumon_Yuki_no_Kizuna": "Agumon_-Yuki_no_Kizuna-",
    "Agumon Yuki no Kizuna": "Agumon_-Yuki_no_Kizuna-",
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
    "rasenmonf": "Rasenmon:_Fury_Mode",
    "ravmonburstmode": "Ravmon:_Burst_Mode",
    "redvegimon": "Red_Vegimon",
    "redvagimon": "Red_Vegimon",
    "renamonx": "Renamon_(X-Antibody)",
    "renammon": "Renamon",
    "renamon": "Renamon",
    "Cernumon": "Cernumon",
    "Fukamon": "Fukamon",
    "Kakamon": "Kakamon",
    "Fujamon": "Fujamon",
    "Rasenmon_Fury_Mode": "Rasenmon:_Fury_Mode",
    "Rasenmon Fury Mode": "Rasenmon:_Fury_Mode",
    "rasenmonfurymode": "Rasenmon:_Fury_Mode",
    "pukummon": "Pukumon",
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
    "sleipmon(burst_mode)": "Sleipmon:_Burst_Mode",
    "sleipmon burst mode": "Sleipmon:_Burst_Mode",
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
    "Shoutmon_X7(Superior_Mode)": "Shoutmon_X7:_Superior_Mode",
    "shoutmon_x7(superior_mode)": "Shoutmon_X7:_Superior_Mode",
    "shoutmon x7 superior mode": "Shoutmon_X7:_Superior_Mode",
    "shoutmonx7superiormode": "Shoutmon_X7:_Superior_Mode",
    "shine_greymon(ruin_mode)": "Shine_Greymon:_Ruin_Mode",
    "shine greymon ruin mode": "Shine_Greymon:_Ruin_Mode",
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
    "Takutoumon:wrathmode": "Takutoumon:_Wrath_Mode",
    "taowumon": "Taomon",
    "terriermonx": "Terriermon_(X-Antibody)",
    "teslajellymon": "Tesla_Jellymon",
    "togemonx": "Togemon_(X-Antibody)",
    "triceramonx": "Triceramon_(X-Antibody)",
    "tylomonx": "Tylomon_(X-Antibody)",
    "tyranomonx": "Tyranomon_(X-Antibody)",
    "ulforcevdramonx": "Ulforce_V-dramon_(X-Antibody)",
    "ulforceveedramonfuturemode": "Ulforce_V-dramon_Future_Mode",
    "ulforceveedramonfuturemode": "Ulforce_V-dramon_Future_Mode",
    "ultimatebrakimon": "Ultimate_Brachimon",
    "vdramon": "V-dramon",
    "vamdemonx": "Vamdemon_(X-Antibody)",
    "Vemmon": "BEMmon",
    "waregarurumonsagittarius": "Were_Garurumon:_Sagittarius_Mode",
    "Waregarurumon:Sagittarius Mode": "Were_Garurumon:_Sagittarius_Mode",
    "Waregarurumon:SagittariusMode": "Were_Garurumon:_Sagittarius_Mode",
    "WaregarurumonSagittariusMode": "Were_Garurumon:_Sagittarius_Mode",
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
    "yatagaramon2006": "Yatagaramon_(2006_Anime_Version)",
    "yatagaramon2006anime": "Yatagaramon_(2006_Anime_Version)",
    "yatagaramon2006animeversion": "Yatagaramon_(2006_Anime_Version)",
    "yatagaramon2006version": "Yatagaramon_(2006_Anime_Version)",
    "yatagaramonsavers": "Yatagaramon_(2006_Anime_Version)",
}

TRACE_LOG_PATH = Path("trace.log")
ERROR_LOG_PATH = Path("error.log")


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


def log_error(message="", exc=None):
    with open(ERROR_LOG_PATH, "a", encoding="utf-8") as f:
        if message:
            f.write(message + "\n")

        if exc is not None:
            traceback.print_exception(type(exc), exc, exc.__traceback__, file=f)

        f.write("\n")

def safe_digimon_name_match_score(input_key: str, api_key: str) -> int:
    """
    Prevent bad short substring matches like:
        Okuwamon -> Amon

    Exact matches still win.
    Longer partial matches are still allowed for names like:
        Imperialdramon Paladin Mode -> Imperialdramon(Paladin Mode)
    """
    if not input_key or not api_key:
        return -1

    if api_key == input_key:
        return 10000

    # Never allow tiny names like "amon" to match inside longer names like "okuwamon".
    if len(input_key) < 5 or len(api_key) < 5:
        return -1

    if input_key in api_key:
        coverage = len(input_key) / max(1, len(api_key))
        if len(input_key) >= 6 and coverage >= 0.65:
            return 8000 + len(input_key)

    if api_key in input_key:
        coverage = len(api_key) / max(1, len(input_key))
        if len(api_key) >= 6 and coverage >= 0.75:
            return 7000 + len(api_key)

    return -1

def normalize_api_name(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())

def get_digi_api_rows():
    global _DIGI_API_ROWS
    if _DIGI_API_ROWS is not None:
        return _DIGI_API_ROWS

    try:
        r = requests.get(DIGI_API_LIST_URL, timeout=30)
        r.raise_for_status()
        data = r.json()
        _DIGI_API_ROWS = data.get("content", [])
        return _DIGI_API_ROWS

    except Exception as e:
        # Important:
        # Digi-API is only used to improve name matching.
        # If it fails on Windows, do NOT kill the whole import process.
        _DIGI_API_ROWS = []

        try:
            log_error("WARNING: Could not load Digi-API list. Falling back to local/manual names.", e)
        except Exception:
            pass

        return []

def resolve_analyzer_search_name(raw_name):
    original = str(raw_name).strip()

    manual_key = normalize_api_name(original)
    if manual_key in MANUAL_NAME_FIXES:
        return MANUAL_NAME_FIXES[manual_key]

    candidates = []

    # Original
    candidates.append(original)

    # Common cleanup variants
    candidates.append(original.replace(":", " "))
    candidates.append(original.replace(":", " Mode "))
    candidates.append(original.replace("-", ""))
    candidates.append(original.replace("-", " "))
    candidates.append(original.replace(":", " ").replace("-", " "))

    # Split glued "mode" names:
    # Dragonmode -> Dragon Mode
    # Fightermode -> Fighter Mode
    # Paladinmode -> Paladin Mode
    candidates += [
        re.sub(r"([A-Za-z]+)mode\b", r"\1 Mode", c, flags=re.I)
        for c in list(candidates)
    ]

    # Deduplicate
    seen = set()
    clean_candidates = []
    for c in candidates:
        c = re.sub(r"\s+", " ", c).strip()
        key = normalize_api_name(c)
        if key and key not in seen:
            seen.add(key)
            clean_candidates.append(c)

    api_rows = get_digi_api_rows()
    if not api_rows:
        return original

    best_name = original
    best_score = -1

    for candidate in clean_candidates:
        ckey = normalize_api_name(candidate)

        for row in api_rows:
            api_name = str(row.get("name", ""))
            akey = normalize_api_name(api_name)

            if not akey:
                continue

            score = safe_digimon_name_match_score(ckey, akey)

            if score > best_score:
                best_score = score
                best_name = api_name

    # Digi-API uses names like Imperialdramon(Dragon Mode).
    # Your analyzer/Wikimon script usually works better with spaces.
    best_name = best_name.replace("(", " ").replace(")", " ")
    best_name = re.sub(r"\s+", " ", best_name).strip()

    return best_name

def safe_name(name):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(name).strip())


def export_to_csv(data_path, csv_path):
    rows = []

    for line in Path(data_path).read_text(encoding="utf-8").splitlines():
        row = line.split("\t")
        while len(row) < len(COLS):
            row.append("")
        rows.append(row[:len(COLS)])

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(COLS)
        writer.writerows(rows)

    print(f"Exported {data_path} -> {csv_path}")
    return rows


def choose_digimon_name(row):
    # Prefer the cleaned English/web names.
    for col in ["name_web", "name_en", "link", "katakana"]:
        value = row.get(col, "").strip()
        if value:
            return value
    return ""


def run_analyzer(
    script,
    digimon_name,
    template,
    jpg_out,
    debug=False,
    data_source="wikimon",
    profile_root="sd/profile",
):
    cmd = [
        sys.executable,
        str(script),
        digimon_name,
        "--template",
        str(template),
        "--output",
        str(jpg_out),
        "--data-source",
        str(data_source),
        "--profile-root",
        str(profile_root),
    ]

    if debug:
        cmd.append("--debug")

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    result = subprocess.run(
        cmd,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )

    if result.returncode == 0:
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)

    if result.returncode != 0:
        with open(ERROR_LOG_PATH, "a", encoding="utf-8") as f:
            f.write("Command failed:\n")
            f.write(" ".join(cmd) + "\n\n")
            if result.stdout:
                f.write("STDOUT:\n")
                f.write(result.stdout + "\n")
            if result.stderr:
                f.write("STDERR / TRACEBACK:\n")
                f.write(result.stderr + "\n")
            f.write("\n")

        raise subprocess.CalledProcessError(
            result.returncode,
            cmd,
            output=result.stdout,
            stderr=result.stderr,
        )


def convert_jpg_to_d3c_bmp(jpg_path, bmp_path, fit="pad"):
    img = Image.open(jpg_path).convert("RGB")

    # Optional safety resize if analyzer output is not the expected size.
    if img.size != (ANALYZER_INPUT_WIDTH, ANALYZER_INPUT_HEIGHT):
        img = img.resize(
            (ANALYZER_INPUT_WIDTH, ANALYZER_INPUT_HEIGHT),
            Image.Resampling.LANCZOS,
        )

    out_size = (CUTIN_OUTPUT_WIDTH, CUTIN_OUTPUT_HEIGHT)

    if fit == "stretch":
        img = img.resize(out_size, Image.Resampling.LANCZOS)

    elif fit == "crop":
        w, h = img.size
        target_w, target_h = out_size

        source_ratio = w / h
        target_ratio = target_w / target_h

        if source_ratio > target_ratio:
            new_w = int(h * target_ratio)
            new_h = h
        else:
            new_w = w
            new_h = int(w / target_ratio)

        # Lower CROP_ZOOM = show more of the original image.
        # 1.00 = current crop behavior.
        # 0.85 = slightly wider / more visible.
        # 0.75 = even more visible.
        new_w = int(new_w / CROP_ZOOM)
        new_h = int(new_h / CROP_ZOOM)

        new_w = min(new_w, w)
        new_h = min(new_h, h)

        left = (w - new_w) // 2
        top = (h - new_h) // 2

        img = img.crop((left, top, left + new_w, top + new_h))
        img = img.resize(out_size, Image.Resampling.LANCZOS)

    else:
        # pad mode: keep full analyzer visible.
        img.thumbnail(out_size, Image.Resampling.LANCZOS)

        canvas = Image.new("RGB", out_size, CUTIN_BACKGROUND_COLOR)

        x = (CUTIN_OUTPUT_WIDTH - img.width) // 2
        y = (CUTIN_OUTPUT_HEIGHT - img.height) // 2

        canvas.paste(img, (x, y))
        img = canvas

    img = img.convert("P", palette=Image.Palette.ADAPTIVE, colors=256)
    img.save(bmp_path, "BMP")

    data = bmp_path.read_bytes()

    if data[:2] != BMP_MAGIC:
        raise RuntimeError(f"{bmp_path} does not start with BMP magic.")

    if len(data) != EXPECTED_CUTIN_SIZE:
        raise RuntimeError(
            f"{bmp_path} has wrong size: 0x{len(data):X}. "
            f"Expected 0x{EXPECTED_CUTIN_SIZE:X}.\n"
            f"Your configured output size is "
            f"{CUTIN_OUTPUT_WIDTH}x{CUTIN_OUTPUT_HEIGHT}."
        )

def load_csv_rows(csv_path):
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def process_table(
    label,
    csv_path,
    bin_path,
    out_bin_path,
    analyzer_script,
    template,
    workdir,
    fit,
    debug=False,
    start=None,
    end=None,
    skip_existing=False,
    data_source="wikimon",
    profile_root="sd/profile",
):
    rows = load_csv_rows(csv_path)
    original = bytearray(Path(bin_path).read_bytes())

    if len(original) % CUTIN_SIZE != 0:
        raise RuntimeError(f"{bin_path} is not a valid D3C cut-in bin.")

    bin_slots = len(original) // CUTIN_SIZE

    print()
    print("=" * 60)
    print(f"Processing {label}")
    print(f"CSV rows: {len(rows)}")
    print(f"BIN slots: {bin_slots}")
    print("=" * 60)

    if len(rows) > bin_slots:
        print(f"WARNING: CSV has {len(rows)} rows but BIN only has {bin_slots} slots.")
        print("Extra CSV rows will be skipped.")

    table_workdir = workdir / label
    jpg_dir = table_workdir / "jpg"
    bmp_dir = table_workdir / "bmp"
    jpg_dir.mkdir(parents=True, exist_ok=True)
    bmp_dir.mkdir(parents=True, exist_ok=True)

    changed = 0
    failed = []

    max_i = min(len(rows), bin_slots)

    if start is None:
        start = 0
    if end is None or end > max_i:
        end = max_i

    for slot_id in range(start, end):
        row = rows[slot_id]
        digimon_name = choose_digimon_name(row)
        
        if not digimon_name:
            print(f"[{label} {slot_id:03d}] SKIP: empty name")
            continue

        search_name = digimon_name

        try:
            search_name = resolve_analyzer_search_name(digimon_name)

            base = safe_name(digimon_name)
            jpg_out = jpg_dir / f"{label}_{slot_id:03d}_{base}.jpg"
            bmp_out = bmp_dir / f"{label}_{slot_id:03d}_{base}.bmp"

            print(f"[{label} {slot_id:03d}] {digimon_name} -> {search_name}")

            if skip_existing and bmp_out.exists():
                print("  using existing BMP")
            else:
                run_analyzer(
                    analyzer_script,
                    search_name,
                    template,
                    jpg_out,
                    debug=debug,
                    data_source=data_source,
                    profile_root=profile_root,
                )
                convert_jpg_to_d3c_bmp(jpg_out, bmp_out, fit=fit)

            bmp = bmp_out.read_bytes()

            if len(bmp) != CUTIN_SIZE:
                raise RuntimeError(f"BMP size mismatch for {bmp_out}")

            start_off = slot_id * CUTIN_SIZE
            original[start_off:start_off + CUTIN_SIZE] = bmp
            changed += 1

        except Exception as e:
            print(f"  FAILED: {e}")

            log_error(
                message=f"[{label} {slot_id:03d}] {digimon_name} -> {search_name}",
                exc=e,
            )

            failed.append((slot_id, digimon_name, str(e)))
            continue

    Path(out_bin_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_bin_path).write_bytes(original)

    print()
    print(f"{label} done.")
    print(f"Imported cut-ins: {changed}")
    print(f"Saved patched BIN: {out_bin_path}")

    if failed:
        fail_csv = table_workdir / f"{label}_failed.csv"
        with open(fail_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["slot", "name", "error"])
            writer.writerows(failed)

        print(f"Failures: {len(failed)}")
        print(f"Failure log: {fail_csv}")

    return changed, failed

def data_sort_key(path: Path):
    try:
        return int(path.stem)
    except ValueError:
        return path.stem.lower()


def load_data_rows(data_path: Path):
    rows = []
    for line in data_path.read_text(encoding="utf-8").splitlines():
        cols = line.split("\t")
        while len(cols) < len(COLS):
            cols.append("")
        rows.append(dict(zip(COLS, cols[:len(COLS)])))
    return rows


def find_device_pairs(device: str):
    data_root = Path("sd/data") / device
    cutin_root = Path("sd/gfx/cutin") / device

    if not data_root.exists():
        raise RuntimeError(f"Missing data folder: {data_root}")

    if not cutin_root.exists():
        raise RuntimeError(f"Missing cutin folder: {cutin_root}")

    data_files = sorted(data_root.glob("*.data"), key=data_sort_key)

    pairs = []

    for data_path in data_files:
        bin_path = cutin_root / f"{data_path.stem}.bin"

        if not bin_path.exists():
            print(f"SKIP: no matching cutin bin for {data_path}")
            continue

        pairs.append((data_path.stem, data_path, bin_path))

    return pairs


def process_device_file(
    device,
    label,
    data_path,
    bin_path,
    out_bin_path,
    analyzer_script,
    template,
    workdir,
    fit,
    debug=False,
    start=None,
    end=None,
    skip_existing=False,
    data_source="wikimon",
    profile_root="sd/profile",
):
    rows = load_data_rows(data_path)
    original = bytearray(Path(bin_path).read_bytes())

    if len(original) % CUTIN_SIZE != 0:
        raise RuntimeError(
            f"{bin_path} is not a valid cut-in bin. "
            f"Size 0x{len(original):X} is not divisible by 0x{CUTIN_SIZE:X}."
        )

    bin_slots = len(original) // CUTIN_SIZE

    print()
    print("=" * 60)
    print(f"Processing {device}/{label}")
    print(f"DATA rows: {len(rows)}")
    print(f"BIN slots: {bin_slots}")
    print("=" * 60)

    table_workdir = workdir / device / label
    jpg_dir = table_workdir / "jpg"
    bmp_dir = table_workdir / "bmp"
    jpg_dir.mkdir(parents=True, exist_ok=True)
    bmp_dir.mkdir(parents=True, exist_ok=True)

    changed = 0
    failed = []

    max_i = min(len(rows), bin_slots)

    if start is None:
        start = 0
    if end is None or end > max_i:
        end = max_i

    for slot_id in range(start, end):
        row = rows[slot_id]
        digimon_name = choose_digimon_name(row)

        if not digimon_name:
            print(f"[{device}/{label} {slot_id:03d}] SKIP: empty name")
            continue

        search_name = digimon_name

        try:
            search_name = resolve_analyzer_search_name(digimon_name)

            base = safe_name(digimon_name)
            jpg_out = jpg_dir / f"{label}_{slot_id:03d}_{base}.jpg"
            bmp_out = bmp_dir / f"{label}_{slot_id:03d}_{base}.bmp"

            print(f"[{device}/{label} {slot_id:03d}] {digimon_name} -> {search_name}")

            if skip_existing and bmp_out.exists():
                print("  using existing BMP")
            else:
                run_analyzer(
                    analyzer_script,
                    search_name,
                    template,
                    jpg_out,
                    debug=debug,
                    data_source=data_source,
                    profile_root=profile_root,
                )

                convert_jpg_to_d3c_bmp(jpg_out, bmp_out, fit=fit)

            bmp = bmp_out.read_bytes()

            if len(bmp) != CUTIN_SIZE:
                raise RuntimeError(f"BMP size mismatch for {bmp_out}")

            start_off = slot_id * CUTIN_SIZE
            original[start_off:start_off + CUTIN_SIZE] = bmp
            changed += 1

        except Exception as e:
            print(f"  FAILED: {e}")

            log_error(
                message=f"[{device}/{label} {slot_id:03d}] {digimon_name} -> {search_name}",
                exc=e,
            )

            failed.append((device, label, slot_id, digimon_name, str(e)))
            continue

    out_bin_path.parent.mkdir(parents=True, exist_ok=True)
    out_bin_path.write_bytes(original)

    print()
    print(f"{device}/{label} done.")
    print(f"Imported cut-ins: {changed}")
    print(f"Saved patched BIN: {out_bin_path}")

    if failed:
        fail_csv = table_workdir / f"{label}_failed.csv"
        with open(fail_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["device", "file", "slot", "name", "error"])
            writer.writerows(failed)

        print(f"Failures: {len(failed)}")
        print(f"Failure log: {fail_csv}")

    return changed, failed


def process_device(
    device,
    analyzer_script,
    template,
    workdir,
    fit,
    debug=False,
    start=None,
    end=None,
    skip_existing=False,
    data_source="wikimon",
    profile_root="sd/profile",
    out_root=None,
):
    pairs = find_device_pairs(device)

    if not pairs:
        raise RuntimeError(f"No matching .data/.bin pairs found for device: {device}")

    all_failed = []

    for label, data_path, bin_path in pairs:
        if out_root:
            out_bin_path = Path(out_root) / device / f"{label}.bin"
        else:
            out_bin_path = bin_path

        _, failed = process_device_file(
            device=device,
            label=label,
            data_path=data_path,
            bin_path=bin_path,
            out_bin_path=out_bin_path,
            analyzer_script=analyzer_script,
            template=template,
            workdir=workdir,
            fit=fit,
            debug=debug,
            start=start,
            end=end,
            skip_existing=skip_existing,
            data_source=data_source,
            profile_root=profile_root,
        )

        all_failed.extend(failed)

    return all_failed

def get_project_root() -> Path:
    if getattr(sys, "frozen", False):
        exe_path = Path(sys.executable).resolve()

        # macOS .app:
        # YourApp.app/Contents/MacOS/YourExecutable
        # We want the folder containing YourApp.app, where your sd folder lives.
        if sys.platform == "darwin" and ".app" in str(exe_path):
            return exe_path.parents[3]

        # Windows/Linux onefile/onedir:
        # use folder beside the exe.
        return exe_path.parent

    # Normal python scripts:
    # scripts/make_and_import_all_analyzer_cutins.py -> project root
    return Path(__file__).resolve().parent.parent


def main():
    PROJECT_ROOT = get_project_root()
    import os
    os.chdir(PROJECT_ROOT)
    
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--analyzer-script",
        default=str(BASE_DIR / "make_digimon_analyzer_images.py"),
    )

    parser.add_argument(
        "--template",
        default=str(BASE_DIR / "Digimon_analyzer_blank.jpg"),
    )

    parser.add_argument("--device", default="d3c")
    parser.add_argument(
        "--all-devices",
        action="store_true",
        help="Process all device folders under sd/data that also exist under sd/gfx/cutin",
    )

    parser.add_argument(
        "--workdir",
        default=str(PROJECT_ROOT / "generated_analyzer_cutins"),
    )
    parser.add_argument("--out-root", default=None)

    parser.add_argument("--fit", choices=["pad", "stretch", "crop"], default="pad")

    parser.add_argument("--start", type=int, default=None)
    parser.add_argument("--end", type=int, default=None)

    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--debug", action="store_true")

    parser.add_argument("--data-source", choices=["wikimon", "terminal"], default="terminal")
    parser.add_argument(
        "--profile-root",
        default=str(PROJECT_ROOT / "sd" / "profile"),
    )

    args = parser.parse_args()

    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    if args.all_devices:
        data_root = PROJECT_ROOT / "sd" / "data"
        cutin_root = PROJECT_ROOT / "sd" / "gfx" / "cutin"

        devices = []
        for folder in sorted(data_root.iterdir(), key=lambda p: p.name.lower()):
            if folder.is_dir() and (cutin_root / folder.name).exists():
                devices.append(folder.name)
    else:
        devices = [args.device]

    all_failed = []

    for device in devices:
        failed = process_device(
            device=device,
            analyzer_script=args.analyzer_script,
            template=args.template,
            workdir=workdir,
            fit=args.fit,
            debug=args.debug,
            start=args.start,
            end=args.end,
            skip_existing=args.skip_existing,
            data_source=args.data_source,
            profile_root=args.profile_root,
            out_root=args.out_root,
        )

        all_failed.extend(failed)

    print()
    print("=" * 60)
    print("MASTER PROCESS COMPLETE")
    print("=" * 60)

    if all_failed:
        print(f"Total failures: {len(all_failed)}")
        print("Check failed CSV files inside the workdir.")
    else:
        print("No failures.")

if __name__ == "__main__":
    TRACE_LOG_PATH.write_text("", encoding="utf-8")
    ERROR_LOG_PATH.write_text("", encoding="utf-8")

    with open(TRACE_LOG_PATH, "a", encoding="utf-8") as trace_file:
        tee_stdout = Tee(sys.__stdout__, trace_file)
        tee_stderr = Tee(sys.__stderr__, trace_file)

        try:
            with contextlib.redirect_stdout(tee_stdout), contextlib.redirect_stderr(tee_stderr):
                main()
        except Exception as e:
            log_error("FATAL ERROR", e)
            raise