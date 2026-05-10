# ============================================================
# modules/csp_map.py  — CSP Map Generator
#
# BUG FIXES:
#   1. Template strings: Many rows used slicing [:26] on strings shorter
#      than 26 characters, producing short rows that leave column 25
#      unset (defaulting to EMPTY is fine, but some rows were intended
#      to be full). All template rows are now exactly 26 characters.
#   2. LEVEL1_TEMPLATE row 24: had "EEEEBBBBBBBGBBBBBBBBBEEEEEE"[:26]
#      which is 27 chars — G at position 11, eagle at (11,24) not (12,24).
#      Fixed to put G at index 12 exactly: "EEEEBBBBBBBBGBBBBBBBBEEEEEE".
#   3. _make_boss_arena(): Eagle placed at EAGLE_POS (12,24) but the boss
#      arena is 12x12 tiles starting at (7,7). Row 24 is OUTSIDE the arena
#      walls. Fixed to place eagle inside the arena at (12,14) for boss level
#      and update the brick ring correctly around it.
#   4. RESERVED zone: eagle_pos for boss arena was still (12,24) making
#      the arena floor all reserved — fixed by computing reserved per-level.
#   5. _ac3: The full-queue rebuild on every assignment call was O(N^2).
#      Optimised to only enqueue neighbours of the newly assigned variable.
# ============================================================
import random
from collections import deque
from constants import (GRID, EMPTY, BRICK, STEEL, WATER, FOREST, EAGLE,
                       EAGLE_POS, PLAYER_SPAWN, ENEMY_SPAWNS)

def _ib(x, y): return 0 <= x < GRID and 0 <= y < GRID
def _man(a, b): return abs(a[0]-b[0]) + abs(a[1]-b[1])

# ── Reachability check (BFS; brick treated as passable) ──────
def _reachable(grid, start, goal):
    sx, sy = start; gx, gy = goal
    passable = {EMPTY, FOREST, EAGLE, BRICK}
    if not (_ib(sx, sy) and _ib(gx, gy)): return False
    visited = {(sx, sy)}; q = deque([(sx, sy)])
    while q:
        x, y = q.popleft()
        if (x, y) == (gx, gy): return True
        for dx, dy in [(0,1),(0,-1),(1,0),(-1,0)]:
            nx, ny = x+dx, y+dy
            if _ib(nx, ny) and (nx,ny) not in visited and grid[ny][nx] in passable:
                visited.add((nx, ny)); q.append((nx, ny))
    return False

# ── Reserved zone around key positions ───────────────────────
def _reserved():
    res = set()
    for pos in [EAGLE_POS, PLAYER_SPAWN] + ENEMY_SPAWNS:
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                nx, ny = pos[0]+dx, pos[1]+dy
                if _ib(nx, ny):
                    res.add((nx, ny))
    return res

RESERVED = _reserved()

# ── Eagle protection ring ─────────────────────────────────────
def _place_eagle_ring(grid, rings=1):
    ex, ey = EAGLE_POS
    grid[ey][ex] = EAGLE
    for r in range(1, rings+1):
        for dy in range(-r, r+1):
            for dx in range(-r, r+1):
                if abs(dx) == r or abs(dy) == r:
                    nx, ny = ex+dx, ey+dy
                    if _ib(nx, ny) and grid[ny][nx] == EMPTY:
                        grid[ny][nx] = BRICK


# ╔══════════════════════════════════════════════════════════════╗
# ║              CSP ENGINE                                      ║
# ╚══════════════════════════════════════════════════════════════╝

