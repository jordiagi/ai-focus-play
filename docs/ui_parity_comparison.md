# Veo Web App vs. Local UI: Comprehensive Parity & Feature Comparison

Date: 2026-09-24  
Target URL (Veo): `https://app.veo.co/matches/20260913-arlington-sa-u16b-ecnl-26-27-vs-skyline-u16b-ecnl-v7228589/`  
Local URL: `http://127.0.0.1:5173/`  
Video Footprint: Arlington SA U16B ECNL (26-27) vs Skyline U16B ECNL (Sep 13, 2026)

---

## 1. Executive Summary

A systematic, live browser-based audit comparing the official Veo platform (`app.veo.co`) with the local analysis platform (`localhost:5173`) was conducted using `browser-harness` across all 6 core drawers and navigation workflows.

Overall, the local UI achieves **structural parity** with Veo's drawer architecture, timeline controls, hotkeys, and color schemes, while adhering to the **Honesty Policy** (zero fabricated literals; empty state `—` with measured defect citations for uncomputed statistics). Furthermore, inspection of the Veo API and CDN responses has unlocked exact camera calibration matrices (`.veo`), tracking trajectories (`.det`), and dual video feeds (1080p standard broadcast + 2048x2048 panorama).

---

## 2. Drawer-by-Drawer Side-by-Side Comparison

### 2.1 Analytics Studio (`#/analysis/`)

| Component / Feature | Veo Web UI (`app.veo.co`) | Local Web UI (`127.0.0.1:5173`) | Parity Status & Analysis |
| :--- | :--- | :--- | :--- |
| **Top Summary Cards** | 3 KPI cards: Goals (3, +1 diff), Shots (9, -5 diff), Possession % (62%, -1% diff) | Direct transition to Stats table | **Feature Gap**: Local UI lacks top delta cards compared to previous match. |
| **Stats Accordion** | 13 rows: Goal, Shot, Total attempts, Corner, Free kick, Throw-in, Foul, Penalty, Tackle, Passes completed, Possession %, Possession minutes, Possession won. | Exactly all 13 rows rendered with Home vs. Away columns. | **Full Structural Parity**. Local UI renders computed metrics (Goals, Shots, Possession) and properly dims uncomputed metrics (`—`) with tooltip explanations. |
| **Team Toggles in Accordions** | Each accordion has dedicated team toggle buttons (ARL crest vs SKY) | Global `Swap Teams` button; individual accordions default to home | **UX Gap**: Veo allows independent per-section team switching. |
| **Shot Map** | SVG pitch, 12 ARL markers / 13 SKY markers with tooltips ("Goal at 02:43"), 8 conversion stats | SVG pitch with circular markers colored by outcome, seek on click, conversion % | **Partial Parity**: Local pitch renders markers and seeks on click; missing inside/outside box conversion breakdown cards. |
| **Pass Location** | 3-thirds horizontal bars (Defensive 7%, Middle 83%, Attacking 10%) on pitch graphic with play direction arrow | `ThirdsBar` component rendering Defensive, Middle, Attacking | **Substantial Parity**: Component logic matches; pitch background graphic is simplified in local. |
| **Possession Location** | 3-thirds breakdown (ARL: 49% Def, 34% Mid, 17% Att; SKY: 33% Def, 44% Mid, 23% Att) | `ThirdsBar` component rendering Defensive, Middle, Attacking | **Substantial Parity**. |
| **Pass Strings** | Summary metrics (3-5 passes: 26, 6+ passes: 9, Longest string: 11) + 8-bar histogram (3, 4, 5, 6, 7, 8, 9, 10+) | Bar chart rendering sequence lengths 3 to 10+ | **Partial Parity**: Local UI has bar chart; needs top summary count containers (3-5, 6+, Longest). |
| **Heat Map** | 2D density heatmap image (`blob:`), period selector, interval time sliders | Displays explicit `Unavailable` banner citing measured defect (lack of real-world metric calibration) | **Intentional Honesty State**: Heatmap is intentionally dimmed until metric pitch calibration is achieved. |

---

### 2.2 Highlights Drawer (`#/highlights/`)

