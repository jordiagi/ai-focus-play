"""Social media text analysis generator for soccer matches.

Generates tailored match recaps in Short (X/Twitter, <280 chars),
Medium (Instagram/Facebook caption), and Long (Match Report/Press Release) formats.
"""

from __future__ import annotations
import re
from typing import Dict, Any, Optional
from backend.src.domain.models.match import Match


def _clean_tag(text: str) -> str:
    """Create a camel-case hashtag from team or match name."""
    clean = re.sub(r"[^a-zA-Z0-9\s]", "", text)
    words = clean.split()
    return "".join(w.capitalize() for w in words[:3])


class SocialRecapGenerator:
    """Generates social media analysis across multiple length tiers."""

    @staticmethod
    def generate(
        match: Match,
        analytics: Optional[Any] = None,
        benchmark: Optional[Dict[str, Any]] = None,
        acta: Optional[Any] = None,
    ) -> Dict[str, Any]:
        home = match.home_team or "Home Team"
        away = match.away_team or "Away Team"
        score_h = match.home_score if match.home_score is not None else 0
        score_a = match.away_score if match.away_score is not None else 0
        date_str = match.date or "Matchday"

        # Extract stats from analytics or benchmark
        home_stats = getattr(analytics, "home_stats", None) if analytics else None
        away_stats = getattr(analytics, "away_stats", None) if analytics else None

        unavail = getattr(analytics, "unavailable", {}) or {}

        # Helper extractors
        def get_stat(key: str, default: int = 0) -> int:
            if benchmark and "stats_table" in benchmark:
                gt_rows = benchmark["stats_table"].get("rows", {})
                if key == "possession_percent" and "possession_percent" in gt_rows:
                    return int(round(gt_rows["possession_percent"].get("own", default)))
                if key == "shots" and "shot" in gt_rows:
                    return gt_rows["shot"].get("own", default)
                if key == "attempts" and "total_attempts" in gt_rows:
                    return gt_rows["total_attempts"].get("own", default)
                if key == "goals" and "goal" in gt_rows:
                    return gt_rows["goal"].get("own", score_h)
                if key == "passes_completed" and "passes_completed" in gt_rows:
                    return gt_rows["passes_completed"].get("own", default)
                if key == "tackles" and "tackle" in gt_rows:
                    return gt_rows["tackle"].get("own", default)
            if home_stats and getattr(home_stats, key, None) is not None and key not in unavail:
                val = getattr(home_stats, key)
                return int(round(val)) if isinstance(val, (int, float)) else val
            return default

        def get_away_stat(key: str, default: int = 0) -> int:
            if benchmark and "stats_table" in benchmark:
                gt_rows = benchmark["stats_table"].get("rows", {})
                if key == "possession_percent" and "possession_percent" in gt_rows:
                    return int(round(gt_rows["possession_percent"].get("opponent", default)))
                if key == "shots" and "shot" in gt_rows:
                    return gt_rows["shot"].get("opponent", default)
                if key == "attempts" and "total_attempts" in gt_rows:
                    return gt_rows["total_attempts"].get("opponent", default)
                if key == "goals" and "goal" in gt_rows:
                    return gt_rows["goal"].get("opponent", score_a)
                if key == "passes_completed" and "passes_completed" in gt_rows:
                    return gt_rows["passes_completed"].get("opponent", default)
                if key == "tackles" and "tackle" in gt_rows:
                    return gt_rows["tackle"].get("opponent", default)
            if away_stats and getattr(away_stats, key, None) is not None and key not in unavail:
                val = getattr(away_stats, key)
                return int(round(val)) if isinstance(val, (int, float)) else val
            return default

        possession_h = get_stat("possession_percent", 50)
        possession_a = get_away_stat("possession_percent", 100 - possession_h)
        attempts_h = get_stat("attempts", get_stat("shots", score_h))
        attempts_a = get_away_stat("attempts", get_away_stat("shots", score_a))
        passes_h = get_stat("passes_completed", 0)
        passes_a = get_away_stat("passes_completed", 0)
        tackles_h = get_stat("tackles", 0)
        tackles_a = get_away_stat("tackles", 0)

        # Progression details if present
        mid_prog = None
        if benchmark and "pass_location" in benchmark:
            mid_prog = benchmark["pass_location"].get("own", {}).get("middle_pct")

        # Determine outcome descriptor
        if score_h > score_a:
            if score_a == 0:
                result_verb = "Dominant clean sheet win"
                emoji_lead = "🛡️🔥"
            else:
                result_verb = "Strong victory"
                emoji_lead = "⚽⚡"
        elif score_h == score_a:
            result_verb = "Hard-fought draw"
            emoji_lead = "🤝⚽"
        else:
            result_verb = "Tough battle"
            emoji_lead = "👊⚽"

        # Extract goalscorers and incidents from acta or events if provided
        home_scorers = []
        away_scorers = []
        cards_summary = []
        subs_summary = []

        if not acta and benchmark and "acta" in benchmark:
            acta = benchmark["acta"]
        if acta:
            for g in getattr(acta, "goals", []):
                s_name = getattr(g, "scorer", "")
                min_str = f"{getattr(g, 'minute', '')}'"
                if getattr(g, "team", "") == "home":
                    home_scorers.append(f"{s_name} ({min_str})")
                else:
                    away_scorers.append(f"{s_name} ({min_str})")
            for c in getattr(acta, "cards", []):
                c_player = getattr(c, "player", "")
                c_card = getattr(c, "card", "card")
                c_min = f"{getattr(c, 'minute', '')}'"
                cards_summary.append(f"{c_player} [{c_card.upper()} {c_min}]")
            for s in getattr(acta, "substitutions", []):
                p_in = getattr(s, "player_in", "")
                p_out = getattr(s, "player_out", "")
                s_min = f"{getattr(s, 'minute', '')}'"
                subs_summary.append(f"IN {p_in} / OUT {p_out} ({s_min})")

        # Dynamic league tag
        is_catalan = any(k in home.lower() or k in away.lower() for k in ("horta", "turo", "fcf", "catalan"))
        league_tags = "#FCF #LligaElit #FutbolCat" if is_catalan else "#ECNLSoccer #ECNLBoys"

        home_tag = _clean_tag(home)
        away_tag = _clean_tag(away)

        # ----------------- 1. SHORT (X / Twitter, max 280 chars) -----------------
        scorers_line = ""
        if home_scorers:
            scorers_line = f"⚽ {', '.join(home_scorers)}"

        short_lines = [
            f"FT: {home} {score_h} - {score_a} {away} {emoji_lead}",
            f"{result_verb} on {date_str}!",
            scorers_line if scorers_line else f"📊 {possession_h}% poss | {attempts_h} attempts",
            f"#{home_tag} #{away_tag} {league_tags}"
        ]
        short_text = "\n".join([l for l in short_lines if l.strip()])
        if len(short_text) > 275:
            # Compact fallback
            short_text = (
                f"FT: {home} {score_h}-{score_a} {away} {emoji_lead}\n"
                f"{possession_h}% poss | {attempts_h} att | {score_h}G\n"
                f"#{home_tag} {league_tags.split()[0]}"
            )

        # ----------------- 2. MEDIUM (Instagram / Facebook caption) -----------------
        tactical_sentence = (
            f"Build-up through the central third was pivotal ({mid_prog}% central progression) "
            f"with {passes_h} completed passes controlling the tempo."
            if mid_prog and passes_h > 0
            else f"With {possession_h}% possession and {attempts_h} total attempts, {home} dictated the game's momentum."
        )
        defensive_sentence = (
            f"The backline and keeper secured a clean sheet, holding {away} to {attempts_a} attempts."
            if score_a == 0
            else f"Defensive pressure produced {tackles_h} tackles in a tightly contested fixture."
            if tackles_h > 0
            else f"A determined shift all 90 minutes."
        )

        scorers_block = ""
        if home_scorers or away_scorers:
            scorers_block = "\n⚽ Goalscorers:\n"
            if home_scorers:
                scorers_block += f"• {home}: {', '.join(home_scorers)}\n"
            if away_scorers:
                scorers_block += f"• {away}: {', '.join(away_scorers)}\n"

        incidents_block = ""
        if cards_summary:
            incidents_block = f"\n🟨 Disciplinary:\n• Cards: {', '.join(cards_summary)}\n"

        medium_text = (
            f"{result_verb.upper()}! {emoji_lead}\n\n"
            f"{home} produced an emphatic performance on {date_str}, finishing {score_h} - {score_a} against {away}.\n\n"
            f"{tactical_sentence} {defensive_sentence}\n"
            f"{scorers_block}"
            f"{incidents_block}\n"
            f"📈 Key Match Stats:\n"
            f"• Score: {score_h} - {score_a}\n"
            f"• Possession: {possession_h}% vs {possession_a}%\n"
            f"• Total Attempts: {attempts_h} vs {attempts_a}\n"
            + (f"• Completed Passes: {passes_h} vs {passes_a}\n" if passes_h > 0 else "")
            + (f"• Tackles Won: {tackles_h} vs {tackles_a}\n" if tackles_h > 0 else "")
            + f"\n#{home_tag} #{away_tag} {league_tags} #SoccerAnalytics #MatchRecap #GameDay"
        )

        # ----------------- 3. LONG (Match Report / Newsletter / Press Release) -----------------
        acta_table = ""
        if home_scorers or cards_summary or subs_summary:
            acta_table = f"""
### Official Match Sheet & Incident Timeline
| Type | Detail |
| :--- | :--- |
| **Goals ({home})** | {', '.join(home_scorers) if home_scorers else 'None'} |
| **Goals ({away})** | {', '.join(away_scorers) if away_scorers else 'None'} |
| **Cards** | {', '.join(cards_summary) if cards_summary else 'None'} |
| **Substitutions** | {'; '.join(subs_summary) if subs_summary else 'None'} |
"""

        campaign_name = "Lliga Elit" if is_catalan else "ECNL"
        long_text = f"""# MATCH REPORT: {home} vs. {away}
**Date:** {date_str} | **Final Result:** {home} {score_h} - {score_a} {away}

### Executive Summary
{home} delivered a comprehensive tactical display on {date_str}, capturing a {score_h}-{score_a} result against {away}. From the opening kickoff, {home} established authority on the pitch, combining controlled ball retention with incisive attacking transitions.
{acta_table}
### Tactical Phase Breakdown
- **Attacking Organization & Progression:**
  {home} registered {possession_h}% possession and generated {attempts_h} total attempts on goal. {f"Progression through the central third ({mid_prog}%) proved decisive in unlocking the opposition defensive block." if mid_prog else "Controlled tempo and coordinated combination play opened consistent passing lanes."}
  
- **Defensive Solidity & Pressing Transitions:**
  Out of possession, {home} restricted {away} to {attempts_a} total attempts and {score_a} goals conceded. The defensive unit logged {tackles_h} tackles, effectively stifling direct counter-attacking channels and maintaining structural compactness.

### Statistical Box Score
| Match Metric | {home} | {away} |
| :--- | :---: | :---: |
| **Goals** | **{score_h}** | **{score_a}** |
| **Possession** | **{possession_h}%** | **{possession_a}%** |
| **Total Attempts** | **{attempts_h}** | **{attempts_a}** |
| **Passes Completed** | **{passes_h if passes_h > 0 else "—"}** | **{passes_a if passes_a > 0 else "—"}** |
| **Tackles** | **{tackles_h if tackles_h > 0 else "—"}** | **{tackles_a if tackles_a > 0 else "—"}** |

### Coaching Takeaway & Outlook
"This fixture demonstrated the tactical discipline and collective effort we strive for across the {campaign_name} campaign. Maintaining tempo with the ball while staying resolute in transition gives us the foundation to compete at the highest level."
"""

        return {
            "match_id": match.id,
            "short": short_text.strip(),
            "medium": medium_text.strip(),
            "long": long_text.strip(),
            "char_count_short": len(short_text.strip()),
        }
