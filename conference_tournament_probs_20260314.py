import csv
from pathlib import Path

# Constants from elo.py
ELO_BASE = 1500
NEW_ELO = 985
K_FACTOR = 47
SEASON_CARRY = 0.64
HOME_ADVANTAGE = 82
GAMES_REQUIRED = 10

DATA_FILE = Path('Data/20101101-20260313.csv')
TODAY_PREDICTIONS_FILE = Path('Outputs/20260314 Game Predictions Based on Ratings through 20260313 with Spreads as of 20260314 at 0917.csv')
OUT_FILE = Path('Outputs/2026 Conference Tournament Championship Probabilities 20260314.csv')

CONFERENCE_SEMIS = {
    'Big Ten': [('Wisconsin', 'Michigan'), ('Purdue', 'UCLA')],
    'SEC': [('Vanderbilt', 'Florida'), ('Ole Miss', 'Arkansas')],
    'American': [('Charlotte', 'South Florida'), ('Tulsa', 'Wichita State')],
    'A10': [('Dayton', 'Saint Louis'), ("St. Joseph's", 'VCU')],
    'Ivy': [('Cornell', 'Yale'), ('Penn', 'Harvard')],
}

# team -> conference lookup used for season carry reset by conference average
CONFERENCE_LOOKUP = {}
with open('Data/conferences.csv', newline='') as f:
    reader = csv.reader(f)
    for row in reader:
        if len(row) >= 2:
            CONFERENCE_LOOKUP[row[0]] = row[1]


def winp(elo_spread: float) -> float:
    if elo_spread > ELO_BASE:
        return 1.0
    if elo_spread < -ELO_BASE:
        return 0.0
    return 1 / (1 + 10 ** (-elo_spread / 400))


def calc_mov_multiplier(elo_margin: float, mov: int) -> float:
    a = (mov + 2.5) ** 0.7
    b = 6 + max(0.006 * elo_margin, -5.99)
    return a / b


def season_reset(teams: dict[str, dict]) -> dict[str, dict]:
    score_by_conf = {}
    count_by_conf = {}

    kept = {}
    for team, d in teams.items():
        if d['season_games'] < GAMES_REQUIRED:
            continue
        kept[team] = d
        conf = d['conference']
        score_by_conf[conf] = score_by_conf.get(conf, 0.0) + d['elo']
        count_by_conf[conf] = count_by_conf.get(conf, 0) + 1

    for team, d in kept.items():
        conf_avg = score_by_conf[d['conference']] / count_by_conf[d['conference']]
        d['elo'] = d['elo'] * SEASON_CARRY + (1 - SEASON_CARRY) * conf_avg
        d['season_games'] = 0

    return kept


def get_team(teams: dict[str, dict], name: str) -> dict:
    if name not in teams:
        teams[name] = {
            'elo': ELO_BASE,
            'season_games': 0,
            'conference': CONFERENCE_LOOKUP.get(name, 'Other'),
        }
    return teams[name]


def build_elo_state(data_file: Path) -> dict[str, dict]:
    teams = {}
    season_count = 0
    current_month = None

    with open(data_file, newline='') as f:
        reader = csv.reader(f)
        for row in reader:
            neutral, away, away_score, home, home_score, date = row[:6]
            row_month = int(date[4:6])

            if current_month is None:
                current_month = row_month

            if current_month in [3, 4] and row_month == 11:
                season_count += 1
                teams = season_reset(teams)

            current_month = row_month

            home_t = get_team(teams, home)
            away_t = get_team(teams, away)

            if season_count > 0:
                if home_t['elo'] == ELO_BASE and home_t['season_games'] == 0:
                    home_t['elo'] = NEW_ELO
                if away_t['elo'] == ELO_BASE and away_t['season_games'] == 0:
                    away_t['elo'] = NEW_ELO

            hs, as_ = int(home_score), int(away_score)
            if hs > as_:
                winner, loser = home, away
                ws, ls = hs, as_
            else:
                winner, loser = away, home
                ws, ls = as_, hs

            w_elo = teams[winner]['elo']
            l_elo = teams[loser]['elo']

            if neutral == '0':
                if winner == home:
                    w_elo += HOME_ADVANTAGE
                else:
                    l_elo += HOME_ADVANTAGE

            elo_margin = w_elo - l_elo
            w_winp = winp(elo_margin)
            mov = ws - ls
            delta = round(K_FACTOR * calc_mov_multiplier(elo_margin, mov) * (1 - w_winp), 2)

            teams[winner]['elo'] = max(0, teams[winner]['elo'] + delta)
            teams[loser]['elo'] = max(0, teams[loser]['elo'] - delta)
            teams[winner]['season_games'] += 1
            teams[loser]['season_games'] += 1

    return teams


