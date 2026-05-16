"""
Return Vector: Boomerang Flight Lab
Streamlit Cloud compatible version.

Run:
    streamlit run app.py
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


st.set_page_config(page_title="Return Vector: Boomerang Flight Lab", page_icon="🪃", layout="wide")

OCHRE = "#C65B1C"
SAND = "#FFC46E"
CLAY = "#8D361F"
CHARCOAL = "#110D0B"
BONE = "#FFEEE6"
SUN = "#FFB824"
TURQUOISE = "#1FBCC2"
WAR_RED = "#DB2826"
GREEN = "#39CC79"

RHO0 = 1.225
G = 9.80665
SCALE_HEIGHT_M = 8500.0

st.markdown(
    f"""
<style>
.stApp {{
    background:
        radial-gradient(circle at 82% 8%, rgba(255,184,36,0.22), transparent 25%),
        linear-gradient(135deg, #160B07 0%, #2B120B 45%, #0F0A08 100%);
    color: {BONE};
}}
.block-container {{ padding-top: 1.4rem; }}
.hero {{
    border: 2px solid {OCHRE};
    border-radius: 22px;
    padding: 1.3rem 1.5rem;
    background:
        linear-gradient(135deg, rgba(198,91,28,0.28), rgba(17,13,11,0.88)),
        repeating-linear-gradient(45deg, rgba(255,196,110,0.10) 0 8px, transparent 8px 22px);
    box-shadow: 0 0 32px rgba(255,98,28,0.18);
}}
.hero h1 {{ color: {SUN}; font-size: 2.5rem; margin-bottom: 0.25rem; }}
.hero p {{ color: {BONE}; font-size: 1.05rem; }}
.warning-box {{
    border-left: 5px solid {WAR_RED};
    background: rgba(219,40,38,0.12);
    padding: 0.9rem 1rem;
    border-radius: 12px;
    color: {BONE};
}}
.good-box {{
    border-left: 5px solid {GREEN};
    background: rgba(57,204,121,0.10);
    padding: 0.9rem 1rem;
    border-radius: 12px;
    color: {BONE};
}}
.small-note {{ color: rgba(255,238,230,0.72); font-size: 0.88rem; }}
div[data-testid="stMetricValue"] {{ color: {SUN}; }}
hr {{ border-color: rgba(255,196,110,0.25); }}
</style>
""",
    unsafe_allow_html=True,
)


@dataclass
class SimConfig:
    mode: str
    throw_angle_deg: float
    throw_speed_mps: float
    spin_rpm: float
    bank_deg: float
    camber: float
    chord_m: float
    arm_length_m: float
    blade_count: int
    wind_on: bool
    duration_s: float
    dt: float = 0.035
    mass_kg: float = 0.095
    cl_alpha: float = 4.8
    cd0: float = 0.045
    k_induced: float = 0.08


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def rpm_to_rad_s(rpm: float) -> float:
    return rpm * 2.0 * math.pi / 60.0


def rad_s_to_rpm(rad_s: float) -> float:
    return rad_s * 60.0 / (2.0 * math.pi)


def unit_from_angle(deg: float) -> np.ndarray:
    rad = math.radians(deg)
    return np.array([math.cos(rad), math.sin(rad)], dtype=float)


def rotate_vec(v: np.ndarray, deg: float) -> np.ndarray:
    rad = math.radians(deg)
    c, s = math.cos(rad), math.sin(rad)
    return np.array([c * v[0] - s * v[1], s * v[0] + c * v[1]], dtype=float)


def air_density_at_altitude(altitude_m: float) -> float:
    return RHO0 * math.exp(-max(0.0, altitude_m) / SCALE_HEIGHT_M)


def wind_vector_mps(t: float, enabled: bool, altitude_m: float) -> np.ndarray:
    if not enabled:
        return np.zeros(2)
    shear = 1.0 + 0.035 * clamp(altitude_m, 0.0, 30.0)
    base = np.array([1.4 + 0.7 * math.sin(t * 0.7), 0.4 * math.cos(t * 0.45)])
    gust = np.array([
        0.35 * math.sin(t * 4.1 + altitude_m * 0.7),
        0.24 * math.cos(t * 3.4 + altitude_m * 0.4),
    ])
    return base * shear + gust


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


def turbulence_vector_mps2(t: float, altitude_m: float, enabled: bool) -> np.ndarray:
    if not enabled:
        return np.zeros(2)
    amp = 0.12 + 0.012 * clamp(altitude_m, 0.0, 25.0)
    return np.array([
        amp * math.sin(9.0 * t + 1.7 * altitude_m),
        amp * math.cos(7.3 * t + 0.9 * altitude_m),
    ])


def aero_coefficients(alpha_rad: float, camber: float, cfg: SimConfig) -> tuple[float, float]:
    alpha_eff = alpha_rad + camber
    cl = clamp(cfg.cl_alpha * alpha_eff, -1.15, 1.35)
    if abs(alpha_eff) > math.radians(15):
        excess = abs(alpha_eff) - math.radians(15)
        cl *= max(0.45, 1.0 - 2.2 * excess)
    cd = cfg.cd0 + cfg.k_induced * cl * cl
    return cl, cd


def simulate(cfg: SimConfig) -> pd.DataFrame:
    pos = np.array([0.0, 0.0], dtype=float)
    vel = unit_from_angle(cfg.throw_angle_deg) * cfg.throw_speed_mps
    omega = rpm_to_rad_s(cfg.spin_rpm)

    roll_deg = cfg.bank_deg
    pitch_deg = 6.0
    yaw_deg = cfg.throw_angle_deg
    p_rad_s = q_rad_s = r_rad_s = 0.0
    altitude = 1.1
    crashed = False
    closest_return = 9999.0
    max_range = 0.0

    blade_area = cfg.arm_length_m * cfg.chord_m * cfg.blade_count
    effective_radius = 0.66 * cfg.arm_length_m
    inertia = cfg.mass_kg * cfg.arm_length_m ** 2 / 3.0

    rows = []
    t = 0.0
    while t <= cfg.duration_s:
        rho = air_density_at_altitude(altitude)
        wind = wind_vector_mps(t, cfg.wind_on, altitude)
        air_v = vel - wind
        airspeed = float(np.linalg.norm(air_v)) + 1e-9

        r = effective_radius
        v_forward = max(0.1, airspeed + r * max(omega, 0.1))
        v_retreat = max(0.1, abs(airspeed - r * max(omega, 0.1)))

        if cfg.mode == "Arcade":
            spin_norm = clamp(rad_s_to_rpm(omega) / 1600.0, 0.0, 1.8)
            bank_norm = math.sin(math.radians(roll_deg))
            lift_n = 0.018 * airspeed ** 2 * (0.40 + spin_norm)
            drag_n = 0.028 * airspeed ** 2
            imbalance_n = lift_n * bank_norm * (0.65 + 0.35 * spin_norm)
            torque_nm = 0.0
            precession = 0.12 * bank_norm * spin_norm
            cl, cd = 0.0, 0.0
            thermal = thermal_uplift_mps2(pos, t, cfg.wind_on)

            vel = rotate_vec(vel, math.degrees(precession * cfg.dt))
            vel += (-air_v / airspeed) * (drag_n / cfg.mass_kg) * cfg.dt * 0.10
            vel += rotate_vec(air_v / airspeed, 90.0) * (imbalance_n / cfg.mass_kg) * cfg.dt * 0.22
            altitude += ((lift_n / cfg.mass_kg) - G + thermal) * cfg.dt * 0.05
            omega *= 1.0 - 0.060 * cfg.dt
        else:
            bank_rad = math.radians(roll_deg)
            pitch_rad = math.radians(pitch_deg)
            alpha_rad = pitch_rad + 0.18 * bank_rad
            cl, cd = aero_coefficients(alpha_rad, cfg.camber, cfg)
            half_area = blade_area / 2.0

            lift_forward = 0.5 * rho * v_forward ** 2 * half_area * cl
            lift_retreat = 0.5 * rho * v_retreat ** 2 * half_area * cl
            drag_forward = 0.5 * rho * v_forward ** 2 * half_area * cd
            drag_retreat = 0.5 * rho * v_retreat ** 2 * half_area * cd

            lift_n = max(0.0, lift_forward + lift_retreat)
            drag_n = drag_forward + drag_retreat
            imbalance_n = lift_forward - lift_retreat

            forward_hat = air_v / airspeed
            drag_force = -forward_hat * drag_n
            lateral_hat = rotate_vec(forward_hat, 90.0 if roll_deg >= 0 else -90.0)
            lateral_force = lateral_hat * abs(lift_n * math.sin(bank_rad)) * 0.65

            vertical_lift = lift_n * max(0.0, math.cos(bank_rad))
            thermal = thermal_uplift_mps2(pos, t, cfg.wind_on)
            vertical_accel = (vertical_lift / cfg.mass_kg) - G + thermal

            torque_nm = imbalance_n * r * math.sin(abs(bank_rad) + 0.08)
            H = inertia * max(omega, 0.1)
            precession = clamp(torque_nm / max(H, 0.015), -2.5, 2.5)

            roll_torque = -0.18 * math.sin(bank_rad) * lift_n
            pitch_torque = 0.08 * (vertical_lift - cfg.mass_kg * G)

            p_rad_s += (roll_torque / max(inertia * 0.62, 1e-9)) * cfg.dt
            q_rad_s += (pitch_torque / max(inertia * 0.78, 1e-9)) * cfg.dt
            r_rad_s = precession * (1.0 if roll_deg >= 0 else -1.0)
            p_rad_s *= 0.985
            q_rad_s *= 0.985

            roll_deg = clamp(roll_deg + math.degrees(p_rad_s * cfg.dt), -75.0, 75.0)
            pitch_deg = clamp(pitch_deg + math.degrees(q_rad_s * cfg.dt), -25.0, 28.0)
            yaw_deg += math.degrees(r_rad_s * cfg.dt)

            vel = rotate_vec(vel, math.degrees(r_rad_s * cfg.dt))
            vel += ((drag_force + lateral_force) / cfg.mass_kg) * cfg.dt
            vel += turbulence_vector_mps2(t, altitude, cfg.wind_on) * cfg.dt

            altitude += vertical_accel * cfg.dt * 0.45
            omega = max(0.1, omega - ((0.035 * drag_n * r) / max(inertia, 1e-9)) * cfg.dt)

        if altitude <= 0.0:
            altitude = 0.0
            vel *= 0.78
            omega *= 0.82
            crashed = True

        pos += vel * cfg.dt + wind * cfg.dt * 0.16
        distance = float(np.linalg.norm(pos))
        max_range = max(max_range, distance)
        if t > 1.0:
            closest_return = min(closest_return, distance)

        energy = 0.5 * cfg.mass_kg * float(np.dot(vel, vel)) + 0.5 * inertia * omega ** 2
        stall = cl < 0.20 or airspeed < 2.0
        return_quality = max(0.0, 1.0 - closest_return / 2.4)
        range_quality = clamp(max_range / 11.0, 0.0, 1.0)
        spin_quality = clamp(rad_s_to_rpm(omega) / 1400.0, 0.0, 1.0)
        altitude_quality = clamp(altitude / 4.0, 0.0, 1.0)
        crash_penalty = 0.55 if crashed else 1.0
        score = int(1000 * crash_penalty * (0.48 * return_quality + 0.27 * range_quality + 0.15 * spin_quality + 0.10 * altitude_quality))

        rows.append({
            "time_s": t, "x_m": pos[0], "y_m": pos[1], "altitude_m": altitude,
            "speed_mps": float(np.linalg.norm(vel)), "airspeed_mps": airspeed,
            "spin_rpm": rad_s_to_rpm(omega), "roll_deg": roll_deg, "pitch_deg": pitch_deg,
            "yaw_deg": yaw_deg, "rho": rho, "lift_n": lift_n, "drag_n": drag_n,
            "imbalance_n": imbalance_n, "torque_nm": torque_nm,
            "precession_rad_s": precession, "v_forward": v_forward, "v_retreat": v_retreat,
            "cl": cl, "cd": cd, "thermal_mps2": thermal, "energy_j": energy,
            "closest_return_m": closest_return, "score": score, "stall": stall, "crashed": crashed,
        })

        if distance > 24 or t > cfg.duration_s or rad_s_to_rpm(omega) < 80:
            break
        t += cfg.dt

    return pd.DataFrame(rows)


def trajectory_plot(df: pd.DataFrame, cfg: SimConfig, targets: list[dict] | None = None) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["x_m"], y=df["y_m"], mode="lines", name="Trajectory", line=dict(color=SUN, width=4)))
    fig.add_trace(go.Scatter(x=[0], y=[0], mode="markers+text", name="Launch", marker=dict(size=16, color=WAR_RED), text=["Launch"], textposition="bottom center"))
    final = df.iloc[-1]
    fig.add_trace(go.Scatter(x=[final["x_m"]], y=[final["y_m"]], mode="markers+text", name="Boomerang", marker=dict(size=18, color=TURQUOISE), text=["Boomerang"], textposition="top center"))

    if targets:
        for target in targets:
            gx, gy, radius = target["x"], target["y"], target["radius"]
            fig.add_shape(
                type="circle",
                x0=gx - radius,
                y0=gy - radius,
                x1=gx + radius,
                y1=gy + radius,
                line=dict(color=TURQUOISE, width=3),
                fillcolor="rgba(31,188,194,0.10)",
            )
            fig.add_trace(go.Scatter(
                x=[gx],
                y=[gy],
                mode="markers+text",
                name=f"{target['name']} ({target['points']} pts)",
                marker=dict(size=10, color=SUN, symbol="x"),
                text=[f"{target['points']} pts"],
                textposition="middle right",
            ))
    else:
        for gx, gy in [(6.5, 3.5), (10.8, 6.2), (15.2, 3.8)]:
            fig.add_shape(type="circle", x0=gx-0.8, y0=gy-0.8, x1=gx+0.8, y1=gy+0.8, line=dict(color=TURQUOISE, width=2))

    fig.update_layout(
        title=f"🪃 Flight Path | {cfg.mode} Mode",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(17,13,11,0.88)",
        font=dict(color=BONE), height=540, margin=dict(l=20, r=20, t=55, b=20),
        xaxis=dict(title="Range X (m)", gridcolor="rgba(255,196,110,0.20)", zerolinecolor=OCHRE),
        yaxis=dict(title="Range Y (m)", gridcolor="rgba(255,196,110,0.20)", zerolinecolor=OCHRE, scaleanchor="x", scaleratio=1),
        legend=dict(bgcolor="rgba(54,28,18,0.65)")
    )
    return fig


def telemetry_plot(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["time_s"], y=df["energy_j"], mode="lines", name="Energy (J)", line=dict(color=SUN)))
    fig.add_trace(go.Scatter(x=df["time_s"], y=df["lift_n"], mode="lines", name="Lift (N)", line=dict(color=TURQUOISE)))
    fig.add_trace(go.Scatter(x=df["time_s"], y=df["torque_nm"], mode="lines", name="Torque (N*m)", line=dict(color=WAR_RED)))
    fig.add_trace(go.Scatter(x=df["time_s"], y=df["closest_return_m"], mode="lines", name="Closest Return (m)", line=dict(color=GREEN)))
    fig.update_layout(
        title="📊 Scientific Telemetry", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(17,13,11,0.88)",
        font=dict(color=BONE), height=390, margin=dict(l=20, r=20, t=55, b=20),
        xaxis=dict(title="Time (s)", gridcolor="rgba(255,196,110,0.20)"),
        yaxis=dict(title="Value", gridcolor="rgba(255,196,110,0.20)"),
        legend=dict(bgcolor="rgba(54,28,18,0.65)")
    )
    return fig


def attitude_plot(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["time_s"], y=df["roll_deg"], mode="lines", name="Roll", line=dict(color=SUN)))
    fig.add_trace(go.Scatter(x=df["time_s"], y=df["pitch_deg"], mode="lines", name="Pitch", line=dict(color=TURQUOISE)))
    fig.add_trace(go.Scatter(x=df["time_s"], y=df["yaw_deg"], mode="lines", name="Yaw", line=dict(color=WAR_RED)))
    fig.update_layout(
        title="🧭 Attitude State", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(17,13,11,0.88)",
        font=dict(color=BONE), height=330, margin=dict(l=20, r=20, t=55, b=20),
        xaxis=dict(title="Time (s)", gridcolor="rgba(255,196,110,0.20)"),
        yaxis=dict(title="Degrees", gridcolor="rgba(255,196,110,0.20)"),
        legend=dict(bgcolor="rgba(54,28,18,0.65)")
    )
    return fig


st.markdown(
    """
<div class="hero">
    <h1>🪃 Return Vector: Boomerang Flight Lab 🦘🔥🌅</h1>
    <p>A Streamlit-compatible aerospace-inspired boomerang simulator with aerodynamic physics, gyroscopic-style turning, atmospheric effects, telemetry plots, target scoring, and a bright ochre/desert theme.</p>
</div>
""",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("🎮 Simulation Controls")
    mode = st.selectbox("Simulation Mode", ["Arcade", "Aerospace", "Wind Tunnel", "Research"], index=1)

    st.subheader("🪃 Launch")
    throw_angle_deg = st.slider("Throw Angle (deg)", 5.0, 75.0, 38.0, 1.0)
    throw_speed_mps = st.slider("Throw Speed (m/s)", 8.0, 30.0, 18.0, 0.5)
    spin_rpm = st.slider("Spin RPM", 300.0, 2600.0, 1450.0, 25.0)
    bank_deg = st.slider("Bank / Roll (deg)", -45.0, 45.0, 24.0, 1.0)

    st.subheader("🎨 Blade Geometry")
    camber = st.slider("Blade Camber", 0.02, 0.22, 0.12, 0.01)
    chord_m = st.slider("Chord (m)", 0.025, 0.080, 0.045, 0.001)
    arm_length_m = st.slider("Arm Length (m)", 0.18, 0.55, 0.32, 0.01)
    blade_count = st.select_slider("Blade Count", options=[2, 3, 4], value=2)

    st.subheader("🌬️ Environment")
    wind_on = st.toggle("Wind / Gusts / Thermal Uplift", value=True)
    duration_s = st.slider("Simulation Duration (s)", 4.0, 22.0, 14.0, 0.5)

    st.subheader("🎯 Target Challenge")
    target_challenge = st.toggle("Enable Target Challenge", value=True)
    target_difficulty = st.selectbox("Target Difficulty", ["Easy", "Medium", "Hard"], index=1)

cfg = SimConfig(mode, throw_angle_deg, throw_speed_mps, spin_rpm, bank_deg, camber, chord_m, arm_length_m, blade_count, wind_on, duration_s)
df = simulate(cfg)
latest = df.iloc[-1]

targets = target_set(target_difficulty) if target_challenge else []
target_scores, target_total = score_targets(df, targets) if targets else (pd.DataFrame(), 0)
combined_score = int(latest["score"]) + int(target_total)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Flight Score", f"{int(latest['score']):04d}")
c2.metric("Target Points", f"{target_total}")
c3.metric("Combined Score", f"{combined_score}")
c4.metric("Closest Return", f"{latest['closest_return_m']:.2f} m")

c5, c6, c7, c8 = st.columns(4)
c5.metric("Lift", f"{latest['lift_n']:.2f} N")
c6.metric("Torque", f"{latest['torque_nm']:.4f} N*m")
c7.metric("Airspeed", f"{latest['airspeed_mps']:.2f} m/s")
c8.metric("Spin", f"{latest['spin_rpm']:.0f} rpm")

if bool(latest["crashed"]):
    st.markdown('<div class="warning-box">⚠️ Ground impact detected. Reduce bank, increase spin, or adjust launch speed.</div>', unsafe_allow_html=True)
elif bool(latest["stall"]):
    st.markdown('<div class="warning-box">⚠️ Stall / low-lift condition detected. Increase airspeed, spin, or reduce excessive camber.</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="good-box">✅ Nominal simulated flight state. Try tuning angle, bank, spin, and geometry for a cleaner return.</div>', unsafe_allow_html=True)

left, right = st.columns([1.45, 1.0])
with left:
    st.plotly_chart(trajectory_plot(df, cfg, targets), use_container_width=True)
with right:
    st.plotly_chart(attitude_plot(df), use_container_width=True)

if target_challenge:
    st.subheader("🎯 Target Challenge Scoreboard")
    st.dataframe(target_scores, use_container_width=True, hide_index=True)

st.plotly_chart(telemetry_plot(df), use_container_width=True)

with st.expander("📚 Physics Summary"):
    st.markdown(
        """
This Streamlit version keeps the core educational model while removing the desktop-only Pygame dependency. Target Challenge mode scores hits when the simulated trajectory passes within a target ring radius.

**Lift**

```text
L = 0.5 * rho * V² * S * CL
```

**Drag**

```text
D = 0.5 * rho * V² * S * CD
```

**Boomerang blade velocity split**

```text
V_forward ≈ V_translation + rω
V_retreat ≈ |V_translation - rω|
```

**Gyroscopic-style response**

```text
precession ≈ torque / angular momentum
```

This is an educational visualization model, not a CFD-grade or flight-certified solver.
"""
    )

st.markdown(
    """
<hr>
<p class="small-note">
🪃 Return Vector is now deployable on Streamlit Cloud. Keep the Pygame desktop version separately as <code>pygame_app.py</code> if you want the local arcade game too.
</p>
""",
    unsafe_allow_html=True,
)
