from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup, Comment
import pandas as pd
from io import StringIO
import time
import os
import sys
import json
import re
import random

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Header separator: change this to "_", " ", ".", "-", etc.
DEFAULT_HEADER_SEP = "_"  

# Base output directory (change this if you want a different root)
BASE_OUTPUT_DIR = r"C:\Users\dasil\My Drive (dasilvadub@gmail.com)\NBA\TEAMS"

# All 30 NBA team abbreviations (using Basketball-Reference.com codes)
ALL_TEAMS = [
    'ATL','BRK','BOS','CHO','CHI','CLE','DAL','DEN','DET','GSW',
    'HOU','IND','LAC','LAL','MEM','MIA','MIL','MIN','NOP','NYK',
    'OKC','ORL','PHI','PHO','POR','SAC','SAS','TOR','UTA','WAS'
]

print("=" * 60)
print("Basketball Reference - All Teams Extraction")
print("=" * 60)

# Ask user for season (use command-line arg or default)
# Note: Basketball-Reference uses the ending year of the season (e.g., 2026 for 2025-26 season)
default_season = "2026"
if len(sys.argv) > 1:
    season = sys.argv[1]
else:
    try:
        season = input(f"Enter season year (YYYY) [{default_season}]: ").strip() or default_season
    except EOFError:
        season = default_season
        print(f"Using default season: {season}")

# Ask user for header separator (optional)
if len(sys.argv) > 2:
    HEADER_SEP = sys.argv[2]
else:
    try:
        header_sep_input = input(f"Header separator (default '{DEFAULT_HEADER_SEP}'). Press Enter to keep default: ").strip()
        HEADER_SEP = header_sep_input if header_sep_input != "" else DEFAULT_HEADER_SEP
    except EOFError:
        HEADER_SEP = DEFAULT_HEADER_SEP
        print(f"Using default header separator: '{HEADER_SEP}'")

print(f"\nFiles will be saved to: {BASE_OUTPUT_DIR}\\<TEAM_ABBR>")
print(f"Using header separator: '{HEADER_SEP}'\n")

# Setup Chrome options
chrome_options = Options()
chrome_options.add_argument('--headless')
chrome_options.add_argument('--disable-gpu')
chrome_options.add_argument('--no-sandbox')
chrome_options.page_load_strategy = 'normal'

# Initialize the driver
print("✓ Starting Chrome browser...")
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)
driver.set_page_load_timeout(180)  # Increase timeout to 3 minutes

# Helper to flatten MultiIndex columns and make unique names
def flatten_columns(df, sep=HEADER_SEP):
    cols = df.columns
    if isinstance(cols, pd.MultiIndex):
        new_cols = []
        for col in cols:
            # col is a tuple; join non-empty parts using sep
            parts = [str(c).strip() for c in col if (c is not None and str(c).strip() != '')]
            joined = sep.join(parts) if parts else ""
            new_cols.append(joined)
        # Ensure uniqueness
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
        # strip whitespace from single-level columns
        df.columns = [str(c).strip() for c in df.columns]
    return df

# Canonical mapping to produce human/machine friendly column names
CANONICAL = {
    'player': 'Player', 'name': 'Player', 'age': 'Age', 'pos': 'Pos', 'team': 'Team',
    'g': 'G', 'gs': 'GS', 'mp': 'MP', 'mp_per_g': 'MP_per_G',
    'fg%': 'FG_pct', 'fg pct': 'FG_pct', 'fg': 'FG',
    '2p%': '2P_pct', '2p pct': '2P_pct', '3p%': '3P_pct', '3p pct': '3P_pct',
    'fg3a': 'FG3A', 'fg3': 'FG3', 'fg3_pct': 'FG3_pct', 'fg_pct': 'FG_pct',
    'efg%': 'eFG_pct', 'ts%': 'TS_pct',
    'ft': 'FT', 'fta': 'FTA', 'ft%': 'FT_pct', 'ft_pct': 'FT_pct',
    'orb': 'ORB', 'drb': 'DRB', 'trb': 'TRB', 'ast': 'AST', 'stl': 'STL', 'blk': 'BLK',
    'tov': 'TOV', 'pf': 'PF', 'pts': 'PTS',
    'per': 'PER', 'ortg': 'ORtg', 'drtg': 'DRtg', 'usg%': 'USG_pct', 'ws': 'WS', 'ws/48': 'WS_per_48',
    '%': '_pct'
}

def normalize_column_name(col, sep=HEADER_SEP):
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

def normalize_dataframe_columns(df, sep=HEADER_SEP):
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

