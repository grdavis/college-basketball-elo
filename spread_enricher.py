import utils
from os import listdir
import csv
import pandas as pd
from fuzzywuzzy import fuzz, process
import requests
from bs4 import BeautifulSoup
from datetime import datetime

def scrape_live_odds():
	'''
	This function scrapes and returns the current spreads for college basketball games posted on DraftKings
	'''
	url = "https://sportsbook.draftkings.com/leagues/basketball/88670771"
	data = requests.get(url).content
	table = BeautifulSoup(data, 'html.parser').find_all('tbody', {'class': 'sportsbook-table__body'})
	rows = []
	for t in table:
		rows.extend(t.find_all('tr'))
	home = False
	all_data = []
	today = datetime.now()
	for row in rows:
		team = row.find('div', {'class': 'event-cell__name-text'}).text
		if home:
			all_data.append(new_data + [team, today.date().strftime('%Y%m%d'), today.time().strftime('%H%M%S')])
		else:
			spread = row.find('span', {'class': 'sportsbook-outcome-cell__line'})
			new_data = [team, spread.text if spread != None else 'NL']
		home = not home
	utils.save_data('New_Spreads/DK_spreads_%s_%s.csv' % (today.date().strftime('%Y%m%d'), today.time().strftime('%H%M%S')), all_data)
	return all_data, today

def add_spreads_to_todays_preds(predictions, forecast_date):
	'''
	This function is used to enrich game predictions with live spread data from DraftKings. If trying to
	forecast for a date in the future or the past, the latest live spreads from DK are not relevant/available.
	In that situation, this prints a warning and puts 'NL' in for all live spreads. If it is the day of the
	predictions, this uses fuzzy matching techniques to match games with their DK spreads. If the match doesn't
	meet a certain threshold, input 'NL' for "No Line".

	This function is only meant to enrich a specific day's predictions. Actual spreads get incorporated into the
	master data with the function add_historical_spreads() in an ad-hoc fashion.
	'''
	if forecast_date != datetime.today().date():
		print('Live spreads only available when making predictions on the day of the event')
		return [row[:4] + ['NL'] + row[4:] for row in predictions], "N/A"

	todays_spreads, timestamp = scrape_live_odds()
	spreads_map = {}
	for t in todays_spreads:
		spreads_map[t[0] + " " + t[2]] = t

	new_data = []
	for row in predictions:
		teamindex = row[1] + " " + row[4]
		best_match = process.extractOne(teamindex, spreads_map.keys(), scorer = fuzz.token_set_ratio)
		spread = (spreads_map[best_match[0]][1]).replace('+', '')
		score = best_match[1]
		if score >= 80:
			new_data.append(row[:4] + [spread] + row[4:])
		else:
			# print(teamindex, best_match)
			new_data.append(row[:4] + ['NL'] + row[4:])

	return new_data, timestamp

def add_historical_spreads():
	'''
	This is a one-off-use function to populate spreads for historical games already in the core data.
	Using the historical spread data from https://www.sportsbookreviewsonline.com/scoresoddsarchives/ncaabasketball/ncaabasketballoddsarchives.htm,
	enrich the latest data with a new column representing the closing line spread for the away team. If a spread cannot be found, writes 'NL'

	Requires downloading xlsx files from the site, moving it to the spreads folder, and saving it as a .csv. If running in the middle of the 
	latest season, note that the xlsx files will not have all the latest data ready (e.g. running on 1/30, this season's xlsx file doesn't have 
	spreads for 1/24-1/30 yet).

	Requires a manual check at the end. Saves the enriched data with a "t" prefix. Manually confirm it worked as expected before removing the "t"
	and overwriting the latest data file
	'''
	SPREAD_FOLDER = 'Old_Spreads/'
	filepath = utils.get_latest_data_filepath() 
	data = utils.read_csv(filepath)
	filenames = listdir(SPREAD_FOLDER)

	spread_data = {}
	for f in ['ncaa basketball 2021-22.csv']: #in filenames: #comment out filenames and provide a subset list of filenames if needed
		if f == '.DS_Store': continue
		print(f)
		raw = utils.read_csv(SPREAD_FOLDER + f)
		for r_index in range(1, len(raw), 2):
			one, two = raw[r_index][8], raw[r_index+1][8]
			if one == 'pk' or one == 'PK': one = 0
			if two == 'pk' or two == 'PK': two = 0
			one = float(one) if one not in ['NL', ''] else 1001
			two = float(two) if two not in ['NL', ''] else 1000
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
			new_data.append(row) # change to new_data.append(row[:6] + ['NL']) if seeding for the first time
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
			new_data.append(row[:6] + [sp])

	#doesn't overwrite the latest data, requires a manual check and overwrite afterwards
	utils.save_data(filepath.replace('/', '/t'), new_data)

# add_historical_spreads()
