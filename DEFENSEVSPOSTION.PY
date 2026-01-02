# file: scripts/bettingpros_dvp_scraper.py
r"""
BettingPros NBA Defense vs. Position scraper.
Saves a single combined JSON file with all positions and timeframes into:
C:\Users\dasil\My Drive (dasilvadub@gmail.com)\NBA\MATCHUP\NBA Defense vs. Position\

Output file:
- defense_vs_position_all.json (all 30 teams across all 5 positions and 4 timeframes)

JSON Structure:
{
  "metadata": {
    "source": "bettingpros.com",
    "scraped_at": "2025-12-31T08:00:00",
    "positions": ["PG", "SG", "SF", "PF", "C"],
    "timeframes": ["2025-26", "Last 7", "Last 15", "Last 30"],
    "total_teams": 30
  },
  "data": {
    "PG": {
      "2025-26": [{team data}, ...],
      "Last 7": [{team data}, ...],
      "Last 15": [{team data}, ...],
      "Last 30": [{team data}, ...]
    },
    "SG": {
      "2025-26": [{team data}, ...],
      "Last 7": [{team data}, ...],
      "Last 15": [{team data}, ...],
      "Last 30": [{team data}, ...]
    },
    ... (same for SF, PF, C)
  }
}

Why this design:
- Single file format makes it easier for LLM analysis and data integration
- Captures multiple timeframes (full season and recent trends) for comprehensive analysis
- Uses robust role/text-based selectors with fallbacks: BettingPros' UI can shift between tabs and dropdowns.
- Validates 30 teams per position and timeframe; retries if the table isn't fully loaded.
- Normalizes team names to consistent folder names to keep storage tidy and predictable.
- Includes metadata for tracking source, timestamp, and data completeness
- Fails fast with a clear summary if anything is missing, so you never trust partial data.
"""

from __future__ import annotations

import json
import logging
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ---------- Configuration ----------
BETTINGPROS_DVP_URL = "https://www.bettingpros.com/nba/defense-vs-position/"

BASE_OUTPUT_DIR = Path(r"C:\Users\dasil\My Drive (dasilvadub@gmail.com)\NBA\MATCHUP\NBA Defense vs. Position")

POSITIONS = ["PG", "SG", "SF", "PF", "C"]
# Timeframes to scrape
TIMEFRAMES = ["2025-26", "Last 7", "Last 15", "Last 30"]
# Single combined output file
COMBINED_OUTPUT_FILE = "defense_vs_position_all.json"

# Header labels we expect to see in the table (case-insensitive match)
REQUIRED_HEADERS = ["Team", "PTS", "REB", "AST", "3PM", "STL", "BLK", "TO"]

# Canonical team folder names (city/brand-only per spec/example)
CANONICAL_TEAMS = [
    "Atlanta", "Boston", "Brooklyn", "Charlotte", "Chicago", "Cleveland", "Dallas", "Denver",
    "Detroit", "Golden State", "Houston", "Indiana", "LA Clippers", "LA Lakers", "Memphis",
    "Miami", "Milwaukee", "Minnesota", "New Orleans", "New York", "Oklahoma City", "Orlando",
    "Philadelphia", "Phoenix", "Portland", "Sacramento", "San Antonio", "Toronto", "Utah",
    "Washington",
]

