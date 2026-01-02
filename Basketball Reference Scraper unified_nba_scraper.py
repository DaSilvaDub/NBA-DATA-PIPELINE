import sys
import os
import time
import json
import re
import random
import argparse
from io import StringIO
from typing import List, Dict, Optional, Union

import pandas as pd
from bs4 import BeautifulSoup, Comment
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# ==========================================
# CONFIGURATION & CONSTANTS
# ==========================================

DEFAULT_SEASON = "2025"
DEFAULT_HEADER_SEP = "_"
# Default output directory - strictly using the path found in your original scripts
DEFAULT_OUTPUT_DIR = r"C:\Users\dasil\My Drive (dasilvadub@gmail.com)\NBA\TEAMS"

ALL_TEAMS = [
    'ATL', 'BKN', 'BOS', 'CHA', 'CHI', 'CLE', 'DAL', 'DEN', 'DET', 'GSW',
    'HOU', 'IND', 'LAC', 'LAL', 'MEM', 'MIA', 'MIL', 'MIN', 'NOP', 'NYK',
    'OKC', 'ORL', 'PHI', 'PHX', 'POR', 'SAC', 'SAS', 'TOR', 'UTA', 'WAS'
]

# Map known table IDs to the specific names requested by the user.
TABLE_NAME_MAP = {
    'roster': 'Roster',
    'team_and_opponent': 'Team_and_Opponent_Stats',
    'team_misc': 'Team_Misc',
    'per_game_stats': 'Per_Game',
    'totals_stats': 'Totals',
    'per_minute_stats': 'Per_36',        # "per 36"
    'per_poss': 'Per_100',               # "per 100"
    'per_poss_stats': 'Per_100',         # Variance handling
    'advanced': 'Advanced',
    'advanced_stats': 'Advanced',        # Variance handling
    'adj_shooting': 'Adjusted_Shooting',
    'shooting': 'Shooting',
    'pbp_stats': 'Play_by_Play'
}

