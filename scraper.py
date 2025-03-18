import datetime
from bs4 import BeautifulSoup
import utils
import requests

'''
The general strategy for this scraper is to scrape all games this season and their neutral status from teamrankings.com (TR).
Then, scrape scores and odds from scoresandodds.com (SO). Then translate both of these to the common language for all 
historical data: sports-reference.com (SR). Leverage so_sr_mapping.csv to go from SO to SR and sr_tr_mapping.csv for SR to TR.

The functions in this file will scrape from SO day by day for specified date ranges. When updating daily, it only scrapes the
new day and appends it to the end of the master data file.
'''

URLV2 = 'https://www.scoresandodds.com/ncaab?date=YEAR-MONTH-DAY'
DATA_FOLDER = utils.DATA_FOLDER
NEUTRAL_MAP = None #will be set if needed. Maps (team1, team2, date) --> 1/0 depending on if the game is at a neutral site
TR_NAMES = None #tracking this temporarily to see if there are teams with improper mapping in SR to TR
TR_NAMES_MAP = utils.read_two_column_csv_to_dict('Data/sr_tr_mapping.csv') #maps sport reference names (our original source of truth for names) to team rankings names
SR_NAMES_MAP = utils.read_two_column_csv_to_dict('Data/so_sr_mapping.csv') #maps scores & odds names to sports reference names (our original source of truth for names)

def scrape_neutral_data():
	'''
	The sports-reference source for all the scores is no longer accurate at providing neutral/not neutral information
	The site at 'https://www.teamrankings.com/ncb/schedules/season/' provides accurate information for the current season
	The strategy will be to scrape games/scores from sports-reference as usual, but then check the Neutral flag with this new source
	'''
	schedule_url = 'https://www.teamrankings.com/ncb/schedules/season/'
	data = requests.get(schedule_url).content
	table_games_data = BeautifulSoup(data,'html.parser').find_all("tr")
	all_rows = [i.text.split('\n') for i in table_games_data]

	global NEUTRAL_MAP
	NEUTRAL_MAP = {}
	TR_NAMES = set() #set of teams mentioned in TR
	this_date = utils.format_tr_dates(all_rows[0][1])
	for r in all_rows[1:]:
		val = r[1]
		if '@' in val:
			teams = val.split('  @  ')
			NEUTRAL_MAP[(teams[0], teams[1], this_date)] = 0
			TR_NAMES.add(teams[0])
			TR_NAMES.add(teams[1])
		elif 'vs.' in val:
			teams = val.split('  vs.  ')
			NEUTRAL_MAP[(teams[0], teams[1], this_date)] = 1
			TR_NAMES.add(teams[0])
			TR_NAMES.add(teams[1])
		else:
			this_date = utils.format_tr_dates(val)

scrape_neutral_data()

