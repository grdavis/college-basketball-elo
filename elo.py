import scraper
import utils
import sys
import datetime
import argparse
import pandas as pd

ELO_BASE = 1500
NEW_ELO = 1050
K_FACTOR = 47
SEASON_CARRY = 1.0
HOME_ADVANTAGE = 83
ELO_TO_POINTS_FACTOR = -25.5 #divide an elo margin by this to get the predicted point spread
DATA_FOLDER = utils.DATA_FOLDER

class Team():
	def __init__(self, name, date, starting_elo):
		self.name = name
		self.elo = starting_elo
		self.snapshots = [(date, starting_elo)] #list of ('date', elo)
		self.seven_days_ago = starting_elo

	def update_elo(self, change):
		self.elo = max(0, self.elo + change)

class ELO_Sim():
	def __init__(self):
		self.teams = {} #maintain a dictionary mapping string team name to a Team object
		self.season_count = 0
		self.date = ''

	def get_elo(self, name):
		return self.teams[name].elo

	def snapshot(self):
		for team in self.teams:
			self.teams[team].snapshots.append((self.date, self.get_elo(team)))

	def season_reset(self, new_season_carry):
		self.snapshot()
		for team in self.teams:
			self.teams[team].elo = (self.get_elo(team) * new_season_carry) + ((1 - new_season_carry) * ELO_BASE)

	def add_team(self, name):
		self.teams[name] = Team(name, self.date, ELO_BASE if self.season_count == 0 else NEW_ELO)

	def update_elos(self, winner, loser, delta):
		self.teams[winner].update_elo(delta)
		self.teams[loser].update_elo(-delta)

	def get_top(self, x):
		return sorted([(self.teams[team].name, round(self.get_elo(team), 0), "{0:+.0f}".format(self.get_elo(team) - self.teams[team].snapshots[-1][-1])) for team in self.teams], key = lambda x: x[1], reverse = True)[:x]

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

	return elo_margin, MoV

def sim(data, k_factor, new_season_carry, home_elo, stop_short, last_snap):
	this_sim = ELO_Sim()
	this_month = data[0][-1][4:6]
	last_day = data[-1][-1] if stop_short > data[-1][-1] else stop_short
	early = (datetime.datetime.strptime(last_day, '%Y%m%d') - datetime.timedelta(days = last_snap)).strftime('%Y%m%d')
	set_early = False

	for row in data:
		if row[-1] > early and not set_early: 
			this_sim.snapshot() #save each team's elo here so we can calculate change in the last 7 days at the end
			set_early = True
		if row[-1] > stop_short: break
		row_month = int(row[-1][4:6])
		if this_month == 4 and row_month == 11: #when the data jumps from April to November, it's the start of a new season
			this_sim.season_count += 1
			this_sim.season_reset(new_season_carry)
		this_sim.date = row[-1]
		this_month = row_month
		step_elo(this_sim, row, k_factor, home_elo)
	
	return this_sim

def main(topteams = False, stop_short = '99999999', period = 7):
	'''
	By default, this updates the data by scraping games through yesterday and returns an elo simulation run on the latest data
	It includes several options:
	- output the x 'topteams' by elo rating along with each teams projected point spread over the next team and their change in elo in the last 'period' days
	- 'stop_short' of simulating through the entire dataset by specifying a day to simulate through instead
	'''	
	filepath = utils.get_latest_data_filepath() 
	yesterday = (datetime.date.today() - datetime.timedelta(days = 1)).strftime('%Y%m%d')
	if filepath[len(DATA_FOLDER):][-12:-4] != yesterday:
		print('updating data...')
		scrape_start = utils.shift_dstring(filepath[len(DATA_FOLDER):][-12:-4], 1)
		scraper.main(filepath[len(DATA_FOLDER):][0:8], scrape_start, yesterday, filepath)
		filepath = utils.get_latest_data_filepath()

	data = utils.read_csv(filepath)
	this_sim = sim(data, K_FACTOR, SEASON_CARRY, HOME_ADVANTAGE, stop_short, period)

	if topteams != False:
		output = pd.DataFrame(this_sim.get_top(int(topteams)), columns = ['Team', 'Elo Rating', '%i Day Change' % period])
		output['Point Spread vs. Next Rank'] = ["{0:+.1f}".format(((output['Elo Rating'][i] - output['Elo Rating'][i+1])/ELO_TO_POINTS_FACTOR)) for i in range(topteams - 1)] + ['']
		output['Rank'] = [i for i in range (1, topteams+1)]
		utils.table_output(output, 'Ratings through ' + this_sim.date, ['Rank', 'Team', 'Elo Rating', 'Point Spread vs. Next Rank', '%i Day Change' % period])
			
	return this_sim

def parseArguments():
	parser = argparse.ArgumentParser(description = 'This script allows the user to view the top elo-rated teams at any given time since the start of the 2010 season. The user has the ability to specify the number of top teams to display, and to specify what date they would like to evaluate on')
	parser.add_argument('-t', '--topteams', type = int, default = 25, help = 'Specify how many of the top teams to output. Default is to display the top 25')
	parser.add_argument('-d', '--date', default = '99999999', type = str, help = 'Use to see the top teams as of a date in the past. Enter date as YYYYMMDD (e.g. 20190315). Default is to calculate through the end of the most recent data in the data folder (after an update if the -u flag is used)')
	parser.add_argument('-p', '--period', default = 7, type = int, help = "In the last column of the output, you see each team's change in elo over a period of time. Specify how many days you want that period to be. Default is 7.")
	return parser.parse_args()

if __name__ == '__main__':
	args = parseArguments()
	main(topteams = args.topteams, stop_short = args.date, period = args.period)