# Map many possible inputs to canonical folder names
TEAM_ALIASES: Dict[str, str] = {
    # Eastern
    "ATL": "Atlanta", "ATLANTA HAWKS": "Atlanta", "ATLANTA": "Atlanta",
    "BOS": "Boston", "BOSTON CELTICS": "Boston", "BOSTON": "Boston",
    "BKN": "Brooklyn", "BROOKLYN NETS": "Brooklyn", "BROOKLYN": "Brooklyn",
    "CHA": "Charlotte", "CHARLOTTE HORNETS": "Charlotte", "CHARLOTTE": "Charlotte",
    "CHI": "Chicago", "CHICAGO BULLS": "Chicago", "CHICAGO": "Chicago",
    "CLE": "Cleveland", "CLEVELAND CAVALIERS": "Cleveland", "CLEVELAND": "Cleveland",
    "DET": "Detroit", "DETROIT PISTONS": "Detroit", "DETROIT": "Detroit",
    "IND": "Indiana", "INDIANA PACERS": "Indiana", "INDIANA": "Indiana",
    "MIA": "Miami", "MIAMI HEAT": "Miami", "MIAMI": "Miami",
    "MIL": "Milwaukee", "MILWAUKEE BUCKS": "Milwaukee", "MILWAUKEE": "Milwaukee",
    "NY": "New York", "NYK": "New York", "NEW YORK KNICKS": "New York", "NEW YORK": "New York",
    "ORL": "Orlando", "ORLANDO MAGIC": "Orlando", "ORLANDO": "Orlando",
    "PHI": "Philadelphia", "PHILADELPHIA 76ERS": "Philadelphia", "PHILADELPHIA": "Philadelphia", "PHILA": "Philadelphia", "SIXERS": "Philadelphia",
    "TOR": "Toronto", "TORONTO RAPTORS": "Toronto", "TORONTO": "Toronto",
    "WAS": "Washington", "WASHINGTON WIZARDS": "Washington", "WASHINGTON": "Washington",
    # Western
    "DAL": "Dallas", "DALLAS MAVERICKS": "Dallas", "DALLAS": "Dallas",
    "DEN": "Denver", "DENVER NUGGETS": "Denver", "DENVER": "Denver",
    "GS": "Golden State", "GSW": "Golden State", "GOLDEN STATE WARRIORS": "Golden State", "GOLDEN STATE": "Golden State",
    "HOU": "Houston", "HOUSTON ROCKETS": "Houston", "HOUSTON": "Houston",
    "LAC": "LA Clippers", "LA CLIPPERS": "LA Clippers", "LOS ANGELES CLIPPERS": "LA Clippers", "CLIPPERS": "LA Clippers",
    "LAL": "LA Lakers", "LA LAKERS": "LA Lakers", "LOS ANGELES LAKERS": "LA Lakers", "LAKERS": "LA Lakers",
    "MEM": "Memphis", "MEMPHIS GRIZZLIES": "Memphis", "MEMPHIS": "Memphis",
    "MIN": "Minnesota", "MINNESOTA TIMBERWOLVES": "Minnesota", "MINNESOTA": "Minnesota",
    "NOP": "New Orleans", "NO": "New Orleans", "NEW ORLEANS PELICANS": "New Orleans", "NEW ORLEANS": "New Orleans", "NOLA": "New Orleans",
    "OKC": "Oklahoma City", "OKLAHOMA CITY THUNDER": "Oklahoma City", "OKLAHOMA CITY": "Oklahoma City",
    "PHX": "Phoenix", "PHOENIX SUNS": "Phoenix", "PHOENIX": "Phoenix",
    "POR": "Portland", "PORTLAND TRAIL BLAZERS": "Portland", "PORTLAND": "Portland",
    "SAC": "Sacramento", "SACRAMENTO KINGS": "Sacramento", "SACRAMENTO": "Sacramento",
    "SAS": "San Antonio", "SAN ANTONIO SPURS": "San Antonio", "SAN ANTONIO": "San Antonio", "SA SPURS": "San Antonio",
    "UTA": "Utah", "UTAH JAZZ": "Utah", "UTAH": "Utah",
}

# ---------- Logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("bettingpros_dvp")


@dataclass(frozen=True)
class DvpRow:
    team_folder: str
    team_raw: str
    position: str
    timeframe: str
    pts: str
    reb: str
    ast: str
    three_pm: str
    stl: str
    blk: str
    to: str

    def to_json_obj(self) -> Dict[str, str]:
        return {
            "Team": self.team_folder,
            "Position": self.position,
            "Timeframe": self.timeframe,
            "PTS": self.pts,
            "REB": self.reb,
            "AST": self.ast,
            "3PM": self.three_pm,
            "STL": self.stl,
            "BLK": self.blk,
            "TO": self.to,
        }


