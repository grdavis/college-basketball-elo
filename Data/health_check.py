import pandas as pd
import sys
import os
# Change working directory to project root before imports
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import utils
import scraper

df = pd.read_csv(utils.get_latest_data_filepath(), 
                header=None, 
                names = ['neutral', 'away', 'ascore', 'home', 'hscore', 'date', 'aspread'])

# Get all team appearances in both home and away columns
away_teams = df[['away', 'date']].rename(columns={'away': 'team'})
home_teams = df[['home', 'date']].rename(columns={'home': 'team'})
all_teams = pd.concat([away_teams, home_teams])

def check_1():
    '''
    This function finds the first and last appearance dates of each team and the total number of appearances to 
    help validate that team names aren't changing mid-season
    '''
    team_stats = all_teams.groupby('team').agg({
        'date': ['min', 'max', 'count']
    }).reset_index()
    team_stats.columns = ['team', 'first_appearance', 'last_appearance', 'total_appearances']
    team_stats.to_csv('Data/team_stats_health_check_1.csv', index=False)

def check_2():
    '''
    This function checks the number of games each team has played since an inputed date to help validate 
    that team names aren't changing mid-season
    '''
    recent_games = all_teams[all_teams['date'] > 20240801].groupby('team').size().reset_index(name='games_since_20240801')
    recent_games_sorted = recent_games.sort_values('games_since_20240801', ascending=False)
    recent_games_sorted.to_csv('Data/team_stats_health_check_2.csv', index=False)

def check_3():
    '''
    This function checks for duplicate games by looking for repeat combinations of away, away_score, home, home_score
    '''
    potential_dupes = df.groupby(['away', 'ascore', 'home', 'hscore']).agg(
        count=('date', 'size'),
        min_date=('date', 'min'),
        max_date=('date', 'max')
    ).reset_index()
    potential_dupes = potential_dupes[potential_dupes['count'] > 1]
    
    # Extract year from min_date and max_date
    potential_dupes['min_year'] = potential_dupes['min_date'].astype(str).str[:4]
    potential_dupes['max_year'] = potential_dupes['max_date'].astype(str).str[:4]

    # Filter to rows where min_year equals max_year as that makes duplicate more likely
    potential_dupes = potential_dupes[potential_dupes['min_year'] == potential_dupes['max_year']]
    potential_dupes = potential_dupes.drop(['min_year', 'max_year'], axis=1)

    if len(potential_dupes) > 0:
        print(f"Found {len(potential_dupes)} potential duplicates:")
        print(potential_dupes)
    else:
        print("No duplicate games found")

def check_4():
    '''
    This function checks for teams that appear in TeamRankings schedules but don't have a mapping from Sports Reference names,
    which indicates the name we're mapping to in TR is incorrect
    '''
    # Find teams in TR_NAMES that don't appear in TR_NAMES_MAP values
    mapped_teams = set(scraper.TR_NAMES_MAP.values())
    tr_teams = set(scraper.TR_NAMES)
    unmapped_teams = tr_teams - mapped_teams
    
    if len(unmapped_teams) > 0:
        print(f"Found {len(unmapped_teams)} teams in TeamRankings that don't have Sports Reference mappings:")
        for team in sorted(unmapped_teams):
            print(f"  {team}")
    else:
        print("All TeamRankings teams have corresponding Sports Reference mappings")

# check_1()
# check_2()
# check_3() # last checked 2025-03-09; games before that date have been validated as non-duplicates
# check_4() # last checked 2025-03-22; 206 changes left to make, but they are small teams