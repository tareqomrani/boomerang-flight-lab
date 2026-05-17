"""
Return Vector — Boomerang Target Lab
Streamlit + HTML5 Canvas game.

Run:
    streamlit run app.py
"""

import json
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Return Vector — Boomerang Target Lab",
    page_icon="🪃",
    layout="wide",
)

st.sidebar.header("🪃 Game Settings")
target_goal = st.sidebar.slider("Target goal", 3, 20, 8, 1)
target_count = st.sidebar.slider("Total targets", target_goal, 30, max(12, target_goal), 1)
rock_count = st.sidebar.slider("Rock hazards", 0, 35, 14, 1)
throw_power = st.sidebar.slider("Throw power", 0.65, 1.60, 1.00, 0.05)
spin_power = st.sidebar.slider("Spin power", 0.65, 1.80, 1.00, 0.05)
wind_strength = st.sidebar.slider("Wind strength", 0.0, 1.8, 0.65, 0.05)
drag = st.sidebar.slider("Aerodynamic drag", 0.20, 1.30, 0.62, 0.05)
control_mode = st.sidebar.selectbox("Control mode", ["D-pad", "Joystick"])
difficulty = st.sidebar.selectbox("Target difficulty", ["Easy", "Medium", "Hard"], index=1)

cfg = dict(
    target_goal=int(target_goal),
    target_count=int(target_count),
    rock_count=int(rock_count),
    throw_power=float(throw_power),
    spin_power=float(spin_power),
    wind_strength=float(wind_strength),
    drag=float(drag),
    control=("joystick" if control_mode == "Joystick" else "dpad"),
    difficulty=difficulty.lower(),
)

