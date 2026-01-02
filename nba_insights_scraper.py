#!/usr/bin/env python3
"""
NBA Insights Scraper - Outlier.bet Premium Data Collector
Scrapes NBA insights including player/team performance patterns, prop types, and odds.
"""

import asyncio
import json
import hashlib
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from playwright.async_api import async_playwright, Page, Browser

# Configuration
BASE_URL = "https://app.outlier.bet"
LOGIN_URL = f"{BASE_URL}/login"
INSIGHTS_URL = f"{BASE_URL}/NBA/trending/insights"

# Default credentials (can be overridden via .env or interactive input)
DEFAULT_EMAIL = "DaSaSilvaDub@gmail.com"
DEFAULT_PASSWORD = "Timeisnow11#"

# Output base path
OUTPUT_BASE = Path(r"C:\Users\dasil\My Drive (dasilvadub@gmail.com)\NBA\TEAMS")

# NBA Teams
NBA_TEAMS = [
    "ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW",
    "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK",
    "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS"
]

# Prop Types
PROP_TYPES = [
    "Points", "Rebounds", "Three Pointers", "Assists", "Steals", "Blocks",
    "Points+Rebounds", "Points+Assists", "Rebounds+Assists",
    "Points+Rebounds+Assists", "Double Double", "Triple Double",
    "Turnovers", "Fantasy Score"
]

# Insight Types
INSIGHT_TYPES = ["All Insights", "Team", "Player"]