# Function to clean and format data
def clean_dataframe(df, table_name):
    """Clean up common issues in basketball reference tables"""
    # Flatten MultiIndex columns if needed
    df = flatten_columns(df, sep=HEADER_SEP)

    # Remove rows where player name is "Player" (header rows)
    if 'Player' in df.columns:
        df = df[df['Player'] != 'Player']

    # Remove rows that are just repeating headers
    if 'Rk' in df.columns:
        df = df[df['Rk'] != 'Rk']

    # For roster table
    if table_name == "Roster":
        if 'Birth Date' in df.columns:
            df['Birth Date'] = pd.to_datetime(df['Birth Date'], errors='coerce').dt.strftime('%m/%d/%Y')
        if 'Birth' in df.columns:
            df['Birth'] = df['Birth'].astype(str).str.replace('us US', 'US', case=False, regex=False)
            df['Birth'] = df['Birth'].astype(str).str.replace('US US', 'US', case=False, regex=False)
            df['Birth'] = df['Birth'].str.strip()

    # Convert numeric columns (attempt numeric conversion safely)
    exclude = ['Player', 'Pos', 'Tm', 'Birth', 'College', 'Team']
    for col in df.columns:
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

def process_team(team_abbr, max_retries=3):
    url = f"https://www.basketball-reference.com/teams/{team_abbr}/{season}.html"

    # Derive final output directories
    team_dir = os.path.join(BASE_OUTPUT_DIR, team_abbr)
    try:
        os.makedirs(team_dir, exist_ok=True)
    except Exception as e:
        print(f"Error creating output directory '{team_dir}': {e}")
        return

    print(f"\n--- Processing {team_abbr} ---")
    print(f"✓ Loading: {url}")

    page_source = None
    for attempt in range(max_retries):
        try:
            driver.get(url)
            time.sleep(3)  # Increased wait time
            page_source = driver.page_source
            break
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"⚠ Attempt {attempt + 1} failed, retrying... ({e})")
                time.sleep(5)  # Wait before retry
            else:
                print(f"✗ Error loading page after {max_retries} attempts: {e}")
                return

    # Parse with BeautifulSoup
    soup = BeautifulSoup(page_source, 'html.parser')

    # Quick check
    page_title = (soup.title.string or "").lower()
    if "page not found" in page_title or "404" in page_title:
        print(f"✗ Page not found for {team_abbr} {season}")
        return

    # Basketball-Reference sometimes puts tables inside HTML comments.
    visible_tables = soup.find_all('table')
    comment_tables = []
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        if '<table' in comment:
            parsed = BeautifulSoup(comment, 'html.parser')
            for t in parsed.find_all('table'):
                comment_tables.append(t)
    all_tables = visible_tables + comment_tables
    print(f"✓ Found {len(all_tables)} tables")

    # Debug: show available table IDs
    available_ids = [t.get('id') for t in all_tables if t.get('id')]
    print(f"  Available table IDs: {available_ids}")

    # Map table IDs to readable names
    # Basketball-Reference table IDs for team pages
    table_names = {
        'roster': 'Roster',
        'team_and_opponent': 'Team_and_Opponent',
        'team_misc': 'Team_Misc',
        'per_game': 'per_game_stats',
        'per_game_stats': 'per_game_stats',
        'totals': 'totals_stats',
        'totals_stats': 'totals_stats',
        'per_minute': 'per_minute_stats',
        'per_minute_stats': 'per_minute_stats',
        'per_poss': 'Per_100_Poss',
        'advanced': 'Advanced',
        'adj_shooting': 'Adjusted_Shooting',
        'shooting': 'Shooting',
        'pbp': 'pbp_stats',
        'pbp_stats': 'pbp_stats'
    }
    
    tables_to_extract = list(table_names.keys())

    all_team_data = {}
    json_output_path = os.path.join(team_dir, f"{team_abbr}_{season}_NBA_Stats.json")

    for table_id in tables_to_extract:
        friendly_name = table_names.get(table_id, table_id)
        
        # Find table
        table_element = None
        for t in all_tables:
            if (t.get('id') or '').strip() == table_id:
                table_element = t
                break

        if not table_element:
            continue

        try:
            df = pd.read_html(StringIO(str(table_element)))[0]
            df = clean_dataframe(df, friendly_name)
            df = normalize_dataframe_columns(df, sep=HEADER_SEP)
            if len(df) < 1: continue
            all_team_data[friendly_name] = df.to_dict(orient='records')
            print(f"    ✓ {friendly_name:25} - Extracted ({len(df)} rows)")
        except Exception as e:
            print(f"    ✗ {friendly_name:25} - ERROR: {str(e)}")

    if all_team_data:
        try:
            with open(json_output_path, "w", encoding="utf-8") as f:
                json.dump(all_team_data, f, indent=2, ensure_ascii=False)
            print(f"  ✅ Saved JSON: {json_output_path}")
        except Exception as e:
            print(f"  ✗ Failed to save JSON file: {e}")

# Main Loop
try:
    for i, team in enumerate(ALL_TEAMS):
        process_team(team)
        if i < len(ALL_TEAMS) - 1:
            time.sleep(random.uniform(2.0, 4.0))
finally:
    print("\nClosing browser...")
    driver.quit()
    print("Done.")