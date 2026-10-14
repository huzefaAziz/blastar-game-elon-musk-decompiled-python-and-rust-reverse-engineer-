"""
BLASTAR  -  Reverse-engineered from E. R. Musk's 1984 MSX-BASIC original.

Controls : Arrow keys = joystick,  SPACE (or Shift) = fire
Quit     : ESC
"""
import math
import random
import sys

import pygame

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# ------------------------------------------------------------------- init
pygame.init()
SOUND_OK = True
try:
    pygame.mixer.pre_init(22050, -16, 1, 256)
    pygame.mixer.init()
except pygame.error:
    SOUND_OK = False

BASE_W, BASE_H = 256, 192          # MSX graphics resolution
SCALE = 3
screen = pygame.display.set_mode((BASE_W * SCALE, BASE_H * SCALE))
pygame.display.set_caption("BLASTAR  -  by E.R. MUSK")
clock = pygame.time.Clock()
canvas = pygame.Surface((BASE_W, BASE_H))

# MSX-ish palette
BLACK   = (0, 0, 0)
WHITE   = (240, 240, 240)
GREEN   = (0, 220, 0)
YELLOW  = (255, 220, 0)
BLUE    = (60, 60, 255)
RED     = (220, 0, 0)
CYAN    = (0, 220, 220)

# ------------------------------------------------------------- sprite data
# Each sprite is 8 rows × 8 bits, copied verbatim from the DATA blocks.
sprite_data = {
    1: ["10011001", "10011001", "10011001", "11100111",
        "11000011", "11000011", "11000011", "11000011"],   # player ship
    2: ["00000000", "00000000", "01000010", "10100101",
        "01000010", "00000000", "00000000", "00000000"],   # rocket
    3: ["00011000", "01000010", "11100111", "10111101",
        "01011010", "00100100", "00111100", "01100110"],   # alien freighter
    4: ["01010110", "11001101", "10010101", "01011011",
        "00011001", "11010011", "01100101", "01011100"],   # debris / explosion
    5: ["00000000", "00010000", "00111000", "01111100",
        "01111100", "00111000", "00010000", "00000000"],   # status beam bomb
}

def make_sprite(idx, color):
    s = pygame.Surface((8, 8), pygame.SRCALPHA)
    for y, row in enumerate(sprite_data[idx]):
        for x, c in enumerate(row):
            if c == '1':
                s.set_at((x, y), color)
    return s

ship_spr      = make_sprite(1, YELLOW)
rocket_spr    = make_sprite(2, CYAN)
alien_spr     = make_sprite(3, GREEN)
explosion_spr = make_sprite(4, RED)
beam_spr      = make_sprite(5, BLUE)

# ------------------------------------------------------------------ audio
NOTE_FREQ = {'C': 261.63, 'D': 293.66, 'E': 329.63, 'F': 349.23,
             'G': 392.00, 'A': 440.00, 'B': 493.88}

def synth(samples, vol=0.18):
    if not SOUND_OK:
        return None
    
    # Check if the system forced a stereo mixer
    mixer_info = pygame.mixer.get_init()
    channels = mixer_info[2] if mixer_info else 1
    
    if HAS_NUMPY:
        a = np.asarray(samples, dtype=np.float32)
        a = np.clip(a * vol, -1, 1)
        a = (a * 32767).astype(np.int16)
        # If the mixer is stereo, convert 1D array to 2D array (samples, 2)
        if channels == 2 and a.ndim == 1:
            a = np.column_stack((a, a))
        return pygame.sndarray.make_sound(a)
    else:
        buf = bytearray()
        for s in samples:
            v = int(max(-1, min(1, s * vol)) * 32767)
            b = v.to_bytes(2, 'little', signed=True)
            buf.extend(b)
            # If stereo, duplicate the mono sample for left and right channels
            if channels == 2:
                buf.extend(b)
        return pygame.mixer.Sound(buffer=bytes(buf))

