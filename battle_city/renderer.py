# ============================================================
# renderer.py — NES-style pixel art renderer
#
# BUG FIXES:
#   1. draw_sidebar(): sx was calculated as BORDER*2+GRID*TILE which is
#      WRONG — that double-counts the left border. Correct formula is
#      BORDER + GRID*TILE + BORDER (left_border + grid + right_border).
#      This made the sidebar draw 24px too far right, clipping it.
#   2. draw_border(): sidebar background region used BORDER+SIDEBAR_W as
#      width — this overflowed. Fixed to SIDEBAR_W only.
#   3. Explosion.draw(): radius could be 0 on first frame causing
#      pygame.draw.circle error with radius=0. Added max(1,...) guard.
#   4. _FONT_LG: exported so game.py can import it (was declared but
#      needed explicit None init before init_fonts() is called).
#   5. draw_menu(): now accepts hovered_level (1/2/3 or None) to
#      highlight the level box the mouse is over. Also returns the
#      list of (level_number, pygame.Rect) so game.py can do hit-testing.
# ============================================================
import pygame
from constants import *

# ── Tile surfaces (built once, cached) ───────────────────────
_cache = {}

def _make_tile(t):
    s = pygame.Surface((TILE, TILE))
    if t == EMPTY:
        s.fill(BLACK)
    elif t == BRICK:
        s.fill(BRICK_A)
        pygame.draw.line(s, BRICK_B, (0, TILE//2), (TILE, TILE//2), 1)
        pygame.draw.line(s, BRICK_B, (0, 0), (TILE, 0), 1)
        pygame.draw.line(s, BRICK_B, (TILE//2, 0), (TILE//2, TILE//2), 1)
        pygame.draw.line(s, BRICK_B, (TILE//4, TILE//2), (TILE//4, TILE), 1)
        pygame.draw.line(s, BRICK_B, (3*TILE//4, TILE//2), (3*TILE//4, TILE), 1)
    elif t == STEEL:
        s.fill(STEEL_B)
        hw = TILE // 2
        pygame.draw.rect(s, STEEL_A, (2, 2, hw-3, hw-3))
        pygame.draw.rect(s, STEEL_A, (hw+1, 2, hw-3, hw-3))
        pygame.draw.rect(s, STEEL_A, (2, hw+1, hw-3, hw-3))
        pygame.draw.rect(s, STEEL_A, (hw+1, hw+1, hw-3, hw-3))
        pygame.draw.rect(s, (40, 40, 80), (0, 0, TILE, TILE), 1)
    elif t == WATER:
        s.fill(WATER_B)
        for wy in range(2, TILE, 6):
            pygame.draw.line(s, WATER_A, (0, wy), (TILE, wy), 2)
    elif t == FOREST:
        s.fill(FOREST_B)
        for gy in range(3, TILE, 5):
            for gx in range(3, TILE, 5):
                pygame.draw.circle(s, FOREST_A, (gx, gy), 2)
    elif t == EAGLE:
        s.fill(BLACK)
        cx, cy = TILE//2, TILE//2
        pygame.draw.polygon(s, EAGLE_C, [(cx, cy-8), (cx-8, cy+6), (cx+8, cy+6)])
        pygame.draw.polygon(s, (100, 80, 0), [(cx, cy-8), (cx-8, cy+6), (cx+8, cy+6)], 1)
        pygame.draw.circle(s, (180, 140, 0), (cx, cy), 3)
    return s

def tile_surf(t):
    if t not in _cache: _cache[t] = _make_tile(t)
    return _cache[t]

# ── NES hatched border ────────────────────────────────────────
_border_cache = {}

def draw_border(surface):
    key = (SCREEN_W, SCREEN_H)
    if key not in _border_cache:
        bsurf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        regions = [
            (0, 0, SCREEN_W, BORDER),                         # top strip
            (0, SCREEN_H-BORDER, SCREEN_W, BORDER),           # bottom strip
            (0, 0, BORDER, SCREEN_H),                         # left strip
            (BORDER+GRID*TILE, 0, BORDER+SIDEBAR_W, SCREEN_H), # right + sidebar bg
        ]
        for rx, ry, rw, rh in regions:
            pygame.draw.rect(bsurf, NES_GRAY, (rx, ry, rw, rh))
        for i in range(-SCREEN_H, SCREEN_W, 4):
            pygame.draw.line(bsurf, NES_DARK, (i, 0), (i+SCREEN_H, SCREEN_H), 1)
        # Black playfield cutout
        pygame.draw.rect(bsurf, BLACK, (BORDER, BORDER, GRID*TILE, GRID*TILE))
        # Sidebar background (dark, not hatched)
        # BUG FIX: x = BORDER+GRID*TILE+BORDER, width = SIDEBAR_W
        pygame.draw.rect(bsurf, (30, 30, 30),
                         (BORDER+GRID*TILE+BORDER, 0, SIDEBAR_W, SCREEN_H))
        _border_cache[key] = bsurf
    surface.blit(_border_cache[key], (0, 0))

# ── Grid ─────────────────────────────────────────────────────
def draw_grid(surface, grid):
    for y in range(GRID):
        for x in range(GRID):
            surface.blit(tile_surf(grid[y][x]),
                         (PLAY_X + x*TILE, PLAY_Y + y*TILE))

# ── Tank sprite drawing ───────────────────────────────────────
def draw_tank(surface, tank):
    if not tank.alive: return
    px = PLAY_X + tank.x * TILE
    py = PLAY_Y + tank.y * TILE
    color = tank.get_color()
    T = TILE

    body = pygame.Rect(px+2, py+2, T-4, T-4)
    pygame.draw.rect(surface, color, body)
    pygame.draw.rect(surface, BLACK, body, 1)

    dark = (max(0, color[0]-60), max(0, color[1]-60), max(0, color[2]-60))
    dx, dy = tank.direction
    if dx == 0:   # facing up/down — treads on left/right
        pygame.draw.rect(surface, dark, (px+2, py+2, 3, T-4))
        pygame.draw.rect(surface, dark, (px+T-5, py+2, 3, T-4))
    else:          # facing left/right — treads on top/bottom
        pygame.draw.rect(surface, dark, (px+2, py+2, T-4, 3))
        pygame.draw.rect(surface, dark, (px+2, py+T-5, T-4, 3))

    # Barrel
    cx, cy = px+T//2, py+T//2
    bx2 = cx + dx*(T//2)
    by2 = cy + dy*(T//2)
    pygame.draw.line(surface, (30, 30, 30), (cx, cy), (bx2, by2), 4)
    pygame.draw.line(surface, WHITE, (cx, cy), (bx2, by2), 2)

    # HP pips for armor/boss
    if tank.max_hp > 1:
        for i in range(tank.hp):
            pip_c = (0, 220, 0) if i < tank.max_hp//2 else (220, 220, 0)
            pygame.draw.rect(surface, pip_c, (px+3+i*4, py+1, 3, 2))

# ── Bullet ───────────────────────────────────────────────────
def draw_bullet(surface, b):
    if not b.active: return
    px = PLAY_X + int(b.fx*TILE) + TILE//2
    py = PLAY_Y + int(b.fy*TILE) + TILE//2
    pygame.draw.circle(surface, WHITE, (px, py), 3)
    dx, dy = b.direction
    pygame.draw.circle(surface, (160, 160, 160), (px-dx*4, py-dy*4), 2)

# ── Explosion ─────────────────────────────────────────────────
class Explosion:
    FRAMES = 12
    def __init__(self, x, y):
        self.x = PLAY_X + x*TILE + TILE//2
        self.y = PLAY_Y + y*TILE + TILE//2
        self.f = 0; self.done = False
    def update(self):
        self.f += 1
        if self.f >= self.FRAMES: self.done = True
    def draw(self, surface):
        if self.done: return
        p = self.f / self.FRAMES
        # BUG FIX: radius must be >= 1 to avoid pygame error
        r = max(1, int(p * TILE * 1.6))
        c = (255, int(200*(1-p)), 0)
        pygame.draw.circle(surface, c, (self.x, self.y), r)
        if r > 5:
            pygame.draw.circle(surface, (255, 255, 200), (self.x, self.y), r//2)

# ── Spawn flash ───────────────────────────────────────────────
class SpawnFlash:
    def __init__(self, x, y):
        self.x = PLAY_X + x*TILE; self.y = PLAY_Y + y*TILE
        self.f = 0; self.done = False
    def update(self): self.f += 1; self.done = self.f > 20
    def draw(self, surface):
        if self.done: return
        a = int(255 * (1 - self.f/20))
        s = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
        s.fill((255, 255, 255, a))
        surface.blit(s, (self.x, self.y))

# ── Sidebar ───────────────────────────────────────────────────
_FONT_SM = None; _FONT_MD = None; _FONT_LG = None

def init_fonts():
    global _FONT_SM, _FONT_MD, _FONT_LG
    _FONT_SM = pygame.font.SysFont("Courier", 11, bold=True)
    _FONT_MD = pygame.font.SysFont("Courier", 14, bold=True)
    _FONT_LG = pygame.font.SysFont("Courier", 28, bold=True)

def _txt(surface, font, text, x, y, color=WHITE):
    surface.blit(font.render(text, True, color), (x, y))

def draw_sidebar(surface, player, enemies_left, active_enemies,
                 level, level_name, kills, phase=None, ab_nodes=None, no_ab_nodes=None):
    # BUG FIX: sidebar x = left_border + grid_width + right_border
    sx = BORDER + GRID*TILE + BORDER
    sw = SIDEBAR_W
    pygame.draw.rect(surface, (20, 20, 20), (sx, 0, sw, SCREEN_H))
    pygame.draw.line(surface, (80, 80, 80), (sx, 0), (sx, SCREEN_H), 2)

    f = _FONT_SM; y = 8
    _txt(surface, _FONT_MD, "BATTLE",   sx+8, y, (220, 180, 0)); y += 18
    _txt(surface, _FONT_MD, "  CITY",   sx+8, y, (220, 180, 0)); y += 22
    pygame.draw.line(surface, (80, 80, 80), (sx+4, y), (sx+sw-4, y)); y += 6

    _txt(surface, f, f"LV {level}", sx+8, y, (100, 220, 220)); y += 14
    for word in level_name.split():
        _txt(surface, f, word, sx+8, y, (160, 160, 160)); y += 13
    y += 4
    pygame.draw.line(surface, (80, 80, 80), (sx+4, y), (sx+sw-4, y)); y += 6

    _txt(surface, f, "PLAYER", sx+8, y, (220, 220, 60)); y += 13
    _txt(surface, f, f"Lives:{player.lives}", sx+8, y, WHITE); y += 13
    _txt(surface, f, f"HP:   {player.hp}", sx+8, y, (60, 220, 60)); y += 16
    pygame.draw.line(surface, (80, 80, 80), (sx+4, y), (sx+sw-4, y)); y += 6

    _txt(surface, f, "ENEMY", sx+8, y, (220, 80, 80)); y += 13
    _txt(surface, f, f"Left: {enemies_left}", sx+8, y, WHITE); y += 13
    _txt(surface, f, f"On:   {len(active_enemies)}", sx+8, y, (220, 120, 60)); y += 13
    _txt(surface, f, f"Kill: {kills}", sx+8, y, (60, 220, 60)); y += 16

    cols = 4; icon = 10; gap = 2
    for i in range(min(enemies_left, 20)):
        ix = sx + 6 + (i%cols)*(icon+gap)
        iy = y + (i//cols)*(icon+gap)
        pygame.draw.rect(surface, (180, 180, 60), (ix, iy, icon, icon))
    y += ((min(enemies_left, 20)-1)//cols + 2)*(icon+gap) + 4

    pygame.draw.line(surface, (80, 80, 80), (sx+4, y), (sx+sw-4, y)); y += 6

    if phase:
        phase_c = [(60, 220, 60), (220, 180, 0), (220, 60, 60)][phase-1]
        _txt(surface, f, f"PHASE {phase}", sx+8, y, phase_c); y += 13
    if ab_nodes is not None:
        _txt(surface, f, f"AB:{ab_nodes}", sx+8, y, (180, 100, 220)); y += 13
    if no_ab_nodes is not None:
        _txt(surface, f, f"NoAB:{no_ab_nodes}", sx+8, y, (220, 140, 60)); y += 13
        if ab_nodes and ab_nodes > 0:
            ratio = round(no_ab_nodes / ab_nodes, 1)
            _txt(surface, f, f"x{ratio}spdup", sx+8, y, (60, 220, 180)); y += 13

    y = SCREEN_H - 90
    pygame.draw.line(surface, (80, 80, 80), (sx+4, y), (sx+sw-4, y)); y += 6
    _txt(surface, f, "CONTROLS", sx+8, y, (100, 180, 220)); y += 13
    for line in ["WASD:Move", "SPC:Shoot", "R:Restart", "ESC:Quit"]:
        _txt(surface, f, line, sx+8, y, (140, 140, 140)); y += 13

# ── Overlay messages ──────────────────────────────────────────
def draw_overlay(surface, font_lg, title, sub="", sub2=""):
    ow = GRID*TILE; oh = SCREEN_H
    ov = pygame.Surface((ow, oh), pygame.SRCALPHA)
    ov.fill((0, 0, 0, 180))
    surface.blit(ov, (PLAY_X, 0))
    t = font_lg.render(title, True, (220, 180, 0))
    surface.blit(t, (PLAY_X + ow//2 - t.get_width()//2, oh//2 - 50))
    sm = pygame.font.SysFont("Courier", 16, bold=True)
    if sub:
        s = sm.render(sub, True, WHITE)
        surface.blit(s, (PLAY_X + ow//2 - s.get_width()//2, oh//2 + 10))
    if sub2:
        s2 = sm.render(sub2, True, (160, 160, 160))
        surface.blit(s2, (PLAY_X + ow//2 - s2.get_width()//2, oh//2 + 32))


# ── Menu ─────────────────────────────────────────────────────
# Returns list of (level_number, pygame.Rect) so game.py can do hit-testing.
# hovered_level: 1, 2, 3, or None — highlights that card.
def draw_menu(surface, hovered_level=None):
    surface.fill((20, 20, 20))
    lg = pygame.font.SysFont("Courier", 36, bold=True)
    md = pygame.font.SysFont("Courier", 16, bold=True)
    sm = pygame.font.SysFont("Courier", 13, bold=False)
    xs = pygame.font.SysFont("Courier", 11, bold=False)

    t = lg.render("BATTLE CITY", True, (220, 180, 0))
    surface.blit(t, (SCREEN_W//2 - t.get_width()//2, 60))
    s = md.render("AL2002 Artificial Intelligence Lab", True, (100, 200, 220))
    surface.blit(s, (SCREEN_W//2 - s.get_width()//2, 108))

    infos = [
        (1, "LEVEL 1", "Brick Maze",      "BFS + Greedy  |  Simple/Goal Agents",  (180, 180, 60)),
        (2, "LEVEL 2", "Steel Fortress",   "A* + Utility  |  Model-Based Agents",  (60,  180, 220)),
        (3, "BOSS",    "Tank Commander",   "Minimax + Alpha-Beta Pruning",          (220, 80,  80)),
    ]

    level_rects = []
    y = 180
    for lv, label, name, ai, c in infos:
        r = pygame.Rect(SCREEN_W//2 - 200, y, 400, 56)
        level_rects.append((lv, r))

        # Highlight background when hovered
        if hovered_level == lv:
            bg_col  = (50, 50, 50)
            bd_size = 3
            hint    = "  <<  CLICK TO PLAY  >>"
        else:
            bg_col  = (30, 30, 30)
            bd_size = 2
            hint    = "  click to play"

        pygame.draw.rect(surface, bg_col, r, border_radius=6)
        pygame.draw.rect(surface, c, r, bd_size, border_radius=6)

        l1 = md.render(f"{label}: {name}", True, c)
        l2 = sm.render(ai, True, (160, 160, 160) if hovered_level != lv else (220, 220, 220))
        l3 = xs.render(hint, True, c if hovered_level == lv else (80, 80, 80))

        surface.blit(l1, (r.x + 12, r.y + 6))
        surface.blit(l2, (r.x + 12, r.y + 26))
        surface.blit(l3, (r.x + 12, r.y + 42))

        y += 68

    # Bottom hint
    hint_txt = xs.render("Hover a level and click  —  or press 1 / 2 / 3", True, (100, 100, 100))
    surface.blit(hint_txt, (SCREEN_W//2 - hint_txt.get_width()//2, y + 10))

    return level_rects


def draw_boss_phase_banner(surface, phase):
    colors = [(60, 220, 60), (220, 180, 0), (220, 60, 60)]
    labels = ["PHASE 1 — Aggressive", "PHASE 2 — Tactical", "PHASE 3 — DESPERATE"]
    md = pygame.font.SysFont("Courier", 15, bold=True)
    t = md.render(labels[phase-1], True, colors[phase-1])
    surface.blit(t, (PLAY_X + GRID*TILE//2 - t.get_width()//2, PLAY_Y+4))