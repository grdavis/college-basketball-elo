import utils
from os import listdir
import csv
import pandas as pd
from fuzzywuzzy import fuzz

def add_historical_spreads():
	'''
	Using the historical spread data from https://www.sportsbookreviewsonline.com/scoresoddsarchives/ncaabasketball/ncaabasketballoddsarchives.htm,
	enrich the latest data with a new column representing the closing line spread for the away team. If a spread cannot be found, writes 'NL'

	Requires downloading xlsx files from the site, moving it to the spreads folder, and saving it as a .csv. If running in the middle of the 
	latest season, note that the xlsx files will not have all the latest data ready (e.g. running on 1/30, the xlsx file doesn't have spreads 
	for 1/24-1/30 yet).
	'''
	SPREAD_FOLDER = 'Spreads/'
	filepath = utils.get_latest_data_filepath() 
	data = utils.read_csv(filepath)
	filenames = listdir(SPREAD_FOLDER)

	spread_data = {}
	for f in filenames:
		if f == '.DS_Store': continue
		print(f)
		raw = utils.read_csv(SPREAD_FOLDER + f)
		for r_index in range(1, len(raw), 2):
			one, two = raw[r_index][8], raw[r_index+1][8]
			if one == 'pk' or one == 'PK': one = 0
			if two == 'pk' or two == 'PK': two = 0
			one = float(one) if one not in ['NL', ''] else 1000
			two = float(two) if two not in ['NL', ''] else 1001
			sp = -one if one < two else two
			date = raw[r_index][0] if len(raw[r_index][0]) == 4 else "0" + raw[r_index][0]
			year = f[-11:-7] if int(date[:2]) > 6 else '20' + f[-6:-4]
			numindex = year + date + raw[r_index][6] + raw[r_index+1][6]
			teamindex = raw[r_index][3] + raw[r_index+1][3]
			spread_data[numindex] = spread_data.get(numindex, []) + [(teamindex, sp)]

	new_data = []
	for row in data:
		numindex = row[5] + row[2] + row[4]
		if numindex not in spread_data:
			new_data.append(row + ['NL'])
		else:
			if len(spread_data[numindex]) == 1:
				sp = spread_data[numindex][0][1]
			else:
				teamindex = (row[1] + row[3]).replace(' ', '')
				best = (fuzz.ratio(spread_data[numindex][0][0], teamindex), spread_data[numindex][0][1])
				for poss in spread_data[numindex][1:]:
					new_ratio = fuzz.ratio(poss[0], teamindex)
					if new_ratio > best[0]:
						best = (new_ratio, poss[1])
				if best[0] < 50:
					#manually check over the games where the match was uncertain
					print(numindex, spread_data[numindex])
					print(teamindex, best)
				sp = best[1]
			sp = sp if sp < 1000 else 'NL'
			new_data.append(row + [sp])

	#doesn't overwrite the latest data, requires a manual check and overwrite afterwards
	utils.save_data(filepath.replace('/', '/t'), new_data)



		