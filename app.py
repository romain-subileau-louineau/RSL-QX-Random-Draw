import json
import random
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

DATA_FILE = Path(__file__).parent / "data.json"

COLORS = [
    "#E74C3C",
    "#3498DB",
    "#27AE60",
    "#F39C12",
    "#8E44AD",
    "#16A085",
    "#E67E22",
    "#D81B60",
    "#0097A7",
    "#7CB342",
    "#BF360C",
    "#546E7A",
    "#6D4C41",
    "#FB8C00",
    "#512DA8",
    "#039BE5",
    "#43A047",
    "#FFB300",
    "#E53935",
    "#7B1FA2",
]
DEFAULT_PEOPLE = ["Alice", "Bob", "Charlie", "Diana", "Ethan", "Frank"]


# ── Persistence ───────────────────────────────────────────────────────────────


def load_data() -> dict:
    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            d = json.load(f)
        # Migrate old plain-string history entries
        d["history"] = [
            {"name": e, "date": "", "week": ""} if isinstance(e, str) else e
            for e in d.get("history", [])
        ]
        # Migrate old text-filter exclusions
        if "filters" in d and "excluded" not in d:
            d["excluded"] = [k for k, v in d["filters"].items() if v.strip()]
            del d["filters"]
        d.setdefault("excluded", [])
        return d
    return {"people": DEFAULT_PEOPLE[:], "history": [], "excluded": []}


def save_data(data: dict) -> None:
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Domain helpers ────────────────────────────────────────────────────────────


def get_counts(data: dict) -> dict:
    counts = {p: 0 for p in data["people"]}
    for e in data["history"]:
        n = e.get("name", "")
        if n in counts:
            counts[n] += 1
    return counts


def get_eligible(data: dict) -> list:
    last = data["history"][-1]["name"] if data["history"] else None
    excluded = set(data.get("excluded", []))
    return [p for p in data["people"] if p != last and p not in excluded]


def compute_weights(eligible: list, counts: dict) -> list:
    """Fewer past draws → higher weight (inverse weighting)."""
    vals = [counts.get(p, 0) for p in eligible]
    mx = max(vals) if vals else 0
    return [mx + 1 - v for v in vals]


def person_color(data: dict, name: str) -> str:
    try:
        return COLORS[data["people"].index(name) % len(COLORS)]
    except ValueError:
        return COLORS[0]


# ── Spinning wheel HTML/JS component ─────────────────────────────────────────


def build_wheel_html(
    sections: list, winner_idx: int, autoplay: bool, uid: str = ""
) -> str:
    """
    sections: [{"label": str, "weight": int, "color": str}]
    Renders a Canvas-based spinning wheel. When autoplay=True, immediately
    spins and stops on the section at winner_idx.
    The pointer is a golden triangle at the top (12 o'clock).
    """
    sj = json.dumps(sections)
    ap = "true" if autoplay else "false"
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{
  background:transparent;
  display:flex;flex-direction:column;align-items:center;
  padding-top:16px;font-family:'Segoe UI',sans-serif
}}
#wrap{{position:relative;display:inline-block}}
#ptr{{
  position:absolute;top:-20px;left:50%;transform:translateX(-50%);
  width:0;height:0;
  border-left:14px solid transparent;border-right:14px solid transparent;
  border-top:34px solid #FFD700;
  filter:drop-shadow(0 2px 8px rgba(0,0,0,.55));z-index:10
}}
canvas{{display:block;border-radius:50%;box-shadow:0 6px 32px rgba(0,0,0,.4)}}
#res{{
  margin-top:16px;font-size:1.6rem;font-weight:700;
  color:#1a1a2e;min-height:42px;text-align:center;letter-spacing:.3px
}}
</style></head>
<body>
<div id="wrap"><div id="ptr"></div>
<canvas id="cv" width="430" height="430"></canvas></div>
<div id="res"></div><!-- {uid} -->
<script>
const S={sj}, WI={winner_idx}, AP={ap};
const cv=document.getElementById('cv'), ctx=cv.getContext('2d');
const CX=cv.width/2, CY=cv.height/2, R=cv.width/2-9;
const TW=S.reduce((a,x)=>a+x.weight,0);

function slices(){{
  let c=0;
  return S.map(s=>{{const sl=(s.weight/TW)*2*Math.PI,r={{s:c,sl}};c+=sl;return r;}});
}}

