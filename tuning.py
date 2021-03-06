import numpy as np
from tqdm import tqdm
import elo
import utils
import random
import plotly.graph_objects as go
from sklearn.metrics import r2_score
from scipy.stats import linregress
import pandas as pd
from predictions import predict_tournament, ROUNDS

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
		self.win_tracker = {}
		self.elo_margin_tracker = {}
		self.MoV_tracker = {}
		self.error1 = []

	def update_errors(self, w_winp):
		if self.season_count >= ERRORS_START:
			rounded, roundedL = round(w_winp, 2), round(1 - w_winp, 2)
			self.error1.append((1 - w_winp)**2)
			self.win_tracker[rounded] = self.win_tracker.get(rounded, 0) + 1
			self.predict_tracker[rounded] = self.predict_tracker.get(rounded, 0) + 1
			self.predict_tracker[roundedL] = self.predict_tracker.get(roundedL, 0) + 1

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

def tuning_sim(data, k_factor, new_season_carry, home_elo):
	'''
	This function runs through all of the data and updates elo and errors along the way
	It is a simplified version of the official sim function used in elo.py
	'''
	this_sim = Tuning_ELO_Sim()
	this_month = data[0][-1][4:6]
	
	for row in data:
		row_month = int(row[-1][4:6])
		if this_month == 4 and row_month == 11:
			this_sim.season_count += 1
			this_sim.season_reset(new_season_carry)
		this_sim.date = row[-1]
		this_month = row_month
		elo_margin, MoV = elo.step_elo(this_sim, row, k_factor, home_elo)
		this_sim.update_errors(elo.winp(elo_margin))
		this_sim.update_MoVs(elo_margin, MoV)
	
	return this_sim

def random_tune(data, number):
	'''
	Use this function to repeatedly narrow down tighter and tighter ranges of possible optimal values for k, carry, and home elo advantage
	Start with wide ranges, then use the outputs (which are sorted by their errors) to inform a tighter range for the next iteration
	Once windows are small enough, switch to brute_tune
	'''
	k_range = np.arange(10, 60.5, .5)
	carry_range = np.arange(.5, 1.05, .05)
	home_range = np.arange(50, 200, 5)
	errors = []
	
	for i in tqdm(range(number)):
		k_factor, new_season_carry, home_elo = random.choice(k_range), random.choice(carry_range), random.choice(home_range)
		error1, error2 = tuning_sim(data, k_factor, new_season_carry, home_elo).get_errors()
		errors.append((error1, error2, k_factor, new_season_carry, home_elo))

	return errors

def brute_tune(data):
	'''
	Use this function to cycle through all possible combinations of the 3 variables within the defined ranges and find the optimal solution
	Since brute force can take some time to run, random_tune first to help narrow possible ranges
	'''
	k_range = np.arange(42, 52, .5)
	carry_range = np.arange(.95, 1.025, .025)
	home_range = np.arange(75, 96, 1)
	errors = []

	for k in tqdm(k_range):
		for c in carry_range:
			for h in home_range:
				error1, error2 = tuning_sim(data, k, c, h).get_errors()
				errors.append((error1, error2, k, c, h))

	return errors

def tune(data):
	#start with random_tune, then switch to brute_tune when the ranges for values are tight enough so as not to take too long to run
	errors = random_tune(data, 5)
	# errors = brute_tune(data)
	print(sorted(errors, key = lambda x: x[0]))
	print(sorted(errors, key = lambda x: x[1]))

filepath = utils.get_latest_data_filepath()
data = utils.read_csv(filepath)
explore = tuning_sim(data, elo.K_FACTOR, elo.SEASON_CARRY, elo.HOME_ADVANTAGE)

###########################TUNING############################
# tune(data)
# # start measuring after season 3 (start fall 2014)
# # best: (error1 = 6787.1710585282635, error2 = 0.010835972134262182, k_factor = 47, carryover = 1, home_elo = 83)

################Brier (Error 1) Over Time####################
# size = 5700 #roughly the number of games per season if we have ~40K errors over the course of 7 seasons (Fall 2014 - Spring 2021)
# leftover = len(explore.error1) % size
# y_vals = [sum(explore.error1[i*size:(i*size)+size])/size for i in range(len(explore.error1)//size)] + [sum(explore.error1[-leftover:])/leftover]
# sizes = [size for i in range(len(explore.error1)//size)] + [leftover]
# x_vals = [i for i in range(len(sizes))]
# fig = go.Figure([go.Bar(x = x_vals, y = y_vals, text = ['n = ' + str(size) for size in sizes], textposition = 'auto')])
# fig.update_layout(title_text = 'Brier Score Over Time: Fall 2014 - Spring 2021', xaxis_title = 'Bucket of Chronological Games', yaxis_title = 'Brier Score in Bucket')
# fig.show()

###################Visualizing Error 2#######################
# x_vals = [i for i in explore.predict_tracker]
# y_vals = [explore.win_tracker[i]/explore.predict_tracker[i] for i in x_vals]
# sizes = [explore.predict_tracker[i] for i in x_vals]
# fig = go.Figure()
# fig.add_trace(go.Scatter(x = x_vals, y = y_vals, mode = 'markers', name = 'Predictions', text = ['n = ' + str(size) for size in sizes]))
# fig.add_trace(go.Scatter(x = [0, 1], y = [0, 1], mode = 'lines', name = 'Perfect Line'))
# r2 = r2_score(x_vals, y_vals)
# fig.update_layout(title_text = 'Predicted vs. Actual Win Probability (R^2 = 0.99)', xaxis_title = 'Predicted Win Probability', yaxis_title = 'Actual Win Probability')
# fig.show()

