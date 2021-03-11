import scraper
import utils
import sys
import datetime
import argparse
import pandas as pd

ELO_BASE = 1500
NEW_ELO = 1050
ERRORS_START = 4
K_FACTOR = 47
SEASON_CARRY = 1.0
HOME_ADVANTAGE = 83
ELO_TO_POINTS_FACTOR = -25.25 #divide an elo margin by this to get the point spread
DATA_FOLDER = utils.DATA_FOLDER

class Team():
	def __init__(self, name, starting_elo):
		self.name = name
		self.elo = starting_elo
		self.seven_days_ago = starting_elo

	def update_elo(self, change):
		self.elo = max(0, self.elo + change)

class ELO_Sim():
	def __init__(self):
		self.teams = {} #maintain a dictionary mapping string team name to a Team object
		self.error1 = 0
		self.predict_tracker = {}
		self.win_tracker = {}
		self.season_count = 0
		self.date = ''

	def get_elo(self, name):
		return self.teams[name].elo

	def season_reset(self, new_season_carry):
		for team in self.teams:
			self.teams[team].elo = (self.get_elo(team) * new_season_carry) + ((1 - new_season_carry) * ELO_BASE)

	def add_team(self, name):
		self.teams[name] = Team(name, ELO_BASE if self.season_count == 0 else NEW_ELO)

	def update_elos(self, winner, loser, delta):
		self.teams[winner].update_elo(delta)
		self.teams[loser].update_elo(-delta)

	def get_top(self, x):
		return sorted([(self.teams[team].name, round(self.get_elo(team), 0), "{0:+.0f}".format(self.get_elo(team) - self.teams[team].seven_days_ago)) for team in self.teams], key = lambda x: x[1], reverse = True)[:x]

	def last_week_save(self):
		for team in self.teams:
			self.teams[team].seven_days_ago = self.get_elo(team)

	#error functions used in tuning.py
	def update_errors(self, w_winp):
		if self.season_count >= ERRORS_START:
			self.error1 += (1 - w_winp)**2
			self.win_tracker[round(w_winp, 2)] = self.win_tracker.get(round(w_winp, 2), 0) + 1
			self.predict_tracker[round(w_winp, 2)] = self.predict_tracker.get(round(w_winp, 2), 0) + 1
			self.predict_tracker[round(1-w_winp, 2)] = self.predict_tracker.get(round(1-w_winp, 2), 0) + 1

	def get_errors(self):
		error2 = 0
		total_games = sum(self.predict_tracker.values())
		for i in sorted(self.predict_tracker):
			result = self.win_tracker.get(i, 0)/self.predict_tracker[i]
			error2 += self.predict_tracker[i] * abs(result - i)
		return (self.error1, error2 / total_games)

def calc_MoV_multiplier(elo_margin, MoV):
	#adjusted 538s NBA MoV multiplier curve to better fit the distribution of NCAA MoVs
	a = (MoV + 2.5)**.7 #nba adds 3 and raise to .8
	b = 6 + max(.006 * elo_margin, -5.99) #nba does 7.5 + .006 * elo_margin
	return a/b

def winp(elo_spread):
	if elo_spread > ELO_BASE:
		return 1
	if elo_spread < -ELO_BASE:
		return 0
	return 1 / (1 + 10**(-elo_spread/400))

def step_elo(this_sim, row, k_factor, home_elo):
	home, away = row[3], row[1]
	homeScore, awayScore = int(row[4]), int(row[2])
	winner, loser = home if homeScore > awayScore else away, home if awayScore > homeScore else away
	winnerScore, loserScore = homeScore if homeScore > awayScore else awayScore, homeScore if awayScore > homeScore else awayScore

	if home not in this_sim.teams: this_sim.add_team(home)
	if away not in this_sim.teams: this_sim.add_team(away)

	home_boost = home_elo if row[0] == '0' else 0
	Welo_0, Lelo_0 = this_sim.get_elo(winner), this_sim.get_elo(loser)
	if winner == home: Welo_0 += home_boost
	else: Lelo_0 += home_boost
	
	elo_margin = Welo_0 - Lelo_0 #winner minus loser elo
	w_winp = winp(elo_margin)
	
	MoV = winnerScore - loserScore
	MoV_multiplier = calc_MoV_multiplier(elo_margin, MoV)
	elo_delta = round(k_factor * MoV_multiplier * (1 - w_winp), 2)
	this_sim.update_elos(winner, loser, elo_delta)
	this_sim.update_errors(w_winp)

