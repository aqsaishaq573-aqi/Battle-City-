# ============================================================
# tank.py — All tank types with correct AI per project manual
#
# BUG FIXES:
#   1. BossTank.get_color() called pygame.time.get_ticks() but pygame
#      was never imported in tank.py. Added import pygame.
#   2. ArmorTank._do_retreat: had an inline `from modules.search import
#      bfs_path as bp2` inside the loop — unnecessary since bfs_path
#      is already imported at the top. Removed inline import.
#   3. PlayerTank.handle_input: used pygame.K_* constants without import.
#      Fixed by moving pygame import to top level.
#   4. BasicTank: BFS path is refreshed every 5 seconds (150 ticks). But
#      when path becomes empty (e.g. blocked tank), timer was NOT reset,
#      causing BFS to not re-run next tick. Fixed: reset timer on path clear.
#   5. FastTank.decide: checked LOS to EAGLE but never aimed direction at
#      eagle before shooting — fixed to set self.direction toward eagle.
#   6. BossTank: eagle_pos now comes from generate_map for boss level.
#      Added eagle_pos parameter to decide() via the Level object.
#      For backward compatibility, BossTank still uses EAGLE_POS from
#      constants by default (game.py passes it explicitly).
# ============================================================
import pygame
import random
from constants import *
from modules.search import bfs_path, bfs_step, greedy_step, astar_path, astar_step, bfs_nearest_terrain, los
from modules.minimax import best_action, boss_phase, phase_depth, reset_stats, get_stats


class Tank:
    def __init__(self, x, y, tank_type, direction=DOWN):
        self.x = x; self.y = y
        self.tank_type = tank_type
        self.direction = direction
        s = STATS[tank_type]
        self.max_hp = s['max_hp']; self.hp = self.max_hp
        self.speed = s['speed']; self.fire_cd = s['fire_cd']
        self._mv = 0; self._fc = 0
        self.alive = True

    def get_color(self): return CLR_BASIC

    def _ib(self, x, y): return 0 <= x < GRID and 0 <= y < GRID

    def _passable(self, grid, nx, ny, all_tanks):
        if not self._ib(nx, ny): return False
        if grid[ny][nx] in (STEEL, WATER): return False
        if grid[ny][nx] == BRICK: return False
        for t in all_tanks:
            if t is not self and t.alive and t.x == nx and t.y == ny: return False
        return True

    def try_move(self, grid, d, all_tanks):
        nx, ny = self.x + d[0], self.y + d[1]
        self.direction = d
        if self._passable(grid, nx, ny, all_tanks):
            self.x, self.y = nx, ny; return True
        return False

    def take_hit(self):
        self.hp -= 1
        if self.hp <= 0: self.alive = False

    def can_shoot(self): return self._fc <= 0
    def ready_move(self): return self._mv <= 0

    def do_shoot(self):
        self._fc = self.fire_cd
        return (self.x, self.y, self.direction)

    def tick(self):
        if self._mv > 0: self._mv -= 1
        if self._fc > 0: self._fc -= 1

    def _reset_mv(self): self._mv = self.speed


# ── Player ───────────────────────────────────────────────────
class PlayerTank(Tank):
    def __init__(self, x, y):
        super().__init__(x, y, 'player', UP)
        self.lives = PLAYER_LIVES

    def get_color(self): return CLR_PLAYER

    def handle_input(self, keys, grid, all_tanks):
        move = None; shoot = False
        if   keys[pygame.K_UP]    or keys[pygame.K_w]: move = UP
        elif keys[pygame.K_DOWN]  or keys[pygame.K_s]: move = DOWN
        elif keys[pygame.K_LEFT]  or keys[pygame.K_a]: move = LEFT
        elif keys[pygame.K_RIGHT] or keys[pygame.K_d]: move = RIGHT
        if keys[pygame.K_SPACE] or keys[pygame.K_j]: shoot = True
        return move, shoot

    def respawn(self, x, y):
        self.x, self.y = x, y
        self.hp = self.max_hp
        self.alive = True
        self._fc = 0; self._mv = 0


