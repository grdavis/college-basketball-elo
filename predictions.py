import elo
import random
import pandas as pd
import utils
import argparse
import scraper
import datetime

DATA_FOLDER = utils.DATA_FOLDER
ROUNDS = ['second', 'sixteen', 'eight', 'four', 'final', 'champion']

def matchups_from_list(team_list):
	'''
	convert a list of team names to a list of tuples that will match up consecutive teams together as opponents
	'''
	ret_list = []
	for i in range(len(team_list)):
		if i % 2 == 0:
			ret_list.append([team_list[i], team_list[i + 1]])
	return ret_list

def predict_game(elo_state, home, away, pick_mode = False, neutral = False, verbose = False):
	'''
	uses the specified elo_state to predict the outcome of a game between home and away
	pick_mode: 0 -> chooose winners probabilistically, 1 -> always choose the better team, 2 -> choose a random team
	neutral: specifies if the game is played at a neutral site
	returns a winner (either home or away), their win probability, and the home team's predicted spread
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

	return winner, "{0:.0%}".format(winp_home) if winner == home else "{0:.0%}".format(1 - winp_home), home_spread

def predict_tournament(elo_state, tournamant_teams, pick_mode = 0, verbose = False, rounds = ROUNDS):
	'''
	uses the specified elo_state to simulate a single tournament for teams in tournament teams
	pick_mode: 0 -> chooose winners probabilistically, 1 -> always choose the better team, 2 -> choose a random team
	outputs a Plotly table summarizing predictions and saves a csv
	'''
	results = {rounds[0]: tournamant_teams}
	remaining = tournamant_teams

	for r in rounds[1:]:
		matchups = matchups_from_list(remaining)
		winners = [predict_game(elo_state, i[0], i[1], pick_mode = pick_mode, neutral = True) for i in matchups]
		remaining = [i[0] for i in winners]
		results[r] = [(i[0], i[1]) for i in winners]

	if verbose:
		output = pd.DataFrame.from_dict(results, orient = 'index').transpose().fillna('').replace('(', '').replace(')', '')
		modes = {0: "Probabilistic Choice", 1: "Better Team", 2: "Random Team"}
		utils.table_output(output, 'Tournament Predictions Based on Ratings through ' + elo_state.date + ' - ' + modes[pick_mode])

	return results

def sim_tournaments(elo_state, tournamant_teams, n, verbose = False, rounds = ROUNDS):
	'''
	uses the specified elo_state to simulate a tournament (specified by tournament_teams) n times
	each row in the output specifies the share of simulations in which a team made it to the corresponding round
	outputs a Plotly table summarizing predictions and saves a csv
	'''
	sim_results = {}
	for team in tournamant_teams:
		sim_results[team] = [0 for _ in range(len(rounds) - 1)]

	for _ in range(n):
		results = predict_tournament(elo_state, tournamant_teams, rounds = rounds)
		for r in range(1, len(rounds)):
			for team in results[rounds[r]]:
				sim_results[team[0]][r-1] += 1

	if verbose:
		formatted = [[team] + [round(i/n, 4) for i in sim_results[team]] for team in tournamant_teams]
		output = pd.DataFrame(formatted, columns = ['team'] + rounds[1:]).sort_values(rounds[-1], ascending = False)
		utils.table_output(output, 'Tournament Predictions Based on Ratings through ' + elo_state.date + ' and ' + str(n) + ' Simulations')

def predict_next_day(elo_state, forecast_date):
	'''
	checks Sports Reference for games on the specified date object date and uses the elo state to predict each game's outcome 
	outputs a Plotly table summarizing predictions and saves a csv
	'''
	games = scraper.scrape_scores(forecast_date, scraper.new_driver())
	if games == []:
		print("No games scheduled on Sports Reference at this time for " + forecast_date.strftime('%Y%m%d'))
		return
	predictions = []
	for game in games:
		is_neutral = True if game[0] == 1 else False
		winner, prob, home_spread = predict_game(elo_state, game[1], game[3], neutral = is_neutral)
		if game[1] == winner:
			predictions.append([game[0], game[1], prob, home_spread, game[3], "{0:.0%}".format(1 - (float(prob[:-1])/100)), -home_spread])
		else:
			predictions.append([game[0], game[1], "{0:.0%}".format(1 - (float(prob[:-1])/100)), home_spread, game[3], prob, -home_spread])
	output = pd.DataFrame(predictions, columns = ['Neutral', 'Home', 'Home Win Prob.', 'Home Pred. Spread', 'Away', 'Away Win Prob.', 'Away Pred. Spread'])
	utils.table_output(output, forecast_date.strftime('%Y%m%d') + ' Game Predictions Based on Ratings through ' + elo_state.date)

def main(forecast_date = False, matchup = False, neutral = False, sim_mode = False, stop_short = '99999999', bracket = False, pick_mode = 0):
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
		tournamant_teams = list(pd.read_csv(file).iloc[:,0].dropna())
		rounds = list(pd.read_csv(file).columns)
		sim_tournaments(elo_state, tournamant_teams, n = int(simulations), verbose = True, rounds = rounds)
	elif bracket != False:
		tournamant_teams = list(pd.read_csv(bracket).iloc[:,0].dropna())
		rounds = list(pd.read_csv(bracket).columns)
		predict_tournament(elo_state, tournamant_teams, pick_mode = pick_mode, verbose = True, rounds = rounds)
	else:
		forecast_date = datetime.date.today() if forecast_date == False else datetime.datetime.strptime(forecast_date, "%Y%m%d")
		predict_next_day(elo_state, forecast_date)

def parseArguments():
	parser = argparse.ArgumentParser(description = 'This script allows the user to predict results of individual games, create a bracket prediction for a tournament, or simulate most likely outcomes for a bracket')
	parser.add_argument('-F', '--ForecastDate', default = False, type = str, help = 'Use if trying to predict games for a particular date in the future, set -f equal to the day you want to predict. If games are scheduled on Sports Reference, the output will be predictions for all games. Enter date as YYYYMMDD (e.g. 20190315)') 
	parser.add_argument('-G', '--GamePredictor', default = False, nargs = 2, type = str, help = 'Use to predict a single game. List home team as a string and away team as a string. Use -n flag to indicate a neutral site')
	parser.add_argument('-n', '--neutral', action = 'store_true', help = 'Use if predicting a single game at a neutral site')
	parser.add_argument('-S', '--SimMode', default = False, nargs = 2, help = 'Use this to run monte carlo simulations for a tournament and see in what share of simulations a team makes it to each round. Enter the filename storing the tournament participants as a string and an integer number of simulations to run')
	parser.add_argument('-d', '--dateSim', type = str, default = '99999999', help = 'Use if predicting games or tournament as of a date in the past. Enter date as YYYYMMDD (e.g. 20190315). Can be specified in any mode to get outputs as of the specified date')
	parser.add_argument('-P', '--PredictBracket', default = False, type = str, help = "Use to predict results of a tournament (i.e. generate a single bracket). Enter the filename storing the tournament participants in the first column. Use the -m flag to specify how each matchup should be decided. Don't forget to use -d if predicting this tournament as of a date in the past")
	parser.add_argument('-m', '--mode', default = 0, choices = [0, 1, 2], type = int, help = "By default, the winner for each matchup in a tournament prediction is selected probabilistically (mode 0). Use 1 to have the model always pick the 'better' team according to Elo ratings. Use 2 to decide each matchup with a coinflip (random selection)")
	return parser.parse_args()

if __name__ == '__main__':
	args = parseArguments()
	main(forecast_date = args.ForecastDate, matchup = args.GamePredictor, neutral = args.neutral, sim_mode = args.SimMode, stop_short = args.dateSim, bracket = args.PredictBracket, pick_mode = args.mode)