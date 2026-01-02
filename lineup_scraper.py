import requests
from bs4 import BeautifulSoup
import json
import re
import os

def scrape_nba_lineups():
    # 1. Ask for the target date
    target_date = input("Which date's lineups do you want to scrape? (e.g., 12/25): ").strip()
    
    # Define the specific directory path
    save_directory = r"C:\Users\dasil\My Drive (dasilvadub@gmail.com)\NBA\MATCHUP\Starting LineUp"
    
    # 2. Setup the request
    url = "https://basketballmonster.com/nbalineups.aspx"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
    except Exception as e:
        print(f"Error fetching the webpage: {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')

    games_data = []

    # 3. Parsing Logic - Each table represents a game
    tables = soup.find_all('table')

    for table in tables:
        rows = table.find_all('tr')
        if len(rows) < 7:  # Need at least header + team names + 5 positions
            continue

        game_info = {}

        # Row 0: Game header - contains game, time, and betting info
        header_row = rows[0]
        header_text = header_row.get_text(separator="|").strip()

        # Split by newlines to extract game info
        lines = [line.strip() for line in re.split(r'\s*[\r\n]+\s*', header_text) if line.strip() and line.strip() != '|']

        if len(lines) < 2:
            continue

        # Find the game matchup (contains '@')
        game_matchup = ""
        game_time = ""
        betting_str = ""

        for line in lines:
            if '@' in line and 'by' not in line:
                game_matchup = line.replace('|', '').strip()
            elif 'PM' in line or 'AM' in line:
                game_time = line.replace('|', '').strip()
            elif 'by' in line and 'o/u' in line:
                betting_str = line.replace('|', '').strip()

        if not game_matchup:
            continue

        game_info['game'] = game_matchup
        game_info['time'] = game_time

        # Extract Betting Data (Favorite, Spread, O/U)
        fav_match = re.search(r'([A-Z]{3}) by (\d+\.?\d*)', betting_str)
        ou_match = re.search(r'o/u (\d+\.?\d*)', betting_str)

        game_info['betting'] = {
            "favorite": fav_match.group(1) if fav_match else "N/A",
            "spread": float(fav_match.group(2)) if fav_match else 0.0,
            "over_under": float(ou_match.group(1)) if ou_match else 0.0
        }

        # Row 1: Team names in th elements (e.g., " | CLE | @ NYK")
        team_row = rows[1]
        team_cells = team_row.find_all('th')
        team_names = []
        for cell in team_cells:
            text = cell.get_text().strip().replace('@ ', '').replace('@', '')
            if text:
                team_names.append(text)

        if len(team_names) < 2:
            continue

        team_a, team_b = team_names[0], team_names[1]
        game_info['lineups'] = {team_a: {}, team_b: {}}

        # Rows 2-6: Position lineups (PG, SG, SF, PF, C)
        for row in rows[2:7]:
            cols = row.find_all('td')
            if len(cols) < 3:
                continue
            pos = cols[0].get_text().strip()
            # Get player name and clean up status indicators
            player_a = cols[1].get_text(separator=" ").strip()
            player_b = cols[2].get_text(separator=" ").strip()
            # Clean up newlines and extra whitespace from status indicators
            player_a = ' '.join(player_a.split())
            player_b = ' '.join(player_b.split())

            if pos in ['PG', 'SG', 'SF', 'PF', 'C']:
                game_info['lineups'][team_a][pos] = player_a
                game_info['lineups'][team_b][pos] = player_b

        # Only add if we have lineup data
        if game_info['lineups'][team_a] and game_info['lineups'][team_b]:
            games_data.append(game_info)

    # 4. Save to JSON in the specified directory
    filename = f"NBA_Lineups_{target_date.replace('/', '-')}.json"
    full_path = os.path.join(save_directory, filename)
    
    # Create directory if it doesn't exist
    if not os.path.exists(save_directory):
        os.makedirs(save_directory)
        print(f"Created directory: {save_directory}")

    try:
        with open(full_path, "w") as f:
            json.dump(games_data, f, indent=2)
        print(f"\nSuccess! Data saved to: {full_path}")
    except Exception as e:
        print(f"Failed to save file: {e}")

if __name__ == "__main__":
    scrape_nba_lineups()