function draw(rot){{
  ctx.clearRect(0,0,cv.width,cv.height);
  const A=slices();
  S.forEach((s,i)=>{{
    const{{s:a,sl}}=A[i], start=a+rot;
    ctx.beginPath();ctx.moveTo(CX,CY);
    ctx.arc(CX,CY,R,start,start+sl);ctx.closePath();
    ctx.fillStyle=s.color;ctx.fill();
    ctx.strokeStyle='rgba(255,255,255,.72)';ctx.lineWidth=2;ctx.stroke();

    if(sl>0.08){{
      const mid=start+sl/2, lr=R*.65;
      ctx.save();
      ctx.translate(CX+lr*Math.cos(mid),CY+lr*Math.sin(mid));
      ctx.rotate(mid+Math.PI/2);
      ctx.textAlign='center';ctx.textBaseline='middle';
      const ml=Math.max(4,Math.floor(sl*13));
      const lbl=s.label.length>ml?s.label.slice(0,ml-1)+'…':s.label;
      ctx.fillStyle='#fff';ctx.shadowColor='rgba(0,0,0,.65)';ctx.shadowBlur=4;
      ctx.font='bold 13px Segoe UI,sans-serif';
      ctx.fillText(lbl,0,-8);
      ctx.restore();
    }}
  }});
  // outer rim
  ctx.beginPath();ctx.arc(CX,CY,R,0,2*Math.PI);
  ctx.strokeStyle='rgba(255,255,255,.2)';ctx.lineWidth=5;ctx.stroke();
  // hub
  const g=ctx.createRadialGradient(CX,CY,0,CX,CY,25);
  g.addColorStop(0,'#888');g.addColorStop(1,'#111');
  ctx.beginPath();ctx.arc(CX,CY,25,0,2*Math.PI);
  ctx.fillStyle=g;ctx.fill();
  ctx.strokeStyle='#FFD700';ctx.lineWidth=3;ctx.stroke();
}}

// Pointer at -PI/2 (top). Find rotation so winner's midpoint lands there.
const A=slices();
const wm=A[WI].s+A[WI].sl/2;
const TARGET=-Math.PI/2-wm+6*2*Math.PI; // 6 full turns + fine alignment

let t0=null;
function ease(t){{return 1-Math.pow(1-t,3.5);}}
function spin(ts){{
  if(!t0)t0=ts;
  const t=Math.min((ts-t0)/6000,1);
  draw(ease(t)*TARGET);
  if(t<1) requestAnimationFrame(spin);
  else document.getElementById('res').textContent='🎉 '+S[WI].label+' !';
}}

