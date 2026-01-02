"""
get_basketball_stats_all_teams.py

Scrapes Basketball-Reference team pages for a given season for all 30 NBA teams,
extracts a standard set of tables, normalizes headers, and saves per-team:
 - individual Excel files (one per table)
 - individual CSV files (one per table)
 - per-table schema JSON
 - combined workbook (all extracted tables as separate sheets)
 - combined schema JSON

Notes:
 - Adjust BASE_OUTPUT_DIR to the folder where you want outputs saved.
 - This script runs sequentially over teams; it re-uses a single Selenium driver
   instance for all requests to reduce startup overhead.
 - The script by default will skip a team if the combined workbook already exists;
   you can choose to overwrite.

Requires:
 - selenium, webdriver-manager, beautifulsoup4, pandas, openpyxl
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup, Comment
import pandas as pd
from io import StringIO
import time
import sys

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass
import os
import sys
import json
import re
import random
from typing import List

# ========== CONFIG ==========
# Default header separator (change if you prefer spaces, dots, etc.)
DEFAULT_HEADER_SEP = "_"

# Base output directory (change this to your desired root)
BASE_OUTPUT_DIR = r"C:\Users\dasil\My Drive (dasilvadub@gmail.com)\NBA\TEAMS"

# Which tables to extract from each team page (IDs used on basketball-reference)
TABLES_TO_EXTRACT = [
    'roster',
    'team_and_opponent',
    'team_misc',
    'per_game_stats',
    'totals_stats',
    'per_minute_stats',
    'per_poss',
    'advanced',
    'adj_shooting',
    'shooting',
    'pbp_stats'
]

# Mapping of table IDs to friendly names (for filenames and sheet names)
TABLE_NAME_MAP = {
    'roster': 'Roster',
    'team_and_opponent': 'Team_and_Opponent',
    'team_misc': 'Team_Misc',
    'per_game_stats': 'per_game_stats',
    'totals_stats': 'totals_stats',
    'per_minute_stats': 'per_minute_stats',
    'per_poss': 'Per_100_Poss',
    'advanced': 'Advanced',
    'adj_shooting': 'Adjusted_Shooting',
    'shooting': 'Shooting',
    'pbp_stats': 'pbp_stats'
}

# All 30 NBA team abbreviations (Basketball-Reference codes)
ALL_TEAMS = [
    'ATL','BKN','BOS','CHA','CHI','CLE','DAL','DEN','DET','GSW',
    'HOU','IND','LAC','LAL','MEM','MIA','MIL','MIN','NOP','NYK',
    'OKC','ORL','PHI','PHX','POR','SAC','SAS','TOR','UTA','WAS'
]

# Minimum/maximum delay between team requests (seconds)
SLEEP_MIN = 2.0
SLEEP_MAX = 5.0

# ============================

def flatten_columns(df: pd.DataFrame, sep: str) -> pd.DataFrame:
    cols = df.columns
    if isinstance(cols, pd.MultiIndex):
        new_cols = []
        for col in cols:
            parts = [str(c).strip() for c in col if (c is not None and str(c).strip() != '')]
            joined = sep.join(parts) if parts else ""
            new_cols.append(joined)
        seen = {}
        unique_cols = []
        for c in new_cols:
            base = c if c != "" else "Unnamed"
            if base in seen:
                seen[base] += 1
                unique = f"{base}{sep}{seen[base]}"
            else:
                seen[base] = 0
                unique = base
            unique_cols.append(unique)
        df.columns = unique_cols
    else:
        df.columns = [str(c).strip() for c in df.columns]
    return df

# Canonical mapping (expand as needed)
CANONICAL = {
    'player': 'Player','name':'Player','age':'Age','pos':'Pos','team':'Team',
    'g':'G','gs':'GS','mp':'MP','mp_per_g':'MP_per_G',
    'fg%':'FG_pct','fg pct':'FG_pct','fg':'FG',
    '2p%':'2P_pct','2p pct':'2P_pct','3p%':'3P_pct','3p pct':'3P_pct',
    'fg3a':'FG3A','fg3':'FG3','fg3_pct':'FG3_pct','fg_pct':'FG_pct',
    'efg%':'eFG_pct','ts%':'TS_pct',
    'ft':'FT','fta':'FTA','ft%':'FT_pct','ft_pct':'FT_pct',
    'orb':'ORB','drb':'DRB','trb':'TRB','ast':'AST','stl':'STL','blk':'BLK',
    'tov':'TOV','pf':'PF','pts':'PTS',
    'per':'PER','ortg':'ORtg','drtg':'DRtg','usg%':'USG_pct','ws':'WS','ws/48':'WS_per_48'
}

def normalize_column_name(col: str, sep: str) -> str:
    s = str(col).strip()
    s = re.sub(r'Unnamed.*', '', s, flags=re.IGNORECASE).strip(sep + " ")
    s = re.sub(r'level_\d+_', '', s)
    s = re.sub(r'\s+', sep, s)
    s_lower = s.lower()
    for token in sorted(CANONICAL.keys(), key=lambda x: -len(x)):
        if token in s_lower:
            return CANONICAL[token]
    if '%' in s:
        s = s.replace('%', '_pct')
    s = re.sub(r'{0}+'.format(re.escape(sep)), sep, s)
    s = s.strip(sep)
    return s or 'Unnamed'

def normalize_dataframe_columns(df: pd.DataFrame, sep: str) -> pd.DataFrame:
    new_cols = [normalize_column_name(c, sep=sep) for c in df.columns]
    seen = {}
    final_cols = []
    for name in new_cols:
        base = name or "Unnamed"
        if base in seen:
            seen[base] += 1
            unique = f"{base}{sep}{seen[base]}"
        else:
            seen[base] = 0
            unique = base
        final_cols.append(unique)
    df.columns = final_cols
    return df

def clean_dataframe(df: pd.DataFrame, table_name: str, sep: str) -> pd.DataFrame:
    df = flatten_columns(df, sep=sep)
    if 'Player' in df.columns:
        df = df[df['Player'] != 'Player']
    if 'Rk' in df.columns:
        df = df[df['Rk'] != 'Rk']
    if table_name == "Roster":
        if 'Birth Date' in df.columns:
            df['Birth Date'] = pd.to_datetime(df['Birth Date'], errors='coerce').dt.strftime('%m/%d/%Y')
        if 'Birth' in df.columns:
            df['Birth'] = df['Birth'].astype(str).str.replace('us US', 'US', case=False, regex=False)
            df['Birth'] = df['Birth'].astype(str).str.replace('US US', 'US', case=False, regex=False)
            df['Birth'] = df['Birth'].str.strip()
    exclude = ['Player', 'Pos', 'Tm', 'Birth', 'College', 'Team']
    for col in list(df.columns):
        if col in exclude:
            continue
        try:
            converted = pd.to_numeric(df[col], errors='coerce')
            orig_non_null = df[col].notna().sum()
            coerced_non_null = converted.notna().sum()
            if orig_non_null == 0 or coerced_non_null >= orig_non_null / 2:
                df[col] = converted
        except Exception:
            pass
    return df

def find_table_by_id(all_tables: List[BeautifulSoup], table_id: str):
    for t in all_tables:
        tid = (t.get('id') or '').strip()
        if tid == table_id:
            return t
    return None

def safe_sheet_name(name: str, used: set) -> str:
    base = str(name)[:31]
    candidate = base
    idx = 1
    while candidate in used:
        suffix = f"_{idx}"
        max_base = 31 - len(suffix)
        candidate = (base[:max_base] + suffix)
        idx += 1
    used.add(candidate)
    return candidate

def scrape_team(team_abbr: str, season: str, driver, header_sep: str, overwrite: bool=False):
    url = f"https://www.basketball-reference.com/teams/{team_abbr}/{season}.html"
    
    # Create folder structure: TEAM
    team_dir = os.path.join(BASE_OUTPUT_DIR, team_abbr)
    os.makedirs(team_dir, exist_ok=True)

    json_output_path = os.path.join(team_dir, f"{team_abbr}_{season}_NBA_Stats.json")
    if os.path.exists(json_output_path) and not overwrite:
        print(f"  - Skipping {team_abbr}: JSON file already exists at {json_output_path}")
        return {"status": "skipped", "team": team_abbr}

    print(f"\n--- Processing {team_abbr} ({url}) ---")
    try:
        driver.get(url)
        time.sleep(1.5)  # short wait for page load
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        page_title = (soup.title.string or "").lower()
        if "page not found" in page_title or "404" in page_title:
            print(f"  ! Page not found for {team_abbr} {season}")
            return {"status": "not_found", "team": team_abbr}

        visible_tables = soup.find_all('table')
        comment_tables = []
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            if '<table' in comment:
                parsed = BeautifulSoup(comment, 'html.parser')
                for t in parsed.find_all('table'):
                    comment_tables.append(t)
        all_tables = visible_tables + comment_tables
        print(f"  Found {len(all_tables)} tables (including commented tables)")

        # Print detected tables briefly
        for idx, table in enumerate(all_tables):
            table_id = (table.get('id') or f'no-id-{idx}').strip()
            rows = len(table.find_all('tr'))
            print(f"    - {table_id:25} ({rows} rows)")

        all_team_data = {}
        successful_files = []

        for table_id in TABLES_TO_EXTRACT:
            friendly_name = TABLE_NAME_MAP.get(table_id, table_id)
            table_element = find_table_by_id(all_tables, table_id)
            if not table_element:
                print(f"    ✗ {table_id:25} - Not found")
                continue
            try:
                df = pd.read_html(StringIO(str(table_element)))[0]
                df = clean_dataframe(df, friendly_name, sep=header_sep)
                df = normalize_dataframe_columns(df, sep=header_sep)
                if len(df) < 1:
                    print(f"    ⚠ {friendly_name:25} - Empty, skipping")
                    continue

                # Convert to list of dicts
                all_team_data[friendly_name] = df.to_dict(orient='records')
                print(f"    ✓ {friendly_name:25} - Extracted ({len(df)} rows)")

                # small pause between tables
                time.sleep(random.uniform(0.3, 0.9))

            except Exception as e:
                print(f"    ✗ {friendly_name:25} - ERROR processing: {e}")

        # Save single JSON file
        if all_team_data:
            try:
                with open(json_output_path, "w", encoding="utf-8") as f:
                    json.dump(all_team_data, f, indent=2, ensure_ascii=False)
                print(f"  ✓ Saved single JSON: {json_output_path}")
                successful_files.append(json_output_path)
            except Exception as e:
                print(f"  ✗ Failed to save JSON for {team_abbr}: {e}")

        return {"status": "done", "team": team_abbr, "files": successful_files}

    except Exception as e:
        print(f"  ✗ Unexpected error for {team_abbr}: {e}")
        return {"status": "error", "team": team_abbr, "error": str(e)}

def main():
    season = input(f"Enter season year (YYYY) [2025]: ").strip() or "2025"
    header_sep = input(f"Header separator (default '{DEFAULT_HEADER_SEP}'): ").strip() or DEFAULT_HEADER_SEP
    overwrite_input = input("Overwrite existing files if present? (y/N): ").strip().lower() or "n"
    overwrite = overwrite_input.startswith('y')

    teams_input = input("Enter comma-separated team abbreviations or 'all' for all teams [all]: ").strip().upper() or "ALL"
    if teams_input in ("ALL", "ALL_TEAMS", "ALLTEAMS"):
        teams = ALL_TEAMS
    else:
        teams = [t.strip() for t in teams_input.split(',') if t.strip()]

    print(f"\nWill scrape {len(teams)} teams for season {season}. Overwrite={overwrite}.")
    print("Starting Selenium Chrome driver (headless)...")
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    # Optional: reduce logging
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    results = []
    try:
        for idx, team in enumerate(teams, start=1):
            print(f"\n==== ({idx}/{len(teams)}) {team} ====")
            res = scrape_team(team, season, driver, header_sep, overwrite=overwrite)
            results.append(res)
            sleep_time = random.uniform(SLEEP_MIN, SLEEP_MAX)
            print(f"Sleeping {sleep_time:.1f}s before next team...")
            time.sleep(sleep_time)
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    # summary
    done = [r for r in results if r.get("status") == "done"]
    skipped = [r for r in results if r.get("status") == "skipped"]
    not_found = [r for r in results if r.get("status") == "not_found"]
    errors = [r for r in results if r.get("status") == "error"]

    print("\n" + "=" * 60)
    print("RUN SUMMARY")
    print("=" * 60)
    print(f"Total teams processed: {len(results)}")
    print(f" - completed: {len(done)}")
    print(f" - skipped (already exist): {len(skipped)}")
    print(f" - page not found: {len(not_found)}")
    print(f" - errors: {len(errors)}")
    if done:
        print("\nExample successful team outputs (first 5):")
        for r in done[:5]:
            print("  -", r.get("team"), "files:", len(r.get("files", [])))
    if errors:
        print("\nErrors (first 5):")
        for e in errors[:5]:
            print("  -", e.get("team"), e.get("error"))

if __name__ == "__main__":
    main()