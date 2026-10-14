// src/main.rs
// BLASTAR - reverse-engineered from E. R. Musk's MSX-BASIC listing.
// Original hardware: MSX (SCREEN2 256x192, 8x8 hardware sprites).
// This port: macroquad, 256x192 internal logical resolution scaled 3x to 768x576.

use macroquad::prelude::*;

// Scale factor to map original 256x192 coordinates to our 768x576 window.
const SCALE: f32 = 3.0;

// ---------------------------------------------------------------------------
// Sprite data - verbatim from the BASIC DATA lines (1250+).
// Each byte is one row of an 8x8 sprite; bit 7 = leftmost pixel.
// ---------------------------------------------------------------------------
const PLAYER_SPRITE: [u8; 8] = [
    0b10011001, // DATA line 1260
    0b10011001,
    0b10011001,
    0b11100111,
    0b11000011,
    0b11000011,
    0b11000011,
    0b11000011,
];

const ROCKET_SPRITE: [u8; 8] = [
    0b00000000,
    0b00000000,
    0b01000010,
    0b10100101,
    0b01000010,
    0b00000000,
    0b00000000,
    0b00000000,
];

const ALIEN_SPRITE: [u8; 8] = [
    0b00011000,
    0b01000010,
    0b11100111,
    0b10111101,
    0b01011010,
    0b00100100,
    0b00111100,
    0b01100110,
];

const EXPLOSION_SPRITE: [u8; 8] = [
    0b01010110,
    0b11001101,
    0b10010101,
    0b01011011,
    0b00011001,
    0b11010011,
    0b01100101,
    0b01011100,
];

const BOMB_SPRITE: [u8; 8] = [
    0b00000000,
    0b00010000,
    0b00111000,
    0b01111100,
    0b01111100,
    0b00111000,
    0b00010000,
    0b00000000,
];

// MSX palette approximations.
const C_YELLOW : Color = Color::from_rgba(221, 221,  30, 255);
const C_CYAN   : Color = Color::from_rgba( 80, 180, 255, 255);
const C_LIME   : Color = Color::from_rgba(180, 220,  30, 255);
const C_RED    : Color = Color::from_rgba(220,  40,  40, 255);
const C_ORANGE : Color = Color::from_rgba(255, 120,   0, 255);
const C_WHITE  : Color = Color::from_rgba(255, 255, 255, 255);

