"""
Cleaning the Glass Data Exporter
Automates login and uses the site's built-in "Download this table" feature.

Requirements:
    pip install selenium webdriver-manager pandas

Usage:
    Option 1: Edit config.json with your credentials, then run:
        python ctg_export.py

    Option 2: Pass credentials directly:
        python ctg_export.py --email YOUR_EMAIL --password YOUR_PASSWORD

    Option 3: Use environment variables:
        set CTG_EMAIL=your_email@example.com
        set CTG_PASSWORD=your_password
        python ctg_export.py
"""

import os
import sys
import json
import time
import argparse
import shutil
import csv
from pathlib import Path
from datetime import datetime

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    print("="*60)
    print("ERROR: Required packages not installed!")
    print("="*60)
    print("\nRun this command to install:")
    print("    pip install selenium webdriver-manager pandas")
    print()
    sys.exit(1)

# Paths
SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = Path(r"C:\Users\dasil\My Drive (dasilvadub@gmail.com)\NBA\TEAMS\BOS\CLEANINGdaGLASS")
CONFIG_FILE = SCRIPT_DIR / "config.json"

# All pages to scrape
ALL_PAGES = {
    "players": {
        "url": "https://cleaningtheglass.com/stats/players",
        "folder": "players",
        "name": "Player Statistics",
        "tables": ["main"]
    },
    "summary": {
        "url": "https://cleaningtheglass.com/stats/league/summary",
        "folder": "summary",
        "name": "League Summary",
        "tables": ["main"]
    },
    "fourfactors": {
        "url": "https://cleaningtheglass.com/stats/league/fourfactors",
        "folder": "fourfactors",
        "name": "Four Factors",
        "tables": ["main"]
    },
    "shots": {
        "url": "https://cleaningtheglass.com/stats/league/shots",
        "folder": "shots",
        "name": "Shooting Stats",
        "tables": ["frequency", "accuracy"]  # Multiple tables on this page
    },
    "context": {
        "url": "https://cleaningtheglass.com/stats/league/context",
        "folder": "context",
        "name": "Play Context",
        "tables": ["halfcourt", "transition"]
    },
    "lineups": {
        "url": "https://cleaningtheglass.com/stats/lineups",
        "folder": "lineups",
        "name": "Lineup Stats",
        "tables": ["main"]
    }
}