# Canonical column mapping
CANONICAL_COLUMNS = {
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

class BasketballScraper:
    def __init__(self, output_dir: str = DEFAULT_OUTPUT_DIR, season: str = DEFAULT_SEASON,
                 header_sep: str = DEFAULT_HEADER_SEP, headless: bool = True):
        self.output_dir = output_dir
        self.season = season
        self.header_sep = header_sep
        self.headless = headless
        self.driver = None

        # Ensure output directory exists
        if not os.path.exists(self.output_dir):
            try:
                os.makedirs(self.output_dir)
            except OSError:
                print(f"Warning: Could not create base directory {self.output_dir}. Using current directory.")
                self.output_dir = "."

    def _setup_driver(self):
        """Initializes the Selenium Chrome Driver."""
        print("✓ Starting Chrome browser...")
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument('--headless=new')

        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.page_load_strategy = 'normal'

        # Suppress logging
        chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])

        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.set_page_load_timeout(180)
        except Exception as e:
            print(f"Error initializing driver: {e}")
            sys.exit(1)

    def _teardown_driver(self):
        """Closes the Selenium Driver."""
        if self.driver:
            print("Closing browser...")
            self.driver.quit()
            self.driver = None

    def _flatten_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Flattens MultiIndex columns."""
        cols = df.columns
        if isinstance(cols, pd.MultiIndex):
            new_cols = []
            for col in cols:
                parts = [str(c).strip() for c in col if (c is not None and str(c).strip() != '')]
                joined = self.header_sep.join(parts) if parts else ""
                new_cols.append(joined)

            # Ensure uniqueness
            seen = {}
            unique_cols = []
            for c in new_cols:
                base = c if c != "" else "Unnamed"
                if base in seen:
                    seen[base] += 1
                    unique = f"{base}{self.header_sep}{seen[base]}"
                else:
                    seen[base] = 0
                    unique = base
                unique_cols.append(unique)
            df.columns = unique_cols
        else:
            df.columns = [str(c).strip() for c in df.columns]
        return df

    def _normalize_column_name(self, col: str) -> str:
        """Normalizes a single column name using canonical mapping."""
        s = str(col).strip()
        s = re.sub(r'Unnamed.*', '', s, flags=re.IGNORECASE).strip(self.header_sep + " ")
        s = re.sub(r'level_\d+_', '', s)
        s = re.sub(r'\s+', self.header_sep, s)
        s_lower = s.lower()

        for token in sorted(CANONICAL_COLUMNS.keys(), key=lambda x: -len(x)):
            if token in s_lower:
                return CANONICAL_COLUMNS[token]

        if '%' in s:
            s = s.replace('%', '_pct')

        s = re.sub(r'{0}+'.format(re.escape(self.header_sep)), self.header_sep, s)
        s = s.strip(self.header_sep)
        return s or 'Unnamed'

    def _normalize_dataframe_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Applies column normalization to the entire DataFrame."""
        new_cols = [self._normalize_column_name(c) for c in df.columns]
        seen = {}
        final_cols = []
        for name in new_cols:
            base = name or "Unnamed"
            if base in seen:
                seen[base] += 1
                unique = f"{base}{self.header_sep}{seen[base]}"
            else:
                seen[base] = 0
                unique = base
            final_cols.append(unique)
        df.columns = final_cols
        return df

    def _clean_dataframe(self, df: pd.DataFrame, table_name: str) -> pd.DataFrame:
        """Cleans data issues common to Basketball Reference."""
        df = self._flatten_columns(df)

        # Remove repeating header rows
        if 'Player' in df.columns:
            df = df[df['Player'] != 'Player'].copy()
        if 'Rk' in df.columns:
            df = df[df['Rk'] != 'Rk'].copy()

        # Specific Roster cleaning
        if table_name == "Roster":
            if 'Birth Date' in df.columns:
                df['Birth Date'] = pd.to_datetime(df['Birth Date'], errors='coerce').dt.strftime('%m/%d/%Y')
            if 'Birth' in df.columns:
                df['Birth'] = df['Birth'].astype(str).str.replace('us US', 'US', case=False, regex=False)
                df['Birth'] = df['Birth'].astype(str).str.replace('US US', 'US', case=False, regex=False)
                df['Birth'] = df['Birth'].str.strip()

        # Numeric conversion
        exclude = ['Player', 'Pos', 'Tm', 'Birth', 'College', 'Team']
        for col in df.columns:
            if col in exclude:
                continue
            try:
                converted = pd.to_numeric(df[col], errors='coerce')
                orig_non_null = df[col].notna().sum()
                coerced_non_null = converted.notna().sum()
                # Only keep conversion if we didn't lose too much data (heuristic)
                if orig_non_null == 0 or coerced_non_null >= orig_non_null / 2:
                    df[col] = converted
            except Exception:
                pass
        return df

    def scrape_team(self, team_abbr: str, retry_count: int = 3) -> Optional[Dict]:
        """Scrapes a single team's data and returns it as a dict."""
        if not self.driver:
            self._setup_driver()

        team_abbr = team_abbr.upper()
        url = f"https://www.basketball-reference.com/teams/{team_abbr}/{self.season}.html"
        team_dir = os.path.join(self.output_dir, team_abbr)
        os.makedirs(team_dir, exist_ok=True)

        print(f"\n--- Processing {team_abbr} ({self.season}) ---")
        print(f"Loading: {url}")

        page_source = None
        for attempt in range(retry_count):
            try:
                self.driver.get(url)
                time.sleep(3)
                page_source = self.driver.page_source
                break
            except Exception as e:
                print(f"⚠ Attempt {attempt + 1} failed: {e}")
                time.sleep(5)

        if not page_source:
            print(f"✗ Failed to load page for {team_abbr}")
            return None

        soup = BeautifulSoup(page_source, 'html.parser')

        # Check for 404
        page_title = (soup.title.string or "").lower()
        if "page not found" in page_title or "404" in page_title:
            print(f"✗ Page not found for {team_abbr} {self.season}")
            return None

        # Extract tables (visible + commented)
        visible_tables = soup.find_all('table')
        comment_tables = []
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            if '<table' in comment:
                parsed = BeautifulSoup(comment, 'html.parser')
                for t in parsed.find_all('table'):
                    comment_tables.append(t)

        all_tables = visible_tables + comment_tables
        print(f"✓ Found {len(all_tables)} total tables (visible + hidden)")

        all_team_data = {}

        # Iterate through EVERY table found
        for i, table_element in enumerate(all_tables):
            # Get table ID or generate a generic one
            raw_id = (table_element.get('id') or '').strip()

            # Determine the key to use in the JSON
            # 1. Check if ID matches our specific map (PRIORITY)
            if raw_id in TABLE_NAME_MAP:
                friendly_name = TABLE_NAME_MAP[raw_id]
            # 2. If valid ID but not in map, use ID
            elif raw_id:
                friendly_name = raw_id
            # 3. Fallback
            else:
                friendly_name = f"Unidentified_Table_{i}"

            try:
                # Use StringIO to parse the HTML table
                df = pd.read_html(StringIO(str(table_element)))[0]

                # Perform cleaning
                df = self._clean_dataframe(df, friendly_name)
                df = self._normalize_dataframe_columns(df)

                # Skip empty dataframes
                if len(df) < 1:
                    continue

                # Add to data dictionary
                all_team_data[friendly_name] = df.to_dict(orient='records')
                print(f"  ✓ {friendly_name:25} - Extracted ({len(df)} rows)")

            except Exception as e:
                # Log errors but don't stop the whole process
                print(f"  ⚠ Skipped {friendly_name}: {e}")

        # Save Individual Team JSON
        if all_team_data:
            json_path = os.path.join(team_dir, f"{team_abbr}_{self.season}_NBA_Stats.json")
            try:
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(all_team_data, f, indent=2, ensure_ascii=False)
                print(f"✅ Saved JSON: {json_path}")
                return all_team_data
            except Exception as e:
                print(f"✗ Failed to save JSON: {e}")
                return None
        else:
            print(f"✗ No data extracted for {team_abbr}")
            return None

    def run(self, mode: str, teams: List[str] = None):
        try:
            target_teams = []
            if mode == 'single':
                target_teams = teams
            elif mode == 'all':
                target_teams = ALL_TEAMS
            elif mode == 'retry':
                target_teams = teams if teams else ['BKN', 'CHA', 'DEN', 'DET', 'PHX']

            print(f"Starting scraping for {len(target_teams)} teams in mode: {mode}")

            # Dictionary to store all data if running multiple teams
            aggregated_data = {}

            for i, team in enumerate(target_teams):
                team_data = self.scrape_team(team)

                if team_data:
                    aggregated_data[team] = team_data

                # Sleep to be polite to the server
                if i < len(target_teams) - 1:
                    sleep_time = random.uniform(2.0, 5.0)
                    print(f"Sleeping {sleep_time:.1f}s...")
                    time.sleep(sleep_time)

            # If we scraped multiple teams, save a combined JSON output
            if len(aggregated_data) > 0 and mode in ['all', 'retry']:
                combined_path = os.path.join(self.output_dir, f"ALL_TEAMS_{self.season}_NBA_Stats.json")
                try:
                    print(f"\n--- Saving Combined JSON ---")
                    with open(combined_path, "w", encoding="utf-8") as f:
                        json.dump(aggregated_data, f, indent=2, ensure_ascii=False)
                    print(f"✅ Saved Combined JSON: {combined_path}")
                except Exception as e:
                    print(f"✗ Failed to save combined JSON: {e}")

        finally:
            self._teardown_driver()

