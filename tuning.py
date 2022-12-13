import numpy as np
from tqdm import tqdm
import elo
import utils
import random
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sklearn.metrics import r2_score
from scipy.stats import linregress
import pandas as pd
from predictions import predict_tournament, ROUNDS, predict_game

ERRORS_START = 4 #after 4 seasons (starts counting errors 20141114)

class Tuning_ELO_Sim(elo.ELO_Sim):
	'''
	This class is an extension of ELO_Sim that allows us to keep track of errors and extra metrics through the
	simulation process which are useful for tuning. Errors tracked are...
	error1: calculated (1 - predicted win probability)^2 for each game and add them up. More commonly known as Brier score (https://en.wikipedia.org/wiki/Brier_score). This is the primary error of interest
	error2: calculated at the end of a simulation as the average absolute difference between predicted win probability and actual win probability for teams who were given that prediction
	'''
	def __init__(self):
		super().__init__()
		self.predict_tracker = {}
		self.spread_tracker = []
		self.win_tracker = {0.0: 0}
		self.elo_margin_tracker = {}
		self.MoV_tracker = {}
		self.error1 = []

	def update_errors(self, w_winp, for_spread_tracker):
		if self.season_count >= ERRORS_START:
			rounded, roundedL = round(w_winp, 2), round(1 - w_winp, 2)
			self.error1.append((1 - w_winp)**2)
			self.win_tracker[rounded] = self.win_tracker.get(rounded, 0) + 1
			self.predict_tracker[rounded] = self.predict_tracker.get(rounded, 0) + 1
			self.predict_tracker[roundedL] = self.predict_tracker.get(roundedL, 0) + 1
			self.spread_tracker.append((for_spread_tracker['away_score'], for_spread_tracker['home_score'],
				for_spread_tracker['veg_away_spread'], for_spread_tracker['away_elo_spread'], self.date))

	def update_MoVs(self, elo_margin, MoV):
		if self.season_count >= ERRORS_START:
			rounded = round(elo_margin/25) * 25 #round to nearest 25
			self.elo_margin_tracker[rounded] = self.elo_margin_tracker.get(rounded, 0) + 1
			self.MoV_tracker[rounded] = self.MoV_tracker.get(rounded, 0) + MoV
			self.elo_margin_tracker[-rounded] = self.elo_margin_tracker.get(-rounded, 0) + 1
			self.MoV_tracker[-rounded] = self.MoV_tracker.get(-rounded, 0) - MoV

	def get_errors(self):
		error2 = 0
		total_games = sum(self.predict_tracker.values())
		for i in sorted(self.predict_tracker):
			result = self.win_tracker.get(i, 0)/self.predict_tracker[i]
			error2 += self.predict_tracker[i] * abs(result - i)
		return (sum(self.error1), error2 / total_games)

def tuning_sim(data, k_factor, new_season_carry, home_elo, new_team_elo):
	'''
	This function runs through all of the data and updates elo and errors along the way
	It is a simplified version of the official sim function used in elo.py
	'''
	this_sim = Tuning_ELO_Sim()
	this_month = data[0][5][4:6]
	elo.NEW_ELO = new_team_elo

	for row in data:
		row_month = int(row[5][4:6])
		if this_month in [3, 4] and row_month == 11:
			this_sim.season_count += 1
			this_sim.season_reset(new_season_carry)
		this_sim.date = row[5]
		this_month = row_month

		#make predictions for row
		is_neutral = True if row[0] == 1 else False
		winner, prob, home_spread = predict_game(this_sim, row[3], row[1], pick_mode = 1, neutral = is_neutral)
		for_spread_tracker = {'away_score': row[2], 'home_score': row[4], 'veg_away_spread': row[6], 'away_elo_spread': -home_spread}

		#elo and error updates
		elo_margin, MoV = elo.step_elo(this_sim, row, k_factor, home_elo)
		this_sim.update_errors(elo.winp(elo_margin), for_spread_tracker)
		this_sim.update_MoVs(elo_margin, MoV)
	
	return this_sim

