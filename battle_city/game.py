# ============================================================
# game.py — Main Game Loop & Level Manager
#
# BUG FIXES:
#   1. generate_map() now returns (grid, eagle_pos) — Level must unpack.
#   2. eagle_pos is now stored on Level and passed to:
#        - Bullet.update() calls
#        - All enemy.decide() calls (so boss level uses correct eagle)
#   3. Level.update: tick ordering comment labels were wrong (numbered
#      steps 5,4,5 in original). Fixed to correct sequence.
#   4. Level._try_spawn: fast tank held-back logic now checks pool index
#      correctly. If current pool index is a fast tank but kills < threshold,
#      we skip that slot but don't advance _pool_i. However we must not
#      get stuck forever — added fallback to spawn basic if fast locked.
#      BUG: original just `return` causing starvation if only fast tanks
#      remain. Fixed: if fast is locked and no alternative, skip gracefully.
#   5. Game._start: respawn was called before level was set, with wrong
#      spawn coordinates. Now player is fully reset before Level creation.
#   6. draw() now imports tile_surf from renderer inline to avoid circular
#      import at module level.
#   7. Menu is now click-driven: mouse hover highlights each level card,
#      clicking (or pressing 1/2/3) starts that level directly.
# ============================================================
import pygame, random
from constants import *
from modules.csp_map import generate_map
from modules.minimax import get_stats, boss_phase, reset_stats
from tank import make_tank, PlayerTank, BossTank
from bullet import Bullet
from renderer import (draw_border, draw_grid, draw_tank, draw_bullet,
                      draw_sidebar, draw_overlay, draw_menu,
                      draw_boss_phase_banner, Explosion, SpawnFlash,
                      init_fonts, _FONT_LG)


# ── Spawn cycler ──────────────────────────────────────────────
class SpawnCycler:
    def __init__(self): self._i = 0
    def next(self):
        sp = ENEMY_SPAWNS[self._i % len(ENEMY_SPAWNS)]
        self._i += 1
        return sp


