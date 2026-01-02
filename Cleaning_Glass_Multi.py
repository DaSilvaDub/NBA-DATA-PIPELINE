"""
Cleaning The Glass NBA Team Data Scraper - MULTI-TEAM VERSION
==============================================================
Scrape multiple teams at once by providing comma-separated abbreviations.

Usage:
  python Cleaning_Glass_Multi.py LAL,BOS,MIA        # Scrape Lakers, Celtics, Heat
  python Cleaning_Glass_Multi.py LAL,BOS --headless # Run without browser window
  python Cleaning_Glass_Multi.py ALL                # Scrape all 30 teams

Requires: selenium, pandas, webdriver-manager, openpyxl
Install: pip install selenium pandas webdriver-manager openpyxl --break-system-packages
"""

import os
import sys
import time
import json

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import pandas as pd
from io import StringIO
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.common.action_chains import ActionChains

# Configuration
BASE_OUTPUT_DIR = r"C:\Users\dasil\My Drive (dasilvadub@gmail.com)\NBA\TEAMS"

# Team mappings
TEAMS = {
    "ATL": {"id": 1, "name": "Atlanta Hawks", "slug": "atlanta_hawks"},
    "BOS": {"id": 2, "name": "Boston Celtics", "slug": "boston_celtics"},
    "BKN": {"id": 3, "name": "Brooklyn Nets", "slug": "brooklyn_nets"},
    "CHA": {"id": 4, "name": "Charlotte Hornets", "slug": "charlotte_hornets"},
    "CHI": {"id": 5, "name": "Chicago Bulls", "slug": "chicago_bulls"},
    "CLE": {"id": 6, "name": "Cleveland Cavaliers", "slug": "cleveland_cavaliers"},
    "DAL": {"id": 7, "name": "Dallas Mavericks", "slug": "dallas_mavericks"},
    "DEN": {"id": 8, "name": "Denver Nuggets", "slug": "denver_nuggets"},
    "DET": {"id": 9, "name": "Detroit Pistons", "slug": "detroit_pistons"},
    "GSW": {"id": 10, "name": "Golden State Warriors", "slug": "golden_state_warriors"},
    "HOU": {"id": 11, "name": "Houston Rockets", "slug": "houston_rockets"},
    "IND": {"id": 12, "name": "Indiana Pacers", "slug": "indiana_pacers"},
    "LAC": {"id": 13, "name": "LA Clippers", "slug": "la_clippers"},
    "LAL": {"id": 14, "name": "Los Angeles Lakers", "slug": "los_angeles_lakers"},
    "MEM": {"id": 15, "name": "Memphis Grizzlies", "slug": "memphis_grizzlies"},
    "MIA": {"id": 16, "name": "Miami Heat", "slug": "miami_heat"},
    "MIL": {"id": 17, "name": "Milwaukee Bucks", "slug": "milwaukee_bucks"},
    "MIN": {"id": 18, "name": "Minnesota Timberwolves", "slug": "minnesota_timberwolves"},
    "NOP": {"id": 19, "name": "New Orleans Pelicans", "slug": "new_orleans_pelicans"},
    "NYK": {"id": 20, "name": "New York Knicks", "slug": "new_york_knicks"},
    "OKC": {"id": 21, "name": "Oklahoma City Thunder", "slug": "oklahoma_city_thunder"},
    "ORL": {"id": 22, "name": "Orlando Magic", "slug": "orlando_magic"},
    "PHI": {"id": 23, "name": "Philadelphia 76ers", "slug": "philadelphia_76ers"},
    "PHX": {"id": 24, "name": "Phoenix Suns", "slug": "phoenix_suns"},
    "POR": {"id": 25, "name": "Portland Trail Blazers", "slug": "portland_trail_blazers"},
    "SAC": {"id": 26, "name": "Sacramento Kings", "slug": "sacramento_kings"},
    "SAS": {"id": 27, "name": "San Antonio Spurs", "slug": "san_antonio_spurs"},
    "TOR": {"id": 28, "name": "Toronto Raptors", "slug": "toronto_raptors"},
    "UTA": {"id": 29, "name": "Utah Jazz", "slug": "utah_jazz"},
    "WAS": {"id": 30, "name": "Washington Wizards", "slug": "washington_wizards"},
}