def normalize_space(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


_la_teams_count = 0  # Counter for LA teams in current position


def canonicalize_team_folder(team_text: str, row_index: int = -1) -> str:
    """
    Canonicalize team name to folder name.
    For LA teams, uses order of appearance to assign Lakers to the first LA team and Clippers to the second.
    """
    global _la_teams_count
    original_text = team_text
    t = normalize_space(team_text).upper().replace(".", "")

    # Remove record in parentheses (e.g., "Chicago (14-15)" -> "CHICAGO")
    t = re.sub(r"\s*\([^)]*\)\s*$", "", t).strip()

    # Handle "LOS ANGELES" ambiguity using order of appearance
    # Assumption: Lakers and Clippers appear in a consistent order
    # We'll assign the first "Los Angeles" to Lakers and second to Clippers
    if t == "LOS ANGELES":
        _la_teams_count += 1
        if _la_teams_count == 1:
            # First LA team -> Lakers
            return "LA Lakers"
        else:
            # Second LA team -> Clippers
            return "LA Clippers"

    # Remove mascots when present (HAWKS, CELTICS, etc.) to match our city/brand folders.
    # Only done when it safely maps via TEAM_ALIASES; otherwise leave as-is for visibility.
    return TEAM_ALIASES.get(t, TEAM_ALIASES.get(re.sub(r"\b(HAWKS|CELTICS|NETS|HORNETS|BULLS|CAVALIERS|PISTONS|PACERS|HEAT|BUCKS|KNICKS|MAGIC|RAPTORS|WIZARDS|MAVERICKS|NUGGETS|WARRIORS|ROCKETS|CLIPPERS|LAKERS|GRIZZLIES|TIMBERWOLVES|PELICANS|THUNDER|SUNS|TRAIL BLAZERS|KINGS|SPURS|JAZZ)\b", "", t).strip(), None)) or team_text


def ensure_dirs(base: Path) -> None:
    """Ensure the output directory exists."""
    base.mkdir(parents=True, exist_ok=True)


def dismiss_cookie_banner(page) -> None:
    # Why: cookie walls can block clicks; we try common accept patterns without being site-specific.
    candidates = [
        "button:has-text('Accept')",
        "button:has-text('I Accept')",
        "button:has-text('I Agree')",
        "text=Accept All",
    ]
    for sel in candidates:
        try:
            el = page.locator(sel)
            if el.first.is_visible(timeout=1000):
                el.first.click()
                page.wait_for_timeout(300)
                return
        except Exception:
            pass


def dismiss_premium_modal(page) -> None:
    """Dismiss any premium/paywall modals that block content."""
    # Try multiple approaches to close the modal
    close_candidates = [
        # Close button selectors
        "button[aria-label='Close']",
        "button[class*='close']",
        "button[class*='dismiss']",
        "[class*='modal'] button:has-text('×')",
        "[class*='modal'] button:has-text('X')",
        "[class*='overlay'] button:has-text('×')",
        # Click outside the modal
        ".modal-backdrop",
        ".overlay",
    ]

    for sel in close_candidates:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=1000):
                el.click(timeout=1000)
                page.wait_for_timeout(500)
                logger.info("Dismissed premium modal using: %s", sel)
                return
        except Exception:
            pass

    # Try pressing Escape key
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
        logger.info("Dismissed modal with Escape key")
    except Exception:
        pass


def wait_for_table_ready(page, timeout_ms: int = 15000) -> None:
    # Why: BettingPros is JS-rendered; we wait for the correct table to appear and settle.
    end = time.time() + (timeout_ms / 1000)
    last_count = -1
    stable_for = 0.0
    debug_logged = False
    while time.time() < end:
        try:
            # Table that includes "Team" and "Record" headers
            table = page.locator("table").filter(has=page.locator("thead")).first
            # Make sure header contains key columns
            header_cells = table.locator("thead th").all_inner_texts()
            header_text = " | ".join([h.strip() for h in header_cells]).upper()

            # Debug: log headers once
            if not debug_logged:
                logger.info("Table headers found: %s", header_text)
                debug_logged = True

            if not ("TEAM" in header_text):
                page.wait_for_timeout(200)
                continue
            rows = table.locator("tbody tr")
            count = rows.count()
            if count > 0:
                # Check if row count stabilized for ~600ms
                if count == last_count:
                    stable_for += 0.2
                    if stable_for >= 0.6:
                        logger.info("Table ready with %d rows", count)
                        return
                else:
                    stable_for = 0.0
                last_count = count
            page.wait_for_timeout(200)
        except PWTimeout:
            page.wait_for_timeout(200)
        except Exception as e:
            if not debug_logged:
                logger.warning("Error while waiting for table: %s", e)
                debug_logged = True
            page.wait_for_timeout(200)

    # Debug: capture what's on the page when we timeout
    try:
        all_tables = page.locator("table").all()
        logger.error("Table timeout. Found %d tables on page", len(all_tables))
        for i, t in enumerate(all_tables[:3]):
            try:
                headers = t.locator("thead th").all_inner_texts()
                logger.error("Table[%d] headers: %s", i, headers)
            except Exception:
                pass
        page.screenshot(path="debug_table_timeout.png")
        logger.error("Screenshot saved to debug_table_timeout.png")
    except Exception:
        pass

    raise PWTimeout("DvP table not ready in time")