| Feature | Veo Web UI | Local Web UI | Status |
| :--- | :--- | :--- | :--- |
| **Header** | Highlights count, "Play all" button | Highlights count, "Play all" button | **Full Parity** |
| **Quick Filters** | All, Goals, Shots, By me | All, Goals, Shots | **Minor Gap**: "By me" (user clips) not present in local read-only mode |
| **Clip Cards** | Thumbnail preview, Duration/Time, Title, Event Type, Jersey badge (#), AI badge | Thumbnail preview, Timestamp, Title, Event Type, Jersey badge (#), AI badge | **Full Parity** |
| **Active Playback Highlight** | Card highlights green when playhead is within clip range | Card highlights with green border and glow (`#00E676`) | **Full Parity** |

---

### 2.3 Events Chronology (`#/events/`)

| Feature | Veo Web UI | Local Web UI | Status |
| :--- | :--- | :--- | :--- |
| **Event Timeline** | 447 chronological events across 1st & 2nd periods | Timeline events partitioned by 1st / 2nd Half with click-to-seek | **Substantial Parity** |
| **Event Types** | 14 fine-grained types (Pass, Tackle, Interception, Kickoff, Goal, Shot, Foul, etc.) | Detected events (Goal, Shot, Kickoff) | **Data Scale Gap**: ML pipeline detects major macroscopic events; micro-events require fine-grained action classification models. |
| **Capability Governance** | None (silently omits unattempted events) | Explicit "Event Detection Capabilities" table displaying detected counts, unavailable reasons, and not attempted states | **Local UI Advantage**: Transparent engineering introspection. |

---

### 2.4 Lineup & Tactics (`#/lineup/`)

| Feature | Veo Web UI | Local Web UI | Status |
| :--- | :--- | :--- | :--- |
| **Formation Tab** | Interactive formation diagram (e.g. 4-3-3), Captain selector, Player of Match selector | Starting XI + Substitutes table with Captain/MOTM badges, Position, and Minutes Played | **Different UX Paradigm**: Veo uses pitch diagram; local uses tabular roster list. |
| **Roster Tab** | 16 players with initials avatars, names, jersey assignment buttons | Integrated in lineup table with jersey numbers and minutes | **Substantial Parity**: All 16 players represented. |

---

### 2.5 Player Moments (`#/player-moments/`)

| Feature | Veo Web UI | Local Web UI | Status |
| :--- | :--- | :--- | :--- |
| **Player Selection** | Dropdown / modal in right-hand drawer | Bottom persistent jersey carousel (`ALL`, `GK`, `1`, `2`, `4`...) | **Local UI Advantage**: Quick 1-click filtering directly beneath video player. |
| **Filtered Moments** | Shows clips and total minutes for selected player | Filters highlights list to chosen player jersey and highlights radar trails | **Full Parity** |

---

### 2.6 Summary & Notes (`#/summary/`)

| Feature | Veo Web UI | Local Web UI | Status |
| :--- | :--- | :--- | :--- |
| **Header & Score** | Match title, Date, Views count, Home/Away team crests, Score (3-3) | Match title, Date, Views count, Score (3-3), Teams | **Full Parity** |
| **Coach's Journal** | Editable notes textarea (visible to team only) | Editable notes textarea with auto-save | **Full Parity** |

---

## 3. Video Player & Interactive Controls

| Control | Veo Web UI | Local Web UI | Notes |
| :--- | :--- | :--- | :--- |
| **Camera Modes** | Follow-cam, Interactive / Panoramic cam | Follow-Cam, Pan & Zoom (custom virtual pan/tilt) | **Full Parity** |
| **Telestrator** | Drawing tools, laser, spot spotlight | Full HTML5 Canvas telestrator with Hotkey (D), shapes, lines | **Full Parity** |
| **Minimap / Radar** | 2D radar view overlay | Interactive 2D Pitch Radar with player dots, ball trajectory, team colors, rotation toggle, lines/trails toggle | **Local UI Advantage**: Real-time smoothing and trail toggles. |
| **Hotkeys** | Space (play/pause), J/L (seek 5s), Arrows (frame step), F (fullscreen) | Space, J/L, Arrows, F, D (draw), R (radar) | **Full Parity** |
| **Download Options** | Saved clips (.mp4 zip) & Full game (.mp4) | Export Clips (.zip) with metadata CSV & Full game (.mp4) | **Full Parity** |

---

## 4. Key Recommendations for Parity Upgrades

1. **Top KPI Cards in Analytics Studio**: Add the 3 top metrics cards (Goals scored, Shots, Possession %) above the Stats accordion to match Veo's layout.
2. **Shot Map Breakdown Panel**: Add conversion rate cards (overall %, inside box %, outside box %) alongside the pitch diagram.
3. **Pass Strings Top Metrics**: Display the three category count cards (`3 to 5 passes`, `6 or more passes`, `Longest pass string`) above the histogram.
4. **Per-Accordion Team Toggle**: Allow switching between own and opponent breakdown within each individual analysis accordion.