draw(0);
if(AP) setTimeout(()=>requestAnimationFrame(spin),350);
</script></body></html>"""


# ── Streamlit app ─────────────────────────────────────────────────────────────

st.set_page_config(page_title="Random Picker", page_icon="🎯", layout="wide")

if "data" not in st.session_state:
    st.session_state.data = load_data()
for k, v in [("autoplay", False), ("draw_secs", []), ("draw_winner", 0), ("uid", "")]:
    if k not in st.session_state:
        st.session_state[k] = v

data = st.session_state.data

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("👥 People")

    c1, c2 = st.columns([4, 1])
    with c1:
        new_name = st.text_input(
            "name", label_visibility="collapsed", placeholder="Name…"
        )
    with c2:
        if st.button("➕", use_container_width=True):
            n = new_name.strip()
            if n and n not in data["people"]:
                data["people"].append(n)
                save_data(data)
                st.rerun()

    to_rm = st.selectbox("remove", ["—"] + data["people"], label_visibility="collapsed")
    if st.button("🗑️ Remove", use_container_width=True) and to_rm != "—":
        data["people"].remove(to_rm)
        if to_rm in data.get("excluded", []):
            data["excluded"].remove(to_rm)
        save_data(data)
        st.rerun()

    st.divider()
    st.header("🚫 Exclusions")
    st.caption("ON = excluded from the draw")

    old_excl = set(data.get("excluded", []))
    new_excl = set()
    for p in data["people"]:
        if st.toggle(p, value=p in old_excl, key=f"x_{p}"):
            new_excl.add(p)
    if new_excl != old_excl:
        data["excluded"] = list(new_excl)
        save_data(data)

    st.divider()
    st.header("📜 History")
    st.caption("Editable — click 💾 to save.")

    if data["history"]:
        df_h = (
            pd.DataFrame(data["history"])
            .reindex(columns=["name", "date", "week"])
            .fillna("")
        )
        df_edit = st.data_editor(
            df_h,
            column_config={
                "name": st.column_config.SelectboxColumn(
                    "Name", options=data["people"], required=True, width="medium"
                ),
                "date": st.column_config.TextColumn("Date", width="small"),
                "week": st.column_config.TextColumn("Week", width="small"),
            },
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
        )
        cs, ce = st.columns(2)
        with cs:
            if st.button("💾 Save", use_container_width=True):
                clean = df_edit.dropna(subset=["name"]).query("name != ''")
                data["history"] = clean.to_dict("records")
                save_data(data)
                st.rerun()
        with ce:
            if st.button("🗑️ Clear all", use_container_width=True):
                data["history"] = []
                save_data(data)
                st.rerun()
    else:
        st.info("No draws yet.")


# ── Main area ─────────────────────────────────────────────────────────────────

st.title("🎯 Random Picker")
st.caption(
    "Spin the wheel to randomly pick someone from your team. "
    "People who have been drawn less often get a higher chance — keeping it fair over time."
)

eligible = get_eligible(data)
counts = get_counts(data)
weights = compute_weights(eligible, counts) if eligible else []

col_wheel, col_stats = st.columns([3, 2])

with col_wheel:
    if eligible:
        just_drew = st.session_state.autoplay and bool(st.session_state.draw_secs)
        if just_drew:
            # Post-draw: render the animation with the pre-draw state
            secs = st.session_state.draw_secs
            wi = st.session_state.draw_winner
            ap = True
            uid = st.session_state.uid
            st.session_state.autoplay = False  # prevent re-trigger on next rerun
        else:
            secs = [
                {"label": p, "weight": w, "color": person_color(data, p)}
                for p, w in zip(eligible, weights)
            ]
            wi = 0
            ap = False
            uid = ""

        components.html(build_wheel_html(secs, wi, ap, uid), height=520)

        if st.button("🚀 Spin the wheel!", type="primary", use_container_width=True):
            ws = compute_weights(eligible, counts)
            winner = random.choices(eligible, weights=ws, k=1)[0]
            winner_idx = eligible.index(winner)

            now = datetime.now()
            iso = now.isocalendar()
            data["history"].append(
                {
                    "name": winner,
                    "date": now.strftime("%Y-%m-%d"),
                    "week": f"{iso.year}-S{iso.week:02d}",
                }
            )
            save_data(data)

            st.session_state.draw_secs = [
                {"label": p, "weight": w, "color": person_color(data, p)}
                for p, w in zip(eligible, ws)
            ]
            st.session_state.draw_winner = winner_idx
            st.session_state.autoplay = True
            st.session_state.uid = str(random.random())  # force iframe refresh
            st.rerun()

        # While animating, skip the last entry (winner not yet revealed)
        display_history = data["history"][:-1] if just_drew else data["history"]
        if display_history:
            st.divider()
            st.subheader("📜 History")
            for entry in reversed(display_history):
                name = entry.get("name", "")
                date = entry.get("date", "")
                week = entry.get("week", "")
                meta = f" — {week}" if week else ""
                st.write(f"• **{name}**{meta}")
    else:
        st.warning(
            "⚠️ No eligible person! "
            "Disable some exclusions or add people in the sidebar."
        )

with col_stats:
    st.subheader("📊 Draw odds")
    if eligible:
        total_w = sum(weights)
        df_stats = pd.DataFrame(
            [
                {
                    "👤 Name": p,
                    "🔢 Draws": counts[p],
                    "📈 Chance": f"{w / total_w * 100:.1f}%",
                }
                for p, w in zip(eligible, weights)
            ]
        )
        st.dataframe(df_stats, use_container_width=True, hide_index=True)

        st.caption(
            "**Weight** = max(group draws) + 1 − person's draws.  \n"
            "Fewer past draws → higher weight → higher chance."
        )

        non_elig = []
        last_p = data["history"][-1]["name"] if data["history"] else None
        if last_p:
            non_elig.append(f"**{last_p}** – last drawn")
        for p in data.get("excluded", []):
            non_elig.append(f"**{p}** – manually excluded")
        if non_elig:
            with st.expander(f"🚫 {len(non_elig)} excluded this round"):
                for msg in non_elig:
                    st.write(f"• {msg}")
    else:
        st.info("No eligible person to calculate odds.")
