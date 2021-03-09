import numpy as np
from tqdm import tqdm
from elo import sim
from scraper import read_csv
import random

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
		error1, error2 = sim(data, k_factor, new_season_carry, home_elo).get_errors()
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
				error1, error2 = sim(data, k, c, h).get_errors()
				errors.append((error1, error2, k, c, h))

	return errors

def main(filepath):
	data = read_csv(filepath)

	#start with random_tune, then switch to brute_tune when the ranges for values are tight enough so as not to take too long to run
	errors = random_tune(data, 5)
	# errors = brute_tune(data)
	
	print(sorted(errors, key = lambda x: x[0]))
	print(sorted(errors, key = lambda x: x[1]))

if __name__ == '__main__':
	pass

# start measuring after season 3
# best: (6787.1710585282635, 0.010835972134262182, 47, 1, 83)