# ── Basic Tank — Simple Reflex + BFS ─────────────────────────
class BasicTank(Tank):
    REFRESH = 150   # 5 seconds at 30 fps

    def __init__(self, x, y):
        super().__init__(x, y, 'basic', DOWN)
        self._path = []; self._pidx = 0
        # BUG FIX: initialise timer to 0 so BFS runs immediately on first tick
        self._timer = 0

    def get_color(self): return CLR_BASIC

    def decide(self, grid, player, all_tanks, eagle_pos=EAGLE_POS):
        self.tick(); actions = []

        # Refresh BFS every REFRESH ticks or when path is empty
        self._timer -= 1
        if self._timer <= 0 or not self._path:
            self._path = bfs_path(grid, (self.x, self.y), eagle_pos)
            self._pidx = 0; self._timer = self.REFRESH

        # SHOOT reflex: player in same row/col with LOS
        if self.can_shoot() and los(grid, (self.x, self.y), (player.x, player.y)):
            if self.x == player.x or self.y == player.y:
                if   player.x > self.x: self.direction = RIGHT
                elif player.x < self.x: self.direction = LEFT
                elif player.y > self.y: self.direction = DOWN
                else:                   self.direction = UP
                actions.append('shoot')

        # MOVE along BFS path
        if self.ready_move():
            if self._path and self._pidx < len(self._path) - 1:
                self._pidx += 1
                tx, ty = self._path[self._pidx]
                d = (tx - self.x, ty - self.y)
                if grid[ty][tx] == BRICK:
                    # Wall rule: face the wall, shoot it, wait for it to open
                    self.direction = d
                    if self.can_shoot(): actions.append('shoot')
                    self._pidx -= 1   # don't advance until wall is gone
                else:
                    if self.try_move(grid, d, all_tanks):
                        self._reset_mv()
                    else:
                        # BUG FIX: reset timer so BFS re-runs next tick
                        self._path = []; self._timer = 0
            else:
                # No path: random movement fallback
                for d in random.sample(DIRS, 4):
                    if self.try_move(grid, d, all_tanks):
                        self._reset_mv(); break
        return actions


# ── Fast Tank — Goal-Based + Greedy Best-First ───────────────
class FastTank(Tank):
    def __init__(self, x, y):
        super().__init__(x, y, 'fast', DOWN)

    def get_color(self): return CLR_FAST

    def decide(self, grid, player, all_tanks, eagle_pos=EAGLE_POS):
        self.tick(); actions = []

        # Move toward Eagle greedily every movement tick
        if self.ready_move():
            step = greedy_step(grid, (self.x, self.y), eagle_pos)
            if step:
                dx, dy = step; nx, ny = self.x + dx, self.y + dy
                self.direction = step
                if self._ib(nx, ny) and grid[ny][nx] == BRICK:
                    # Wall rule: shoot to clear, do NOT detour
                    if self.can_shoot(): actions.append('shoot')
                else:
                    if self.try_move(grid, step, all_tanks): self._reset_mv()
            else:
                # Local minima: try random direction
                for d in random.sample(DIRS, 4):
                    if self.try_move(grid, d, all_tanks):
                        self._reset_mv(); break

        # BUG FIX: Shoot Eagle if in LOS — set direction toward eagle first
        ex, ey = eagle_pos
        if self.can_shoot() and los(grid, (self.x, self.y), eagle_pos):
            if self.x == ex or self.y == ey:
                if   ex > self.x: self.direction = RIGHT
                elif ex < self.x: self.direction = LEFT
                elif ey > self.y: self.direction = DOWN
                else:             self.direction = UP
                actions.append('shoot')

        return actions