def make_tone(freq, dur_ms, vol=0.25, decay=0.3):
    rate = 22050
    n = max(1, int(rate * dur_ms / 1000))
    if HAS_NUMPY:
        t = np.arange(n) / rate
        env = np.maximum(0.0, 1.0 - np.arange(n) / n * decay)
        wave = np.where(np.sin(2 * np.pi * freq * t) > 0, 1.0, -1.0)
        return synth(env * wave, vol)
    samples = []
    for i in range(n):
        env = max(0.0, 1 - i / n * decay)
        samples.append(env * (1 if math.sin(2 * math.pi * freq * i / rate) > 0 else -1))
    return synth(samples, vol)

def make_melody(notes, octave, dur_ms, vol=0.14):
    rate = 22050
    n_per = max(1, int(rate * dur_ms / 1000))
    if HAS_NUMPY:
        out = np.zeros(n_per * len(notes), dtype=np.float32)
        for k, ch in enumerate(notes):
            if ch in NOTE_FREQ:
                f = NOTE_FREQ[ch] * (2 ** (octave - 4))
                t = (np.arange(n_per) + k * n_per) / rate
                env = np.maximum(0.0, 1.0 - np.arange(n_per) / n_per * 0.25)
                out[k*n_per:(k+1)*n_per] = env * np.where(
                    np.sin(2 * np.pi * f * t) > 0, 1.0, -1.0)
        return synth(out, vol)
    samples = []
    for ch in notes:
        if ch in NOTE_FREQ:
            f = NOTE_FREQ[ch] * (2 ** (octave - 4))
            for i in range(n_per):
                env = max(0.0, 1 - i / n_per * 0.25)
                samples.append(env * (1 if math.sin(2*math.pi*f*i/rate) > 0 else -1))
    return synth(samples, vol)

TUNE = "CECECDBABADACECEBDACDBDCEGG"
music_o3 = make_melody(TUNE, 3, 50)
music_o4 = make_melody(TUNE, 4, 50)
snd_beep       = make_tone(880, 80, 0.25)
snd_shoot      = make_melody("DF", 4, 40, 0.30)
snd_alien      = make_tone(196, 150, 0.20, decay=0.1)
snd_explosion  = make_tone(110, 220, 0.30, decay=0.6)
snd_hit        = make_tone(90,  400, 0.30, decay=0.7)

# ------------------------------------------------------------------- fonts
font_big   = pygame.font.SysFont("Courier", 20, bold=True)
font_med   = pygame.font.SysFont("Courier", 12, bold=True)
font_small = pygame.font.SysFont("Courier", 10, bold=True)

# ----------------------------------------------------------- game class
class Game:
    def __init__(self):
        self.state = 'title'
        self.state_timer = 0
        self.SH = 5
        self.SC = 0
        self.reset_playfield()
        self.explosion_t = 0
        self.flash_t = 0
        self.music_idx = 0
        self.music_channel = None
        self.play_next_music()

    def reset_playfield(self):
        self.P = 120            # player X (column)
        self.C = 180            # player Y (row)
        self.H = 30             # alien X
        self.G = 15             # alien Y
        self.rocket_active = False
        self.U = self.W = 0
        self.beam_active = False
        self.OO = self.NN = 0

    def reset_game(self):
        self.SH = 5
        self.SC = 0
        self.reset_playfield()

    def play_next_music(self):
        if not SOUND_OK:
            return
        if self.music_idx % 2 == 0:
            snd = music_o3
        else:
            snd = music_o4
        self.music_idx += 1
        if snd:
            self.music_channel = snd.play()

# ----------------------------------------------------------- title screen
def draw_title():
    canvas.fill(BLACK)
    t = font_big.render("BLASTAR", True, WHITE)
    canvas.blit(t, (104, 8))

def draw_author():
    canvas.fill(BLACK)
    t = font_med.render("  BY E.R.MUSK", True, WHITE)
    canvas.blit(t, (60, 80))

def draw_instr_prompt():
    canvas.fill(BLACK)
    canvas.blit(font_med.render("              BLASTAR", True, WHITE), (8, 32))
    canvas.blit(font_med.render("         DO YOU NEED INSTRUCTIONS", True, WHITE), (8, 56))
    canvas.blit(font_med.render("                 (Y/N)", True, WHITE), (8, 72))