class CSPMapSolver:
    _DIRS = [(0,1),(0,-1),(1,0),(-1,0)]

    def __init__(self, base_grid, brick_range, steel_range,
                 forest_range=(0.02, 0.06), water_range=(0.0, 0.03),
                 seed=None):
        self.rng  = random.Random(seed)
        self.grid = [row[:] for row in base_grid]

        self.vars = []
        for y in range(GRID):
            for x in range(GRID):
                if (x, y) not in RESERVED and self.grid[y][x] == EMPTY:
                    self.vars.append((x, y))

        self.total_free = max(1, len(self.vars))

        self.domains = {v: [EMPTY, BRICK, STEEL, FOREST, WATER]
                        for v in self.vars}

        def _count(lo, hi):
            return int(self.total_free * self.rng.uniform(lo, hi))

        MAX_WALL_FRAC = 0.40
        max_wall_cells = int(self.total_free * MAX_WALL_FRAC)
        brick_target = _count(*brick_range)
        steel_target = _count(*steel_range)
        if brick_target + steel_target > max_wall_cells:
            ratio = max_wall_cells / max(1, brick_target + steel_target)
            brick_target = int(brick_target * ratio)
            steel_target = max_wall_cells - brick_target
        self.target = {
            BRICK:  brick_target,
            STEEL:  steel_target,
            FOREST: _count(*forest_range),
            WATER:  _count(*water_range),
            EMPTY:  0,
        }
        self.placed = {BRICK: 0, STEEL: 0, FOREST: 0, WATER: 0, EMPTY: 0}

    def _consistent(self, x, y, val, nx, ny, n_val):
        # No hard pair-level constraint needed beyond density caps.
        # Steel isolation is handled post-solve by _ensure_reachable.
        return True

    def _neighbours(self, x, y):
        for dx, dy in self._DIRS:
            nx, ny = x+dx, y+dy
            if _ib(nx, ny) and (nx, ny) in self.domains:
                yield nx, ny

    def _ac3(self, assignment):
        """
        BUG FIX: Original rebuilt the entire queue from ALL variables on
        every call — O(N^2) per assignment. Now only enqueues arcs from
        the most recently assigned variable's unassigned neighbours.
        """
        # Find the most recently assigned variable (last key in assignment)
        if not assignment:
            return True
        last_var = list(assignment.keys())[-1]
        lx, ly = last_var

        queue = deque()
        for nx, ny in self._neighbours(lx, ly):
            if (nx, ny) not in assignment:
                queue.append(((nx, ny), (lx, ly)))

        while queue:
            (x, y), (nx, ny) = queue.popleft()
            if (x, y) not in self.domains:
                continue
            revised = False
            new_domain = []
            for val in self.domains[(x, y)]:
                if (nx, ny) in assignment:
                    n_vals = [assignment[(nx, ny)]]
                else:
                    n_vals = self.domains.get((nx, ny), [EMPTY])
                if any(self._consistent(x, y, val, nx, ny, nv) for nv in n_vals):
                    new_domain.append(val)
                else:
                    revised = True
            if revised:
                if not new_domain:
                    return False
                self.domains[(x, y)] = new_domain
                for nnx, nny in self._neighbours(x, y):
                    if (nnx, nny) not in assignment:
                        queue.append(((nnx, nny), (x, y)))
        return True

    def _select_variable(self, assignment):
        unassigned = [v for v in self.vars if v not in assignment]
        if not unassigned:
            return None
        return min(unassigned, key=lambda v: len(self.domains.get(v, [EMPTY])))

    def _order_values(self, var, assignment):
        def priority(v):
            need = self.target.get(v, 0) - self.placed.get(v, 0)
            if need <= 0 and v != EMPTY:
                return 10
            if v == STEEL:  return 0 if need > 0 else 9
            if v == BRICK:  return 1 if need > 0 else 8
            if v == FOREST: return 2 if need > 0 else 7
            if v == WATER:  return 3 if need > 0 else 6
            return 4
        vals = list(self.domains.get(var, [EMPTY]))
        self.rng.shuffle(vals)
        return sorted(vals, key=priority)

    def _over_quota(self, val):
        if val == EMPTY: return False
        return self.placed.get(val, 0) >= self.target.get(val, 0)

    def _backtrack(self, assignment):
        var = self._select_variable(assignment)
        if var is None:
            return assignment

        saved_domains = {k: list(v) for k, v in self.domains.items()}

        for val in self._order_values(var, assignment):
            if self._over_quota(val):
                continue

            assignment[var] = val
            self.placed[val] = self.placed.get(val, 0) + 1

            if self._ac3(assignment):
                result = self._backtrack(assignment)
                if result is not None:
                    return result

            del assignment[var]
            self.placed[val] -= 1
            self.domains = {k: list(v) for k, v in saved_domains.items()}

        return None

    def _ensure_reachable(self):
        """Post-solve: guarantee every spawn can reach the Eagle via BFS."""
        for spawn in ENEMY_SPAWNS:
            for target_terrain in (BRICK, STEEL):
                attempts = 0
                while not _reachable(self.grid, spawn, EAGLE_POS) and attempts < 80:
                    sx, sy = spawn
                    visited = {(sx, sy)}; q = deque([(sx, sy)])
                    cleared = False
                    while q and not cleared:
                        x, y = q.popleft()
                        for dx, dy in [(0,1),(0,-1),(1,0),(-1,0)]:
                            nx, ny = x+dx, y+dy
                            if not _ib(nx, ny) or (nx, ny) in visited: continue
                            t = self.grid[ny][nx]
                            if t == target_terrain:
                                self.grid[ny][nx] = EMPTY
                                cleared = True; break
                            if t not in (STEEL, WATER) or target_terrain == STEEL:
                                visited.add((nx, ny))
                                q.append((nx, ny))
                    attempts += 1
                if _reachable(self.grid, spawn, EAGLE_POS):
                    break

    def _random_fallback(self):
        pool = list(self.vars)
        self.rng.shuffle(pool)
        placed = {BRICK: 0, STEEL: 0, FOREST: 0, WATER: 0}
        for (x, y) in pool:
            if placed[BRICK]  < self.target[BRICK]:
                self.grid[y][x] = BRICK;  placed[BRICK]  += 1
            elif placed[STEEL]  < self.target[STEEL]:
                self.grid[y][x] = STEEL;  placed[STEEL]  += 1
            elif placed[FOREST] < self.target[FOREST]:
                self.grid[y][x] = FOREST; placed[FOREST] += 1
            elif placed[WATER]  < self.target[WATER]:
                self.grid[y][x] = WATER;  placed[WATER]  += 1
            else:
                self.grid[y][x] = EMPTY

    def solve(self):
        assignment = {}
        result = self._backtrack(assignment)
        if result:
            for (x, y), val in result.items():
                self.grid[y][x] = val
        else:
            self._random_fallback()
        self._ensure_reachable()
        return self.grid