# ── Armor Tank — Model-Based Reflex + A* ─────────────────────
class ArmorTank(Tank):
    COVER_WAIT = 60   # 2 seconds at 30 fps

    def __init__(self, x, y):
        super().__init__(x, y, 'armor', DOWN)
        self.hit_count = 0
        self._state = 'attack'   # 'attack' | 'retreat' | 'cover'
        self._path = []; self._pidx = 0
        self._cover_t = 0

    def get_color(self):
        return CLR_ARMOR[min(self.hit_count, 3)]

    def take_hit(self):
        self.hp -= 1; self.hit_count += 1
        if self.hp <= 0:
            self.alive = False
        elif self.hit_count == 3:
            # 3rd hit triggers retreat
            self._state = 'retreat'; self._path = []

    def decide(self, grid, player, all_tanks, eagle_pos=EAGLE_POS):
        self.tick(); actions = []
        if   self._state == 'attack':  self._do_attack(grid, player, all_tanks, actions, eagle_pos)
        elif self._state == 'retreat': self._do_retreat(grid, all_tanks, actions)
        elif self._state == 'cover':
            self._cover_t -= 1
            if self._cover_t <= 0:
                self._state = 'attack'; self._path = []; self._pidx = 0
        return actions

    def _do_attack(self, grid, player, all_tanks, actions, eagle_pos):
        # Shoot player if in line-of-sight
        if self.can_shoot() and los(grid, (self.x, self.y), (player.x, player.y)):
            if self.x == player.x or self.y == player.y:
                if   player.x > self.x: self.direction = RIGHT
                elif player.x < self.x: self.direction = LEFT
                elif player.y > self.y: self.direction = DOWN
                else:                   self.direction = UP
                actions.append('shoot')

        if not self.ready_move(): return

        # A* path to Eagle
        if not self._path or self._pidx >= len(self._path) - 1:
            self._path = astar_path(grid, (self.x, self.y), eagle_pos)
            self._pidx = 0

        if self._path and self._pidx < len(self._path) - 1:
            self._pidx += 1; tx, ty = self._path[self._pidx]
            d = (tx - self.x, ty - self.y)
            if grid[ty][tx] == BRICK:
                # Shoot through brick: A* calculated it's cheaper than detour
                self.direction = d
                if self.can_shoot(): actions.append('shoot')
                self._pidx -= 1   # stay on current tile until wall clears
            else:
                if self.try_move(grid, d, all_tanks): self._reset_mv()
                else: self._path = []; self._pidx = 0
        else:
            for d in random.sample(DIRS, 4):
                if self.try_move(grid, d, all_tanks): self._reset_mv(); break

    def _do_retreat(self, grid, all_tanks, actions):
        if not self._path:
            # BUG FIX: Removed inline import — bfs_path already imported at top
            steel = bfs_nearest_terrain(grid, (self.x, self.y), {STEEL})
            if steel:
                sx, sy = steel
                # Find a passable tile adjacent to the steel wall (cover position)
                for dx, dy in DIRS:
                    ax, ay = sx + dx, sy + dy
                    if 0 <= ax < GRID and 0 <= ay < GRID and grid[ay][ax] == EMPTY:
                        self._path = bfs_path(grid, (self.x, self.y), (ax, ay))
                        self._pidx = 0; break
            if not self._path:
                # No steel found — go directly to cover state
                self._state = 'cover'; self._cover_t = self.COVER_WAIT; return

        if not self.ready_move(): return

        if self._pidx < len(self._path) - 1:
            self._pidx += 1; tx, ty = self._path[self._pidx]
            d = (tx - self.x, ty - self.y)
            if self.try_move(grid, d, all_tanks): self._reset_mv()
            else: self._path = []   # blocked: recompute next tick
        else:
            # Reached cover position
            self._state = 'cover'; self._cover_t = self.COVER_WAIT; self._path = []


