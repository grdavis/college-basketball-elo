import datetime
from bs4 import BeautifulSoup
import utils
import requests

schedule_url = 'https://www.teamrankings.com/ncb/schedules/season/'
data = requests.get(schedule_url).content

table_games_data = BeautifulSoup(data,'html.parser').find_all("tr")
all_rows = [i.text.split('\n') for i in table_games_data]

cleaned_rows = []
this_date = all_rows[0][1]
for r in all_rows[1:]:
	val = r[1]
	if '@' in val:
		teams = val.split('  @  ')
		cleaned_rows.append([0, teams[0], teams[1], this_date])
	elif 'vs.' in val:
		teams = val.split('  vs.  ')
		cleaned_rows.append([1, teams[0], teams[1], this_date])
	else:
		this_date = val

utils.save_data('temp2.csv', cleaned_rows)