import csv
import re
import os
import plotly.graph_objects as go
from datetime import datetime, timedelta

DATA_FOLDER = 'Data/'
OUTPUTS_FOLDER = 'Outputs/'
SPREAD_FOLDER = 'New_Spreads/'

def save_data(filepath, data):
	with open(filepath, "w") as f:
		wr = csv.writer(f)
		for row in data:
			wr.writerow(row)

def read_csv(filepath):
	with open(filepath, encoding = 'utf-8-sig') as csvfile:
		return list(csv.reader(csvfile))

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
	r = re.compile(".*Predictions.*.csv")
	elligible_data = list(filter(r.match, os.listdir(OUTPUTS_FOLDER)))
	sorted_files = sorted(elligible_data, key = lambda x: os.path.getmtime(os.path.join(OUTPUTS_FOLDER, x)), reverse = True)
	remove_files([OUTPUTS_FOLDER + f for f in sorted_files], 3)

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