// ---------------------------------------------------------------------------
// Sprite blitter - equivalent to MSX `PUT SPRITE n,(x,y),col,pat`.
// ---------------------------------------------------------------------------
fn draw_sprite(x: f32, y: f32, sprite: &[u8; 8], color: Color, scale: f32) {
    for row in 0..8u32 {
        let bits = sprite[row as usize];
        for col in 0..8u32 {
            if (bits >> (7 - col)) & 1 == 1 {
                draw_rectangle(
                    x + col as f32 * scale,
                    y + row as f32 * scale,
                    scale,
                    scale,
                    color,
                );
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Game states - every GOTO/GOSUB target in the original maps to one of these.
// ---------------------------------------------------------------------------
#[derive(Clone, Copy, PartialEq)]
enum State {
    Title,        // lines 60-160
    Prompt,       // lines 170-230   "DO YOU NEED INSTRUCTIONS (Y/N)"
    Instructions, // lines 240-270
    Playing,      // lines 560-1030
    GameOver,     // lines 1200-1230
}

struct Game {
    state: State,
    score: i32,
    ships: i32,
    // player position (BASIC vars P,C) - MSX origin top-left.
    px: f32, py: f32,
    // alien freighter (BASIC vars H,G).
    ax: f32, ay: f32,
    alien_speed: f32,
    // player's rocket (BASIC vars U,W; F=-1 means active).
    rocket: bool, rx: f32, ry: f32,
    // alien's status-beam bomb (BASIC vars OO,NN).
    bomb: bool, bx: f32, by: f32,
    // explosion timer for the 20-frame CLS flash at line 1030.
    expl: f32, ex: f32, ey: f32,
    // title screen dwell.
    title_t: f32,
}

impl Game {
    fn new() -> Self {
        Self {
            state: State::Title,
            score: 0,
            ships: 5,
            px: 120.0, py: 180.0,
            ax: 30.0,  ay: 15.0,
            alien_speed: 90.0,
            rocket: false, rx: 0.0, ry: 0.0,
            bomb: false, bx: 0.0, by: 0.0,
            expl: 0.0, ex: 0.0, ey: 0.0,
            title_t: 0.0,
        }
    }

    fn reset_play(&mut self) {
        self.score = 0;
        self.ships = 5;
        self.px = 120.0; self.py = 180.0;
        self.ax = 30.0;  self.ay = 15.0;
        self.alien_speed = 90.0;
        self.rocket = false;
        self.bomb = false;
        self.expl = 0.0;
    }

    fn update(&mut self, dt: f32) {
        match self.state {
            State::Title => {
                self.title_t += dt;
                if self.title_t > 2.5 { self.state = State::Prompt; }
            }
            State::Prompt => {
                if is_key_pressed(KeyCode::Y) { self.state = State::Instructions; }
                else if is_key_pressed(KeyCode::N) { self.state = State::Playing; }
            }
            State::Instructions => {
                if is_key_pressed(KeyCode::Space) || is_key_pressed(KeyCode::Enter) {
                    self.state = State::Playing;
                }
            }
            State::Playing => {
                // ---- Player movement: original maps STICK(1) 1..8 onto
                //      P,C deltas (lines 650-730). Here we use arrow keys.
                let s = 120.0;
                if is_key_down(KeyCode::Left)  { self.px -= s * dt; }
                if is_key_down(KeyCode::Right) { self.px += s * dt; }
                if is_key_down(KeyCode::Up)    { self.py -= s * 0.7 * dt; }
                if is_key_down(KeyCode::Down)  { self.py += s * 0.7 * dt; }
                // Lines 750-780: clamp.
                self.px = self.px.clamp(10.0, 240.0);
                self.py = self.py.clamp(80.0, 184.0);

                // ---- Alien freighter (lines 800-830): H = H + 3 each frame.
                self.ax += self.alien_speed * dt;
                if self.ax > 248.0 { self.ax = 8.0; }

                // ---- Fire button (STRIG(1) -> -1 when pressed): lines 860-870.
                if is_key_pressed(KeyCode::Space) && !self.rocket {
                    self.rocket = true;
                    self.rx = self.px;
                    self.ry = self.py - 10.0;
                }

                // ---- Rocket motion + hit-test (lines 870-1010).
                if self.rocket {
                    self.ry -= 240.0 * dt;
                    if self.ry < -10.0 { self.rocket = false; }
                    // line 950:  IF H=P THEN 1050  (alien hit player x).
                    if (self.rx - self.ax).abs() < 10.0
                       && (self.ry - self.ay).abs() < 10.0
                    {
                        self.rocket = false;
                        self.score += 80;                          // SC=SC+80
                        self.expl = 0.4;                            // 20-frame flash
                        self.ex = self.ax; self.ey = self.ay;
                        // line 1030: respawn alien at random G.
                        self.ay = 15.0 + rand::gen_range(0.0, 60.0);
                        self.ax = 8.0;
                        self.alien_speed *= 1.05;                   // escalate
                    }
                }

                // ---- Alien drops a "status beam" bomb - original uses
                //      ON INTERVAL=30 GOSUB 650 to make it periodic.
                if !self.bomb && rand::gen_range(0.0, 1.0) < 0.8 * dt {
                    self.bomb = true;
                    self.bx = self.ax;
                    self.by = self.ay + 8.0;
                }
                if self.bomb {
                    self.by += 120.0 * dt;
                    if self.by > 200.0 { self.bomb = false; }
                    // lines 1110-1180: ON SPRITE collision.
                    if (self.bx - self.px).abs() < 10.0
                       && (self.by - self.py).abs() < 10.0
                    {
                        self.bomb = false;
                        self.ships -= 1;
                        self.expl = 0.4;
                        self.ex = self.px; self.ey = self.py;
                        if self.ships <= 0 { self.state = State::GameOver; }
                    }
                }

                if self.expl > 0.0 { self.expl -= dt; }
            }
            State::GameOver => {
                // line 1220:  IF A$="Y" THEN RUN
                if is_key_pressed(KeyCode::Y) {
                    self.reset_play();
                    self.state = State::Playing;
                }
                if is_key_pressed(KeyCode::N) || is_key_pressed(KeyCode::Escape) {
                    std::process::exit(0);
                }
            }
        }
    }

    fn draw(&self) {
        clear_background(BLACK);

        match self.state {
            State::Title => {
                draw_text("BLASTAR",     60.0 * SCALE,  60.0 * SCALE, 28.0 * SCALE, C_YELLOW);
                draw_text("BY E.R. MUSK", 70.0 * SCALE, 100.0 * SCALE, 16.0 * SCALE, C_WHITE);
            }
            State::Prompt => {
                draw_text("BLASTAR", 70.0 * SCALE, 30.0 * SCALE, 24.0 * SCALE, C_YELLOW);
                draw_text("DO YOU NEED INSTRUCTIONS?", 20.0 * SCALE, 80.0 * SCALE, 12.0 * SCALE, C_WHITE);
                draw_text("(Y/N)", 100.0 * SCALE, 110.0 * SCALE, 16.0 * SCALE, C_LIME);
            }
            State::Instructions => {
                draw_text("USE ARROW KEYS TO MOVE",  30.0 * SCALE,  40.0 * SCALE, 12.0 * SCALE, C_WHITE);
                draw_text("SPACE TO FIRE",            70.0 * SCALE,  65.0 * SCALE, 12.0 * SCALE, C_WHITE);
                draw_text("MISSION: DESTROY ALIEN",   25.0 * SCALE, 100.0 * SCALE, 10.0 * SCALE, C_WHITE);
                draw_text("FREIGHTER CARRYING H2",    25.0 * SCALE, 115.0 * SCALE, 10.0 * SCALE, C_WHITE);
                draw_text("BOMBS AND STATUS BEAMS",   25.0 * SCALE, 130.0 * SCALE, 10.0 * SCALE, C_WHITE);
                draw_text("[PRESS SPACE]",            75.0 * SCALE, 160.0 * SCALE, 10.0 * SCALE, C_YELLOW);
            }
            State::Playing => {
                // line 580:  PRINT"   SCORE";SC;"           SHIPS";SH
                draw_text(&format!("SCORE {}", self.score),   4.0 * SCALE, 12.0 * SCALE, 10.0 * SCALE, C_WHITE);
                draw_text(&format!("SHIPS {}", self.ships), 190.0 * SCALE, 12.0 * SCALE, 10.0 * SCALE, C_WHITE);

                // Sprites scaled by 2 internally (16x16 on logical 256x192 grid)
                draw_sprite(self.px * SCALE, self.py * SCALE, &PLAYER_SPRITE,    C_YELLOW, 2.0 * SCALE);
                draw_sprite(self.ax * SCALE, self.ay * SCALE, &ALIEN_SPRITE,     C_LIME,   2.0 * SCALE);
                if self.rocket {
                    draw_sprite(self.rx * SCALE, self.ry * SCALE, &ROCKET_SPRITE, C_CYAN,  2.0 * SCALE);
                }
                if self.bomb {
                    draw_sprite(self.bx * SCALE, self.by * SCALE, &BOMB_SPRITE,   C_RED,   2.0 * SCALE);
                }
                if self.expl > 0.0 {
                    draw_sprite(self.ex * SCALE, self.ey * SCALE, &EXPLOSION_SPRITE, C_ORANGE, 2.0 * SCALE);
                }
            }
            State::GameOver => {
                draw_text("BLASTAR",          70.0 * SCALE,  30.0 * SCALE, 24.0 * SCALE, C_YELLOW);
                draw_text("FLEET DESTROYED",  35.0 * SCALE,  80.0 * SCALE, 14.0 * SCALE, C_RED);
                draw_text(&format!("SCORE: {}", self.score), 60.0 * SCALE, 110.0 * SCALE, 12.0 * SCALE, C_WHITE);
                draw_text("PLAY AGAIN? (Y/N)",60.0 * SCALE, 140.0 * SCALE, 10.0 * SCALE, C_YELLOW);
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Window Configuration (Fixed Resolution)
// ---------------------------------------------------------------------------
fn window_conf() -> Conf {
    Conf {
        window_title: "BLASTAR - by E.R. Musk".to_owned(),
        window_width: 768,   // 256 * 3
        window_height: 576,  // 192 * 3
        window_resizable: false,
        ..Default::default()
    }
}

// ---------------------------------------------------------------------------
// Entry point - macroquad's async main.
// ---------------------------------------------------------------------------
#[macroquad::main(window_conf)]
async fn main() {
    set_default_filter_mode(FilterMode::Nearest); // Crisp retro pixels

    let mut game = Game::new();
    loop {
        // Clamp dt so a stalled frame doesn't teleport sprites across the screen.
        let dt = get_frame_time().min(0.05);
        game.update(dt);
        
        // By using macroquad's default camera, (0,0) is natively top-left.
        // We simply multiply our drawing coordinates by SCALE (3.0) to fill the window.
        game.draw();
        
        next_frame().await;
    }
}