# Define tabs to scrape for Game Logs page
GAMELOG_TABS = [
    {"id": "four_factors", "name": "Team Efficiency and Four Factors"},
    {"id": "offense_halfcourt", "name": "Offense - Halfcourt and Putbacks"},
    {"id": "offense_transition", "name": "Offense - Transition"},
    {"id": "offense_shooting_frequency", "name": "Offense - Shooting Frequency"},
    {"id": "offense_shooting_accuracy", "name": "Offense - Shooting Accuracy"},
    {"id": "defense_halfcourt", "name": "Defense - Halfcourt and Putbacks"},
    {"id": "defense_transition", "name": "Defense - Transition"},
    {"id": "defense_shooting_frequency", "name": "Defense - Shooting Frequency"},
    {"id": "defense_shooting_accuracy", "name": "Defense - Shooting Accuracy"},
]

# Define tabs to scrape for Team Overall Stats page
STATS_TABS = [
    {"id": "four_factors", "name": "Team Efficiency and Four Factors"},
    {"id": "offense_halfcourt", "name": "Offense - Halfcourt and Putbacks"},
    {"id": "offense_transition", "name": "Offense - Transition"},
    {"id": "offense_shooting_frequency", "name": "Offense - Shooting Frequency"},
    {"id": "offense_shooting_accuracy", "name": "Offense - Shooting Accuracy"},
    {"id": "defense_halfcourt", "name": "Defense - Halfcourt and Putbacks"},
    {"id": "defense_transition", "name": "Defense - Transition"},
    {"id": "defense_shooting_frequency", "name": "Defense - Shooting Frequency"},
    {"id": "defense_shooting_accuracy", "name": "Defense - Shooting Accuracy"},
]

# Define tabs to scrape for Lineups page
LINEUPS_TABS = [
    {"id": "four_factors", "name": "Lineups - Four Factors"},
    {"id": "offense_halfcourt", "name": "Lineups - Offense Halfcourt"},
    {"id": "offense_transition", "name": "Lineups - Offense Transition"},
    {"id": "offense_shooting_frequency", "name": "Lineups - Offense Shooting Frequency"},
    {"id": "offense_shooting_accuracy", "name": "Lineups - Offense Shooting Accuracy"},
    {"id": "defense_halfcourt", "name": "Lineups - Defense Halfcourt"},
    {"id": "defense_transition", "name": "Lineups - Defense Transition"},
    {"id": "defense_shooting_frequency", "name": "Lineups - Defense Shooting Frequency"},
    {"id": "defense_shooting_accuracy", "name": "Lineups - Defense Shooting Accuracy"},
]

# Define tabs to scrape for On/Off Stats page
ONOFF_TABS = [
    {"id": "four_factors", "name": "On/Off - Four Factors"},
    {"id": "offense_halfcourt", "name": "On/Off - Offense Halfcourt"},
    {"id": "offense_transition", "name": "On/Off - Offense Transition"},
    {"id": "offense_shooting_frequency", "name": "On/Off - Offense Shooting Frequency"},
    {"id": "offense_shooting_accuracy", "name": "On/Off - Offense Shooting Accuracy"},
    {"id": "defense_halfcourt", "name": "On/Off - Defense Halfcourt"},
    {"id": "defense_transition", "name": "On/Off - Defense Transition"},
    {"id": "defense_shooting_frequency", "name": "On/Off - Defense Shooting Frequency"},
    {"id": "defense_shooting_accuracy", "name": "On/Off - Defense Shooting Accuracy"},
]

# Define tabs to scrape for Player Stats page
PLAYER_TABS = [
    {"id": "four_factors", "name": "Player - Four Factors"},
    {"id": "offense_halfcourt", "name": "Player - Offense Halfcourt"},
    {"id": "offense_transition", "name": "Player - Offense Transition"},
    {"id": "offense_shooting_frequency", "name": "Player - Offense Shooting Frequency"},
    {"id": "offense_shooting_accuracy", "name": "Player - Offense Shooting Accuracy"},
    {"id": "defense_halfcourt", "name": "Player - Defense Halfcourt"},
    {"id": "defense_transition", "name": "Player - Defense Transition"},
    {"id": "defense_shooting_frequency", "name": "Player - Defense Shooting Frequency"},
    {"id": "defense_shooting_accuracy", "name": "Player - Defense Shooting Accuracy"},
]


