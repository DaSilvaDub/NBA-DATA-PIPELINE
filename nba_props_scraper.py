"""
NBA Props Scraper for Hard Rock Bet
Scrapes all player props or game props for an entire NBA slate on a selected date.
Creates separate folders for each matchup with JSON output.
"""

import os
import re
import json
import time
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager


class NBAHardRockScraper:
    """Scraper for Hard Rock Bet NBA odds and player props."""

    BASE_URL = "https://app.hardrock.bet"
    NBA_URL = "/home/sport-leagues/basketball/691033199537586178"  # NBA league page
    OUTPUT_BASE_PATH = r"C:\Users\dasil\My Drive (dasilvadub@gmail.com)\NBA\MATCHUP\BETS (HARDROCK)"

    def __init__(self, headless: bool = False):
        """Initialize the scraper with Chrome WebDriver."""
        self.driver = None
        self.headless = headless
        self.wait = None
        self.scraped_date = None
        self.prop_type = None  # 'player' or 'game'

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

    def navigate_to_nba(self) -> bool:
        """Navigate to NBA page."""
        url = f"{self.BASE_URL}{self.NBA_URL}"
        print(f"\nNavigating to {url}...")
        self.driver.get(url)
        time.sleep(4)  # Allow page to load
        return True

    def select_date(self, target_date: str) -> bool:
        """
        Attempt to select a specific date on the NBA page.
        target_date format: 'YYYY-MM-DD' or 'today', 'tomorrow'
        """
        try:
            # Parse the target date
            if target_date.lower() == 'today':
                date_obj = datetime.now()
            elif target_date.lower() == 'tomorrow':
                date_obj = datetime.now() + timedelta(days=1)
            else:
                date_obj = datetime.strptime(target_date, '%Y-%m-%d')

            self.scraped_date = date_obj.strftime('%Y-%m-%d')
            print(f"Target date: {date_obj.strftime('%A, %B %d, %Y')}")

            # Try to find and click date selector
            time.sleep(2)

            # Look for date navigation elements
            date_selectors = [
                "[data-testid='date-picker']",
                "[class*='date-selector']",
                "[class*='DateSelector']",
                "[class*='calendar']",
                "button[class*='date']",
                "[class*='day-selector']",
            ]

            # Try to find date tabs/buttons
            date_buttons = self.driver.find_elements(By.CSS_SELECTOR, "button, [role='tab']")

            target_day = date_obj.strftime('%a').upper()  # e.g., 'MON', 'TUE'
            target_day_full = date_obj.strftime('%A')  # e.g., 'Monday'
            target_date_num = date_obj.strftime('%d')  # e.g., '15'
            target_month_day = date_obj.strftime('%b %d')  # e.g., 'Jan 15'

            for btn in date_buttons:
                try:
                    btn_text = btn.text.strip().upper()
                    if (target_day in btn_text or
                        target_day_full.upper() in btn_text or
                        target_date_num in btn_text or
                        target_month_day.upper() in btn_text):
                        print(f"Found date button: {btn.text}")
                        btn.click()
                        time.sleep(2)
                        return True
                except:
                    continue

            # If today, we might already be on the right page
            if target_date.lower() == 'today':
                print("Assuming today's games are already displayed")
                return True

            print("Could not find date selector - will scrape currently displayed games")
            return True

        except Exception as e:
            print(f"Error selecting date: {e}")
            return True  # Continue anyway

    def scrape_all_matches(self, debug=False) -> list:
        """Scrape all available NBA matches from the page."""
        matches = []
        time.sleep(5)  # Increased wait time for page load

        try:
            if debug:
                # Save screenshot for debugging
                screenshot_path = Path(self.OUTPUT_BASE_PATH) / f"debug_screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                self.driver.save_screenshot(str(screenshot_path))
                print(f"Debug: Screenshot saved to {screenshot_path}")

                # Save page source
                page_source_path = Path(self.OUTPUT_BASE_PATH) / f"debug_page_source_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
                with open(page_source_path, 'w', encoding='utf-8') as f:
                    f.write(self.driver.page_source)
                print(f"Debug: Page source saved to {page_source_path}")

            # Multiple strategies to find matches
            print("\nSearching for NBA matches...")

            # Strategy 1: Look for all clickable elements containing team names
            all_elements = self.driver.find_elements(By.XPATH, "//*[contains(@href, 'basketball') or contains(@href, 'nba')]")
            print(f"Found {len(all_elements)} NBA-related elements")

            # Strategy 2: Look for event links with various patterns
            event_link_patterns = [
                "a[href*='/event/']",
                "a[href*='basketball']",
                "a[href*='nba']",
                "[role='button'][href]",
                "div[class*='event'] a",
                "div[class*='game'] a",
                "div[class*='match'] a",
            ]

            seen_urls = set()
            for pattern in event_link_patterns:
                try:
                    event_links = self.driver.find_elements(By.CSS_SELECTOR, pattern)
                    print(f"Pattern '{pattern}': found {len(event_links)} links")

                    for link in event_links:
                        try:
                            href = link.get_attribute("href")
                            if not href or href in seen_urls:
                                continue

                            # Check if it's an NBA link
                            if "nba" not in href.lower() and "basketball" not in href.lower():
                                continue

                            seen_urls.add(href)

                            # Get text - might contain team names
                            text = link.text.strip()

                            # Try to get parent container for more context
                            parent = link
                            for _ in range(7):  # Increased from 5
                                try:
                                    parent = parent.find_element(By.XPATH, "..")
                                    parent_text = parent.text.strip()
                                    if len(parent_text) > len(text) and len(parent_text) < 500:
                                        text = parent_text
                                except:
                                    break

                            if text and len(text) > 3:
                                matches.append({
                                    "teams": self._extract_team_names(text),
                                    "url": href,
                                    "raw_text": text[:200]
                                })
                        except (StaleElementReferenceException, Exception):
                            continue
                except Exception:
                    continue

            # Strategy 3: Find team name text directly on page and construct URLs
            if len(matches) < 3:
                print("Trying to find team names in page text...")
                try:
                    page_source = self.driver.page_source
                    # Look for event IDs in the page source
                    event_ids = re.findall(r'/event/([a-zA-Z0-9\-_]+)', page_source)
                    print(f"Found {len(event_ids)} potential event IDs in page source")

                    for event_id in set(event_ids):
                        url = f"{self.BASE_URL}/event/{event_id}"
                        if url not in seen_urls and "nba" in url.lower():
                            seen_urls.add(url)
                            matches.append({
                                "teams": f"Event {event_id}",
                                "url": url,
                                "raw_text": event_id
                            })
                except Exception as e:
                    print(f"Error in strategy 3: {e}")

            # Strategy 4: Look for game rows with "More wagers" buttons
            if len(matches) < 3:
                print("Looking for game rows with 'More wagers' buttons...")
                try:
                    # Find all game container divs
                    game_containers = self.driver.find_elements(By.CSS_SELECTOR, ".hr-market-view")
                    print(f"Found {len(game_containers)} game containers")

                    for idx, game_container in enumerate(game_containers):
                        try:
                            # Get team names from this container
                            text = game_container.text.strip()
                            teams = self._extract_team_names(text)

                            # Skip live games (those showing scores and "Quarter" or "Half Time")
                            is_live = any(indicator in text for indicator in ["Quarter", "Half Time", "Live", "live-icon"])

                            if not is_live:
                                # Try to find the More wagers button
                                try:
                                    more_wagers_btn = game_container.find_element(By.CSS_SELECTOR, ".more-wagers")

                                    # Create a unique identifier for this game
                                    game_id = f"game_{idx}_{teams.replace(' ', '_').replace('vs', '')}"

                                    matches.append({
                                        "teams": teams,
                                        "game_element": more_wagers_btn,
                                        "game_container": game_container,
                                        "game_id": game_id,
                                        "raw_text": text[:200]
                                    })
                                except:
                                    # No more wagers button, skip
                                    pass
                        except Exception as e:
                            continue

                    print(f"Found {len(matches)} tomorrow's games")
                except Exception as e:
                    print(f"Error in strategy 4: {e}")

            # Remove duplicates based on URL or game_id
            unique_matches = []
            seen = set()
            for match in matches:
                identifier = match.get('url') or match.get('game_id') or match.get('teams')
                if identifier and identifier not in seen:
                    seen.add(identifier)
                    unique_matches.append(match)

            print(f"\nFound {len(unique_matches)} unique NBA matches")
            return unique_matches

        except Exception as e:
            print(f"Error scraping matches: {e}")
            import traceback
            traceback.print_exc()
            return matches

    def _extract_team_names(self, text: str) -> str:
        """Extract team names from text."""
        # Clean up the text
        lines = text.split('\n')

        # NBA team indicators
        nba_teams = [
            'Hawks', 'Celtics', 'Nets', 'Hornets', 'Bulls', 'Cavaliers', 'Mavericks',
            'Nuggets', 'Pistons', 'Warriors', 'Rockets', 'Pacers', 'Clippers', 'Lakers',
            'Grizzlies', 'Heat', 'Bucks', 'Timberwolves', 'Pelicans', 'Knicks', 'Thunder',
            'Magic', '76ers', 'Sixers', 'Suns', 'Blazers', 'Trail Blazers', 'Kings', 'Spurs',
            'Raptors', 'Jazz', 'Wizards', 'Atlanta', 'Boston', 'Brooklyn', 'Charlotte',
            'Chicago', 'Cleveland', 'Dallas', 'Denver', 'Detroit', 'Golden State',
            'Houston', 'Indiana', 'LA Clippers', 'LA Lakers', 'Los Angeles', 'Memphis',
            'Miami', 'Milwaukee', 'Minnesota', 'New Orleans', 'New York', 'Oklahoma City',
            'Orlando', 'Philadelphia', 'Phoenix', 'Portland', 'Sacramento', 'San Antonio',
            'Toronto', 'Utah', 'Washington'
        ]

        found_teams = []
        for line in lines:
            for team in nba_teams:
                if team.lower() in line.lower():
                    # Get the full line or a portion
                    cleaned = line.strip()
                    if cleaned and cleaned not in found_teams:
                        found_teams.append(cleaned)
                    break

        if len(found_teams) >= 2:
            return f"{found_teams[0]} vs {found_teams[1]}"
        elif len(found_teams) == 1:
            return found_teams[0]
        else:
            # Return first meaningful line
            for line in lines:
                if len(line.strip()) > 5 and not line.strip().startswith('+') and not line.strip().startswith('-'):
                    return line.strip()[:100]
            return text[:100] if text else "Unknown Matchup"

    def navigate_to_match(self, match: dict) -> bool:
        """Navigate to a specific match page."""
        # If match has a URL, use it
        if match.get("url"):
            print(f"Navigating to: {match['url']}")
            self.driver.get(match["url"])
            time.sleep(4)
            return True
        # If match has a game_element, click it
        elif match.get("game_element"):
            try:
                print(f"Clicking 'More wagers' for: {match['teams']}")
                # Scroll element into view (centered)
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", match["game_element"])
                time.sleep(1)
                # Click using JavaScript to avoid interception
                self.driver.execute_script("arguments[0].click();", match["game_element"])
                time.sleep(5)  # Wait for page to load
                return True
            except Exception as e:
                print(f"Error clicking game element: {e}")
                return False
        return False

    def scrape_all_game_props(self) -> dict:
        """Scrape all game props (spreads, totals, moneylines) from match page."""
        props = {
            "type": "game_props",
            "scraped_at": datetime.now().isoformat(),
            "date": self.scraped_date,
            "moneyline": [],
            "spread": [],
            "total": [],
            "quarter_props": [],
            "half_props": [],
            "alternate_lines": [],
            "other": []
        }

        time.sleep(2)

        try:
            # Click on different tabs to get all game props
            tabs_to_try = ['game', 'main', 'spread', 'total', 'moneyline', 'quarters', 'halves', 'alternate']

            all_tabs = self.driver.find_elements(By.CSS_SELECTOR, "button, [role='tab'], a")

            for tab in all_tabs:
                try:
                    tab_text = tab.text.strip().lower()
                    for target in tabs_to_try:
                        if target in tab_text:
                            tab.click()
                            time.sleep(1.5)
                            self._extract_game_markets(props)
                            break
                except:
                    continue

            # Also scrape the main page
            self._extract_game_markets(props)

            # Capture page structure for debugging
            try:
                body_text = self.driver.find_element(By.TAG_NAME, "body").text
                props["page_snapshot"] = body_text[:5000]
            except:
                pass

        except Exception as e:
            print(f"Error scraping game props: {e}")
            props["error"] = str(e)

        return props

    def _extract_game_markets(self, props: dict):
        """Extract game market data from current page state."""
        try:
            # Find all market containers
            market_selectors = [
                "[data-testid='market']",
                "[class*='market']",
                "[class*='Market']",
                "[class*='betting-option']",
                "[class*='odds-button']",
                "[class*='outcome']",
            ]

            for selector in market_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        try:
                            text = elem.text.strip()
                            if not text or len(text) < 3:
                                continue

                            market_data = self._parse_game_market(text)
                            if not market_data:
                                continue

                            # Categorize
                            text_lower = text.lower()
                            if 'spread' in text_lower or 'handicap' in text_lower:
                                if market_data not in props["spread"]:
                                    props["spread"].append(market_data)
                            elif 'total' in text_lower or 'over' in text_lower or 'under' in text_lower:
                                if '1st' in text_lower or 'first' in text_lower:
                                    if market_data not in props["quarter_props"]:
                                        props["quarter_props"].append(market_data)
                                elif 'half' in text_lower:
                                    if market_data not in props["half_props"]:
                                        props["half_props"].append(market_data)
                                else:
                                    if market_data not in props["total"]:
                                        props["total"].append(market_data)
                            elif 'money' in text_lower or 'winner' in text_lower or 'ml' in text_lower:
                                if market_data not in props["moneyline"]:
                                    props["moneyline"].append(market_data)
                            elif 'alt' in text_lower:
                                if market_data not in props["alternate_lines"]:
                                    props["alternate_lines"].append(market_data)
                            else:
                                if market_data not in props["other"]:
                                    props["other"].append(market_data)
                        except:
                            continue
                except:
                    continue

        except Exception as e:
            print(f"Error extracting game markets: {e}")

    def _parse_game_market(self, text: str) -> dict:
        """Parse game market text into structured data."""
        if not text or len(text) < 3:
            return None

        lines = text.split('\n')

        market_data = {
            "raw_text": text[:500],
            "selections": [],
            "odds": []
        }

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Extract odds (American format: +150, -110)
            odds_matches = re.findall(r'[+-]\d{3,4}', line)
            market_data["odds"].extend(odds_matches)

            # Extract point values (spreads, totals)
            points_matches = re.findall(r'[+-]?\d+\.5|\d+\.5', line)

            # Extract over/under values
            ou_matches = re.findall(r'[OU]\s*(\d+\.?\d*)', line, re.I)

            if odds_matches or points_matches or ou_matches:
                market_data["selections"].append({
                    "text": line,
                    "odds": odds_matches,
                    "points": points_matches,
                    "over_under": ou_matches
                })

        return market_data if market_data["selections"] or market_data["odds"] else None

    def scrape_all_player_props(self) -> dict:
        """Scrape ALL player props from match page."""
        props = {
            "type": "player_props",
            "scraped_at": datetime.now().isoformat(),
            "date": self.scraped_date,
            "categories": {},
            "players": {},
            "all_props": []
        }

        time.sleep(2)

        try:
            # First, find and click on Player Props tab
            print("  Looking for Player Props tab...")
            tabs = self.driver.find_elements(By.CSS_SELECTOR, "button, [role='tab'], a, [class*='tab']")

            player_props_clicked = False
            for tab in tabs:
                try:
                    tab_text = tab.text.strip().lower()
                    if 'player' in tab_text and ('prop' in tab_text or 'bet' in tab_text):
                        print(f"  Clicking: {tab.text.strip()}")
                        tab.click()
                        time.sleep(2)
                        player_props_clicked = True
                        break
                    elif tab_text == 'player props' or tab_text == 'players':
                        print(f"  Clicking: {tab.text.strip()}")
                        tab.click()
                        time.sleep(2)
                        player_props_clicked = True
                        break
                except:
                    continue

            if not player_props_clicked:
                print("  Could not find Player Props tab, checking current page...")

            # Get all prop categories and iterate through them
            prop_categories = [
                'points', 'rebounds', 'assists', 'threes', '3-pointers', '3 pointers',
                'steals', 'blocks', 'turnovers', 'pts + reb', 'pts + ast',
                'reb + ast', 'pts + reb + ast', 'double-double', 'triple-double',
                'first basket', 'first scorer', 'fantasy', 'combos', 'all'
            ]

            # Click through each category tab if available
            category_tabs = self.driver.find_elements(By.CSS_SELECTOR, "button, [role='tab'], a")

            for cat in prop_categories:
                for tab in category_tabs:
                    try:
                        tab_text = tab.text.strip().lower()
                        if cat in tab_text:
                            print(f"  Scraping category: {tab.text.strip()}")
                            tab.click()
                            time.sleep(1.5)
                            self._extract_player_props(props, tab.text.strip())
                            break
                    except:
                        continue

            # Also extract from current page state
            self._extract_player_props(props, "main")

            # Scroll down to load more props
            print("  Scrolling to load more props...")
            for _ in range(5):
                try:
                    self.driver.execute_script("window.scrollBy(0, 800)")
                    time.sleep(1)
                    self._extract_player_props(props, "scroll")
                except:
                    break

            # Scroll back to top
            self.driver.execute_script("window.scrollTo(0, 0)")

        except Exception as e:
            print(f"Error scraping player props: {e}")
            props["error"] = str(e)

        # Clean up and organize
        props["total_props_found"] = len(props["all_props"])
        props["total_players"] = len(props["players"])

        return props

    def _extract_player_props(self, props: dict, category: str):
        """Extract player props from current page state."""
        try:
            # Initialize category if not exists
            if category not in props["categories"]:
                props["categories"][category] = []

            # Various selectors for player prop elements
            prop_selectors = [
                "[data-testid*='player']",
                "[class*='player-prop']",
                "[class*='PlayerProp']",
                "[class*='prop-row']",
                "[class*='market-row']",
                "[class*='outcome-row']",
                "[class*='betting-row']",
            ]

            # Get page text for parsing
            body = self.driver.find_element(By.TAG_NAME, "body")
            page_text = body.text

            # Parse page text for player props
            lines = page_text.split('\n')
            current_player = None
            current_prop_type = None

            nba_prop_types = ['points', 'rebounds', 'assists', '3-pointers', 'threes',
                             'steals', 'blocks', 'turnovers', 'fantasy', 'double', 'triple',
                             'pts', 'reb', 'ast', 'stl', 'blk', 'to']

            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue

                # Check if this is a prop type header
                line_lower = line.lower()
                for pt in nba_prop_types:
                    if pt in line_lower and len(line) < 50:
                        current_prop_type = line
                        break

                # Check if this looks like a player name
                if self._is_player_name(line):
                    current_player = line

                # Check if this line has odds
                if re.search(r'[+-]\d{3}', line) or re.search(r'[OU]\s*\d+\.?\d*', line, re.I):
                    prop_data = self._parse_player_prop_line(line, current_player, current_prop_type)

                    if prop_data:
                        # Add to all props
                        if prop_data not in props["all_props"]:
                            props["all_props"].append(prop_data)

                        # Add to player's props
                        if prop_data.get("player"):
                            player_name = prop_data["player"]
                            if player_name not in props["players"]:
                                props["players"][player_name] = []
                            if prop_data not in props["players"][player_name]:
                                props["players"][player_name].append(prop_data)

                        # Add to category
                        if prop_data not in props["categories"][category]:
                            props["categories"][category].append(prop_data)

            # Also try structured element approach
            for selector in prop_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        try:
                            text = elem.text.strip()
                            if text and len(text) > 5:
                                prop_data = self._parse_player_prop_element(text)
                                if prop_data and prop_data not in props["all_props"]:
                                    props["all_props"].append(prop_data)

                                    if prop_data.get("player"):
                                        player_name = prop_data["player"]
                                        if player_name not in props["players"]:
                                            props["players"][player_name] = []
                                        props["players"][player_name].append(prop_data)
                        except:
                            continue
                except:
                    continue

        except Exception as e:
            print(f"  Error extracting player props: {e}")

    def _is_player_name(self, text: str) -> bool:
        """Check if text looks like a player name."""
        if not text or len(text) < 4 or len(text) > 40:
            return False

        # Player names are typically 2-4 words, capitalized
        words = text.split()
        if len(words) < 2 or len(words) > 4:
            return False

        # Check if words are capitalized and contain only letters
        for word in words:
            if not word or not word[0].isupper():
                return False
            # Allow letters, periods, hyphens, apostrophes
            if not re.match(r"^[A-Za-z\.\-\']+$", word):
                return False

        # Exclude common non-name patterns
        excluded = ['over', 'under', 'spread', 'total', 'points', 'rebounds',
                   'assists', 'player', 'props', 'game', 'live', 'more']
        if text.lower() in excluded:
            return False

        return True

    def _parse_player_prop_line(self, line: str, current_player: str, current_prop_type: str) -> dict:
        """Parse a line that contains player prop data."""
        prop_data = {
            "raw_text": line,
            "player": current_player,
            "prop_type": current_prop_type,
            "line": None,
            "over_odds": None,
            "under_odds": None,
            "odds": []
        }

        # Extract line value (O/U number)
        line_match = re.search(r'[OU]\s*(\d+\.?\d*)', line, re.I)
        if line_match:
            prop_data["line"] = float(line_match.group(1))

        # Also look for standalone numbers that could be lines
        if not prop_data["line"]:
            num_match = re.search(r'\b(\d+\.5)\b', line)
            if num_match:
                prop_data["line"] = float(num_match.group(1))

        # Extract all odds
        odds_matches = re.findall(r'([+-]\d{3,4})', line)
        prop_data["odds"] = odds_matches

        # Try to determine over/under odds
        line_lower = line.lower()
        for odds in odds_matches:
            if 'over' in line_lower or 'o ' in line_lower:
                if not prop_data["over_odds"]:
                    prop_data["over_odds"] = odds
            elif 'under' in line_lower or 'u ' in line_lower:
                if not prop_data["under_odds"]:
                    prop_data["under_odds"] = odds

        return prop_data

    def _parse_player_prop_element(self, text: str) -> dict:
        """Parse a player prop element text."""
        lines = text.split('\n')

        prop_data = {
            "raw_text": text[:500],
            "player": None,
            "prop_type": None,
            "line": None,
            "over_odds": None,
            "under_odds": None,
            "odds": []
        }

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check for player name
            if not prop_data["player"] and self._is_player_name(line):
                prop_data["player"] = line
                continue

            # Check for prop type
            prop_types = ['points', 'rebounds', 'assists', '3-pointers', 'threes',
                         'steals', 'blocks', 'turnovers', 'pts + reb', 'pts + ast',
                         'reb + ast', 'pts + reb + ast', 'fantasy']
            for pt in prop_types:
                if pt.lower() in line.lower():
                    prop_data["prop_type"] = pt
                    break

            # Extract line value
            line_match = re.search(r'[OU]\s*(\d+\.?\d*)', line, re.I)
            if line_match:
                prop_data["line"] = float(line_match.group(1))

            # Extract odds
            odds_matches = re.findall(r'([+-]\d{3,4})', line)
            prop_data["odds"].extend(odds_matches)

            # Categorize odds
            line_lower = line.lower()
            for odds in odds_matches:
                if 'over' in line_lower or line.startswith('O'):
                    prop_data["over_odds"] = odds
                elif 'under' in line_lower or line.startswith('U'):
                    prop_data["under_odds"] = odds

        return prop_data if (prop_data["player"] or prop_data["odds"]) else None

    def save_match_data(self, data: dict, match_info: str) -> str:
        """Save data to JSON file in matchup folder."""
        # Clean match info for folder name
        folder_name = self._clean_filename(match_info)

        # Add date to folder name
        date_str = self.scraped_date or datetime.now().strftime('%Y-%m-%d')
        folder_name = f"{date_str}_{folder_name}"

        # Create folder path
        folder_path = Path(self.OUTPUT_BASE_PATH) / folder_name
        folder_path.mkdir(parents=True, exist_ok=True)

        # Create filename with timestamp and prop type
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prop_type = data.get("type", "props")
        filename = f"{prop_type}_{timestamp}.json"

        # Full file path
        file_path = folder_path / filename

        # Add metadata
        data["metadata"] = {
            "source": "Hard Rock Bet",
            "sport": "NBA",
            "match": match_info,
            "scraped_at": datetime.now().isoformat(),
            "date": self.scraped_date,
            "url": self.driver.current_url if self.driver else None
        }

        # Save JSON
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"  Saved to: {file_path}")
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
        return cleaned[:80]  # Limit length


