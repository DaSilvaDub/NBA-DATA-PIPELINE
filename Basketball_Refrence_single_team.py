import sys

# Copy all imports and functions from the original script
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup, Comment
import pandas as pd
from io import StringIO
import time
import os
import json
import re

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

DEFAULT_HEADER_SEP = "_"
BASE_OUTPUT_DIR = r"C:\Users\dasil\My Drive (dasilvadub@gmail.com)\NBA\TEAMS"

# Get team abbreviation from command line
# Note: Basketball-Reference uses the ending year of the season (e.g., 2026 for 2025-26 season)
if len(sys.argv) < 2:
    print("Usage: python Basketball_Refrence_single_team.py <TEAM_ABBR> [SEASON]")
    print("Example: python Basketball_Refrence_single_team.py BRK 2026")
    sys.exit(1)

team_abbr = sys.argv[1].upper()
season = sys.argv[2] if len(sys.argv) > 2 else "2026"
HEADER_SEP = DEFAULT_HEADER_SEP

print(f"Processing {team_abbr} for {season} season...")

# Helper functions
def flatten_columns(df, sep=HEADER_SEP):
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

def clean_dataframe(df, table_name):
    df = flatten_columns(df, sep=HEADER_SEP)
    if 'Player' in df.columns:
        df = df[df['Player'] != 'Player'].copy()
    if 'Rk' in df.columns:
        df = df[df['Rk'] != 'Rk'].copy()

    if table_name == "Roster":
        if 'Birth Date' in df.columns:
            df.loc[:, 'Birth Date'] = pd.to_datetime(df['Birth Date'], errors='coerce').dt.strftime('%m/%d/%Y')
        if 'Birth' in df.columns:
            df.loc[:, 'Birth'] = df['Birth'].astype(str).str.replace('us US', 'US', case=False, regex=False)
            df.loc[:, 'Birth'] = df['Birth'].astype(str).str.replace('US US', 'US', case=False, regex=False)
            df.loc[:, 'Birth'] = df['Birth'].str.strip()

    exclude = ['Player', 'Pos', 'Tm', 'Birth', 'College', 'Team']
    for col in df.columns:
        if col in exclude:
            continue
        try:
            converted = pd.to_numeric(df[col], errors='coerce')
            orig_non_null = df[col].notna().sum()
            coerced_non_null = converted.notna().sum()
            if orig_non_null == 0 or coerced_non_null >= orig_non_null / 2:
                df.loc[:, col] = converted
        except Exception:
            pass
    return df

# Setup Chrome
chrome_options = Options()
chrome_options.add_argument('--headless=new')
chrome_options.add_argument('--disable-gpu')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')

print("Starting Chrome browser...")
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)
driver.set_page_load_timeout(180)

url = f"https://www.basketball-reference.com/teams/{team_abbr}/{season}.html"
team_dir = os.path.join(BASE_OUTPUT_DIR, team_abbr)
os.makedirs(team_dir, exist_ok=True)

print(f"Loading: {url}")

try:
    driver.get(url)
    time.sleep(3)
    page_source = driver.page_source

    soup = BeautifulSoup(page_source, 'html.parser')
    page_title = (soup.title.string or "").lower()

    if "page not found" in page_title or "404" in page_title:
        print(f"Page not found for {team_abbr} {season}")
        driver.quit()
        sys.exit(1)

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

    all_team_data = {}
    json_output_path = os.path.join(team_dir, f"{team_abbr}_{season}_NBA_Stats.json")

    for table_id in table_names.keys():
        friendly_name = table_names.get(table_id, table_id)

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
            if len(df) < 1:
                continue
            all_team_data[friendly_name] = df.to_dict(orient='records')
            print(f"  ✓ {friendly_name:25} - Extracted ({len(df)} rows)")
        except Exception as e:
            print(f"  ✗ {friendly_name:25} - ERROR: {str(e)}")

    if all_team_data:
        with open(json_output_path, "w", encoding="utf-8") as f:
            json.dump(all_team_data, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Saved JSON: {json_output_path}")
    else:
        print("\n✗ No data extracted")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    driver.quit()
    print("Done.")
