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

def predict_game(elo_state, home, away, pick_mode = False, neutral = False, verbose = False):
	'''
	pick_mode = 0 -> chooose winners probabilistically, 1 -> always choose the better team, 2 -> choose a random team
	'''
	home_boost = elo.HOME_ADVANTAGE if not neutral else 0
	home_elo = elo_state.get_elo(home) + home_boost
	away_elo = elo_state.get_elo(away)
	winp_home = elo.winp(home_elo - away_elo)
	home_spread = round((home_elo - away_elo)/elo.ELO_TO_POINTS_FACTOR, 1)

	if verbose: print(home, "{0:.0%}".format(winp_home), str(home_spread), away, "{0:.0%}".format(1 - winp_home), str(-home_spread))

	if pick_mode == 1:
		winner = home if home_elo > away_elo else away
	elif pick_mode == 2:
		winner = random.choice([home, away])
	else:
		winner = random.choices([home, away], weights = (winp_home, 1-winp_home))[0]

	return winner, "{0:.0%}".format(winp_home) if winner == home else "{0:.0%}".format(1 - winp_home)

def predict_tournament(elo_state, tournamant_teams, pick_mode = 0, verbose = False):
	results = {'first': tournamant_teams}
	remaining = tournamant_teams

	for r in ROUNDS:
		matchups = matchups_from_list(remaining)
		winners = [predict_game(elo_state, i[0], i[1], pick_mode = pick_mode, neutral = True) for i in matchups]
		remaining = [i[0] for i in winners]
		results[r] = winners

	if verbose:
		output = pd.DataFrame.from_dict(results, orient = 'index').transpose().fillna('').replace('(', '').replace(')', '')
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

def main(matchup = False, neutral = False, sim_mode = False, stop_short = '99999999', bracket = False, pick_mode = 0):
	'''
	Retrieves an elo simulation through the specified 'stop_short' date then cascades through options:
	1. if a 'matchup' of two teams is provided, print out predictions for that matchup - factoring in 
	whether the matchup is at a 'neutral' site or not
	2. if 'sim_mode' is specified [a filepath to a bracket, a number of simulations], then run the specified 
	number of bracket simulations on the specified bracket
	3. if just 'bracket', which is a filepath to a bracket, is specified, deliver a one-time prediction for that 
	bracket based on the starting teams. 'pick_mode' chooses probabilistically (0), the better team (1), or randomly (2)
	4. if nothing is specified, print out an explanation
	'''
	elo_state = elo.main(stop_short = stop_short)
	if matchup != False:
		home, away = matchup
		print('Ratings through ' + elo_state.date)
		if neutral:
			print(home, "vs.", away, "@ neutral site")
		else:
			print(away, "@", home)
		predict_game(elo_state, home, away, neutral = neutral, verbose = True)
	elif sim_mode != False:
		file, simulations = sim_mode
		tournamant_teams = list(pd.read_csv(file)['first'].dropna())
		sim_tournaments(elo_state, tournamant_teams, n = int(simulations), verbose = True)
	elif bracket != False:
		tournamant_teams = list(pd.read_csv(bracket)['first'].dropna())
		predict_tournament(elo_state, tournamant_teams, pick_mode = pick_mode, verbose = True)
	else:
		print('You must enter some optional arguments for something to happen. Use -h to see options.')

def parseArguments():
	parser = argparse.ArgumentParser(description = 'This script allows the user to predict results of individual games, create a bracket prediction for a tournament, or simulate most likely outcomes for a bracket')
	parser.add_argument('-G', '--GamePredictor', default = False, nargs = 2, type = str, help = 'Use to predict a single game. List home team as a string and away team as a string. Use -n flag to indicate a neutral site')
	parser.add_argument('-n', '--neutral', action = 'store_true', help = 'Use if predicting a single game at a neutral site')
	parser.add_argument('-S', '--SimMode', default = False, nargs = 2, help = 'Use to run monte carlo simulations to predict most likely tournament outcomes. Enter the filename storing the tournament participants and the number of simulations to run')
	parser.add_argument('-d', '--dateSim', type = str, default = '99999999', help = 'Use if predicting a game or tournament as of a date in the past. Enter date as YYYYMMDD (e.g. 20190315)')
	parser.add_argument('-P', '--PredictBracket', default = False, type = str, help = "Use to predict results of a tournament (i.e. generate a single bracket). Enter the filename storing the tournament participants. Use the -b flag to pick the better team in each matchup. Don't forget to use -d if predicting this tournament as of a date in the past")
	parser.add_argument('-m', '--mode', default = 0, choices = [1, 2], type = int, help = "By default, the winner for each matchup in a tournament is selected probabilistically. Use 1 to have the model always pick the 'better' team. Use 2 to decide each matchup with a coinflip (randomly)")
	return parser.parse_args()

if __name__ == '__main__':
	args = parseArguments()
	main(matchup = args.GamePredictor, neutral = args.neutral, sim_mode = args.SimMode, stop_short = args.dateSim, bracket = args.PredictBracket, pick_mode = args.mode)