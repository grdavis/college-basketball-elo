import csv
import scraper

ELO_BASE = 1500
NEW_ELO = 1050
ERRORS_START = 4
K_FACTOR = 47
SEASON_CARRY = 1.0
HOME_ADVANTAGE = 83

class Team():
	def __init__(self, name, starting_elo):
		self.name = name
		self.elo = starting_elo

	def update_elo(self, change):
		self.elo = max(0, self.elo + change)

class ELO_Sim():
	def __init__(self):
		self.teams = {}
		self.error1 = 0
		self.predict_tracker = {}
		self.win_tracker = {}
		self.season_count = 0

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

	def update_errors(self, w_winp):
		if self.season_count >= ERRORS_START:
			self.error1 += (1 - w_winp)**2
			self.win_tracker[round(w_winp, 2)] = self.win_tracker.get(round(w_winp, 2), 0) + 1
			self.predict_tracker[round(w_winp, 2)] = self.predict_tracker.get(round(w_winp, 2), 0) + 1
			self.predict_tracker[round(1-w_winp, 2)] = self.predict_tracker.get(round(1-w_winp, 2), 0) + 1

	def get_top(self, x):
		return sorted([(self.teams[team].name, round(self.teams[team].elo, 2)) for team in self.teams], key = lambda x: x[1], reverse = True)[:x]

	def print_predict_tracker(self):
		for i in sorted(self.predict_tracker):
			result = self.win_tracker.get(i, 0)/self.predict_tracker[i]
			print(i, result)

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

def sim(data, k_factor, new_season_carry, home_elo, stop_short = False, performance_tracker = False, top_x = False):
	this_sim = ELO_Sim()
	this_month = data[0][-1][4:6]

	for row in data:
		if row[-1] == stop_short: break
		row_month = int(row[-1][4:6])
		if this_month == 4 and row_month == 11:
			this_sim.season_count += 1
			this_sim.season_reset(new_season_carry)
		this_month = row_month
		step_elo(this_sim, row, k_factor, home_elo)
	
	if top_x: print(this_sim.get_top(top_x))
	if performance_tracker: this_sim.print_predict_tracker()

	return this_sim

def main(filepath, stop_short = False, performance_tracker = False, top_x = False):
	data = scraper.read_csv(filepath)
	this_sim = sim(data, K_FACTOR, SEASON_CARRY, HOME_ADVANTAGE, stop_short = stop_short, performance_tracker = performance_tracker, top_x = top_x)
	return this_sim

if __name__ == '__main__':
	main('', top_x = 25)