def scrape_scores(date_obj):
	'''
	scrape and return stats in the form of a list of lists where each sublist is information from a single game played on the specified day 
	'''
	day, month, year = str(date_obj.day), str(date_obj.month), str(date_obj.year)
	day_stats = []
	url = URLV2.replace("DAY", day).replace("MONTH", month).replace("YEAR", year)
	response = requests.get(url)
	if response.status_code != 200:
		print(f'ERROR: Response Code {response.status_code}')
	data = response.content

	table_divs = BeautifulSoup(data, 'html.parser').find_all('tbody')
	this_day_string = date_obj.strftime('%Y%m%d')
	print(this_day_string)

	def get_info_from_row(row):
		team = row.find('span', {'class': 'team-name'})
		if team.find('a') == None:
			team = team.find('span').text.strip(' 1234567890()')
		else:
			team = team.find('a').text.strip(' 1234567890()')
		
		if team not in SR_NAMES_MAP:
			print(f"Warning... {team} not found in scores & odds map back to sports reference. {team} will count as a brand new team in the simulation")
		team = SR_NAMES_MAP.get(team, team) #map scores and odds names to sports reference names if it exists

		team_score = row.find('td', {'class': 'event-card-score'})
		if team_score == None or team_score.text.strip() == '0':
			#the game was either canceled or postponed, indicate with an empty string
			return team, ''
		else:
			return team, team_score.text.strip()

	for game in table_divs:
		away_row, home_row = game.find_all('tr')
		away, away_score = get_info_from_row(away_row) #away is now mapped to sports reference names
		home, home_score = get_info_from_row(home_row) #home is now mapped to sports reference names

		#if the game hasn't happened yet, no need to grab spreads from this source. This function will grab source of truth spreads when the games are final
		spread_field = away_row.find('td', {'data-field': 'live-spread'})
		if spread_field == None: away_spread = 'NL'
		else:
			away_span = spread_field.find('span')
			if away_span == None: away_spread = 'NL'
			else: 
				away_spread = away_span.text.strip()  # First strip whitespace
				away_spread = away_spread.replace('+', '')  # Then remove plus sign
				away_spread = 'NL' if away_spread == '' else away_spread

		if away not in TR_NAMES_MAP:
			print(f"Warning... {away} not found in sports reference map to teamrankings. {away} cannot be checked for neutral site game accurately")
		if home not in TR_NAMES_MAP:
			print(f"Warning... {home} not found in sports reference map to teamrankings. {home} cannot be checked for neutral site game accurately")
		
		TR1, TR2 = TR_NAMES_MAP.get(away, away), TR_NAMES_MAP.get(home, home) #TR1 and TR2 are now mapped from sports reference to team rankings names if they exist

		if TR_NAMES != None:
			if TR1 not in TR_NAMES:
				print(f"Warning... {TR1} never appears in teamrankings schedule. The mapping in sr_tr_mapping.csv may be incorrect")
			if TR2 not in TR_NAMES:
				print(f"Warning... {TR2} never appears in teamrankings schedule. The mapping in sr_tr_mapping.csv may be incorrect")

		if (TR1, TR2, this_day_string) in NEUTRAL_MAP:
			n_flag = NEUTRAL_MAP[(TR1, TR2, this_day_string)]
		else:
			n_flag = NEUTRAL_MAP.get((TR2, TR1, this_day_string), 0) #if this other orientation of names isn't there, default to non-neutral (0)

		day_stats.append([n_flag, away, away_score, home, home_score, this_day_string, away_spread])

	return day_stats

def check_for_incomplete(new):
	modified = []
	for i in range(len(new)):
		row = new[i]
		if row[1] != '' and row[2] != '' and row[3] != '' and row[4] != '':
			modified.append(row)

	return modified

def scrape_by_day(file_start, scrape_start, scrape_end, all_data):
	'''
	scrape data from scrape_start to end, append it to all_data, and save this new file as a csv
	file_start: specifies a string to use for save name purposes. This is the date ('YYYYMMDD') on which the data file begins
	scrape_start: different from the file start, this is the date object of the day on which to start scraping new data
	scrape_end: this is the date object specifying what the last day to scrape should be
	all_data: this is a list of all the existing data that the new data will be appended to
	'''
	scrape_neutral_data() #set the NEUTRAL_MAP variable
	new_data = []
	i = scrape_start
	this_month = scrape_start.month
	while i <= scrape_end:
		if i.month in [5, 6, 7, 8, 9, 10]: 
			i += datetime.timedelta(days = 1)
			continue
		new_data.extend(check_for_incomplete(scrape_scores(i)))
		i += datetime.timedelta(days = 1)
		if i.month != this_month:
			this_month = i.month
			print(len(new_data), "games recorded")
			all_data.extend(new_data)
			new_data = []
			utils.save_data(DATA_FOLDER + file_start + "-" + (i - datetime.timedelta(days = 1)).strftime('%Y%m%d') + ".csv", all_data)
	print(len(new_data), "games recorded")
	all_data.extend(new_data)
	utils.save_data(DATA_FOLDER + file_start + "-" + (i - datetime.timedelta(days = 1)).strftime('%Y%m%d') + ".csv", all_data)
	return all_data

def main(file_start, scrape_start, scrape_end, data_filepath = False):
	'''
	performs some preliminary setup work and calls functions to scrape data in the specified date ranges and add it to an already exisiting file of data (if specified)
	file_start: specifies a string to use for save name purposes. This is the date ('YYYYMMDD') on which the data file begins
	scrape_start: different from the file start, this is the date string ('YYYYMMDD') of the day on which to start scraping new data
	scrape_end: this is a string date ('YYYYMMDD') specifying what the last day to scrape should be
	data_filepath: specifies where to find the existing data we want to append new data to. If not specified, the scraped data is saved as a standalone
	'''
	start = datetime.datetime.strptime(scrape_start, "%Y%m%d")
	end = datetime.datetime.strptime(scrape_end, "%Y%m%d")
	if data_filepath != False:
		all_data = utils.read_csv(data_filepath)
		if all_data[-1][5] >= scrape_end:
			print('data already updated')
			return
	else:
		all_data = []
	scrape_by_day(file_start, start, end, all_data)