def draw_instr():
    canvas.fill(BLACK)
    # Box from  CIRCLE(45,90),0 : DRAW"u80 r180 d80 l180"
    pts = [(45, 90), (45, 10), (225, 10), (225, 90), (45, 90)]
    pygame.draw.lines(canvas, WHITE, False, pts)
    canvas.blit(font_small.render("<       USE JOYSTICK        >", True, WHITE), (50, 100))
    canvas.blit(font_small.render("    FOR CONTROL AND", True, WHITE), (60, 112))
    canvas.blit(font_small.render("      FIRE BUTTON", True, WHITE), (70, 124))
    canvas.blit(font_small.render("       TO SHOOT", True, WHITE), (80, 136))
    canvas.blit(font_small.render("MISSION:DESTROY ALIEN FREIGHTER", True, WHITE), (8, 156))
    canvas.blit(font_small.render("CARRYING DEADLY HYDROGEN BOMBS", True, WHITE), (8, 168))
    canvas.blit(font_small.render("AND STATUS BEAM MACHINES", True, WHITE), (8, 180))

# ----------------------------------------------------------- gameplay
def get_stick(keys):
    up    = keys[pygame.K_UP]
    down  = keys[pygame.K_DOWN]
    left  = keys[pygame.K_LEFT]
    right = keys[pygame.K_RIGHT]
    if up and not (left or right):           return 1
    if up and right:                          return 2
    if right and not (up or down):            return 3
    if down and right:                        return 4
    if down and not (left or right):          return 5
    if down and left:                        return 6
    if left and not (up or down):             return 7
    if up and left:                          return 8
    return 0

def update_game(g, keys):
    # ---- move player (same increments as STICK branches) ----
    P, C = g.P, g.C
    D = get_stick(keys)
    if   D == 1: P, C = P + 0, C - 4
    elif D == 2: P, C = P + 2, C - 2
    elif D == 3: P, C = P + 4, C + 0
    elif D == 4: P, C = P + 2, C + 2
    elif D == 5: P, C = P + 0, C + 4
    elif D == 6: P, C = P - 2, C + 2
    elif D == 7: P, C = P - 4, C + 0
    elif D == 8: P, C = P - 2, C - 2
    # bounds (lines 750-780)
    if C < 10:  C = 10
    if C > 190: C = 180
    if P < 10:  P = 10
    if P > 240: P = 240
    g.P, g.C = P, C

    # ---- fire button ----
    fire = keys[pygame.K_SPACE] or keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
    if fire and not g.rocket_active:
        g.rocket_active = True
        g.U = g.P
        g.W = g.C - 5
        if SOUND_OK and snd_shoot: snd_shoot.play()

    # ---- alien scroll (always; H = H + 3, wrap at 250) ----
    g.H += 3
    if g.H > 250: g.H = 10

    # ---- alien fires status beam when X-aligned with player ----
    if not g.beam_active and abs(g.H - g.P) <= 1:
        g.beam_active = True
        g.OO = g.H
        g.NN = g.G + 5
        if SOUND_OK and snd_alien: snd_alien.play()

    # ---- update beam (NN += 4, drop until > 205) ----
    if g.beam_active:
        g.NN += 4
        if g.NN > 205:
            g.beam_active = False

    # ---- update rocket (W -= 6, off-screen at < -10) ----
    if g.rocket_active:
        g.W -= 6
        if g.W < -10:
            g.rocket_active = False

    # ---- collision: rocket vs alien (sprite overlap ~8 px) ----
    if g.rocket_active and abs(g.U - g.H) < 8 and abs(g.W - g.G) < 8:
        g.SC += 80
        g.rocket_active = False
        g.explosion_t = 20
        if SOUND_OK and snd_explosion: snd_explosion.play()
        # alien respawn (lines 1030): random Y in [20, 170), X = 0
        g.G = 20 + int(150 * random.random())
        g.H = 0

    # ---- collision: beam vs player ----
    if g.beam_active and abs(g.OO - g.P) < 8 and abs(g.NN - g.C) < 8:
        g.SH -= 1
        g.beam_active = False
        g.flash_t = 30
        if SOUND_OK and snd_hit: snd_hit.play()
        g.G = 20 + int(170 * random.random())
        g.H = 0
        if g.SH < 0:
            g.state = 'game_over'
            g.state_timer = 0

    if g.explosion_t > 0: g.explosion_t -= 1
    if g.flash_t > 0:     g.flash_t     -= 1