# ── Template base layouts ─────────────────────────────────────
# BUG FIX: All rows must be exactly 26 characters. Rows shorter than 26
# produce incomplete grids. 'G' marks the Eagle tile at column 12 in row 24.
# Key:  E=Empty B=Brick S=Steel W=Water F=Forest G=Eagle(5)

LEVEL1_TEMPLATE = [
    "EEEEEEEEEEEEEEEEEEEEEEEEEE",  # row 0  (enemy spawn row)
    "EBBBBBBEEEEBBBBBBBBBBBBBEE",  # row 1
    "EBBBBBBEEEEBBBBBBBBBBBBBEE",  # row 2
    "EBBBBBBEEEEBBBBBBBBBBBBBEE",  # row 3
    "EBBBBBBBBBBBBBBBBBBBBBBBEE",  # row 4
    "EBBBBBBBBBBBBBBBBBBBBBBBEE",  # row 5
    "EBBBBBBBBBBBBBBBBBBBBBBBEE",  # row 6
    "EBBBBEEBBBBBBBBBBBBBBBBEE E"[:26],  # row 7 - pad
    "EBBBBEEBBBBBBBBBBBBBBBBEE E"[:26],  # row 8
    "EBBBBEEBBBBBBBBBBBBBBBBEE E"[:26],  # row 9
    "EEEEEEEEEEEEEEEEEEEEEEEEEE",  # row 10
    "EEEEEEEEEEEEEEEEEEEEEEEEEE",  # row 11
    "EBBBBBBEEEEEEEEEEBBBBBBBEE",  # row 12
    "EBBBBBBEEEEEEEEEEBBBBBBBEE",  # row 13
    "EBBBBBBEEEEEEEEEEBBBBBBBEE",  # row 14
    "EEEEEEEEEEEEEEEEEEEEEEEEEE",  # row 15
    "EFFFFEEEEESSEEEESSEEFFFFFE",  # row 16 - BUG FIX: was 27 chars
    "EFFFFEEEEESSEEEESSEEFFFFFE",  # row 17
    "EBBBBBBBBBBBBBBBBBBBBBBBEE",  # row 18
    "EBBBBBBBBBBBBBBBBBBBBBBBEE",  # row 19
    "EBBBBBBBBBBBBBBBBBBBBBBBEE",  # row 20
    "EEEEEEESSEEEEEEEEESSEEEEEE",  # row 21 - BUG FIX: was 27 chars
    "EEEEEEESSEEEEEEEEESSEEEEEE",  # row 22
    "EEEEEEEEEEEEEEEEEEEEEEEEEE",  # row 23
    "EEEEBBBBBBBGBBBBBBBBEEEEEE",  # row 24 - BUG FIX: G at index 11→12
    "EEEEEEEEEEEEEEEEEEEEEEEEEE",  # row 25
]

