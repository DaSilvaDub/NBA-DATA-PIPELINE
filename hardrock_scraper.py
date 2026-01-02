"""
Hard Rock Bet Odds Scraper
Scrapes game odds and player props from Hard Rock Bet sportsbook.
Interactive prompts for sport, match, and prop type selection.
Formats data for LLM analysis and saves to JSON.
"""

import os
import re
import json
import time
from datetime import datetime
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager


class HardRockScraper:
    """Scraper for Hard Rock Bet sportsbook odds and player props."""

    BASE_URL = "https://app.hardrock.bet"
    OUTPUT_BASE_PATH = r"C:\Users\dasil\My Drive (dasilvadub@gmail.com)\NBA\MATCHUP\BETS (HARDROCK)"

    # Sport URL mappings
    SPORT_URLS = {
        "nba": "/sports/basketball/nba",
        "nfl": "/sports/football/nfl",
        "mlb": "/sports/baseball/mlb",
        "nhl": "/sports/hockey/nhl",
        "ncaab": "/sports/basketball/ncaab",
        "ncaaf": "/sports/football/ncaaf",
        "soccer": "/sports/soccer",
        "ufc": "/sports/mma/ufc",
        "tennis": "/sports/tennis",
    }

    def __init__(self, headless: bool = False):
        """Initialize the scraper with Chrome WebDriver."""
        self.driver = None
        self.headless = headless
        self.wait = None

    def setup_driver(self):
        """Set up Chrome WebDriver with appropriate options."""
        chrome_options = Options()

        if self.headless:
            chrome_options.add_argument("--headless=new")

        # Common options for stability
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)

        # User agent to appear more like a regular browser
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.wait = WebDriverWait(self.driver, 20)

        # Execute CDP commands to prevent detection
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """
        })

    def close(self):
        """Close the WebDriver."""
        if self.driver:
            self.driver.quit()

    def navigate_to_sport(self, sport: str) -> bool:
        """Navigate to a specific sport page."""
        sport_lower = sport.lower()
        if sport_lower not in self.SPORT_URLS:
            print(f"Sport '{sport}' not found in available sports.")
            return False

        url = f"{self.BASE_URL}{self.SPORT_URLS[sport_lower]}"
        print(f"\nNavigating to {url}...")
        self.driver.get(url)
        time.sleep(3)  # Allow page to load
        return True

    def get_available_sports(self) -> list:
        """Return list of available sports."""
        return list(self.SPORT_URLS.keys())

    def scrape_matches(self) -> list:
        """Scrape available matches from the current sport page."""
        matches = []
        time.sleep(2)

        try:
            # Wait for event containers to load
            # Hard Rock uses various class patterns - we'll try multiple selectors
            selectors = [
                "[data-testid='event-card']",
                ".event-card",
                "[class*='EventCard']",
                "[class*='event-row']",
                "[class*='match-row']",
                ".sports-event",
                "[data-qa='event']",
                "article[class*='event']",
            ]

            event_elements = []
            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        event_elements = elements
                        print(f"Found {len(elements)} events using selector: {selector}")
                        break
                except:
                    continue

            if not event_elements:
                # Try finding by link patterns
                links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/event/']")
                print(f"Found {len(links)} event links")

                seen_events = set()
                for link in links:
                    try:
                        href = link.get_attribute("href")
                        text = link.text.strip()

                        if href and text and href not in seen_events:
                            seen_events.add(href)
                            # Extract team names from link text
                            if " vs " in text.lower() or " @ " in text.lower():
                                matches.append({
                                    "teams": text,
                                    "url": href,
                                    "element": link
                                })
                            elif text and len(text) > 3:
                                matches.append({
                                    "teams": text,
                                    "url": href,
                                    "element": link
                                })
                    except:
                        continue
            else:
                for i, element in enumerate(event_elements):
                    try:
                        text = element.text.strip()
                        # Try to get the event URL
                        try:
                            link = element.find_element(By.CSS_SELECTOR, "a[href*='/event/']")
                            href = link.get_attribute("href")
                        except:
                            href = None

                        if text:
                            matches.append({
                                "teams": text.split('\n')[0] if '\n' in text else text,
                                "url": href,
                                "element": element,
                                "full_text": text
                            })
                    except:
                        continue

        except TimeoutException:
            print("Timeout waiting for matches to load")
        except Exception as e:
            print(f"Error scraping matches: {e}")

        return matches

    def navigate_to_match(self, match: dict) -> bool:
        """Navigate to a specific match page."""
        if match.get("url"):
            self.driver.get(match["url"])
            time.sleep(3)
            return True
        elif match.get("element"):
            try:
                match["element"].click()
                time.sleep(3)
                return True
            except:
                pass
        return False

    def scrape_game_props(self) -> dict:
        """Scrape game props (spreads, totals, moneylines) from match page."""
        props = {
            "type": "game_props",
            "scraped_at": datetime.now().isoformat(),
            "moneyline": [],
            "spread": [],
            "total": [],
            "other": []
        }

        time.sleep(2)

        try:
            # Look for market sections
            market_selectors = [
                "[data-testid='market']",
                "[class*='market']",
                "[class*='Market']",
                ".betting-market",
                "[class*='odds-row']",
            ]

            page_text = self.driver.find_element(By.TAG_NAME, "body").text

            # Parse odds from page text using regex
            # Look for odds patterns like -110, +150, etc.
            odds_pattern = r'[+-]\d{3,4}'
            odds_found = re.findall(odds_pattern, page_text)

            # Try to find structured market data
            for selector in market_selectors:
                try:
                    markets = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for market in markets:
                        market_text = market.text.strip()
                        if market_text:
                            # Categorize the market
                            market_lower = market_text.lower()
                            if "spread" in market_lower or "handicap" in market_lower:
                                props["spread"].append(self._parse_market(market_text))
                            elif "total" in market_lower or "over" in market_lower or "under" in market_lower:
                                props["total"].append(self._parse_market(market_text))
                            elif "money" in market_lower or "winner" in market_lower:
                                props["moneyline"].append(self._parse_market(market_text))
                            else:
                                props["other"].append(self._parse_market(market_text))
                except:
                    continue

            # Also capture raw page structure for analysis
            props["raw_odds_found"] = odds_found[:50]  # Limit to first 50

        except Exception as e:
            print(f"Error scraping game props: {e}")
            props["error"] = str(e)

        return props

    def scrape_player_props(self) -> dict:
        """Scrape player props from match page."""
        props = {
            "type": "player_props",
            "scraped_at": datetime.now().isoformat(),
            "players": {},
            "categories": []
        }

        time.sleep(2)

        try:
            # First, try to click on "Player Props" tab if it exists
            tab_selectors = [
                "button:contains('Player Props')",
                "[data-testid='player-props-tab']",
                "a[href*='player-props']",
                "[class*='player-props']",
                "button[class*='tab']",
            ]

            # Try clicking player props tab
            tabs = self.driver.find_elements(By.CSS_SELECTOR, "button, a")
            for tab in tabs:
                try:
                    if "player" in tab.text.lower() and "prop" in tab.text.lower():
                        tab.click()
                        time.sleep(2)
                        print("Clicked Player Props tab")
                        break
                except:
                    continue

            # Now scrape the player props
            prop_selectors = [
                "[data-testid='player-prop']",
                "[class*='player-prop']",
                "[class*='PlayerProp']",
                "[class*='prop-row']",
            ]

            # Get all text content and parse it
            body = self.driver.find_element(By.TAG_NAME, "body")
            page_html = self.driver.page_source
            page_text = body.text

            # Look for player names and associated props
            # Common patterns: "Player Name - Points O/U 25.5"
            lines = page_text.split('\n')

            current_category = "Unknown"
            current_player = None

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Check if it's a category header
                prop_categories = ["points", "rebounds", "assists", "threes", "steals",
                                   "blocks", "passing", "rushing", "receiving", "touchdowns",
                                   "strikeouts", "hits", "runs", "goals", "shots"]

                line_lower = line.lower()
                for cat in prop_categories:
                    if cat in line_lower and len(line) < 50:
                        current_category = line
                        if current_category not in props["categories"]:
                            props["categories"].append(current_category)
                        break

                # Look for odds patterns in the line
                if re.search(r'[+-]\d{3}', line) or re.search(r'O\s*\d+\.?\d*|U\s*\d+\.?\d*', line, re.I):
                    # This line likely contains betting data
                    if current_player:
                        if current_player not in props["players"]:
                            props["players"][current_player] = []
                        props["players"][current_player].append({
                            "category": current_category,
                            "line": line,
                            "raw": line
                        })
                else:
                    # Could be a player name
                    # Player names typically are 2-4 words with capital letters
                    words = line.split()
                    if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if w):
                        potential_name = line
                        # Verify it looks like a name (letters and spaces only)
                        if re.match(r'^[A-Za-z\s\.\-\']+$', potential_name):
                            current_player = potential_name

            # Try structured element approach
            for selector in prop_selectors:
                try:
                    prop_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in prop_elements:
                        elem_text = elem.text.strip()
                        if elem_text:
                            # Parse the element
                            parsed = self._parse_player_prop(elem_text)
                            if parsed and parsed.get("player"):
                                player = parsed["player"]
                                if player not in props["players"]:
                                    props["players"][player] = []
                                props["players"][player].append(parsed)
                except:
                    continue

        except Exception as e:
            print(f"Error scraping player props: {e}")
            props["error"] = str(e)

        return props

    def _parse_market(self, text: str) -> dict:
        """Parse a market text into structured data."""
        lines = text.split('\n')

        market_data = {
            "raw": text,
            "lines": [],
            "odds": []
        }

        for line in lines:
            line = line.strip()
            # Extract odds
            odds_match = re.findall(r'[+-]\d{3,4}', line)
            if odds_match:
                market_data["odds"].extend(odds_match)

            # Extract numbers (could be spreads or totals)
            numbers = re.findall(r'-?\d+\.?\d*', line)
            if numbers and line not in market_data["lines"]:
                market_data["lines"].append({
                    "text": line,
                    "numbers": numbers
                })

        return market_data

    def _parse_player_prop(self, text: str) -> dict:
        """Parse player prop text into structured data."""
        lines = text.split('\n')

        prop_data = {
            "raw": text,
            "player": None,
            "prop_type": None,
            "line": None,
            "over_odds": None,
            "under_odds": None
        }

        for line in lines:
            line = line.strip()

            # Look for player name (typically first line with proper name format)
            if not prop_data["player"] and re.match(r'^[A-Z][a-z]+ [A-Z][a-z]+', line):
                prop_data["player"] = line
                continue

            # Look for prop type keywords
            prop_types = ["points", "rebounds", "assists", "3-pointers", "steals", "blocks",
                         "passing yards", "rushing yards", "receiving yards", "touchdowns"]
            for pt in prop_types:
                if pt.lower() in line.lower():
                    prop_data["prop_type"] = pt
                    break

            # Extract line value (O/U number)
            line_match = re.search(r'[OU]\s*(\d+\.?\d*)', line, re.I)
            if line_match:
                prop_data["line"] = float(line_match.group(1))

            # Extract odds
            odds_match = re.search(r'([+-]\d{3,4})', line)
            if odds_match:
                odds_val = odds_match.group(1)
                if "over" in line.lower() or "o " in line.lower():
                    prop_data["over_odds"] = odds_val
                elif "under" in line.lower() or "u " in line.lower():
                    prop_data["under_odds"] = odds_val

        return prop_data

    def format_for_llm(self, data: dict, match_info: str) -> dict:
        """Format scraped data for LLM analysis."""
        formatted = {
            "metadata": {
                "source": "Hard Rock Bet",
                "scraped_at": datetime.now().isoformat(),
                "match": match_info,
                "url": self.driver.current_url if self.driver else None
            },
            "data": data,
            "analysis_prompt": self._generate_analysis_prompt(data, match_info)
        }
        return formatted

    def _generate_analysis_prompt(self, data: dict, match_info: str) -> str:
        """Generate a prompt for LLM analysis of the data."""
        if data.get("type") == "player_props":
            return f"""
