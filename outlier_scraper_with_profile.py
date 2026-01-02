"""
Outlier Insights Scraper - Uses Chrome Profile for Authentication

This version uses your existing Chrome profile, so if you're already logged into
Outlier.bet in Chrome, it will use that session.

IMPORTANT: Close all Chrome windows before running this script!
"""

import os
import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

def scrape_outlier_with_profile():
    # Setup Path and Folders
    target_dir = r"C:\Users\dasil\My Drive (dasilvadub@gmail.com)\NBA\MATCHUP\Outlier_insight"
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    file_path = os.path.join(target_dir, "nba_insights.json")

    # Configure Selenium with Chrome user profile
    chrome_options = Options()

    # Use your Chrome profile - this will use your existing login session
    user_data_dir = os.path.expanduser(r"~\AppData\Local\Google\Chrome\User Data")
    chrome_options.add_argument(f"user-data-dir={user_data_dir}")
    chrome_options.add_argument("--profile-directory=Default")

    # Disable some features to avoid issues
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    print("Starting Chrome with your profile...")
    print("IMPORTANT: Make sure all Chrome windows are closed before running this!")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.maximize_window()

    try:
        # Navigate directly to insights page
        print("Navigating to insights page...")
        insights_url = "https://app.outlier.bet/NBA/trending/insights"
        driver.get(insights_url)

        # Give time to manually login if needed
        print("\nIf you see a login page, please log in manually in the browser window.")
        print("Waiting 10 seconds for page to load (or for you to login)...")
        time.sleep(10)

        # Check current URL
        current_url = driver.current_url
        print(f"Current URL: {current_url}")

        if 'login' in current_url.lower():
            print("\nYou're still on the login page.")
            print("Please log in manually in the browser window, then press Enter here...")
            input("Press Enter after you've logged in...")

            # Navigate to insights again
            driver.get(insights_url)
            time.sleep(5)

        print("Starting to scrape insights...")

        # Scroll to load all insights
        scroll_delay = 1.5
        last_height = driver.execute_script("return document.body.scrollHeight")
        scroll_count = 0
        max_scrolls = 15

        while scroll_count < max_scrolls:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(scroll_delay)

            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                print(f"Reached end of page after {scroll_count} scrolls")
                break

            last_height = new_height
            scroll_count += 1
            print(f"Scroll {scroll_count}...")

        print("Scrolling complete. Extracting insights...")
        time.sleep(2)

        # Extract insights
        insights_data = []

        # Try multiple selector strategies
        containers = driver.find_elements(By.XPATH,
            "//div[contains(@class, 'insight')] | " +
            "//div[contains(@class, 'card')] | " +
            "//div[contains(@class, 'trend')] | " +
            "//article | " +
            "//li[contains(@class, 'item')] | " +
            "//*[contains(@class, 'InsightCard')]"
        )

        print(f"Found {len(containers)} potential containers")

        for container in containers:
            try:
                text = container.text.strip()

                # Filter for meaningful NBA insights
                if len(text) > 30 and any(keyword in text.lower() for keyword in
                    ['pts', 'points', 'reb', 'rebounds', 'ast', 'assists', 'over', 'under',
                     'exceeded', 'hit', 'line', 'vs', '@', 'game', 'streak', 'last', 'player']):

                    url = None
                    try:
                        link = container.find_element(By.TAG_NAME, 'a')
                        url = link.get_attribute('href')
                    except:
                        pass

                    insight_obj = {
                        "content": text,
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                    }

                    if url:
                        insight_obj["url"] = url

                    insights_data.append(insight_obj)

            except Exception as e:
                continue

        # Remove duplicates
        seen = set()
        unique_insights = []
        for insight in insights_data:
            key = insight["content"][:100]
            if key not in seen:
                seen.add(key)
                unique_insights.append(insight)

        insights_data = unique_insights

        # If still no insights found, save debug info
        if len(insights_data) == 0:
            print("\nNo insights found using standard selectors.")
            print("Saving page source for debugging...")

            debug_html = os.path.join(target_dir, "page_debug.html")
            with open(debug_html, 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            print(f"Page source saved to: {debug_html}")

            screenshot = os.path.join(target_dir, "page_screenshot.png")
            driver.save_screenshot(screenshot)
            print(f"Screenshot saved to: {screenshot}")

            print("\nPlease check:")
            print("1. Are you logged in?")
            print("2. Does the page show insights?")
            print("3. Check the screenshot to see what's displayed")

        # Save insights to JSON
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(insights_data, f, indent=4, ensure_ascii=False)

        print(f"\n✓ Successfully saved {len(insights_data)} insights to {file_path}")

        if len(insights_data) > 0:
            print("\nSample insight:")
            print(json.dumps(insights_data[0], indent=2))

    except Exception as e:
        print(f"\nError occurred: {str(e)}")
        try:
            screenshot = os.path.join(target_dir, "error_screenshot.png")
            driver.save_screenshot(screenshot)
            print(f"Error screenshot saved to: {screenshot}")
        except:
            pass
        raise

    finally:
        print("\nClosing browser in 5 seconds...")
        time.sleep(5)
        driver.quit()

if __name__ == "__main__":
    print("=" * 60)
    print("Outlier Insights Scraper - Profile Version")
    print("=" * 60)
    print("\nIMPORTANT: Close ALL Chrome windows before continuing!")
    input("Press Enter when ready...")

    scrape_outlier_with_profile()