class CTGScraperV2:
    def __init__(self, headless=False):
        """Initialize Chrome WebDriver"""
        print("🚀 Initializing browser...")

        self.options = Options()
        if headless:
            self.options.add_argument("--headless=new")

        self.options.add_argument("--no-sandbox")
        self.options.add_argument("--disable-dev-shm-usage")
        self.options.add_argument("--window-size=1920,1080")
        self.options.add_argument("--disable-blink-features=AutomationControlled")
        self.options.add_experimental_option("excludeSwitches", ["enable-automation"])
        self.options.add_experimental_option('useAutomationExtension', False)

        try:
            from webdriver_manager.chrome import ChromeDriverManager
            self.driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=self.options
            )
        except Exception as e:
            print(f"WebDriver Manager failed ({e}), trying default Chrome...")
            self.driver = webdriver.Chrome(options=self.options)

        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self.wait = WebDriverWait(self.driver, 15)
        self.short_wait = WebDriverWait(self.driver, 5)
        print("✅ Browser initialized")


    def login_auto(self, email, password):
        """Automatically log in to Cleaning The Glass"""
        print("\n" + "="*60)
        print("  LOGGING IN TO CLEANING THE GLASS")
        print("="*60)

        self.driver.get("https://cleaningtheglass.com/login")
        time.sleep(3)

        try:
            # Find all input fields
            inputs = self.driver.find_elements(By.TAG_NAME, "input")
            email_field = None
            password_field = None

            for inp in inputs:
                inp_type = inp.get_attribute("type") or ""
                inp_name = inp.get_attribute("name") or ""
                inp_id = inp.get_attribute("id") or ""
                inp_placeholder = inp.get_attribute("placeholder") or ""

                if inp_type == "email" or "email" in inp_name.lower() or "email" in inp_id.lower() or "email" in inp_placeholder.lower():
                    email_field = inp
                elif inp_type == "password":
                    password_field = inp
                elif inp_type == "text" and not email_field:
                    # Sometimes email field is type="text"
                    if "email" in inp_placeholder.lower() or "user" in inp_placeholder.lower():
                        email_field = inp

            if email_field:
                email_field.clear()
                email_field.send_keys(email)
                print("📧 Email entered")
            else:
                print("⚠️ Could not find email field, trying first text input...")
                text_inputs = [i for i in inputs if i.get_attribute("type") in ["text", "email"]]
                if text_inputs:
                    text_inputs[0].clear()
                    text_inputs[0].send_keys(email)
                    print("📧 Email entered (fallback)")

            if password_field:
                password_field.clear()
                password_field.send_keys(password)
                print("🔑 Password entered")
            else:
                print("❌ Could not find password field")
                return False

            time.sleep(1)

            # Find and click login button - try multiple methods
            login_clicked = False

            # Method 1: Find button by type
            buttons = self.driver.find_elements(By.CSS_SELECTOR, "button[type='submit'], input[type='submit']")
            for btn in buttons:
                if btn.is_displayed():
                    btn.click()
                    login_clicked = True
                    break

            # Method 2: Find by text
            if not login_clicked:
                all_buttons = self.driver.find_elements(By.TAG_NAME, "button")
                for btn in all_buttons:
                    if btn.is_displayed() and ("log" in btn.text.lower() or "sign" in btn.text.lower()):
                        btn.click()
                        login_clicked = True
                        break

            # Method 3: Submit form
            if not login_clicked and password_field:
                password_field.submit()
                login_clicked = True

            if login_clicked:
                print("🔄 Logging in...")
            else:
                print("⚠️ Could not find login button")

            time.sleep(5)

            # Verify login
            if "stats" in self.driver.current_url or "login" not in self.driver.current_url:
                print("✅ Login successful!")
                return True
            else:
                print("⚠️ Login may have failed, continuing anyway...")
                return True

        except Exception as e:
            print(f"⚠️ Auto-login encountered issue: {e}")
            return True  # Continue anyway to see what happens

    def login_manual(self):
        """Navigate to login page and wait for manual login"""
        print("\n" + "="*60)
        print("  LOGIN TO CLEANING THE GLASS")
        print("="*60)

        self.driver.get("https://cleaningtheglass.com/login")
        time.sleep(2)

        print("\n📝 Please log in to Cleaning the Glass in the browser window.")
        print("   (The site requires a subscription for full access)")
        print("\n   Once logged in, press ENTER to continue...")
        input()

        # Verify login by checking for logout link or user menu
        try:
            self.driver.find_element(By.PARTIAL_LINK_TEXT, "Log Out")
            print("✅ Login verified!")
            return True
        except:
            print("✅ Continuing (login status uncertain)...")
            return True

    def click_tab(self, tab_id):
        """Click a specific tab and wait for content to load"""
        try:
            # Multiple selector strategies for finding tabs
            selectors = [
                f"a[href*='#tab-{tab_id}']",
                f"a[href*='#{tab_id}']",
                f"[data-tab='{tab_id}']",
                f"a.nav-link[href*='{tab_id}']",
                f"li[data-tab='{tab_id}'] a",
            ]

            tab_element = None
            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        if elem.is_displayed():
                            tab_element = elem
                            break
                    if tab_element:
                        break
                except:
                    continue

            if tab_element:
                # Scroll to element and click
                self.driver.execute_script("arguments[0].scrollIntoView(true);", tab_element)
                time.sleep(0.5)
                try:
                    tab_element.click()
                except:
                    self.driver.execute_script("arguments[0].click();", tab_element)
                time.sleep(2)
                return True

            # Try clicking by text content
            tabs = self.driver.find_elements(By.CSS_SELECTOR, "a.nav-link, .tab-link, .stats-tab")
            for tab in tabs:
                if tab_id.replace("_", " ").lower() in tab.text.lower():
                    tab.click()
                    time.sleep(2)
                    return True

            return False
        except Exception as e:
            print(f"   ⚠️ Could not click tab {tab_id}: {e}")
            return False


    def extract_table_from_page(self):
        """Extract the main data table from the current page"""
        try:
            time.sleep(1)

            # Try various table selectors
            table_selectors = [
                "table.stats-table",
                "table.sortable",
                "div.stats-container table",
                "div.table-container table",
                ".team-stats table",
                "table.data-table",
                "table",
            ]

            for selector in table_selectors:
                try:
                    tables = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    valid_tables = [t for t in tables if t.is_displayed() and len(t.text.strip()) > 50]

                    if valid_tables:
                        # Get the table with the most rows
                        best_table = None
                        max_rows = 0

                        for table in valid_tables:
                            rows = table.find_elements(By.TAG_NAME, "tr")
                            if len(rows) > max_rows:
                                max_rows = len(rows)
                                best_table = table

                        if best_table and max_rows > 1:
                            html = best_table.get_attribute('outerHTML')
                            dfs = pd.read_html(StringIO(html))
                            if dfs and len(dfs[0]) > 0:
                                df = dfs[0]
                                if isinstance(df.columns, pd.MultiIndex):
                                    df.columns = [' '.join([str(c) for c in col if "Unnamed" not in str(c)]).strip() for col in df.columns.values]
                                return df
                except Exception as e:
                    continue

            return None
        except Exception as e:
            print(f"   ❌ Table extraction error: {e}")
            return None

    def prepare_dataframe(self, df, stat_type):
        """Prepare dataframe by fixing columns and converting to records format"""
        if df is None or df.empty:
            return None

        # Fix for NotImplementedError: Ensure columns are flattened before saving
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [' '.join([str(c) for c in col if "Unnamed" not in str(c)]).strip() for col in df.columns.values]

        # Fix duplicate column names by appending suffix
        cols = df.columns.tolist()
        seen = {}
        new_cols = []
        for col in cols:
            if col in seen:
                seen[col] += 1
                new_cols.append(f"{col}_{seen[col]}")
            else:
                seen[col] = 0
                new_cols.append(col)
        df.columns = new_cols

        # Convert to records
        return df.to_dict(orient='records')

    def save_combined_data(self, all_data, team_abbrev, page_type):
        """Save all data from a page into a single JSON file"""
        if not all_data:
            return False

        team_info = TEAMS[team_abbrev]
        team_slug = team_info["slug"]
        date_str = datetime.now().strftime("%m_%d_%Y")

        # Map page type to filename
        if page_type == "game_log":
            filename = "GAME_LOGS"
        elif page_type == "stats":
            filename = "TEAM_STATS"
        elif page_type == "lineups":
            filename = "LINEUPS"
        elif page_type == "onoff":
            filename = "ONOFF"
        elif page_type == "players":
            filename = "PLAYERS"
        else:
            filename = "OTHER"

        # Create team-specific CLEANINGdaGLASS folder
        team_output_dir = os.path.join(BASE_OUTPUT_DIR, team_abbrev, "CLEANINGdaGLASS")
        os.makedirs(team_output_dir, exist_ok=True)

        # Single JSON file for the entire page
        json_filename = f"{filename}_{date_str}.json"
        json_path = os.path.join(team_output_dir, json_filename)
        file_exists = os.path.exists(json_path)

        # Save combined data
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, indent=2)

        if file_exists:
            print(f"   🔄 Replaced {team_abbrev}\\CLEANINGdaGLASS\\{json_filename}")
        else:
            print(f"   💾 Saved to {team_abbrev}\\CLEANINGdaGLASS\\{json_filename}")
        return True


    def scrape_gamelogs(self, team_abbrev, team_id):
        """Scrape all game log tabs for a team"""
        print(f"\n📊 Scraping GAME LOGS...")

        base_url = f"https://cleaningtheglass.com/stats/team/{team_id}/gamelogs"
        self.driver.get(base_url)
        time.sleep(3)

        combined_data = {}
        for tab in GAMELOG_TABS:
            print(f"   📋 Tab: {tab['name']}")

            # Navigate to specific tab
            tab_url = f"{base_url}#tab-{tab['id']}"
            self.driver.get(tab_url)
            time.sleep(2)

            # Try clicking the tab if direct URL doesn't work
            self.click_tab(tab['id'])

            # Extract table
            df = self.extract_table_from_page()
            if df is not None:
                data = self.prepare_dataframe(df, tab['id'])
                if data:
                    combined_data[tab['id']] = data
                    print(f"      ✅ Collected {len(data)} records")
            else:
                print(f"      ⚠️ No data found")

        # Save all data in a single JSON file
        if combined_data:
            self.save_combined_data(combined_data, team_abbrev, "game_log")

        return combined_data

    def scrape_team_stats(self, team_abbrev, team_id):
        """Scrape all team overall stats tabs"""
        print(f"\n📊 Scraping TEAM STATS...")

        base_url = f"https://cleaningtheglass.com/stats/team/{team_id}/overall"
        self.driver.get(base_url)
        time.sleep(3)

        combined_data = {}
        for tab in STATS_TABS:
            print(f"   📋 Tab: {tab['name']}")

            # Navigate to specific tab
            tab_url = f"{base_url}#tab-{tab['id']}"
            self.driver.get(tab_url)
            time.sleep(2)

            # Try clicking the tab
            self.click_tab(tab['id'])

            # Extract table
            df = self.extract_table_from_page()
            if df is not None:
                data = self.prepare_dataframe(df, tab['id'])
                if data:
                    combined_data[tab['id']] = data
                    print(f"      ✅ Collected {len(data)} records")
            else:
                print(f"      ⚠️ No data found")

        # Save all data in a single JSON file
        if combined_data:
            self.save_combined_data(combined_data, team_abbrev, "stats")

        return combined_data

    def scrape_lineups(self, team_abbrev, team_id):
        """Scrape all lineup stats tabs"""
        print(f"\n📊 Scraping LINEUPS...")

        base_url = f"https://cleaningtheglass.com/stats/team/{team_id}/lineups"
        self.driver.get(base_url)
        time.sleep(3)

        combined_data = {}
        for tab in LINEUPS_TABS:
            print(f"   📋 Tab: {tab['name']}")

            # Navigate to specific tab
            tab_url = f"{base_url}#tab-{tab['id']}"
            self.driver.get(tab_url)
            time.sleep(2)

            # Try clicking the tab
            self.click_tab(tab['id'])

            # Extract table
            df = self.extract_table_from_page()
            if df is not None:
                data = self.prepare_dataframe(df, tab['id'])
                if data:
                    combined_data[tab['id']] = data
                    print(f"      ✅ Collected {len(data)} records")
            else:
                print(f"      ⚠️ No data found")

        # Save all data in a single JSON file
        if combined_data:
            self.save_combined_data(combined_data, team_abbrev, "lineups")

        return combined_data

    def scrape_onoff_stats(self, team_abbrev, team_id):
        """Scrape all on/off stats tabs"""
        print(f"\n📊 Scraping ON/OFF STATS...")

        base_url = f"https://cleaningtheglass.com/stats/team/{team_id}/onoff"
        self.driver.get(base_url)
        time.sleep(3)

        combined_data = {}
        for tab in ONOFF_TABS:
            print(f"   📋 Tab: {tab['name']}")

            # Navigate to specific tab
            tab_url = f"{base_url}#tab-{tab['id']}"
            self.driver.get(tab_url)
            time.sleep(2)

            # Try clicking the tab
            self.click_tab(tab['id'])

            # Extract table
            df = self.extract_table_from_page()
            if df is not None:
                data = self.prepare_dataframe(df, tab['id'])
                if data:
                    combined_data[tab['id']] = data
                    print(f"      ✅ Collected {len(data)} records")
            else:
                print(f"      ⚠️ No data found")

        # Save all data in a single JSON file
        if combined_data:
            self.save_combined_data(combined_data, team_abbrev, "onoff")

        return combined_data

    def scrape_player_stats(self, team_abbrev, team_id):
        """Scrape all player stats tabs"""
        print(f"\n📊 Scraping PLAYER STATS...")

        base_url = f"https://cleaningtheglass.com/stats/team/{team_id}/players"
        self.driver.get(base_url)
        time.sleep(3)

        combined_data = {}
        for tab in PLAYER_TABS:
            print(f"   📋 Tab: {tab['name']}")

            # Navigate to specific tab
            tab_url = f"{base_url}#tab-{tab['id']}"
            self.driver.get(tab_url)
            time.sleep(2)

            # Try clicking the tab
            self.click_tab(tab['id'])

            # Extract table
            df = self.extract_table_from_page()
            if df is not None:
                data = self.prepare_dataframe(df, tab['id'])
                if data:
                    combined_data[tab['id']] = data
                    print(f"      ✅ Collected {len(data)} records")
            else:
                print(f"      ⚠️ No data found")

        # Save all data in a single JSON file
        if combined_data:
            self.save_combined_data(combined_data, team_abbrev, "players")

        return combined_data


    def scrape_team(self, team_abbrev):
        """Scrape all data for a specific team"""
        team_abbrev = team_abbrev.upper()

        if team_abbrev not in TEAMS:
            print(f"❌ Unknown team: {team_abbrev}")
            return None

        team = TEAMS[team_abbrev]
        team_id = team["id"]
        team_name = team["name"]

        print("\n" + "="*60)
        print(f"🏀 SCRAPING: {team_name} ({team_abbrev})")
        print("="*60)

        all_results = {
            "team": team_abbrev,
            "name": team_name,
            "gamelogs": {},
            "stats": {},
            "lineups": {},
            "onoff": {},
            "players": {},
        }

        # Scrape game logs
        all_results["gamelogs"] = self.scrape_gamelogs(team_abbrev, team_id)

        # Scrape team stats
        all_results["stats"] = self.scrape_team_stats(team_abbrev, team_id)

        # Scrape lineups
        all_results["lineups"] = self.scrape_lineups(team_abbrev, team_id)

        # Scrape on/off stats
        all_results["onoff"] = self.scrape_onoff_stats(team_abbrev, team_id)

        # Scrape player stats
        all_results["players"] = self.scrape_player_stats(team_abbrev, team_id)

        # Summary
        total_tables = (len(all_results["gamelogs"]) + len(all_results["stats"]) +
                       len(all_results["lineups"]) + len(all_results["onoff"]) +
                       len(all_results["players"]))
        print(f"\n✅ Completed {team_name}: {total_tables} tables scraped")

        return all_results

    def close(self):
        """Close the browser"""
        try:
            self.driver.quit()
        except:
            pass
        print("\n🔒 Browser closed.")