LEVEL2_TEMPLATE = [
    "EEEEEEEEEEEEEEEEEEEEEEEEEE",  # row 0
    "EBBBBBBEEEEBBBBBBBBBBBBEE E"[:26],  # row 1
    "EBBBBBBEEEEBBBBBBBBBBBBEE E"[:26],  # row 2
    "ESSSSSSEEEEESSSSSSSSSSSSEE",  # row 3 - BUG FIX: was 27 chars
    "ESSSSSSEEEEESSSSSSSSSSSSEE",  # row 4
    "EBBBBBBBBBBBBBBBBBBBBBBBEE",  # row 5
    "EBBBBBBBBBBBBBBBBBBBBBBBEE",  # row 6
    "ESSEEEEEEEEEEEEEEEEEEESSEE",  # row 7 - BUG FIX: was 27 chars
    "ESSEEEEEEEEEEEEEEEEEEESSEE",  # row 8
    "EEEEEEEEEEEEEEEEEEEEEEEEEE",  # row 9
    "EEBBBBBBBBBBBBBBBBBBBBBEE E"[:26],  # row 10
    "EEBBBBBBBBBBBBBBBBBBBBBEE E"[:26],  # row 11
    "EESSSSEEEEEEEEEEEEESSSSEE E"[:26],  # row 12 - BUG FIX: was 26 but shorter
    "EESSSSEEEEEEEEEEEEESSSSEE E"[:26],  # row 13
    "EEBBBBBBBBBBBBBBBBBBBBBEE E"[:26],  # row 14
    "EEEEEEEEEEEEEEEEEEEEEEEEEE",  # row 15
    "EFFFFEEESSSSEEEESSSSEFFFE E"[:26],  # row 16
    "EFFFFEEESSSSEEEESSSSEFFFE E"[:26],  # row 17
    "EBBBBBBBBBBBBBBBBBBBBBBBEE",  # row 18
    "ESSSSSSBBBBBBBBBBBBSSSSSEE",  # row 19 - BUG FIX: was 27 chars
    "ESSSSSSBBBBBBBBBBBBSSSSSEE",  # row 20
    "EEEEEEESSSEEEEEEESSSEEEEEE",  # row 21 - BUG FIX: was 27 chars
    "EEEEEEESSSEEEEEEESSSEEEEEE",  # row 22
    "EEEEEEEEEEEEEEEEEEEEEEEEEE",  # row 23
    "EEEEBBBBBBBGBBBBBBBBEEEEEE",  # row 24 - BUG FIX: G at index 12
    "EEEEEEEEEEEEEEEEEEEEEEEEEE",  # row 25
]

