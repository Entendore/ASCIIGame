"""
ASCII FPS: NEON PROTOCOL - ENHANCED EDITION v7
A first-person shooter rendered entirely in ASCII art.
Built with PySide6. Uses raycasting for 3D walls and sprite projection.

v7 Cyberpunk/Sci-Fi Overhaul:
- Re-themed entirely to a Cyberpunk/Sci-Fi setting (replaces DOOM theme)
- 6 Enemy Types: Drone, Android, Turret, Mech (Boss), Spider-bot, Cyborg
- 3 Weapons: Laser Pistol, Plasma Shotgun, Railgun
- Pickups: Repair Kits, Energy Cells, EMP Grenades
- Power-ups: Overclock, Stim, Rage, Cloak
- Glitch/Static damage effects instead of blood
- Cybernetic HUD elements and neon color palette
- All previous features retained (massive sprites, multi-story buildings, slow-mo, etc.)
"""

import sys
import math
import time
import random
import json
import os
from typing import List, Set, Tuple, Optional, Dict

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor, QFont, QFontMetrics, QKeyEvent
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget

# ======================== SOUND ENGINE (8-BIT) ========================
try:
    import pygame
    import numpy as np
    from pygame import sndarray
    PYGAME_OK = True
except ImportError:
    PYGAME_OK = False

class SoundManager:
    def __init__(self):
        self.enabled = False
        if not PYGAME_OK:
            print("Pygame/Numpy not found. Running without sound.")
            return
        try:
            pygame.mixer.pre_init(22050, -16, 1, 256)
            pygame.mixer.init()
            self.enabled = True
        except Exception as e:
            print(f"Audio init failed: {e}. Running without sound.")
            return
            
        self.sounds = {}
        self.sounds['shoot_laser'] = self._gen_sweep(800, 200, 0.1, 'square', 0.4)
        self.sounds['shoot_plasma'] = self._gen_noise(0.15, 0.5, decay=10)
        self.sounds['shoot_railgun'] = self._gen_sweep(1200, 400, 0.05, 'sawtooth', 0.3)
        self.sounds['enemy_hit'] = self._gen_sweep(1200, 1600, 0.05, 'sine', 0.3)
        self.sounds['enemy_die'] = self._gen_sweep(400, 50, 0.3, 'sawtooth', 0.4)
        self.sounds['player_hit'] = self._gen_sweep(200, 80, 0.2, 'sawtooth', 0.4)
        self.sounds['pickup'] = self._gen_arpeggio([523, 659, 784], 0.05, 'square', 0.3)
        self.sounds['explode'] = self._gen_explosion(0.5, 0.6)
        self.sounds['game_over'] = self._gen_arpeggio([392, 330, 261, 196], 0.2, 'triangle', 0.4)
        self.sounds['victory'] = self._gen_arpeggio([261, 329, 392, 523], 0.1, 'square', 0.4)
        self.sounds['menu_move'] = self._gen_wave(600, 0.03, 'sine', 0.2)
        self.sounds['menu_select'] = self._gen_sweep(400, 800, 0.1, 'square', 0.3)
        self.sounds['dry_fire'] = self._gen_sweep(200, 100, 0.05, 'sawtooth', 0.2)
        self.sounds['enemy_shoot'] = self._gen_sweep(300, 200, 0.1, 'sawtooth', 0.2)
        self.sounds['wall_hit'] = self._gen_noise(0.05, 0.2, decay=20)
        self.sounds['switch'] = self._gen_arpeggio([400, 600], 0.03, 'square', 0.2)
        self.sounds['pause'] = self._gen_wave(400, 0.1, 'sine', 0.2)
        self.sounds['grenade_throw'] = self._gen_sweep(200, 600, 0.15, 'square', 0.3)
        self.sounds['grenade_bounce'] = self._gen_wave(300, 0.05, 'sine', 0.2)
        self.sounds['powerup_pickup'] = self._gen_arpeggio([523, 659, 784, 1046], 0.08, 'square', 0.4)
        self.sounds['hit_marker'] = self._gen_wave(1200, 0.04, 'square', 0.25)
        self.sounds['footstep'] = self._gen_noise(0.04, 0.15, decay=30)
        self.sounds['adrenaline'] = self._gen_sweep(100, 800, 0.3, 'sawtooth', 0.4)
        self.sounds['achievement'] = self._gen_arpeggio([523, 659, 784, 1046, 1318], 0.1, 'triangle', 0.4)
        self.sounds['regen'] = self._gen_wave(800, 0.1, 'sine', 0.15)
        self.sounds['boss_spawn'] = self._gen_sweep(100, 50, 0.8, 'sawtooth', 0.5)
        self.sounds['boss_hit'] = self._gen_sweep(150, 80, 0.15, 'sawtooth', 0.4)
        self.sounds['crit'] = self._gen_arpeggio([800, 1200, 1600], 0.04, 'square', 0.35)
        self.sounds['ambient1'] = self._gen_sweep(80, 60, 0.5, 'sine', 0.15)
        self.sounds['ambient2'] = self._gen_wave(120, 0.3, 'sine', 0.1)

    def _make_sound(self, wave):
        audio = np.int16(wave * 32767)
        audio = np.ascontiguousarray(audio.reshape(-1, 1))
        return sndarray.make_sound(audio)

    def _gen_wave(self, freq, dur, wave_type='sine', vol=0.2):
        sr = 22050
        t = np.linspace(0, dur, int(sr * dur), False)
        if wave_type == 'square': wave = np.sign(np.sin(2 * np.pi * freq * t))
        elif wave_type == 'sawtooth': wave = 2 * (t * freq - np.floor(0.5 + t * freq))
        elif wave_type == 'sine': wave = np.sin(2 * np.pi * freq * t)
        elif wave_type == 'triangle': wave = 2 * np.abs(2 * (t * freq - np.floor(0.5 + t * freq))) - 1
        else: wave = np.sin(2 * np.pi * freq * t)
        env = np.exp(-4 * t)
        return self._make_sound(wave * env * vol)

    def _gen_sweep(self, f_start, f_end, dur, wave_type='square', vol=0.5):
        sr = 22050
        t = np.linspace(0, dur, int(sr * dur), False)
        freq = np.linspace(f_start, f_end, len(t))
        phase = 2 * np.pi * np.cumsum(freq) / sr
        if wave_type == 'square': wave = np.sign(np.sin(phase))
        elif wave_type == 'sawtooth': wave = 2 * (phase / (2*np.pi) - np.floor(0.5 + phase / (2*np.pi)))
        else: wave = np.sin(phase)
        env = np.exp(-4 * t)
        return self._make_sound(wave * env * vol)

    def _gen_noise(self, dur, vol=0.5, decay=6):
        sr = 22050
        t = np.linspace(0, dur, int(sr * dur), False)
        wave = np.random.uniform(-1, 1, len(t))
        alpha = 0.2
        for i in range(1, len(wave)): wave[i] = alpha * wave[i] + (1 - alpha) * wave[i-1]
        env = np.exp(-decay * t)
        return self._make_sound(wave * env * vol)

    def _gen_explosion(self, dur, vol=0.6):
        sr = 22050
        t = np.linspace(0, dur, int(sr * dur), False)
        noise = np.random.uniform(-1, 1, len(t))
        alpha = 0.05
        for i in range(1, len(noise)): noise[i] = alpha * noise[i] + (1 - alpha) * noise[i-1]
        sine = np.sin(2 * np.pi * (80 * np.exp(-3*t)) * t)
        wave = noise * 0.6 + sine * 0.4
        env = np.exp(-2 * t)
        return self._make_sound(wave * env * vol)

    def _gen_arpeggio(self, freqs, dur, wave_type='square', vol=0.4):
        sr = 22050
        total_dur = dur * len(freqs)
        t = np.linspace(0, total_dur, int(sr * total_dur), False)
        wave = np.zeros(len(t))
        for i, f in enumerate(freqs):
            t_slice = np.linspace(0, dur, int(sr * dur), False)
            if wave_type == 'square': w = np.sign(np.sin(2 * np.pi * f * t_slice))
            elif wave_type == 'triangle': w = 2 * np.abs(2 * (t_slice * f - np.floor(0.5 + t_slice * f))) - 1
            else: w = np.sin(2 * np.pi * f * t_slice)
            wave[i*int(sr*dur) : (i+1)*int(sr*dur)] = w
        env = np.exp(-2 * t)
        return self._make_sound(wave * env * vol)

    def play(self, name):
        if not self.enabled or name not in self.sounds: return
        try: self.sounds[name].play()
        except Exception: pass


# ======================== HIGH SCORE PERSISTENCE ========================
HIGHSCORE_FILE = "ascii_fps_scores.json"

def load_highscores() -> Dict[str, int]:
    try:
        with open(HIGHSCORE_FILE, 'r') as f: return json.load(f)
    except Exception: return {}

def save_highscore(difficulty: str, score: int) -> bool:
    scores = load_highscores()
    if score > scores.get(difficulty, 0):
        scores[difficulty] = score
        try:
            with open(HIGHSCORE_FILE, 'w') as f: json.dump(scores, f)
        except Exception: pass
        return True
    return False


# ======================== CONFIGURATION ========================
COLS = 120
ROWS = 44
HUD_ROWS = 8
VIEW_ROWS = ROWS - HUD_ROWS

FOV = math.pi / 3
HALF_FOV = FOV / 2
MAX_DEPTH = 40
TEXTURE_SCALE = 3.0

CEILING_COLOR = QColor(10, 10, 30)
FLOOR_COLOR = QColor(40, 40, 50)
HUD_COLOR = QColor(80, 200, 255) # Neon Cyan
HUD_BG = QColor(12, 12, 12)

SKY_TINTS = [
    ((5, 5, 15), "NIGHT"),
    ((15, 12, 30), "DUSK"),
    ((8, 15, 35), "PRE-DAWN"),
    ((20, 8, 30), "BLOOD MOON"),
    ((12, 18, 25), "ALIEN"),
]


# ======================== WEAPONS (Massive 22-Line Sprites) ========================
WEAPONS = {
    'laser': {
        'name': 'LASER PISTOL', 'damage': 1, 'fire_rate': 0.18,
        'pellets': 1, 'spread': 0.02, 'ammo_per_shot': 1,
        'range': 25, 'recoil': 1.0, 'crit_chance': 0.15,
    },
    'plasma': {
        'name': 'PLASMA SHOTGUN', 'damage': 1, 'fire_rate': 0.7,
        'pellets': 6, 'spread': 0.18, 'ammo_per_shot': 1,
        'range': 14, 'recoil': 2.0, 'crit_chance': 0.05,
    },
    'railgun': {
        'name': 'RAILGUN', 'damage': 1, 'fire_rate': 0.07,
        'pellets': 1, 'spread': 0.08, 'ammo_per_shot': 1,
        'range': 20, 'recoil': 0.7, 'crit_chance': 0.1,
    },
}
WEAPON_ORDER = ['laser', 'plasma', 'railgun']

WEAPON_SPRITES = {
    'laser': [
        "                       __          ",
        "                     /    \\        ",
        "                    |      |       ",
        "                     \\    /        ",
        "                      |  |         ",
        "                      |  |         ",
        "                      |  |         ",
        "                      |  |         ",
        "                      |  |         ",
        "                      |  |         ",
        "                      |  |         ",
        "                      |  |         ",
        "                    __|  |         ",
        "                   /  |  |         ",
        "                  /___|  |         ",
        "                 //___|__|_______ ",
        "                ====__|__|_______|",
        "               +=====+ |  |       ",
        "              +======+ |  |       ",
        "             +=======+ |  |       ",
        "            +========+ |  |       ",
        "           +=========+ |__|       "
    ],
    'plasma': [
        "             __________________  ",
        "            |__________________| ",
        "            |                  \\",
        "            |                   \\",
        "            |                    |",
        "            |                    |",
        "            |                    |",
        "            |                    |",
        "            |                    |",
        "            |                    |",
        "            |                    |",
        "            |                    |",
        "            |                    |",
        "            |                    |",
        "            |                    |",
        "            |                    |",
        "          __|                    |",
        "         /  |                    |",
        "        /___|____________________|",
        "        |___|____________________|",
        "            |                    |",
        "            |____________________|"
    ],
    'railgun': [
        "             ___________     ",
        "            |  ___O_  |     ",
        "            | | o o | |     ",
        "            | | o o | |     ",
        "            | | o o | |     ",
        "            | | o o | |     ",
        "            | | o o | |     ",
        "            | |__O__| |     ",
        "            |         |     ",
        "            |         |     ",
        "            |         |     ",
        "            |         |     ",
        "            |         |     ",
        "            |         |     ",
        "            |         |     ",
        "            |         |     ",
        "          __|         |     ",
        "         /  |         |     ",
        "        /___|_________|_____",
        "        |___|_________|_____|",
        "            |         |     ",
        "            |_________|     "
    ],
}

def pad_sprite(sprite):
    w = max(len(row) for row in sprite)
    return [row.ljust(w) for row in sprite]

for w in WEAPON_SPRITES:
    WEAPON_SPRITES[w] = pad_sprite(WEAPON_SPRITES[w])