def random_tune(data, number):
	'''
	Use this function to repeatedly narrow down tighter and tighter ranges of possible optimal values for k, carry, and home elo advantage
	Start with wide ranges, then use the outputs (which are sorted by their errors) to inform a tighter range for the next iteration
	Once windows are small enough, switch to brute_tune
	'''
	k_range = [47, 48, 49]
	carry_range = [.92, .93, .94]
	home_range = [74, 75, 76, 78]
	new_team_range = [850, 875, 900]
	errors = []
	
	for i in tqdm(range(number)):
		k_factor, new_season_carry, home_elo, nte = random.choice(k_range), random.choice(carry_range), random.choice(home_range), random.choice(new_team_range)
		error1, error2 = tuning_sim(data, k_factor, new_season_carry, home_elo, nte).get_errors()
		errors.append((error1, error2, k_factor, new_season_carry, home_elo, nte))

	return errors

def brute_tune(data):
	'''
	Use this function to cycle through all possible combinations of the 4 variables within the defined ranges and find the optimal solution
	Since brute force can take some time to run, random_tune first to help narrow possible ranges
	'''
	k_range = [46]
	carry_range = [.9, .91]
	home_range = [75, 78, 79, 80, 82]
	new_team_range = [915, 925, 940, 950] 
	errors = []

	for k in tqdm(k_range):
		for c in tqdm(carry_range, leave = False):
			for h in tqdm(home_range, leave = False):
				for n in tqdm(new_team_range, leave = False):
					error1, error2 = tuning_sim(data, k, c, h, n).get_errors()
					errors.append((error1, error2, k, c, h, n))

	return errors

def tune(data, tune_style_random = False, random_iterations = 50):
	if tune_style_random:
		errors = random_tune(data, random_iterations)
	else:
		errors = brute_tune(data)

	se1 = sorted(errors, key = lambda x: x[0])
	se2 = sorted(errors, key = lambda x: x[1])
	return se1, se2