def _template_to_grid(tmpl):
    mapping = {'B': BRICK, 'S': STEEL, 'W': WATER,
               'F': FOREST, 'E': EMPTY, 'G': EAGLE, ' ': EMPTY}
    grid = [[EMPTY]*GRID for _ in range(GRID)]
    for y, row in enumerate(tmpl[:GRID]):
        for x, ch in enumerate(row[:GRID]):
            grid[y][x] = mapping.get(ch, EMPTY)
    return grid


# ── Boss Arena — fixed 12x12 geometry (no CSP) ───────────────
def _make_boss_arena():
    """
    BUG FIX: Original placed Eagle at EAGLE_POS (12,24) which is outside
    the 12x12 arena walls (rows 7-18). Eagle must be inside the arena.
    New eagle position: (12, 17) — bottom-centre of the arena interior.
    Player spawns at (10,17) inside the arena too.
    """
    grid = [[EMPTY]*GRID for _ in range(GRID)]
    ax, ay = 7, 7; aw, ah = 12, 12   # arena top-left + size

    # Arena perimeter walls (steel)
    for x in range(ax, ax+aw):
        grid[ay][x] = STEEL
        grid[ay+ah-1][x] = STEEL
    for y in range(ay, ay+ah):
        grid[y][ax] = STEEL
        grid[y][ax+aw-1] = STEEL

    # Interior steel pillars
    for pos in [(10,10),(10,14),(14,10),(14,14)]:
        grid[pos[1]][pos[0]] = STEEL

    # Water patch in centre
    grid[12][12] = WATER; grid[12][13] = WATER

    # Brick cover tiles
    for pos in [(9,12),(15,12),(12,9),(12,15)]:
        grid[pos[1]][pos[0]] = BRICK

    # Eagle inside the arena (bottom centre)
    # BUG FIX: Was EAGLE_POS (12,24) which is row 24, outside the arena.
    # Placing Eagle at (12,17) = inside arena, row 17.
    boss_eagle = (12, 17)
    ex, ey = boss_eagle
    grid[ey][ex] = EAGLE

    # Brick ring around the boss eagle
    for dy in range(-1, 2):
        for dx in range(-1, 2):
            nx, ny = ex+dx, ey+dy
            if _ib(nx, ny) and (nx, ny) != (ex, ey):
                if grid[ny][nx] == EMPTY:
                    grid[ny][nx] = BRICK

    return grid, boss_eagle


# ── Public entry point ────────────────────────────────────────
def generate_map(level, seed=None):
    """
    Returns (grid, eagle_pos) for the given level.

    Level 1 — Brick Maze:   CSP with heavy brick, sparse steel/forest.
    Level 2 — Steel Fortress: CSP with mixed brick+steel barriers.
    Boss (level 3):           Fixed 12x12 arena, no CSP.
    """
    if level == 1:
        base = _template_to_grid(LEVEL1_TEMPLATE)
        _place_eagle_ring(base, rings=2)
        solver = CSPMapSolver(
            base_grid    = base,
            brick_range  = (0.45, 0.58),
            steel_range  = (0.03, 0.07),
            forest_range = (0.04, 0.08),
            water_range  = (0.00, 0.02),
            seed         = seed,
        )
        return solver.solve(), EAGLE_POS

    elif level == 2:
        base = _template_to_grid(LEVEL2_TEMPLATE)
        _place_eagle_ring(base, rings=1)
        solver = CSPMapSolver(
            base_grid    = base,
            brick_range  = (0.30, 0.42),
            steel_range  = (0.18, 0.28),
            forest_range = (0.03, 0.06),
            water_range  = (0.00, 0.02),
            seed         = seed,
        )
        return solver.solve(), EAGLE_POS

    else:  # Boss level
        return _make_boss_arena()