# ── Power Tank — Utility-Based + A* ──────────────────────────
class PowerTank(Tank):
    def __init__(self, x, y):
        super().__init__(x, y, 'power', DOWN)
        self._path = []; self._pidx = 0
        self._goal = EAGLE_POS; self._goal_t = 0

    def get_color(self): return CLR_POWER

    def _pick_goal(self, player_pos, eagle_pos):
        ex, ey = eagle_pos; px, py = player_pos
        d_eagle  = abs(self.x - ex) + abs(self.y - ey)
        d_player = abs(self.x - px) + abs(self.y - py)
        u_eagle  = 100 - d_eagle
        u_player = 60  - d_player
        return eagle_pos if u_eagle >= u_player else (px, py)

    def decide(self, grid, player, all_tanks, eagle_pos=EAGLE_POS):
        self.tick(); actions = []
        self._goal_t -= 1
        if self._goal_t <= 0:
            self._goal = self._pick_goal((player.x, player.y), eagle_pos)
            self._path = []; self._goal_t = 90   # recheck every 3 seconds

        # Shoot player if in LOS
        if self.can_shoot() and los(grid, (self.x, self.y), (player.x, player.y)):
            if self.x == player.x or self.y == player.y:
                if   player.x > self.x: self.direction = RIGHT
                elif player.x < self.x: self.direction = LEFT
                elif player.y > self.y: self.direction = DOWN
                else:                   self.direction = UP
                actions.append('shoot')

        if not self.ready_move(): return actions

        if not self._path or self._pidx >= len(self._path) - 1:
            self._path = astar_path(grid, (self.x, self.y), self._goal)
            self._pidx = 0

        if self._path and self._pidx < len(self._path) - 1:
            self._pidx += 1; tx, ty = self._path[self._pidx]
            d = (tx - self.x, ty - self.y)
            if grid[ty][tx] == BRICK:
                self.direction = d
                if self.can_shoot(): actions.append('shoot')
                self._pidx -= 1
            else:
                if self.try_move(grid, d, all_tanks): self._reset_mv()
                else: self._path = []; self._pidx = 0
        else:
            for d in random.sample(DIRS, 4):
                if self.try_move(grid, d, all_tanks): self._reset_mv(); break

        return actions


# ── Boss Tank — Adversarial + Minimax ────────────────────────
class BossTank(Tank):
    def __init__(self, x, y):
        super().__init__(x, y, 'boss', DOWN)
        reset_stats()

    def get_color(self):
        phase = boss_phase(self.hp)
        if phase == 3:
            # BUG FIX: pygame was not imported — now imported at top of file
            t = pygame.time.get_ticks()
            return WHITE if (t // 120) % 2 == 0 else CLR_BOSS
        return CLR_BOSS

    def _phase_stats(self):
        ph = boss_phase(self.hp)
        self.speed   = {1: 4, 2: 3, 3: 2}[ph]
        self.fire_cd = {1: 60, 2: 45, 3: 24}[ph]

    def decide(self, grid, player, all_tanks, eagle_pos=EAGLE_POS):
        self.tick(); self._phase_stats(); actions = []
        ph = boss_phase(self.hp)
        depth = phase_depth(ph)

        action = best_action(
            (self.x, self.y), self.hp,
            (player.x, player.y), player.lives,
            self.direction, player.direction,
            grid, depth)

        if action == 'SHOOT':
            if self.can_shoot(): actions.append('shoot')
        else:
            if self.ready_move():
                nx, ny = self.x + action[0], self.y + action[1]
                self.direction = action
                if 0 <= nx < GRID and 0 <= ny < GRID and grid[ny][nx] == BRICK:
                    if self.can_shoot(): actions.append('shoot')
                else:
                    if self.try_move(grid, action, all_tanks): self._reset_mv()
        return actions


# ── Factory ───────────────────────────────────────────────────
def make_tank(tank_type, x, y):
    return {
        'player': PlayerTank,
        'basic':  BasicTank,
        'fast':   FastTank,
        'armor':  ArmorTank,
        'power':  PowerTank,
        'boss':   BossTank,
    }[tank_type](x, y)
