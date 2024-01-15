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
from datetime import datetime
from predictions import predict_tournament, ROUNDS, predict_game
import math

ERRORS_START = 3 #after how many seasons should we start tracking performance (3 = start with 2013 season = 10 full seasons of data 2013-2022)

class Tuning_ELO_Sim(elo.ELO_Sim):
	'''
	This class is an extension of ELO_Sim that allows us to keep track of errors and extra metrics through the
	simulation process which are useful for tuning. Errors tracked are...
	error1: Brier score (https://en.wikipedia.org/wiki/Brier_score). Average of (predicted probability - outcome)^2
	error2: Log loss (https://www.analyticsvidhya.com/blog/2020/11/binary-cross-entropy-aka-log-loss-the-cost-function-used-in-logistic-regression/). Average of -(outcome * log(predicted probability of that outcome))
	'''
	def __init__(self):
		super().__init__()
		self.predict_tracker = {}
		self.spread_tracker = []
		self.win_tracker = {0.0: 0}
		self.elo_margin_tracker = {}
		self.MoV_tracker = {}
		self.error1 = []
		self.error2 = []

	def update_errors(self, w_winp, for_spread_tracker):
		if self.season_count >= ERRORS_START:
			rounded, roundedL = round(w_winp, 2), round(1 - w_winp, 2)
			self.error1.append((1 - w_winp)**2)
			self.error2.append(-math.log(w_winp) if w_winp != 0 else -math.log(.000000001))
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
		return (sum(self.error1) / len(self.error1), sum(self.error2) / len(self.error2))

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
	k_range = np.arange(45, 51, 1)
	carry_range = np.arange(.58, .71, .03)
	home_range = np.arange(78, 87, 2)
	new_team_range = np.arange(950, 1051, 25)
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
	k_range = [46, 47]
	carry_range = [.64, .66]
	home_range = [81, 82, 83, 84]
	new_team_range = [970, 985, 1000] 
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