def sim(data, k_factor, new_season_carry, home_elo, stop_short = '99999999'):
	this_sim = ELO_Sim()
	this_month = data[0][-1][4:6]
	last_day = data[-1][-1] if stop_short > data[-1][-1] else (datetime.datetime.strptime(stop_short, '%Y%m%d') - datetime.timedelta(days = 1)).strftime('%Y%m%d')
	week_early = (datetime.datetime.strptime(last_day, '%Y%m%d') - datetime.timedelta(days = 6)).strftime('%Y%m%d')
	set_early = False

	for row in data:
		if row[-1] >= week_early and not set_early: 
			this_sim.last_week_save() #save each team's elo here so we can calculate change in the last 7 days at the end
			set_early = True
		if row[-1] >= stop_short: break
		this_sim.date = row[-1]
		row_month = int(row[-1][4:6])
		if this_month == 4 and row_month == 11:
			this_sim.season_count += 1
			this_sim.season_reset(new_season_carry)
		this_month = row_month
		step_elo(this_sim, row, k_factor, home_elo)
	
	return this_sim

def main(args):
	#args is a dictionary mapping 'u', 't', and 'd' to their various inputs (all default to None, except 't' defaults to 25)
	#Assumes data formats used throughout are YYYYMMDD
	#By default returns the top 25 teams at the end of the filepath provided.
	#If updating, updates through games completed yesterday. If stopping short, ends sim the day before day specified in 'd'
	filepath = utils.get_latest_data_filepath()
	if args['u']: 
		yesterday = (datetime.date.today() - datetime.timedelta(days = 1)).strftime('%Y%m%d')
		scraper.main(filepath[len(DATA_FOLDER):][0:8], filepath[len(DATA_FOLDER):][-12:-4], yesterday, filepath)
		filepath = filepath[:8 + len(DATA_FOLDER)] + '-' + datetime.date.today().strftime('%Y%m%d') + '.csv'

	data = utils.read_csv(filepath)
	this_sim = sim(data, K_FACTOR, SEASON_CARRY, HOME_ADVANTAGE, stop_short = args['d'])
	rank = 1
	if args['t'] != False:
		output = pd.DataFrame(this_sim.get_top(int(args['t'])), columns = ['Team', 'Elo Rating', '7 Day Change'])
		output['Point Spread vs. Next Rank'] = ["{0:+.1f}".format(((output['Elo Rating'][i] - output['Elo Rating'][i+1])/ELO_TO_POINTS_FACTOR)) for i in range(args['t'] - 1)] + ['']
		output['Rank'] = [i for i in range (1, args['t']+1)]
		utils.table_output(output, 'Ratings through ' + this_sim.date, ['Rank', 'Team', 'Elo Rating', 'Point Spread vs. Next Rank', '7 Day Change'])
			
	return this_sim

def parseArguments():
	parser = argparse.ArgumentParser()
	parser.add_argument('-u', action = 'store_true', help = 'Asks to scrape and update the data with games completed through yesterday')
	parser.add_argument('-t', type = int, default = 25, help = 'Specify how many of the top teams to output. Default is to display the top 25')
	parser.add_argument('-d', type = str, help = 'Use to see the top teams as of a date in the past. Enter date as YYYYMMDD (e.g. 20190315)')
	return parser.parse_args()

if __name__ == '__main__':
	main(parseArguments().__dict__)