def load_config():
    """Load configuration from config.json if it exists."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


class CTGExporter:
    def __init__(self, email: str, password: str, headless: bool = False):
        self.email = email
        self.password = password
        self.headless = headless
        self.driver = None
        self.wait = None
        self.download_dir = SCRIPT_DIR / "temp_downloads"
        self.download_dir.mkdir(exist_ok=True)
        self.results = []

    def setup_driver(self):
        """Initialize Chrome with proper download settings."""
        print("[SETUP] Initializing Chrome browser...")

        options = Options()
        if self.headless:
            options.add_argument("--headless=new")

        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")

        # Download preferences
        prefs = {
            "download.default_directory": str(self.download_dir),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "profile.default_content_settings.popups": 0
        }
        options.add_experimental_option("prefs", prefs)

        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            self.wait = WebDriverWait(self.driver, 15)
            print("[SETUP] Browser ready!")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to start browser: {e}")
            return False

    def login(self) -> bool:
        """Log into Cleaning the Glass."""
        print("\n[LOGIN] Navigating to login page...")
        self.driver.get("https://cleaningtheglass.com/login")
        time.sleep(3)

        try:
            # CTG uses WordPress login - the field ID is "user_login"
            email_selectors = [
                (By.ID, "user_login"),
                (By.NAME, "log"),
                (By.ID, "email"),
                (By.NAME, "email"),
                (By.CSS_SELECTOR, "input[type='text']"),
                (By.CSS_SELECTOR, "input[type='email']"),
                (By.CSS_SELECTOR, "input[name='log']"),
            ]

            email_field = None
            for by, selector in email_selectors:
                try:
                    email_field = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((by, selector))
                    )
                    if email_field:
                        print(f"[LOGIN] Found email field with: {by}='{selector}'")
                        break
                except:
                    continue

            if not email_field:
                # Last resort: find all input fields and use the first text/email one
                try:
                    inputs = self.driver.find_elements(By.TAG_NAME, "input")
                    for inp in inputs:
                        inp_type = inp.get_attribute("type")
                        if inp_type in ["text", "email"]:
                            email_field = inp
                            print(f"[LOGIN] Found email field by scanning inputs")
                            break
                except:
                    pass

            if not email_field:
                print("[ERROR] Could not find email/username field")
                # Debug: print page source snippet
                print("[DEBUG] Page title:", self.driver.title)
                return False

            email_field.clear()
            email_field.send_keys(self.email)
            print(f"[LOGIN] Entered email: {self.email[:3]}***")

            # Find password field - CTG uses "user_pass" or "pwd"
            password_selectors = [
                (By.ID, "user_pass"),
                (By.NAME, "pwd"),
                (By.ID, "password"),
                (By.NAME, "password"),
                (By.CSS_SELECTOR, "input[type='password']"),
            ]

            password_field = None
            for by, selector in password_selectors:
                try:
                    password_field = self.driver.find_element(by, selector)
                    if password_field:
                        print(f"[LOGIN] Found password field with: {by}='{selector}'")
                        break
                except:
                    continue

            if not password_field:
                print("[ERROR] Could not find password field")
                return False

            password_field.clear()
            password_field.send_keys(self.password)
            print("[LOGIN] Entered password: ***")

            # Try to find and click submit button first
            submit_clicked = False
            submit_selectors = [
                (By.ID, "wp-submit"),
                (By.NAME, "wp-submit"),
                (By.CSS_SELECTOR, "input[type='submit']"),
                (By.CSS_SELECTOR, "button[type='submit']"),
                (By.CSS_SELECTOR, ".login-submit input"),
            ]

            for by, selector in submit_selectors:
                try:
                    submit_btn = self.driver.find_element(by, selector)
                    submit_btn.click()
                    submit_clicked = True
                    print("[LOGIN] Clicked submit button")
                    break
                except:
                    continue

            if not submit_clicked:
                # Fallback: press Enter
                password_field.send_keys(Keys.RETURN)
                print("[LOGIN] Pressed Enter to submit")

            time.sleep(4)

            # Check if login was successful
            current_url = self.driver.current_url.lower()
            if "login" in current_url and "wp-login" not in current_url:
                # Check for error messages
                try:
                    error = self.driver.find_element(By.CSS_SELECTOR, ".login-error, .error, .alert-danger, #login_error")
                    print(f"[ERROR] Login failed: {error.text[:100]}")
                    return False
                except:
                    pass
                print("[WARNING] May still be on login page, but continuing...")

            # Verify we can access subscriber content
            print("[LOGIN] Checking login status...")
            self.driver.get("https://cleaningtheglass.com/stats/league/summary")
            time.sleep(2)

            # If redirected to login, we're not logged in
            if "login" in self.driver.current_url.lower():
                print("[ERROR] Redirected to login - authentication failed")
                return False

            print("[LOGIN] Success! Logged in.")
            return True

        except Exception as e:
            print(f"[ERROR] Login error: {e}")
            import traceback
            traceback.print_exc()
            return False

    def clear_downloads(self):
        """Clear the temp downloads folder."""
        for f in self.download_dir.glob("*"):
            if f.is_file():
                f.unlink()

    def wait_for_download(self, timeout: int = 30) -> Path:
        """Wait for a download to complete and return the file path."""
        start = time.time()
        while time.time() - start < timeout:
            files = list(self.download_dir.glob("*"))
            # Ignore partial downloads
            complete = [f for f in files if not f.suffix in ['.crdownload', '.tmp', '.part']]
            if complete:
                latest = max(complete, key=lambda x: x.stat().st_mtime)
                # Make sure it's recent and not still being written
                time.sleep(0.5)
                size1 = latest.stat().st_size
                time.sleep(0.5)
                size2 = latest.stat().st_size
                if size1 == size2 and size1 > 0:
                    return latest
            time.sleep(0.5)
        return None

    def find_and_click_download(self) -> bool:
        """Find and click the download link/button."""
        # Look for download links
        try:
            # First try: look for links with "download" text
            links = self.driver.find_elements(By.TAG_NAME, "a")
            for link in links:
                try:
                    text = link.text.lower().strip()
                    href = link.get_attribute("href") or ""
                    if "download" in text or "download" in href.lower():
                        # Scroll into view and click
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", link)
                        time.sleep(0.3)
                        link.click()
                        print(f"[DOWNLOAD] Clicked: '{link.text}'")
                        return True
                except:
                    continue

            # Second try: look for buttons
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            for btn in buttons:
                try:
                    text = btn.text.lower().strip()
                    if "download" in text or "export" in text:
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                        time.sleep(0.3)
                        btn.click()
                        print(f"[DOWNLOAD] Clicked button: '{btn.text}'")
                        return True
                except:
                    continue

            # Third try: JavaScript to find and click
            result = self.driver.execute_script("""
                var links = document.querySelectorAll('a, button');
                for (var i = 0; i < links.length; i++) {
                    var text = links[i].innerText.toLowerCase();
                    if (text.includes('download') || text.includes('export')) {
                        links[i].click();
                        return links[i].innerText;
                    }
                }
                return null;
            """)
            if result:
                print(f"[DOWNLOAD] JS click: '{result}'")
                return True

        except Exception as e:
            print(f"[ERROR] Click error: {e}")

        return False

    def scrape_table_to_json(self, page_key: str) -> dict:
        """Scrape the table directly from the page and convert to JSON."""
        try:
            tables = self.driver.find_elements(By.TAG_NAME, "table")
            if not tables:
                return None

            all_data = []
            for table in tables:
                try:
                    # Get headers
                    headers = []
                    header_row = table.find_element(By.TAG_NAME, "thead")
                    for th in header_row.find_elements(By.TAG_NAME, "th"):
                        headers.append(th.text.strip())

                    # Get rows
                    tbody = table.find_element(By.TAG_NAME, "tbody")
                    for row in tbody.find_elements(By.TAG_NAME, "tr"):
                        cells = row.find_elements(By.TAG_NAME, "td")
                        if cells:
                            row_data = {}
                            for i, cell in enumerate(cells):
                                if i < len(headers):
                                    row_data[headers[i]] = cell.text.strip()
                                else:
                                    row_data[f"col_{i}"] = cell.text.strip()
                            all_data.append(row_data)
                except Exception as e:
                    continue

            return all_data if all_data else None

        except Exception as e:
            print(f"[ERROR] Table scrape error: {e}")
            return None

    def convert_csv_to_json(self, csv_path: Path, json_path: Path):
        """Convert a CSV file to JSON format."""
        try:
            data = []
            with open(csv_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Clean up the row data
                    cleaned = {}
                    for k, v in row.items():
                        if k:  # Skip empty keys
                            cleaned[k.strip()] = v.strip() if v else ""
                    if cleaned:
                        data.append(cleaned)

            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "metadata": {
                        "source": "cleaningtheglass.com",
                        "exported": datetime.now().isoformat(),
                        "records": len(data)
                    },
                    "data": data
                }, f, indent=2)

            return True
        except Exception as e:
            print(f"[ERROR] CSV to JSON conversion failed: {e}")
            return False

    def export_page(self, page_key: str, config: dict) -> dict:
        """Export data from a single page."""
        result = {
            "page": page_key,
            "name": config["name"],
            "url": config["url"],
            "success": False,
            "files": [],
            "error": None
        }

        print(f"\n{'='*60}")
        print(f"[EXPORT] {config['name']}")
        print(f"[EXPORT] URL: {config['url']}")
        print('='*60)

        try:
            # Navigate to page
            self.driver.get(config["url"])
            time.sleep(3)

            # Wait for content to load
            try:
                self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
                print("[EXPORT] Page loaded with table content")
            except:
                print("[EXPORT] Page loaded (no table detected)")

            # Clear old downloads
            self.clear_downloads()

            # Try to click download button
            if self.find_and_click_download():
                time.sleep(2)

                # Wait for file
                downloaded = self.wait_for_download()

                if downloaded:
                    # Create output folder
                    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

                    # Determine file names
                    timestamp = datetime.now().strftime("%Y%m%d")
                    original_ext = downloaded.suffix.lower()

                    # Save original file - use config name for clarity
                    new_name = f"{config['folder'].upper()}_{timestamp}{original_ext}"
                    final_path = OUTPUT_DIR / new_name
                    shutil.copy2(downloaded, final_path)
                    result["files"].append(str(final_path))
                    print(f"[EXPORT] Saved: {final_path.name}")

                    # Convert to JSON if it's a CSV
                    if original_ext == '.csv':
                        json_name = f"{config['folder'].upper()}_{timestamp}.json"
                        json_path = OUTPUT_DIR / json_name
                        if self.convert_csv_to_json(downloaded, json_path):
                            result["files"].append(str(json_path))
                            print(f"[EXPORT] Converted to: {json_path.name}")

                    result["success"] = True
                    downloaded.unlink()  # Clean up temp file

                else:
                    result["error"] = "Download did not complete"
                    print("[ERROR] Download timeout")
            else:
                # Fallback: scrape table directly
                print("[EXPORT] No download button found, scraping table directly...")
                table_data = self.scrape_table_to_json(page_key)

                if table_data:
                    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

                    timestamp = datetime.now().strftime("%Y%m%d")
                    json_path = OUTPUT_DIR / f"{config['folder'].upper()}_{timestamp}.json"

                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump({
                            "metadata": {
                                "source": config["url"],
                                "exported": datetime.now().isoformat(),
                                "method": "table_scrape",
                                "records": len(table_data)
                            },
                            "data": table_data
                        }, f, indent=2)

                    result["files"].append(str(json_path))
                    result["success"] = True
                    print(f"[EXPORT] Scraped and saved: {json_path.name}")
                else:
                    result["error"] = "No download button and table scrape failed"

        except Exception as e:
            result["error"] = str(e)
            print(f"[ERROR] Export failed: {e}")

        return result

    def run(self, pages: list = None):
        """Run the exporter."""
        print("\n" + "="*60)
        print("CLEANING THE GLASS DATA EXPORTER")
        print("="*60)

        if not self.setup_driver():
            return

        try:
            if not self.login():
                print("\n[FATAL] Login failed. Please check your credentials.")
                return

            # Determine which pages to export
            pages_to_export = pages if pages else list(ALL_PAGES.keys())

            for page_key in pages_to_export:
                if page_key in ALL_PAGES:
                    result = self.export_page(page_key, ALL_PAGES[page_key])
                    self.results.append(result)
                    time.sleep(1)

            # Summary
            self.print_summary()

        finally:
            if self.driver:
                self.driver.quit()
                print("\n[DONE] Browser closed")

            # Clean up temp folder
            try:
                shutil.rmtree(self.download_dir)
            except:
                pass

    def print_summary(self):
        """Print export summary."""
        print("\n" + "="*60)
        print("EXPORT SUMMARY")
        print("="*60)

        success = sum(1 for r in self.results if r["success"])
        failed = len(self.results) - success

        print(f"\nTotal: {len(self.results)} | Success: {success} | Failed: {failed}")

        if success > 0:
            print("\nSuccessful exports:")
            for r in self.results:
                if r["success"]:
                    print(f"  + {r['name']}")
                    for f in r["files"]:
                        print(f"      -> {Path(f).name}")

        if failed > 0:
            print("\nFailed exports:")
            for r in self.results:
                if not r["success"]:
                    print(f"  - {r['name']}: {r['error']}")

        # Save summary
        summary_path = OUTPUT_DIR / "export_summary.json"
        with open(summary_path, 'w') as f:
            json.dump({
                "export_date": datetime.now().isoformat(),
                "success_count": success,
                "failed_count": failed,
                "results": self.results
            }, f, indent=2)
        print(f"\nSummary saved to: {summary_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Export data from Cleaning the Glass",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python ctg_export.py --email user@email.com --password mypass
  python ctg_export.py --pages summary fourfactors
  python ctg_export.py --headless

Environment variables (alternative to --email/--password):
  CTG_EMAIL - Your Cleaning the Glass email
  CTG_PASSWORD - Your Cleaning the Glass password
        """
    )

    parser.add_argument("-e", "--email", help="CTG account email")
    parser.add_argument("-p", "--password", help="CTG account password")
    parser.add_argument("--headless", action="store_true", help="Run without visible browser")
    parser.add_argument("--pages", nargs="+", choices=list(ALL_PAGES.keys()),
                        help="Specific pages to export (default: all)")

    args = parser.parse_args()

    # Get credentials from: args > env > config
    email = args.email or os.environ.get("CTG_EMAIL")
    password = args.password or os.environ.get("CTG_PASSWORD")

    if not email or not password:
        config = load_config()
        creds = config.get("credentials", {})
        email = email or creds.get("email")
        password = password or creds.get("password")

    if not email or not password or "YOUR_" in str(email) or "YOUR_" in str(password):
        print("="*60)
        print("ERROR: Credentials required!")
        print("="*60)
        print("\nProvide your Cleaning the Glass credentials via one of:")
        print("  1. Command line: --email EMAIL --password PASSWORD")
        print("  2. Environment: CTG_EMAIL and CTG_PASSWORD")
        print("  3. Edit config.json with your credentials")
        print()
        sys.exit(1)

    exporter = CTGExporter(
        email=email,
        password=password,
        headless=args.headless
    )
    exporter.run(pages=args.pages)


if __name__ == "__main__":
    main()