def main():
    """Main function to run the NBA scraper."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='NBA Props Scraper for Hard Rock Bet')
    parser.add_argument('--date', '-d', type=str, default=None,
                        help="Date to scrape: 'today', 'tomorrow', or YYYY-MM-DD format")
    parser.add_argument('--prop-type', '-p', type=str, default=None, choices=['player', 'game', 'both'],
                        help="Type of props to scrape: 'player', 'game', or 'both'")
    parser.add_argument('--headless', action='store_true',
                        help="Run browser in headless mode")
    parser.add_argument('--no-pause', action='store_true',
                        help="Don't pause for user input at the end")
    parser.add_argument('--debug', action='store_true',
                        help="Save screenshots and page source for debugging")
    parser.add_argument('--url', '-u', type=str, default=None,
                        help="Custom URL to scrape (if not using default Hard Rock Bet URL)")

    args = parser.parse_args()

    print("=" * 70)
    print("       HARD ROCK BET - NBA PROPS SCRAPER")
    print("=" * 70)
    print()

    # STEP 1: Get date from user or args
    if args.date:
        target_date = args.date
        print(f"Using date from command line: {target_date}")
    else:
        print("-" * 50)
        print("STEP 1: Select Date")
        print("-" * 50)
        print("\nEnter the date you want to scrape:")
        print("  - 'today' for today's games")
        print("  - 'tomorrow' for tomorrow's games")
        print("  - Or enter date in YYYY-MM-DD format (e.g., 2024-01-15)")
        print()

        target_date = input("Enter date: ").strip()
        if not target_date:
            target_date = 'today'
            print("Using today's date")

    # STEP 2: Get prop type from user or args
    if args.prop_type:
        prop_type = args.prop_type
        print(f"Using prop type from command line: {prop_type.upper()}")
    else:
        print()
        print("-" * 50)
        print("STEP 2: Select Prop Type")
        print("-" * 50)
        print("\n  1. Player Props (all player props for each game)")
        print("  2. Game Props (spreads, totals, moneylines)")
        print("  3. Both Player and Game Props")
        print()

        while True:
            prop_choice = input("Enter your choice (1-3): ").strip()
            if prop_choice in ['1', '2', '3']:
                break
            print("Invalid choice. Please enter 1, 2, or 3.")

        prop_type_map = {
            '1': 'player',
            '2': 'game',
            '3': 'both'
        }
        prop_type = prop_type_map[prop_choice]

    print(f"\nSelected: {prop_type.upper()} props")

    # STEP 3: Initialize scraper and start
    print()
    print("-" * 50)
    print("STEP 3: Initializing Browser")
    print("-" * 50)

    scraper = NBAHardRockScraper(headless=args.headless if hasattr(args, 'headless') else False)

    try:
        print("\nStarting Chrome browser...")
        scraper.setup_driver()
        scraper.prop_type = prop_type

        # Navigate to NBA page or custom URL
        if args.url:
            print(f"\nNavigating to custom URL: {args.url}")
            scraper.driver.get(args.url)
            time.sleep(4)
        else:
            scraper.navigate_to_nba()

        # Try to select the date
        scraper.select_date(target_date)

        # STEP 4: Scrape all matches
        print()
        print("-" * 50)
        print("STEP 4: Finding All NBA Matches")
        print("-" * 50)

        matches = scraper.scrape_all_matches(debug=args.debug if hasattr(args, 'debug') else False)

        if not matches:
            print("\nNo matches found automatically.")
            print("The page structure may have changed or there are no games for this date.")

            # Only ask for manual intervention if not in no-pause mode
            if not args.no_pause:
                print("\nPlease manually navigate to the NBA page with games.")
                input("Press Enter when you see the games list...")
                matches = scraper.scrape_all_matches(debug=args.debug if hasattr(args, 'debug') else False)

        if not matches:
            print("\nNo matches found. Exiting...")
            if not args.no_pause:
                input("Press Enter to close...")
            return

        print(f"\nFound {len(matches)} NBA matches to scrape:")
        for i, match in enumerate(matches, 1):
            print(f"  {i}. {match['teams']}")

        # STEP 5: Scrape each match
        print()
        print("-" * 50)
        print("STEP 5: Scraping All Matches")
        print("-" * 50)

        results = {
            "date": target_date,
            "prop_type": prop_type,
            "matches_scraped": 0,
            "files_created": [],
            "errors": []
        }

        for i, match in enumerate(matches, 1):
            print(f"\n[{i}/{len(matches)}] Scraping: {match['teams']}")
            print("-" * 40)

            try:
                # Navigate back to main page before each game (to refresh elements)
                if i > 1:
                    print("  Returning to NBA page...")
                    if args.url:
                        scraper.driver.get(args.url)
                    else:
                        scraper.navigate_to_nba()
                    time.sleep(4)

                    # Re-find the game element by searching for team names
                    try:
                        game_containers = scraper.driver.find_elements(By.CSS_SELECTOR, ".hr-market-view")
                        game_found = False

                        # Extract individual team names from the match
                        team_parts = match['teams'].split(' vs ')
                        if len(team_parts) == 2:
                            team1, team2 = team_parts[0].strip(), team_parts[1].strip()

                            for idx, container in enumerate(game_containers):
                                container_text = container.text
                                # Check if both teams are in this container
                                if team1 in container_text and team2 in container_text:
                                    # Verify it's not a live game
                                    is_live = any(indicator in container_text for indicator in ["Quarter", "Half Time"])
                                    if not is_live:
                                        more_wagers_btn = container.find_element(By.CSS_SELECTOR, ".more-wagers")
                                        match['game_element'] = more_wagers_btn
                                        game_found = True
                                        print(f"  Re-found game element")
                                        break

                        if not game_found:
                            print(f"  Could not re-find game element for {match['teams']}")
                            results["errors"].append(f"Element not found: {match['teams']}")
                            continue
                    except Exception as e:
                        print(f"  Error re-finding element: {e}")
                        results["errors"].append(f"Element refresh failed: {match['teams']}")
                        continue

                if not scraper.navigate_to_match(match):
                    print(f"  Failed to navigate to match")
                    results["errors"].append(f"Navigation failed: {match['teams']}")
                    continue

                # Scrape based on prop type
                if prop_type in ['player', 'both']:
                    print("  Scraping player props...")
                    player_props = scraper.scrape_all_player_props()
                    file_path = scraper.save_match_data(player_props, match['teams'])
                    results["files_created"].append(file_path)
                    print(f"  Found {player_props.get('total_props_found', 0)} player props for {player_props.get('total_players', 0)} players")

                if prop_type in ['game', 'both']:
                    print("  Scraping game props...")
                    game_props = scraper.scrape_all_game_props()
                    file_path = scraper.save_match_data(game_props, match['teams'])
                    results["files_created"].append(file_path)
                    total_game_props = (len(game_props.get('moneyline', [])) +
                                       len(game_props.get('spread', [])) +
                                       len(game_props.get('total', [])))
                    print(f"  Found {total_game_props} game prop markets")

                results["matches_scraped"] += 1

                # Small delay between matches
                time.sleep(2)

            except Exception as e:
                print(f"  Error scraping match: {e}")
                results["errors"].append(f"{match['teams']}: {str(e)}")

        # STEP 6: Summary
        print()
        print("=" * 70)
        print("                    SCRAPING COMPLETE")
        print("=" * 70)
        print(f"\nDate: {target_date}")
        print(f"Prop Type: {prop_type}")
        print(f"Matches Scraped: {results['matches_scraped']} / {len(matches)}")
        print(f"Files Created: {len(results['files_created'])}")
        print(f"\nOutput Directory: {scraper.OUTPUT_BASE_PATH}")

        if results["files_created"]:
            print("\nFiles saved:")
            for f in results["files_created"]:
                print(f"  - {Path(f).name}")

        if results["errors"]:
            print(f"\nErrors ({len(results['errors'])}):")
            for err in results["errors"]:
                print(f"  - {err}")

        # Save summary file
        summary_path = Path(scraper.OUTPUT_BASE_PATH) / f"scrape_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(summary_path, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nSummary saved to: {summary_path}")

    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        if not args.no_pause:
            input("\nPress Enter to close the browser...")
        scraper.close()


if __name__ == "__main__":
    main()