def select_timeframe(page, timeframe: str) -> None:
    """Select a timeframe (2025-26, Last 7, Last 15, Last 30) from the dropdown."""
    tried = []
    page.wait_for_timeout(1000)

    # Try the specific dropdown that BettingPros uses for timeframe selection
    try:
        # Click the dropdown trigger - look for the one that contains season/timeframe options
        dropdown_trigger = page.locator("button.dropdown-select__trigger").filter(has_text=re.compile(r"2025-26|Last \d+")).first
        if dropdown_trigger.is_visible(timeout=2000):
            dropdown_trigger.click(timeout=2000)
            page.wait_for_timeout(500)
            # Now click the menu option for the timeframe
            option = page.locator(f"li.menu__option:has-text('{timeframe}')").first
            if option.is_visible(timeout=2000):
                option.click(timeout=2000)
                page.wait_for_timeout(2000)  # Give more time for table to load
                page.wait_for_load_state("networkidle", timeout=10000)
                logger.info("Selected timeframe %s via dropdown", timeframe)
                return
    except Exception as e:
        tried.append(f"dropdown:{e!r}")

    # Try broad text-based approach
    try:
        loc = page.locator("button, a, div[role='button'], li").filter(
            has_text=re.compile(fr"\b{re.escape(timeframe)}\b", re.I)
        )
        visible_count = 0
        for i in range(loc.count()):
            try:
                if loc.nth(i).is_visible(timeout=500):
                    visible_count += 1
                    loc.nth(i).click(timeout=2000)
                    page.wait_for_timeout(1000)
                    page.wait_for_load_state("networkidle", timeout=5000)
                    logger.info("Selected timeframe %s via text match", timeframe)
                    return
            except Exception:
                continue
        if visible_count == 0:
            tried.append(f"text-match: no visible elements found")
    except Exception as e:
        tried.append(f"text-match:{e!r}")

    raise RuntimeError(f"Unable to select timeframe {timeframe}. Attempts: {tried}")


def select_position(page, position: str) -> None:
    # Why: Position control could be tabs or a combobox; try multiple patterns for resilience.
    tried = []

    # First, wait a bit for any Vue.js content to render
    page.wait_for_timeout(1000)


    # Try the specific dropdown that BettingPros uses for position selection
    try:
        # Click the dropdown trigger
        dropdown_trigger = page.locator("button.dropdown-select__trigger, .dropdown-select__trigger").first
        if dropdown_trigger.is_visible(timeout=2000):
            dropdown_trigger.click(timeout=2000)
            page.wait_for_timeout(500)
            # Now click the menu option for the position
            option = page.locator(f"li.menu__option:has-text('{position}')").first
            if option.is_visible(timeout=2000):
                option.click(timeout=2000)
                page.wait_for_timeout(2000)  # Give more time for table to load
                page.wait_for_load_state("networkidle", timeout=10000)
                logger.info("Selected position %s via dropdown", position)
                return
    except Exception as e:
        tried.append(f"dropdown:{e!r}")

    # Try broad text-based approach (works with Vue.js rendered content)
    try:
        # Look for clickable elements containing exactly the position text
        loc = page.locator("button, a, div[role='button'], li, span").filter(
            has_text=re.compile(fr"\b{position}\b", re.I)
        )
        visible_count = 0
        for i in range(loc.count()):
            try:
                if loc.nth(i).is_visible(timeout=500):
                    visible_count += 1
                    # Click the first visible match
                    loc.nth(i).click(timeout=2000)
                    page.wait_for_timeout(1000)
                    page.wait_for_load_state("networkidle", timeout=5000)
                    return
            except Exception:
                continue
        if visible_count == 0:
            tried.append(f"text-match: no visible elements found")
    except Exception as e:
        tried.append(f"text-match:{e!r}")

    # Try role-based tab
    try:
        page.get_by_role("tab", name=position, exact=True).click(timeout=2000)
        page.wait_for_load_state("networkidle", timeout=5000)
        return
    except Exception as e:
        tried.append(f"tab:{e!r}")

    # Try role-based button
    try:
        page.get_by_role("button", name=re.compile(fr"^{position}$", re.I)).click(timeout=2000)
        page.wait_for_load_state("networkidle", timeout=5000)
        return
    except Exception as e:
        tried.append(f"button:{e!r}")

    # Try combobox approach
    try:
        cb = page.get_by_role("combobox", name=re.compile("Position", re.I))
        cb.click(timeout=2000)
        page.get_by_role("option", name=position, exact=True).click(timeout=2000)
        page.wait_for_load_state("networkidle", timeout=5000)
        return
    except Exception as e:
        tried.append(f"combobox:{e!r}")

    # Try CSS selector approach for common navigation patterns
    try:
        selectors = [
            f"nav a:has-text('{position}')",
            f"ul.nav li:has-text('{position}')",
            f".tabs a:has-text('{position}')",
            f".position-selector *:has-text('{position}')",
        ]
        for sel in selectors:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=1000):
                    el.click(timeout=2000)
                    page.wait_for_timeout(1000)
                    page.wait_for_load_state("networkidle", timeout=5000)
                    return
            except Exception:
                continue
        tried.append("css-selectors: none matched")
    except Exception as e:
        tried.append(f"css:{e!r}")

    raise RuntimeError(f"Unable to select position {position}. Attempts: {tried}")


