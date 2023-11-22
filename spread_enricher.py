import utils
import pandas as pd
from fuzzywuzzy import fuzz, process
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from scraper import scrape_scores

def scrape_live_odds():
	'''
	This function scrapes and returns the current spreads for college basketball games posted on Scores and Odds
	DraftKings was the original source, but they altered their page to make it more difficult than needed
	'''
	url = "https://www.scoresandodds.com/ncaab"

	data = requests.get(url).content
	games = BeautifulSoup(data, 'html.parser').find_all('tbody')
	all_data = []
	today = datetime.now()
	for game in games:
		away_row, home_row = game.find_all('tr')
		away = away_row.find('span', {'class': 'team-name'})
		if away.find('a') == None:
			away = away.find('span').text.strip(' 1234567890()')
		else:
			away = away.find('a').text.strip(' 1234567890()')

		odds_obj = away_row.find('div', {'class': 'game-odds'})
		away_spread = 'NL' if odds_obj == None else odds_obj.find('span').text.replace('+', '')

		home = home_row.find('span', {'class': 'team-name'})
		if home.find('a') == None:
			home = home.find('span').text.strip(' 1234567890()')
		else:
			home = home.find('a').text.strip(' 1234567890()')

		all_data.append([away, away_spread, home, today.date().strftime('%Y%m%d'), today.time().strftime('%H%M%S')])
	
	utils.save_data('New_Spreads/SO_spreads_%s_%s.csv' % (today.date().strftime('%Y%m%d'), today.time().strftime('%H%M%S')), all_data)
	return all_data, today

def add_spreads_to_todays_preds(predictions, forecast_date):
	'''
	This function is used to enrich game predictions with live spread data. If trying to
	forecast for a date in the future or the past, the latest live spreads are not relevant/available.
	In that situation, this prints a warning and puts 'NL' in for all live spreads. If it is the day of the
	predictions, this uses fuzzy matching techniques to match games with their scraped spreads. If the match doesn't
	meet a certain threshold, input 'NL' for "No Line".

	Since these spreads are scraped directly from a site, they may be more volatile than those scraped from our 
	official scrape source. Thus, these spreads are only displayed in predictions output and not stored long-term
	'''
	if forecast_date != datetime.today().date():
		print('Accurate spreads only available when making predictions on the day of the event')
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
			new_data.append(row[:4] + ['NL'] + row[4:])

	return new_data, timestamp

def add_historical_spreads(start_date_str, last_date_str, scrape_needed = True):
	'''
	This is a one-off use function attempting to make up for our previous source for historical 
	spreads going down (https://github.com/grdavis/college-basketball-elo/issues/10)
	Takes in start_date_str and last_date_str in format YYYYMMDD (e.g. 20231102)
	The approach here will be to scrape scores and spreads from our new source (https://www.scoresandodds.com/ncaab)
	and match them with the existing games in our dataset based on the game date, score, and team name fuzzy match
	'''
	date_obj, last_date_obj = datetime.strptime(start_date_str, "%Y%m%d"), datetime.strptime(last_date_str, "%Y%m%d")
	filepath = f'{utils.DATA_FOLDER}add_historical_spreads_{start_date_str}_{last_date_str}.csv'
	
	#if we haven't already scraped the data for the relevant time period, scrape that now. Otherwise, just load the file
	if scrape_needed:
		historical_data = []
		iterations = 0
		while date_obj <= last_date_obj:
			iterations += 1
			historical_data.extend(scrape_scores(date_obj))
			date_obj += timedelta(days = 1)
			
			#save progress every 30 scraped days
			if iterations == 30:
				iterations = 0
				utils.save_data(f"{utils.DATA_FOLDER}add_historical_spreads_{start_date_str}_{date_obj.strftime('%Y%m%d')}.csv", historical_data)
		
		#final data save
		utils.save_data(filepath, historical_data)

	#for games in the existing game data, find those where the spread is 'NL' and the date is on or after start_date_str
	latest_filepath = utils.get_latest_data_filepath()
	full_df = pd.read_csv(latest_filepath, names = ['N', 'AWAY', 'AWAY_SCORE', 'HOME', 'HOME_SCORE', 'DATE', 'AWAY_SPREAD'])
	latest_df = full_df.loc[(full_df['DATE'] >= int(start_date_str)) & (full_df['AWAY_SPREAD'] == 'NL')]
	historical_df = pd.read_csv(filepath, names = ['N', 'AWAY', 'AWAY_SCORE', 'HOME', 'HOME_SCORE', 'DATE', 'AWAY_SPREAD'])
	print(f"Found {latest_df.shape[0]} games without lines on or after {start_date_str}")
	
	#for each game (X) in this list of games
	#trim our historical spreads to just games with the same date, away score, and home score as X
	#if there is only one match, assign it as the correct spread in the full_df
	matched_counter = 0
	for index, row in latest_df.iterrows():
		thdf = historical_df.loc[(historical_df['DATE'] == row['DATE']) & (historical_df['AWAY_SCORE'] == row['AWAY_SCORE']) & (historical_df['HOME_SCORE'] == row['HOME_SCORE'])].reset_index()

		if thdf.shape[0] == 0: 
			full_df.loc[index, 'AWAY_SPREAD'] = 'NL'
			continue
		
		if thdf.shape[0] == 1: 
			full_df.loc[index, 'AWAY_SPREAD'] = thdf.iloc[0]['AWAY_SPREAD'] if thdf.iloc[0]['AWAY_SPREAD'][0] != '+' else thdf.iloc[0]['AWAY_SPREAD'][1:]
			matched_counter += 1
			continue

		thdf['hist_index'] = thdf.apply(lambda x: ((x['AWAY'] + x['HOME']).replace(' ', ''), x['AWAY_SPREAD'], x['DATE']), axis = 1)
		possible_matches = list(thdf['hist_index'])

		#calculate how close the team names match for every game in the historical spread data where the scores match
		this_index = (row['AWAY'] + row['HOME']).replace(' ', '')
		best = (fuzz.ratio(possible_matches[0][0], this_index), possible_matches[0][1])
		for poss in possible_matches[1:]:
			new_ratio = fuzz.ratio(poss[0], this_index)
			if new_ratio > best[0]:
				best = (new_ratio, poss[1])

		#assign the best-scored match
		full_df.loc[index, 'AWAY_SPREAD'] = best[1] if best[1][0] != '+' else best[1][1:]
		matched_counter += 1

		#manually check over the games where even the best match was uncertain
		#confirm that the selected spread aligned with the spread in the correct game in the list
		if best[0] < 70:
			print(this_index, row['DATE'], best) # <- game we are trying to match to a spread, (match score, selected spread)
			print(possible_matches) # <- list of possible games/spread to match it with - NOT IN MATCH SCORE ORDER

	full_df.to_csv(latest_filepath.replace('/', '/temp_'), index = False, header = False)
	print(f"Matched {matched_counter} games")
	
# add_historical_spreads('20230101', '20230403', scrape_needed = False)
