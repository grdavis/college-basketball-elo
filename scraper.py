import datetime
import csv
from selenium import webdriver
from bs4 import BeautifulSoup
import utils

URL = 'https://www.sports-reference.com/cbb/boxscores/index.cgi?month=MONTH&day=DAY&year=YEAR'
DATA_FOLDER = utils.DATA_FOLDER

def new_driver():
	chrome_options = webdriver.ChromeOptions()  
	chrome_options.add_argument("--headless")
	return webdriver.Chrome(options = chrome_options)

def get_chrome_data(url, driver):
	driver.get(url)
	return driver.page_source

def fix_dates_for_data(date_obj):
	#make sure dates are in the format: 20210130
	new_month = str(date_obj.month) if len(str(date_obj.month)) == 2 else "0" + str(date_obj.month)
	new_day = str(date_obj.day) if len(str(date_obj.day)) == 2 else "0" + str(date_obj.day)
	return str(date_obj.year) + new_month + new_day 

def scrape_scores(date_obj, driver):
	#scrape the scores from a single day
	day, month, year = str(date_obj.day), str(date_obj.month), str(date_obj.year)
	day_stats = []
	url = URL.replace("DAY", day).replace("MONTH", month).replace("YEAR", year)
	data = get_chrome_data(url, driver)
	table_divs = BeautifulSoup(data,'html.parser').find_all("div", {'class': 'game_summary'})
	this_day_string = fix_dates_for_data(date_obj)
	print(this_day_string)
	for div in table_divs:
		tables = div.find('tbody')
		rows = tables.find_all('tr')
		stats = [1 if len(rows) == 3 else 0]
		for row in rows[:2]:
			datapts = row.find_all('td')[:2]
			stats.append(datapts[0].find('a').text)
			stats.append(datapts[1].text)
		day_stats.append(stats + [this_day_string])
	return day_stats

def scrape_by_day(file_start, scrape_start, end, all_data):
	driver = new_driver()
	new_data = []
	i = scrape_start
	this_month = scrape_start.month
	while i <= end:
		if i.month in [5, 6, 7, 8, 9, 10]: 
			i += datetime.timedelta(days = 1)
			continue
		new_data.extend(scrape_scores(i, driver))
		i += datetime.timedelta(days = 1)
		if i.month != this_month:
			this_month = i.month
			print(len(new_data), "games recorded")
			all_data.extend(new_data)
			new_data = []
			utils.save_data(DATA_FOLDER + file_start + "-" + fix_dates_for_data(i - datetime.timedelta(days = 1)) + ".csv", all_data)
	print(len(new_data), "games recorded")
	all_data.extend(new_data)
	utils.save_data(DATA_FOLDER + file_start + "-" + fix_dates_for_data(i - datetime.timedelta(days = 1)) + ".csv", all_data)
	driver.quit()
	return all_data

def main(file_start, scrape_start, scrape_end, data_filepath = False):
	#assumes data formats used throughout are YYYYMMDD
	#scrapes from scrape_start through scrape_end and appends results to provided data_filepath
	#file_start is used for naming purposes as the start of data_filepath may be different from scrape_start
	start = datetime.datetime.strptime(scrape_start, "%Y%m%d")
	end = datetime.datetime.strptime(scrape_end, "%Y%m%d")
	if data_filepath != False:
		all_data = utils.read_csv(data_filepath)
		if all_data[-1][-1] >= scrape_end:
			print('data already updated')
			return
	else:
		all_data = []
	scrape_by_day(file_start, start, end, all_data)