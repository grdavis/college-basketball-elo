import elo
import scraper
import random
import pandas as pd

ROUNDS = ['second', 'sixteen', 'eight', 'four', 'final', 'champion']

def matchups_from_list(team_list):
	ret_list = []
	for i in range(len(team_list)):
		if i % 2 == 0:
			ret_list.append([team_list[i], team_list[i + 1]])
	return ret_list

def predict_game(elo_state, home, away, pick_favorite = False, neutral = False, verbose = False):
	home_boost = elo.HOME_ADVANTAGE if not neutral else 0
	home_elo = elo_state.get_elo(home) + home_boost
	away_elo = elo_state.get_elo(away)
	winp_home = elo.winp(home_elo - away_elo)

	if verbose: print(home, "{0:.0%}".format(winp_home), away, "{0:.0%}".format(1 - winp_home))

	if pick_favorite:
		return home if home_elo > away_elo else away
	else:
		return random.choices([home, away], weights = (winp_home, 1-winp_home))[0]

def predict_tournament(elo_state, tournamant_teams, pick_favorites = False):
	
	results = {'first': tournamant_teams}
	remaining = tournamant_teams

	for r in ROUNDS:
		matchups = matchups_from_list(remaining)
		winners = [predict_game(elo_state, i[0], i[1], pick_favorite = pick_favorites, neutral = True) for i in matchups]
		remaining = winners
		results[r] = winners

	return results

def sim_tournaments(elo_state, tournamant_teams, n, savename = False):
	sim_results = {}
	for team in tournamant_teams:
		sim_results[team] = [0, 0, 0, 0, 0, 0]

	for i in range(n):
		results = predict_tournament(elo_state, tournamant_teams)
		for r in range(len(ROUNDS)):
			for team in results[ROUNDS[r]]:
				sim_results[team][r] += 1

	if savename:
		save_formatted = []
		for team in tournamant_teams:
			save_formatted.append([team] + [round(i/n, 4) for i in sim_results[team]])
		scraper.save_data(savename, save_formatted)

def evaluate_brackets(predictions, real_results):
	scores = [10, 20, 40, 80, 160, 320] #ESPN scoring system for correct game in round
	predictions_score = 0
	for index in range(len(ROUNDS)):
		predictions_score += sum([scores[index] if predictions[ROUNDS[index]][i] == real_results[ROUNDS[index]][i] else 0 for i in range(len(predictions[ROUNDS[index]]))])
	return predictions_score

def main(data_filepath, tourney_filepath, stop_date, sims = 10000, save_sims = False, evaluate = False):
	elo_state = elo.main(data_filepath, stop_short = stop_date, top_25 = True)
	df = pd.read_csv(tourney_filepath)
	tournamant_teams = list(df['first'].dropna())
	if evaluate:
		results = {'first': tournamant_teams}
		for r in ROUNDS:
			results[r] = df[r].dropna().values
		best_bracket = predict_tournament(elo_state, tournamant_teams, pick_favorites = True)
		return evaluate_brackets(best_bracket, results)

	sim_tournaments(elo_state, tournamant_teams, sims, save =save_sims)

# scraper.main(file_start = '20101101', scrape_start = '20210303', scrape_end = '20210307', data_filepath = '20101101-20210303.csv')
elo_state = elo.main('20101101-20210308.csv')
predict_game(elo_state, 'Gonzaga', "Saint Mary's", neutral = True, verbose = True)
# print(elo_state.get_top(75))
# print(main('20101101-20210303.csv', 'tournament_results_2019.csv', '20190320', evaluate = True))
# 1260
# print(main('20101101-20210303.csv', 'tournament_results_2018.csv', '20180314', evaluate = True))
# 1230
# print(main('20101101-20210303.csv', 'tournament_results_2017.csv', '20180315', evaluate = True))
# 660



