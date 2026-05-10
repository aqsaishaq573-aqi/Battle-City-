# ============================================================
# modules/minimax.py  — Minimax + Alpha-Beta for Boss
#
# BUG FIXES:
#   1. phase_depth() was referenced in tank.py but defined here — confirmed
#      it exists. Added it clearly with docstring.
#   2. evaluate(): "Player HP missing +20 per HP" — original used
#      `PLAYER_LIVES - php` where php=player.lives (0-10). This is correct
#      when php represents remaining lives (fewer lives = higher score for boss).
#   3. _move(): allowed moving into EAGLE tile (terrain=5) which is not
#      a passable cell for the simulated player/boss in minimax. Fixed.
#   4. minimax_no_ab and minimax: terminal condition `php<=0 or bhp<=0`
#      was fine but added `bhp<=0` path returns correct terminal value.
#   5. best_action(): no_ab counter was accumulating across turns (never
#      reset). Now reset_stats() is called at start of BossTank.__init__
#      which is correct. Added note.
# ============================================================
import heapq
from constants import GRID,EMPTY,FOREST,BRICK,STEEL,WATER,DIRS,EAGLE_POS,PLAYER_LIVES

_stats={"ab":0, "no_ab":0}

def get_stats(): return dict(_stats)

def reset_stats(): _stats["ab"]=0; _stats["no_ab"]=0

def _ib(x,y): return 0<=x<GRID and 0<=y<GRID

# BUG FIX: _pass must NOT include EAGLE tile (5) as passable movement target
# during minimax simulation — the eagle is the goal/terminal, not a traversal tile.
def _pass(grid,x,y):
    return _ib(x,y) and grid[y][x] in (EMPTY,FOREST)

def _man(a,b): return abs(a[0]-b[0])+abs(a[1]-b[1])

def _los(grid,a,b):
    ax,ay=a; bx,by=b
    blocking={BRICK,STEEL,WATER}
    # Same position: trivially in LOS
    if ax==bx and ay==by: return True
    if ax==bx:
        y0,y1=(ay+1,by) if ay<by else (by+1,ay)
        return not any(grid[y][ax] in blocking for y in range(y0,y1))
    if ay==by:
        x0,x1=(ax+1,bx) if ax<bx else (bx+1,ax)
        return not any(grid[ay][x] in blocking for x in range(x0,x1))
    return False

def _move(pos,d,grid):
    """Simulate a single-step move in direction d. Returns new position or stays."""
    x,y=pos; nx,ny=x+d[0],y+d[1]
    return (nx,ny) if _pass(grid,nx,ny) else pos

def _shoot_hits(src,d,grid,target):
    """Trace a bullet from src in direction d. Returns True if it reaches target."""
    x,y=src
    for _ in range(GRID):
        x+=d[0]; y+=d[1]
        if not _ib(x,y): break
        if (x,y)==target: return True
        if grid[y][x] in (BRICK,STEEL,WATER): break
    return False

def evaluate(bp,bhp,pp,php,bd,grid):
    """
    Boss Tank evaluation heuristic (MAX perspective = Boss wants high score).

    Factor                        | Score
    ------------------------------|--------
    Player within 3 tiles         | +60
    Proximity bonus (12-dist)*4   | up to +48
    Player in line-of-sight       | +50
    Boss adjacent to steel (cover)| +30
    Player HP/lives missing       | +20 per missing life
    Boss HP missing               | -40 per missing HP
    Player in forest (uncertainty)| -20
    """
    score=0.0
    bx,by=bp; px,py=pp
    dist=_man(bp,pp)
    if dist<=3: score+=60
    score+=max(0,12-dist)*4
    if _los(grid,bp,pp): score+=50
    # Cover check: boss adjacent to any steel tile
    for d in DIRS:
        nx,ny=bx+d[0],by+d[1]
        if _ib(nx,ny) and grid[ny][nx]==STEEL: score+=30; break
    # Player is weakened: +20 per missing life (out of 10)
    score+=20*(PLAYER_LIVES-php)
    # Boss is losing: -40 per missing HP (out of 10)
    score-=40*(10-bhp)
    # Player hidden in forest: uncertain shot
    if _ib(px,py) and grid[py][px]==FOREST: score-=20
    return score

ACTIONS=[*DIRS,"SHOOT"]