HTML = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no" />
<title>Return Vector — Boomerang Target Lab</title>
<style>
  :root{
    --charcoal:#110d0b; --clay:#8d361f; --ochre:#c65b1c; --sand:#ffc46e;
    --sun:#ffb824; --red:#db2826; --bone:#fff0d0; --turq:#1fbcc2; --green:#39cc79;
  }
  html,body{
    margin:0;height:100%;
    background:radial-gradient(circle at 76% 12%, rgba(255,184,36,.22), transparent 24%),
      linear-gradient(180deg,#2a1008 0%, #140906 52%, #070403 100%);
    color:var(--bone);
    font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;
    overflow-x:hidden;
  }
  .wrap{display:flex;flex-direction:column;min-height:720px}
  header{
    display:flex;justify-content:space-between;align-items:center;gap:.6rem;
    padding:.7rem 1rem;
    background:repeating-linear-gradient(45deg, rgba(255,196,110,.16) 0 8px, transparent 8px 22px),
      linear-gradient(90deg,#140805,#8d361f 42%,#110d0b);
    border-bottom:3px solid var(--ochre);
    box-shadow:0 8px 20px rgba(0,0,0,.25);
  }
  header h1{font-size:1.2rem;margin:0;color:var(--sun);letter-spacing:.02em}
  .pill{font-size:.82rem;padding:.25rem .6rem;border-radius:999px;background:#0007;border:1px solid var(--sand);color:var(--bone);white-space:nowrap}
  .row{display:flex;gap:.45rem;align-items:center}
  .col{display:flex;flex-direction:column;gap:.45rem;align-items:center;justify-content:center;min-width:160px}
  #arena{
    border:4px solid rgba(255,196,110,.85); border-radius:18px; position:relative; overflow:hidden;
    min-height:460px; max-width:1220px; margin:.4rem auto 7rem auto; background:#160b07;
    box-shadow:0 0 0 3px #0008 inset, 0 12px 30px #0008;
  }
  canvas{display:block;width:100%;height:100%}
  .hud{
    position:absolute;right:.65rem;bottom:.65rem;z-index:3;background:rgba(17,13,11,.88);
    border:2px solid var(--ochre);border-radius:14px;padding:.45rem .6rem;
    display:grid;grid-template-columns:repeat(2,minmax(90px,1fr));gap:.28rem .7rem;
    box-shadow:0 0 20px rgba(255,184,36,.18);pointer-events:none;font-weight:800;color:var(--bone);font-size:.82rem;
  }
  .hud span{color:var(--sun)}
  .aeroHud{
    position:absolute;left:.65rem;top:.65rem;z-index:3;background:rgba(17,13,11,.84);
    border:2px solid var(--turq);border-radius:14px;padding:.55rem .7rem;min-width:245px;
    box-shadow:0 0 20px rgba(31,188,194,.18);pointer-events:none;font-weight:750;color:var(--bone);font-size:.82rem;
  }
  .aeroHud h3{margin:.1rem 0 .4rem 0;color:var(--turq);font-size:.9rem;letter-spacing:.06em}
  .aeroLine{display:flex;justify-content:space-between;gap:1rem;border-bottom:1px dotted rgba(255,196,110,.25);padding:.08rem 0}
  .aeroLine span:last-child{color:var(--sun)}
  .hint{color:rgba(255,240,208,.86);text-align:center;padding:.4rem 0;font-weight:700}
  .dock{
    position:fixed;left:0;right:0;bottom:0;z-index:10;display:flex;justify-content:space-between;align-items:center;
    gap:.75rem;padding:.7rem 1rem;background:repeating-linear-gradient(90deg, rgba(198,91,28,.15) 0 14px, transparent 14px 32px),
      linear-gradient(180deg, rgba(17,13,11,.76), rgba(17,13,11,.96));
    border-top:3px solid var(--ochre);backdrop-filter:saturate(1.1) blur(6px);
  }
  .btn{
    display:flex;align-items:center;justify-content:center;width:64px;height:64px;border-radius:16px;
    font-weight:900;font-size:22px;border:2px solid rgba(255,196,110,.66);
    background:linear-gradient(180deg,#3a160b,#1b0c07);color:var(--sand);box-shadow:0 4px 0 #0008;
    touch-action:none;user-select:none;-webkit-user-select:none;
  }
  .btn:active,.btn.active{transform:translateY(1px);box-shadow:0 2px 0 #0008;background:linear-gradient(180deg,#6b2715,#2a1008);border-color:var(--sun)}
  .widebtn{width:160px;height:64px;font-size:17px;border-radius:16px}
  .pad{display:grid;grid-template-columns:repeat(3,64px);grid-template-rows:repeat(3,64px);gap:.4rem}
  .ghost{opacity:0}
  .stickpad{
    position:relative;width:180px;height:180px;border-radius:50%;background:radial-gradient(circle at 50% 50%, #5b2110, #170906);
    border:2px solid var(--sand);box-shadow:inset 0 8px 18px #0008, 0 4px 0 #0007;touch-action:none;
  }
  .stick{
    position:absolute;left:50%;top:50%;width:84px;height:84px;margin:-42px 0 0 -42px;border-radius:50%;
    background:linear-gradient(180deg,var(--sun),var(--ochre));border:3px solid var(--bone);box-shadow:0 4px 0 #0008;
    display:flex;align-items:center;justify-content:center;font-weight:900;color:var(--charcoal);
  }
  @media(max-width:720px){
    header h1{font-size:1rem}.pill{font-size:.72rem}.hud{grid-template-columns:1fr;right:.4rem;bottom:.4rem;font-size:.72rem}
    .aeroHud{left:.4rem;top:.4rem;min-width:190px;font-size:.72rem;padding:.45rem}
    .btn{width:56px;height:56px;font-size:19px;border-radius:14px}.widebtn{width:136px;height:56px}
    .pad{grid-template-columns:repeat(3,56px);grid-template-rows:repeat(3,56px)}
    .stickpad{width:158px;height:158px}.stick{width:74px;height:74px;margin:-37px 0 0 -37px}
  }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>🪃 Return Vector — Boomerang Target Lab 🦘🐨🔥</h1>
    <div class="row"><span class="pill">Aim • Throw • Return • Score</span><button class="btn widebtn" id="mode">Switch to Joystick</button></div>
  </header>
  <div id="arena">
    <canvas id="game" width="1280" height="720" aria-label="Boomerang target arena"></canvas>
    <div class="aeroHud" id="aeroHud">
      <h3>FLIGHT TELEMETRY</h3>
      <div class="aeroLine"><span>Airspeed</span><span id="airspeed">0.0</span></div>
      <div class="aeroLine"><span>Spin</span><span id="spin">0</span></div>
      <div class="aeroLine"><span>Lift</span><span id="lift">0.0</span></div>
      <div class="aeroLine"><span>Drag</span><span id="dragv">0.0</span></div>
      <div class="aeroLine"><span>Torque</span><span id="torque">0.000</span></div>
      <div class="aeroLine"><span>Precession</span><span id="prec">0.00</span></div>
      <div class="aeroLine"><span>Blade V f/r</span><span id="bladev">0/0</span></div>
    </div>
    <div class="hud" id="hud">
      <div>Targets: <span id="score">0</span>/<span id="goal">8</span></div>
      <div>Points: <span id="points">0</span></div>
      <div>Throws: <span id="throws">0</span></div>
      <div>Wind: <span id="windread">0.0</span></div>
    </div>
  </div>
  <div class="hint">Use D-pad/joystick to aim • Press THROW • Hit target rings • Curve comes from spin, lift imbalance, and precession</div>
  <div class="dock">
    <div id="leftDock"></div>
    <div class="col">
      <button class="btn widebtn" id="throwBtn">🪃 THROW</button>
      <div class="row"><button class="btn" id="mute">🔈</button><button class="btn widebtn" id="reset">⟳ Restart</button></div>
    </div>
  </div>
</div>
<script id="cfg" type="application/json">__CFG_JSON__</script>
<script>
(() => {
  const cfg = JSON.parse(document.getElementById('cfg').textContent || "{}");
  let audioCtx, muted=false;
  const AC = window.AudioContext || window.webkitAudioContext;
  function ensureAudio(){ if(!audioCtx && AC){ audioCtx=new AC(); } if(audioCtx && audioCtx.state==='suspended') audioCtx.resume(); }
  function beep(freq=660,dur=90,type='sine',gain=0.04){
    if(muted||!audioCtx)return; const o=audioCtx.createOscillator(),g=audioCtx.createGain();
    o.type=type;o.frequency.value=freq;g.gain.value=gain;o.connect(g);g.connect(audioCtx.destination);o.start();setTimeout(()=>o.stop(),dur);
  }
  function vibrate(ms=20){ if(navigator.vibrate) try{navigator.vibrate(ms);}catch{} }
  document.getElementById('mute').addEventListener('click',e=>{ensureAudio();muted=!muted;e.currentTarget.textContent=muted?'🔇':'🔈';});
  const canvas=document.getElementById('game'),ctx=canvas.getContext('2d');
  const W=canvas.width,H=canvas.height,rand=(a,b)=>a+Math.random()*(b-a),clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
  function fit(){const r=W/H,box=document.getElementById('arena').getBoundingClientRect();let w=box.width,h=box.height;if(w/h>r)w=h*r;else h=w/r;canvas.style.width=w+'px';canvas.style.height=h+'px';}
  addEventListener('resize',fit);fit();
  function difficultyRadius(){return cfg.difficulty==='easy'?36:(cfg.difficulty==='hard'?22:29);}
  function targetPoints(){return cfg.difficulty==='easy'?75:(cfg.difficulty==='hard'?175:125);}
  function spawn(){const r=difficultyRadius();return{
    aim:{angle:-0.20,power:cfg.throw_power||1,spin:cfg.spin_power||1},
    boomerang:{x:W*.16,y:H*.62,vx:0,vy:0,omega:0,angle:0,active:false,t:0,trail:[]},
    targets:Array.from({length:cfg.target_count||12},(_,i)=>({x:rand(W*.28,W*.9),y:rand(H*.12,H*.78),r:r,hit:false,points:targetPoints()+Math.floor(i*8)})),
    rocks:Array.from({length:cfg.rock_count||14},()=>({x:rand(W*.25,W*.95),y:rand(H*.16,H*.83),r:rand(16,31)})),
    score:0,points:0,throws:0,goal:cfg.target_goal||8,won:false,telemetry:{airspeed:0,spin:0,lift:0,drag:0,torque:0,prec:0,vf:0,vr:0,wind:0}
  };}
  let state=spawn();
  const keys={};addEventListener('keydown',e=>{keys[e.code]=true;ensureAudio();if(e.code==='Space'){e.preventDefault();throwBoomerang();}});addEventListener('keyup',e=>{keys[e.code]=false;});
  function buildDpad(){const pad=document.createElement('div');pad.className='pad';pad.innerHTML=`
    <div class="ghost"></div><button class="btn" data-key="ArrowUp">▲</button><div class="ghost"></div>
    <button class="btn" data-key="ArrowLeft">◀</button><div class="ghost"></div><button class="btn" data-key="ArrowRight">▶</button>
    <div class="ghost"></div><button class="btn" data-key="ArrowDown">▼</button><div class="ghost"></div>`;
    pad.querySelectorAll('.btn[data-key]').forEach(el=>{const code=el.getAttribute('data-key');const press=e=>{e.preventDefault();ensureAudio();keys[code]=true;};const release=e=>{e.preventDefault();keys[code]=false;};
      el.addEventListener('touchstart',press,{passive:false});el.addEventListener('touchend',release,{passive:false});el.addEventListener('touchcancel',release,{passive:false});el.addEventListener('mousedown',press);el.addEventListener('mouseup',release);el.addEventListener('mouseleave',release);});
    return pad;}
  let joy={x:0,y:0,active:false};
  function buildStick(){const pad=document.createElement('div');pad.className='stickpad';const knob=document.createElement('div');knob.className='stick';knob.textContent='🪃';pad.appendChild(knob);
    const rect=()=>pad.getBoundingClientRect();function setFrom(evt){const r=rect(),t=(evt.touches&&evt.touches[0])||evt,cx=r.left+r.width/2,cy=r.top+r.height/2;let dx=t.clientX-cx,dy=t.clientY-cy;const max=r.width*.42,m=Math.hypot(dx,dy);if(m>max){dx*=max/m;dy*=max/m;}knob.style.transform=`translate(${dx}px,${dy}px)`;joy={x:dx/max,y:dy/max,active:true};ensureAudio();}
    function reset(){knob.style.transform='translate(0,0)';joy={x:0,y:0,active:false};}
    pad.addEventListener('touchstart',e=>{e.preventDefault();setFrom(e);},{passive:false});pad.addEventListener('touchmove',e=>{e.preventDefault();setFrom(e);},{passive:false});pad.addEventListener('touchend',e=>{e.preventDefault();reset();},{passive:false});pad.addEventListener('mousedown',e=>{e.preventDefault();setFrom(e);});pad.addEventListener('mousemove',e=>{if(e.buttons)setFrom(e);});pad.addEventListener('mouseup',reset);pad.addEventListener('mouseleave',reset);return pad;}
  const leftDock=document.getElementById('leftDock'),modeBtn=document.getElementById('mode');let mode=cfg.control||'dpad';
  function renderLeft(){leftDock.innerHTML='';if(mode==='dpad'){leftDock.appendChild(buildDpad());modeBtn.textContent='Switch to Joystick';}else{leftDock.appendChild(buildStick());modeBtn.textContent='Switch to D-pad';}}
  modeBtn.addEventListener('click',()=>{mode=(mode==='dpad'?'joystick':'dpad');renderLeft();ensureAudio();beep(440,80,'triangle',.025);});renderLeft();
  document.getElementById('reset').addEventListener('click',()=>{state=spawn();vibrate(35);beep(380,90,'square',.035);});
  document.getElementById('throwBtn').addEventListener('click',()=>{ensureAudio();throwBoomerang();});
  function throwBoomerang(){const b=state.boomerang;if(b.active)return;state.throws++;const speed=430*(cfg.throw_power||1)*state.aim.power,angle=state.aim.angle;b.x=W*.16;b.y=H*.62;b.vx=Math.cos(angle)*speed;b.vy=Math.sin(angle)*speed;b.omega=1650*(cfg.spin_power||1)*state.aim.spin;b.angle=angle;b.active=true;b.t=0;b.trail=[];vibrate(32);beep(660,70,'sine',.04);setTimeout(()=>beep(820,55,'triangle',.032),75);}
  function updateAim(dt){if(state.boomerang.active)return;if(mode==='joystick'&&joy.active){state.aim.angle=Math.atan2(joy.y,Math.max(.15,joy.x));state.aim.power=clamp(.7+Math.hypot(joy.x,joy.y)*.7,.65,1.55);state.aim.spin=clamp(.8+Math.max(0,-joy.y)*.65,.65,1.8);}else{if(keys.ArrowLeft)state.aim.angle-=1.65*dt;if(keys.ArrowRight)state.aim.angle+=1.65*dt;if(keys.ArrowUp)state.aim.power=clamp(state.aim.power+.55*dt,.65,1.55);if(keys.ArrowDown)state.aim.power=clamp(state.aim.power-.55*dt,.65,1.55);}state.aim.angle=clamp(state.aim.angle,-1.20,.45);}
  function updateBoomerang(dt){const b=state.boomerang;if(!b.active)return;b.t+=dt;const windBase=cfg.wind_strength||.65,wx=22*windBase+12*windBase*Math.sin(b.t*.9),wy=7*windBase*Math.cos(b.t*.55),airVx=b.vx-wx,airVy=b.vy-wy,V=Math.max(1,Math.hypot(airVx,airVy)),omegaRad=Math.max(.1,b.omega*2*Math.PI/60),r=.32,vf=V+r*omegaRad,vr=Math.max(.1,Math.abs(V-r*omegaRad));
    const rho=1.225,area=.32*.045*2,cl=.68+.12*Math.sin(b.t*1.2),cd=.055+.045*cl*cl,lift=.5*rho*((vf*vf+vr*vr)/2)*area*cl,dragForce=.5*rho*V*V*area*cd*(cfg.drag||.62),imbalance=.5*rho*(vf*vf-vr*vr)*(area/2)*cl,torque=imbalance*r*.20,H=.095*(.32*.32/3)*omegaRad,precession=clamp(torque/Math.max(H,.015),-2.2,2.2);
    const turn=precession*.82*dt,c=Math.cos(turn),s=Math.sin(turn),nvx=b.vx*c-b.vy*s,nvy=b.vx*s+b.vy*c;b.vx=nvx;b.vy=nvy;b.vx+=(-airVx/V)*dragForce*dt*.38;b.vy+=(-airVy/V)*dragForce*dt*.38;b.vy-=lift*dt*1.1;b.vx+=wx*dt*.18;b.vy+=wy*dt*.18;b.x+=b.vx*dt;b.y+=b.vy*dt;b.omega*=(1-.075*dt);b.angle+=omegaRad*dt*2;b.trail.push({x:b.x,y:b.y});if(b.trail.length>160)b.trail.shift();
    state.telemetry={airspeed:V,spin:b.omega,lift,drag:dragForce,torque,prec:precession,vf,vr,wind:Math.hypot(wx,wy)};
    for(const t of state.targets){if(t.hit)continue;const d=Math.hypot(b.x-t.x,b.y-t.y);if(d<t.r+20){t.hit=true;state.score++;state.points+=t.points;vibrate(22);beep(900,65,'sine',.04);setTimeout(()=>beep(1120,55,'triangle',.035),60);if(state.score>=state.goal){state.won=true;vibrate(90);setTimeout(()=>vibrate(90),120);}}}
    for(const rck of state.rocks){if(Math.hypot(b.x-rck.x,b.y-rck.y)<rck.r+16){b.vx*=.72;b.vy*=.72;b.omega*=.88;vibrate(18);beep(170,70,'square',.025);}}
    if(b.x<-120||b.x>W+140||b.y<-160||b.y>H+160||b.t>14||b.omega<110){b.active=false;beep(240,65,'sine',.025);}}
  function update(dt){updateAim(dt);updateBoomerang(dt);document.getElementById('score').textContent=Math.min(state.score,state.goal);document.getElementById('goal').textContent=state.goal;document.getElementById('points').textContent=state.points;document.getElementById('throws').textContent=state.throws;document.getElementById('windread').textContent=state.telemetry.wind.toFixed(1);document.getElementById('airspeed').textContent=state.telemetry.airspeed.toFixed(1)+' px/s';document.getElementById('spin').textContent=state.telemetry.spin.toFixed(0)+' rpm';document.getElementById('lift').textContent=state.telemetry.lift.toFixed(2)+' N';document.getElementById('dragv').textContent=state.telemetry.drag.toFixed(2)+' N';document.getElementById('torque').textContent=state.telemetry.torque.toFixed(3);document.getElementById('prec').textContent=state.telemetry.prec.toFixed(2);document.getElementById('bladev').textContent=state.telemetry.vf.toFixed(0)+'/'+state.telemetry.vr.toFixed(0);}
  function drawBackground(){const grad=ctx.createLinearGradient(0,0,0,H);grad.addColorStop(0,'#3a160b');grad.addColorStop(.55,'#8d361f');grad.addColorStop(1,'#160806');ctx.fillStyle=grad;ctx.fillRect(0,0,W,H);ctx.fillStyle='rgba(255,184,36,.88)';ctx.beginPath();ctx.arc(W*.77,H*.32,56,0,Math.PI*2);ctx.fill();ctx.fillStyle='#2a1008';ctx.beginPath();ctx.moveTo(0,H*.72);for(let x=0;x<=W;x+=80){ctx.lineTo(x,H*.72+Math.sin(x*.011)*22);}ctx.lineTo(W,H);ctx.lineTo(0,H);ctx.closePath();ctx.fill();for(let x=45;x<W;x+=80){for(let y=42;y<H;y+=92){ctx.fillStyle='rgba(255,196,110,.45)';ctx.beginPath();ctx.arc(x,y,2.3+Math.sin((x+y)*.02)*1.2,0,Math.PI*2);ctx.fill();}}ctx.strokeStyle='rgba(219,40,38,.55)';ctx.lineWidth=10;for(let x=-W;x<W;x+=180){ctx.beginPath();ctx.moveTo(x,H);ctx.lineTo(x+H,0);ctx.stroke();}ctx.strokeStyle='rgba(31,188,194,.45)';ctx.lineWidth=4;for(let x=-W+60;x<W;x+=180){ctx.beginPath();ctx.moveTo(x,H);ctx.lineTo(x+H,0);ctx.stroke();}}
  function drawBoomerang(x,y,ang,scale=1){ctx.save();ctx.translate(x,y);ctx.rotate(ang);ctx.scale(scale,scale);ctx.lineCap='round';ctx.lineJoin='round';ctx.strokeStyle='#fff0d0';ctx.lineWidth=18;ctx.beginPath();ctx.moveTo(-52,16);ctx.quadraticCurveTo(-4,-20,58,-10);ctx.stroke();ctx.strokeStyle='#db2826';ctx.lineWidth=10;ctx.beginPath();ctx.moveTo(-42,13);ctx.quadraticCurveTo(-1,-12,48,-7);ctx.stroke();ctx.strokeStyle='#ffb824';ctx.lineWidth=4;ctx.beginPath();ctx.moveTo(-20,8);ctx.quadraticCurveTo(4,-4,28,-3);ctx.stroke();ctx.fillStyle='#1fbcc2';for(let i=-35;i<=35;i+=22){ctx.beginPath();ctx.arc(i,2*Math.sin(i),3,0,Math.PI*2);ctx.fill();}ctx.restore();}
  function drawAim(){const b=state.boomerang;if(b.active)return;const x=W*.16,y=H*.62,len=145*state.aim.power;ctx.strokeStyle='#ffb824';ctx.lineWidth=5;ctx.setLineDash([10,8]);ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x+Math.cos(state.aim.angle)*len,y+Math.sin(state.aim.angle)*len);ctx.stroke();ctx.setLineDash([]);drawBoomerang(x,y,state.aim.angle,.7);}
  function drawTargets(){for(const t of state.targets){if(t.hit)continue;ctx.save();ctx.translate(t.x,t.y);ctx.strokeStyle='#1fbcc2';ctx.lineWidth=4;ctx.beginPath();ctx.arc(0,0,t.r,0,Math.PI*2);ctx.stroke();ctx.strokeStyle='#ffb824';ctx.lineWidth=3;ctx.beginPath();ctx.arc(0,0,t.r*.58,0,Math.PI*2);ctx.stroke();ctx.fillStyle='#fff0d0';ctx.font='bold 13px system-ui';ctx.textAlign='center';ctx.fillText(t.points,0,4);ctx.restore();}}
  function drawRocks(){for(const r of state.rocks){ctx.fillStyle='#3d251c';ctx.strokeStyle='#ffc46e88';ctx.lineWidth=2;ctx.beginPath();ctx.arc(r.x,r.y,r.r,0,Math.PI*2);ctx.fill();ctx.stroke();}}
  function drawBoomerangFlight(){const b=state.boomerang;if(!b.active)return;for(let i=1;i<b.trail.length;i++){const a=i/b.trail.length;ctx.strokeStyle=`rgba(255,184,36,${a*.75})`;ctx.lineWidth=2+a*4;ctx.beginPath();ctx.moveTo(b.trail[i-1].x,b.trail[i-1].y);ctx.lineTo(b.trail[i].x,b.trail[i].y);ctx.stroke();}drawBoomerang(b.x,b.y,b.angle,.82);}
  function drawWin(){if(!state.won)return;ctx.fillStyle='rgba(17,13,11,.82)';ctx.fillRect(W*.22,H*.39,W*.56,120);ctx.strokeStyle='#ffb824';ctx.lineWidth=5;ctx.strokeRect(W*.22,H*.39,W*.56,120);ctx.fillStyle='#ffb824';ctx.font='900 34px system-ui';ctx.textAlign='center';ctx.fillText('TARGET MASTER',W*.5,H*.39+55);ctx.fillStyle='#fff0d0';ctx.font='bold 18px system-ui';ctx.fillText('Reset to play again',W*.5,H*.39+86);}
  function draw(){ctx.clearRect(0,0,W,H);drawBackground();drawTargets();drawRocks();drawAim();drawBoomerangFlight();drawWin();}
  draw();let last=performance.now();function tick(t){const dt=Math.min(.032,(t-last)/1000);last=t;update(dt);draw();requestAnimationFrame(tick);}requestAnimationFrame(tick);
})();
</script>
</body>
</html>
"""

components.html(HTML.replace("__CFG_JSON__", json.dumps(cfg)), height=850, scrolling=False)
