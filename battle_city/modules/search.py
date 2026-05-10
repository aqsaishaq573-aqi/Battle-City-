# ============================================================
# modules/search.py  — BFS · Greedy Best-First · A*
#
# BUG FIXES:
#   1. bfs_path: path reconstruction used `while cur` which stops when
#      cur is falsy (e.g. (0,0) tuple is truthy, but visited[(0,0)]=None
#      breaks correctly). Added explicit None sentinel check for safety.
#   2. astar_path: stale-node check `if g > g_cost[node]` must use .get()
#      with inf default — was correct but added comment clarity.
#   3. greedy_step: BRICK tiles should be passable targets (tank will shoot
#      them). EAGLE tile included so tank can reach goal.
#   4. bfs_nearest_terrain: was including starting tile itself as valid
#      find — added (x,y)!=(sx,sy) guard (was already there, confirmed OK).
#   5. los(): when positions are identical (same tile), now returns True
#      instead of False — a tank at the same tile has line-of-sight.
# ============================================================
from collections import deque
import heapq
from constants import GRID,EMPTY,BRICK,STEEL,WATER,FOREST,EAGLE,EAGLE_POS,ASTAR_COST,DIRS

def _ib(x,y): return 0<=x<GRID and 0<=y<GRID

def _nb(x,y):
    for dx,dy in DIRS:
        nx,ny=x+dx,y+dy
        if _ib(nx,ny): yield nx,ny,dx,dy

def _man(ax,ay,bx,by): return abs(ax-bx)+abs(ay-by)

# ── BFS ──────────────────────────────────────────────────────
# Basic Tank: passable = EMPTY, FOREST, EAGLE, BRICK
# Brick is passable because the tank will shoot it to open the path.
def bfs_path(grid, start, goal=EAGLE_POS):
    sx,sy=start; gx,gy=goal
    if (sx,sy)==(gx,gy): return [(sx,sy)]
    passable={EMPTY,FOREST,EAGLE,BRICK}
    # BUG FIX: visited maps position -> parent. Use None as sentinel for start.
    visited={(sx,sy): None}
    q=deque([(sx,sy)])
    while q:
        x,y=q.popleft()
        if (x,y)==(gx,gy):
            path=[]; cur=(gx,gy)
            # Reconstruct: walk parent chain until start (None parent)
            while cur is not None:
                path.append(cur)
                cur=visited[cur]
            path.reverse()
            return path
        for nx,ny,_,_ in _nb(x,y):
            if (nx,ny) not in visited and grid[ny][nx] in passable:
                visited[(nx,ny)]=(x,y)
                q.append((nx,ny))
    return []

def bfs_step(grid, start, goal=EAGLE_POS):
    path=bfs_path(grid,start,goal)
    if len(path)<2: return None
    sx,sy=start; nx,ny=path[1]
    return (nx-sx,ny-sy)

# ── Greedy Best-First ─────────────────────────────────────────
# Fast Tank: single-step decision, picks neighbour with lowest h(n).
# BUG FIX: Must include BRICK as passable (tank shoots brick walls on path).
def greedy_step(grid, start, goal=EAGLE_POS):
    sx,sy=start; gx,gy=goal
    passable={EMPTY,FOREST,EAGLE,BRICK}
    best_h=float('inf'); best_dir=None
    for nx,ny,dx,dy in _nb(sx,sy):
        if grid[ny][nx] in passable:
            h=_man(nx,ny,gx,gy)
            if h<best_h: best_h=h; best_dir=(dx,dy)
    return best_dir

# ── A* ────────────────────────────────────────────────────────
# Armor Tank: cost-aware — brick=3, steel/water=inf
# BUG FIX: Added tie-breaking counter in heap to avoid comparing tuples
# when f-values are equal (would try to compare grid coords as tiebreak
# which can fail if they're equal too). Using a counter avoids this.
def astar_path(grid, start, goal=EAGLE_POS):
    sx,sy=start; gx,gy=goal
    if (sx,sy)==(gx,gy): return [(sx,sy)]
    counter=0
    open_h=[(0+_man(sx,sy,gx,gy), counter, 0, sx, sy)]
    came={(sx,sy):None}
    g_cost={(sx,sy):0}
    while open_h:
        f,_,g,x,y=heapq.heappop(open_h)
        if (x,y)==(gx,gy):
            path=[]; cur=(gx,gy)
            while cur is not None:
                path.append(cur)
                cur=came[cur]
            path.reverse()
            return path
        # BUG FIX: stale node check — skip if we've found a better path already
        if g > g_cost.get((x,y), float('inf')):
            continue
        for nx,ny,_,_ in _nb(x,y):
            cost=ASTAR_COST.get(grid[ny][nx], float('inf'))
            if cost==float('inf'): continue
            ng=g+cost
            if ng < g_cost.get((nx,ny), float('inf')):
                g_cost[(nx,ny)]=ng
                came[(nx,ny)]=(x,y)
                counter+=1
                heapq.heappush(open_h,(ng+_man(nx,ny,gx,gy), counter, ng, nx, ny))
    return []

def astar_step(grid, start, goal=EAGLE_POS):
    path=astar_path(grid,start,goal)
    if len(path)<2: return None
    sx,sy=start; nx,ny=path[1]
    return (nx-sx,ny-sy)

# ── BFS to nearest tile of a terrain type ────────────────────
def bfs_nearest_terrain(grid, start, terrains):
    sx,sy=start
    passable={EMPTY,FOREST,EAGLE,BRICK,STEEL}
    visited={(sx,sy)}; q=deque([(sx,sy)])
    while q:
        x,y=q.popleft()
        if grid[y][x] in terrains and (x,y)!=(sx,sy): return (x,y)
        for nx,ny,_,_ in _nb(x,y):
            if (nx,ny) not in visited and grid[ny][nx] in passable:
                visited.add((nx,ny)); q.append((nx,ny))
    return None

# ── Line of sight ─────────────────────────────────────────────
# BUG FIX: When a==b (same tile), original returned False.
# A tank at same position trivially has line-of-sight to itself.
def los(grid, a, b):
    ax,ay=a; bx,by=b
    # Same position: trivially in LOS
    if ax==bx and ay==by: return True
    blocking={BRICK,STEEL,WATER}
    if ax==bx:
        y0,y1=(ay+1,by) if ay<by else (by+1,ay)
        return not any(grid[y][ax] in blocking for y in range(y0,y1))
    if ay==by:
        x0,x1=(ax+1,bx) if ax<bx else (bx+1,ax)
        return not any(grid[ay][x] in blocking for x in range(x0,x1))
    return False