def draw_game(g):
    if g.flash_t > 0 and g.flash_t % 4 < 2:
        canvas.fill(RED)
    else:
        canvas.fill(BLACK)

    canvas.blit(font_small.render(
        f"SCORE {g.SC}            SHIPS {g.SH}", True, WHITE), (0, 0))

    canvas.blit(ship_spr,  (int(g.P), int(g.C)))
    canvas.blit(alien_spr, (int(g.H), int(g.G)))

    if g.rocket_active:
        canvas.blit(rocket_spr, (int(g.U), int(g.W)))

    if g.beam_active:
        canvas.blit(font_small.render("STATUS BEAM", True, WHITE), (120, 120))
        canvas.blit(beam_spr, (int(g.OO), int(g.NN)))

    if g.explosion_t > 0:
        canvas.blit(explosion_spr, (int(g.H), int(g.G)))

def draw_game_over(g):
    canvas.fill(BLACK)
    canvas.blit(font_med.render("                  BLASTAR", True, WHITE), (0, 0))
    canvas.blit(font_med.render("             FLEET DESTROYED", True, WHITE), (0, 16))
    canvas.blit(font_med.render("      WOULD YOU LIKE ANOTHER GAME", True, WHITE), (0, 32))
    canvas.blit(font_small.render(f"            FINAL SCORE  {g.SC}", True, YELLOW), (0, 56))
    canvas.blit(font_small.render("               (Y/N)", True, WHITE), (0, 72))

# ----------------------------------------------------------- main loop
g = Game()
running = True
while running:
    clock.tick(30)
    events = pygame.event.get()
    for e in events:
        if e.type == pygame.QUIT:
            running = False
        elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            running = False

    keys = pygame.key.get_pressed()
    canvas.fill(BLACK)

    if g.state == 'title':
        draw_title()
        g.state_timer += 1
        # auto-advance after ~7 s, or skip on key
        if g.state_timer > 30 * 7:
            g.state = 'author'; g.state_timer = 0; g.play_next_music()
        for e in events:
            if e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_SPACE):
                g.state = 'author'; g.state_timer = 0; g.play_next_music()
        # chain music
        if SOUND_OK and (g.music_channel is None or not g.music_channel.get_busy()):
            g.play_next_music()

    elif g.state == 'author':
        draw_author()
        g.state_timer += 1
        if g.state_timer > 30 * 6:
            g.state = 'instr_prompt'; g.state_timer = 0
        for e in events:
            if e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_SPACE):
                g.state = 'instr_prompt'; g.state_timer = 0
        if SOUND_OK and (g.music_channel is None or not g.music_channel.get_busy()):
            g.play_next_music()

    elif g.state == 'instr_prompt':
        draw_instr_prompt()
        for e in events:
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_y:
                    if SOUND_OK and snd_beep: snd_beep.play()
                    g.state = 'instr'; g.state_timer = 0
                elif e.key in (pygame.K_n, pygame.K_RETURN, pygame.K_SPACE):
                    if SOUND_OK and snd_beep: snd_beep.play()
                    g.reset_game(); g.state = 'playing'; g.state_timer = 0

    elif g.state == 'instr':
        draw_instr()
        for e in events:
            if e.type == pygame.KEYDOWN:
                g.reset_game(); g.state = 'playing'; g.state_timer = 0

    elif g.state == 'playing':
        update_game(g, keys)
        draw_game(g)

    elif g.state == 'game_over':
        draw_game_over(g)
        for e in events:
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_y:
                    g.reset_game(); g.state = 'title'
                    g.state_timer = 0; g.play_next_music()
                elif e.key == pygame.K_n:
                    running = False

    scaled = pygame.transform.scale(canvas, (BASE_W * SCALE, BASE_H * SCALE))
    screen.blit(scaled, (0, 0))
    pygame.display.flip()

pygame.quit()
sys.exit()