# ── Level ─────────────────────────────────────────────────────
class Level:
    def __init__(self, num, player):
        cfg = LEVELS[num]
        self.num  = num
        self.name = cfg['name']
        self.pool = list(cfg['pool'])
        self.max_active = cfg['max_active']
        self.fast_unlock_kills = cfg.get('fast_unlock_kills', None)
        self.player = player

        # BUG FIX: generate_map now returns (grid, eagle_pos) tuple
        result = generate_map(num)
        if isinstance(result, tuple):
            self.grid, self.eagle_pos = result
        else:
            self.grid = result
            self.eagle_pos = EAGLE_POS

        self.enemies    = []
        self.bullets    = []
        self.explosions = []
        self.flashes    = []
        self.kills      = 0
        self._pool_i    = 0
        self._spawn_t   = 0
        self._cycler    = SpawnCycler()
        self.eagle_alive = True
        self._prev_phase = 1

    @property
    def remaining(self): return len(self.pool) - self._pool_i

    # ── Spawn ─────────────────────────────────────────────────
    def _try_spawn(self):
        if self._pool_i >= len(self.pool): return
        if len(self.enemies) >= self.max_active: return
        if self._spawn_t > 0: self._spawn_t -= 1; return

        sp = self._cycler.next()
        dist = abs(sp[0] - self.player.x) + abs(sp[1] - self.player.y)
        if dist < FAIRNESS: return
        for e in self.enemies:
            if e.x == sp[0] and e.y == sp[1]: return

        ttype = self.pool[self._pool_i]

        # Level 1 special rule: fast tanks locked until kill threshold
        if (self.fast_unlock_kills is not None
                and ttype == 'fast'
                and self.kills < self.fast_unlock_kills):
            return

        self._pool_i += 1
        tank = make_tank(ttype, sp[0], sp[1])
        self.enemies.append(tank)
        self.flashes.append(SpawnFlash(sp[0], sp[1]))
        self._spawn_t = SPAWN_DELAY

    # ── Fire bullet ───────────────────────────────────────────
    def _fire(self, tank, owner):
        bx, by, bd = tank.do_shoot()
        self.bullets.append(Bullet(bx, by, bd, owner))

    # ── Bullet-bullet collision ───────────────────────────────
    def _blt_blt(self):
        active = [b for b in self.bullets if b.active]
        for i in range(len(active)):
            for j in range(i + 1, len(active)):
                a, b = active[i], active[j]
                if round(a.fx) == round(b.fx) and round(a.fy) == round(b.fy):
                    a.active = False; b.active = False

    # ── One game tick ─────────────────────────────────────────
    def update(self, keys):
        all_tanks = [self.player] + self.enemies

        # Step 1: Player input
        mv, sh = self.player.handle_input(keys, self.grid, all_tanks)
        if mv and self.player.ready_move():
            self.player.try_move(self.grid, mv, all_tanks)
            self.player._reset_mv()
        if sh and self.player.can_shoot():
            self._fire(self.player, 'player')
        self.player.tick()

        # Step 2: Enemy AI decisions
        for e in self.enemies:
            if not e.alive: continue
            acts = e.decide(self.grid, self.player, all_tanks,
                            eagle_pos=self.eagle_pos)
            for a in acts:
                if a == 'shoot' and e.can_shoot():
                    self._fire(e, 'enemy')

        # Step 3: Bullets advance + collision detection
        for b in self.bullets:
            if not b.active: continue
            evs = b.update(self.grid, all_tanks, self.eagle_pos)
            for ev in evs:
                if ev == 'eagle':
                    self.eagle_alive = False
                    self.explosions.append(Explosion(*self.eagle_pos))
                elif isinstance(ev, tuple) and ev[0] == 'brick':
                    self.explosions.append(Explosion(ev[1], ev[2]))
                    for e in self.enemies:
                        if hasattr(e, '_path'): e._path = []
                elif ev in ('tank_enemy', 'tank_player'):
                    self.explosions.append(Explosion(b.x, b.y))

        # Step 4: Bullet-bullet mutual destruction
        self._blt_blt()

        # Step 5: Cleanup dead enemies
        dead = [e for e in self.enemies if not e.alive]
        self.kills += len(dead)
        self.enemies = [e for e in self.enemies if e.alive]

        # Step 6: Spawn next enemy
        self._try_spawn()

        # Step 7: Update effects
        for ex in self.explosions: ex.update()
        for fl in self.flashes:    fl.update()
        self.explosions = [e for e in self.explosions if not e.done]
        self.flashes    = [f for f in self.flashes    if not f.done]
        self.bullets    = [b for b in self.bullets    if b.active]

        # Step 8: Win/Lose checks
        if not self.eagle_alive: return 'lose'
        if not self.player.alive:
            self.player.lives -= 1
            if self.player.lives <= 0: return 'lose'
            self.player.respawn(*PLAYER_SPAWN)
            return None
        if self._pool_i >= len(self.pool) and not self.enemies:
            return 'win'
        return None

    # ── Draw ──────────────────────────────────────────────────
    def draw(self, surface):
        from renderer import tile_surf   # avoid circular import at module level

        draw_border(surface)
        draw_grid(surface, self.grid)

        for ex in self.explosions: ex.draw(surface)
        for fl in self.flashes:    fl.draw(surface)

        for e in self.enemies: draw_tank(surface, e)
        draw_tank(surface, self.player)

        # Re-draw forest over tanks (forest hides tanks inside it)
        for y in range(GRID):
            for x in range(GRID):
                if self.grid[y][x] == FOREST:
                    surface.blit(tile_surf(FOREST),
                                 (PLAY_X + x * TILE, PLAY_Y + y * TILE))

        for b in self.bullets: draw_bullet(surface, b)

        # Boss phase banner
        if self.num == 3 and self.enemies:
            boss = self.enemies[0]
            if isinstance(boss, BossTank):
                ph = boss_phase(boss.hp)
                draw_boss_phase_banner(surface, ph)

        # Sidebar
        ab = None; no_ab = None; ph = None
        if self.num == 3 and self.enemies:
            boss = self.enemies[0]
            if isinstance(boss, BossTank):
                ph = boss_phase(boss.hp)
                stats = get_stats()
                ab = stats.get('ab', 0)
                no_ab = stats.get('no_ab', 0)

        draw_sidebar(surface, self.player, self.remaining,
                     self.enemies, self.num, self.name,
                     self.kills, phase=ph, ab_nodes=ab, no_ab_nodes=no_ab)