Analyze the following player props data for {match_info}:

This data contains player proposition bets scraped from Hard Rock Bet.
For each player, identify:
1. The statistical category (points, rebounds, assists, etc.)
2. The betting line (over/under threshold)
3. The odds for over and under
4. Any notable value bets (favorable odds relative to expected probability)

Consider:
- Which props appear to offer positive expected value?
- Are there any correlated props that could be combined?
- How do these lines compare to typical player averages?

Data:
{json.dumps(data, indent=2)}
"""
        else:
            return f"""
Analyze the following game odds data for {match_info}:

This data contains game-level betting markets scraped from Hard Rock Bet.
Identify:
1. Moneyline odds for each team
2. Point spread and associated odds
3. Total (over/under) and associated odds
4. Any alternate lines or special markets

Consider:
- Implied probability from the odds
- Vig/juice on each market
- Any potential value compared to fair odds

Data:
{json.dumps(data, indent=2)}
"""

    def save_to_json(self, data: dict, match_info: str, prop_type: str) -> str:
        """Save data to JSON file in the specified folder structure."""
        # Clean match info for folder name
        folder_name = self._clean_filename(match_info)

        # Create folder path
        folder_path = Path(self.OUTPUT_BASE_PATH) / folder_name
        folder_path.mkdir(parents=True, exist_ok=True)

        # Create filename with timestamp and prop type
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prop_type}_{timestamp}.json"

        # Full file path
        file_path = folder_path / filename

        # Save JSON
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"\nData saved to: {file_path}")
        return str(file_path)

    def _clean_filename(self, text: str) -> str:
        """Clean text to be used as a filename/folder name."""
        # Remove invalid characters
        cleaned = re.sub(r'[<>:"/\\|?*]', '', text)
        # Replace spaces and special chars with underscores
        cleaned = re.sub(r'[\s\-@]+', '_', cleaned)
        # Remove consecutive underscores
        cleaned = re.sub(r'_+', '_', cleaned)
        # Trim underscores from ends
        cleaned = cleaned.strip('_')
        return cleaned[:100]  # Limit length


def interactive_menu():
    """Run the interactive menu for the scraper."""
    print("=" * 60)
    print("    HARD ROCK BET ODDS SCRAPER")
    print("=" * 60)
    print()

    scraper = HardRockScraper(headless=False)  # Set to True for headless mode

    try:
        print("Initializing browser...")
        scraper.setup_driver()

        # STEP 1: Select Sport
        print("\n" + "-" * 40)
        print("STEP 1: Select a Sport")
        print("-" * 40)

        sports = scraper.get_available_sports()
        for i, sport in enumerate(sports, 1):
            print(f"  {i}. {sport.upper()}")

        while True:
            try:
                choice = input("\nEnter sport number (or name): ").strip()
                if choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(sports):
                        selected_sport = sports[idx]
                        break
                else:
                    if choice.lower() in sports:
                        selected_sport = choice.lower()
                        break
                print("Invalid choice. Please try again.")
            except ValueError:
                print("Please enter a valid number.")

        print(f"\nSelected sport: {selected_sport.upper()}")

        # Navigate to sport
        if not scraper.navigate_to_sport(selected_sport):
            print("Failed to navigate to sport page.")
            return

        # STEP 2: Select Match
        print("\n" + "-" * 40)
        print("STEP 2: Select a Match")
        print("-" * 40)

        print("\nLoading available matches...")
        matches = scraper.scrape_matches()

        if not matches:
            print("\nNo matches found. The page structure may have changed.")
            print("Current URL:", scraper.driver.current_url)
            print("\nTrying alternative approach - please manually navigate to a match.")
            input("Press Enter when you've navigated to the match page...")

            # Create a dummy match entry
            current_url = scraper.driver.current_url
            matches = [{
                "teams": input("Enter the matchup name (e.g., 'Lakers vs Celtics'): "),
                "url": current_url
            }]
        else:
            print(f"\nFound {len(matches)} matches:\n")
            for i, match in enumerate(matches, 1):
                print(f"  {i}. {match['teams']}")

            while True:
                try:
                    choice = input("\nEnter match number: ").strip()
                    idx = int(choice) - 1
                    if 0 <= idx < len(matches):
                        selected_match = matches[idx]
                        break
                    print("Invalid choice. Please try again.")
                except ValueError:
                    print("Please enter a valid number.")

        selected_match = matches[idx] if len(matches) > 1 else matches[0]
        match_name = selected_match['teams']
        print(f"\nSelected match: {match_name}")

        # Navigate to match
        if not scraper.navigate_to_match(selected_match):
            print("Failed to navigate to match page. Please navigate manually.")
            input("Press Enter when ready...")

        # STEP 3: Select Prop Type
        print("\n" + "-" * 40)
        print("STEP 3: Select Prop Type")
        print("-" * 40)
        print("\n  1. Game Props (Spread, Total, Moneyline)")
        print("  2. Player Props")
        print("  3. Both")

        while True:
            try:
                choice = input("\nEnter your choice (1-3): ").strip()
                if choice in ['1', '2', '3']:
                    break
                print("Invalid choice. Please enter 1, 2, or 3.")
            except:
                pass

        # STEP 4: Scrape and Save
        print("\n" + "-" * 40)
        print("STEP 4: Scraping Data")
        print("-" * 40)

        results = {}

        if choice in ['1', '3']:
            print("\nScraping game props...")
            game_props = scraper.scrape_game_props()
            formatted_game = scraper.format_for_llm(game_props, match_name)
            file_path = scraper.save_to_json(formatted_game, match_name, "game_props")
            results['game_props'] = file_path
            print(f"Game props saved: {file_path}")

        if choice in ['2', '3']:
            print("\nScraping player props...")
            player_props = scraper.scrape_player_props()
            formatted_player = scraper.format_for_llm(player_props, match_name)
            file_path = scraper.save_to_json(formatted_player, match_name, "player_props")
            results['player_props'] = file_path
            print(f"Player props saved: {file_path}")

        # Summary
        print("\n" + "=" * 60)
        print("SCRAPING COMPLETE")
        print("=" * 60)
        print(f"\nMatch: {match_name}")
        print(f"Files saved to: {Path(scraper.OUTPUT_BASE_PATH) / scraper._clean_filename(match_name)}")

        for prop_type, path in results.items():
            print(f"  - {prop_type}: {Path(path).name}")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

    finally:
        input("\nPress Enter to close the browser...")
        scraper.close()


if __name__ == "__main__":
    interactive_menu()