def extract_header_map(page) -> Dict[str, int]:
    # Map normalized header -> column index
    table = page.locator("table").filter(has=page.locator("thead")).first
    raw_headers = table.locator("thead th").all_inner_texts()
    hmap: Dict[str, int] = {}
    for idx, h in enumerate(raw_headers):
        # Take only the first line (before any newline) to extract the actual column name
        # This removes sort button text like "CLICK TO SORT..."
        first_line = h.split('\n')[0].strip()
        key = normalize_space(first_line).upper()
        hmap[key] = idx
    return hmap


def find_required_columns(hmap: Dict[str, int]) -> Dict[str, int]:
    resolved: Dict[str, int] = {}
    for label in REQUIRED_HEADERS:
        key = label.upper()
        # Accept direct header match OR common variants (e.g., "3PTM" vs "3PM")
        candidates = [key]
        if key == "3PM":
            candidates += ["3PTM", "3-PTM", "3P MADE", "3PT MADE"]
        for k in candidates:
            if k in hmap:
                resolved[label] = hmap[k]
                break
        if label not in resolved:
            raise KeyError(f"Missing required column: {label} (have: {list(hmap)})")
    return resolved


def read_rows_for_position(page, position: str, timeframe: str) -> List[DvpRow]:
    global _la_teams_count
    # Reset LA teams counter for each position
    _la_teams_count = 0

    wait_for_table_ready(page)
    hmap = extract_header_map(page)
    col_idx = find_required_columns(hmap)
    table = page.locator("table").filter(has=page.locator("thead")).first
    body_rows = table.locator("tbody tr")
    rows: List[DvpRow] = []
    for i in range(body_rows.count()):
        row = body_rows.nth(i)
        cells = [normalize_space(x) for x in row.locator("td").all_inner_texts()]
        team_raw = cells[col_idx["Team"]]
        team_folder = canonicalize_team_folder(team_raw, row_index=i)
        pts = cells[col_idx["PTS"]]
        reb = cells[col_idx["REB"]]
        ast = cells[col_idx["AST"]]
        three = cells[col_idx["3PM"]]
        stl = cells[col_idx["STL"]]
        blk = cells[col_idx["BLK"]]
        to_ = cells[col_idx["TO"]]
        rows.append(
            DvpRow(
                team_folder=team_folder, team_raw=team_raw, position=position,
                timeframe=timeframe, pts=pts, reb=reb, ast=ast, three_pm=three,
                stl=stl, blk=blk, to=to_,
            )
        )
    return rows


def validate_rows(rows: List[DvpRow], position: str) -> Tuple[bool, str]:
    # Why: we only trust a full 30-team table; partial loads produce bad data.
    teams = [r.team_folder for r in rows]
    unique = set(teams)
    # If some teams failed to normalize, they remain as original strings; report explicitly.
    bad_names = [t for t in unique if t not in CANONICAL_TEAMS]
    msg_parts = []
    ok = True
    if len(unique) != 30:
        ok = False
        msg_parts.append(f"{position}: expected 30 teams, got {len(unique)} (rows={len(rows)})")
        missing = [t for t in CANONICAL_TEAMS if t not in unique]
        if missing:
            msg_parts.append(f"missing: {missing}")
    if bad_names:
        ok = False
        msg_parts.append(f"{position}: unrecognized team names (update aliases?): {bad_names}")
    return ok, " | ".join(msg_parts) if msg_parts else f"{position}: OK"