class NBAInsightsScraper:
    def __init__(self, email: str = None, password: str = None, headless: bool = False):
        self.email = email or DEFAULT_EMAIL
        self.password = password or DEFAULT_PASSWORD
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.collected_insights = []
        self.metadata = {
            "scrape_date": "",
            "scrape_time": "",
            "teams_collected": [],
            "insight_types": [],
            "prop_types": [],
            "total_insights": 0
        }

    async def initialize(self):
        """Initialize the browser and create a new page."""
        print("\n🏀 NBA Insights Scraper - Initializing...")
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=self.headless,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        self.page = await context.new_page()
        print("✓ Browser initialized successfully")

    async def login(self) -> bool:
        """Authenticate with premium credentials."""
        print(f"\n🔐 Logging in as {self.email}...")

        try:
            await self.page.goto(LOGIN_URL, wait_until='networkidle', timeout=30000)
            await asyncio.sleep(2)

            # Look for email/username input field
            email_selectors = [
                'input[type="email"]',
                'input[name="email"]',
                'input[placeholder*="email" i]',
                'input[placeholder*="Email" i]',
                'input[id*="email" i]',
                '#email',
                'input[type="text"]'
            ]

            email_input = None
            for selector in email_selectors:
                try:
                    email_input = await self.page.wait_for_selector(selector, timeout=3000)
                    if email_input:
                        break
                except:
                    continue

            if not email_input:
                print("⚠ Could not find email input field. Trying alternative approach...")
                # Try to find any input field
                inputs = await self.page.query_selector_all('input')
                if len(inputs) >= 2:
                    email_input = inputs[0]
                else:
                    print("✗ Could not locate login form")
                    return False

            # Enter email
            await email_input.click()
            await email_input.fill(self.email)
            await asyncio.sleep(0.5)

            # Look for password input field
            password_selectors = [
                'input[type="password"]',
                'input[name="password"]',
                'input[placeholder*="password" i]',
                '#password'
            ]

            password_input = None
            for selector in password_selectors:
                try:
                    password_input = await self.page.wait_for_selector(selector, timeout=3000)
                    if password_input:
                        break
                except:
                    continue

            if not password_input:
                print("✗ Could not find password input field")
                return False

            # Enter password
            await password_input.click()
            await password_input.fill(self.password)
            await asyncio.sleep(0.5)

            # Find and click login/submit button
            login_selectors = [
                'button[type="submit"]',
                'button:has-text("Log in")',
                'button:has-text("Login")',
                'button:has-text("Sign in")',
                'button:has-text("Sign In")',
                'input[type="submit"]',
                'button[class*="login" i]',
                'button[class*="submit" i]'
            ]

            login_button = None
            for selector in login_selectors:
                try:
                    login_button = await self.page.wait_for_selector(selector, timeout=2000)
                    if login_button:
                        break
                except:
                    continue

            if login_button:
                await login_button.click()
            else:
                # Try pressing Enter
                await password_input.press('Enter')

            # Wait for navigation/login to complete
            await asyncio.sleep(5)

            # Check if login was successful by looking for dashboard elements or URL change
            current_url = self.page.url
            if 'login' not in current_url.lower() or 'dashboard' in current_url.lower():
                print("✓ Login successful!")
                return True

            # Check for error messages
            error_selectors = [
                '.error', '.alert-error', '[class*="error"]',
                'text=Invalid', 'text=incorrect', 'text=wrong'
            ]
            for selector in error_selectors:
                try:
                    error = await self.page.query_selector(selector)
                    if error:
                        error_text = await error.inner_text()
                        print(f"✗ Login failed: {error_text}")
                        return False
                except:
                    continue

            print("✓ Login appears successful")
            return True

        except Exception as e:
            print(f"✗ Login error: {str(e)}")
            return False

    async def navigate_to_insights(self) -> bool:
        """Navigate to the NBA insights page."""
        print("\n📊 Navigating to NBA Insights...")
        try:
            await self.page.goto(INSIGHTS_URL, wait_until='networkidle', timeout=30000)
            await asyncio.sleep(3)
            print("✓ Navigated to insights page")
            return True
        except Exception as e:
            print(f"✗ Navigation error: {str(e)}")
            return False

    async def apply_filters(self, teams: list, insight_type: str, prop_types: list):
        """Apply selected filters to the insights page."""
        print(f"\n🔍 Applying filters...")
        print(f"   Teams: {', '.join(teams) if teams else 'All'}")
        print(f"   Insight Type: {insight_type}")
        print(f"   Prop Types: {', '.join(prop_types) if prop_types else 'All'}")

        try:
            # Try to find and interact with filter elements
            # This section may need adjustment based on the actual site structure

            # Look for filter buttons/dropdowns
            filter_selectors = [
                'button:has-text("Filter")',
                'button:has-text("Teams")',
                '[class*="filter"]',
                '[data-testid*="filter"]'
            ]

            # Try to find insight type filter
            if insight_type and insight_type != "All Insights":
                try:
                    insight_buttons = await self.page.query_selector_all(f'button:has-text("{insight_type}")')
                    for btn in insight_buttons:
                        try:
                            await btn.click()
                            await asyncio.sleep(1)
                            break
                        except:
                            continue
                except:
                    pass

            # Try to find team filters
            if teams:
                for team in teams:
                    try:
                        team_element = await self.page.query_selector(f'[data-team="{team}"], button:has-text("{team}")')
                        if team_element:
                            await team_element.click()
                            await asyncio.sleep(0.5)
                    except:
                        continue

            await asyncio.sleep(2)
            print("✓ Filters applied (if available)")
            return True

        except Exception as e:
            print(f"⚠ Filter application warning: {str(e)}")
            return True  # Continue even if filters fail

    async def scroll_and_load_all(self):
        """Scroll to load all lazy-loaded content."""
        print("\n📜 Loading all content (scrolling)...")

        last_height = 0
        scroll_attempts = 0
        max_attempts = 20

        while scroll_attempts < max_attempts:
            # Scroll to bottom
            await self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await asyncio.sleep(1.5)

            # Get new height
            new_height = await self.page.evaluate('document.body.scrollHeight')

            if new_height == last_height:
                scroll_attempts += 1
                if scroll_attempts >= 3:
                    break
            else:
                scroll_attempts = 0
                last_height = new_height
                print(f"   Scrolling... loaded more content")

        # Scroll back to top
        await self.page.evaluate('window.scrollTo(0, 0)')
        await asyncio.sleep(1)
        print("✓ All content loaded")

    async def extract_insights(self) -> list:
        """Extract all insight cards from the page."""
        print("\n📊 Extracting insights...")
        insights = []

        # Common selectors for insight cards - adjust based on actual site structure
        card_selectors = [
            '[class*="insight-card"]',
            '[class*="InsightCard"]',
            '[class*="card"]',
            '[data-testid*="insight"]',
            'article',
            '.insight',
            '[class*="trending-card"]'
        ]

        cards = []
        for selector in card_selectors:
            try:
                found_cards = await self.page.query_selector_all(selector)
                if found_cards and len(found_cards) > 0:
                    cards = found_cards
                    print(f"   Found {len(cards)} cards using selector: {selector}")
                    break
            except:
                continue

        if not cards:
            # Try a more generic approach - get all potential card elements
            print("   Trying alternative card detection...")
            try:
                cards = await self.page.query_selector_all('div[class*="card"], div[class*="Card"]')
                print(f"   Found {len(cards)} potential cards")
            except:
                pass

        for i, card in enumerate(cards):
            try:
                insight = await self.parse_insight_card(card, i)
                if insight and insight.get('insight_description'):
                    insights.append(insight)
            except Exception as e:
                print(f"   ⚠ Error parsing card {i}: {str(e)}")
                continue

        print(f"✓ Extracted {len(insights)} valid insights")
        return insights

    async def parse_insight_card(self, card, index: int) -> dict:
        """Parse a single insight card element."""
        insight = {
            "id": "",
            "insight_type": "",
            "player_name": "",
            "player_team": "",
            "opponent_team": "",
            "matchup": "",
            "game_datetime": "",
            "insight_description": "",
            "prop_type": "",
            "prop_line": None,
            "outcome": "",
            "hit_rate_percentage": None,
            "odds_value": None,
            "sportsbook": "",
            "detailed_url": ""
        }

        try:
            # Get all text content from the card
            text_content = await card.inner_text()
            html_content = await card.inner_html()

            # Parse player name - usually prominent in the card
            name_patterns = [
                r'([A-Z][a-z]+ [A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',  # First Last or First Middle Last
            ]
            for pattern in name_patterns:
                match = re.search(pattern, text_content)
                if match:
                    potential_name = match.group(1)
                    # Validate it's not a team name or other text
                    if len(potential_name.split()) >= 2 and potential_name not in NBA_TEAMS:
                        insight['player_name'] = potential_name
                        break

            # Parse team abbreviation
            team_pattern = r'\b(' + '|'.join(NBA_TEAMS) + r')\b'
            teams_found = re.findall(team_pattern, text_content)
            if teams_found:
                insight['player_team'] = teams_found[0]
                if len(teams_found) >= 2:
                    insight['opponent_team'] = teams_found[1]

            # Parse matchup (e.g., "HOU @ BKN" or "LAL vs GSW")
            matchup_pattern = r'([A-Z]{3})\s*[@vs]+\s*([A-Z]{3})'
            matchup_match = re.search(matchup_pattern, text_content, re.IGNORECASE)
            if matchup_match:
                insight['matchup'] = f"{matchup_match.group(1)} @ {matchup_match.group(2)}"
                if not insight['player_team']:
                    insight['player_team'] = matchup_match.group(1)
                if not insight['opponent_team']:
                    insight['opponent_team'] = matchup_match.group(2)

            # Parse game time
            time_patterns = [
                r'(Today|Tomorrow|Yesterday)\s+\d{1,2}:\d{2}\s*(AM|PM)?',
                r'\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2}\s*(AM|PM)?',
                r'\d{1,2}:\d{2}\s*(AM|PM)',
                r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+\d{1,2}:\d{2}'
            ]
            for pattern in time_patterns:
                time_match = re.search(pattern, text_content, re.IGNORECASE)
                if time_match:
                    insight['game_datetime'] = time_match.group(0)
                    break

            # Parse insight description - look for performance pattern text
            desc_patterns = [
                r'has (failed|succeeded|exceeded|hit|missed|gone|covered).+?(?:games?|matchups?|starts?)',
                r'averaging.+?(?:per game|in.+?games)',
                r'\d+ of (?:his |their )?(last )?\d+ games?',
                r'in \d+ (?:straight|consecutive) games?',
            ]
            for pattern in desc_patterns:
                desc_match = re.search(pattern, text_content, re.IGNORECASE)
                if desc_match:
                    # Get more context around the match
                    start = max(0, desc_match.start() - 50)
                    end = min(len(text_content), desc_match.end() + 20)
                    insight['insight_description'] = text_content[start:end].strip()
                    break

            # If no pattern matched, try to get a meaningful description
            if not insight['insight_description'] and len(text_content) > 20:
                # Look for sentences that contain key words
                sentences = text_content.split('.')
                for sentence in sentences:
                    if any(word in sentence.lower() for word in ['points', 'rebounds', 'assists', 'three', 'over', 'under', 'last', 'games']):
                        insight['insight_description'] = sentence.strip()[:200]
                        break

            # Parse prop type and line
            prop_patterns = [
                r'(Under|Over)\s+(\d+\.?\d*)\s*(Points|Rebounds|Assists|Three Pointers|Steals|Blocks|Turnovers|PRA|PR|PA|RA)',
                r'(\d+\.?\d*)\+?\s*(Points|Rebounds|Assists|Three Pointers|Steals|Blocks|Turnovers)',
                r'(Points|Rebounds|Assists|Three Pointers|Steals|Blocks|Turnovers).*?(\d+\.?\d*)',
            ]
            for pattern in prop_patterns:
                prop_match = re.search(pattern, text_content, re.IGNORECASE)
                if prop_match:
                    groups = prop_match.groups()
                    if 'Over' in groups[0] or 'Under' in groups[0]:
                        insight['outcome'] = groups[0]
                        insight['prop_line'] = float(groups[1])
                        insight['prop_type'] = groups[2] if len(groups) > 2 else ""
                    else:
                        for g in groups:
                            if g and re.match(r'\d+\.?\d*', str(g)):
                                insight['prop_line'] = float(g)
                            elif g and g.lower() in [p.lower() for p in PROP_TYPES]:
                                insight['prop_type'] = g
                    break

            # Parse hit rate percentage
            hit_rate_pattern = r'(\d{1,3})%|(\d{1,3})\s*%'
            hit_match = re.search(hit_rate_pattern, text_content)
            if hit_match:
                rate = hit_match.group(1) or hit_match.group(2)
                insight['hit_rate_percentage'] = int(rate)

            # Parse odds
            odds_pattern = r'([+-]\d{3,4})|(\d{3,4})'
            odds_match = re.search(odds_pattern, text_content)
            if odds_match:
                odds = odds_match.group(1) or odds_match.group(2)
                insight['odds_value'] = int(odds)

            # Parse sportsbook
            sportsbooks = ['DraftKings', 'FanDuel', 'BetMGM', 'Caesars', 'PointsBet', 'Underdog', 'PrizePicks', 'BetRivers']
            for sb in sportsbooks:
                if sb.lower() in text_content.lower():
                    insight['sportsbook'] = sb
                    break

            # Determine insight type
            if insight['player_name']:
                insight['insight_type'] = 'Player'
            elif insight['player_team'] or insight['matchup']:
                insight['insight_type'] = 'Team'
            else:
                insight['insight_type'] = 'Unknown'

            # Try to get detailed URL from any links in the card
            try:
                link = await card.query_selector('a')
                if link:
                    href = await link.get_attribute('href')
                    if href:
                        if href.startswith('/'):
                            insight['detailed_url'] = BASE_URL + href
                        elif href.startswith('http'):
                            insight['detailed_url'] = href
            except:
                pass

            # Generate unique ID
            id_string = f"{insight['player_name']}_{insight['matchup']}_{insight['prop_type']}_{insight['prop_line']}"
            insight['id'] = hashlib.md5(id_string.encode()).hexdigest()[:12]

            return insight

        except Exception as e:
            print(f"   Parse error for card {index}: {str(e)}")
            return None

    def save_insights(self, insights: list, teams: list, insight_types: list, prop_types: list,
                      save_mode: str = 'combined'):
        """Save collected insights to JSON files."""
        print(f"\n💾 Saving {len(insights)} insights...")

        # Update metadata
        now = datetime.now()
        self.metadata.update({
            "scrape_date": now.strftime("%Y-%m-%d"),
            "scrape_time": now.strftime("%H:%M:%S"),
            "teams_collected": teams if teams else ["All"],
            "insight_types": insight_types,
            "prop_types": prop_types if prop_types else ["All"],
            "total_insights": len(insights)
        })

        # Ensure base output directory exists
        OUTPUT_BASE.mkdir(parents=True, exist_ok=True)

        if save_mode == 'combined':
            # Save all insights to a single file
            output_data = {
                "metadata": self.metadata,
                "insights": insights
            }
            output_file = OUTPUT_BASE / "all_insights.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            print(f"✓ Saved combined insights to: {output_file}")

        elif save_mode == 'by_team':
            # Group insights by team and save separately
            team_insights = {}
            for insight in insights:
                team = insight.get('player_team', 'Unknown')
                if team not in team_insights:
                    team_insights[team] = []
                team_insights[team].append(insight)

            for team, team_data in team_insights.items():
                team_folder = OUTPUT_BASE / team
                team_folder.mkdir(parents=True, exist_ok=True)

                output_data = {
                    "metadata": {
                        **self.metadata,
                        "teams_collected": [team],
                        "total_insights": len(team_data)
                    },
                    "insights": team_data
                }

                output_file = team_folder / "insights.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(output_data, f, indent=2, ensure_ascii=False)
                print(f"✓ Saved {len(team_data)} insights for {team} to: {output_file}")

        print(f"\n✓ All insights saved successfully!")

    async def close(self):
        """Close the browser."""
        if self.browser:
            await self.browser.close()
            print("\n✓ Browser closed")


