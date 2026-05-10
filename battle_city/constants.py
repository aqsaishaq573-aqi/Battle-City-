# ============================================================
# constants.py
# ============================================================
import pygame

TILE        = 24          # pixels per tile
GRID        = 26          # 26x26 tiles
BORDER      = 24          # NES grey border width
SIDEBAR_W   = 120         # right panel
# BUG FIX: sidebar x must start AFTER the right border strip
# old: BORDER + GRID*TILE + BORDER + SIDEBAR_W   (right BORDER was baked into sidebar region)
SCREEN_W    = BORDER + GRID*TILE + BORDER + SIDEBAR_W
SCREEN_H    = BORDER + GRID*TILE + BORDER
PLAY_X      = BORDER      # pixel x where grid starts
PLAY_Y      = BORDER      # pixel y where grid starts
FPS         = 30

# ── Terrain codes ─────────────────────────────────────────────
EMPTY=0; BRICK=1; STEEL=2; WATER=3; FOREST=4; EAGLE=5

# ── Directions ────────────────────────────────────────────────
UP=(0,-1); DOWN=(0,1); LEFT=(-1,0); RIGHT=(1,0)
DIRS=[UP,DOWN,LEFT,RIGHT]

# ── A* costs ──────────────────────────────────────────────────
ASTAR_COST={EMPTY:1,FOREST:1,BRICK:3,STEEL:float('inf'),WATER:float('inf'),EAGLE:1}

# ── Key positions ─────────────────────────────────────────────
# BUG FIX: Grid is 26 rows (0-25). Row 24 is valid but row 25 would be OOB.
# Project spec says Eagle at (12,24) — this is correct and kept.
EAGLE_POS   =(12,24)
PLAYER_SPAWN=(4,24)
ENEMY_SPAWNS=[(0,0),(12,0),(24,0)]

# ── NES palette ───────────────────────────────────────────────
BLACK      =(  0,  0,  0)
WHITE      =(255,255,255)
NES_GRAY   =(188,188,188)
NES_DARK   =(120,120,120)
BRICK_A    =(188, 80, 20)
BRICK_B    =(100, 40,  0)
STEEL_A    =(188,188,188)
STEEL_B    =(100,100,140)
WATER_A    =( 60,120,220)
WATER_B    =(  0, 60,180)
FOREST_A   =( 40,140, 40)
FOREST_B   =( 20, 80, 20)
EAGLE_C    =(220,180,  0)

# ── Tank colours ──────────────────────────────────────────────
CLR_PLAYER =(220,220, 60)
CLR_BASIC  =(200,200, 60)
CLR_FAST   =( 60,220,220)
CLR_ARMOR  =[( 80, 60,180),(120, 80,200),(200,120, 60),(220,220,220)]  # per hit stage
CLR_POWER  =(200, 60,200)
CLR_BOSS   =(220, 40, 40)
BULLET_CLR =(255,255,255)

# ── Tank stats: (max_hp, speed_ticks, fire_cd_ticks) ─────────
STATS={
    'player': dict(max_hp=1, speed=3, fire_cd=30),
    'basic':  dict(max_hp=1, speed=4, fire_cd=90),
    'fast':   dict(max_hp=1, speed=2, fire_cd=45),
    'armor':  dict(max_hp=4, speed=3, fire_cd=60),
    'power':  dict(max_hp=2, speed=3, fire_cd=50),
    'boss':   dict(max_hp=10,speed=4, fire_cd=60),
}

# ── Level configs ─────────────────────────────────────────────
LEVELS={
    1:dict(name="Brick Maze",
           # FIX: Spec says "First 7 kills are Basic Tanks, Final 5 are Fast Tanks."
           # Pool of 20 total: 7 Basic first, then 13 Fast fill the remainder.
           # fast_unlock_kills=7 ensures no Fast tank spawns until 7 Basics are killed.
           # After the 7th kill the lock lifts and Fast tanks begin spawning.
           pool=['basic']*7+['fast']*13,
           fast_unlock_kills=7,
           max_active=3,
           eagle_rings=2),
    2:dict(name="Steel Fortress",
           # FIX: Spec says exactly "4x Fast + 3x Armor + 2x Power".
           # Scaled to pool of 20 while preserving the 4:3:2 ratio:
           #   4+3+2 = 9 units  →  multiply by ~2.22 to reach 20
           #   Fast : 4×2 = 8 + 1 remainder  = 9
           #   Armor: 3×2 = 6 + 1 remainder  = 7
           #   Power: 2×2 = 4               = 4
           #   Total: 9+7+4 = 20  ✓  ratio stays closest to 4:3:2
           pool=['fast']*9+['armor']*7+['power']*4,
           fast_unlock_kills=None,
           max_active=3,
           eagle_rings=1),
    3:dict(name="Tank Commander",
           pool=['boss'],
           fast_unlock_kills=None,
           max_active=1,
           eagle_rings=1),
}

PLAYER_LIVES=10
SPAWN_DELAY =45   # ticks between spawns
FAIRNESS    =10   # min manhattan distance from spawn to player