import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import json
from typing import Dict, Any, List

# Core modules imports
from core.models import DraftState, TimelineEvent, MatchTimeline
from core.draft_analyzer import DraftAnalyzer
from core.item_analyzer import ItemAnalyzer
from core.meta_analyzer import MetaAnalyzer
from core.live_coach import LiveCoach
from vision.replay_processor import ReplayProcessor

TEST_VIDEOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test", "videos")
MAX_UPLOAD_MB = 200


@st.cache_resource
def get_meta_analyzer() -> MetaAnalyzer:
    return MetaAnalyzer()


@st.cache_resource
def get_live_coach() -> LiveCoach:
    return LiveCoach()


@st.cache_data(show_spinner=False)
def run_meta_bpw(
    tournament_codes: tuple,
    tournament_tiers: tuple | None,
    tournament_stages: str | None,
    tournament_start_date: int | None,
    tournament_end_date: int | None,
):
    analyzer = get_meta_analyzer()
    result = analyzer.analyze(
        tournament_codes=list(tournament_codes) if tournament_codes else None,
        tournament_tiers=list(tournament_tiers) if tournament_tiers else None,
        tournament_stages=tournament_stages,
        tournament_start_date=tournament_start_date,
        tournament_end_date=tournament_end_date,
    )
    return result["num_games"], result["table"]


def list_test_videos() -> list[str]:
    if not os.path.isdir(TEST_VIDEOS_DIR):
        return []
    return sorted(
        [
            f
            for f in os.listdir(TEST_VIDEOS_DIR)
            if f.lower().endswith(".mp4")
        ]
    )