def p_team_beats(teams: dict[str, dict], a: str, b: str) -> float:
    return winp(teams[a]['elo'] - teams[b]['elo'])


def conference_probs(teams_state: dict[str, dict], semis: list[tuple[str, str]]):
    (a, b), (c, d) = semis

    p_ab = p_team_beats(teams_state, a, b)
    p_cd = p_team_beats(teams_state, c, d)

    p = {}
    p[a] = p_ab * (p_cd * p_team_beats(teams_state, a, c) + (1 - p_cd) * p_team_beats(teams_state, a, d))
    p[b] = (1 - p_ab) * (p_cd * p_team_beats(teams_state, b, c) + (1 - p_cd) * p_team_beats(teams_state, b, d))
    p[c] = p_cd * (p_ab * p_team_beats(teams_state, c, a) + (1 - p_ab) * p_team_beats(teams_state, c, b))
    p[d] = (1 - p_cd) * (p_ab * p_team_beats(teams_state, d, a) + (1 - p_ab) * p_team_beats(teams_state, d, b))
    return p


def get_today_matchups() -> set[tuple[str, str]]:
    pair_set = set()
    with open(TODAY_PREDICTIONS_FILE, newline='') as f:
        r = csv.DictReader(f)
        for row in r:
            pair_set.add((row['Away'], row['Home']))
    return pair_set


def main():
    today_matchups = get_today_matchups()

    # sanity-check our semifinal list against today's games file
    for conf, semis in CONFERENCE_SEMIS.items():
        for away, home in semis:
            if (away, home) not in today_matchups and (home, away) not in today_matchups:
                raise ValueError(f'{conf} semifinal not found in today output: {away} vs {home}')

    elo_state = build_elo_state(DATA_FILE)

    rows = []
    for conf, semis in CONFERENCE_SEMIS.items():
        teams = [semis[0][0], semis[0][1], semis[1][0], semis[1][1]]
        probs = conference_probs(elo_state, semis)

        for t in teams:
            rows.append([
                conf,
                semis[0][0] + ' vs ' + semis[0][1],
                semis[1][0] + ' vs ' + semis[1][1],
                t,
                round(elo_state[t]['elo'], 2),
                round(probs[t], 6),
                f"{probs[t]:.2%}",
            ])

    with open(OUT_FILE, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow([
            'Conference',
            'Semifinal 1',
            'Semifinal 2',
            'Team',
            'Current Elo (through 20260313)',
            'Tournament Win Probability',
            'Tournament Win Probability (Pct)'
        ])
        w.writerows(rows)

    print(f'Wrote {OUT_FILE}')

    # print concise summary to terminal
    by_conf = {}
    for row in rows:
        by_conf.setdefault(row[0], []).append(row)

    for conf, conf_rows in by_conf.items():
        print(f'\n{conf}')
        for row in sorted(conf_rows, key=lambda x: x[5], reverse=True):
            print(f"  {row[3]:<15} {row[6]:>8}")


if __name__ == '__main__':
    main()
