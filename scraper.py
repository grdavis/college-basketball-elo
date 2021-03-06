import datetime
import csv
from selenium import webdriver
from bs4 import BeautifulSoup
import utils

URL = 'https://www.sports-reference.com/cbb/boxscores/index.cgi?month=MONTH&day=DAY&year=YEAR'
DATA_FOLDER = utils.DATA_FOLDER

def new_driver():
	'''
	return a new healdless chrome webdriver
	'''
	chrome_options = webdriver.ChromeOptions()  
	chrome_options.add_argument("--headless")
	return webdriver.Chrome(options = chrome_options)

def get_chrome_data(url, driver):
	'''
	given a driver object, retrieve the page source of the specified url
	'''
	driver.get(url)
	return driver.page_source

def scrape_scores(date_obj, driver):
	'''
	scrape and return stats in the form of a list of lists where each sublist is information from a single game played on the specified day 
	'''
	day, month, year = str(date_obj.day), str(date_obj.month), str(date_obj.year)
	day_stats = []
	url = URL.replace("DAY", day).replace("MONTH", month).replace("YEAR", year)
	data = get_chrome_data(url, driver)
	table_divs = BeautifulSoup(data,'html.parser').find_all("div", {'class': 'game_summary'})
	this_day_string = date_obj.strftime('%Y%m%d')
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

def scrape_by_day(file_start, scrape_start, scrape_end, all_data):
	'''
	scrape data from scrape_start to end, append it to all_data, and save this new file as a csv
	file_start: specifies a string to use for save name purposes. This is the date ('YYYYMMDD') on which the data file begins
	scrape_start: different from the file start, this is the date object of the day on which to start scraping new data
	scrape_end: this is the date object specifying what the last day to scrape should be
	all_data: this is a list of all the existing data that the new data will be appended to
	'''
	driver = new_driver()
	new_data = []
	i = scrape_start
	this_month = scrape_start.month
	while i <= scrape_end:
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
			utils.save_data(DATA_FOLDER + file_start + "-" + (i - datetime.timedelta(days = 1)).strftime('%Y%m%d') + ".csv", all_data)
	print(len(new_data), "games recorded")
	all_data.extend(new_data)
	utils.save_data(DATA_FOLDER + file_start + "-" + (i - datetime.timedelta(days = 1)).strftime('%Y%m%d') + ".csv", all_data)
	driver.quit()
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
		if all_data[-1][-1] >= scrape_end:
			print('data already updated')
			return
	else:
		all_data = []
	scrape_by_day(file_start, start, end, all_data)