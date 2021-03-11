import elo
import random
import pandas as pd
import utils
import argparse

DATA_FOLDER = utils.DATA_FOLDER
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
	home_spread = round((home_elo - away_elo)/elo.ELO_TO_POINTS_FACTOR, 1)

	if verbose: print(home, "{0:.0%}".format(winp_home), str(home_spread), away, "{0:.0%}".format(1 - winp_home), str(-home_spread))

	if pick_favorite:
		return home if home_elo > away_elo else away
	else:
		return random.choices([home, away], weights = (winp_home, 1-winp_home))[0]

def predict_tournament(elo_state, tournamant_teams, pick_favorites = False, verbose = False):
	results = {'first': tournamant_teams}
	remaining = tournamant_teams

	for r in ROUNDS:
		matchups = matchups_from_list(remaining)
		winners = [predict_game(elo_state, i[0], i[1], pick_favorite = pick_favorites, neutral = True) for i in matchups]
		remaining = winners
		results[r] = winners

	if verbose:
		output = pd.DataFrame.from_dict(results, orient = 'index').transpose().fillna('')
		utils.table_output(output, 'Tournament Predictions Based on Ratings through ' + elo_state.date)

	return results

def sim_tournaments(elo_state, tournamant_teams, n, verbose = False):
	sim_results = {}
	for team in tournamant_teams:
		sim_results[team] = [0, 0, 0, 0, 0, 0]

	for i in range(n):
		results = predict_tournament(elo_state, tournamant_teams)
		for r in range(len(ROUNDS)):
			for team in results[ROUNDS[r]]:
				sim_results[team][r] += 1

	if verbose:
		formatted = [[team] + [round(i/n, 4) for i in sim_results[team]] for team in tournamant_teams]
		output = pd.DataFrame(formatted, columns = ['team'] + ROUNDS).sort_values(ROUNDS[-1], ascending = False)
		utils.table_output(output, 'Tournament Predictions Based on Ratings through ' + elo_state.date + ' and ' + str(n) + ' Simulations')

def main(args):
	# args is a dictionary mapping 'd', 'n', 'G', 'P', 'b', and 'S' to their various inputs (all default to None, except 'n' and 'b')
	# use the latest data in the DATA_FOLDER that's in the right format: YYYYMMDD-YYYYMMDD.csv
	elo_state = elo.main({'t': False, 'd': args['d'], 'u': None})
	
	if args['G'] != None:
		home, away = args['G']
		print('Ratings through ' + elo_state.date)
		if args['n']:
			print(home, "vs.", away, "@ neutral site")
		else:
			print(away, "@", home)
		predict_game(elo_state, args['G'][0], args['G'][1], neutral = args['n'], verbose = True)
	elif args['S'] != None:
		df = pd.read_csv(args['S'][0])
		tournamant_teams = list(df['first'].dropna())
		sim_tournaments(elo_state, tournamant_teams, n = int(args['S'][1]), verbose = True)
	elif args['P'] != None:
		df = pd.read_csv(args['P'])
		tournamant_teams = list(df['first'].dropna())
		predict_tournament(elo_state, tournamant_teams, pick_favorites = args['b'], verbose = True)
	else:
		print('You must enter some optional arguments for something to happen. Use -h to see options.')

def parseArguments():
	parser = argparse.ArgumentParser()
	parser.add_argument('-G', nargs = 2, type = str, help = 'Use to predict a single game. List home team as a string and away team as a string. Use -n flag to indicate a neutral site')
	parser.add_argument('-n', action = 'store_true', help = 'Use if predicting a single game at a neutral site')
	parser.add_argument('-S', nargs = 2, help = 'Use to run monte carlo simulations to predict most likely tournament outcomes. Enter the filename storing the tournament participants and the number of simulations to run')
	parser.add_argument('-d', type = str, default = '99999999', help = 'Use if predicting a game or tournament as of a date in the past. Enter date as YYYYMMDD (e.g. 20190315)')
	parser.add_argument('-P', type = str, help = "Use to predict results of a tournament (i.e. generate a single bracket). Enter the filename storing the tournament participants. Use the -b flag to pick the better team in each matchup. Don't forget to use -d if predicting this tournament as of a date in the past")
	parser.add_argument('-b', action = 'store_true', help = "By default, the winner for each matchup in a tournament is selected probabilistically. Use this flag to always choose the 'better' team instead")
	return parser.parse_args()

if __name__ == '__main__':
	main(parseArguments().__dict__)

#################################################
'''
def evaluate_brackets(predictions, real_results):
	scores = [10, 20, 40, 80, 160, 320] #ESPN scoring system for correct game in round
	predictions_score = 0
	for index in range(len(ROUNDS)):
		predictions_score += sum([scores[index] if predictions[ROUNDS[index]][i] == real_results[ROUNDS[index]][i] else 0 for i in range(len(predictions[ROUNDS[index]]))])
	return predictions_score

for stop_date, tourney_filepath in [('20190321', 'tournament_results_2019.csv'), ('20180315', 'tournament_results_2018.csv'), ('20170316', 'tournament_results_2017.csv')]:
	elo_state = elo.main({'t': False, 'd': stop_date, 'u': None})
	df = pd.read_csv(DATA_FOLDER + tourney_filepath)
	tournamant_teams = list(df['first'].dropna())
	results = {'first': tournamant_teams}
	for r in ROUNDS:
		results[r] = df[r].dropna().values
	best_bracket = predict_tournament(elo_state, tournamant_teams, pick_favorites = True)
	print(evaluate_brackets(best_bracket, results))

#2019: 1260
#2018: 830
#2017: 720
'''
