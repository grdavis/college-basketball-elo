import csv
import re
import os
import plotly.graph_objects as go
from datetime import datetime, timedelta

DOCS_FOLDER = 'docs/'
DATA_FOLDER = 'Data/'
OUTPUTS_FOLDER = 'Outputs/'
SPREAD_FOLDER = 'New_Spreads/'

# Dynamically determine the current basketball season start year
# Basketball seasons start in November, so:
# - If current month is Nov-Dec, season start is current year
# - If current month is Jan-Oct, season start is previous year
_current_date = datetime.now()
_current_year = _current_date.year
_current_month = _current_date.month
SEASON_START = _current_year if _current_month >= 11 else _current_year - 1

MO_MAP = {'Nov': '11', 'Dec': '12', 'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04'}
YR_MAP = {'Nov': SEASON_START, 'Dec': SEASON_START, 'Jan': SEASON_START+1, 'Feb': SEASON_START+1, 'Mar': SEASON_START+1, 'Apr': SEASON_START+1}

def save_data(filepath, data):
	with open(filepath, "w") as f:
		wr = csv.writer(f)
		for row in data:
			wr.writerow(row)

def read_csv(filepath):
	with open(filepath, encoding = 'utf-8-sig') as csvfile:
		return list(csv.reader(csvfile))

def read_two_column_csv_to_dict(filepath):
	this_dict = {}
	with open(filepath, 'r', encoding = 'utf-8-sig') as csvfile:
		for line in csv.reader(csvfile):
			this_dict[line[0]] = line[1]
	return this_dict

def format_tr_dates(date_string):
	'''
	takes in a string like 'Mon Nov  7' and converts it to '20221107' format
	'''
	ret_string = date_string[4:]
	day_part = ret_string[4:]
	day_part = day_part if day_part[0] != ' ' else '0' + day_part[1]
	month_part = MO_MAP[ret_string[:3]]
	year_part = str(YR_MAP[ret_string[:3]])
	return year_part + month_part + day_part

def shift_dstring(day_string, days):
	'''
	take in a string in the format YYYYMMDD and return it shifted the specified number of days (could be positive or negative days)
	'''
	return (datetime.strptime(day_string, "%Y%m%d") + timedelta(days = days)).strftime('%Y%m%d')

def get_latest_data_filepath():
	'''
	searches the data folder and returns the most recent data
	'''
	r = re.compile("[0-9]{8}-[0-9]{8}.csv")
	elligible_data = list(filter(r.match, os.listdir(DATA_FOLDER)))
	return DATA_FOLDER + sorted(elligible_data, key = lambda x: x[9:17], reverse = True)[0]

def remove_files(to_remove, k):
	'''
	Deletes all but the first k files provided in to_remove. Assuming to_remove is sorted chronologically,
	this removes all but the most recent k files
	'''
	if len(to_remove) > k:
		for f in to_remove[k:]:
			os.remove(f)

def clean_up_old_outputs_and_data():
	'''
	Goes through the outputs, data, and spreads folders to remove all but the 3 latest files. The files are
	really only saved for debugging purposes anyways, so no need to have so much extra data.
	'''
	#DATA
	r = re.compile("[0-9]{8}-[0-9]{8}.csv")
	elligible_data = list(filter(r.match, os.listdir(DATA_FOLDER)))
	sorted_files = sorted(elligible_data, key = lambda x: x[9:17], reverse = True)
	remove_files([DATA_FOLDER + f for f in sorted_files], 3)

	#SPREADS
	r = re.compile(".*.csv")
	elligible_data = list(filter(r.match, os.listdir(SPREAD_FOLDER)))
	sorted_files = sorted(elligible_data, key = lambda x: x[11:19] + x[20:26], reverse = True)
	remove_files([SPREAD_FOLDER + f for f in sorted_files], 3)

	#OUTPUTS
	r = re.compile(".*Game Predictions.*.csv")
	elligible_data = list(filter(r.match, os.listdir(OUTPUTS_FOLDER)))
	sorted_files = sorted(elligible_data, key = lambda x: x[:8], reverse = True)
	remove_files([OUTPUTS_FOLDER + f for f in sorted_files], 3)

def save_markdown_df(predictions, top_50, date_str):
	'''
	Takes in a predictions dataframe of today's predictions and a table with the top 50 team rankings
	Converts tables to markdown, and saves them in the same file in the docs folder for GitHub pages to find
	'''
	with open(f"{DOCS_FOLDER}/index.md", 'w') as md:
		md.write(f'# NCAAM ELO Game Predictions for {date_str} - @grdavis\n')
		md.write("Below are predictions for today's Men's college basketball games using an ELO rating methodology. Check out the full [college-basketball-elo](https://github.com/grdavis/college-basketball-elo) repository on github to see methodology and more.\n\n")
		md.write("Note: Teams with * or those written as abbreviations (e.g. BREC) are likely new to the model (i.e. they haven't played any/many D1 games) and predictions are more uncertain.\n\n")
		predictions.to_markdown(buf = md, index = False)
		md.write('\n\n')
		md.write('# Top 50 Teams by ELO Rating\n')
		top_50.index = top_50.index + 1
		top_50.to_markdown(buf = md, index = True)

def table_output(df, table_title, order = None):
	'''
	saves the specified dataframe as a csv and outputs it in the form of a Plotly table
	df: dataframe to structure in the form of a plotly table for .html output
	table_title: title used in table
	order: optional list of strings that specifies an order the columns should be presented in
	'''
	if order != None:
		df = df[order]
	df.to_csv(OUTPUTS_FOLDER + table_title + '.csv', index = False)
	fig = go.Figure(data=[go.Table(
	    header=dict(values=list(df.columns),
	                fill_color='paleturquoise',
	                align='left'),
	    cells=dict(values=[df[col].to_list() for col in list(df)],
	               # fill_color='lavender',
	               align='left'))
	])
	fig.update_layout(title = {'text': table_title, 'xanchor': 'center', 'x': .5})
	fig.show()