def show_menu():
    """Display team selection menu"""
    print("\n" + "="*70)
    print("   🏀 CLEANING THE GLASS - MULTI-TEAM SCRAPER 🏀")
    print("="*70)
    print("\nAvailable teams:\n")

    # Display in columns
    teams_list = sorted(TEAMS.keys())
    for i in range(0, len(teams_list), 6):
        row = teams_list[i:i+6]
        print("  " + "  ".join(f"{t:5}" for t in row))

    print("\n" + "-"*70)
    print("Enter multiple teams separated by commas (e.g., LAL,BOS,MIA)")
    print("Or enter 'ALL' to scrape all 30 teams")
    print("-"*70)


def parse_teams(team_input):
    """Parse team input string and return list of valid teams"""
    team_input = team_input.upper().strip()

    if team_input == 'ALL':
        return list(TEAMS.keys())

    # Split by comma and clean up
    team_list = [t.strip() for t in team_input.split(',')]

    valid_teams = []
    invalid_teams = []

    for team in team_list:
        if team in TEAMS:
            if team not in valid_teams:  # Avoid duplicates
                valid_teams.append(team)
        elif team:  # Ignore empty strings
            invalid_teams.append(team)

    if invalid_teams:
        print(f"⚠️ Unknown teams (skipping): {', '.join(invalid_teams)}")

    return valid_teams


