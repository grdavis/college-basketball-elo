import elo
import random
import pandas as pd
import utils
import argparse
import scraper
import datetime
import spread_enricher

DATA_FOLDER = utils.DATA_FOLDER
ALL_ROUNDS = ['first', 'second', 'sixteen', 'eight', 'four', 'final', 'champion']

def matchups_from_list(team_list):
	'''
	convert a list of team names to a list of tuples that will match up consecutive teams together as opponents
	'''
	ret_list = []
	for i in range(len(team_list)):
		if i % 2 == 0:
			ret_list.append([team_list[i], team_list[i + 1]])
	return ret_list

def add_home_advantage(home_elo):
	'''
	In the tuning process, we found that the flat home advantage of about ~3.3 points (~80 elo points) works for the majority of games
	However, when the home team's ELO is outside of the (1600, 2000) range, a pattern of inaccuracy emerges.
	We attempt to correct for that pattern in this function. Essentially, below 1600, home teams should get more of a boost
	while above 2000, home teams should have their boost reduced. The outcome isn't perfect, but it results in a more smooth relationship
	between home ELO and our prediction accuracy (see tuning.home_pred_vs_actual_by_elo() for visual)
	'''
	if home_elo < 1600:
		return (elo.HOME_ADVANTAGE + ((-75/550)*home_elo) + 218)
	elif home_elo > 2000:
		return (elo.HOME_ADVANTAGE + ((-125/200)*home_elo) + 1250)
	else:
		return elo.HOME_ADVANTAGE

def predict_game(elo_state, home, away, pick_mode = False, neutral = False, verbose = False):
	'''
	uses the specified elo_state to predict the outcome of a game between home and away
	pick_mode: 0 -> chooose winners probabilistically, 1 -> always choose the better team, 2 -> choose a random team
	neutral: specifies if the game is played at a neutral site
	returns a winner (either home or away), their win probability, and the home team's predicted spread
	'''

	#to account for conference tournaments where there are byes, the bracket will be formatted to have a team play itself
	if home == away:
		return home, "BYE", "N/A"

	#to account for play-in games, we need to predict those outcomes first and they will have a / in the team name
	if '/' in home:
		pihome, piaway = home.split('/')[0], home.split('/')[1]
		home = predict_game(elo_state, pihome, piaway, pick_mode = pick_mode, neutral = neutral)[0]
	elif '/' in away:
		pihome, piaway = away.split('/')[0], away.split('/')[1]
		away = predict_game(elo_state, pihome, piaway, pick_mode = pick_mode, neutral = neutral)[0]
	
	home_elo = elo_state.get_elo(home)
	home_boost = add_home_advantage(home_elo) if not neutral else 0
	home_elo += home_boost
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

def predict_tournament(elo_state, tournamant_teams, pick_mode = 0, verbose = False, rounds = ALL_ROUNDS):
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

def sim_tournaments(elo_state, tournamant_teams, n, verbose = False, rounds = ALL_ROUNDS):
	'''
	uses the specified elo_state to simulate a tournament (specified by tournament_teams) n times
	each row in the output specifies the share of simulations in which a team made it to the corresponding round
	outputs a Plotly table summarizing predictions and saves a csv
	'''
	sim_results = {}
	for team in tournamant_teams:
		if '/' in team:
			team1, team2 = team.split('/')[0], team.split('/')[1]
			sim_results[team1] = [0 for _ in range(len(rounds) - 1)]
			sim_results[team2] = [0 for _ in range(len(rounds) - 1)]
		else:
			sim_results[team] = [0 for _ in range(len(rounds) - 1)]

	for _ in range(n):
		results = predict_tournament(elo_state, tournamant_teams, rounds = rounds)
		for r in range(1, len(rounds)):
			for team in results[rounds[r]]:
				sim_results[team[0]][r-1] += 1

	if verbose:
		current_rankings = elo_state.get_rankings_dict()
		formatted = [[f'{team} (#{current_rankings[team]})'] + [round(i/n, 4) for i in sim_results[team]] for team in sim_results]
		output = pd.DataFrame(formatted, columns = ['team'] + rounds[1:]).sort_values(rounds[-1], ascending = False).drop_duplicates()
		utils.table_output(output, 'Tournament Predictions Based on Ratings through ' + elo_state.date + ' and ' + str(n) + ' Simulations')

def predict_next_day(elo_state, forecast_date, auto):
	'''
	checks scrape source for games on forecast_date and uses the elo state to predict each game's outcome 
	outputs a Plotly table summarizing predictions and saves a csv
	'''
	scraper.scrape_neutral_data() #set the NEUTRAL_MAP for predictions
	games = scraper.scrape_scores(forecast_date)
	if games == []:
		print("No games scheduled on Sports Reference at this time for " + forecast_date.strftime('%Y%m%d'))
		return
	predictions = []
	for game in games:
		is_neutral = True if game[0] == 1 else False
		winner, prob, home_spread = predict_game(elo_state, game[3], game[1], pick_mode = 1, neutral = is_neutral)
		if game[1] == winner:
			predictions.append([game[0], game[1], prob, -home_spread, game[3], "{0:.0%}".format(1 - (float(prob[:-1])/100)), home_spread])
		else:
			predictions.append([game[0], game[1], "{0:.0%}".format(1 - (float(prob[:-1])/100)), -home_spread, game[3], prob, home_spread])
	predictions, timestamp = spread_enricher.add_spreads_to_todays_preds(predictions, forecast_date)
	output = pd.DataFrame(predictions, columns = ['Neutral', 'Away', 'Away Win Prob.', 'Away Pred. Spread', 'Live Away Spread', 'Home', 'Home Win Prob.', 'Home Pred. Spread'])
	
	#add a * to the team names that are brand new to the simulation. Take those predictions with a grain of salt
	output['Away'] = output.apply(lambda x: x['Away'] + "*" if elo_state.get_elo(x['Away']) == elo.NEW_ELO else x['Away'], axis = 1)
	output['Home'] = output.apply(lambda x: x['Home'] + "*" if elo_state.get_elo(x['Home']) == elo.NEW_ELO else x['Home'], axis = 1)
	
	spreads_string = ''
	if timestamp != 'N/A':
		spreads_string = ' with Spreads as of '
		spreads_string +=  (timestamp - datetime.timedelta(hours = 5)).strftime('%Y%m%d at %H%M') if auto else timestamp.strftime('%Y%m%d at %H%M')
	utils.table_output(output, forecast_date.strftime('%Y%m%d') + ' Game Predictions Based on Ratings through ' + elo_state.date + spreads_string)
	
	#save the predictions output in markdown where github pages can find it
	new_top_50 = pd.DataFrame(elo_state.get_top(50), columns = ['Team', 'Elo Rating', '7 Day Change']) 
	utils.save_markdown_df(output, new_top_50, forecast_date.strftime('%Y-%m-%d'))

