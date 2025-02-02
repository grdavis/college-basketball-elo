import pandas as pd

df = pd.read_csv("Data/20101101-20250131.csv", header=None, names = ['neutral', 'away', 'ascore', 'home', 'hscore', 'date', 'aspread'])

# Get all team appearances in both home and away columns
away_teams = df[['away', 'date']].rename(columns={'away': 'team'})
home_teams = df[['home', 'date']].rename(columns={'home': 'team'})
all_teams = pd.concat([away_teams, home_teams])

# Group by team and calculate first date, last date, and count
team_stats = all_teams.groupby('team').agg({
    'date': ['min', 'max', 'count']
}).reset_index()

# Rename columns
team_stats.columns = ['team', 'first_appearance', 'last_appearance', 'total_appearances']

# Sort by total appearances descending
team_stats = team_stats.sort_values('total_appearances', ascending=False)

# Output team stats to CSV
team_stats.to_csv('Data/team_stats_health_check.csv', index=False)