def main():
    """Main function - supports both interactive and command-line modes"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Cleaning The Glass NBA Multi-Team Data Scraper',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python Cleaning_Glass_Multi.py LAL,BOS,MIA        # Scrape 3 teams
  python Cleaning_Glass_Multi.py LAL,BOS --headless # Run without browser
  python Cleaning_Glass_Multi.py ALL                # Scrape all 30 teams
        """
    )
    parser.add_argument('teams', nargs='?', help='Comma-separated team abbreviations (e.g., LAL,BOS,MIA) or ALL')
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')
    parser.add_argument('--no-login', action='store_true', help='Skip login (if already logged in via cookies)')
    args = parser.parse_args()

    # If teams provided via command line, use non-interactive mode
    if args.teams:
        teams = parse_teams(args.teams)
        if not teams:
            print("❌ No valid teams provided.")
            print("Valid teams:", ", ".join(sorted(TEAMS.keys())))
            return

        print(f"\n✅ Selected {len(teams)} team(s): {', '.join(teams)}")
        for team in teams:
            print(f"   • {TEAMS[team]['name']}")

        headless = args.headless
    else:
        # Interactive mode
        show_menu()

        # Get team selection
        while True:
            choice = input("\n🏀 Enter teams (comma-separated), 'ALL', or 'Q' to quit: ").strip()

            if choice.upper() == 'Q':
                print("👋 Goodbye!")
                return

            teams = parse_teams(choice)

            if not teams:
                print("❌ No valid teams entered. Try again.")
                continue

            print(f"\n✅ Selected {len(teams)} team(s):")
            for team in teams:
                print(f"   • {TEAMS[team]['name']}")

            confirm = input("\n   Proceed? (y/n): ").strip().lower()
            if confirm == 'y':
                break

        # Ask about headless mode
        headless_choice = input("\n🖥️  Run in headless mode (no browser window)? (y/n): ").strip().lower()
        headless = headless_choice == 'y'

    # Credentials for auto-login
    CTG_EMAIL = "DaSilvaDub@gmail.com"
    CTG_PASSWORD = "TImeisnow11#"

    # Initialize scraper
    scraper = CTGScraperV2(headless=headless)

    # Track results
    completed_teams = []
    failed_teams = []

    try:
        # Auto-login (skip if --no-login flag is set)
        if args.teams and args.no_login:
            print("⏭️  Skipping login prompt...")
            scraper.driver.get("https://cleaningtheglass.com/stats")
            time.sleep(2)
        else:
            scraper.login_auto(CTG_EMAIL, CTG_PASSWORD)

        # Scrape each selected team
        total_teams = len(teams)
        for idx, team in enumerate(teams, 1):
            print(f"\n{'#'*70}")
            print(f"# TEAM {idx} of {total_teams}")
            print(f"{'#'*70}")

            try:
                result = scraper.scrape_team(team)
                if result:
                    completed_teams.append(team)
                else:
                    failed_teams.append(team)
            except Exception as e:
                print(f"❌ Error scraping {team}: {e}")
                failed_teams.append(team)

            if idx < total_teams:
                print("\n⏳ Pausing before next team...")
                time.sleep(5)

        # Final summary
        print("\n" + "="*70)
        print("🎉 SCRAPING COMPLETE!")
        print("="*70)
        print(f"\n📊 Results Summary:")
        print(f"   ✅ Completed: {len(completed_teams)} teams")
        if completed_teams:
            for team in completed_teams:
                print(f"      • {TEAMS[team]['name']}")

        if failed_teams:
            print(f"   ❌ Failed: {len(failed_teams)} teams")
            for team in failed_teams:
                print(f"      • {TEAMS[team]['name']}")

        print(f"\n📁 Files saved to:")
        print(f"   {BASE_OUTPUT_DIR}")
        print(f"   Structure: [TEAM]/CLEANINGdaGLASS/[CATEGORY]/...")
        print("="*70)

    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        scraper.close()


if __name__ == "__main__":
    # Quick check for required packages
    try:
        import pandas
        from selenium import webdriver
    except ImportError as e:
        print("❌ Missing required packages!")
        print("   Run: pip install selenium pandas webdriver-manager openpyxl --break-system-packages")
        sys.exit(1)

    main()
