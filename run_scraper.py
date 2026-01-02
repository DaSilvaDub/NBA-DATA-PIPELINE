"""
Outlier Insights Scraper - Manual Login Version
Scrapes all NBA teams from Outlier.bet
"""

import os
import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

def scrape_outlier():
    # Setup
    target_dir = r"C:\Users\dasil\My Drive (dasilvadub@gmail.com)\NBA\MATCHUP\Outlier_insight"
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    file_path = os.path.join(target_dir, "nba_insights.json")

    # Configure Chrome
    chrome_options = Options()
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])

    print("Starting Chrome...")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.maximize_window()

    try:
        # Go to insights page  (no team filter = all teams)
        print("\nNavigating to Outlier.bet insights page (ALL TEAMS)...")
        driver.get("https://app.outlier.bet/NBA/trending/insights")

        print("\n" + "=" * 60)
        print("MANUAL LOGIN REQUIRED")
        print("=" * 60)
        print("Please log in to Outlier.bet in the browser window that opened.")
        print("After logging in successfully, the insights page should load.")
        print("\nWaiting 60 seconds for you to log in...")
        print("=" * 60 + "\n")

        time.sleep(60)

        # Check if we're still on login page
        if 'login' in driver.current_url.lower():
            print("Still on login page. Waiting another 30 seconds...")
            time.sleep(30)

        # Make sure we're on the insights page
        if '/insights' not in driver.current_url:
            print(f"Navigating to insights page...")
            driver.get("https://app.outlier.bet/NBA/trending/insights")
            time.sleep(5)

        print("\n[OK] Starting to scrape insights...")

        # Scroll to load all insights
        print("Scrolling to load all content...")
        last_height = driver.execute_script("return document.body.scrollHeight")
        scroll_count = 0
        max_scrolls = 20

        while scroll_count < max_scrolls:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.5)

            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                print(f"  Reached end after {scroll_count} scrolls")
                break

            last_height = new_height
            scroll_count += 1
            if scroll_count % 5 == 0:
                print(f"  Scrolled {scroll_count} times...")

        time.sleep(2)
        print("\n[OK] Extracting insights from page...")

        # Extract all text elements that look like insights
        insights_data = []

        # Get all divs, articles, and list items
        elements = driver.find_elements(By.XPATH,
            "//div | //article | //li | //section"
        )

        print(f"  Checking {len(elements)} elements...")

        for elem in elements:
            try:
                text = elem.text.strip()

                # Look for NBA insight patterns
                if (len(text) > 40 and len(text) < 500 and
                    any(keyword in text.lower() for keyword in
                        ['pts', 'points', 'reb', 'rebounds', 'ast', 'assists',
                         'over', 'under', 'exceeded', 'hit', '@', 'vs'])):

                    # Try to get URL
                    url = None
                    try:
                        link = elem.find_element(By.TAG_NAME, 'a')
                        url = link.get_attribute('href')
                    except:
                        pass

                    insight = {
                        "content": text,
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                    }

                    if url and 'outlier.bet' in url:
                        insight["url"] = url

                    insights_data.append(insight)

            except:
                continue

        # Remove duplicates
        seen = {}
        unique_insights = []
        for insight in insights_data:
            # Use first 80 chars as key
            key = insight["content"][:80]
            if key not in seen:
                seen[key] = True
                unique_insights.append(insight)

        insights_data = unique_insights

        print(f"  Found {len(insights_data)} unique insights\n")

        # Save to JSON
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(insights_data, f, indent=2, ensure_ascii=False)

        print("=" * 60)
        print(f"SUCCESS!")
        print(f"Saved {len(insights_data)} insights to:")
        print(f"  {file_path}")
        print("=" * 60)

        if len(insights_data) > 0:
            print("\nFirst 3 insights:")
            for i, insight in enumerate(insights_data[:3], 1):
                print(f"\n{i}. {insight['content'][:100]}...")

        # If no insights found, save debug info
        if len(insights_data) == 0:
            print("\nWARNING: No insights found!")
            print("Saving debug information...")

            debug_html = os.path.join(target_dir, "debug_page.html")
            with open(debug_html, 'w', encoding='utf-8') as f:
                f.write(driver.page_source)

            debug_screenshot = os.path.join(target_dir, "debug_screenshot.png")
            driver.save_screenshot(debug_screenshot)

            print(f"  Debug HTML: {debug_html}")
            print(f"  Screenshot: {debug_screenshot}")

    except Exception as e:
        print(f"\nERROR: {str(e)}")
        try:
            screenshot = os.path.join(target_dir, "error.png")
            driver.save_screenshot(screenshot)
            print(f"  Error screenshot: {screenshot}")
        except:
            pass

    finally:
        print("\nClosing browser in 3 seconds...")
        time.sleep(3)
        driver.quit()
        print("Done!")

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("OUTLIER INSIGHTS SCRAPER")
    print("Scrapes ALL NBA teams (no filter)")
    print("=" * 60)

    scrape_outlier()