# ======================== ENEMY TYPES (Sci-Fi/Robots) ========================
ENEMY_TYPES = {
    'drone': {
        'sprite': [
            "    /---\\    ",
            "   | o o |   ",
            "  /| \\-/ |\\  ",
            " | | ___ | | ",
            " | |/   \\| | ",
            "  \\|_____|/  ",
            "   |__|__|   ",
            "  /  |   \\  ",
            " /   |    \\ ",
            "[____|____]",
        ],
        'health': 3, 'speed': 1.4, 'damage': 8,
        'attack_range': 0.7, 'attack_cooldown': 1.0,
        'ranged': False, 'score': 100, 'color': (220, 60, 50),
    },
    'android': {
        'sprite': [
            "   /|\\___/|\\   ",
            "  | | o o | |  ",
            "  | \\_/\\_/ |  ",
            "   \\  -  /    ",
            "    |   |     ",
            "   /|\\_/|\\    ",
            "  / |_|_| \\   ",
            " / /|___|\\ \\  ",
            "/ / |___| \\ \\ ",
            "|/___|___|__\\|",
            "  |  |   |  | ",
            " [__]   [__]  "
        ],
        'health': 2, 'speed': 2.4, 'damage': 6,
        'attack_range': 0.6, 'attack_cooldown': 0.8,
        'ranged': False, 'score': 150, 'color': (255, 180, 50),
    },
    'turret': {
        'sprite': [
            "    /===\\   ",
            "   |  O  |  ",
            "  /| [---] |\\",
            " | |_______| |",
            " |  [=====]  |",
            "  \\|_______|/",
            "   |__|__|",
            "  / | | \\",
            " /  | |  \\",
            "[___|_|___]",
        ],
        'health': 6, 'speed': 0.9, 'damage': 12,
        'attack_range': 6.0, 'attack_cooldown': 1.8,
        'ranged': True, 'projectile_speed': 5.0,
        'score': 250, 'color': (100, 130, 255),
    },
    'mech': {
        'sprite': [
            "   /=======\\   ",
            "  |  X   X  |  ",
            "  |  \\ - /  |  ",
            "  |  [===]  |  ",
            "   \\  |||  /   ",
            "   /|_____|\\   ",
            "  / |_____| \\  ",
            " /  |_____|  \\ ",
            "/   |_____|   \\",
            "|___[=======]___|",
            "  |  |___|  |  ",
            " [__]     [__]  "
        ],
        'health': 18, 'speed': 1.1, 'damage': 20,
        'attack_range': 8.0, 'attack_cooldown': 1.2,
        'ranged': True, 'projectile_speed': 6.5,
        'score': 1500, 'color': (200, 50, 255),
    },
    'spider': {
        'sprite': [
            "  /\\  /\\  ",
            " | o || o | ",
            "  \\_/__\\_/  ",
            "  /|    |\\  ",
            " / |____| \\ ",
            "/  |    |  \\ ",
            "|  |____|  | ",
            "|__________|",
            "  | |  | |  ",
            " [_] [_] "
        ],
        'health': 1, 'speed': 3.2, 'damage': 4,
        'attack_range': 0.5, 'attack_cooldown': 0.6,
        'ranged': False, 'score': 80, 'color': (180, 255, 100),
    },
    'cyborg': {
        'sprite': [
            "   /=======\\   ",
            "  |  O   O  |  ",
            "  |  \\-=-/  |  ",
            "  | [=======] |  ",
            " /=============\\",
            "|  [=========]  |",
            "|   [=======]   |",
            " /|=============|\\",
            "/ | [=========] | \\",
            "|  |  [=======]  |  |",
            "|__|__[=======]__|__|",
            "  |__|_______|__|  "
        ],
        'health': 12, 'speed': 0.6, 'damage': 18,
        'attack_range': 0.8, 'attack_cooldown': 1.5,
        'ranged': False, 'score': 350, 'color': (180, 100, 200),
    },
}

for etype in ENEMY_TYPES:
    ENEMY_TYPES[etype]['sprite'] = pad_sprite(ENEMY_TYPES[etype]['sprite'])


DIFFICULTY = {
    'easy':   {'enemy_count': 10, 'enemy_hp_mod': 0.7, 'enemy_speed_mod': 0.7, 'player_health': 150, 'label': 'ROOKIE',      'regen': 3.0, 'grenades': 5, 'stamina_drain': 0.7},
    'normal': {'enemy_count': 15, 'enemy_hp_mod': 1.0, 'enemy_speed_mod': 1.0, 'player_health': 100, 'label': 'AGENT',    'regen': 1.5, 'grenades': 3, 'stamina_drain': 1.0},
    'hard':   {'enemy_count': 22, 'enemy_hp_mod': 1.3, 'enemy_speed_mod': 1.3, 'player_health': 75,  'label': 'VETERAN',      'regen': 0.0, 'grenades': 2, 'stamina_drain': 1.2},
    'nightmare': {'enemy_count': 30, 'enemy_hp_mod': 1.6, 'enemy_speed_mod': 1.5, 'player_health': 50, 'label': 'OVERLORD', 'regen': 0.0, 'grenades': 1, 'stamina_drain': 1.4},
}
DIFFICULTY_ORDER = ['easy', 'normal', 'hard', 'nightmare']


# ======================== POWER-UPS ========================
POWERUP_TYPES = {
    'overclock':    {'name': 'OVERCLOCK',  'duration': 12.0, 'color': (255, 80, 255), 'sprite': ["(O)", "[O]", "(O)"], 'msg': 'OVERCLOCK!'},
    'stim':   {'name': 'STIM',     'duration': 10.0, 'color': (80, 255, 255), 'sprite': ["(S)", ">>", "(S)"], 'msg': 'STIMPACK!'},
    'rage': {'name': 'RAGE',   'duration': 15.0, 'color': (255, 80, 80),  'sprite': ["(R)", "!!", "(R)"], 'msg': 'RAGE!'},
    'cloak':   {'name': 'CLOAK',     'duration': 8.0,  'color': (200, 200, 255),'sprite': ["(C)", "::", "(C)"], 'msg': 'CLOAK ENGAGED!'},
}


# ======================== EXPERT PROCEDURAL GENERATION ========================
def hash_noise(x: int, y: int, seed: int) -> float:
    h = (x * 73856093) ^ (y * 19349663) ^ (seed * 83492791)
    h = (h * (h * h * 15731 + 789221) + 1376312589) & 0x7fffffff
    return h / 0x7fffffff