################Error Over Time####################
def error_viz(explore, error_list, error_string):
	size = 5750 #roughly the number of games per season if we have ~40K errors over the course of 7 seasons (Fall 2014 - Spring 2021)
	leftover = len(error_list) % size
	y_vals = [sum(error_list[i*size:(i*size)+size])/size for i in range(len(error_list)//size)] + [sum(error_list[-leftover:])/leftover]
	sizes = [size for i in range(len(error_list)//size)] + [leftover]
	x_vals = [i for i in range(len(sizes))]
	fig = go.Figure([go.Bar(x = x_vals, y = y_vals, text = ['n = ' + str(size) for size in sizes], textposition = 'auto')])
	fig.update_layout(title_text = f'{error_string} Over Time', 
		xaxis_title = 'Bucket of Chronological Games', yaxis_title = f'Avg. {error_string} in Bucket')
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
	print(f'Slope of {slope}. R^2 of {r}. Fitted from {min(x_trimmed)} to {max(x_trimmed)}')
	print(f'The elo difference equivalent to a 1-point difference: {1/slope}')
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
def get_breakeven(x_vals, y_vals):
	'''
	Loop through x and y values to find the first instance where the y_val is greater than the 
	typical vegas breakeven rate (52.381%)
	'''
	for x, y in zip(x_vals, y_vals):
		if y > .52381: return x

def convert_spread_to_winnings_mult(spread):
	'''
	What is the relationship between a vegas spread and the ml? 
	Use https://oddsjam.com/betting-calculators/point-spread for exact estimates between -6.5 and 6.5
	Fit an exponential function to 2-13.5 and -6.5--13.5 to predict the rest of the relationships

	Then what is the profit earned if you won with that ML?
	- when ML > 0, p = ml/100
	- when ML < 0, p = -100/ml
	'''
	sp_map = {-6.5: -288, -6: -264, -5.5: -235, -5: -212, -4.5: -191, -4: -180, -3.5: -168, -3: -155, -2.5: -140, -2: -134, -1.5: -127, -1: -118, -0.5: -114, 0: -110,
				6.5: 215, 6: 197, 5.5: 183, 5: 171, 4.5: 160, 4: 148, 3.5: 136, 3: 129, 2.5: 119, 2: 111, 1.5: 106, 1: 100, 0.5: -106}
	if spread in sp_map:
		ml = sp_map[spread]
		return ml / 100 if ml > 0 else -100 / ml
	elif spread <= -1:
		ml = 67.154 * math.exp(-.2105 * spread)
		return 100 / ml
	elif spread >= 1:
		ml = 77.055 * math.exp(.1623 * spread)
		return ml / 100

def create_predictions_csv_for_export(explore, exclude_nls = True):
	save_rows = []
	for row in explore.spread_tracker:
		if exclude_nls and row[2] == 'NL': 
			continue #we don't have a historical spread, so ignore

		away_score, home_score, away_veg_spread, away_elo_spread = map(float, row[:4])
		away_winp = elo.winp(away_elo_spread * elo.ELO_TO_POINTS_FACTOR)
		home_winp = 1 - away_winp
		home_profit = convert_spread_to_winnings_mult(-away_veg_spread)
		away_profit = convert_spread_to_winnings_mult(away_veg_spread)
		if away_elo_spread == away_veg_spread:
			spread_pred = 'N/A'
		elif away_veg_spread - away_elo_spread > 0:
			spread_pred = 'Away'
		elif away_elo_spread - away_veg_spread > 0:
			spread_pred = 'Home'

		adjusted_score_away = away_score + away_veg_spread
		if adjusted_score_away == home_score:
			spread_outcome = 'N/A'
		elif adjusted_score_away > home_score:
			spread_outcome = 'Away'
		elif adjusted_score_away < home_score:
			spread_outcome = 'Home'

		if home_winp == away_winp:
			ml_pred = 'N/A'
		elif home_winp > away_winp:
			ml_pred = 'Home'
		elif home_winp < away_winp:
			ml_pred = 'Away'

		ml_outcome = 'Home' if home_score > away_score else 'Away'

		save_rows.append([away_score, away_elo_spread, away_veg_spread, away_winp, away_profit, home_score, home_winp, home_profit, spread_pred, spread_outcome, ml_pred, ml_outcome])

	utils.save_data(utils.DATA_FOLDER + 'all_preds_through_' + explore.date + '_as_of_'+ datetime.now().date().strftime('%Y%m%d') + '.csv', save_rows)

def spread_evaluation(explore, exclusion_threshold = 25, accuracy_cap = 1000, by_month = None, plot = True):
	'''
	The exclusion_threshold does not count games where the difference between the elo and vegas spreads is greater than
	this threshold. These games are likely errors in either the spread predicted or in the vegas spread read in from the
	historical data file. 

	accuracy_cap ignores games where the elo difference between two teams is too large for us to be confident in
	the projection. Per findings in the elo_vs_MoV() graph, once the elo difference between two teams gets large enough,
	we can no longer accurately project the margin of victory with a straight-line relationship between ELO and margin

	The by_month parameter can be set to a string representing a month of the CBB season (e.g. '11', '12', '01', etc.).
	The purpose of this will be to evaluate performance against the spread at various points in the season. The hypothesis
	is that the model needs some time to sort out who is good and who is bad every season such that our predictions, and
	our edge, become more prominent in the later months of a season
	'''
	x_vals = []
	y_vals_win = []
	y_vals_pick = []
	ns = []
	for k in np.arange(0, min(exclusion_threshold, 20), .25): #don't want to graph more than 20 on the x axis
		take_a_side = 0 #made a "bet"
		correct_side = 0 #"bet" was correct
		tied_side = 0 #"bet" was a push
		agreed = 0 #the elo vs. vegas spread difference was not great enough to trigger "bet"
		for row in explore.spread_tracker:
			if row[2] == 'NL': continue #we don't have a historical spread, so ignore
			away_score, home_score, away_veg_spread, away_elo_spread = map(float, row[:4])
			
			game_month = row[-1][4:6] #e.g. from '20221118', this takes '11'
			if by_month != None and game_month != by_month: continue #if by_month is set, skip all games not in the set by_month

			if abs(away_veg_spread - away_elo_spread) > exclusion_threshold: continue #skip those where the difference is too big to trust

			if abs(away_elo_spread) > accuracy_cap / - elo.ELO_TO_POINTS_FACTOR: continue #skip those where the predicted margin is outside our confidence zone

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
		y_vals_win.append(0 if correct_side == 0 else correct_side/(take_a_side - tied_side)) #track win percentage
		y_vals_pick.append(take_a_side/(take_a_side + agreed)) #track % of games with spread data for which a pick was made
		ns.append(take_a_side)

	if not plot: return get_breakeven(x_vals, y_vals_win) #if we're not using this function to graph, we're using it to find the first breakeven
	
	fig = make_subplots(specs=[[{"secondary_y": True}]])
	fig.add_trace(go.Scatter(x = x_vals, y = y_vals_win, mode = 'lines', name = 'Elo Pick Win'), secondary_y = False)
	fig.add_trace(go.Scatter(x = x_vals, y = y_vals_pick, mode = 'lines', name = 'Games Meeting Criteria',
					hovertemplate="%: %{y}<br>games: %{customdata}<extra></extra>", customdata = ns), 
					secondary_y = True)
	fig.add_trace(go.Scatter(x = x_vals, y = [.52381 for _ in x_vals], mode = 'lines', 
					name = 'Breakeven with -110 Odds', line = dict(dash='dashdot')), secondary_y = False)
	fig.update_yaxes(title_text = 'Elo Win %', secondary_y = False)
	fig.update_yaxes(title_text = 'Games Meeting Criteria %', secondary_y = True)
	fig.update_layout(title_text = f'Win Percentage of Elo-Informed Picks with Accuracy Cap = {accuracy_cap} Elo points and Exclusion Threshold = {exclusion_threshold} points', 
					xaxis_title = 'Difference between Elo and Vegas Required for Pick',
					plot_bgcolor='rgba(0,0,0,0)', yaxis_tickformat = ',.2%', yaxis2_tickformat = ',.2%')
	fig.show()

###############SPREAD OVER COURSE OF SEASON####################
def eval_spread_over_season(explore, months = ['11', '12', '01', '02', '03', '04'], exclusion_threshold = 25, accuracy_cap = 1000):
	'''
	The hypothesis is that early in the season, our predictions will be less accurate than they are later in the season.
	The model needs time (game data) to sort out the kinks and converge on a more accurate Elo rating for each team.
	When the difference between the model's prediction and the vegas spread is greater than X, we should trust our model
	to outperform Vegas. To do that, we need to be right more than ~52% of the time. This function loops through the months
	specified (format as 'MM') and calculates that X breakeven value within that month historically. In theory, we should see
	the value of X decreases as we get further and futher into the season. Our predictions are more and more accurate.
	'''
	print('Finding breakeven for multiple date cutoffs...')
	y_vals = []
	for d in tqdm(months):
		y_vals.append(spread_evaluation(explore, exclusion_threshold, accuracy_cap, d, plot = False))
	fig = go.Figure([go.Bar(x = months, y = y_vals, name = 'Breakeven Difference for Games After')])
	fig.update_layout(title_text = 'Difference Between Model Prediction and Vegas Spread Needed to Break Even (52.381%+) Re-Calculated as Season Progresses', 
		xaxis_title = 'Predictions Made After Date (MMDD)', yaxis_title = 'Breakeven Difference')
	fig.update_xaxes(type = 'category')
	fig.show()

###############HISTORICAL BRACKET PERFORMANCE##################
def historical_brackets(explore):
	scores = [10, 20, 40, 80, 160, 320] #ESPN scoring system for correct game in round
	def evaluate_brackets(predictions, real_results):
		predictions_score = 0
		for index in range(len(ROUNDS)-1):
			predictions_score += sum([scores[index] if predictions[ROUNDS[index+1]][i][0] == real_results[ROUNDS[index+1]][i] else 0 for i in range(len(predictions[ROUNDS[index+1]]))])
		return predictions_score

	for stop_date, tourney_filepath in [('20230315', 'tournament_results_2023.csv'),
										('20220316', 'tournament_results_2022.csv'),
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

	#2023: 380
	#2022: 450
	#2021: 820
	#2019: 1340
	#2018: 890
	#2017: 650
	#Random: 315

###########################GRAPHING##########################
def graphing(data):
	explore = tuning_sim(data, elo.K_FACTOR, elo.SEASON_CARRY, elo.HOME_ADVANTAGE, elo.NEW_ELO)
	# print(explore.get_errors())
	# error_viz(explore, explore.error1, 'Brier Score')
	# error_viz(explore, explore.error2, 'Log Loss')
	# elo_vs_MoV(explore)
	# elo_season_over_season(explore)
	# latest_dist(explore)
	# historical_brackets(explore)
	# eval_spread_over_season(explore, exclusion_threshold = 25, accuracy_cap = 325)
	# spread_evaluation(explore, exclusion_threshold = 25, accuracy_cap = 325)
	# spread_evaluation(explore, exclusion_threshold = 25, accuracy_cap = 325, by_month = '11')
	# spread_evaluation(explore, exclusion_threshold = 25, accuracy_cap = 325, by_month = '12')
	# spread_evaluation(explore, exclusion_threshold = 25, accuracy_cap = 325, by_month = '01')
	# spread_evaluation(explore, exclusion_threshold = 25, accuracy_cap = 325, by_month = '02')
	# spread_evaluation(explore, exclusion_threshold = 25, accuracy_cap = 325, by_month = '03')
	# create_predictions_csv_for_export(explore)

###########################TUNING############################
def tuning(data, target = 'error1', graphs = True, verbose = False, tune_style_random = False, random_iterations = 50):
	se1, se2 = tune(data, tune_style_random, random_iterations)
	if verbose: print(se1, se2)
	if not graphs: return
	
	# important to remember the final step after setting k, carryover, home_elo, and new_team in elo.py: run elo_vs_MoV()! 
	# This prints out the slope of the relationship between elo differences and margins of victory. Take 1/slope and set 
	# ELO_TO_POINTS_FACTOR equal to -(1/slope)

	# start measuring after season 3 (start fall 2013), errors as of games through 11/17/2023
	# hybrid (active):	(error1 = 0.16893, error2 = 0.50379, k_factor = 47, carryover = .64, home_elo = 82, new_team = 985), 24.78
	# e1 (brier score):	(error1 = 0.16892, error2 = 0.50393, k_factor = 46, carryover = .64, home_elo = 81, new_team = 1000), 24.35
	# e2 (log loss):	(error1 = 0.16896, error2 = 0.50373, k_factor = 47, carryover = .65, home_elo = 84, new_team = 970), 25.18
	

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
	# tuning(data, target = 'error1', graphs = True, verbose = True, tune_style_random = False, random_iterations = 50)
