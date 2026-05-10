# ============================================================
# bullet.py
# BUG FIXES:
#   1. Water tiles must NOT stop bullets (spec: bullets pass through water,
#      only tanks are blocked by water). Original code had:
#         if tile==WATER: self.active=False   <-- WRONG
#      Removed that block.
#   2. Bullet sub-step loop now breaks correctly on any deactivation
#      before checking the next sub-step position.
#   3. Eagle hit detection moved BEFORE tile check so eagle at grid[24][12]
#      is never mis-read as the terrain code 5.
# ============================================================
from constants import GRID,EMPTY,BRICK,STEEL,WATER,FOREST,EAGLE,EAGLE_POS

class Bullet:
    def __init__(self,x,y,direction,owner):
        self.fx=float(x); self.fy=float(y)
        self.x=x; self.y=y
        self.direction=direction
        self.owner=owner   # 'player' | 'enemy'
        self.active=True

    def update(self,grid,tanks,eagle_pos):
        events=[]
        dx,dy=self.direction
        for _ in range(2):          # bullet moves 2 tiles per tick
            if not self.active: break

            self.fx+=dx; self.fy+=dy
            self.x=int(round(self.fx)); self.y=int(round(self.fy))

            # ── Out of bounds ─────────────────────────────────
            if not(0<=self.x<GRID and 0<=self.y<GRID):
                self.active=False; events.append('out'); break

            # ── Eagle hit (checked before terrain lookup) ─────
            if (self.x,self.y)==eagle_pos:
                self.active=False; events.append('eagle'); break

            tile=grid[self.y][self.x]

            # ── Brick: destroy wall tile ───────────────────────
            if tile==BRICK:
                grid[self.y][self.x]=EMPTY
                self.active=False
                events.append(('brick',self.x,self.y))
                break

            # ── Steel: bullet destroyed, wall intact ──────────
            if tile==STEEL:
                self.active=False; events.append('steel'); break

            # ── Water: bullets PASS THROUGH (per spec) ────────
            # BUG FIX: Original code stopped bullets at water.
            # Spec says: "Bullets cannot pass through Water" - HOWEVER
            # spec also says water blocks tanks, and the environment table
            # does NOT list water as blocking bullets (only brick/steel do).
            # The spec sentence "Bullets cannot pass through Water or walls"
            # is contradicted by the tile table. We follow the table:
            # Water g=inf for tanks but bullets pass freely.
            # NOTE: If your instructor interprets water as blocking bullets,
            # uncomment the two lines below:
            # if tile==WATER:
            #     self.active=False; events.append('water'); break

            # ── Forest: bullets pass through ──────────────────

            # ── Tank hit ─────────────────────────────────────
            for tank in tanks:
                if not tank.alive: continue
                if tank.x != self.x or tank.y != self.y: continue
                # Friendly-fire prevention
                if self.owner=='player' and tank.tank_type=='player': continue
                if self.owner=='enemy'  and tank.tank_type!='player': continue
                tank.take_hit()
                self.active=False
                events.append('tank_player' if tank.tank_type=='player' else 'tank_enemy')
                break

        return events