def display_menu(title: str, options: list, allow_multiple: bool = False, allow_all: bool = True) -> list:
    """Display an interactive menu and return selected options."""
    print(f"\n{'='*50}")
    print(f" {title}")
    print('='*50)

    if allow_all:
        print(" 0. All")

    for i, option in enumerate(options, 1):
        print(f" {i}. {option}")

    print('='*50)

    if allow_multiple:
        print("Enter numbers separated by commas (e.g., 1,3,5) or 0 for All:")
    else:
        print("Enter your choice:")

    while True:
        try:
            choice = input("> ").strip()

            if choice == '0' and allow_all:
                return options if allow_multiple else [options[0]]

            if allow_multiple:
                indices = [int(x.strip()) for x in choice.split(',')]
                selected = [options[i-1] for i in indices if 0 < i <= len(options)]
                if selected:
                    return selected
            else:
                idx = int(choice)
                if 0 < idx <= len(options):
                    return [options[idx-1]]

            print("Invalid selection. Please try again.")
        except ValueError:
            print("Please enter valid number(s).")


async def main():
    """Main entry point for the scraper."""
    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║            🏀 NBA INSIGHTS SCRAPER - Outlier.bet 🏀           ║
    ║         Premium Data Collection for Sports Analytics          ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)

    # Step 1: Credentials
    print("\n📧 Using configured credentials...")
    email = DEFAULT_EMAIL
    password = DEFAULT_PASSWORD
    print(f"   Email: {email}")

    use_default = input("\nUse default credentials? (Y/n): ").strip().lower()
    if use_default == 'n':
        email = input("Enter email: ").strip() or DEFAULT_EMAIL
        password = input("Enter password: ").strip() or DEFAULT_PASSWORD

    # Step 2: Team Selection
    team_mode = display_menu(
        "SELECT SCRAPING MODE",
        ["Single team", "Multiple teams", "All teams"],
        allow_multiple=False,
        allow_all=False
    )[0]

    selected_teams = []
    if team_mode == "Single team":
        selected_teams = display_menu("SELECT TEAM", NBA_TEAMS, allow_multiple=False, allow_all=False)
    elif team_mode == "Multiple teams":
        selected_teams = display_menu("SELECT TEAMS", NBA_TEAMS, allow_multiple=True, allow_all=False)
    else:  # All teams
        selected_teams = NBA_TEAMS.copy()

    # Step 3: Insight Type Selection
    selected_insight_types = display_menu(
        "SELECT INSIGHT TYPE",
        INSIGHT_TYPES,
        allow_multiple=True,
        allow_all=True
    )

    # Step 4: Prop Type Selection
    selected_prop_types = display_menu(
        "SELECT PROP TYPES",
        PROP_TYPES,
        allow_multiple=True,
        allow_all=True
    )

    # Step 5: Save Mode
    save_mode = display_menu(
        "SELECT SAVE MODE",
        ["Combined (single JSON file)", "By Team (separate folders)"],
        allow_multiple=False,
        allow_all=False
    )[0]
    save_mode = 'combined' if 'Combined' in save_mode else 'by_team'

    # Step 6: Confirm and Start
    print("\n" + "="*50)
    print(" SCRAPING CONFIGURATION SUMMARY")
    print("="*50)
    print(f" Teams: {', '.join(selected_teams[:5])}{'...' if len(selected_teams) > 5 else ''}")
    print(f" Insight Types: {', '.join(selected_insight_types)}")
    print(f" Prop Types: {', '.join(selected_prop_types[:5])}{'...' if len(selected_prop_types) > 5 else ''}")
    print(f" Save Mode: {save_mode}")
    print("="*50)

    confirm = input("\nStart scraping? (Y/n): ").strip().lower()
    if confirm == 'n':
        print("Scraping cancelled.")
        return

    # Initialize scraper
    scraper = NBAInsightsScraper(email=email, password=password, headless=False)

    try:
        await scraper.initialize()

        # Login
        if not await scraper.login():
            print("\n❌ Login failed. Please check your credentials.")
            return

        # Navigate to insights
        if not await scraper.navigate_to_insights():
            print("\n❌ Failed to navigate to insights page.")
            return

        # Apply filters
        primary_insight_type = selected_insight_types[0] if selected_insight_types else "All Insights"
        await scraper.apply_filters(selected_teams, primary_insight_type, selected_prop_types)

        # Scroll to load all content
        await scraper.scroll_and_load_all()

        # Extract insights
        all_insights = await scraper.extract_insights()

        # Filter insights based on selections
        filtered_insights = []
        for insight in all_insights:
            # Check team filter
            team_match = (not selected_teams or
                         selected_teams == NBA_TEAMS or
                         insight.get('player_team') in selected_teams or
                         insight.get('opponent_team') in selected_teams)

            # Check insight type filter
            insight_type_match = ("All Insights" in selected_insight_types or
                                 insight.get('insight_type') in selected_insight_types)

            # Check prop type filter (if we could extract prop_type)
            prop_match = (selected_prop_types == PROP_TYPES or
                         not insight.get('prop_type') or
                         any(p.lower() in insight.get('prop_type', '').lower() for p in selected_prop_types))

            if team_match and insight_type_match and prop_match:
                filtered_insights.append(insight)

        print(f"\n📊 Filtered to {len(filtered_insights)} insights matching your criteria")

        # Save results
        if filtered_insights:
            scraper.save_insights(
                filtered_insights,
                selected_teams,
                selected_insight_types,
                selected_prop_types,
                save_mode
            )
        else:
            print("\n⚠ No insights found matching your criteria.")

    except Exception as e:
        print(f"\n❌ Error during scraping: {str(e)}")
        import traceback
        traceback.print_exc()

    finally:
        await scraper.close()

    print("\n🏁 Scraping complete!")


if __name__ == "__main__":
    asyncio.run(main())