# ==========================================
# MAIN ENTRY POINT
# ==========================================

if __name__ == "__main__":
    # Fix encoding for Windows console
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')

    parser = argparse.ArgumentParser(description="Unified NBA Stats Scraper")

    parser.add_argument('--mode', choices=['single', 'all', 'retry'], default='single',
                        help="Scraping mode: 'single' (one team), 'all' (all 30 teams), or 'retry' (specific list)")

    parser.add_argument('--team', type=str, help="Team abbreviation (e.g., DET) for single mode")

    parser.add_argument('--teams', type=str, help="Comma separated list of teams for retry mode (e.g., 'DET,BKN')")

    parser.add_argument('--season', type=str, default=DEFAULT_SEASON,
                        help=f"Season year (default: {DEFAULT_SEASON})")

    parser.add_argument('--output', type=str, default=DEFAULT_OUTPUT_DIR,
                        help="Base output directory")

    parser.add_argument('--visible', action='store_true', help="Run with visible browser (not headless)")

    # Handle Colab/Jupyter specific arguments to prevent argparse errors
    args, unknown = parser.parse_known_args()


    # Handle team input
    team_list = []

    # INTERACTIVE MODE
    # If mode is default (single) and no specific team is passed, prompt the user.
    if args.mode == 'single' and args.team is None:
        print(f"\n--- NBA Stats Scraper ({args.season}) ---")
        print("Please select teams to scrape:")
        print("1. Enter 'ALL' for all 30 teams.")
        print("2. Enter team abbreviations separated by commas (e.g. LAL, BOS).")
        print("3. Press Enter for default (DET).")

        user_input = input("\nSelection: ").strip().upper()

        if user_input in ['ALL', 'ALL TEAMS', 'EVERYONE']:
            args.mode = 'all'
            team_list = ALL_TEAMS
        elif ',' in user_input or len(user_input) > 0:
            # Assume it is a list of teams or a single team code
            args.mode = 'retry' # 'retry' here just means 'custom list'
            team_list = [t.strip() for t in user_input.split(',') if t.strip()]
        else:
            # Default empty input
            args.mode = 'single'
            team_list = ['DET']

    # COMMAND LINE ARGUMENT MODE
    elif args.mode == 'single' and args.team:
        team_list = [args.team]

    elif args.mode == 'retry':
        if args.teams:
            team_list = [t.strip().upper() for t in args.teams.split(',')]
        else:
            team_list = ['BKN', 'CHA', 'DEN', 'DET', 'PHX']

    # Initialize and run
    scraper = BasketballScraper(
        output_dir=args.output,
        season=args.season,
        headless=not args.visible
    )

    scraper.run(mode=args.mode, teams=team_list)