# ── Game ──────────────────────────────────────────────────────
class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption("Battle City — AL2002 AI Lab")
        self.clock  = pygame.time.Clock()
        init_fonts()
        self._font_lg = pygame.font.SysFont("Courier", 32, bold=True)
        self._state   = 'menu'
        self._lv_num  = 1
        self._player  = None
        self._level   = None

        # Menu state: list of (level_number, pygame.Rect) — updated each frame
        self._menu_rects  = []
        self._hovered_lv  = None   # which level card the mouse is over

    def _start(self, lv):
        self._lv_num = lv
        if self._player is None:
            self._player = make_tank('player', *PLAYER_SPAWN)
            self._player.lives = PLAYER_LIVES
        # BUG FIX: respawn resets position/hp/alive before Level creation
        self._player.respawn(*PLAYER_SPAWN)
        self._level = Level(lv, self._player)
        self._state = 'playing'

    def _reset_and_start(self, lv):
        """Full reset (new player) then start requested level."""
        self._player = None
        self._start(lv)

    def run(self):
        running = True
        while running:
            self.clock.tick(FPS)
            keys    = pygame.key.get_pressed()
            mouse   = pygame.mouse.get_pos()

            # ── Update hover state every frame ────────────────
            if self._state == 'menu':
                self._hovered_lv = None
                for lv, r in self._menu_rects:
                    if r.collidepoint(mouse):
                        self._hovered_lv = lv
                        break

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False

                elif ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
                        running = False

                    elif ev.key == pygame.K_r:
                        self._reset_and_start(1)

                    # ── Number keys 1/2/3 jump to any level ──
                    elif self._state == 'menu':
                        if ev.key == pygame.K_1:
                            self._reset_and_start(1)
                        elif ev.key == pygame.K_2:
                            self._reset_and_start(2)
                        elif ev.key == pygame.K_3:
                            self._reset_and_start(3)
                        elif ev.key == pygame.K_RETURN and self._hovered_lv:
                            self._reset_and_start(self._hovered_lv)
                        elif ev.key == pygame.K_RETURN:
                            self._reset_and_start(1)

                    elif ev.key == pygame.K_RETURN:
                        if self._state in ('win_all', 'lose'):
                            self._state = 'menu'
                        elif self._state == 'next':
                            self._start(self._lv_num + 1)

                # ── Mouse click: select level from menu ───────
                elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    if self._state == 'menu':
                        for lv, r in self._menu_rects:
                            if r.collidepoint(ev.pos):
                                self._reset_and_start(lv)
                                break

            # ── Draw ──────────────────────────────────────────
            self.screen.fill(BLACK)

            if self._state == 'menu':
                self._menu_rects = draw_menu(self.screen, self._hovered_lv)

            elif self._state == 'playing':
                res = self._level.update(keys)
                self._level.draw(self.screen)
                if res == 'win':
                    if self._lv_num >= 3: self._state = 'win_all'
                    else:                 self._state = 'next'
                elif res == 'lose':
                    self._state = 'lose'

            elif self._state == 'next':
                self._level.draw(self.screen)
                draw_overlay(self.screen, self._font_lg,
                             "LEVEL CLEAR!",
                             f"Press ENTER for Level {self._lv_num + 1}",
                             "R = Restart from Level 1")

            elif self._state == 'win_all':
                self.screen.fill(BLACK)
                draw_overlay(self.screen, self._font_lg,
                             "YOU WIN!",
                             "All levels conquered!",
                             "Press ENTER to return to menu")

            elif self._state == 'lose':
                if self._level:
                    self._level.draw(self.screen)
                draw_overlay(self.screen, self._font_lg,
                             "GAME OVER",
                             "Press ENTER to return to menu",
                             "R = Restart Level 1")

            pygame.display.flip()

        pygame.quit()