def save_all_positions(all_position_data: dict, base_dir: Path) -> None:
    """Save all positions and timeframes to a single combined JSON file."""
    from datetime import datetime

    out_file = base_dir / COMBINED_OUTPUT_FILE

    # Create structured output with metadata
    output = {
        "metadata": {
            "source": "bettingpros.com",
            "url": BETTINGPROS_DVP_URL,
            "scraped_at": datetime.now().isoformat(),
            "positions": list(all_position_data.keys()),
            "timeframes": TIMEFRAMES,
            "total_teams": 30
        },
        "data": all_position_data
    }

    with out_file.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # Count total records across all positions and timeframes
    total_records = sum(
        len(teams)
        for position_data in all_position_data.values()
        for teams in position_data.values()
    )
    logger.info(f"Saved {total_records} total records across {len(all_position_data)} positions and {len(TIMEFRAMES)} timeframes to {out_file.name}")


def final_validation(all_position_data: dict) -> Tuple[bool, str]:
    """Verify all 5 positions and all timeframes were scraped."""
    missing_positions = []
    missing_timeframes = []

    for position in POSITIONS:
        if position not in all_position_data or not all_position_data[position]:
            missing_positions.append(position)
        else:
            # Check that all timeframes are present for this position
            for timeframe in TIMEFRAMES:
                if timeframe not in all_position_data[position] or not all_position_data[position][timeframe]:
                    missing_timeframes.append(f"{position}/{timeframe}")

    errors = []
    if missing_positions:
        errors.append(f"Missing positions: {missing_positions}")
    if missing_timeframes:
        errors.append(f"Missing timeframes: {missing_timeframes}")

    if errors:
        return False, "; ".join(errors)

    return True, f"All {len(POSITIONS)} positions and {len(TIMEFRAMES)} timeframes scraped successfully."


def scrape(
    headless: bool = True,
    slow_mo_ms: int = 0,
    max_retries_per_position: int = 3,
) -> None:
    ensure_dirs(BASE_OUTPUT_DIR)

    # Dictionary to store all position data
    all_position_data = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=slow_mo_ms)
        context = browser.new_context(locale="en-US", viewport={"width": 1440, "height": 900})
        page = context.new_page()
        try:
            logger.info("Opening BettingPros DvP page")
            page.goto(BETTINGPROS_DVP_URL, wait_until="domcontentloaded", timeout=45000)
            dismiss_cookie_banner(page)
            page.wait_for_load_state("networkidle")
            # Dismiss any premium modals that might block content
            dismiss_premium_modal(page)
            page.wait_for_timeout(1000)

            for pos in POSITIONS:
                # Initialize position data structure if not exists
                if pos not in all_position_data:
                    all_position_data[pos] = {}

                for timeframe in TIMEFRAMES:
                    logger.info(f"Scraping {pos} - {timeframe}")
                    success = False
                    last_err = ""
                    for attempt in range(1, max_retries_per_position + 1):
                        try:
                            select_position(page, pos)
                            select_timeframe(page, timeframe)
                            rows = read_rows_for_position(page, pos, timeframe)
                            ok, reason = validate_rows(rows, pos)
                            if not ok:
                                raise RuntimeError(reason)

                            # Store position and timeframe data
                            all_position_data[pos][timeframe] = [r.to_json_obj() for r in rows]
                            logger.info(f"{pos} - {timeframe}: scraped {len(rows)} teams")
                            success = True
                            break
                        except Exception as e:
                            last_err = str(e)
                            logger.warning(f"{pos} - {timeframe}: attempt {attempt} failed: {e}")
                            # Backoff and try again (refresh helps when content locks up)
                            try:
                                page.wait_for_timeout(600 * attempt)
                                page.reload(wait_until="domcontentloaded", timeout=45000)
                                dismiss_cookie_banner(page)
                                page.wait_for_load_state("networkidle")
                                dismiss_premium_modal(page)
                                page.wait_for_timeout(500)
                            except Exception:
                                pass
                    if not success:
                        raise RuntimeError(f"Failed to scrape {pos} - {timeframe} after retries. Last error: {last_err}")

            # Validate all positions were scraped
            ok, report = final_validation(all_position_data)
            if not ok:
                raise RuntimeError(report)

            # Save all data to single JSON file
            save_all_positions(all_position_data, BASE_OUTPUT_DIR)
            logger.info(report)

        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    # Set headless=False to watch it, or use environment flags as needed.
    # For debugging: headless=False, slow_mo_ms=100
    import os
    debug_mode = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")
    try:
        scrape(headless=not debug_mode, slow_mo_ms=100 if debug_mode else 0, max_retries_per_position=4)
    except Exception as exc:
        logger.error("SCRAPE FAILED: %s", exc)
        sys.exit(1)
    sys.exit(0)