# 1. Page Configuration
st.set_page_config(
    page_title="MLBB Match Analyst",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# 2. Theme Toggle State
if "theme" not in st.session_state:
    st.session_state.theme = "dark"  # Default to premium dark mode

def toggle_theme():
    st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"

IS_DARK = st.session_state.theme == "dark"

# 3. CSS Design System
# Custom color palette and layout styles injected into Streamlit
bg_val = "#09090b" if IS_DARK else "#ffffff"
bg_subtle_val = "#0c0c0f" if IS_DARK else "#f9fafb"
card_val = "#0c0c0f" if IS_DARK else "#ffffff"
card_hover_val = "#131316" if IS_DARK else "#f4f4f5"
border_val = "#1e1e24" if IS_DARK else "#e4e4e7"
border_subtle_val = "#16161a" if IS_DARK else "#f0f0f2"
text_val = "#fafafa" if IS_DARK else "#09090b"
text_muted_val = "#a1a1aa" if IS_DARK else "#71717a"
text_dim_val = "#52525b" if IS_DARK else "#a1a1aa"
green_val = "#22c55e" if IS_DARK else "#16a34a"
green_muted_val = "rgba(34,197,94,0.12)" if IS_DARK else "rgba(22,163,74,0.08)"
red_val = "#ef4444" if IS_DARK else "#dc2626"
red_muted_val = "rgba(239,68,68,0.12)" if IS_DARK else "rgba(220,38,38,0.08)"
amber_val = "#f59e0b" if IS_DARK else "#d97706"
amber_muted_val = "rgba(245,158,11,0.12)" if IS_DARK else "rgba(217,119,6,0.08)"
shadow_val = "none" if IS_DARK else "0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.03)"

css = f"""
<style>
/* Hide default Streamlit decoration */
header[data-testid="stHeader"], #MainMenu, footer, [data-testid="stToolbar"],
[data-testid="stDecoration"], [data-testid="stStatusWidget"], .stDeployButton,
div[data-testid="stSidebarCollapsedControl"] {{
    display: none !important;
}}

/* Global Application Variables & Styles */
html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"], .main, .block-container, section[data-testid="stMain"] {{
    background-color: {bg_val} !important;
    color: {text_val} !important;
    font-family: 'DM Sans', -apple-system, sans-serif !important;
}}

.block-container {{
    padding: 1.5rem 2.5rem 2rem !important;
    max-width: 1380px !important;
}}

/* Custom Grid Margins */
[data-testid="stHorizontalBlock"] {{
    gap: 1.25rem !important;
}}
[data-testid="stVerticalBlock"] > div:has(> [data-testid="stHorizontalBlock"]) {{
    margin-bottom: 0.5rem !important;
}}

/* Pill Tabs styling */
button[data-baseweb="tab"] {{
    background: transparent !important;
    color: {text_muted_val} !important;
    font-size: 0.85rem !important;
    font-weight: 600 !important;
    padding: 0.6rem 1.2rem !important;
    border: 1px solid transparent !important;
    border-radius: 7px !important;
    transition: all 0.2s ease !important;
}}
button[data-baseweb="tab"]:hover {{
    color: {text_val} !important;
}}
button[data-baseweb="tab"][aria-selected="true"] {{
    color: {text_val} !important;
    background: {card_val} !important;
    border-color: {border_val} !important;
}}
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"] {{
    display: none !important;
}}
[data-baseweb="tab-list"] {{
    gap: 6px !important;
    background: {bg_subtle_val} !important;
    border: 1px solid {border_val} !important;
    border-radius: 10px !important;
    padding: 4px !important;
    margin-bottom: 1.5rem !important;
}}

/* Custom Panel Card */
.panel-card {{
    background: {card_val};
    border: 1px solid {border_val};
    border-radius: 10px;
    padding: 1.25rem 1.4rem;
    margin-bottom: 1rem;
    box-shadow: {shadow_val};
}}
.panel-card:hover {{
    border-color: {text_dim_val};
    transition: border-color 0.2s ease;
}}
.panel-title {{
    font-size: 0.9rem;
    font-weight: 700;
    color: {text_val};
    margin-bottom: 0.6rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}}

/* Metric Card */
.metric-card {{
    background: {card_val};
    border: 1px solid {border_val};
    border-radius: 10px;
    padding: 1.25rem 1.4rem;
    box-shadow: {shadow_val};
    height: 100%;
}}
.metric-label {{
    font-size: 0.78rem;
    color: {text_muted_val};
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}}
.metric-value {{
    font-size: 1.8rem;
    font-weight: 700;
    color: {text_val};
    letter-spacing: -0.03em;
    margin-top: 0.25rem;
}}
.metric-delta {{
    font-size: 0.75rem;
    font-weight: 600;
    margin-top: 0.4rem;
    padding: 2px 8px;
    border-radius: 6px;
    display: inline-flex;
    align-items: center;
    gap: 3px;
}}
.delta-up {{ color: {green_val}; background: {green_muted_val}; }}
.delta-down {{ color: {red_val}; background: {red_muted_val}; }}
.delta-warn {{ color: {amber_val}; background: {amber_muted_val}; }}

/* Chart Wrapper */
.chart-wrap {{
    background: {card_val};
    border: 1px solid {border_val};
    border-radius: 10px;
    padding: 1.2rem 1.2rem 0.6rem;
    box-shadow: {shadow_val};
    margin-bottom: 1.25rem;
}}
.chart-header-title {{
    font-size: 0.85rem;
    font-weight: 700;
    color: {text_val};
    text-transform: uppercase;
    letter-spacing: 0.05em;
}}
.chart-subtitle {{
    font-size: 0.75rem;
    color: {text_muted_val};
    margin-bottom: 0.8rem;
}}

/* Custom Data Table */
.data-table {{
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    font-size: 0.825rem;
    margin-top: 0.5rem;
}}
.data-table th {{
    text-align: left;
    padding: 0.75rem 0.85rem;
    color: {text_muted_val};
    font-weight: 600;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    border-bottom: 1px solid {border_val};
}}
.data-table td {{
    padding: 0.75rem 0.85rem;
    color: {text_val};
    border-bottom: 1px solid {border_subtle_val};
    vertical-align: middle;
}}
.data-table tr:last-child td {{
    border-bottom: none;
}}
.data-table tr:hover td {{
    background: {card_hover_val};
    transition: background 0.15s ease;
}}

/* Status Badges */
.badge {{
    display: inline-block;
    padding: 3px 8px;
    border-radius: 6px;
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
}}
.badge-green {{ color: {green_val}; background: {green_muted_val}; }}
.badge-red {{ color: {red_val}; background: {red_muted_val}; }}
.badge-amber {{ color: {amber_val}; background: {amber_muted_val}; }}
.badge-blue {{ color: #2563eb; background: rgba(37,99,235,0.1); }}

/* Brand Header */
.brand-container {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 1.25rem;
    border-bottom: 1px solid {border_val};
    margin-bottom: 1.5rem;
}}
.brand-title {{
    font-size: 1.35rem;
    font-weight: 800;
    letter-spacing: -0.02em;
    color: {text_val};
    display: flex;
    align-items: center;
    gap: 0.5rem;
}}
.brand-subtitle {{
    font-size: 0.75rem;
    color: {text_muted_val};
    font-weight: 400;
    margin-top: 0.1rem;
}}
</style>
"""
st.markdown(css, unsafe_allow_html=True)

# 4. Brand / Logo Header Row
head_left, head_right = st.columns([8, 1])
with head_left:
    st.markdown(f"""
    <div class="brand-container">
        <div>
            <div class="brand-title">⚔️ MLBB MATCH ANALYST <span class="badge badge-blue">Offline + Live Coach</span></div>
            <div class="brand-subtitle">Draft · meta BPW · replay timelines · ban/pick overlay coach</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
with head_right:
    theme_label = "☀️ Light" if IS_DARK else "🌙 Dark"
    st.button(theme_label, on_click=toggle_theme, use_container_width=True)

# 5. Initialize analyzers
# Handled gracefully with fallback relative folders
try:
    draft_anal = DraftAnalyzer()
    item_anal = ItemAnalyzer()
    hero_list = sorted(list(draft_anal.heroes_db.keys()))
    item_list = sorted(list(item_anal.items_db.keys()))
except Exception as e:
    st.error(f"Error loading game catalog assets: {e}")
    hero_list = ["Tigreal", "Gusion", "Layla", "Esmeralda", "Claude"]
    item_list = ["Athena's Shield", "Sea Halberd", "Dominance Ice", "Malefic Roar", "Blade of Despair"]

# 6. Tab Selection Navigation
tab_names = [
    "🎯 Draft & Item Analyzer",
    "📼 Replay Timeline Analyzer",
    "📊 Meta Ban / Pick / Win",
    "📱 Live Overlay Coach",
]
tab_draft, tab_replay, tab_meta, tab_overlay = st.tabs(tab_names)

# --- TAB 1: DRAFT & ITEM ANALYZER ---
with tab_draft:
    st.markdown("<p style='font-size: 0.85rem; color:#71717a; margin-top:-0.5rem; margin-bottom:1.5rem;'>Interactive draft selection scoring, synergy matching, composition check, and build counters.</p>", unsafe_allow_html=True)
    
    col_sel_left, col_sel_right = st.columns(2)
    with col_sel_left:
        st.markdown("<h4 style='font-size:0.95rem; margin-bottom:0.4rem;'>Ally Team Selection</h4>", unsafe_allow_html=True)
        allies = st.multiselect("Select Ally Heroes (Max 5)", options=hero_list, max_selections=5, key="allies_sel")
    with col_sel_right:
        st.markdown("<h4 style='font-size:0.95rem; margin-bottom:0.4rem;'>Enemy Team Selection</h4>", unsafe_allow_html=True)
        enemies = st.multiselect("Select Enemy Heroes (Max 5)", options=hero_list, max_selections=5, key="enemies_sel")

    # Run analysis
    draft_state = DraftState(allies=allies, enemies=enemies)
    analysis = draft_anal.analyze_draft(draft_state)

    st.markdown("<hr style='margin:1.5rem 0; border:0; border-top:1px solid #1e1e24;'>", unsafe_allow_html=True)

    # Scored Row of KPIs
    kpi_col1, kpi_col2, kpi_col3 = st.columns(3)
    with kpi_col1:
        # Score mapping
        score = analysis["overall_score"]
        delta_type = "up" if score >= 60 else ("down" if score < 45 else "warn")
        delta_label = "Favored" if score >= 60 else ("Unfavored" if score < 45 else "Even")
        
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Draft Strength Score</div>
            <div class="metric-value">{score}%</div>
            <div class="metric-delta delta-{delta_type}">⚔️ {delta_label}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with kpi_col2:
        syn_score = analysis["synergy_score"]
        syn_delta = "High Cohesion" if syn_score >= 70 else ("Needs Synergy" if syn_score < 40 else "Moderate")
        syn_type = "up" if syn_score >= 70 else ("down" if syn_score < 40 else "warn")
        
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Team Synergy Rating</div>
            <div class="metric-value">{syn_score}%</div>
            <div class="metric-delta delta-{syn_type}">⚡ {syn_delta}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with kpi_col3:
        cnt_score = analysis["counter_score"]
        cnt_delta = "Strong Counter" if cnt_score >= 60 else ("Countered" if cnt_score < 45 else "Neutral Match")
        cnt_type = "up" if cnt_score >= 60 else ("down" if cnt_score < 45 else "warn")
        
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Lane Matchup / Counter Score</div>
            <div class="metric-value">{cnt_score}%</div>
            <div class="metric-delta delta-{cnt_type}">🛡️ {cnt_delta}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height: 1.25rem;'></div>", unsafe_allow_html=True)

    # Detailed Panels
    col_panels_left, col_panels_right = st.columns(2)
    with col_panels_left:
        # Suggested Win Condition Card
        st.markdown(f"""
        <div class="panel-card" style="height:100%;">
            <div class="panel-title">💡 SUGGESTED WIN CONDITION</div>
            <div style="font-size:0.875rem; line-height:1.45; color:{text_val}; font-weight: 500;">
                {analysis["win_condition"]}
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_panels_right:
        # Composition Gaps Card
        gap_items = ""
        gaps_list = analysis["gaps"]
        if gaps_list:
            for g in gaps_list:
                gap_items += f"<li style='margin-bottom:0.35rem;'>⚠️ {g}</li>"
        else:
            gap_items = f"<li style='color:{green_val}; list-style-type:none;'>✓ Team composition is well-balanced. No gaps detected!</li>"

        st.markdown(f"""
        <div class="panel-card" style="height:100%;">
            <div class="panel-title">⚠️ COMPOSITION CRITIQUE & GAPS</div>
            <ul style="font-size:0.825rem; color:{text_val}; margin-left:-0.75rem; line-height:1.4;">
                {gap_items}
            </ul>
        </div>
        """, unsafe_allow_html=True)

    # Detailed Breakdown Table/Lists
    st.markdown("<div style='height:1.25rem;'></div>", unsafe_allow_html=True)
    st.markdown("<h4 style='font-size:0.95rem; margin-bottom:0.5rem;'>Analytical Breakdown Details</h4>", unsafe_allow_html=True)
    
    col_break_left, col_break_right = st.columns(2)
    with col_break_left:
        st.markdown("<p style='font-size:0.75rem; color:#71717a; text-transform:uppercase; letter-spacing:0.04em; font-weight:600;'>Synergy Connections</p>", unsafe_allow_html=True)
        syn_details = analysis["synergy_details"]
        if syn_details:
            rows_html = "".join([f"<tr><td>⚡</td><td>{d}</td><td><span class='badge badge-green'>Active</span></td></tr>" for d in syn_details])
        else:
            rows_html = "<tr><td colspan='3' style='text-align:center; color:#71717a;'>No significant synergy matchups detected among selected heroes.</td></tr>"
            
        st.markdown(f"""
        <table class="data-table">
            <thead>
                <tr>
                    <th style="width:10%;">Icon</th>
                    <th style="width:70%;">Description</th>
                    <th style="width:20%;">Status</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
        """, unsafe_allow_html=True)

    with col_break_right:
        st.markdown("<p style='font-size:0.75rem; color:#71717a; text-transform:uppercase; letter-spacing:0.04em; font-weight:600;'>Counter Matchups</p>", unsafe_allow_html=True)
        cnt_details = analysis["counter_details"]
        if cnt_details:
            rows_html = ""
            for d in cnt_details:
                badge_class = "badge-green" if "Ally" in d else "badge-red"
                badge_text = "Advantage" if "Ally" in d else "Threat"
                rows_html += f"<tr><td>🛡️</td><td>{d}</td><td><span class='badge {badge_class}'>{badge_text}</span></td></tr>"
        else:
            rows_html = "<tr><td colspan='3' style='text-align:center; color:#71717a;'>No direct counter relationships detected in selected matchup.</td></tr>"
            
        st.markdown(f"""
        <table class="data-table">
            <thead>
                <tr>
                    <th style="width:10%;">Icon</th>
                    <th style="width:70%;">Description</th>
                    <th style="width:20%;">Type</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
        """, unsafe_allow_html=True)

    # Item Build Recommendations
    st.markdown("<hr style='margin:2rem 0 1.5rem; border:0; border-top:1px solid #1e1e24;'>", unsafe_allow_html=True)
    st.markdown("<h4 style='font-size:1rem; font-weight:700;'>🛡️ DYNAMIC COUNTER-ITEM RECOMMENDATIONS</h4>", unsafe_allow_html=True)
    st.markdown("<p style='font-size:0.8rem; color:#71717a; margin-top:-0.4rem;'>Select active items bought by the enemy team to receive dynamic build counters.</p>", unsafe_allow_html=True)

    col_build_left, col_build_right = st.columns([1, 2])
    with col_build_left:
        active_enemy_hero = st.selectbox("Select Enemy Threat Hero", options=enemies if enemies else hero_list, index=0)
        active_enemy_items = st.multiselect("Select Active Enemy Items", options=item_list, key="enemy_items_sel")
    
    with col_build_right:
        st.markdown("<p style='font-size:0.75rem; color:#71717a; text-transform:uppercase; letter-spacing:0.04em; font-weight:600;'>Recommended Counter Items</p>", unsafe_allow_html=True)
        # Process recommendations
        recs = item_anal.suggest_counters(enemy_heroes=[active_enemy_hero] if active_enemy_hero else [], enemy_items=active_enemy_items)
        if recs:
            rows_html = ""
            for r in recs:
                badge_class = "badge-red" if r["priority"] == "High" else "badge-amber"
                stats_str = ", ".join([f"{k.replace('_', ' ').title()}: {v}" for k, v in r["stats"].items()])
                rows_html += f"""
                <tr>
                    <td style="font-weight:700;">{r["recommended_item"]}</td>
                    <td><span class="badge {badge_class}">{r["priority"]}</span></td>
                    <td style="font-size:0.75rem; color:#a1a1aa;">{stats_str}</td>
                    <td>{r["reason"]}</td>
                    <td style="text-align:right; font-weight:600;">{r["price"]}g</td>
                </tr>
                """
        else:
            rows_html = "<tr><td colspan='5' style='text-align:center; color:#71717a; padding:1.5rem;'>No counter item recommendations triggered. Check if enemy heroes or items warrant counter builds.</td></tr>"

        st.markdown(f"""
        <table class="data-table">
            <thead>
                <tr>
                    <th style="width:20%;">Counter Item</th>
                    <th style="width:10%;">Priority</th>
                    <th style="width:25%;">Stats Provided</th>
                    <th style="width:35%;">Tactical Rationale</th>
                    <th style="width:10%; text-align:right;">Price</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
        """, unsafe_allow_html=True)


# --- TAB 2: REPLAY TIMELINE ---
with tab_replay:
    st.markdown(
        "<p style='font-size: 0.85rem; color:#71717a; margin-top:-0.5rem; margin-bottom:1.5rem;'>"
        f"Load a local replay from <code>test/videos/</code> or upload an MP4 (max {MAX_UPLOAD_MB} MB). "
        "Simulation Mode still works for an instant demo."
        "</p>",
        unsafe_allow_html=True,
    )
    
    col_vid_left, col_vid_right = st.columns([2, 1])
    
    with col_vid_left:
        video_input_type = st.radio(
            "Select Input Mode",
            options=[
                "Run Match Simulation (Recommended / Instant Demo)",
                "Load from test/videos folder",
                "Upload Replay File (.mp4)",
            ],
            horizontal=False,
        )
        
        uploaded_file_path = None
        if video_input_type == "Load from test/videos folder":
            videos = list_test_videos()
            if not videos:
                st.warning(
                    f"No `.mp4` files found in `{TEST_VIDEOS_DIR}`. "
                    "Drop a replay there and refresh."
                )
            else:
                chosen = st.selectbox("Choose test video", options=videos, key="test_video_sel")
                candidate = os.path.join(TEST_VIDEOS_DIR, chosen)
                size_mb = os.path.getsize(candidate) / (1024 * 1024)
                st.caption(f"Selected: {chosen} ({size_mb:.1f} MB)")
                if size_mb > MAX_UPLOAD_MB:
                    st.error(f"File exceeds {MAX_UPLOAD_MB} MB test limit.")
                else:
                    uploaded_file_path = candidate
                    st.success(f"Ready: {chosen}")
        elif video_input_type == "Upload Replay File (.mp4)":
            uploaded_file = st.file_uploader(
                f"Upload Replay Video (.mp4, max {MAX_UPLOAD_MB} MB)",
                type=["mp4"],
            )
            if uploaded_file:
                size_mb = uploaded_file.size / (1024 * 1024)
                if size_mb > MAX_UPLOAD_MB:
                    st.error(
                        f"Upload is {size_mb:.1f} MB — limit is {MAX_UPLOAD_MB} MB "
                        "(see `.streamlit/config.toml`)."
                    )
                else:
                    temp_dir = os.path.join(os.getcwd(), "scratch")
                    os.makedirs(temp_dir, exist_ok=True)
                    uploaded_file_path = os.path.join(temp_dir, uploaded_file.name)
                    with open(uploaded_file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    st.success(f"Video uploaded: {uploaded_file.name} ({size_mb:.1f} MB)")
        else:
            uploaded_file_path = "simulated_match.mp4"  # Triggers simulation fallback path
            
        sample_interval = st.slider("Frame Sampling Interval (seconds)", min_value=1, max_value=30, value=5)
        
    with col_vid_right:
        st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)
        # Start processing button
        process_btn = st.button("🚀 Process Replay & Analyze", use_container_width=True, type="primary")

    if process_btn and uploaded_file_path:
        st.markdown("<hr style='margin:1.5rem 0; border:0; border-top:1px solid #1e1e24;'>", unsafe_allow_html=True)
        progress_bar = st.progress(0.0)
        progress_text = st.empty()
        
        def update_progress(val):
            progress_bar.progress(val)
            progress_text.text(f"Extracting frame metrics... {int(val * 100)}% complete")

        # Process the video
        # If simulation, runs instantly and mocks OCR/template-match. If real video, processes frame by frame
        # Set use_mock_vision if running simulated_match
        use_mock = (uploaded_file_path == "simulated_match.mp4")
        
        processor = ReplayProcessor(use_mock_vision=use_mock)
        timeline = processor.process_video(uploaded_file_path, sample_interval_seconds=sample_interval, progress_callback=update_progress)
        
        progress_bar.progress(1.0)
        progress_text.text("Analysis Complete! Generating visual dashboard...")
        
        # Store timeline in session state to persist between page interactions
        st.session_state["active_timeline"] = timeline

    # Render results if timeline is in session state
    if "active_timeline" in st.session_state:
        timeline: MatchTimeline = st.session_state["active_timeline"]
        
        st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)
        
        # Summary Row of KPIs
        sum_c1, sum_c2, sum_c3, sum_c4 = st.columns(4)
        
        gold_lead = timeline.ally_total_gold - timeline.enemy_total_gold
        lead_label = "Ally Gold Lead" if gold_lead >= 0 else "Enemy Gold Lead"
        lead_delta_type = "up" if gold_lead >= 0 else "down"
        lead_arrow = "+" if gold_lead >= 0 else ""
        
        with sum_c1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Game Time</div>
                <div class="metric-value">{timeline.gold_diff_history[-1]["timestamp"] if timeline.gold_diff_history else "00:00"}</div>
            </div>
            """, unsafe_allow_html=True)
        with sum_c2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Ally KDA</div>
                <div class="metric-value">{timeline.ally_kda}</div>
            </div>
            """, unsafe_allow_html=True)
        with sum_c3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Total Gold (Ally/Enemy)</div>
                <div class="metric-value">{timeline.ally_total_gold:,} / {timeline.enemy_total_gold:,}</div>
            </div>
            """, unsafe_allow_html=True)
        with sum_c4:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">{lead_label}</div>
                <div class="metric-value">{lead_arrow}{gold_lead:,}</div>
                <div class="metric-delta delta-{lead_delta_type}">💰 {lead_arrow}{gold_lead:,}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)

        # Plotly Gold Difference Timeline Chart
        df = pd.DataFrame(timeline.gold_diff_history)
        if not df.empty:
            fig = go.Figure()
            # Draw line for gold difference
            fig.add_trace(go.Scatter(
                x=df["timestamp"],
                y=df["gold_diff"],
                mode="lines",
                name="Gold Difference (Ally - Enemy)",
                line=dict(color="#2563eb", width=3),
                fill="tozeroy",
                fillcolor="rgba(37,99,235,0.06)" if gold_lead >= 0 else "rgba(220,38,38,0.06)"
            ))
            # Reference zero line
            fig.add_hline(y=0, line_dash="dash", line_color="#71717a", opacity=0.5)

            # Theme Plotly chart based on active standard layout rules
            font_color = "#fafafa" if IS_DARK else "#09090b"
            grid_color = "rgba(255,255,255,0.06)" if IS_DARK else "rgba(0,0,0,0.06)"
            
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="DM Sans, sans-serif", color=font_color, size=11),
                margin=dict(l=0, r=0, t=10, b=0),
                height=260,
                xaxis=dict(
                    gridcolor=grid_color,
                    zerolinecolor=grid_color,
                    tickfont=dict(size=10, color=font_color),
                ),
                yaxis=dict(
                    gridcolor=grid_color,
                    zerolinecolor=grid_color,
                    tickfont=dict(size=10, color=font_color),
                ),
            )
            
            # Wrap chart in card
            st.markdown("""
            <div class="chart-wrap">
                <div class="chart-header-title">📊 Team Gold Advantage Timeline</div>
                <div class="chart-subtitle">Analyzed economy difference curve (positive indicates ally advantage, negative indicates enemy advantage)</div>
            """, unsafe_allow_html=True)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            st.markdown("</div>", unsafe_allow_html=True)

        # Commentary Event Log
        st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)
        st.markdown("<h4 style='font-size:0.95rem; margin-bottom:0.5rem;'>📝 Match Event Commentary Timeline</h4>", unsafe_allow_html=True)
        
        if timeline.events:
            rows_html = ""
            for event in timeline.events:
                # Severity-specific badges
                if event.severity == "critical":
                    badge_html = "<span class='badge badge-red'>Critical</span>"
                elif event.severity == "warning":
                    badge_html = "<span class='badge badge-amber'>Warning</span>"
                else:
                    badge_html = "<span class='badge badge-green'>Info</span>"
                    
                # Type indicator emoji
                icon = "📦"
                if event.event_type == "objective":
                    icon = "🐢"
                elif event.event_type == "gold":
                    icon = "💰"
                elif event.event_type == "kda":
                    icon = "☠️"
                elif event.event_type == "item_buy":
                    icon = "⚔️"
                    
                rows_html += f"""
                <tr>
                    <td style="font-weight:700; font-family:'JetBrains Mono', monospace;">{event.timestamp}</td>
                    <td>{icon} {event.event_type.upper()}</td>
                    <td>{badge_html}</td>
                    <td>{event.text}</td>
                </tr>
                """
        else:
            rows_html = "<tr><td colspan='4' style='text-align:center; color:#71717a; padding:1.5rem;'>No commentary events generated for this match timeline yet.</td></tr>"

        st.markdown(f"""
        <table class="data-table">
            <thead>
                <tr>
                    <th style="width:10%;">Time</th>
                    <th style="width:15%;">Category</th>
                    <th style="width:15%;">Severity</th>
                    <th style="width:60%;">Tactical Commentary & Alerts</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
        """, unsafe_allow_html=True)

        # JSON Timeline Downloader
        st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)
        
        # Prepare JSON string
        timeline_dict = {
            "ally_total_gold": timeline.ally_total_gold,
            "enemy_total_gold": timeline.enemy_total_gold,
            "gold_difference": timeline.ally_total_gold - timeline.enemy_total_gold,
            "ally_kda": timeline.ally_kda,
            "gold_diff_history": timeline.gold_diff_history,
            "events": [
                {
                    "timestamp": e.timestamp,
                    "event_type": e.event_type,
                    "text": e.text,
                    "severity": e.severity
                }
                for e in timeline.events
            ]
        }
        json_str = json.dumps(timeline_dict, indent=2)
        
        st.download_button(
            label="💾 Download Timeline JSON Report",
            data=json_str,
            file_name="mlbb_timeline_report.json",
            mime="application/json",
            use_container_width=True
        )

# --- TAB 3: META BAN / PICK / WIN ---
with tab_meta:
    st.markdown(
        "<p style='font-size: 0.85rem; color:#71717a; margin-top:-0.5rem; margin-bottom:1.5rem;'>"
        "Offline Ban / Pick / Win rates from Liquipedia tournament game logs. "
        "Default filter matches the notebook example: M5 World Championship, bracket stage."
        "</p>",
        unsafe_allow_html=True,
    )

    try:
        meta_anal = get_meta_analyzer()
        tournaments_df = meta_anal.list_tournaments()
    except Exception as e:
        st.error(f"Could not load tournament meta datasets: {e}")
        tournaments_df = pd.DataFrame()

    if not tournaments_df.empty:
        tournaments_df = tournaments_df.copy()
        tournaments_df["label"] = tournaments_df.apply(
            lambda r: f"{r['tournament_code']} — {r['tournament_name']} ({r['tier']})",
            axis=1,
        )
        label_to_code = dict(
            zip(tournaments_df["label"], tournaments_df["tournament_code"].astype(str))
        )
        default_labels = [
            label
            for label, code in label_to_code.items()
            if str(code) == "1"
        ]

        f1, f2, f3 = st.columns([2, 1, 1])
        with f1:
            selected_labels = st.multiselect(
                "Tournaments",
                options=list(label_to_code.keys()),
                default=default_labels or list(label_to_code.keys())[:1],
                key="meta_tournaments",
            )
        with f2:
            tier_options = sorted(
                [t for t in tournaments_df["tier"].dropna().unique().tolist() if t]
            )
            selected_tiers = st.multiselect(
                "Tiers (optional)",
                options=tier_options,
                default=[],
                key="meta_tiers",
            )
        with f3:
            stage_choice = st.selectbox(
                "Stage",
                options=["Bracket only", "All stages"],
                index=0,
                key="meta_stage",
            )

        d1, d2, d3 = st.columns([1, 1, 1])
        with d1:
            use_dates = st.checkbox("Filter by tournament date range", value=False, key="meta_use_dates")
        with d2:
            start_date = st.date_input("Tournament start on/after", key="meta_start")
        with d3:
            end_date = st.date_input("Tournament end on/before", key="meta_end")

        run_meta = st.button("📈 Compute BPW Table", type="primary", use_container_width=True)
        auto_run = "meta_bpw_table" not in st.session_state

        if run_meta or auto_run or "meta_bpw_table" in st.session_state:
            if run_meta or auto_run:
                codes = tuple(label_to_code[label] for label in selected_labels)
                tiers = tuple(selected_tiers) if selected_tiers else None
                stages = "b" if stage_choice == "Bracket only" else None
                start_int = (
                    int(start_date.strftime("%Y%m%d"))
                    if use_dates and start_date is not None
                    else None
                )
                end_int = (
                    int(end_date.strftime("%Y%m%d"))
                    if use_dates and end_date is not None
                    else None
                )

                with st.spinner("Computing ban / pick / win rates across filtered games..."):
                    num_games, table = run_meta_bpw(
                        codes, tiers, stages, start_int, end_int
                    )
                st.session_state["meta_bpw_num_games"] = num_games
                st.session_state["meta_bpw_table"] = table

            num_games = st.session_state.get("meta_bpw_num_games", 0)
            table: pd.DataFrame = st.session_state.get("meta_bpw_table", pd.DataFrame())

            st.markdown("<hr style='margin:1.5rem 0; border:0; border-top:1px solid #1e1e24;'>", unsafe_allow_html=True)

            if num_games == 0 or table.empty:
                st.warning("No games matched these filters. Broaden tournaments, tiers, or stage.")
            else:
                active = table[table["full_bp_num"] > 0].copy()
                top_ban = active.sort_values("full_ban_rate", ascending=False).head(1)
                top_pick = active.sort_values("full_pick_rate", ascending=False).head(1)
                top_wr = active[active["full_pick_num"] >= 3].sort_values(
                    "full_win_rate", ascending=False
                ).head(1)

                k1, k2, k3, k4 = st.columns(4)
                with k1:
                    st.markdown(
                        f"""
                        <div class="metric-card">
                            <div class="metric-label">Games Analyzed</div>
                            <div class="metric-value">{num_games}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with k2:
                    ban_name = top_ban["hero_name"].iloc[0] if not top_ban.empty else "—"
                    ban_rate = f"{top_ban['full_ban_rate'].iloc[0]*100:.1f}%" if not top_ban.empty else "—"
                    st.markdown(
                        f"""
                        <div class="metric-card">
                            <div class="metric-label">Highest Ban Rate</div>
                            <div class="metric-value">{ban_rate}</div>
                            <div class="metric-delta delta-warn">{ban_name}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with k3:
                    pick_name = top_pick["hero_name"].iloc[0] if not top_pick.empty else "—"
                    pick_rate = f"{top_pick['full_pick_rate'].iloc[0]*100:.1f}%" if not top_pick.empty else "—"
                    st.markdown(
                        f"""
                        <div class="metric-card">
                            <div class="metric-label">Highest Pick Rate</div>
                            <div class="metric-value">{pick_rate}</div>
                            <div class="metric-delta delta-up">{pick_name}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with k4:
                    wr_name = top_wr["hero_name"].iloc[0] if not top_wr.empty else "—"
                    wr_rate = f"{top_wr['full_win_rate'].iloc[0]*100:.1f}%" if not top_wr.empty else "—"
                    st.markdown(
                        f"""
                        <div class="metric-card">
                            <div class="metric-label">Highest Win Rate (min 3 picks)</div>
                            <div class="metric-value">{wr_rate}</div>
                            <div class="metric-delta delta-up">{wr_name}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                st.markdown("<div style='height: 1.25rem;'></div>", unsafe_allow_html=True)

                chart_metric = st.selectbox(
                    "Chart metric",
                    options=["full_ban_rate", "full_pick_rate", "full_win_rate", "full_bp_rate"],
                    format_func=lambda m: {
                        "full_ban_rate": "Ban Rate",
                        "full_pick_rate": "Pick Rate",
                        "full_win_rate": "Win Rate",
                        "full_bp_rate": "Ban+Pick Presence",
                    }[m],
                    key="meta_chart_metric",
                )
                chart_df = active.sort_values(chart_metric, ascending=False).head(15)
                if not chart_df.empty:
                    font_color = "#fafafa" if IS_DARK else "#09090b"
                    grid_color = "rgba(255,255,255,0.06)" if IS_DARK else "rgba(0,0,0,0.06)"
                    fig_meta = go.Figure(
                        data=[
                            go.Bar(
                                x=chart_df["hero_name"],
                                y=chart_df[chart_metric],
                                marker_color="#2563eb",
                            )
                        ]
                    )
                    fig_meta.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font=dict(family="DM Sans, sans-serif", color=font_color, size=11),
                        margin=dict(l=0, r=0, t=10, b=0),
                        height=320,
                        yaxis=dict(
                            tickformat=".0%",
                            gridcolor=grid_color,
                            zerolinecolor=grid_color,
                        ),
                        xaxis=dict(gridcolor=grid_color, tickangle=-35),
                    )
                    st.markdown(
                        """
                        <div class="chart-wrap">
                            <div class="chart-header-title">Top Heroes by Selected Meta Metric</div>
                            <div class="chart-subtitle">Rates are computed only over games that match the tournament filters above</div>
                        """,
                        unsafe_allow_html=True,
                    )
                    st.plotly_chart(fig_meta, use_container_width=True, config={"displayModeBar": False})
                    st.markdown("</div>", unsafe_allow_html=True)

                display_cols = [
                    "hero_name",
                    "full_ban_num",
                    "full_ban_rate",
                    "full_pick_num",
                    "full_pick_rate",
                    "full_bp_rate",
                    "full_win_num",
                    "full_lose_num",
                    "full_win_rate",
                    "full_win_avg_game_time_sec",
                    "mpnt_team_name",
                    "mwrt_team_name",
                ]
                show_df = active[display_cols].copy()
                for rate_col in ("full_ban_rate", "full_pick_rate", "full_bp_rate", "full_win_rate"):
                    show_df[rate_col] = (show_df[rate_col] * 100).round(1)
                show_df = show_df.rename(
                    columns={
                        "hero_name": "Hero",
                        "full_ban_num": "Bans",
                        "full_ban_rate": "Ban %",
                        "full_pick_num": "Picks",
                        "full_pick_rate": "Pick %",
                        "full_bp_rate": "BP %",
                        "full_win_num": "Wins",
                        "full_lose_num": "Losses",
                        "full_win_rate": "Win %",
                        "full_win_avg_game_time_sec": "Avg Win Time (s)",
                        "mpnt_team_name": "Most Picks Team",
                        "mwrt_team_name": "Highest WR Team",
                    }
                )
                st.markdown("<h4 style='font-size:0.95rem; margin:1rem 0 0.5rem;'>Hero BPW Table</h4>", unsafe_allow_html=True)
                st.dataframe(show_df, use_container_width=True, hide_index=True)

                csv_bytes = show_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="💾 Download BPW CSV",
                    data=csv_bytes,
                    file_name="hero_bpw_table.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

# --- TAB 4: LIVE OVERLAY COACH ---
with tab_overlay:
    st.markdown(
        "<p style='font-size: 0.85rem; color:#71717a; margin-top:-0.5rem; margin-bottom:1.5rem;'>"
        "Desktop preview of an MLBB live overlay coach: ban priorities, pick suggestions with synergy/counter reasons, "
        "and counter-item calls for the enemy draft. Android MediaProjection overlay is Phase 2 — this tab reuses the same advice engine."
        "</p>",
        unsafe_allow_html=True,
    )

    try:
        coach = get_live_coach()
    except Exception as e:
        st.error(f"Could not load live coach: {e}")
        coach = None

    if coach is not None:
        rank_meta = coach.rank_meta or {}
        st.caption(
            f"Rank snapshot source: {rank_meta.get('source', 'missing')} · "
            f"updated: {rank_meta.get('updated_at', 'run scripts/fetch_rank_meta.py')}"
        )

        o1, o2, o3 = st.columns(3)
        with o1:
            ov_allies = st.multiselect(
                "Your team picks",
                options=hero_list,
                max_selections=5,
                key="ov_allies",
            )
        with o2:
            ov_enemies = st.multiselect(
                "Enemy picks",
                options=hero_list,
                max_selections=5,
                key="ov_enemies",
            )
        with o3:
            ov_banned = st.multiselect(
                "Already banned",
                options=hero_list,
                max_selections=10,
                key="ov_banned",
            )

        ov_items = st.multiselect(
            "Enemy items (optional)",
            options=item_list,
            key="ov_items",
        )

        advice = coach.advise(
            allies=ov_allies,
            enemies=ov_enemies,
            banned=ov_banned,
            enemy_items=ov_items,
        )

        # Overlay-styled panels
        st.markdown(
            f"""
            <div class="panel-card" style="border-color:#2563eb;">
              <div style="font-size:0.75rem; letter-spacing:0.08em; text-transform:uppercase; color:#71717a;">Live Overlay · Draft Phase</div>
              <div style="display:flex; gap:1.5rem; flex-wrap:wrap; margin-top:0.75rem;">
                <div><strong>Ally</strong>: {', '.join(ov_allies) or '—'}</div>
                <div><strong>Enemy</strong>: {', '.join(ov_enemies) or '—'}</div>
                <div><strong>Banned</strong>: {', '.join(ov_banned) or '—'}</div>
              </div>
              <div style="margin-top:0.75rem; font-size:0.9rem;">
                Draft strength <strong>{advice['draft']['overall_score']}%</strong>
                · Synergy <strong>{advice['draft']['synergy_score']}%</strong>
                · Matchup <strong>{advice['draft']['counter_score']}%</strong>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        bcol, pcol = st.columns(2)
        with bcol:
            st.markdown("<h4 style='font-size:0.95rem;'>Ban recommendations</h4>", unsafe_allow_html=True)
            ban_df = pd.DataFrame(advice["ban_recommendations"])
            if ban_df.empty:
                st.info("No ban candidates.")
            else:
                show_ban = ban_df[["hero", "role", "ban_rate", "pick_rate", "win_rate", "reason"]].copy()
                for c in ("ban_rate", "pick_rate", "win_rate"):
                    show_ban[c] = (show_ban[c] * 100).round(1)
                st.dataframe(show_ban, use_container_width=True, hide_index=True)

        with pcol:
            st.markdown("<h4 style='font-size:0.95rem;'>Pick recommendations</h4>", unsafe_allow_html=True)
            pick_df = pd.DataFrame(advice["pick_recommendations"])
            if pick_df.empty:
                st.info("No pick candidates.")
            else:
                show_pick = pick_df[["hero", "role", "win_rate", "pick_rate", "reason"]].copy()
                for c in ("win_rate", "pick_rate"):
                    show_pick[c] = (show_pick[c] * 100).round(1)
                st.dataframe(show_pick, use_container_width=True, hide_index=True)

        st.markdown("<h4 style='font-size:0.95rem; margin-top:1rem;'>Synergy / matchup notes</h4>", unsafe_allow_html=True)
        notes = advice["draft"].get("synergy_details", []) + advice["draft"].get("counter_details", [])
        if notes:
            for note in notes[:12]:
                st.markdown(f"- {note}")
        else:
            st.caption("Pick allies/enemies to see synergy and counter callouts.")

        gaps = advice["draft"].get("gaps") or []
        if gaps:
            st.markdown("<h4 style='font-size:0.95rem;'>Composition gaps</h4>", unsafe_allow_html=True)
            for gap in gaps:
                st.markdown(f"- {gap}")

        st.markdown("<h4 style='font-size:0.95rem; margin-top:1rem;'>Counter items vs enemy</h4>", unsafe_allow_html=True)
        item_recs = advice.get("item_recommendations") or []
        if not ov_enemies and not ov_items:
            st.caption("Select enemy heroes (and optional items) for counter builds.")
        elif not item_recs:
            st.info("No strong counter-item matches for this enemy set.")
        else:
            item_df = pd.DataFrame(item_recs)[["recommended_item", "priority", "price", "reason"]]
            st.dataframe(item_df, use_container_width=True, hide_index=True)

        st.markdown(
            "<p style='font-size:0.8rem; color:#71717a; margin-top:1rem;'>"
            "Refresh meta: <code>.\\.venv\\Scripts\\python.exe scripts\\fetch_rank_meta.py</code> "
            "· Official UI reference: "
            "<a href='https://www.mobilelegends.com/rank' target='_blank'>mobilelegends.com/rank</a>"
            "</p>",
            unsafe_allow_html=True,
        )