################Brier (Error 1) Over Time####################
def error1_viz(explore):
	size = 5750 #roughly the number of games per season if we have ~40K errors over the course of 7 seasons (Fall 2014 - Spring 2021)
	leftover = len(explore.error1) % size
	y_vals = [sum(explore.error1[i*size:(i*size)+size])/size for i in range(len(explore.error1)//size)] + [sum(explore.error1[-leftover:])/leftover]
	sizes = [size for i in range(len(explore.error1)//size)] + [leftover]
	x_vals = [i for i in range(len(sizes))]
	fig = go.Figure([go.Bar(x = x_vals, y = y_vals, text = ['n = ' + str(size) for size in sizes], textposition = 'auto')])
	fig.update_layout(title_text = 'Brier Score Over Time: Fall 2014 - Fall 2022', 
		xaxis_title = 'Bucket of Chronological Games', yaxis_title = 'Avg. Brier Score in Bucket')
	fig.show()

###################Visualizing Error 2#######################
def error2_viz(explore):
	x_vals = [i for i in explore.predict_tracker]
	y_vals = [explore.win_tracker[i]/explore.predict_tracker[i] for i in x_vals]
	sizes = [explore.predict_tracker[i] for i in x_vals]
	fig = go.Figure()
	fig.add_trace(go.Scatter(x = x_vals, y = y_vals, mode = 'markers', name = 'Predictions', text = ['n = ' + str(size) for size in sizes]))
	fig.add_trace(go.Scatter(x = [0, 1], y = [0, 1], mode = 'lines', name = 'Perfect Line'))
	r2 = r2_score(x_vals, y_vals)
	fig.update_layout(title_text = 'Predicted vs. Actual Win Probability (R^2 = 0.99)', xaxis_title = 'Predicted Win Probability', yaxis_title = 'Actual Win Probability')
	fig.show()

##############Elo margin vs. Margin of Victory################
def elo_vs_MoV(explore):
	x_vals = [i for i in explore.elo_margin_tracker]
	y_vals = [explore.MoV_tracker[i]/explore.elo_margin_tracker[i] for i in x_vals]
	sizes = [explore.elo_margin_tracker[i] for i in x_vals]
	fig = go.Figure()
	fig.add_trace(go.Scatter(x = x_vals, y = y_vals, mode = 'markers', name = 'Results', 
		text = ['n = ' + str(size) for size in sizes], marker=dict(size=[s/120 for s in sizes])))
	#fit a line to middle 80% of data (Pareto principle)
	target_points = sum(sizes)*.8*.5 #I want to reach 80% of points on the positive side. They are duplicated on the negative side, so really 40% of total points
	points_reached = explore.elo_margin_tracker[0]
	for i in range(1, int(max(x_vals)/25)):
		points_reached += explore.elo_margin_tracker.get(i*25, 0)
		if points_reached > target_points: break
	x_trimmed = [j*25 for j in range(-i, i+1)]
	y_trimmed = [explore.MoV_tracker[i]/explore.elo_margin_tracker[i] for i in x_trimmed]
	slope, intercept, r, p, se = linregress(x_trimmed, y_trimmed)
	print(slope, r)
	# 1/slope tells us what elo difference is equivalent to 1 point difference
	fig.add_trace(go.Scatter(x = x_trimmed, y = [i*slope + intercept for i in x_trimmed], mode = 'lines', 
		name = 'LSRL for Middle 80% of Games (R^2 > 0.99)'))
	fig.update_layout(title_text = f'Elo Margin vs. Average Scoring Margin: 1 game point = {-elo.ELO_TO_POINTS_FACTOR} Elo points', 
		xaxis_title = 'Elo Margin', yaxis_title = 'Average Actual Scoring Margin')
	fig.show()

#################Elo Season-over-Season########################
def elo_season_over_season(explore):
	season_totals = {}
	season_teams = {}
	years = ['20110404', '20120402', '20130408', '20140407', 
			'20150406', '20160404', '20170403', '20180402', 
			'20190408', '20200311', '20210405', '20220404']
	if years[-1] == explore.date: explore.season_reset(elo.SEASON_CARRY)
	for team in explore.teams:
		for year in years:
			for date, snap in explore.teams[team].snapshots:
				if date == year:
					season_totals[year] = season_totals.get(year, 0) + snap
					season_teams[year] = season_teams.get(year, 0) + 1
	y_vals = [round(season_totals[i]/season_teams[i]) for i in season_teams]
	x_vals = [i[:4] for i in season_teams]
	sizes = ['teams = ' + str(season_teams[i]) for i in season_teams]
	fig = go.Figure([go.Bar(x = x_vals, y = y_vals, text = sizes, textposition = 'auto')])
	fig.update_layout(title_text = 'Average End-of-Season Elo over Time: Spring 2011 - Spring 2022', 
		xaxis_title = 'Year', yaxis_title = 'End of Season Elo')
	fig.show()

##################LATEST DISTRIBUTION##########################
def latest_dist(explore):
	bucketing = {}
	bucket_size = 20
	for team in explore.teams:
		rounded = round(explore.get_elo(team) / bucket_size) * bucket_size
		bucketing[rounded] = bucketing.get(rounded, []) + [team]
	x_vals = [i for i in range(min(bucketing), max(bucketing) + 1, 10)]
	y_vals = [len(bucketing.get(i, [])) for i in x_vals]
	fig = go.Figure([go.Bar(x = x_vals, y = y_vals, text = [bucketing.get(i, []) for i in x_vals])])
	fig.update_layout(title_text = 'Elo Distribution through ' + explore.date, xaxis_title = 'Elo Rating', 
		yaxis_title = 'Number of Teams', xaxis_range = [1000, x_vals[-1]+1], yaxis_range = [0, 20])
	fig.show()

##################SPREAD EVALUATION##############################
def spread_evaluation(explore, exclusion_threshold = 25, month_day_start = '1201'):
	'''
	The exclusion_threshold does not count games where the difference between the elo and vegas spreads is greater than
	this threshold. These games are likely errors in either the spread predicted or in the vegas spread read in from the
	historical data file. 
	In addition, games occurring before month_day_start within a season are not tracked. The theory is that the model
	needs some time each season to tune itself. We need to wait until it has seen a few games from each season before we
	would consider acting on its predictions.
	'''
	x_vals = []
	y_vals_win = []
	y_vals_pick = []
	ns = []
	for k in np.arange(0, min(exclusion_threshold, 20), .25):
		take_a_side = 0 #made a "bet"
		correct_side = 0 #"bet" was correct
		tied_side = 0 #"bet" was a push
		agreed = 0 #the elo vs. vegas spread difference was not great enough to trigger "bet"
		for row in explore.spread_tracker:
			if row[2] == 'NL': continue #we don't have a historical spread, so ignore
			away_score, home_score, away_veg_spread, away_elo_spread = map(float, row[:4])
			
			game_month_day = row[-1][4:]
			if game_month_day >= '0501' and game_month_day < month_day_start: continue #skip those too early in the season
			if abs(away_veg_spread - away_elo_spread) > exclusion_threshold: continue #skip those where the difference is too big to trust

			adjusted_score_away = away_score + away_veg_spread
			if away_veg_spread - away_elo_spread > k: #elo says take the away team
				if adjusted_score_away > home_score: 
					correct_side += 1 #elo-informed "bet" was correct
				if adjusted_score_away == home_score:
					tied_side += 1 #elo-informed "bet" was a push
				take_a_side += 1 #either way, elo suggested making a "bet"
			elif away_elo_spread - away_veg_spread > k: #elo says take the home team
				if adjusted_score_away < home_score: 
					correct_side += 1 #elo-informed "bet" was correct
				if adjusted_score_away == home_score:
					tied_side += 1 #elo-informed "bet" was a push
				take_a_side += 1 #either way, elo suggested making a "bet"
			else: #elo agrees with vegas
				agreed += 1
		x_vals.append(k)
		y_vals_win.append(correct_side/(take_a_side - tied_side)) #track win percentage
		y_vals_pick.append(take_a_side/(take_a_side + agreed)) #track % of games with spread data for which a pick was made
		ns.append(take_a_side)

	fig = make_subplots(specs=[[{"secondary_y": True}]])
	fig.add_trace(go.Scatter(x = x_vals, y = y_vals_win, mode = 'lines', name = 'Elo Pick Win'), secondary_y = False)
	fig.add_trace(go.Scatter(x = x_vals, y = y_vals_pick, mode = 'lines', name = 'Games Meeting Criteria',
					hovertemplate="%: %{y}<br>games: %{customdata}<extra></extra>", customdata = ns), 
					secondary_y = True)
	fig.add_trace(go.Scatter(x = x_vals, y = [.52381 for _ in x_vals], mode = 'lines', 
					name = 'Breakeven with -110 Odds', line = dict(dash='dashdot')), secondary_y = False)
	fig.update_yaxes(title_text = 'Elo Win %', secondary_y = False)
	fig.update_yaxes(title_text = 'Games Meeting Criteria %', secondary_y = True)
	fig.update_layout(title_text = 'Win Percentage of Elo-Informed Picks', 
					xaxis_title = 'Difference between Elo and Vegas Required for Pick',
					plot_bgcolor='rgba(0,0,0,0)', yaxis_tickformat = ',.2%', yaxis2_tickformat = ',.2%')
	fig.show()

###############HISTORICAL BRACKET PERFORMANCE##################
def historical_brackets(explore):
	scores = [10, 20, 40, 80, 160, 320] #ESPN scoring system for correct game in round
	def evaluate_brackets(predictions, real_results):
		predictions_score = 0
		for index in range(len(ROUNDS)-1):
			predictions_score += sum([scores[index] if predictions[ROUNDS[index+1]][i][0] == real_results[ROUNDS[index+1]][i] else 0 for i in range(len(predictions[ROUNDS[index+1]]))])
		return predictions_score

	for stop_date, tourney_filepath in [('20210316', 'tournament_results_2022.csv'),
										('20210317', 'tournament_results_2021.csv'), 
										('20190320', 'tournament_results_2019.csv'), 
										('20180314', 'tournament_results_2018.csv'), 
										('20170315', 'tournament_results_2017.csv')]:
		elo_state = elo.main(stop_short = stop_date)
		df = pd.read_csv(utils.DATA_FOLDER + tourney_filepath)
		tournamant_teams = list(df['first'].dropna())
		results = {'first': tournamant_teams}
		for r in ROUNDS:
			results[r] = df[r].dropna().values
		best_bracket = predict_tournament(elo_state, tournamant_teams, pick_mode = 1)
		print(evaluate_brackets(best_bracket, results))

	remaining = [32, 16, 8, 4, 2, 1]
	print(sum([remaining[index]*scores[index]*(.5**(index + 1)) for index in range(6)]))

	#2022: 350
	#2021: 860
	#2019: 1250
	#2018: 840
	#2017: 740
	#Random: 315

###########################GRAPHING##########################
def graphing(data):
	explore = tuning_sim(data, elo.K_FACTOR, elo.SEASON_CARRY, elo.HOME_ADVANTAGE, elo.NEW_ELO)
	# print(explore.get_errors())
	# error1_viz(explore)
	# error2_viz(explore)
	# elo_vs_MoV(explore)
	# elo_season_over_season(explore)
	# latest_dist(explore)
	spread_evaluation(explore, exclusion_threshold = 25, month_day_start = '1201')
	# historical_brackets(explore)

###########################TUNING############################
def tuning(data, target = 'error1', graphs = True, verbose = False, tune_style_random = False, random_iterations = 50):
	se1, se2 = tune(data, tune_style_random, random_iterations)
	if verbose: print(se1, se2)
	if not graphs: return
	
	# start measuring after season 3 (start fall 2014), errors as of games through 11/22/2022
	# best e1 optimized:	(error1 = 7958.22, error2 = 0.0135, k_factor = 46, carryover = .9, home_elo = 82, new_team = 950)
	# best e2 optimized:	(error1 = 7961.10, error2 = 0.0085, k_factor = 46, carryover = .91, home_elo = 75, new_team = 925)
	# hybrid (active):		(error1 = 7958.51, error2 = 0.0099, k_factor = 46, carryover = .91, home_elo = 80, new_team = 950), 25.6

	# take the output of tuning and plot the errors over each of the variables
	mapping = {'error1': 0, 'error2': 1}
	for i in [2, 3, 4, 5]:
		fig = go.Figure()
		fig.add_trace(go.Scatter(x = [j[i] for j in se1], y = [j[mapping[target]] for j in se1], mode = 'markers'))
		fig.show()
	fig = go.Figure()
	fig.add_trace(go.Scatter(x = [j[0] for j in se1], y = [j[1] for j in se1], mode = 'markers'))
	fig.show()	

if __name__ == '__main__':
	filepath = utils.get_latest_data_filepath()
	data = utils.read_csv(filepath)

	### UNCOMMENT A FUNCTION BELOW DEPENDING ON USE CASE ###

	#go into the graphing() function above to comment/uncomment which figures are desired
	graphing(data)

	#start with random_tune, then switch to brute_tune when the ranges for values are tight enough so as not to take too long to run
	# tuning(data, target = 'error2', graphs = True, verbose = True, tune_style_random = False, random_iterations = 50)
