import pandas as pd
import utils

df = pd.read_csv(utils.get_latest_data_filepath().strip('Data/'), 
                header=None, 
                names = ['neutral', 'away', 'ascore', 'home', 'hscore', 'date', 'aspread'])

# Get all team appearances in both home and away columns
away_teams = df[['away', 'date']].rename(columns={'away': 'team'})
home_teams = df[['home', 'date']].rename(columns={'home': 'team'})
all_teams = pd.concat([away_teams, home_teams])

def check_1():
    # Find all the team names in our data log and finds their first and last appearance dates
    # Group by team and calculate first date, last date, and count
    team_stats = all_teams.groupby('team').agg({
        'date': ['min', 'max', 'count']
    }).reset_index()

    # Rename columns
    team_stats.columns = ['team', 'first_appearance', 'last_appearance', 'total_appearances']

    # Output team stats to CSV
    team_stats.to_csv('Data/team_stats_health_check_1.csv', index=False)

def check_2():
    # Count games since start of 2024-25 season
    recent_games = all_teams[all_teams['date'] > 20240801].groupby('team').size().reset_index(name='games_since_20240801')

    # Sort by number of games descending and get top 100
    recent_games_sorted = recent_games.sort_values('games_since_20240801', ascending=False)

    # Output to CSV
    recent_games_sorted.to_csv('Data/team_stats_health_check_2.csv', index=False)

# check_1()
# check_2()