##############Elo margin vs. Margin of Victory################
# x_vals = [i for i in explore.elo_margin_tracker]
# y_vals = [explore.MoV_tracker[i]/explore.elo_margin_tracker[i] for i in x_vals]
# sizes = [explore.elo_margin_tracker[i] for i in x_vals]
# fig = go.Figure()
# fig.add_trace(go.Scatter(x = x_vals, y = y_vals, mode = 'markers', name = 'Results', text = ['n = ' + str(size) for size in sizes], marker=dict(size=[s/120 for s in sizes])))
# #fit a line to middle 80% of data (Pareto principle)
# target_points = sum(sizes)*.8*.5 #I want to reach 80% of points on the positive side. They are duplicated on the negative side, so really 40% of total points
# points_reached = explore.elo_margin_tracker[0]
# for i in range(1, int(max(x_vals)/25)):
# 	points_reached += explore.elo_margin_tracker.get(i*25, 0)
# 	if points_reached > target_points: break
# x_trimmed = [j*25 for j in range(-i, i+1)]
# y_trimmed = [explore.MoV_tracker[i]/explore.elo_margin_tracker[i] for i in x_trimmed]
# slope, intercept, r, p, se = linregress(x_trimmed, y_trimmed)
# # slope: 0.03922 -> 1/slope: 25.5 elo difference / point difference
# fig.add_trace(go.Scatter(x = x_trimmed, y = [i*slope + intercept for i in x_trimmed], mode = 'lines', name = 'LSRL for Middle 80% of Games (R^2 = 0.99)'))
# fig.update_layout(title_text = 'Elo Margin vs. Average Scoring Margin: 1 game point = 25.5 Elo points', xaxis_title = 'Elo Margin', yaxis_title = 'Average Actual Scoring Margin')
# fig.show()

#################Elo Season-over-Season########################
# season_totals = {}
# season_teams = {}
# years = ['20110404', '20120402', '20130408', '20140407', '20150406', '20160404', '20170403', '20180402', '20190408']
# for team in explore.teams:
# 	for year in years:
# 		for date, snap in explore.teams[team].snapshots:
# 			if date == year:
# 				season_totals[year] = season_totals.get(year, 0) + snap
# 				season_teams[year] = season_teams.get(year, 0) + 1
# y_vals = [round(season_totals[i]/season_teams[i]) for i in season_teams]
# x_vals = [i[:4] for i in season_teams]
# sizes = ['teams = ' + str(season_teams[i]) for i in season_teams]
# fig = go.Figure([go.Bar(x = x_vals, y = y_vals, text = sizes, textposition = 'auto')])
# fig.update_layout(title_text = 'Average End-of-Season Elo over Time: Spring 2011 - Spring 2019', xaxis_title = 'Year', yaxis_title = 'End of Season Elo')
# fig.show()

##################LATEST DISTRIBUTION##########################
# bucketing = {}
# for team in explore.teams:
# 	rounded = round(explore.get_elo(team) / 50) * 50
# 	bucketing[rounded] = bucketing.get(rounded, 0) + 1
# x_vals = [i for i in range(min(bucketing), max(bucketing) + 1, 10)]
# y_vals = [bucketing.get(i, 0) for i in x_vals]
# fig = go.Figure([go.Bar(x = x_vals, y = y_vals)])
# fig.update_layout(title_text = 'Elo Distribution through ' + explore.date, xaxis_title = 'Elo Rating', yaxis_title = 'Number of Teams')
# fig.show()

###############HISTORICAL BRACKET PERFORMANCE##################
# scores = [10, 20, 40, 80, 160, 320] #ESPN scoring system for correct game in round
# def evaluate_brackets(predictions, real_results):
# 	predictions_score = 0
# 	for index in range(len(ROUNDS)):
# 		predictions_score += sum([scores[index] if predictions[ROUNDS[index]][i] == real_results[ROUNDS[index]][i] else 0 for i in range(len(predictions[ROUNDS[index]]))])
# 	return predictions_score

# for stop_date, tourney_filepath in [('20190320', 'tournament_results_2019.csv'), ('20180314', 'tournament_results_2018.csv'), ('20170315', 'tournament_results_2017.csv')]:
# 	elo_state = elo.main(stop_short = stop_date)
# 	df = pd.read_csv(utils.DATA_FOLDER + tourney_filepath)
# 	tournamant_teams = list(df['first'].dropna())
# 	results = {'first': tournamant_teams}
# 	for r in ROUNDS:
# 		results[r] = df[r].dropna().values
# 	best_bracket = predict_tournament(elo_state, tournamant_teams, pick_mode = 1)
# 	print(evaluate_brackets(best_bracket, results))

# remaining = [32, 16, 8, 4, 2, 1]
# print(sum([remaining[index]*scores[index]*(.5**(index + 1)) for index in range(6)]))

# #2019: 1260
# #2018: 830
# #2017: 720
# #Random: 315