# NBA Insights Scraper - Outlier.bet

Premium data collection tool for scraping NBA betting insights from Outlier.bet.

## Setup

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Playwright Browsers

```bash
playwright install chromium
```

### 3. Configure Credentials

Credentials are pre-configured in the script and `.env` file. To change them, edit either:
- `.env` file (recommended for security)
- Or modify `DEFAULT_EMAIL` and `DEFAULT_PASSWORD` in the script

## Usage

Run the scraper:

```bash
python nba_insights_scraper.py
```

### Interactive Menu Flow

1. **Confirm/Enter Credentials** - Use default or enter custom credentials
2. **Select Scraping Mode**:
   - Single team
   - Multiple teams
   - All teams
3. **Select Insight Type**:
   - All Insights
   - Team insights
   - Player insights
4. **Select Prop Types**:
   - Points, Rebounds, Three Pointers, Assists, etc.
5. **Select Save Mode**:
   - Combined (single JSON file)
   - By Team (separate folders per team)
6. **Confirm and Start**

## Output Structure

### Combined Mode
```
C:\Users\dasil\My Drive (dasilvadub@gmail.com)\NBA\TEAMS\all_insights.json
```

### By Team Mode
```
C:\Users\dasil\My Drive (dasilvadub@gmail.com)\NBA\TEAMS\
├── LAL\
│   └── insights.json
├── BOS\
│   └── insights.json
└── ...
```

### JSON Format

```json
{
  "metadata": {
    "scrape_date": "2026-01-01",
    "scrape_time": "02:05:17",
    "teams_collected": ["LAL", "BOS"],
    "insight_types": ["Team"],
    "prop_types": ["Rebounds", "Points"],
    "total_insights": 42
  },
  "insights": [
    {
      "id": "unique_hash",
      "insight_type": "Team",
      "player_name": "James Harden",
      "player_team": "LAC",
      "opponent_team": "UTA",
      "matchup": "UTA @ LAC",
      "game_datetime": "Today 10:30 PM",
      "insight_description": "James Harden has failed to exceed 3.5 three pointers...",
      "prop_type": "Three Pointers",
      "prop_line": 3.5,
      "outcome": "Under",
      "hit_rate_percentage": 80,
      "odds_value": -135,
      "sportsbook": "Underdog",
      "detailed_url": "https://app.outlier.bet/NBA/..."
    }
  ]
}
```

## Features

- **Authenticated Access**: Logs into premium account for full data access
- **Dynamic Content Handling**: Automatically scrolls to load lazy-loaded content
- **Flexible Filtering**: Filter by team, insight type, and prop types
- **Multiple Output Modes**: Save combined or by team
- **Error Handling**: Graceful handling of network issues and missing data
- **Session Management**: Maintains login session throughout scraping

## Troubleshooting

### Login Issues
- Verify credentials in `.env` file
- The site may have CAPTCHA or 2FA - run with `headless=False` to manually complete

### No Data Found
- The site structure may have changed - update CSS selectors in the script
- Check if you have an active premium subscription

### Browser Errors
- Run `playwright install chromium` to ensure browser is installed
- Try running with `headless=False` to see what's happening

## Requirements

- Python 3.8+
- Playwright
- Active Outlier.bet premium subscription