def generate_city_map(enemy_count=15, enemy_hp_mod=1.0, enemy_speed_mod=1.0):
    W, H = 40, 40
    grid = [[0 for _ in range(W)] for _ in range(H)]
    centers = []
    for wt in [1, 2, 3, 4, 5]:
        centers.append((random.randint(2, W-3), random.randint(2, H-3), wt))
    def get_district(x, y):
        best_d = float('inf'); best_wt = 1
        for cx, cy, wt in centers:
            d = (x - cx)**2 + (y - cy)**2
            if d < best_d: best_d = d; best_wt = wt
        return best_wt
    for y in range(H):
        for x in range(W): grid[y][x] = get_district(x, y)
    def carve_road(x1, y1, x2, y2, depth):
        if depth > 4 or x2 - x1 < 6 or y2 - y1 < 6: return
        if random.random() > 0.5 and (x2 - x1 > y2 - y1):
            rx = random.randint(x1 + 2, x2 - 2)
            for y in range(y1, y2 + 1):
                if random.random() > 0.1: grid[y][rx] = 0
            carve_road(x1, y1, rx - 1, y2, depth + 1)
            carve_road(rx + 1, y1, x2, y2, depth + 1)
        else:
            ry = random.randint(y1 + 2, y2 - 2)
            for x in range(x1, x2 + 1):
                if random.random() > 0.1: grid[ry][x] = 0
            carve_road(x1, y1, x2, ry - 1, depth + 1)
            carve_road(x1, ry + 1, x2, y2, depth + 1)
    carve_road(1, 1, W - 2, H - 2, 0)
    for _ in range(W * H // 15):
        rx, ry = random.randint(1, W-2), random.randint(1, H-2)
        if grid[ry][rx] != 0: grid[ry][rx] = 0
    for i in range(W):
        grid[0][i] = 1; grid[H-1][i] = 1
        grid[i][0] = 1; grid[i][W-1] = 1
    px, py = float(W//2), float(H//2)
    attempts = 0
    while grid[int(py)][int(px)] != 0 and attempts < 1000:
        px = random.uniform(1, W-1); py = random.uniform(1, H-1)
        attempts += 1
    enemies = []
    attempts = 0
    boss_spawned = False
    while len(enemies) < enemy_count and attempts < 5000:
        attempts += 1
        ex, ey = random.randint(1, W-2), random.randint(1, H-2)
        if grid[ey][ex] == 0:
            d = math.hypot(ex - px, ey - py)
            if d > 8.0:
                r = random.random()
                if not boss_spawned and enemy_count >= 10 and len(enemies) == enemy_count - 1:
                    etype = 'mech'; boss_spawned = True
                elif r < 0.35: etype = 'drone'
                elif r < 0.55: etype = 'android'
                elif r < 0.70: etype = 'spider'
                elif r < 0.88: etype = 'turret'
                else: etype = 'cyborg'
                e = Enemy(ex + 0.5, ey + 0.5, etype)
                e.health = max(1, int(e.health * enemy_hp_mod))
                e.max_health = e.health
                e.speed *= enemy_speed_mod
                enemies.append(e)
    pickups = []
    for _ in range(10):
        attempts = 0
        while attempts < 100:
            attempts += 1
            ppx, ppy = random.randint(1, W-2), random.randint(1, H-2)
            if grid[ppy][ppx] == 0:
                d = math.hypot(ppx - px, ppy - py)
                if d > 4.0:
                    r = random.random()
                    if r < 0.35: kind = 'health'
                    elif r < 0.70: kind = 'ammo'
                    else: kind = 'grenade'
                    pickups.append(Pickup(ppx + 0.5, ppy + 0.5, kind))
                    break
    powerups = []
    for _ in range(3):
        attempts = 0
        while attempts < 100:
            attempts += 1
            ppx, ppy = random.randint(1, W-2), random.randint(1, H-2)
            if grid[ppy][ppx] == 0:
                d = math.hypot(ppx - px, ppy - py)
                if d > 6.0:
                    ptype = random.choice(list(POWERUP_TYPES.keys()))
                    powerups.append(Powerup(ppx + 0.5, ppy + 0.5, ptype))
                    break
    barrels = []
    for _ in range(6):
        attempts = 0
        while attempts < 100:
            attempts += 1
            bx, by = random.randint(1, W-2), random.randint(1, H-2)
            if grid[by][bx] == 0:
                barrels.append(Barrel(bx + 0.5, by + 0.5))
                break
    map_strings = ["".join(str(c) for c in row) for row in grid]
    return map_strings, px, py, enemies, pickups, barrels, powerups


def gen_texture_v2(wt: int, seed: int):
    tex = [[(' ', 5, 5, 15) for _ in range(64)] for _ in range(64)]
    for y in range(64):
        for x in range(64):
            n = hash_noise(x, y, seed)
            n2 = hash_noise(x, y, seed+100)
            if y < 10:
                if y == 0: tex[y][x] = ('=', 80, 80, 80)
                elif y == 9: tex[y][x] = ('-', 60, 60, 60)
                elif x % 16 == 0 and y < 6: tex[y][x] = ('|', 120, 120, 120)
                elif n > 0.85: tex[y][x] = ('[', 90, 90, 90)
                elif n > 0.7: tex[y][x] = (':', 40, 40, 50)
                else: tex[y][x] = (' ', 20, 20, 30)
            elif y < 22:
                if y == 10 or y == 21: tex[y][x] = ('=', 100, 100, 100)
                else:
                    if wt == 1:
                        if x % 12 == 0: tex[y][x] = ('|', 80, 100, 120)
                        elif n > 0.7: tex[y][x] = (':', 150, 200, 255)
                        else: tex[y][x] = ('.', 50, 80, 100)
                    elif wt == 2:
                        if x % 8 == 0: tex[y][x] = ('|', 120, 60, 30)
                        elif n > 0.8: tex[y][x] = ('@', 150, 80, 40)
                        elif n > 0.5: tex[y][x] = ('%', 80, 40, 20)
                        else: tex[y][x] = (' ', 30, 15, 10)
                    elif wt == 3:
                        if y % 10 == 5 and x % 8 == 4: tex[y][x] = ('=', 255, 50, 200)
                        elif n > 0.9: tex[y][x] = ('*', 255, 200, 50)
                        else: tex[y][x] = (' ', 10, 5, 20)
                    elif wt == 4:
                        if y % 7 == 0 or x % 14 == 0: tex[y][x] = ('+', 90, 90, 90)
                        elif n > 0.7: tex[y][x] = ('.', 110, 110, 110)
                        else: tex[y][x] = (' ', 70, 70, 70)
                    elif wt == 5:
                        if x % 10 == 0: tex[y][x] = ('|', 100, 100, 100)
                        elif n > 0.8: tex[y][x] = ('#', 80, 80, 80)
                        else: tex[y][x] = (':', 60, 60, 60)
            elif y < 34:
                if y == 22 or y == 33: tex[y][x] = ('=', 100, 100, 100)
                else:
                    ox = (x + 6) % 64
                    if wt == 1:
                        if ox % 12 == 0: tex[y][x] = ('|', 80, 100, 120)
                        elif n2 > 0.6: tex[y][x] = (':', 150, 200, 255)
                        else: tex[y][x] = ('.', 50, 80, 100)
                    elif wt == 2:
                        if ox % 8 == 0: tex[y][x] = ('|', 120, 60, 30)
                        elif n2 > 0.8: tex[y][x] = ('@', 150, 80, 40)
                        elif n2 > 0.5: tex[y][x] = ('%', 80, 40, 20)
                        else: tex[y][x] = (' ', 30, 15, 10)
                    elif wt == 3:
                        if y % 10 == 5 and ox % 8 == 4: tex[y][x] = ('-', 50, 200, 255)
                        elif n2 > 0.9: tex[y][x] = ('*', 255, 200, 50)
                        else: tex[y][x] = (' ', 10, 5, 20)
                    elif wt == 4:
                        if y % 7 == 0 or ox % 14 == 0: tex[y][x] = ('+', 90, 90, 90)
                        elif n2 > 0.7: tex[y][x] = ('.', 110, 110, 110)
                        else: tex[y][x] = (' ', 70, 70, 70)
                    elif wt == 5:
                        if ox % 10 == 0: tex[y][x] = ('|', 100, 100, 100)
                        elif n2 > 0.8: tex[y][x] = ('#', 80, 80, 80)
                        else: tex[y][x] = (':', 60, 60, 60)
            elif y < 46:
                if y == 34 or y == 45: tex[y][x] = ('=', 100, 100, 100)
                else:
                    if wt == 1:
                        if x % 16 == 0: tex[y][x] = ('|', 80, 100, 120)
                        elif n > 0.5: tex[y][x] = (':', 150, 200, 255)
                        else: tex[y][x] = ('.', 50, 80, 100)
                    elif wt == 2:
                        if x % 12 == 0: tex[y][x] = ('|', 120, 60, 30)
                        elif n > 0.8: tex[y][x] = ('@', 150, 80, 40)
                        else: tex[y][x] = (' ', 30, 15, 10)
                    elif wt == 3:
                        if y % 10 == 5 and x % 10 == 5: tex[y][x] = ('=', 255, 50, 200)
                        elif n > 0.9: tex[y][x] = ('*', 255, 200, 50)
                        else: tex[y][x] = (' ', 10, 5, 20)
                    elif wt == 4:
                        if x % 16 == 0: tex[y][x] = ('+', 90, 90, 90)
                        else: tex[y][x] = (' ', 70, 70, 70)
                    elif wt == 5:
                        if x % 12 == 0: tex[y][x] = ('|', 100, 100, 100)
                        else: tex[y][x] = (':', 60, 60, 60)
            else:
                if y == 46: tex[y][x] = ('=', 80, 80, 80)
                elif y == 63: tex[y][x] = ('=', 50, 50, 50)
                else:
                    if 20 < x < 40:
                        if y == 47 or y == 62: tex[y][x] = ('-', 120, 80, 40)
                        elif x == 20 or x == 39: tex[y][x] = ('|', 120, 80, 40)
                        elif n > 0.8: tex[y][x] = (':', 80, 50, 20)
                        else: tex[y][x] = ('.', 40, 30, 10)
                    else:
                        if n > 0.8: tex[y][x] = (':', 50, 50, 60)
                        elif n > 0.5: tex[y][x] = ('.', 30, 30, 30)
                        else: tex[y][x] = (' ', 10, 10, 15)
    return tex

TEXTURES = {}
def init_textures():
    global TEXTURES
    TEXTURES = {}
    for wt in range(1, 6):
        TEXTURES[wt] = [gen_texture_v2(wt, i) for i in range(4)]


# ======================== ENTITIES ========================
class Enemy:
    def __init__(self, x: float, y: float, enemy_type: str = 'drone'):
        self.x = x; self.y = y
        self.type = enemy_type
        spec = ENEMY_TYPES[enemy_type]
        self.sprite = spec['sprite']
        self.health = spec['health']
        self.max_health = spec['health']
        self.speed = spec['speed']
        self.damage = spec['damage']
        self.attack_range = spec['attack_range']
        self.base_attack_cd = spec['attack_cooldown']
        self.attack_cooldown = random.uniform(0, 1.0)
        self.ranged = spec.get('ranged', False)
        self.proj_speed = spec.get('projectile_speed', 0)
        self.score_value = spec['score']
        self.color = spec['color']
        self.alive = True
        self.hit_flash = 0.0
        self.death_anim = 0.0

class Pickup:
    HEALTH_SPRITE = [" + ", "+R+", " + "]
    AMMO_SPRITE = ["[=]", "|E|", "[=]"]
    GRENADE_SPRITE = [" o ", "(G)", " o "]

    def __init__(self, x, y, kind):
        self.x = x; self.y = y
        self.kind = kind
        self.taken = False
        self.bob = random.random() * math.pi * 2
        if kind == 'health':
            self.sprite = pad_sprite(self.HEALTH_SPRITE); self.amount = 25; self.color = (100, 255, 100)
        elif kind == 'ammo':
            self.sprite = pad_sprite(self.AMMO_SPRITE); self.amount = 15; self.color = (255, 220, 100)
        else:
            self.sprite = pad_sprite(self.GRENADE_SPRITE); self.amount = 1; self.color = (100, 200, 255)

class Powerup:
    def __init__(self, x, y, ptype):
        self.x = x; self.y = y
        self.ptype = ptype
        self.taken = False
        self.bob = random.random() * math.pi * 2
        spec = POWERUP_TYPES[ptype]
        self.sprite = pad_sprite(spec['sprite'])
        self.color = spec['color']
        self.duration = spec['duration']
        self.name = spec['name']
        self.msg = spec['msg']

class Projectile:
    def __init__(self, x, y, dx, dy, damage, owner='enemy'):
        self.x = x; self.y = y
        self.dx = dx; self.dy = dy
        self.damage = damage
        self.owner = owner
        self.alive = True
        self.life = 3.0

class Grenade:
    SPRITE = ["(G)"]
    def __init__(self, x, y, dx, dy):
        self.x = x; self.y = y
        self.dx = dx; self.dy = dy
        self.timer = 1.2
        self.alive = True
        self.bounces = 0

class Barrel:
    SPRITE = [" _ ", "|*|", "|0|", "[=]"]
    def __init__(self, x, y):
        self.x = x; self.y = y
        self.exploded = False
        self.explode_timer = 0.0

class Particle:
    def __init__(self, x, y, vx, vy, char, color, life):
        self.x = x; self.y = y
        self.vx = vx; self.vy = vy
        self.char = char
        self.color = color
        self.life = life
        self.max_life = life
        self.alive = True

class DamageNumber:
    def __init__(self, sx, sy, amount, crit=False):
        self.sx = sx; self.sy = sy
        self.amount = amount
        self.crit = crit
        self.life = 0.8
        self.vy = -2.0
        self.alive = True


# ======================== GAME LOGIC ========================
class Game:
    def __init__(self, difficulty='normal', sound=None):
        self.sound = sound
        self.difficulty = difficulty
        diff = DIFFICULTY[difficulty]

        (self.map_data, self.px, self.py, self.enemies, self.pickups,
         self.barrels, self.powerups) = generate_city_map(
            diff['enemy_count'], diff['enemy_hp_mod'], diff['enemy_speed_mod']
        )
        self.map_w = len(self.map_data[0])
        self.map_h = len(self.map_data)

        self.map_textures = {}
        for y in range(self.map_h):
            for x in range(self.map_w):
                wt = self.map_data[y][x]
                if wt != '0':
                    var = (x * 7 + y * 13) % 4
                    self.map_textures[(x, y)] = TEXTURES[int(wt)][var]

        self.angle = 0.0
        self.max_health = diff['player_health']
        self.health = self.max_health
        self.ammo = 50
        self.max_ammo = 99
        self.grenades = diff['grenades']
        self.max_grenades = 5
        self.score = 0
        self.fire_cooldown = 0.0
        self.grenade_cooldown = 0.0
        self.total_enemies = len(self.enemies)

        self.current_weapon = 'laser'

        self.keys: Set[int] = set()
        self.muzzle_flash = 0.0
        self.damage_flash = 0.0
        self.message = ""
        self.message_time = 0.0
        self.game_over = False
        self.victory = False
        self.paused = False

        self.projectiles: List[Projectile] = []
        self.grenades_list: List[Grenade] = []
        self.particles: List[Particle] = []
        self.damage_numbers: List[DamageNumber] = []

        self.bob_time = 0.0
        self.recoil = 0.0
        self.flash_frame = 0
        self.combo = 0
        self.combo_max = 0
        self.combo_timer = 0.0
        self.last_damage_dir: Optional[float] = None
        self.damage_dir_time = 0.0
        self.damage_immunity = 0.0
        self.last_damage_time = 0.0
        self.hit_marker_time = 0.0
        self.kill_marker_time = 0.0

        self.max_stamina = 100.0
        self.stamina = 100.0
        self.stamina_drain = 30.0 * diff['stamina_drain']
        self.stamina_regen = 25.0

        self.adrenaline = 0.0
        self.adrenaline_max = 100.0
        self.adrenaline_active = 0.0
        self.adrenaline_uses = 0
        self.slow_mo_factor = 1.0

        self.active_powerups: Dict[str, float] = {}
        self.powerups_used = 0

        self.shots_fired = 0
        self.shots_hit = 0
        self.kills = 0
        self.barrel_kills = 0
        self.grenade_kills = 0
        self.crits = 0
        self.took_damage_ever = False
        self.start_time = time.time()
        self.end_time = 0.0

        self.sky_tint, self.sky_name = random.choice(SKY_TINTS)

        self.footstep_timer = 0.0
        self.ambient_timer = random.uniform(4, 10)
        self.is_new_highscore = False
        
        self.cloud_offsets = [random.uniform(0, COLS) for _ in range(4)]
        self.birds = []
        for _ in range(3):
            self.birds.append({
                'x': random.uniform(0, COLS),
                'y': random.uniform(2, 8),
                'speed': random.uniform(0.5, 1.5),
                'dir': 1 if random.random() > 0.5 else -1
            })

    def has_powerup(self, name): return self.active_powerups.get(name, 0) > 0

    def damage_multiplier(self):
        m = 1.0
        if self.has_powerup('overclock'): m *= 4.0
        if self.has_powerup('rage'): m *= 2.0
        return m

    def speed_multiplier(self):
        m = 1.0
        if self.has_powerup('stim'): m *= 1.7
        return m

    def update(self, dt: float):
        if self.paused or self.game_over or self.victory: return

        world_dt = dt
        if self.adrenaline_active > 0:
            self.adrenaline_active = max(0, self.adrenaline_active - dt)
            world_dt = dt * 0.3
            self.slow_mo_factor = 0.3
        else:
            self.slow_mo_factor = 1.0

        want_sprint = Qt.Key_Shift in self.keys
        can_sprint = want_sprint and self.stamina > 0 and (Qt.Key_W in self.keys or Qt.Key_Up in self.keys or Qt.Key_S in self.keys or Qt.Key_Down in self.keys or Qt.Key_A in self.keys or Qt.Key_D in self.keys)
        if can_sprint:
            self.stamina = max(0.0, self.stamina - self.stamina_drain * dt)
            sprint = 1.6
        else:
            self.stamina = min(self.max_stamina, self.stamina + self.stamina_regen * dt)
            sprint = 1.0

        sprint *= self.speed_multiplier()
        move_speed = 3.5 * dt * sprint
        turn_speed = 2.5 * dt

        fwd = 0; strafe = 0
        if Qt.Key_W in self.keys or Qt.Key_Up in self.keys: fwd += 1
        if Qt.Key_S in self.keys or Qt.Key_Down in self.keys: fwd -= 1
        if Qt.Key_A in self.keys: strafe -= 1
        if Qt.Key_D in self.keys: strafe += 1

        is_moving = False
        if fwd != 0:
            self.try_move(math.cos(self.angle) * move_speed * fwd, math.sin(self.angle) * move_speed * fwd)
            is_moving = True
        if strafe != 0:
            self.try_move(math.cos(self.angle + math.pi / 2) * move_speed * strafe, math.sin(self.angle + math.pi / 2) * move_speed * strafe)
            is_moving = True

        if is_moving:
            self.bob_time += dt * 8.0 * sprint
            self.footstep_timer -= dt
            if self.footstep_timer <= 0:
                if self.sound: self.sound.play('footstep')
                self.footstep_timer = 0.35 / sprint

        if Qt.Key_Left in self.keys: self.angle -= turn_speed
        if Qt.Key_Right in self.keys: self.angle += turn_speed

        if self.fire_cooldown > 0: self.fire_cooldown -= dt
        if self.grenade_cooldown > 0: self.grenade_cooldown -= dt
        if Qt.Key_Space in self.keys and self.fire_cooldown <= 0:
            self.shoot()
            w = WEAPONS[self.current_weapon]
            self.fire_cooldown = w['fire_rate']
        if Qt.Key_G in self.keys and self.grenade_cooldown <= 0:
            self.throw_grenade()
            self.grenade_cooldown = 0.8

        self.muzzle_flash = max(0, self.muzzle_flash - dt * 3.0)
        self.recoil = max(0, self.recoil - dt * 5.0)
        self.damage_flash = max(0, self.damage_flash - dt)
        self.message_time = max(0, self.message_time - dt)
        self.combo_timer = max(0, self.combo_timer - dt)
        if self.combo_timer <= 0: self.combo = 0
        self.damage_immunity = max(0, self.damage_immunity - dt)
        self.damage_dir_time = max(0, self.damage_dir_time - dt)
        self.hit_marker_time = max(0, self.hit_marker_time - dt)
        self.kill_marker_time = max(0, self.kill_marker_time - dt)
        self.last_damage_time += dt

        expired = []
        for name in list(self.active_powerups.keys()):
            self.active_powerups[name] -= dt
            if self.active_powerups[name] <= 0:
                expired.append(name)
                del self.active_powerups[name]

        regen = DIFFICULTY[self.difficulty]['regen']
        if regen > 0 and self.last_damage_time > 4.0 and self.health < self.max_health and self.health > 0:
            self.health = min(self.max_health, self.health + regen * dt)

        cloak_active = self.has_powerup('cloak')
        for e in self.enemies:
            if not e.alive:
                if e.death_anim > 0: e.death_anim -= world_dt
                continue
            e.hit_flash = max(0, e.hit_flash - world_dt)
            e.attack_cooldown = max(0, e.attack_cooldown - world_dt)

            dx = self.px - e.x; dy = self.py - e.y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < 0.001: continue

            if cloak_active and dist > 3.0:
                if random.random() < 0.02:
                    ang = random.uniform(0, math.pi * 2)
                    nx = e.x + math.cos(ang) * e.speed * world_dt * 0.5
                    ny = e.y + math.sin(ang) * e.speed * world_dt * 0.5
                    if not self.is_wall(nx, e.y): e.x = nx
                    if not self.is_wall(e.x, ny): e.y = ny
                continue

            if e.ranged:
                if dist > e.attack_range:
                    speed = e.speed * world_dt
                    nx = e.x + (dx / dist) * speed; ny = e.y + (dy / dist) * speed
                    if not self.is_wall(nx, e.y): e.x = nx
                    if not self.is_wall(e.x, ny): e.y = ny
                elif dist < e.attack_range * 0.4:
                    speed = e.speed * 0.7 * world_dt
                    nx = e.x - (dx / dist) * speed; ny = e.y - (dy / dist) * speed
                    if not self.is_wall(nx, e.y): e.x = nx
                    if not self.is_wall(e.x, ny): e.y = ny
                if e.attack_cooldown <= 0 and not self.wall_between(e.x, e.y) and dist < e.attack_range + 2:
                    pdx = dx / dist * e.proj_speed
                    pdy = dy / dist * e.proj_speed
                    self.projectiles.append(Projectile(e.x, e.y, pdx, pdy, e.damage, 'enemy'))
                    e.attack_cooldown = e.base_attack_cd
                    if self.sound: self.sound.play('enemy_shoot')
            else:
                if dist > 0.7:
                    speed = e.speed * world_dt
                    nx = e.x + (dx / dist) * speed; ny = e.y + (dy / dist) * speed
                    if not self.is_wall(nx, e.y): e.x = nx
                    if not self.is_wall(e.x, ny): e.y = ny
                elif e.attack_cooldown <= 0:
                    self.take_damage(e.damage, math.atan2(dy, dx))
                    e.attack_cooldown = e.base_attack_cd

        for p in self.projectiles:
            if not p.alive: continue
            p.life -= world_dt
            if p.life <= 0: p.alive = False; continue
            nx = p.x + p.dx * world_dt; ny = p.y + p.dy * world_dt
            if self.is_wall(nx, ny):
                p.alive = False
                if self.sound: self.sound.play('wall_hit')
                for _ in range(4):
                    ang = random.uniform(0, math.pi * 2)
                    spd = random.uniform(1, 3)
                    self.particles.append(Particle(p.x, p.y, math.cos(ang) * spd, math.sin(ang) * spd, '*', QColor(255, 200, 100), 0.4))
                continue
            p.x, p.y = nx, ny
            if p.owner == 'enemy':
                pdx = p.x - self.px; pdy = p.y - self.py
                if pdx*pdx + pdy*pdy < 0.16:
                    p.alive = False
                    self.take_damage(p.damage, math.atan2(p.dy, p.dx))
        self.projectiles = [p for p in self.projectiles if p.alive]

        for gr in self.grenades_list:
            if not gr.alive: continue
            gr.timer -= world_dt
            nx = gr.x + gr.dx * world_dt; ny = gr.y + gr.dy * world_dt
            if self.is_wall(nx, gr.y):
                gr.dx = -gr.dx * 0.5; gr.bounces += 1
                if self.sound: self.sound.play('grenade_bounce')
            else: gr.x = nx
            if self.is_wall(gr.x, ny):
                gr.dy = -gr.dy * 0.5; gr.bounces += 1
                if self.sound: self.sound.play('grenade_bounce')
            else: gr.y = ny
            gr.dx *= 0.97; gr.dy *= 0.97
            if gr.timer <= 0:
                self.explode_grenade(gr)
                gr.alive = False
        self.grenades_list = [g for g in self.grenades_list if g.alive]

        for prt in self.particles:
            prt.life -= world_dt
            if prt.life <= 0: prt.alive = False; continue
            prt.x += prt.vx * world_dt; prt.y += prt.vy * world_dt
            prt.vx *= 0.92; prt.vy *= 0.92
        self.particles = [p for p in self.particles if p.alive]

        for dn in self.damage_numbers:
            dn.life -= dt
            if dn.life <= 0: dn.alive = False; continue
            dn.sy += dn.vy * dt * 3
        self.damage_numbers = [d for d in self.damage_numbers if d.alive]

        for pk in self.pickups:
            if pk.taken: continue
            pk.bob += dt * 3
            dx = pk.x - self.px; dy = pk.y - self.py
            if dx*dx + dy*dy < 0.25:
                pk.taken = True
                if self.sound: self.sound.play('pickup')
                if pk.kind == 'health':
                    self.health = min(self.max_health, self.health + pk.amount)
                    self.message = f"+{pk.amount} REPAIR"
                elif pk.kind == 'ammo':
                    self.ammo = min(self.max_ammo, self.ammo + pk.amount)
                    self.message = f"+{pk.amount} ENERGY"
                else:
                    self.grenades = min(self.max_grenades, self.grenades + pk.amount)
                    self.message = f"+{pk.amount} EMP"
                self.message_time = 1.5

        for pu in self.powerups:
            if pu.taken: continue
            pu.bob += dt * 3
            dx = pu.x - self.px; dy = pu.y - self.py
            if dx*dx + dy*dy < 0.25:
                pu.taken = True
                if self.sound: self.sound.play('powerup_pickup')
                self.active_powerups[pu.ptype] = pu.duration
                self.powerups_used += 1
                self.message = pu.msg
                self.message_time = 2.0

        self.ambient_timer -= dt
        if self.ambient_timer <= 0:
            if self.sound: self.sound.play(random.choice(['ambient1', 'ambient2']))
            self.ambient_timer = random.uniform(5, 15)
            
        for i in range(len(self.cloud_offsets)):
            self.cloud_offsets[i] += dt * 1.5
            if self.cloud_offsets[i] > COLS + 20:
                self.cloud_offsets[i] = -20
        for b in self.birds:
            b['x'] += b['dir'] * b['speed'] * dt * 5
            if b['x'] < 0: b['x'] = COLS
            if b['x'] > COLS: b['x'] = 0

        if all(not e.alive for e in self.enemies) and not self.victory:
            self.victory = True
            self.end_time = time.time()
            if self.sound: self.sound.play('victory')
            self.is_new_highscore = save_highscore(self.difficulty, self.score)
            if self.is_new_highscore and self.sound: self.sound.play('achievement')

    def take_damage(self, amount, src_angle):
        if self.damage_immunity > 0: return
        if self.has_powerup('rage'): amount = int(amount * 0.4)
        if amount <= 0: return
        self.health = max(0, self.health - amount)
        self.damage_flash = 0.4
        self.damage_immunity = 0.3
        self.last_damage_time = 0.0
        self.took_damage_ever = True
        self.last_damage_dir = (src_angle - self.angle + math.pi) % (2 * math.pi) - math.pi
        self.damage_dir_time = 1.2
        self.adrenaline = min(self.adrenaline_max, self.adrenaline + 15)
        if self.sound: self.sound.play('player_hit')
        if self.health <= 0:
            self.game_over = True
            self.end_time = time.time()
            if self.sound: self.sound.play('game_over')

    def try_move(self, dx, dy):
        r = 0.25
        nx = self.px + dx
        if not self.is_wall(nx + (r if dx > 0 else -r), self.py): self.px = nx
        ny = self.py + dy
        if not self.is_wall(self.px, ny + (r if dy > 0 else -r)): self.py = ny

    def is_wall(self, x, y):
        mx, my = int(x), int(y)
        if mx < 0 or mx >= self.map_w or my < 0 or my >= self.map_h: return True
        return self.map_data[my][mx] != '0'

    def shoot(self):
        if self.game_over or self.victory or self.paused: return
        w = WEAPONS[self.current_weapon]
        if self.ammo < w['ammo_per_shot']:
            self.message = "ENERGY DEPLETED!"
            self.message_time = 1.0
            if self.sound: self.sound.play('dry_fire')
            return
        self.ammo -= w['ammo_per_shot']
        if self.sound: self.sound.play(f'shoot_{self.current_weapon}')
        self.muzzle_flash = 1.0
        self.recoil = w['recoil']
        self.flash_frame = random.randint(0, 2)
        self.shots_fired += w['pellets']
        for _ in range(w['pellets']):
            spread = (random.random() - 0.5) * w['spread']
            self.fire_ray(self.angle + spread, w)
        for _ in range(2):
            ang = self.angle + random.uniform(-0.2, 0.2)
            spd = random.uniform(0.3, 1.0)
            self.particles.append(Particle(
                self.px + math.cos(self.angle) * 0.5, self.py + math.sin(self.angle) * 0.5,
                math.cos(ang) * spd, math.sin(ang) * spd, random.choice(".,'"), QColor(180, 180, 180), 0.5))

    def fire_ray(self, angle, weapon):
        dx = math.cos(angle); dy = math.sin(angle)
        step_size = 0.05
        dist = 0
        while dist < weapon['range']:
            dist += step_size
            cx = self.px + dx * dist; cy = self.py + dy * dist
            if self.is_wall(cx, cy):
                if self.sound: self.sound.play('wall_hit')
                for _ in range(3):
                    ang = random.uniform(0, math.pi * 2)
                    spd = random.uniform(0.5, 2)
                    self.particles.append(Particle(cx, cy, math.cos(ang) * spd, math.sin(ang) * spd, '.', QColor(255, 200, 100), 0.3))
                return
            for b in self.barrels:
                if b.exploded: continue
                if (b.x - cx)**2 + (b.y - cy)**2 < 0.16:
                    self.explode_barrel(b); return
            for e in self.enemies:
                if not e.alive: continue
                if (e.x - cx)**2 + (e.y - cy)**2 < 0.16:
                    is_crit = random.random() < weapon.get('crit_chance', 0.1)
                    damage = weapon['damage'] * self.damage_multiplier()
                    if is_crit:
                        damage *= 2
                        self.crits += 1
                        if self.sound: self.sound.play('crit')
                    damage = int(damage)
                    if damage < 1: damage = 1
                    e.health -= damage
                    e.hit_flash = 0.2
                    self.shots_hit += 1
                    self.hit_marker_time = 0.15
                    if self.sound: self.sound.play('enemy_hit' if e.type != 'mech' else 'boss_hit')
                    if self.sound: self.sound.play('hit_marker')
                    cx_screen = COLS // 2
                    cy_screen = VIEW_ROWS // 2 - 3
                    self.damage_numbers.append(DamageNumber(cx_screen + random.randint(-2, 2), cy_screen, damage, is_crit))
                    for _ in range(6):
                        ang = random.uniform(0, math.pi * 2)
                        spd = random.uniform(1, 3)
                        self.particles.append(Particle(e.x, e.y, math.cos(ang) * spd, math.sin(ang) * spd, '*', QColor(200, 30, 30), 0.5))
                    if e.health <= 0:
                        e.alive = False
                        e.death_anim = 0.5
                        self.kills += 1
                        self.combo += 1
                        self.combo_max = max(self.combo_max, self.combo)
                        self.combo_timer = 3.0
                        self.kill_marker_time = 0.4
                        combo_bonus = (self.combo - 1) * 25
                        gain = e.score_value + combo_bonus
                        self.score += gain
                        self.adrenaline = min(self.adrenaline_max, self.adrenaline + 6)
                        if self.sound: self.sound.play('enemy_die')
                        if self.combo > 1: self.message = f"TERMINATED! +{gain}  (x{self.combo} COMBO)"
                        else: self.message = f"TERMINATED! +{gain}"
                        self.message_time = 2.0
                        r = random.random()
                        if r < 0.15:
                            kind = 'health' if random.random() < 0.5 else 'ammo'
                            self.pickups.append(Pickup(e.x, e.y, kind))
                        if e.type in ('turret', 'mech', 'cyborg') and random.random() < 0.35:
                            ptype = random.choice(list(POWERUP_TYPES.keys()))
                            self.powerups.append(Powerup(e.x, e.y, ptype))
                        elif e.type == 'cyborg' and random.random() < 0.5:
                            self.pickups.append(Pickup(e.x, e.y, 'grenade'))
                    return

    def throw_grenade(self):
        if self.grenades <= 0:
            self.message = "NO EMPs!"
            self.message_time = 1.0
            return
        self.grenades -= 1
        if self.sound: self.sound.play('grenade_throw')
        dx = math.cos(self.angle); dy = math.sin(self.angle)
        self.grenades_list.append(Grenade(self.px + dx * 0.5, self.py + dy * 0.5, dx * 5.0, dy * 5.0))

    def explode_grenade(self, grenade):
        if self.sound: self.sound.play('explode')
        radius = 3.5
        for e in self.enemies:
            if not e.alive: continue
            d = math.hypot(e.x - grenade.x, e.y - grenade.y)
            if d < radius:
                dmg = int(6 * (1 - d/radius))
                if dmg > 0:
                    e.health -= dmg
                    e.hit_flash = 0.3
                    if e.health <= 0:
                        e.alive = False
                        e.death_anim = 0.5
                        self.kills += 1
                        self.grenade_kills += 1
                        self.combo += 1
                        self.combo_max = max(self.combo_max, self.combo)
                        self.combo_timer = 3.0
                        self.score += e.score_value
                        if self.sound: self.sound.play('enemy_die')
                        self.message = f"EMP KILL! +{e.score_value}"
                        self.message_time = 2.0
        for b in self.barrels:
            if b.exploded: continue
            d = math.hypot(b.x - grenade.x, b.y - grenade.y)
            if d < 2.5: self.explode_barrel(b)
        pd = math.hypot(self.px - grenade.x, self.py - grenade.y)
        if pd < radius:
            self.take_damage(int(12 * (1 - pd/radius)), math.atan2(grenade.y - self.py, grenade.x - self.px))
        for _ in range(25):
            ang = random.uniform(0, math.pi * 2)
            spd = random.uniform(2, 6)
            self.particles.append(Particle(grenade.x, grenade.y, math.cos(ang) * spd, math.sin(ang) * spd, random.choice('*#o@'), QColor(255, random.randint(100, 220), 50), 0.7))

    def explode_barrel(self, barrel, depth=0):
        if barrel.exploded or depth > 5: return
        barrel.exploded = True
        if self.sound: self.sound.play('explode')
        radius = 3.0
        for e in self.enemies:
            if not e.alive: continue
            d = math.hypot(e.x - barrel.x, e.y - barrel.y)
            if d < radius:
                e.health -= 4
                e.hit_flash = 0.3
                if e.health <= 0:
                    e.alive = False
                    e.death_anim = 0.5
                    self.kills += 1
                    self.barrel_kills += 1
                    self.score += e.score_value
                    if self.sound: self.sound.play('enemy_die')
                    self.message = f"EXPLOSION KILL! +{e.score_value}"
                    self.message_time = 2.0
        for _ in range(15):
            ang = random.uniform(0, math.pi * 2)
            spd = random.uniform(2, 5)
            self.particles.append(Particle(barrel.x, barrel.y, math.cos(ang) * spd, math.sin(ang) * spd, random.choice('*#o'), QColor(255, random.randint(100, 200), 50), 0.6))
        for b in self.barrels:
            if b.exploded: continue
            d = math.hypot(b.x - barrel.x, b.y - barrel.y)
            if d < 2.5: self.explode_barrel(b, depth + 1)
        pd = math.hypot(self.px - barrel.x, self.py - barrel.y)
        if pd < radius:
            self.take_damage(int(15 * (1 - pd/radius)), math.atan2(barrel.y - self.py, barrel.x - self.px))

    def wall_between(self, ex, ey):
        dx = ex - self.px; dy = ey - self.py
        d = math.sqrt(dx * dx + dy * dy)
        steps = max(int(d * 8), 2)
        for i in range(1, steps):
            t = i / steps
            if self.is_wall(self.px + dx * t, self.py + dy * t): return True
        return False

    def switch_weapon(self, weapon_name):
        if weapon_name in WEAPONS:
            if self.current_weapon != weapon_name:
                self.current_weapon = weapon_name
                self.message = f"EQUIPPED {WEAPONS[weapon_name]['name']}"
                self.message_time = 1.0
                if self.sound: self.sound.play('switch')

    def activate_adrenaline(self):
        if self.adrenaline >= self.adrenaline_max and self.adrenaline_active <= 0:
            self.adrenaline = 0
            self.adrenaline_active = 5.0
            self.adrenaline_uses += 1
            if self.sound: self.sound.play('adrenaline')
            self.message = "FOCUS ENGAGED!"
            self.message_time = 2.0

    def find_nearest_enemy(self):
        nearest = None
        min_d = float('inf')
        for e in self.enemies:
            if not e.alive: continue
            d = math.hypot(e.x - self.px, e.y - self.py)
            if d < min_d:
                min_d = d
                nearest = e
        return nearest, min_d

    def compute_achievements(self):
        ach = []
        elapsed = self.end_time - self.start_time
        if self.health == self.max_health and not self.took_damage_ever and self.kills > 0:
            ach.append(("FLAWLESS", "No damage taken"))
        if elapsed < 90 and self.victory:
            ach.append(("SPEEDRUN", "Cleared under 90s"))
        if self.combo_max >= 5: ach.append(("KILLING SPREE", "5x combo"))
        if self.combo_max >= 10: ach.append(("RAMPAGE", "10x combo"))
        acc = self.shots_hit / max(1, self.shots_fired)
        if acc >= 0.85 and self.shots_fired >= 10: ach.append(("SHARPSHOOTER", "85%+ accuracy"))
        if self.barrel_kills >= 3: ach.append(("PYROMANIAC", "3+ barrel kills"))
        if self.grenade_kills >= 3: ach.append(("DEMOLITIONIST", "3+ EMP kills"))
        if self.crits >= 5: ach.append(("CRITICAL", "5+ critical hits"))
        if self.difficulty == 'nightmare' and self.victory: ach.append(("OVERLORD", "Beat Overlord!"))
        elif self.difficulty == 'hard' and self.victory: ach.append(("VETERAN", "Beat Veteran!"))
        if self.powerups_used >= 3: ach.append(("POWERED UP", "Used 3+ power-ups"))
        if self.adrenaline_uses >= 1: ach.append(("FOCUS", "Used slow-mo"))
        if self.victory and self.kills == self.total_enemies: ach.append(("EXTERMINATOR", "Cleared all enemies"))
        return ach


# ======================== ASCII RENDERER ========================
class AsciiRenderer(QWidget):
    def __init__(self):
        super().__init__()
        self.sound = SoundManager()
        self.state = 'menu'
        self.menu_selection = 1
        self.game: Optional[Game] = None

        self.font = QFont("Courier New", 10)
        self.font.setStyleHint(QFont.Monospace)
        self.font.setBold(True)

        fm = QFontMetrics(self.font)
        self.char_w = max(fm.horizontalAdvance('M'), 1)
        self.char_h = max(fm.ascent() + fm.descent(), 1)
        self.ascent = fm.ascent()

        self.setFixedSize(COLS * self.char_w, ROWS * self.char_h)
        self.setFocusPolicy(Qt.StrongFocus)

        self.buffer = [(' ', QColor(0, 0, 0)) for _ in range(COLS * ROWS)]
        self.depth_buffer = [float('inf')] * COLS

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.last_time = time.time()
        self.timer.start(16)
        self.menu_time = 0.0
        self.highscores = load_highscores()

    def start_game(self, difficulty):
        self.game = Game(difficulty, self.sound)
        self.state = 'playing'
        if self.sound: self.sound.play('menu_select')
        if self.game.enemies and any(e.type == 'mech' for e in self.game.enemies if e.alive):
            if self.sound: self.sound.play('boss_spawn')

    def tick(self):
        now = time.time()
        dt = min(now - self.last_time, 0.1)
        self.last_time = now
        if self.state == 'menu':
            self.menu_time += dt
            self.render_menu()
        elif self.state == 'playing':
            self.game.update(dt)
            if self.game.game_over: self.state = 'gameover'
            elif self.game.victory: self.state = 'victory'
            elif self.game.paused: self.state = 'paused'
            self.render()
        elif self.state == 'paused':
            self.render()
            self.render_pause_overlay()
        elif self.state == 'gameover':
            self.render()
            self.render_end_overlay("SYSTEM FAILURE", QColor(255, 50, 50))
        elif self.state == 'victory':
            self.render()
            self.render_end_overlay("MISSION COMPLETE", QColor(50, 255, 50))
        self.update()

    def set_char(self, x, y, ch, color):
        if 0 <= x < COLS and 0 <= y < ROWS:
            self.buffer[y * COLS + x] = (ch, color)

    def fill_rect(self, x0, y0, x1, y1, ch, color):
        for y in range(max(0, y0), min(ROWS, y1)):
            for x in range(max(0, x0), min(COLS, x1)):
                self.buffer[y * COLS + x] = (ch, color)

    def draw_text(self, x, y, text, color):
        for i, c in enumerate(text):
            if 0 <= x + i < COLS and 0 <= y < ROWS:
                self.buffer[y * COLS + x + i] = (c, color)

    def render(self):
        for i in range(COLS * ROWS): self.buffer[i] = (' ', QColor(0, 0, 0))
        self.render_view()
        self.render_hud()

    def render_view(self):
        g = self.game
        if g is None: return
        px, py, angle = g.px, g.py, g.angle

        sr, sg, sb = g.sky_tint
        sky_color = QColor(sr, sg, sb)

        for col in range(COLS):
            ray_angle = angle - HALF_FOV + (col + 0.5) / COLS * FOV
            result = self.cast_ray(px, py, ray_angle, g.map_data)
            if result is None:
                self.depth_buffer[col] = float('inf')
                for row in range(VIEW_ROWS): self.set_char(col, row, ' ', QColor(0, 0, 0))
                continue
            perp_dist, side, wall_type, wall_x, map_x, map_y = result
            self.depth_buffer[col] = perp_dist

            wall_height = VIEW_ROWS / max(perp_dist, 0.1)
            wall_top = (VIEW_ROWS - wall_height) / 2
            wall_bottom = (VIEW_ROWS + wall_height) / 2
            tex = g.map_textures.get((map_x, map_y), TEXTURES[1][0])

            for row in range(VIEW_ROWS):
                if row < wall_top:
                    half = VIEW_ROWS / 2
                    depth = (half - row) / half
                    if depth > 0.2:
                        star_hash = (col * 37 + row * 91) % 100
                        if star_hash < 2: self.set_char(col, row, '*', QColor(255, 255, 255))
                        elif star_hash < 5: self.set_char(col, row, '.', QColor(200, 200, 255))
                        else: self.set_char(col, row, ':', QColor(sr//2, sg//2, sb//2))
                    else:
                        glow = (0.2 - depth) / 0.2
                        gr = int(sr + 50 * glow); gg2 = int(sg + 20 * glow); gb = int(sb + 5 * glow)
                        self.set_char(col, row, ':', QColor(min(255,gr), min(255,gg2), min(255,gb)))
                elif row >= wall_bottom:
                    half = VIEW_ROWS / 2
                    depth = (row - half) / half
                    fd = 1.0 / max(depth, 0.01)
                    ff = max(0, 1 - fd / 7)
                    fr = int(FLOOR_COLOR.red() * ff + 5 * (1 - ff))
                    fg = int(FLOOR_COLOR.green() * ff + 5 * (1 - ff))
                    fb = int(FLOOR_COLOR.blue() * ff + 15 * (1 - ff))
                    if g.muzzle_flash > 0:
                        flash_amt = g.muzzle_flash * max(0, 1.0 - fd / 4.0)
                        fr = min(255, int(fr + 255 * flash_amt * 0.8))
                        fg = min(255, int(fg + 220 * flash_amt * 0.8))
                        fb = min(255, int(fb + 100 * flash_amt * 0.8))
                    fc = QColor(fr, fg, fb)
                    if fd > 6: ch = ' '
                    elif fd > 4: ch = '.'
                    elif fd > 2: ch = ':'
                    else: ch = '='
                    self.set_char(col, row, ch, fc)
                else:
                    tex_y_f = (row - wall_top) / max(wall_height, 1.0)
                    tex_y = int(tex_y_f * 64 * TEXTURE_SCALE) % 64
                    tx = int(wall_x * 64) % 64
                    ch, br, bg, bb = tex[tex_y][tx]
                    if perp_dist > 14:
                        if ch in '#%@~H': ch = '+'
                        elif ch in '|=': ch = ':'
                        elif ch == 'o': ch = '.'
                        elif ch == '.': ch = ':'
                    elif perp_dist > 9:
                        if ch in '#%@~H': ch = '+'
                        elif ch in '|=': ch = ':'
                    fog = max(0.05, 1.0 - perp_dist / 14.0)
                    amb = 1.0 - fog
                    r = int(br * fog + sky_color.red() * amb)
                    gg = int(bg * fog + sky_color.green() * amb)
                    b = int(bb * fog + sky_color.blue() * amb)
                    if side == 0:
                        r = int(r * 0.6); gg = int(gg * 0.6); b = int(b * 0.6)
                    if g.muzzle_flash > 0:
                        flash_amt = g.muzzle_flash * max(0, 1.0 - perp_dist / 6.0)
                        r = min(255, int(r + 255 * flash_amt * 0.8))
                        gg = min(255, int(gg + 220 * flash_amt * 0.8))
                        b = min(255, int(b + 100 * flash_amt * 0.8))
                    if g.adrenaline_active > 0:
                        tint = g.adrenaline_active / 5.0
                        r = min(255, int(r + 40 * tint))
                        b = min(255, int(b + 60 * tint))
                    self.set_char(col, row, ch, QColor(r, gg, b))

        self.render_sky_overlay()
        self.render_world_sprites()
        self.render_weapon()
        if g.muzzle_flash > 0:
            self.render_muzzle_flash()
            self.render_tracer()
        self.render_crosshair()
        self.render_damage_numbers()
        if g.damage_flash > 0: self.render_damage_flash()
        if g.last_damage_dir is not None and g.damage_dir_time > 0:
            self.render_damage_indicator()
        self.render_boss_bar()
        if g.adrenaline_active > 0:
            self.render_slowmo_overlay()

    def render_sky_overlay(self):
        g = self.game
        if g is None: return
        for i, c_off in enumerate(g.cloud_offsets):
            c_y = 3 + (i % 2) * 3
            c_x = int(c_off)
            cloud_shape = ["  ___    ", " (   )   ", "(_____)__"]
            for sy, row in enumerate(cloud_shape):
                for sx, c in enumerate(row):
                    if c != ' ':
                        x = (c_x + sx) % COLS
                        y = c_y + sy
                        if y < 10:
                            self.set_char(x, y, c, QColor(60, 60, 80))
        
        for b in g.birds:
            b_x = int(b['x'])
            b_y = int(b['y'])
            if 0 <= b_x < COLS and 0 <= b_y < VIEW_ROWS:
                wing = 0 if int(time.time() * 4) % 2 == 0 else 1
                if wing == 0:
                    self.set_char(b_x, b_y, 'v', QColor(20, 20, 20))
                    if b_x + 1 < COLS: self.set_char(b_x + 1, b_y, '^', QColor(20, 20, 20))
                else:
                    self.set_char(b_x, b_y, 'V', QColor(20, 20, 20))
                    if b_x + 1 < COLS: self.set_char(b_x + 1, b_y, '_', QColor(20, 20, 20))

    def cast_ray(self, px, py, angle, map_data):
        dx = math.cos(angle); dy = math.sin(angle)
        if abs(dx) < 1e-30: dx = 1e-30 if dx >= 0 else -1e-30
        if abs(dy) < 1e-30: dy = 1e-30 if dy >= 0 else -1e-30
        map_x = int(px); map_y = int(py)
        delta_x = abs(1 / dx); delta_y = abs(1 / dy)
        if dx < 0: step_x, side_x = -1, (px - map_x) * delta_x
        else: step_x, side_x = 1, (map_x + 1.0 - px) * delta_x
        if dy < 0: step_y, side_y = -1, (py - map_y) * delta_y
        else: step_y, side_y = 1, (map_y + 1.0 - py) * delta_y
        side = 0; wall_type = 0
        for _ in range(MAX_DEPTH):
            if side_x < side_y:
                side_x += delta_x; map_x += step_x; side = 0
            else:
                side_y += delta_y; map_y += step_y; side = 1
            if map_x < 0 or map_x >= len(map_data[0]) or map_y < 0 or map_y >= len(map_data): return None
            cell = map_data[map_y][map_x]
            if cell != '0':
                wall_type = int(cell); break
        else:
            return None
        if side == 0:
            perp = side_x - delta_x; wall_x = py + perp * dy
        else:
            perp = side_y - delta_y; wall_x = px + perp * dx
        wall_x -= math.floor(wall_x)
        return perp, side, wall_type, wall_x, map_x, map_y

    def render_world_sprites(self):
        g = self.game
        if g is None: return
        sprites = []
        for e in g.enemies:
            if not e.alive and e.death_anim <= 0: continue
            d = math.hypot(e.x - g.px, e.y - g.py)
            sprites.append((d, 'enemy', e))
        for p in g.pickups:
            if p.taken: continue
            d = math.hypot(p.x - g.px, p.y - g.py)
            sprites.append((d, 'pickup', p))
        for pu in g.powerups:
            if pu.taken: continue
            d = math.hypot(pu.x - g.px, pu.y - g.py)
            sprites.append((d, 'powerup', pu))
        for b in g.barrels:
            if b.exploded: continue
            d = math.hypot(b.x - g.px, b.y - g.py)
            sprites.append((d, 'barrel', b))
        for p in g.projectiles:
            if not p.alive: continue
            d = math.hypot(p.x - g.px, p.y - g.py)
            sprites.append((d, 'proj', p))
        for gr in g.grenades_list:
            if not gr.alive: continue
            d = math.hypot(gr.x - g.px, gr.y - g.py)
            sprites.append((d, 'grenade', gr))
        for prt in g.particles:
            d = math.hypot(prt.x - g.px, prt.y - g.py)
            sprites.append((d, 'particle', prt))
        sprites.sort(key=lambda t: -t[0])
        for dist, kind, obj in sprites:
            self.render_sprite(kind, obj, dist)

    def render_sprite(self, kind, obj, dist):
        g = self.game
        if dist > 22 and kind not in ('particle',): return
        if dist > 14 and kind == 'particle': return
        if dist < 0.05: return

        dx = obj.x - g.px; dy = obj.y - g.py
        if kind in ('enemy', 'pickup', 'powerup', 'barrel', 'grenade'):
            if g.wall_between(obj.x, obj.y): return

        ea = math.atan2(dy, dx)
        diff = (ea - g.angle + math.pi) % (2 * math.pi) - math.pi
        if abs(diff) > HALF_FOV + 0.3: return

        screen_x = (diff + HALF_FOV) / FOV * COLS
        scale = max(0.3, VIEW_ROWS / max(dist, 0.5) / 2.5)

        if kind == 'enemy':
            sprite = obj.sprite
            sp_h, sp_w = len(sprite), len(sprite[0])
            sh, sw = int(sp_h * scale), int(sp_w * scale)
            cy = VIEW_ROWS // 2
            sx0, sy0 = int(screen_x - sw / 2), cy - sh // 2
            if not obj.alive and obj.death_anim > 0:
                t = 1.0 - obj.death_anim / 0.5
                sh2 = max(1, int(sh * (1 - t * 0.7)))
                sy0 += int(sh * t * 0.5)
                sh = sh2
            fog = max(0.2, 1 - dist / 14); amb = 1.0 - fog
            sr, sg, sb = g.sky_tint
            if obj.hit_flash > 0.05: 
                r, gg, b = 255, 255, 255
            else: 
                r, gg, b = obj.color
                r = int(r * fog + sr * amb)
                gg = int(gg * fog + sg * amb)
                b = int(b * fog + sb * amb)
            if g.muzzle_flash > 0:
                fa = g.muzzle_flash * max(0, 1.0 - dist / 6.0)
                r = min(255, int(r + 255 * fa * 0.8))
                gg = min(255, int(gg + 220 * fa * 0.8))
                b = min(255, int(b + 100 * fa * 0.8))
            color = QColor(r, gg, b)
            
            sy_start = max(0, -sy0)
            sy_end = min(sh, VIEW_ROWS - sy0)
            sx_start = max(0, -sx0)
            sx_end = min(sw, COLS - sx0)
            
            for sy in range(sy_start, sy_end):
                tsy = min(int(sy / scale), sp_h - 1)
                for sx in range(sx_start, sx_end):
                    tsx = min(int(sx / scale), sp_w - 1)
                    c = sprite[tsy][tsx]
                    if c == ' ': continue
                    if obj.hit_flash > 0.05 and (tsx + tsy) % 2 == 0: c = '#'
                    bx, by = sx0 + sx, sy0 + sy
                    if dist < self.depth_buffer[bx]:
                        self.set_char(bx, by, c, color)
            if obj.alive:
                bw = max(3, sw)
                bx0, by = int(screen_x - bw / 2), sy0 - 1
                hr = obj.health / obj.max_health
                for i in range(bw):
                    x = bx0 + i
                    if x < 0 or x >= COLS or by < 0 or by >= ROWS: continue
                    if i < bw * hr: self.set_char(x, by, '=', QColor(255, 50, 50))
                    else: self.set_char(x, by, '-', QColor(80, 80, 80))
        elif kind in ('pickup', 'powerup'):
            sprite = obj.sprite
            sp_h, sp_w = len(sprite), len(sprite[0])
            sh, sw = max(2, int(sp_h * scale)), max(2, int(sp_w * scale))
            cy = VIEW_ROWS // 2
            bob_y = int(math.sin(obj.bob) * scale)
            sx0, sy0 = int(screen_x - sw / 2), cy - sh // 2 + bob_y
            fog = max(0.2, 1 - dist / 14); amb = 1.0 - fog
            r, gg, b = obj.color
            sr, sg, sb = g.sky_tint
            r = int(r * fog + sr * amb)
            gg = int(gg * fog + sg * amb)
            b = int(b * fog + sb * amb)
            if kind == 'powerup':
                pulse = abs(math.sin(obj.bob * 2)) * 80
                r = min(255, int(r + pulse))
                gg = min(255, int(gg + pulse))
                b = min(255, int(b + pulse))
            color = QColor(r, gg, b)
            
            sy_start = max(0, -sy0)
            sy_end = min(sh, VIEW_ROWS - sy0)
            sx_start = max(0, -sx0)
            sx_end = min(sw, COLS - sx0)
            
            for sy in range(sy_start, sy_end):
                tsy = min(int(sy / scale), sp_h - 1)
                for sx in range(sx_start, sx_end):
                    tsx = min(int(sx / scale), sp_w - 1)
                    c = sprite[tsy][tsx]
                    if c == ' ': continue
                    bx = sx0 + sx
                    by = sy0 + sy
                    if dist < self.depth_buffer[bx]:
                        self.set_char(bx, by, c, color)
        elif kind == 'barrel':
            sprite = obj.SPRITE
            sp_h, sp_w = len(sprite), len(sprite[0])
            sh, sw = int(sp_h * scale), int(sp_w * scale)
            cy = VIEW_ROWS // 2
            sx0, sy0 = int(screen_x - sw / 2), cy - sh // 2
            fog = max(0.2, 1 - dist / 14); amb = 1.0 - fog
            r, gg, b = 200, 150, 50
            sr, sg, sb = g.sky_tint
            r = int(r * fog + sr * amb)
            gg = int(gg * fog + sg * amb)
            b = int(b * fog + sb * amb)
            color = QColor(r, gg, b)
            
            sy_start = max(0, -sy0)
            sy_end = min(sh, VIEW_ROWS - sy0)
            sx_start = max(0, -sx0)
            sx_end = min(sw, COLS - sx0)
            
            for sy in range(sy_start, sy_end):
                tsy = min(int(sy / scale), sp_h - 1)
                for sx in range(sx_start, sx_end):
                    tsx = min(int(sx / scale), sp_w - 1)
                    c = sprite[tsy][tsx]
                    if c == ' ': continue
                    bx = sx0 + sx
                    by = sy0 + sy
                    if dist < self.depth_buffer[bx]:
                        self.set_char(bx, by, c, color)
        elif kind == 'grenade':
            sh, sw = max(1, int(2 * scale)), max(1, int(3 * scale))
            cy = VIEW_ROWS // 2
            sx0, sy0 = int(screen_x - sw / 2), cy - sh // 2
            blink = (math.sin(obj.timer * 15) > 0)
            color = QColor(255, 50, 50) if blink else QColor(180, 30, 30)
            for sy in range(sh):
                for sx in range(sw):
                    c = 'G' if (sx + sy) % 2 == 0 else 'o'
                    bx, by = sx0 + sx, sy0 + sy
                    if 0 <= bx < COLS and 0 <= by < VIEW_ROWS:
                        if dist < self.depth_buffer[bx]:
                            self.set_char(bx, by, c, color)
        elif kind == 'proj':
            sh, sw = max(2, int(3 * scale)), max(2, int(3 * scale))
            cy = VIEW_ROWS // 2
            sx0, sy0 = int(screen_x - sw / 2), cy - sh // 2
            fog = max(0.3, 1 - dist / 14)
            sr, sg, sb = g.sky_tint
            r = int(255 * fog + sr * (1 - fog))
            gg = int(100 * fog + sg * (1 - fog))
            b = int(50 * fog + sb * (1 - fog))
            color = QColor(r, gg, b)
            for sy in range(sh):
                for sx in range(sw):
                    c = '*' if (sx + sy) % 2 == 0 else 'o'
                    bx, by = sx0 + sx, sy0 + sy
                    if 0 <= bx < COLS and 0 <= by < VIEW_ROWS:
                        if dist < self.depth_buffer[bx]:
                            self.set_char(bx, by, c, color)
        elif kind == 'particle':
            screen_x_int = int(screen_x)
            cy = VIEW_ROWS // 2
            sy = cy + 1
            if 0 <= screen_x_int < COLS and 0 <= sy < VIEW_ROWS:
                if dist < self.depth_buffer[screen_x_int]:
                    alpha = max(0.3, obj.life / obj.max_life)
                    r = int(obj.color.red() * alpha)
                    gg = int(obj.color.green() * alpha)
                    b = int(obj.color.blue() * alpha)
                    self.set_char(screen_x_int, sy, obj.char, QColor(r, gg, b))

    def render_weapon(self):
        g = self.game
        gun = WEAPON_SPRITES.get(g.current_weapon, WEAPON_SPRITES['laser'])
        bob_x = math.cos(g.bob_time) * 2.0
        bob_y = abs(math.sin(g.bob_time)) * 2.0
        recoil_y = int(g.recoil * 4)
        gun_h = len(gun)
        gx = COLS // 2 - (len(gun[0]) // 2) + int(bob_x)
        gy = VIEW_ROWS - gun_h + int(bob_y) + recoil_y
        
        if gy < 0: gy = 0
        
        if g.has_powerup('overclock'):
            color = QColor(220, 100, 220) if g.ammo > 0 else QColor(70, 70, 70)
        elif g.has_powerup('rage'):
            color = QColor(255, 100, 100) if g.ammo > 0 else QColor(70, 70, 70)
        else:
            color = QColor(170, 170, 180) if g.ammo > 0 else QColor(70, 70, 70)
            
        for sy, row in enumerate(gun):
            for sx, c in enumerate(row):
                if c != ' ':
                    if gy + sy < VIEW_ROWS:
                        self.set_char(gx + sx, gy + sy, c, color)

    def render_muzzle_flash(self):
        g = self.game
        flash_frames = [
            ["      *      ", "     ***     ", "    *****    ", "   *******   ", "   *******   ", "    *****    ", "     ***     ", "      *      "],
            ["    * * *    ", "   * * * *   ", "    *****    ", "   * * * *   ", "    * * *    ", "     * *     ", "      *      "],
            [" *   * *   * ", "  *  * *  *  ", "   * * * *   ", "    *****    ", "   * * * *   ", "  *  * *  *  ", " *   * *   * "]
        ]
        flash = flash_frames[g.flash_frame]
        bob_x = math.cos(g.bob_time) * 2.0
        bob_y = abs(math.sin(g.bob_time)) * 2.0
        recoil_y = int(g.recoil * 4)
        
        gun_len = len(WEAPON_SPRITES[g.current_weapon])
        gy = VIEW_ROWS - gun_len + int(bob_y) + recoil_y
        if gy < 0: gy = 0
        
        fx = COLS // 2 - 6 + int(bob_x)
        fy = gy - 4
        if fy < 0: fy = 0
        
        color = QColor(255, 230, 120)
        for sy, row in enumerate(flash):
            for sx, c in enumerate(row):
                if c != ' ': self.set_char(fx + sx, fy + sy, c, color)

    def render_tracer(self):
        g = self.game
        bob_x = math.cos(g.bob_time) * 2.0
        bob_y = abs(math.sin(g.bob_time)) * 2.0
        recoil_y = int(g.recoil * 4)
        
        gun_len = len(WEAPON_SPRITES[g.current_weapon])
        gy = VIEW_ROWS - gun_len + int(bob_y) + recoil_y
        if gy < 0: gy = 0
        
        tx0 = COLS // 2 + int(bob_x)
        ty0 = gy - 3
        tx1 = COLS // 2
        ty1 = VIEW_ROWS // 2
        
        for i in range(8):
            t = i / 8.0
            tx = int(tx0 + (tx1 - tx0) * t + random.uniform(-1, 1))
            ty = int(ty0 + (ty1 - ty0) * t)
            if 0 <= tx < COLS and 0 <= ty < VIEW_ROWS:
                self.set_char(tx, ty, '|', QColor(255, 255, 150))

    def render_crosshair(self):
        cx, cy = COLS // 2, VIEW_ROWS // 2
        g = self.game
        if g.kill_marker_time > 0:
            c = QColor(255, 80, 80)
            self.set_char(cx, cy, 'X', c)
            self.set_char(cx - 1, cy - 1, '\\', c)
            self.set_char(cx + 1, cy - 1, '/', c)
            self.set_char(cx - 1, cy + 1, '/', c)
            self.set_char(cx + 1, cy + 1, '\\', c)
            return
        if g.hit_marker_time > 0:
            c = QColor(255, 200, 100)
            self.set_char(cx - 1, cy - 1, '\\', c)
            self.set_char(cx + 1, cy - 1, '/', c)
            self.set_char(cx - 1, cy + 1, '/', c)
            self.set_char(cx + 1, cy + 1, '\\', c)
        c = QColor(255, 255, 100)
        self.set_char(cx, cy, '+', c)
        self.set_char(cx - 2, cy, '-', c)
        self.set_char(cx + 2, cy, '-', c)

    def render_damage_numbers(self):
        g = self.game
        for dn in g.damage_numbers:
            if dn.life <= 0: continue
            alpha = min(1.0, dn.life / 0.4)
            if dn.crit:
                col = QColor(int(255 * alpha), int(80 * alpha), int(80 * alpha))
                text = f"!{dn.amount}!"
            else:
                col = QColor(int(255 * alpha), int(220 * alpha), int(100 * alpha))
                text = str(dn.amount)
            x = dn.sx - len(text) // 2
            y = int(dn.sy)
            for i, ch in enumerate(text):
                if 0 <= x + i < COLS and 0 <= y < VIEW_ROWS:
                    self.set_char(x + i, y, ch, col)

    def render_damage_flash(self):
        a = self.game.damage_flash / 0.4
        if a <= 0: return
        col = QColor(int(200 * a), int(20 * a), int(200 * a)) # Cyberpunk glitch magenta
        for x in range(COLS):
            if random.random() < 0.4 + 0.4 * a:
                self.set_char(x, 0, random.choice('#%@&'), col)
                glitch_len = random.randint(1, 5)
                for d in range(1, glitch_len):
                    if random.random() < 0.8:
                        self.set_char(x, d, random.choice('|/\\'), col)
                    else:
                        break
        for x in range(COLS):
            if random.random() < 0.4 + 0.4 * a:
                self.set_char(x, VIEW_ROWS - 1, random.choice('#%@&'), col)
                glitch_len = random.randint(1, 5)
                for d in range(1, glitch_len):
                    if random.random() < 0.8:
                        self.set_char(x, VIEW_ROWS - 1 - d, random.choice('|/\\'), col)
                    else:
                        break
        for y in range(VIEW_ROWS):
            if random.random() < 0.3 * a:
                self.set_char(0, y, random.choice('#%&'), col)
            if random.random() < 0.3 * a:
                self.set_char(COLS - 1, y, random.choice('#%&'), col)

    def render_damage_indicator(self):
        g = self.game
        if g.last_damage_dir is None: return
        alpha = g.damage_dir_time / 1.2
        col = QColor(int(255 * alpha), int(50 * alpha), int(50 * alpha))
        cx, cy = COLS // 2, VIEW_ROWS // 2
        d = g.last_damage_dir
        r = 8
        ax = cx + int(math.cos(d) * r)
        ay = cy + int(math.sin(d) * r * 0.5)
        if -math.pi/4 <= d < math.pi/4: ach = '>'
        elif math.pi/4 <= d < 3*math.pi/4: ach = 'v'
        elif d >= 3*math.pi/4 or d < -3*math.pi/4: ach = '<'
        else: ach = '^'
        if 0 <= ax < COLS and 0 <= ay < VIEW_ROWS:
            self.set_char(ax, ay, ach, col)

    def render_boss_bar(self):
        g = self.game
        boss = None
        for e in g.enemies:
            if e.alive and e.type == 'mech':
                boss = e; break
        if boss is None: return
        bar_w = 60
        bar_x = (COLS - bar_w) // 2
        bar_y = 1
        hr = boss.health / boss.max_health
        self.draw_text(bar_x - 6, bar_y, "MECH", QColor(255, 50, 50))
        for i in range(bar_w):
            ch = '#' if i < hr * bar_w else '-'
            col = QColor(255, 50, 50) if i < hr * bar_w else QColor(80, 30, 30)
            self.set_char(bar_x + i, bar_y, ch, col)
        self.set_char(bar_x - 1, bar_y, '[', QColor(255, 80, 80))
        self.set_char(bar_x + bar_w, bar_y, ']', QColor(255, 80, 80))

    def render_slowmo_overlay(self):
        g = self.game
        intensity = g.adrenaline_active / 5.0
        col = QColor(int(80 * intensity), int(80 * intensity), int(180 * intensity))
        for x in range(COLS):
            self.set_char(x, 0, '~', col)
            self.set_char(x, VIEW_ROWS - 1, '~', col)

    def render_hud(self):
        g = self.game
        if g is None: return
        hy = VIEW_ROWS
        self.fill_rect(0, hy, COLS, ROWS, ' ', HUD_BG)
        
        for x in range(COLS):
            self.set_char(x, hy, '=', HUD_COLOR)
            self.set_char(x, ROWS-1, '=', HUD_COLOR)
        for y in range(hy, ROWS):
            self.set_char(0, y, '|', HUD_COLOR)
            self.set_char(COLS-1, y, '|', HUD_COLOR)
        self.set_char(0, hy, '+', HUD_COLOR)
        self.set_char(COLS-1, hy, '+', HUD_COLOR)
        self.set_char(0, ROWS-1, '+', HUD_COLOR)
        self.set_char(COLS-1, ROWS-1, '+', HUD_COLOR)

        hc = QColor(255, 100, 100) if g.health < 30 else QColor(100, 255, 100)
        self.draw_text(2, hy + 1, f"HP:{g.health:3d}/{g.max_health:3d}", hc)
        hp_frac = g.health / g.max_health
        for i in range(20):
            ch = '#' if i < hp_frac * 20 else '-'
            col = QColor(255, 60, 60) if i < hp_frac * 20 else QColor(60, 60, 60)
            self.set_char(15 + i, hy + 1, ch, col)

        st_frac = g.stamina / g.max_stamina
        for i in range(20):
            ch = '=' if i < st_frac * 20 else '-'
            col = QColor(100, 200, 255) if i < st_frac * 20 else QColor(40, 40, 60)
            self.set_char(15 + i, hy + 2, ch, col)

        ac = QColor(255, 100, 100) if g.ammo == 0 else QColor(255, 220, 100)
        self.draw_text(40, hy + 1, f"ENG:{g.ammo:3d}", ac)

        gc = QColor(255, 100, 100) if g.grenades == 0 else QColor(100, 200, 255)
        self.draw_text(52, hy + 1, f"EMP:{g.grenades}", gc)

        wname = WEAPONS[g.current_weapon]['name']
        self.draw_text(62, hy + 1, f"WPN:{wname}", QColor(255, 200, 200))

        self.draw_text(2, hy + 3, f"SCR:{g.score:6d}", QColor(255, 255, 255))
        alive = sum(1 for e in g.enemies if e.alive)
        self.draw_text(20, hy + 3, f"TGT:{alive}/{g.total_enemies}", QColor(255, 100, 100))
        if g.combo > 1:
            combo_col = QColor(255, 200, 50) if g.combo_timer > 1 else QColor(255, 100, 50)
            self.draw_text(40, hy + 3, f"COMBO x{g.combo}!", combo_col)

        nearest, nd = g.find_nearest_enemy()
        if nearest is not None and nd < 30:
            dx = nearest.x - g.px; dy = nearest.y - g.py
            ang = math.atan2(dy, dx)
            rel = (ang - g.angle + math.pi) % (2 * math.pi) - math.pi
            if -math.pi/4 <= rel < math.pi/4: pch = '>'
            elif math.pi/4 <= rel < 3*math.pi/4: pch = 'v'
            elif rel >= 3*math.pi/4 or rel < -3*math.pi/4: pch = '<'
            else: pch = '^'
            self.draw_text(72, hy + 1, f"NEAR:{pch} {nd:4.1f}m", QColor(255, 150, 150))

        self.draw_text(2, hy + 4, "[1]LSR [2]PLS [3]RLG [G]EMP [Q]FOC", QColor(120, 120, 120))
        widx = WEAPON_ORDER.index(g.current_weapon)
        starts = [2, 9, 16]
        self.set_char(starts[widx] - 1, hy + 4, '>', QColor(255, 255, 100))
        self.draw_text(44, hy + 4, f"THREAT: {DIFFICULTY[g.difficulty]['label']}  SKY: {g.sky_name}", QColor(150, 150, 200))

        self.render_minimap(COLS - 22, hy + 1, 20, 6)

        px = 2
        py = hy + 5
        for name, t in g.active_powerups.items():
            spec = POWERUP_TYPES[name]
            col = QColor(*spec['color'])
            self.draw_text(px, py, f"{spec['name']}:{t:.1f}s", col)
            px += len(spec['name']) + 8
            if px > COLS - 25: break

        adr_frac = g.adrenaline / g.adrenaline_max
        ad_color = QColor(255, 200, 100) if g.adrenaline >= g.adrenaline_max else QColor(100, 200, 255)
        self.draw_text(40, hy + 5, "FOC:", ad_color)
        for i in range(15):
            ch = '#' if i < adr_frac * 15 else '-'
            col = ad_color if i < adr_frac * 15 else QColor(40, 40, 60)
            self.set_char(45 + i, hy + 5, ch, col)
        if g.adrenaline >= g.adrenaline_max:
            self.draw_text(61, hy + 5, "[Q]!", QColor(255, 200, 100))
        elif g.adrenaline_active > 0:
            self.draw_text(61, hy + 5, "SLOW!", QColor(100, 150, 255))

        if g.message_time > 0:
            mx = (COLS - 22 - len(g.message)) // 2
            self.draw_text(mx, hy + 6, g.message, QColor(255, 255, 0))
        elif g.score == 0 and g.ammo == 50:
            hint = "WASD:Move  L/R:Turn  SHIFT:Run  SPACE:Fire  G:EMP  Q:Focus  P:Pause  ESC:Quit"
            hx = (COLS - 22 - len(hint)) // 2
            self.draw_text(hx, hy + 6, hint, QColor(120, 120, 120))

        # Cybernetic Shield HUD Icon (Replaces DOOM Face)
        fc = QColor(100, 255, 100)
        if g.health < 75: fc = QColor(255, 255, 100)
        if g.health < 40: fc = QColor(255, 100, 100)
        if g.health <= 0: fc = QColor(150, 0, 0)
        if g.has_powerup('rage'): fc = QColor(255, 50, 50)
        if g.has_powerup('overclock'): fc = QColor(220, 100, 220)

        icon = [
            r"  /\\  ",
            r" /  \\ ",
            r"| ## |",
            r"| ## |",
            r" \\__/ "
        ]
        if g.health <= 0:
            icon = [
                r"  /\\  ",
                r" /  \\ ",
                r"| ## |",
                r"| -- |",
                r" \\__/ "
            ]
            
        fx, fy = 64, hy + 2
        for sy, row in enumerate(icon):
            for sx, c in enumerate(row):
                if c != ' ': self.set_char(fx + sx, fy + sy, c, fc)

        elapsed = (g.end_time if (g.game_over or g.victory) else time.time()) - g.start_time
        mins = int(elapsed) // 60; secs = int(elapsed) % 60
        self.draw_text(2, hy + 6, f"TIME:{mins:02d}:{secs:02d}", QColor(150, 200, 255))
        self.draw_text(14, hy + 6, f"KILLS:{g.kills}", QColor(255, 150, 150))
        if g.is_new_highscore:
            self.draw_text(24, hy + 6, "**NEW HIGH SCORE!**", QColor(255, 255, 100))

    def render_minimap(self, x0, y0, w, h):
        g = self.game
        if g is None: return
        for x in range(w + 2):
            self.set_char(x0 + x, y0, '=', HUD_COLOR)
            self.set_char(x0 + x, y0 + h + 1, '=', HUD_COLOR)
        for y in range(h + 2):
            self.set_char(x0, y0 + y, '|', HUD_COLOR)
            self.set_char(x0 + w + 1, y0 + y, '|', HUD_COLOR)
        self.set_char(x0, y0, '+', HUD_COLOR)
        self.set_char(x0+w+1, y0, '+', HUD_COLOR)
        self.set_char(x0, y0+h+1, '+', HUD_COLOR)
        self.set_char(x0+w+1, y0+h+1, '+', HUD_COLOR)
        self.draw_text(x0 + 1, y0, "MAP", HUD_COLOR)

        cell_w = w; cell_h = h
        pmx = cell_w // 2; pmy = cell_h // 2
        for my in range(cell_h):
            for mx in range(cell_w):
                wx = int(g.px) + (mx - pmx)
                wy = int(g.py) + (my - pmy)
                if 0 <= wx < g.map_w and 0 <= wy < g.map_h:
                    cell = g.map_data[wy][wx]
                    if cell != '0':
                        self.set_char(x0 + 1 + mx, y0 + 1 + my, '#', QColor(80, 80, 100))
                    else:
                        self.set_char(x0 + 1 + mx, y0 + 1 + my, '.', QColor(40, 40, 50))

        for e in g.enemies:
            if not e.alive: continue
            mx = int(e.x - g.px) + pmx; my = int(e.y - g.py) + pmy
            if 0 <= mx < cell_w and 0 <= my < cell_h:
                ch = 'E'
                if e.type == 'mech': ch = 'B'
                elif e.type == 'turret': ch = 'R'
                elif e.type == 'android': ch = 'D'
                elif e.type == 'spider': ch = 'S'
                elif e.type == 'cyborg': ch = 'T'
                col = QColor(*e.color)
                self.set_char(x0 + 1 + mx, y0 + 1 + my, ch, col)

        for p in g.pickups:
            if p.taken: continue
            mx = int(p.x - g.px) + pmx; my = int(p.y - g.py) + pmy
            if 0 <= mx < cell_w and 0 <= my < cell_h:
                if p.kind == 'health': ch = '+'; col = QColor(100, 255, 100)
                elif p.kind == 'ammo': ch = 'E'; col = QColor(255, 220, 100)
                else: ch = 'G'; col = QColor(100, 200, 255)
                self.set_char(x0 + 1 + mx, y0 + 1 + my, ch, col)

        for pu in g.powerups:
            if pu.taken: continue
            mx = int(pu.x - g.px) + pmx; my = int(pu.y - g.py) + pmy
            if 0 <= mx < cell_w and 0 <= my < cell_h:
                col = QColor(*pu.color)
                self.set_char(x0 + 1 + mx, y0 + 1 + my, 'P', col)

        for b in g.barrels:
            if b.exploded: continue
            mx = int(b.x - g.px) + pmx; my = int(b.y - g.py) + pmy
            if 0 <= mx < cell_w and 0 <= my < cell_h:
                self.set_char(x0 + 1 + mx, y0 + 1 + my, 'O', QColor(255, 150, 50))

        a = g.angle
        if -math.pi/4 <= a < math.pi/4: pch = '>'
        elif math.pi/4 <= a < 3*math.pi/4: pch = 'v'
        elif a >= 3*math.pi/4 or a < -3*math.pi/4: pch = '<'
        else: pch = '^'
        self.set_char(x0 + 1 + pmx, y0 + 1 + pmy, pch, QColor(255, 255, 100))

    def render_menu(self):
        for i in range(COLS * ROWS): self.buffer[i] = (' ', QColor(5, 5, 15))
        random.seed(42)
        for _ in range(60):
            x = random.randint(0, COLS-1); y = random.randint(0, ROWS-1)
            if random.random() < 0.3: self.set_char(x, y, '*', QColor(255, 255, 255))
            else: self.set_char(x, y, '.', QColor(150, 150, 200))
        random.seed()

        title_art = [
            " #   #  ###   ###   ###  # ",
            " #   # #   # #   # #     # ",
            " #   # #   # #     #     # ",
            " ####  #   # #     ####  # ",
            " #   # #   # #     #     # ",
            " #   # #   # #   # #     # ",
            " #   #  ###   ###   ###  # "
        ]
        pulse = abs(math.sin(self.menu_time * 2))
        title_col = QColor(int(50 + 50 * pulse), int(200 * (0.7 + 0.3 * pulse)), int(255 * (0.7 + 0.3 * pulse)))
        start_y = 3
        for i, line in enumerate(title_art):
            x = (COLS - len(line)) // 2
            self.draw_text(x, start_y + i, line, title_col)
            
        subtitle = "NEON PROTOCOL - ENHANCED EDITION v7"
        self.draw_text((COLS - len(subtitle)) // 2, start_y + len(title_art) + 1, subtitle, QColor(80, 200, 255))

        city_skyline = [
            "       |  |        |  |        |    |        |  |          ",
            "       |  |__      |  |____    |    |        |  |__         ",
            "      _|____|_    _|______|   |____|       _|____|_        "
        ]
        sky_y = ROWS - 4
        for i, line in enumerate(city_skyline):
            self.draw_text((COLS - len(line)) // 2, sky_y + i, line, QColor(100, 100, 120))

        diff_y = start_y + len(title_art) + 3
        self.draw_text((COLS - 20) // 2, diff_y, "SELECT THREAT LEVEL:", QColor(255, 255, 255))

        for i, d in enumerate(DIFFICULTY_ORDER):
            dy = diff_y + 2 + i
            prefix = ">" if i == self.menu_selection else " "
            label = DIFFICULTY[d]['label']
            hi = self.highscores.get(d, 0)
            info = f"  {prefix}[{i+1}] {label:12s} EN:{DIFFICULTY[d]['enemy_count']:2d} HP:{DIFFICULTY[d]['player_health']:3d} HI:{hi:6d}"
            col = QColor(80, 200, 255) if i == self.menu_selection else QColor(180, 180, 180)
            mx = (COLS - len(info)) // 2
            self.draw_text(mx, dy, info, col)

        hint_y = ROWS - 7
        if not self.sound.enabled:
            hints = [
                "Sound disabled (install pygame & numpy)",
                "Use 1/2/3/4 or Up/Down to select threat level",
                "Press SPACE or ENTER to start",
                "Press ESC to quit",
                "Controls: WASD move, L/R turn, SHIFT sprint, SPACE fire",
                "G: EMP grenade, Q: Focus time, 1/2/3 weapon, P: pause, R: restart",
            ]
        else:
            hints = [
                "Use 1/2/3/4 or Up/Down to select threat level",
                "Press SPACE or ENTER to start",
                "Press ESC to quit",
                "",
                "Controls: WASD move, L/R turn, SHIFT sprint, SPACE fire",
                "G: EMP grenade, Q: Focus time, 1/2/3 weapon, P: pause, R: restart",
            ]
        for i, h in enumerate(hints):
            col = QColor(120, 120, 120)
            if i == 1: col = QColor(200, 200, 200)
            if i == 5: col = QColor(150, 200, 255)
            self.draw_text((COLS - len(h)) // 2, hint_y + i, h, col)

    def render_pause_overlay(self):
        hy = VIEW_ROWS // 2
        for x in range(COLS):
            self.set_char(x, hy - 3, '=', QColor(80, 80, 80))
            self.set_char(x, hy + 3, '=', QColor(80, 80, 80))
        for y in range(hy - 3, hy + 4):
            self.set_char(10, y, '|', QColor(80, 80, 80))
            self.set_char(COLS - 11, y, '|', QColor(80, 80, 80))
        self.set_char(10, hy - 3, '+', QColor(80, 80, 80))
        self.set_char(COLS - 11, hy - 3, '+', QColor(80, 80, 80))
        self.set_char(10, hy + 3, '+', QColor(80, 80, 80))
        self.set_char(COLS - 11, hy + 3, '+', QColor(80, 80, 80))
        self.draw_text((COLS - 6) // 2, hy - 1, "PAUSED", QColor(255, 255, 100))
        self.draw_text((COLS - 30) // 2, hy + 1, "Press P to resume, R for new map", QColor(180, 180, 180))

    def render_end_overlay(self, title, color):
        g = self.game
        bx0 = 10; by0 = 5
        bx1 = COLS - 10; by1 = ROWS - 5
        for x in range(bx0, bx1):
            self.set_char(x, by0, '=', color)
            self.set_char(x, by1, '=', color)
        for y in range(by0, by1):
            self.set_char(bx0, y, '|', color)
            self.set_char(bx1, y, '|', color)
        self.set_char(bx0, by0, '+', color)
        self.set_char(bx1, by0, '+', color)
        self.set_char(bx0, by1, '+', color)
        self.set_char(bx1, by1, '+', color)
        
        art = []
        if title == "SYSTEM FAILURE":
            art = [
                "      _______      ",
                "    .-'       '-.   ",
                "   /  _       _  \  ",
                "  |  (X)     (X)  |  ",
                "  |      <       |  ",
                "   \    \___/    /  ",
                "    '-._______.-'   ",
                "      | | | | |     "
            ]
            art_col = QColor(60, 0, 0)
        else:
            art = [
                "      *       ",
                "     ***      ",
                "    *****     ",
                "   *******    ",
                "  *********   ",
                "   *******    ",
                "    *****     ",
                "     ***      ",
                "      *       "
            ]
            art_col = QColor(0, 60, 0)
        
        art_x = (COLS - len(art[0])) // 2
        art_y = by0 + 2
        for i, line in enumerate(art):
            self.draw_text(art_x, art_y + i, line, art_col)

        tx = (COLS - len(title)) // 2
        self.draw_text(tx, by0 + 2, title, color)
        
        if g.is_new_highscore:
            nh = "** NEW HIGH SCORE! **"
            self.draw_text((COLS - len(nh)) // 2, by0 + 3, nh, QColor(255, 255, 100))
            
        elapsed = g.end_time - g.start_time
        mins = int(elapsed) // 60; secs = int(elapsed) % 60
        accuracy = (g.shots_hit / g.shots_fired * 100) if g.shots_fired > 0 else 0
        stats = [
            f"SCORE:       {g.score}",
            f"KILLS:       {g.kills} / {g.total_enemies}",
            f"TIME:        {mins:02d}:{secs:02d}",
            f"ACCURACY:    {accuracy:.1f}%",
            f"SHOTS FIRED: {g.shots_fired}",
            f"CRITS:       {g.crits}",
            f"BARREL KILLS:{g.barrel_kills}",
            f"EMP KILLS:   {g.grenade_kills}",
            f"MAX COMBO:   x{g.combo_max}",
            f"DIFFICULTY:  {DIFFICULTY[g.difficulty]['label']}",
        ]
        for i, s in enumerate(stats):
            sx = (COLS - len(s)) // 2 - 18
            col = QColor(255, 255, 100) if i == 0 else QColor(200, 200, 200)
            self.draw_text(sx, by0 + 5 + i, s, col)

        achs = g.compute_achievements()
        ach_x = (COLS // 2) + 5
        self.draw_text(ach_x, by0 + 4, "DEBRIEF:", QColor(255, 200, 100))
        if not achs:
            self.draw_text(ach_x, by0 + 6, "(none unlocked)", QColor(120, 120, 120))
        else:
            for i, (name, desc) in enumerate(achs[:10]):
                self.draw_text(ach_x, by0 + 6 + i, f"[*] {name}", QColor(255, 220, 100))
                self.draw_text(ach_x + 18, by0 + 6 + i, f"- {desc}", QColor(180, 180, 180))

        prompt = "Press R for new map  |  ESC to quit"
        self.draw_text((COLS - len(prompt)) // 2, by1 - 1, prompt, QColor(180, 180, 180))

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0))
        p.setFont(self.font)
        shake_x, shake_y = 0, 0
        if self.game and self.game.recoil > 0.7:
            shake_x = random.randint(-1, 1)
            shake_y = random.randint(-1, 0)
        for y in range(ROWS):
            base = y * COLS
            x = 0
            while x < COLS:
                _, color = self.buffer[base + x]
                end = x + 1
                while end < COLS and self.buffer[base + end][1] == color:
                    end += 1
                text = ''.join(self.buffer[base + i][0] for i in range(x, end))
                if text.strip():
                    p.setPen(color)
                    p.drawText(x * self.char_w + shake_x, y * self.char_h + self.ascent + shake_y, text)
                x = end

    def keyPressEvent(self, event: QKeyEvent):
        if event.isAutoRepeat(): return
        k = event.key()
        if self.state == 'menu':
            if k == Qt.Key_1: self.menu_selection = 0; self.sound.play('menu_move')
            elif k == Qt.Key_2: self.menu_selection = 1; self.sound.play('menu_move')
            elif k == Qt.Key_3: self.menu_selection = 2; self.sound.play('menu_move')
            elif k == Qt.Key_4: self.menu_selection = 3; self.sound.play('menu_move')
            elif k == Qt.Key_Up: self.menu_selection = (self.menu_selection - 1) % 4; self.sound.play('menu_move')
            elif k == Qt.Key_Down: self.menu_selection = (self.menu_selection + 1) % 4; self.sound.play('menu_move')
            elif k in (Qt.Key_Space, Qt.Key_Return):
                self.highscores = load_highscores()
                self.start_game(DIFFICULTY_ORDER[self.menu_selection])
            elif k == Qt.Key_Escape: QApplication.quit()
        elif self.state == 'playing':
            if k == Qt.Key_P:
                self.game.paused = True; self.state = 'paused'
                self.sound.play('pause')
            elif k == Qt.Key_R: self.start_game(self.game.difficulty)
            elif k == Qt.Key_1: self.game.switch_weapon('laser')
            elif k == Qt.Key_2: self.game.switch_weapon('plasma')
            elif k == Qt.Key_3: self.game.switch_weapon('railgun')
            elif k == Qt.Key_Q: self.game.activate_adrenaline()
            elif k == Qt.Key_Escape: QApplication.quit()
            else: self.game.keys.add(k)
        elif self.state == 'paused':
            if k == Qt.Key_P: 
                self.game.paused = False; self.state = 'playing'
                self.sound.play('pause')
            elif k == Qt.Key_R: self.start_game(self.game.difficulty)
            elif k == Qt.Key_Escape: QApplication.quit()
        elif self.state in ('gameover', 'victory'):
            if k == Qt.Key_R: self.start_game(self.game.difficulty)
            elif k == Qt.Key_Escape: QApplication.quit()

    def keyReleaseEvent(self, event: QKeyEvent):
        if event.isAutoRepeat(): return
        if self.state == 'playing' and self.game is not None:
            self.game.keys.discard(event.key())


# ======================== MAIN ========================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ASCII FPS: NEON PROTOCOL - ENHANCED v7")
        renderer = AsciiRenderer()
        self.setCentralWidget(renderer)
        self.setFixedSize(renderer.size())


def main():
    init_textures()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()