def minimax_no_ab(bp,bhp,pp,php,bd,pd,grid,depth,is_max):
    """
    Minimax WITHOUT alpha-beta pruning.
    Used only for node-count measurement for the project report.
    """
    _stats["no_ab"]+=1
    if depth==0 or php<=0 or bhp<=0:
        return evaluate(bp,bhp,pp,php,bd,grid)
    if is_max:
        val=float('-inf')
        for a in ACTIONS:
            if a=="SHOOT":
                # Boss shoots: if it hits player, player loses 1 life
                nhp=php-1 if _shoot_hits(bp,bd,grid,pp) else php
                v=minimax_no_ab(bp,bhp,pp,nhp,bd,pd,grid,depth-1,False)
            else:
                nbp=_move(bp,a,grid)
                v=minimax_no_ab(nbp,bhp,pp,php,a,pd,grid,depth-1,False)
            val=max(val,v)
        return val
    else:
        val=float('inf')
        for a in ACTIONS:
            if a=="SHOOT":
                # Player shoots: if it hits boss, boss loses 1 HP
                nbhp=bhp-1 if _shoot_hits(pp,pd,grid,bp) else bhp
                v=minimax_no_ab(bp,nbhp,pp,php,bd,pd,grid,depth-1,True)
            else:
                npp=_move(pp,a,grid)
                v=minimax_no_ab(bp,bhp,npp,php,bd,a,grid,depth-1,True)
            val=min(val,v)
        return val

def minimax(bp,bhp,pp,php,bd,pd,grid,depth,alpha,beta,is_max):
    """Minimax WITH alpha-beta pruning — used for actual boss decisions."""
    _stats["ab"]+=1
    if depth==0 or php<=0 or bhp<=0:
        return evaluate(bp,bhp,pp,php,bd,grid)
    if is_max:
        val=float('-inf')
        for a in ACTIONS:
            if a=="SHOOT":
                nhp=php-1 if _shoot_hits(bp,bd,grid,pp) else php
                v=minimax(bp,bhp,pp,nhp,bd,pd,grid,depth-1,alpha,beta,False)
            else:
                nbp=_move(bp,a,grid)
                v=minimax(nbp,bhp,pp,php,a,pd,grid,depth-1,alpha,beta,False)
            val=max(val,v); alpha=max(alpha,val)
            if alpha>=beta: break   # Beta cutoff
        return val
    else:
        val=float('inf')
        for a in ACTIONS:
            if a=="SHOOT":
                nbhp=bhp-1 if _shoot_hits(pp,pd,grid,bp) else bhp
                v=minimax(bp,nbhp,pp,php,bd,pd,grid,depth-1,alpha,beta,True)
            else:
                npp=_move(pp,a,grid)
                v=minimax(bp,bhp,npp,php,bd,a,grid,depth-1,alpha,beta,True)
            val=min(val,v); beta=min(beta,val)
            if alpha>=beta: break   # Alpha cutoff
        return val

def best_action(bp,bhp,pp,php,bd,pd,grid,depth):
    """
    Returns the best action for the boss tank.
    Also runs minimax_no_ab once for node-count data (project report requirement).
    """
    # Measure nodes WITHOUT pruning (for speedup ratio in report)
    minimax_no_ab(bp,bhp,pp,php,bd,pd,grid,depth,True)

    best_val=float('-inf'); best_a=DIRS[0]
    for a in ACTIONS:
        if a=="SHOOT":
            nhp=php-1 if _shoot_hits(bp,bd,grid,pp) else php
            v=minimax(bp,bhp,pp,nhp,bd,pd,grid,depth-1,float('-inf'),float('inf'),False)
        else:
            nbp=_move(bp,a,grid)
            v=minimax(nbp,bhp,pp,php,a,pd,grid,depth-1,float('-inf'),float('inf'),False)
        if v>best_val: best_val=v; best_a=a
    return best_a

def boss_phase(hp):
    """
    Returns phase number (1, 2, or 3) based on remaining HP.
    Phase 1: 10-7 HP  | Phase 2: 6-3 HP  | Phase 3: 2-1 HP
    """
    if hp>=7: return 1
    if hp>=3: return 2
    return 3

def phase_depth(phase):
    """
    Returns minimax search depth per phase.
    Phase 1: depth 2 | Phase 2: depth 3 | Phase 3: depth 4
    """
    return {1:2, 2:3, 3:4}[phase]