def main(auto = False, forecast_date = False, matchup = False, neutral = False, sim_mode = False, stop_short = '99999999', bracket = False, pick_mode = 0, bracket_round_start = 0):
	'''
	Retrieves an elo simulation through the specified 'stop_short' date then cascades through options:
	1. if a 'matchup' of two teams is provided, print out predictions for that matchup - factoring in 
	whether the matchup is at a 'neutral' site or not
	2. if 'sim_mode' is specified [a filepath to a bracket, a number of simulations], then run the specified 
	number of bracket simulations on the specified bracket
	3. if just 'bracket', which is a filepath to a bracket, is specified, deliver a one-time prediction for that 
	bracket based on the starting teams. 'pick_mode' chooses probabilistically (0), the better team (1), or randomly (2)
	4. if nothing is specified, make predictions for today's games
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
		tournamant_teams = list(pd.read_csv(file).iloc[:,bracket_round_start].dropna())
		rounds = list(pd.read_csv(file).columns)
		sim_tournaments(elo_state, tournamant_teams, n = int(simulations), verbose = True, rounds = rounds[bracket_round_start:])
	elif bracket != False:
		tournamant_teams = list(pd.read_csv(bracket).iloc[:,bracket_round_start].dropna())
		rounds = list(pd.read_csv(bracket).columns)
		predict_tournament(elo_state, tournamant_teams, pick_mode = pick_mode, verbose = True, rounds = rounds[bracket_round_start:])
	else:
		forecast_date = datetime.date.today() if forecast_date == False else datetime.datetime.strptime(forecast_date, "%Y%m%d")
		forecast_date = forecast_date - datetime.timedelta(hours = 5) if auto else forecast_date
		predict_next_day(elo_state, forecast_date, auto)
	utils.clean_up_old_outputs_and_data()

def parseArguments():
	parser = argparse.ArgumentParser(description = 'This script allows the user to predict results of individual games, create a bracket prediction for a tournament, or simulate most likely outcomes for a bracket')
	parser.add_argument('-F', '--ForecastDate', default = False, type = str, help = 'Use if trying to predict games for a particular date in the future, set -f equal to the day you want to predict. If games are scheduled on Sports Reference, the output will be predictions for all games. Enter date as YYYYMMDD (e.g. 20190315)') 
	parser.add_argument('-G', '--GamePredictor', default = False, nargs = 2, type = str, help = 'Use to predict a single game. List home team as a string and away team as a string. Use -n flag to indicate a neutral site')
	parser.add_argument('-n', '--neutral', action = 'store_true', help = 'Use if predicting a single game at a neutral site')
	parser.add_argument('-S', '--SimMode', default = False, nargs = 2, help = 'Use this to run monte carlo simulations for a tournament and see in what share of simulations a team makes it to each round. Enter the filename storing the tournament participants as a string and an integer number of simulations to run')
	parser.add_argument('-d', '--dateSim', type = str, default = '99999999', help = 'Use if predicting games or tournament as of a date in the past. Enter date as YYYYMMDD (e.g. 20190315). Can be specified in any mode to get outputs as of the specified date')
	parser.add_argument('-P', '--PredictBracket', default = False, type = str, help = "Use to predict results of a tournament (i.e. generate a single bracket). Enter the filename storing the tournament participants in the first column. Use the -m flag to specify how each matchup should be decided. Don't forget to use -d if predicting this tournament as of a date in the past")
	parser.add_argument('-m', '--mode', default = 0, choices = [0, 1, 2], type = int, help = "By default, the winner for each matchup in a tournament prediction is selected probabilistically (mode 0). Use 1 to have the model always pick the 'better' team according to Elo ratings. Use 2 to decide each matchup with a coinflip (random selection)")
	parser.add_argument('-r', '--round', default = 0, type = int, help = "When using -P PredictBracket or -S SimMode, optionally specify which round of the tournament file to start making predictions from (e.g. 0 = predict advancements from the 0th column onwards in the tournament file)")
	parser.add_argument('-A', '--auto', action = 'store_true', help = 'Used only by github actions to account for the time difference on the virtual machine')
	return parser.parse_args()

if __name__ == '__main__':
	args = parseArguments()
	main(auto = args.auto, forecast_date = args.ForecastDate, matchup = args.GamePredictor, neutral = args.neutral, sim_mode = args.SimMode, 
		stop_short = args.dateSim, bracket = args.PredictBracket, pick_mode = args.mode, bracket_round_start = args.round)