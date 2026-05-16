"""
Return Vector: Boomerang Flight Lab
app.py
Bright Ochre / Warpaint UI Theme Edition

A colorful aerospace-themed Pygame boomerang simulator/game.

Features:
- Mobile-friendly responsive window, compact HUD, and touch/on-screen controls
- Arcade and aerospace simulation modes
- Basic no-asset synthesized sound effects
- SI-unit aerodynamic model in Aerospace mode
- Lift and drag: L/D = 0.5 * rho * V^2 * S * C
- Forward/retreating blade velocity split
- Lift imbalance, torque, angular momentum, gyroscopic-style turn response
- Roll, pitch, yaw attitude state
- Altitude-dependent air density
- Wind shear, gusts, turbulence, thermal uplift
- Adjustable blade chord, arm length, camber, blade count
- Wind tunnel and research visualization modes
- Aerospace HUD, artificial horizon, live telemetry graphs
- Bright ochre/desert warpaint UI theme with dotted borders and sunburst accents

Install:
    pip install pygame numpy

Run:
    python app.py

Controls:
    SPACE        Throw / reset after flight
    R            Reset
    M            Cycle mode: Arcade / Aerospace / Wind Tunnel / Research
    LEFT/RIGHT   Adjust throw angle
    UP/DOWN      Adjust spin RPM
    W/S          Adjust throw speed
    A/D          Adjust bank / roll
    Q/E          Adjust blade camber
    Z/X          Adjust blade chord
    C/F          Adjust arm length
    1/2/3        Blade count: 2 / 3 / 4
    TAB          Toggle wind
    B            Toggle sound
    H            Toggle help

Mobile / tablet:
    Use on-screen buttons for launch, reset, mode, angle, RPM, speed, and bank.
    Small screens automatically use Compact HUD mode.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass

import numpy as np
import pygame


# =============================================================================
# CONSTANTS
# =============================================================================

WIDTH, HEIGHT = 1280, 760
MIN_WIDTH, MIN_HEIGHT = 900, 560
FPS = 60
PX_PER_M = 54.0

# Bright ochre/desert "warpaint" theme.
# Inspired by earth pigments, sun, desert sky, charcoal, and boomerang graphics.
# This uses generalized visual motifs only, not sacred or clan-specific patterns.
BG = (24, 12, 8)
PANEL = (54, 28, 18)
GRID = (92, 48, 28)
TEXT = (255, 244, 214)
MUTED = (226, 177, 111)
BLUE = (28, 170, 214)
ORANGE = (255, 98, 28)
GREEN = (57, 204, 121)
YELLOW = (255, 210, 67)
RED = (225, 48, 48)
PURPLE = (177, 86, 220)
CYAN = (44, 218, 230)

OCHRE = (198, 91, 28)
SAND = (255, 196, 110)
CLAY = (141, 54, 31)
CHARCOAL = (17, 13, 11)
BONE = (255, 238, 198)
SUN = (255, 184, 36)
TURQUOISE = (31, 188, 194)
WAR_RED = (219, 40, 38)
WHITE_PAINT = (255, 250, 232)

LAUNCH_PX = np.array([170.0, 560.0], dtype=float)
LAUNCH_M = np.array([0.0, 0.0], dtype=float)

RHO0 = 1.225
G = 9.80665
SCALE_HEIGHT_M = 8500.0
EPS = 1e-9

SIM_MODES = ["ARCADE", "AEROSPACE", "WIND TUNNEL", "RESEARCH"]


# =============================================================================
# SOUND
# =============================================================================

class SoundFX:
    """Simple generated Pygame tones, no external assets."""

    def __init__(self) -> None:
        self.enabled = True
        self.sounds = {}
        try:
            pygame.mixer.pre_init(44100, -16, 1, 512)
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self.sounds = {
                "launch": self._tone(660, 0.07, 0.35),
                "return": self._tone(880, 0.11, 0.35),
                "stall": self._tone(230, 0.13, 0.28),
                "impact": self._tone(95, 0.18, 0.42),
                "toggle": self._tone(520, 0.08, 0.28),
            }
        except Exception:
            self.enabled = False

    def _tone(self, freq_hz: float, duration_s: float, volume: float) -> pygame.mixer.Sound:
        sr = 44100
        n = int(sr * duration_s)
        t = np.linspace(0, duration_s, n, False)
        wave = np.sin(2.0 * np.pi * freq_hz * t)
        fade = max(1, int(sr * 0.006))
        env = np.ones(n)
        env[:fade] = np.linspace(0, 1, fade)
        env[-fade:] = np.linspace(1, 0, fade)
        audio = (wave * env * volume * 32767).astype(np.int16)
        return pygame.sndarray.make_sound(audio)

    def play(self, name: str) -> None:
        if not self.enabled:
            return
        snd = self.sounds.get(name)
        if snd:
            try:
                snd.play()
            except Exception:
                pass


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class Tuning:
    throw_angle_deg: float = 38.0
    throw_speed_mps: float = 18.0
    spin_rpm: float = 1450.0
    bank_deg: float = 24.0
    camber: float = 0.12
    chord_m: float = 0.045
    arm_length_m: float = 0.32
    blade_count: int = 2
    sim_mode: int = 1
    wind_on: bool = True
    sound_on: bool = True
    show_help: bool = True


@dataclass
class BoomerangGeometry:
    mass_kg: float = 0.095
    arm_length_m: float = 0.32
    chord_m: float = 0.045
    blade_count: int = 2
    cl_alpha: float = 4.8
    cd0: float = 0.045
    k_induced: float = 0.08

    @property
    def blade_area_m2(self) -> float:
        return self.arm_length_m * self.chord_m * self.blade_count

    @property
    def effective_radius_m(self) -> float:
        return 0.66 * self.arm_length_m

    @property
    def inertia_kgm2(self) -> float:
        # Thin-arm approximation: I_total ≈ mL²/3.
        return self.mass_kg * self.arm_length_m ** 2 / 3.0


@dataclass
class FlightState:
    pos_m: np.ndarray
    vel_mps: np.ndarray
    omega_rad_s: float
    bank_deg: float
    yaw_deg: float
    roll_deg: float = 24.0
    pitch_deg: float = 6.0
    p_rad_s: float = 0.0
    q_rad_s: float = 0.0
    r_rad_s: float = 0.0
    altitude_m: float = 1.1
    alive: bool = False
    time_s: float = 0.0
    max_range_m: float = 0.0
    closest_return_m: float = 9999.0
    score: int = 0
    phase_deg: float = 0.0
    energy_j: float = 0.0
    crashed: bool = False
    stall: bool = False


# =============================================================================
# MATH / ATMOSPHERE
# =============================================================================

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def rpm_to_rad_s(rpm: float) -> float:
    return rpm * 2.0 * math.pi / 60.0


def rad_s_to_rpm(rad_s: float) -> float:
    return rad_s * 60.0 / (2.0 * math.pi)


def unit_from_angle(deg: float) -> np.ndarray:
    rad = math.radians(deg)
    return np.array([math.cos(rad), -math.sin(rad)], dtype=float)


def rotate_vec(v: np.ndarray, deg: float) -> np.ndarray:
    rad = math.radians(deg)
    c, s = math.cos(rad), math.sin(rad)
    return np.array([c * v[0] - s * v[1], s * v[0] + c * v[1]], dtype=float)


def m_to_px(pos_m: np.ndarray, altitude_m: float = 0.0) -> np.ndarray:
    return LAUNCH_PX + np.array([pos_m[0] * PX_PER_M, -pos_m[1] * PX_PER_M - altitude_m * 8.0])


def air_density_at_altitude(altitude_m: float) -> float:
    return RHO0 * math.exp(-max(0.0, altitude_m) / SCALE_HEIGHT_M)


def wind_vector_mps(t: float, enabled: bool, altitude_m: float = 0.0) -> np.ndarray:
    if not enabled:
        return np.zeros(2)
    shear = 1.0 + 0.035 * clamp(altitude_m, 0.0, 30.0)
    base = np.array([1.4 + 0.7 * math.sin(t * 0.7), 0.4 * math.cos(t * 0.45)])
    gust = np.array([
        0.35 * math.sin(t * 4.1 + altitude_m * 0.7),
        0.24 * math.cos(t * 3.4 + altitude_m * 0.4),
    ])
    return base * shear + gust


def turbulence_vector_mps2(t: float, altitude_m: float, enabled: bool) -> np.ndarray:
    if not enabled:
        return np.zeros(2)
    amp = 0.12 + 0.012 * clamp(altitude_m, 0.0, 25.0)
    return np.array([
        amp * math.sin(9.0 * t + 1.7 * altitude_m),
        amp * math.cos(7.3 * t + 0.9 * altitude_m),
    ])


def thermal_uplift_mps2(pos_m: np.ndarray, t: float, enabled: bool) -> float:
    if not enabled:
        return 0.0
    columns = [
        (np.array([6.5, 3.5]), 2.2, 1.35),
        (np.array([13.0, 7.5]), 2.8, 0.95),
    ]
    uplift = 0.0
    for center, radius, strength in columns:
        d = float(np.linalg.norm(pos_m - center))
        uplift += strength * math.exp(-(d * d) / (2.0 * radius * radius))
    return uplift * (0.7 + 0.3 * math.sin(t * 0.8))


def aero_coefficients(alpha_rad: float, camber: float, geom: BoomerangGeometry) -> tuple[float, float]:
    alpha_eff = alpha_rad + camber
    cl = geom.cl_alpha * alpha_eff
    cl = clamp(cl, -1.15, 1.35)

    # Stall-like degradation above roughly 15 degrees effective AoA.
    if abs(alpha_eff) > math.radians(15):
        excess = abs(alpha_eff) - math.radians(15)
        cl *= max(0.45, 1.0 - 2.2 * excess)

    cd = geom.cd0 + geom.k_induced * cl * cl
    return cl, cd


def compute_score(state: FlightState) -> int:
    return_quality = max(0.0, 1.0 - state.closest_return_m / 2.4)
    range_quality = clamp(state.max_range_m / 11.0, 0.0, 1.0)
    spin_quality = clamp(rad_s_to_rpm(state.omega_rad_s) / 1400.0, 0.0, 1.0)
    altitude_quality = clamp(state.altitude_m / 4.0, 0.0, 1.0)
    crash_penalty = 0.55 if state.crashed else 1.0
    return int(1000 * crash_penalty * (
        0.48 * return_quality + 0.27 * range_quality +
        0.15 * spin_quality + 0.10 * altitude_quality
    ))


# =============================================================================
# PHYSICS
# =============================================================================

def step_arcade(state: FlightState, tuning: Tuning, geom: BoomerangGeometry, dt: float) -> dict:
    v_px = state.vel_mps * PX_PER_M
    wind = wind_vector_mps(state.time_s, tuning.wind_on, state.altitude_m)
    wind_px = wind * PX_PER_M
    air_v_px = v_px - wind_px
    airspeed_px = float(np.linalg.norm(air_v_px)) + EPS

    spin_norm = clamp(rad_s_to_rpm(state.omega_rad_s) / 1600.0, 0.0, 1.8)
    bank_norm = math.sin(math.radians(state.bank_deg))
    lift_strength = 0.00072 * airspeed_px ** 2 * (0.40 + spin_norm)
    imbalance = lift_strength * bank_norm * (0.65 + 0.35 * spin_norm)

    turn_dir = rotate_vec(air_v_px / airspeed_px, -90.0)
    turn_accel_px = turn_dir * imbalance
    glide_px = np.array([0.0, -0.11 * lift_strength])
    gravity_px = np.array([0.0, 52.0])
    drag_px = -0.00115 * airspeed_px * air_v_px

    accel_px = turn_accel_px + glide_px + gravity_px + drag_px
    state.vel_mps += (accel_px / PX_PER_M) * dt
    state.pos_m += state.vel_mps * dt + wind * dt * 0.45
    state.omega_rad_s *= 1.0 - 0.060 * dt
    state.time_s += dt
    state.phase_deg += math.degrees(state.omega_rad_s * dt)

    state.roll_deg = state.bank_deg
    state.pitch_deg = 5.0
    if float(np.linalg.norm(state.vel_mps)) > 0.1:
        state.yaw_deg = math.degrees(math.atan2(-state.vel_mps[1], state.vel_mps[0]))

    dist = float(np.linalg.norm(state.pos_m - LAUNCH_M))
    state.max_range_m = max(state.max_range_m, dist)
    if state.time_s > 1.0:
        state.closest_return_m = min(state.closest_return_m, dist)

    state.energy_j = 0.5 * geom.mass_kg * float(np.dot(state.vel_mps, state.vel_mps))
    state.score = compute_score(state)

    if (
        state.pos_m[0] < -3 or state.pos_m[0] > 23 or
        state.pos_m[1] < -5 or state.pos_m[1] > 14 or
        state.time_s > 18.0 or rad_s_to_rpm(state.omega_rad_s) < 120
    ):
        state.alive = False

    return {
        "mode": "ARCADE",
        "speed_mps": float(np.linalg.norm(state.vel_mps)),
        "airspeed_mps": float(np.linalg.norm(state.vel_mps - wind)),
        "lift_n": lift_strength / 20.0,
        "drag_n": float(np.linalg.norm(drag_px)) / 20.0,
        "imbalance_n": imbalance / 20.0,
        "torque_nm": 0.0,
        "precession_rad_s": 0.0,
        "v_forward": 0.0,
        "v_retreat": 0.0,
        "cl": 0.0,
        "cd": 0.0,
        "alpha_deg": 0.0,
        "rho": air_density_at_altitude(state.altitude_m),
        "thermal_mps2": thermal_uplift_mps2(state.pos_m, state.time_s, tuning.wind_on),
        "wind": wind,
    }


def step_aerospace(state: FlightState, tuning: Tuning, geom: BoomerangGeometry, dt: float) -> dict:
    geom.chord_m = tuning.chord_m
    geom.arm_length_m = tuning.arm_length_m
    geom.blade_count = tuning.blade_count

    rho = air_density_at_altitude(state.altitude_m)
    wind = wind_vector_mps(state.time_s, tuning.wind_on, state.altitude_m)
    air_v = state.vel_mps - wind
    airspeed = float(np.linalg.norm(air_v)) + EPS

    r = geom.effective_radius_m
    omega = max(state.omega_rad_s, 0.1)
    blade_tangential = r * omega

    # Core returning-boomerang idea: forward blade sees higher relative velocity.
    v_forward = max(0.1, airspeed + blade_tangential)
    v_retreat = max(0.1, abs(airspeed - blade_tangential))

    bank_rad = math.radians(state.roll_deg)
    pitch_rad = math.radians(state.pitch_deg)
    alpha_rad = pitch_rad + 0.18 * bank_rad

    cl, cd = aero_coefficients(alpha_rad, tuning.camber, geom)
    half_area = geom.blade_area_m2 / 2.0

    lift_forward = 0.5 * rho * v_forward ** 2 * half_area * cl
    lift_retreat = 0.5 * rho * v_retreat ** 2 * half_area * cl
    drag_forward = 0.5 * rho * v_forward ** 2 * half_area * cd
    drag_retreat = 0.5 * rho * v_retreat ** 2 * half_area * cd

    total_lift = max(0.0, lift_forward + lift_retreat)
    total_drag = drag_forward + drag_retreat
    lift_imbalance = lift_forward - lift_retreat

    forward_hat = air_v / airspeed
    drag_force = -forward_hat * total_drag
    lateral_hat = rotate_vec(forward_hat, -90.0 if state.roll_deg >= 0 else 90.0)
    lateral_force = lateral_hat * abs(total_lift * math.sin(bank_rad)) * 0.65

    vertical_lift = total_lift * max(0.0, math.cos(bank_rad))
    thermal = thermal_uplift_mps2(state.pos_m, state.time_s, tuning.wind_on)
    vertical_accel = (vertical_lift / geom.mass_kg) - G + thermal

    torque_nm = lift_imbalance * r * math.sin(abs(bank_rad) + 0.08)
    H = geom.inertia_kgm2 * omega
    precession_rad_s = clamp(torque_nm / max(H, 0.015), -2.5, 2.5)

    # 3-axis educational attitude approximation.
    roll_torque = -0.18 * math.sin(bank_rad) * total_lift
    pitch_torque = 0.08 * (vertical_lift - geom.mass_kg * G)

    ix = geom.inertia_kgm2 * 0.62
    iy = geom.inertia_kgm2 * 0.78

    state.p_rad_s += (roll_torque / max(ix, EPS)) * dt
    state.q_rad_s += (pitch_torque / max(iy, EPS)) * dt
    state.r_rad_s = precession_rad_s * (1.0 if state.roll_deg >= 0 else -1.0)

    state.p_rad_s *= 0.985
    state.q_rad_s *= 0.985

    state.roll_deg = clamp(state.roll_deg + math.degrees(state.p_rad_s * dt), -75.0, 75.0)
    state.pitch_deg = clamp(state.pitch_deg + math.degrees(state.q_rad_s * dt), -25.0, 28.0)
    state.yaw_deg += math.degrees(state.r_rad_s * dt)

    state.vel_mps = rotate_vec(state.vel_mps, math.degrees(state.r_rad_s * dt))
    accel_xy = (drag_force + lateral_force) / geom.mass_kg
    accel_xy += turbulence_vector_mps2(state.time_s, state.altitude_m, tuning.wind_on)
    state.vel_mps += accel_xy * dt

    state.altitude_m += vertical_accel * dt * 0.45
    if state.altitude_m > 0.5 and vertical_accel > 0:
        state.vel_mps *= max(0.992, 1.0 - 0.010 * dt * vertical_accel)

    if state.altitude_m <= 0.0:
        state.altitude_m = 0.0
        state.vel_mps *= 0.78
        state.omega_rad_s *= 0.82
        state.crashed = True
        if float(np.linalg.norm(state.vel_mps)) < 2.2:
            state.alive = False

    spin_drag_torque = 0.035 * total_drag * r
    state.omega_rad_s = max(0.1, state.omega_rad_s - (spin_drag_torque / max(geom.inertia_kgm2, EPS)) * dt)

    state.pos_m += state.vel_mps * dt + wind * dt * 0.16
    state.time_s += dt
    state.phase_deg += math.degrees(state.omega_rad_s * dt)

    dist = float(np.linalg.norm(state.pos_m - LAUNCH_M))
    state.max_range_m = max(state.max_range_m, dist)
    if state.time_s > 1.0:
        state.closest_return_m = min(state.closest_return_m, dist)

    state.energy_j = (
        0.5 * geom.mass_kg * float(np.dot(state.vel_mps, state.vel_mps)) +
        0.5 * geom.inertia_kgm2 * state.omega_rad_s ** 2
    )
    state.stall = cl < 0.20 or airspeed < 2.0
    state.score = compute_score(state)

    if (
        state.pos_m[0] < -3 or state.pos_m[0] > 23 or
        state.pos_m[1] < -5 or state.pos_m[1] > 14 or
        state.time_s > 22.0 or rad_s_to_rpm(state.omega_rad_s) < 90
    ):
        state.alive = False

    return {
        "mode": SIM_MODES[tuning.sim_mode],
        "speed_mps": float(np.linalg.norm(state.vel_mps)),
        "airspeed_mps": airspeed,
        "lift_n": total_lift,
        "drag_n": total_drag,
        "imbalance_n": lift_imbalance,
        "torque_nm": torque_nm,
        "precession_rad_s": precession_rad_s,
        "v_forward": v_forward,
        "v_retreat": v_retreat,
        "cl": cl,
        "cd": cd,
        "alpha_deg": math.degrees(alpha_rad + tuning.camber),
        "rho": rho,
        "thermal_mps2": thermal,
        "wind": wind,
    }


# =============================================================================
# DRAWING
# =============================================================================

def draw_dotted_line(surface, start, end, color, radius=3, spacing=14) -> None:
    sx, sy = start
    ex, ey = end
    dx, dy = ex - sx, ey - sy
    dist = max(1.0, math.hypot(dx, dy))
    steps = int(dist // spacing)
    for i in range(steps + 1):
        t = i / max(1, steps)
        x = int(sx + dx * t)
        y = int(sy + dy * t)
        pygame.draw.circle(surface, color, (x, y), radius)


def draw_paint_panel(surface, rect) -> None:
    pygame.draw.rect(surface, PANEL, rect, border_radius=16)
    pygame.draw.rect(surface, OCHRE, rect, 3, border_radius=16)

    # Dotted paint border.
    pad = 10
    draw_dotted_line(surface, (rect.left + pad, rect.top + pad), (rect.right - pad, rect.top + pad), SAND, 2, 16)
    draw_dotted_line(surface, (rect.left + pad, rect.bottom - pad), (rect.right - pad, rect.bottom - pad), SAND, 2, 16)
    draw_dotted_line(surface, (rect.left + pad, rect.top + pad), (rect.left + pad, rect.bottom - pad), WAR_RED, 2, 16)
    draw_dotted_line(surface, (rect.right - pad, rect.top + pad), (rect.right - pad, rect.bottom - pad), TURQUOISE, 2, 16)


def draw_sunburst(surface, center, radius) -> None:
    cx, cy = center
    for i in range(24):
        a = math.radians(i * 15)
        r1 = radius * 0.62
        r2 = radius
        p1 = (int(cx + math.cos(a) * r1), int(cy + math.sin(a) * r1))
        p2 = (int(cx + math.cos(a) * r2), int(cy + math.sin(a) * r2))
        pygame.draw.line(surface, SUN if i % 2 == 0 else WAR_RED, p1, p2, 3)
    pygame.draw.circle(surface, SUN, center, int(radius * 0.46))
    pygame.draw.circle(surface, WAR_RED, center, int(radius * 0.46), 3)
    pygame.draw.circle(surface, WHITE_PAINT, center, int(radius * 0.20), 2)


def draw_warpaint_background(surface, t: float = 0.0) -> None:
    # Broad diagonal paint bands.
    for i in range(-HEIGHT, WIDTH, 160):
        pygame.draw.line(surface, CLAY, (i, HEIGHT), (i + HEIGHT, 0), 18)
        pygame.draw.line(surface, OCHRE, (i + 42, HEIGHT), (i + HEIGHT + 42, 0), 7)
        pygame.draw.line(surface, TURQUOISE, (i + 82, HEIGHT), (i + HEIGHT + 82, 0), 4)

    # Dot constellations.
    for x in range(60, WIDTH, 95):
        for y in range(70, HEIGHT, 95):
            pulse = 1 + int(1.5 * (1 + math.sin(t * 2.0 + x * 0.01 + y * 0.02)))
            pygame.draw.circle(surface, SAND, (x, y), pulse)

    draw_sunburst(surface, (WIDTH - 96, HEIGHT - 92), 58)


def draw_boomerang_motif(surface, center, scale=1.0) -> None:
    cx, cy = center
    pts = [
        np.array([-50, 18]) * scale,
        np.array([-10, -8]) * scale,
        np.array([52, -14]) * scale,
        np.array([16, 12]) * scale,
        np.array([-34, 36]) * scale,
    ]
    pts = [(int(cx + p[0]), int(cy + p[1])) for p in pts]
    pygame.draw.polygon(surface, OCHRE, pts)
    pygame.draw.lines(surface, WHITE_PAINT, False, pts, 3)
    for p in pts[::2]:
        pygame.draw.circle(surface, SUN, p, max(2, int(4 * scale)))


def draw_text(surface, font, text, x, y, color=TEXT) -> None:
    surface.blit(font.render(text, True, color), (x, y))


def draw_grid(surface) -> None:
    for x in range(0, WIDTH, 40):
        pygame.draw.line(surface, GRID, (x, 0), (x, HEIGHT), 1)
    for y in range(0, HEIGHT, 40):
        pygame.draw.line(surface, GRID, (0, y), (WIDTH, y), 1)
    for r in [100, 200, 300, 400, 500]:
        pygame.draw.circle(surface, OCHRE if r % 200 == 0 else CLAY, LAUNCH_PX.astype(int), r, 1)
    draw_boomerang_motif(surface, (86, 84), 0.7)


def draw_panel(surface, rect) -> None:
    draw_paint_panel(surface, rect)


def draw_vector(surface, origin, vec, color, scale=1.0, label=None, font=None) -> None:
    end = origin + vec * scale
    pygame.draw.line(surface, color, origin.astype(int), end.astype(int), 3)
    pygame.draw.circle(surface, color, end.astype(int), 5)
    if label and font:
        draw_text(surface, font, label, int(end[0]) + 6, int(end[1]) - 8, color)


def draw_slider(surface, font, label, value, lo, hi, x, y, w, color, fmt="{:.0f}") -> None:
    pygame.draw.rect(surface, (21, 47, 75), (x, y + 22, w, 8), border_radius=6)
    t = clamp((value - lo) / (hi - lo), 0.0, 1.0)
    pygame.draw.rect(surface, color, (x, y + 22, int(w * t), 8), border_radius=6)
    pygame.draw.circle(surface, color, (x + int(w * t), y + 26), 9)
    draw_text(surface, font, f"{label}: {fmt.format(value)}", x, y, TEXT)


def draw_boomerang(surface, pos_px, angle_deg, spin_phase, roll_deg, blade_count) -> None:
    arm_len = 44
    center = pos_px.astype(int)
    colors = [WAR_RED, SUN, TURQUOISE, WHITE_PAINT]

    for i in range(blade_count):
        local = i * 360.0 / blade_count + 24.0
        p = rotate_vec(np.array([arm_len, 0.0]), angle_deg + local + spin_phase)
        pygame.draw.line(surface, colors[i % len(colors)], center, (pos_px + p).astype(int), 11)

    status_color = GREEN if abs(roll_deg) < 18 else SUN if abs(roll_deg) < 34 else WAR_RED
    pygame.draw.circle(surface, TEXT, center, 6)
    pygame.draw.circle(surface, status_color, center, 23, 2)
    pygame.draw.circle(surface, PURPLE, center, 33, 1)


def draw_environment(surface, mode) -> None:
    pygame.draw.circle(surface, WAR_RED, LAUNCH_PX.astype(int), 16)
    pygame.draw.circle(surface, SUN, LAUNCH_PX.astype(int), 34, 3)
    pygame.draw.circle(surface, WHITE_PAINT, LAUNCH_PX.astype(int), 48, 1)
    pygame.draw.line(surface, OCHRE, (80, 610), (270, 610), 8)
    draw_dotted_line(surface, (88, 624), (260, 624), WHITE_PAINT, 3, 18)

    gates = [((520, 360), 52), ((760, 220), 46), ((960, 420), 58)]
    for center, r in gates:
        pygame.draw.circle(surface, SUN, center, r, 4)
        pygame.draw.circle(surface, TURQUOISE, center, r + 7, 2)
        draw_dotted_line(surface, (center[0] - r, center[1]), (center[0] + r, center[1]), WHITE_PAINT, 2, 14)

    if mode == 2:
        for i in range(0, WIDTH, 55):
            pygame.draw.line(surface, (25, 90, 140), (i, 0), (i + 120, HEIGHT), 1)
    elif mode == 3:
        for i in range(0, WIDTH, 90):
            pygame.draw.line(surface, (70, 40, 110), (i, 0), (i, HEIGHT), 1)
        for j in range(0, HEIGHT, 90):
            pygame.draw.line(surface, (70, 40, 110), (0, j), (WIDTH, j), 1)


def draw_wind_tunnel(surface, state, tuning, telemetry) -> None:
    if not tuning.wind_on:
        return

    wind = telemetry.get("wind", np.zeros(2))
    spacing = 42 if tuning.sim_mode in (2, 3) else 55

    for y in range(80, HEIGHT - 80, spacing):
        phase = math.sin(state.time_s * 1.7 + y * 0.04) * 15
        start = np.array([430 + phase, y], dtype=float)
        vec = np.array([wind[0] * 30.0, -wind[1] * 30.0])
        draw_vector(surface, start, vec, CYAN, 1.0)

        if tuning.sim_mode in (2, 3):
            for i in range(3):
                swirl = np.array([
                    math.sin(state.time_s * 3.0 + y * 0.03 + i) * 12,
                    math.cos(state.time_s * 2.5 + y * 0.02 + i) * 8,
                ])
                p = start + swirl + np.array([i * 28, 0])
                pygame.draw.circle(surface, PURPLE, p.astype(int), 2)


def draw_attitude_indicator(surface, font, state) -> None:
    cx, cy = 118, HEIGHT - 110
    radius = 58
    pygame.draw.circle(surface, (18, 42, 68), (cx, cy), radius)
    pygame.draw.circle(surface, CYAN, (cx, cy), radius, 2)

    roll = math.radians(state.roll_deg)
    pitch_offset = clamp(state.pitch_deg, -25, 28) * 1.2
    length = 92
    dx = math.cos(roll) * length / 2
    dy = math.sin(roll) * length / 2
    pygame.draw.line(
        surface,
        ORANGE,
        (int(cx - dx), int(cy - dy + pitch_offset)),
        (int(cx + dx), int(cy + dy + pitch_offset)),
        4,
    )

    pygame.draw.line(surface, TEXT, (cx - 28, cy), (cx - 8, cy), 3)
    pygame.draw.line(surface, TEXT, (cx + 8, cy), (cx + 28, cy), 3)
    pygame.draw.circle(surface, TEXT, (cx, cy), 4)
    draw_text(surface, font, "ATT", cx - 20, cy + 70, CYAN)
    draw_text(surface, font, f"R {state.roll_deg: .0f}  P {state.pitch_deg: .0f}", cx - 55, cy + 91, TEXT)


def draw_science_graph(surface, values, rect, color, label, font, max_points=120) -> None:
    pygame.draw.rect(surface, (12, 26, 44), rect, border_radius=10)
    pygame.draw.rect(surface, GRID, rect, 1, border_radius=10)
    draw_text(surface, font, label, rect.x + 8, rect.y + 6, color)

    if len(values) < 2:
        return

    vals = values[-max_points:]
    vmin, vmax = min(vals), max(vals)
    span = max(1e-6, vmax - vmin)

    pts = []
    for i, v in enumerate(vals):
        x = rect.x + (i / max(1, len(vals) - 1)) * rect.w
        y = rect.y + rect.h - ((v - vmin) / span) * rect.h
        pts.append((x, y))

    pygame.draw.lines(surface, color, False, pts, 2)



def draw_compact_hud(surface, fonts, tuning, geom, state, telemetry, history, screen_w, screen_h) -> None:
    """Small-screen HUD: gameplay-first, no large side panels."""
    if compact:
        draw_compact_hud(surface, fonts, tuning, geom, state, telemetry, history, screen_w, screen_h)
        return

    title_font, font, small = fonts
    mode_name = SIM_MODES[tuning.sim_mode]

    # Top status strip.
    top = pygame.Rect(10, 8, screen_w - 20, 82)
    draw_panel(surface, top)
    draw_text(surface, font, "RETURN VECTOR", 28, 22, SUN)
    draw_text(surface, small, f"{mode_name} | {'FLIGHT' if state.alive else 'READY'} | Score {state.score:04d}", 28, 52, TEXT)

    # Compact left telemetry card.
    card = pygame.Rect(10, 98, min(360, screen_w - 20), 158)
    draw_panel(surface, card)
    rows = [
        f"Speed {telemetry.get('speed_mps', 0):.1f} m/s",
        f"Spin {rad_s_to_rpm(state.omega_rad_s):.0f} rpm",
        f"Roll/Pitch {state.roll_deg:.0f}/{state.pitch_deg:.0f}",
        f"Lift {telemetry.get('lift_n', 0):.2f} N",
        f"Torque {telemetry.get('torque_nm', 0):.3f} N*m",
        f"Return {state.closest_return_m:.1f} m",
    ]
    for i, row in enumerate(rows):
        draw_text(surface, small, row, 28, 122 + i * 20, TEXT)

    # Compact tuning card.
    tune_w = min(360, screen_w - 20)
    tune = pygame.Rect(10, 266, tune_w, 158)
    draw_panel(surface, tune)
    rows2 = [
        f"Angle {tuning.throw_angle_deg:.0f}°",
        f"Speed {tuning.throw_speed_mps:.1f} m/s",
        f"RPM {tuning.spin_rpm:.0f}",
        f"Bank {tuning.bank_deg:.0f}°",
        f"Camber {tuning.camber:.2f}",
        f"Blades {tuning.blade_count}",
    ]
    for i, row in enumerate(rows2):
        draw_text(surface, small, row, 28, 290 + i * 20, MUTED)

    # Tiny graph strip across middle/bottom above controls.
    graph_y = max(430, screen_h - 178)
    graph_w = max(120, (screen_w - 60) // 4)
    draw_science_graph(surface, history["energy"], pygame.Rect(10, graph_y, graph_w, 46), ORANGE, "E", small)
    draw_science_graph(surface, history["lift"], pygame.Rect(20 + graph_w, graph_y, graph_w, 46), CYAN, "L", small)
    draw_science_graph(surface, history["torque"], pygame.Rect(30 + graph_w * 2, graph_y, graph_w, 46), PURPLE, "T", small)
    draw_science_graph(surface, history["return"], pygame.Rect(40 + graph_w * 3, graph_y, graph_w, 46), GREEN, "R", small)

    # Minimal flags.
    flag = "NOMINAL"
    color = GREEN
    if state.crashed:
        flag, color = "IMPACT", RED
    elif state.stall:
        flag, color = "STALL", YELLOW
    elif tuning.wind_on:
        flag, color = "WIND", CYAN
    draw_text(surface, small, flag, screen_w - 100, 52, color)

def draw_hud(surface, fonts, tuning, geom, state, telemetry, history, screen_w=WIDTH, screen_h=HEIGHT, compact=False) -> None:
    if compact:
        draw_compact_hud(surface, fonts, tuning, geom, state, telemetry, history, screen_w, screen_h)
        return

    title_font, font, small = fonts
    mode_name = SIM_MODES[tuning.sim_mode]

    draw_panel(surface, pygame.Rect(22, 18, 590, 124))
    draw_text(surface, title_font, "RETURN VECTOR: BOOMERANG FLIGHT LAB", 42, 34, SUN)
    draw_boomerang_motif(surface, (548, 58), 0.55)
    draw_text(surface, font, f"MODE: {mode_name} | aerospace physics + colorful game feedback", 42, 76, GREEN)
    draw_text(surface, font, f"STATUS: {'IN FLIGHT' if state.alive else 'READY / TUNE LAUNCH'}", 42, 108, GREEN if state.alive else YELLOW)

    draw_panel(surface, pygame.Rect(22, 158, 392, 400))
    draw_text(surface, font, "LAUNCH + GEOMETRY", 42, 176, CYAN)
    draw_slider(surface, small, "Throw Angle", tuning.throw_angle_deg, 5, 75, 42, 214, 310, ORANGE)
    draw_slider(surface, small, "Throw Speed m/s", tuning.throw_speed_mps, 8, 30, 42, 264, 310, BLUE)
    draw_slider(surface, small, "Spin RPM", tuning.spin_rpm, 300, 2600, 42, 314, 310, GREEN)
    draw_slider(surface, small, "Bank / Roll", tuning.bank_deg, -45, 45, 42, 364, 310, PURPLE)
    draw_slider(surface, small, "Blade Camber", tuning.camber, 0.02, 0.22, 42, 414, 310, YELLOW, "{:.2f}")
    draw_slider(surface, small, "Chord m", tuning.chord_m, 0.025, 0.080, 42, 464, 310, CYAN, "{:.3f}")
    draw_slider(surface, small, "Arm Length m", tuning.arm_length_m, 0.18, 0.55, 42, 514, 310, GREEN, "{:.2f}")

    draw_panel(surface, pygame.Rect(WIDTH - 430, 18, 400, 516))
    draw_text(surface, font, "AEROSPACE TELEMETRY", WIDTH - 410, 38, CYAN)
    lines = [
        f"Time:             {state.time_s:7.2f} s",
        f"Speed:            {telemetry.get('speed_mps', 0):7.2f} m/s",
        f"Airspeed:         {telemetry.get('airspeed_mps', 0):7.2f} m/s",
        f"Spin:             {rad_s_to_rpm(state.omega_rad_s):7.0f} rpm",
        f"Altitude:         {state.altitude_m:7.2f} m",
        f"Rho:              {telemetry.get('rho', RHO0):7.4f} kg/m3",
        f"Roll/Pitch/Yaw:   {state.roll_deg:5.1f}/{state.pitch_deg:5.1f}/{state.yaw_deg:5.1f}",
        f"p/q/r rates:      {state.p_rad_s:5.2f}/{state.q_rad_s:5.2f}/{state.r_rad_s:5.2f}",
        f"Thermal uplift:   {telemetry.get('thermal_mps2', 0):7.3f} m/s2",
        f"Lift:             {telemetry.get('lift_n', 0):7.3f} N",
        f"Drag:             {telemetry.get('drag_n', 0):7.3f} N",
        f"Lift imbalance:   {telemetry.get('imbalance_n', 0):7.3f} N",
        f"Torque:           {telemetry.get('torque_nm', 0):7.4f} N*m",
        f"Precession:       {telemetry.get('precession_rad_s', 0):7.3f} rad/s",
        f"V fwd/retreat:    {telemetry.get('v_forward', 0):5.1f}/{telemetry.get('v_retreat', 0):5.1f} m/s",
        f"CL/CD:            {telemetry.get('cl', 0):5.2f} / {telemetry.get('cd', 0):5.2f}",
        f"Energy:           {state.energy_j:7.2f} J",
        f"Blades:           {geom.blade_count:7d}",
        f"Closest return:   {state.closest_return_m:7.2f} m",
        f"Score:            {state.score:04d}",
    ]
    for i, line in enumerate(lines):
        color = GREEN if "Score" in line else TEXT
        if "Torque" in line or "Precession" in line:
            color = YELLOW
        draw_text(surface, small, line, WIDTH - 410, 76 + i * 20, color)

    draw_panel(surface, pygame.Rect(WIDTH - 430, 548, 400, 76))
    flags = []
    if tuning.wind_on:
        flags.append("WIND")
    if state.stall:
        flags.append("STALL/LOW LIFT")
    if state.crashed:
        flags.append("GROUND IMPACT")
    if not flags:
        flags.append("NOMINAL")
    draw_text(surface, font, "MODEL FLAGS", WIDTH - 410, 566, ORANGE)
    draw_text(surface, small, " | ".join(flags), WIDTH - 410, 596, RED if state.crashed or state.stall else GREEN)
    draw_text(surface, small, f"Sound: {'ON' if tuning.sound_on else 'OFF'}", WIDTH - 250, 596, MUTED)

    graph_y = HEIGHT - 92
    draw_science_graph(surface, history["energy"], pygame.Rect(220, graph_y, 180, 68), ORANGE, "ENERGY", small)
    draw_science_graph(surface, history["lift"], pygame.Rect(410, graph_y, 180, 68), CYAN, "LIFT", small)
    draw_science_graph(surface, history["torque"], pygame.Rect(600, graph_y, 180, 68), PURPLE, "TORQUE", small)
    draw_science_graph(surface, history["return"], pygame.Rect(790, graph_y, 180, 68), GREEN, "RETURN", small)

    if tuning.show_help:
        draw_panel(surface, pygame.Rect(430, 158, 410, 150))
        draw_text(surface, font, "CONTROLS", 450, 178, ORANGE)
        controls = [
            "SPACE throw/reset | R reset | M mode",
            "←/→ angle | ↑/↓ spin | W/S speed",
            "A/D bank | Q/E camber | Z/X chord",
            "C/F arm length | 1/2/3 blade count",
            "TAB wind | B sound | H help",
        ]
        for i, line in enumerate(controls):
            draw_text(surface, small, line, 450, 210 + i * 22, TEXT)



def build_touch_buttons(width: int, height: int) -> dict:
    """Responsive touch controls for tablets/mobile-sized displays."""
    compact = width < 1120 or height < 700
    size = max(54, min(78, width // 16))
    pad = max(8, width // 100)
    bottom = height - size - pad

    if compact:
        # Mobile landscape: left cluster tunes, right cluster launches.
        return {
            "angle_left": pygame.Rect(pad, bottom - size - pad, size, size),
            "angle_right": pygame.Rect(pad + size + pad, bottom - size - pad, size, size),
            "spin_up": pygame.Rect(pad + size // 2, bottom - size * 2 - pad * 2, size, size),
            "spin_down": pygame.Rect(pad + size // 2, bottom, size, size),

            "speed_up": pygame.Rect(pad + size * 2 + pad * 3, bottom - size * 2 - pad * 2, size, size),
            "speed_down": pygame.Rect(pad + size * 2 + pad * 3, bottom, size, size),
            "bank_left": pygame.Rect(pad + size * 3 + pad * 4, bottom - size - pad, size, size),
            "bank_right": pygame.Rect(pad + size * 4 + pad * 5, bottom - size - pad, size, size),

            "mode": pygame.Rect(width - size * 4 - pad * 4, bottom, size, size),
            "reset": pygame.Rect(width - size * 3 - pad * 3, bottom, size, size),
            "launch": pygame.Rect(width - size * 2 - pad * 2, bottom, size * 2, size),
        }

    return {
        "launch": pygame.Rect(width - size * 2 - pad * 2, bottom, size * 2, size),
        "reset": pygame.Rect(width - size * 3 - pad * 3, bottom, size, size),
        "mode": pygame.Rect(width - size * 4 - pad * 4, bottom, size, size),

        "angle_left": pygame.Rect(pad, bottom - size - pad, size, size),
        "angle_right": pygame.Rect(pad + size + pad, bottom - size - pad, size, size),
        "spin_up": pygame.Rect(pad + size // 2, bottom - size * 2 - pad * 2, size, size),
        "spin_down": pygame.Rect(pad + size // 2, bottom, size, size),

        "speed_up": pygame.Rect(pad + size * 3 + pad * 3, bottom - size * 2 - pad * 2, size, size),
        "speed_down": pygame.Rect(pad + size * 3 + pad * 3, bottom, size, size),
        "bank_left": pygame.Rect(pad + size * 4 + pad * 4, bottom - size - pad, size, size),
        "bank_right": pygame.Rect(pad + size * 5 + pad * 5, bottom - size - pad, size, size),
    }

def draw_touch_buttons(surface, font, buttons: dict, show: bool) -> None:
    if not show:
        return

    labels = {
        "launch": "THROW",
        "reset": "R",
        "mode": "M",
        "angle_left": "ANG+",
        "angle_right": "ANG-",
        "spin_up": "RPM+",
        "spin_down": "RPM-",
        "speed_up": "SPD+",
        "speed_down": "SPD-",
        "bank_left": "BANK-",
        "bank_right": "BANK+",
    }

    for name, rect in buttons.items():
        pygame.draw.rect(surface, (65, 32, 20), rect, border_radius=14)
        pygame.draw.rect(surface, SUN if name == "launch" else TURQUOISE, rect, 3, border_radius=14)
        text = labels.get(name, name)
        rendered = font.render(text, True, TEXT)
        surface.blit(rendered, rendered.get_rect(center=rect.center))


def apply_touch_action(name: str, tuning: Tuning, state: FlightState, dt: float) -> None:
    """Continuous tuning changes while touch/mouse button is held."""
    if state.alive and name not in ("launch", "reset", "mode"):
        return

    if name == "angle_left":
        tuning.throw_angle_deg = clamp(tuning.throw_angle_deg + 75 * dt, 5, 75)
    elif name == "angle_right":
        tuning.throw_angle_deg = clamp(tuning.throw_angle_deg - 75 * dt, 5, 75)
    elif name == "spin_up":
        tuning.spin_rpm = clamp(tuning.spin_rpm + 1200 * dt, 300, 2600)
    elif name == "spin_down":
        tuning.spin_rpm = clamp(tuning.spin_rpm - 1200 * dt, 300, 2600)
    elif name == "speed_up":
        tuning.throw_speed_mps = clamp(tuning.throw_speed_mps + 16 * dt, 8, 30)
    elif name == "speed_down":
        tuning.throw_speed_mps = clamp(tuning.throw_speed_mps - 16 * dt, 8, 30)
    elif name == "bank_left":
        tuning.bank_deg = clamp(tuning.bank_deg - 60 * dt, -45, 45)
    elif name == "bank_right":
        tuning.bank_deg = clamp(tuning.bank_deg + 60 * dt, -45, 45)


# =============================================================================
# MAIN LOOP
# =============================================================================

def new_state(tuning: Tuning) -> FlightState:
    return FlightState(
        pos_m=LAUNCH_M.copy(),
        vel_mps=unit_from_angle(tuning.throw_angle_deg) * tuning.throw_speed_mps,
        omega_rad_s=rpm_to_rad_s(tuning.spin_rpm),
        bank_deg=tuning.bank_deg,
        yaw_deg=tuning.throw_angle_deg,
        roll_deg=tuning.bank_deg,
        pitch_deg=6.0,
        altitude_m=1.1,
        alive=True,
    )


def idle_state(tuning: Tuning) -> FlightState:
    return FlightState(
        pos_m=LAUNCH_M.copy(),
        vel_mps=np.zeros(2),
        omega_rad_s=rpm_to_rad_s(tuning.spin_rpm),
        bank_deg=tuning.bank_deg,
        yaw_deg=tuning.throw_angle_deg,
        roll_deg=tuning.bank_deg,
        pitch_deg=6.0,
        altitude_m=1.1,
        alive=False,
    )


def main() -> None:
    pygame.init()
    soundfx = SoundFX()

    pygame.display.set_caption("Return Vector: Boomerang Flight Lab")
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
    screen_w, screen_h = WIDTH, HEIGHT
    clock = pygame.time.Clock()

    title_font = pygame.font.SysFont("arial", 26, bold=True)
    font = pygame.font.SysFont("arial", 20, bold=True)
    small = pygame.font.SysFont("consolas", 15)

    tuning = Tuning()
    geom = BoomerangGeometry()
    state = idle_state(tuning)
    trail: list[tuple[int, int]] = []
    history = {"energy": [], "lift": [], "torque": [], "return": []}

    telemetry = {
        "speed_mps": tuning.throw_speed_mps,
        "airspeed_mps": tuning.throw_speed_mps,
        "lift_n": 0.0,
        "drag_n": 0.0,
        "imbalance_n": 0.0,
        "torque_nm": 0.0,
        "precession_rad_s": 0.0,
        "v_forward": 0.0,
        "v_retreat": 0.0,
        "cl": 0.0,
        "cd": 0.0,
        "rho": RHO0,
        "thermal_mps2": 0.0,
        "wind": np.zeros(2),
    }

    prev_stall = False
    prev_crashed = False
    return_sound_played = False
    active_touch: str | None = None

    running = True
    while running:
        dt = min(clock.tick(FPS) / 1000.0, 0.033)

        touch_buttons = build_touch_buttons(screen_w, screen_h)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.VIDEORESIZE:
                screen_w = max(MIN_WIDTH, event.w)
                screen_h = max(MIN_HEIGHT, event.h)
                screen = pygame.display.set_mode((screen_w, screen_h), pygame.RESIZABLE)

            if event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                for name, rect in touch_buttons.items():
                    if rect.collidepoint(mx, my):
                        active_touch = name
                        if name == "launch":
                            state = new_state(tuning)
                            trail.clear()
                            history = {"energy": [], "lift": [], "torque": [], "return": []}
                            return_sound_played = False
                            if tuning.sound_on:
                                soundfx.play("launch")
                        elif name == "reset":
                            state = idle_state(tuning)
                            trail.clear()
                            history = {"energy": [], "lift": [], "torque": [], "return": []}
                            return_sound_played = False
                            if tuning.sound_on:
                                soundfx.play("toggle")
                        elif name == "mode":
                            tuning.sim_mode = (tuning.sim_mode + 1) % len(SIM_MODES)
                            state = idle_state(tuning)
                            trail.clear()
                            history = {"energy": [], "lift": [], "torque": [], "return": []}
                            return_sound_played = False
                            if tuning.sound_on:
                                soundfx.play("toggle")
                        break

            if event.type == pygame.MOUSEBUTTONUP:
                active_touch = None

            if event.type == pygame.FINGERDOWN:
                mx, my = int(event.x * screen_w), int(event.y * screen_h)
                for name, rect in touch_buttons.items():
                    if rect.collidepoint(mx, my):
                        active_touch = name
                        break

            if event.type == pygame.FINGERUP:
                active_touch = None

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    state = new_state(tuning)
                    trail.clear()
                    history = {"energy": [], "lift": [], "torque": [], "return": []}
                    return_sound_played = False
                    if tuning.sound_on:
                        soundfx.play("launch")
                elif event.key == pygame.K_r:
                    state = idle_state(tuning)
                    trail.clear()
                    history = {"energy": [], "lift": [], "torque": [], "return": []}
                    return_sound_played = False
                    if tuning.sound_on:
                        soundfx.play("toggle")
                elif event.key == pygame.K_m:
                    tuning.sim_mode = (tuning.sim_mode + 1) % len(SIM_MODES)
                    state = idle_state(tuning)
                    trail.clear()
                    history = {"energy": [], "lift": [], "torque": [], "return": []}
                    return_sound_played = False
                    if tuning.sound_on:
                        soundfx.play("toggle")
                elif event.key == pygame.K_TAB:
                    tuning.wind_on = not tuning.wind_on
                    if tuning.sound_on:
                        soundfx.play("toggle")
                elif event.key == pygame.K_b:
                    tuning.sound_on = not tuning.sound_on
                    soundfx.enabled = tuning.sound_on
                    if tuning.sound_on:
                        soundfx.play("toggle")
                elif event.key == pygame.K_h:
                    tuning.show_help = not tuning.show_help
                elif event.key == pygame.K_1:
                    tuning.blade_count = 2
                elif event.key == pygame.K_2:
                    tuning.blade_count = 3
                elif event.key == pygame.K_3:
                    tuning.blade_count = 4

        keys = pygame.key.get_pressed()
        if not state.alive:
            if keys[pygame.K_LEFT]:
                tuning.throw_angle_deg = clamp(tuning.throw_angle_deg + 50 * dt, 5, 75)
            if keys[pygame.K_RIGHT]:
                tuning.throw_angle_deg = clamp(tuning.throw_angle_deg - 50 * dt, 5, 75)
            if keys[pygame.K_UP]:
                tuning.spin_rpm = clamp(tuning.spin_rpm + 900 * dt, 300, 2600)
            if keys[pygame.K_DOWN]:
                tuning.spin_rpm = clamp(tuning.spin_rpm - 900 * dt, 300, 2600)
            if keys[pygame.K_w]:
                tuning.throw_speed_mps = clamp(tuning.throw_speed_mps + 12 * dt, 8, 30)
            if keys[pygame.K_s]:
                tuning.throw_speed_mps = clamp(tuning.throw_speed_mps - 12 * dt, 8, 30)
            if keys[pygame.K_a]:
                tuning.bank_deg = clamp(tuning.bank_deg - 45 * dt, -45, 45)
            if keys[pygame.K_d]:
                tuning.bank_deg = clamp(tuning.bank_deg + 45 * dt, -45, 45)
            if keys[pygame.K_q]:
                tuning.camber = clamp(tuning.camber + 0.08 * dt, 0.02, 0.22)
            if keys[pygame.K_e]:
                tuning.camber = clamp(tuning.camber - 0.08 * dt, 0.02, 0.22)
            if keys[pygame.K_z]:
                tuning.chord_m = clamp(tuning.chord_m - 0.025 * dt, 0.025, 0.080)
            if keys[pygame.K_x]:
                tuning.chord_m = clamp(tuning.chord_m + 0.025 * dt, 0.025, 0.080)
            if keys[pygame.K_c]:
                tuning.arm_length_m = clamp(tuning.arm_length_m - 0.16 * dt, 0.18, 0.55)
            if keys[pygame.K_f]:
                tuning.arm_length_m = clamp(tuning.arm_length_m + 0.16 * dt, 0.18, 0.55)

            state = idle_state(tuning)
            prev_stall = False
            prev_crashed = False

        if active_touch:
            apply_touch_action(active_touch, tuning, state, dt)
            if not state.alive and active_touch not in ("launch", "reset", "mode"):
                state = idle_state(tuning)

        geom.chord_m = tuning.chord_m
        geom.arm_length_m = tuning.arm_length_m
        geom.blade_count = tuning.blade_count

        if state.alive:
            if tuning.sim_mode == 0:
                telemetry = step_arcade(state, tuning, geom, dt)
            else:
                telemetry = step_aerospace(state, tuning, geom, dt)

            if tuning.sound_on:
                if state.stall and not prev_stall:
                    soundfx.play("stall")
                if state.crashed and not prev_crashed:
                    soundfx.play("impact")
                if state.time_s > 1.6 and state.closest_return_m < 1.6 and not return_sound_played:
                    soundfx.play("return")
                    return_sound_played = True

            prev_stall = state.stall
            prev_crashed = state.crashed

            history["energy"].append(state.energy_j)
            history["lift"].append(telemetry.get("lift_n", 0.0))
            history["torque"].append(telemetry.get("torque_nm", 0.0))
            history["return"].append(min(state.closest_return_m, 30.0))
            for key in history:
                history[key] = history[key][-240:]

            trail.append(tuple(m_to_px(state.pos_m, state.altitude_m).astype(int)))
            if len(trail) > 720:
                trail.pop(0)

        compact_mobile = screen_w < 1120 or screen_h < 700
        if compact_mobile:
            tuning.show_help = False

        screen.fill(BG)
        draw_warpaint_background(screen, state.time_s)
        draw_grid(screen)
        draw_environment(screen, tuning.sim_mode)
        draw_wind_tunnel(screen, state, tuning, telemetry)

        if len(trail) > 1:
            for i in range(1, len(trail)):
                age = i / len(trail)
                color = (
                    int(ORANGE[0] * age + BLUE[0] * (1 - age)),
                    int(ORANGE[1] * age + BLUE[1] * (1 - age)),
                    int(ORANGE[2] * age + BLUE[2] * (1 - age)),
                )
                pygame.draw.line(screen, color, trail[i - 1], trail[i], 3)

        pos_px = m_to_px(state.pos_m, state.altitude_m)

        if not state.alive:
            launch_vec = unit_from_angle(tuning.throw_angle_deg) * tuning.throw_speed_mps * 5.5
            draw_vector(screen, LAUNCH_PX, launch_vec, ORANGE, 1.0, "throw vector", small)

        if state.alive:
            draw_vector(screen, pos_px, state.vel_mps * np.array([1, -1]) * 9.0, GREEN, 1.0, "velocity", small)
            wind = telemetry.get("wind", np.zeros(2))
            draw_vector(screen, pos_px + np.array([0, 28]), wind * np.array([1, -1]) * 34.0, CYAN, 1.0, "wind", small)
            lift_mag = telemetry.get("lift_n", 0.0)
            torque_mag = telemetry.get("torque_nm", 0.0)
            draw_vector(screen, pos_px + np.array([0, -20]), np.array([0, -lift_mag * 18.0]), YELLOW, 1.0, "lift", small)
            draw_vector(screen, pos_px + np.array([0, 44]), np.array([torque_mag * 700.0, 0]), PURPLE, 1.0, "torque", small)

        draw_boomerang(screen, pos_px, state.yaw_deg, state.phase_deg, state.roll_deg, tuning.blade_count)
        if not compact_mobile or screen_h > 620:
            draw_attitude_indicator(screen, small, state)
        draw_hud(screen, (title_font, font, small), tuning, geom, state, telemetry, history, screen_w, screen_h, compact_mobile)

        draw_touch_buttons(screen, small, build_touch_buttons(screen_w, screen_h), True)
        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
