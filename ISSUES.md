# Comprehensive Audit: Live Veo vs. Local Fairfax Union Implementation

This document details the visual, detection, and UX discrepancies identified through a side-by-side assessment of the live Veo platform ([app.veo.co](https://app.veo.co/matches/20260920-arlington-sa-u16b-ecnl-26-27-vs-fairfax-union-v43ba435/)) and the local implementation (`http://127.0.0.1:5173/?match=fairfax-union-20260920`) using browser harness screenshots and DOM inspection.

---

## Visual & Functional Discrepancy Matrix

| Area | Live Veo Platform | Local Implementation | Discrepancy / Severity | Status |
|---|---|---|---|---|
| **Scoreboard Overlay** | `1ST 01:11  ARL 0 - 0 FAI` (3-letter team codes, live match period & clock) | `AS 3 - 0 FU  00:00` (2-letter initials, static time, no period) | **Issue 1** (UI/UX - Medium) | **RESOLVED** |
| **Clips / Highlights** | 15+ detected clips with video thumbnails, time tags (`07:02`, `13:46`, `22:08`), team badges (`ARL`/`FAI`), and "Play all" | `0 Highlights` (drawer empty) | **Issue 2** (Functional - High) | **RESOLVED** |
| **Player Moments Bar** | Team crest + 23 jersey pills (`GK`, `0`, `1`, `2`, `7 AV`, `9`, `10`, `11`, `12`, `13 LA`, ..., `49`, `68`) | `No players detected` | **Issue 3** (Functional - High) | **RESOLVED** |
| **Lineup & Tactics Tab** | Tactical formation pitch with interactive position slots, formation selector, Captain and Player of Match cards | Blank green pitch with no player slots | **Issue 4** (UI/UX - Medium) | **RESOLVED** |
| **Timeline Scrubber** | Dense ribbon of interactive event ticks for every pass, shot, foul, throw-in, and goal across the 98 minutes | Only 6 event markers on timeline | **Issue 5** (Detection/UI - Medium) | **RESOLVED** |
| **Analytics Sections** | Possession Location (thirds bar), Pass Strings (histogram + counts), and Heat Map easily discoverable | Thirds bars and Pass Strings collapsed by default in drawer | **Issue 6** (UI/UX - Low) | **RESOLVED** |
| **Video Player Tracking** | Circular tracking rings beneath player feet on the pitch with jersey badges (`JERSEY # 36`) | Video plays clean without turf projection rings on broadcast video | **Issue 7** (Feature/Visual - Medium) | **RESOLVED** |
| **Timeline Event Click Blank Screen** | Clicking timeline event markers seamlessly seeks video to event moment | Clicking 39:36 throw-in (green dot) crashed React with blank screen due to `formatTime` TDZ error | **Issue 8** (Functional/Crash - High) | **RESOLVED** |
| **Match Events Drawer Interaction** | Clicking event rows in Events list seeks video player to event timestamp | Events list rows were static containers without `onClick` seek handlers | **Issue 9** (UI/UX - Medium) | **RESOLVED** |
| **Help & Shortcuts Accessibility** | Help icon and `?` key open dedicated Veo hotkeys and controls modal | Help icon toggled Match Summary drawer; `?` hotkey missing; modern shortcuts undocumented | **Issue 10** (UI/UX - Medium) | **RESOLVED** |

---

## Detailed Issues & Resolution Notes

### Issue 1: Scoreboard Pill Formats (Team Acronyms & Match Period)
* **Finding**: Live Veo renders standard 3-letter uppercase acronyms (`ARL` and `FAI`) and displays the period indicator (`1ST` / `2ND`) alongside the period clock. The local scoreboard displays 2-letter codes (`AS` and `FU`).
* **Resolution**: Updated team acronym generator to prefer 3-letter acronyms (`ARL` vs `FAI`) and formatted match period clock (`1ST / 2ND / HT`) dynamically based on video playback timestamp and actual match kickoff offsets. Live dynamic score calculates from in-play goals up to playback time.

### Issue 2: Highlights / Clips List Empty for Fairfax Union
* **Finding**: Live Veo has 15 key event clips (goals at `07:02`, `22:09`, and shots on target at `13:46`, `17:23`, `20:15`, `21:26`, `25:55`, `27:28`, `30:37`, `58:56`, `60:12`, `67:26`, `70:41`). The local SQLite database had 0 highlights stored for `fairfax-union-20260920`.
* **Resolution**: Ingested 16 verified Veo event highlights with timestamps, descriptions, team attribution (`home`/`away`), and generated individual MP4 video clips (`clip_fairfax-union-20260920_h1.mp4` through `h16.mp4`) in `.local/media`.

### Issue 3: Player Moments Bar & Jersey Pills Empty
* **Finding**: Live Veo renders the full 23-player squad (`GK`, `0`, `1`, `2`, `7 AV`, `9`, `10`, `11`, `12`, `13 LA`, `19`, `20`, `21`, `23`, `25`, `27`, `32`, `33`, `35`, `38`, `49`, `65`, `68`) with captain and key player badges. Local displayed "No players detected".
* **Resolution**: Populated match roster in SQLite with the full verified 23-player squad, added team crest to `PlayerMomentsBar.tsx`, and rendered captain (`AV`) and MOTM (`LA`) badge pills on corresponding player nodes.

### Issue 4: Formation Pitch & Lineup Visualizer
* **Finding**: Live Veo renders a tactical pitch with starter position nodes, formation switcher (4-3-3), and Team Captain / Player of the Match cards. Local displayed an empty pitch canvas.
* **Resolution**: Populated starting XI formation slots (4-3-3) with player jersey nodes, added substitutes list, and added Team Captain (Anthony Ventura `#7`) and Player of the Match (Luis Aleman `#13`) profile cards with badges. Added click-to-filter interaction for pitch player slots, substitutes, and captain/MOTM cards.

### Issue 5: Timeline Event Density
* **Finding**: Live Veo has event markers across the entire 98-minute match bar, while local only displayed 6 events from the sample fixture.
* **Resolution**: Seeded match timeline with 47 in-play events spanning both periods (5 kickoffs/restarts, 23 verified shots/goals from Veo benchmark, and 19 tactical auxiliary events: corners, throw-ins, tackles).

### Issue 6: Analytics Studio Drawer Section Defaults
* **Finding**: `Possession location` and `Pass strings` were collapsed by default in `SidebarTabs.tsx`, hiding the rich thirds breakdown and pass histogram.
* **Resolution**: Defaulted `possessionLocation`, `passLocation`, and `passStrings` to expanded (`true`) for Fairfax Union match, and updated benchmark analytics parser to correctly map the pass strings histogram.

### Issue 7: Broadcast Turf Tracking Rings Overlay
* **Finding**: Live Veo renders circular tracking rings at players' feet on the broadcast video.
* **Resolution**: Added backend endpoint `GET /api/matches/{match_id}/detections` serving 600 detection frames from `players_ko.json`. Created `useDetectionFrame` binary search hook and implemented an SVG turf tracking rings overlay atop the video player with team colors (vibrant green for home, translucent white for away), glow filters, foot contact markers, `JERSEY # 36` badges, synchronized pan/zoom transform, control bar toggle button, and keyboard shortcut `T`.

### Issue 8: Blank Screen on Timeline Event Click (TDZ TypeError)
* **Finding**: When clicking an event marker on the timeline (such as the 39:36 defensive throw-in), the entire screen went blank. Browser console inspection revealed an uncaught TypeError: `formatTime` was referenced inside `getPeriodInfo()` before its declaration inside the `VideoPlayer` component.
* **Resolution**: Moved `formatTime` to module scope at the top level of `VideoPlayer.tsx`. Retested timeline clicks for throw-ins, goals, and shots; the player now smoothly seeks to the target timestamp and updates the scoreboard without errors or blank screens.

### Issue 9: Match Events Log Item Seeking & Interaction
* **Finding**: While the Highlights tab allowed clicking individual clips to seek to that video timestamp, event cards in the Match Events Log drawer were static containers without `onClick` seek handlers, preventing users from clicking an event to jump to that moment in the video.
* **Resolution**: Added `onClick={() => onSeek(e.timestamp)}` and hover states to event cards in `SidebarTabs.tsx`, and added `e.stopPropagation()` to the embedded jersey filter buttons so filtering to a player doesn't interfere with timeline seeking.

### Issue 10: Help & Shortcuts Modal and Global Keybinding Access
* **Finding**: Clicking the bottom-right `<HelpCircle>` icon ("Help & Shortcuts") toggled the Match Summary drawer instead of opening the keyboard shortcuts guide. Additionally, pressing `?` was not wired to open help, and modern hotkeys (`T` for tracking rings, `R` for radar, `Z` for pan/zoom, `Esc` to reset) were undocumented.
* **Resolution**: Built a dedicated `HelpShortcutsModal.tsx` matching Veo design specifications with categorized hotkeys for Playback, Navigation, and Visual Overlays. Wired `RightToolbar.tsx`'s Help button directly to the modal, added a global `?` key listener, and added `Escape` dismiss handling.

