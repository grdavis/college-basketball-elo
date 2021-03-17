# college-basketball-elo
intro
Implementing an Elo rating system for Men's NCAA Basketball
2010-today

### Usage
There are several ways to use this program. They are organized into two scripts, each with several optional inputs to control functionality.
#### elo.py
This script allows you to view the top elo-rated teams at any given time since the start of the 2010 season. In addition to specifying the historical date of interest, you also have the ability to control multiple aspects of the output with optional arguments.
```
python3 elo.py
```
By default, the script will:
1. Refresh data through games completed yesterday
2. Calculate the latest team Elo ratings
3. Open a Plotly table displaying the top 25 teams, their Elo ratings, and their change in rating from 7 days earlier. Also a part of the table is _Point Spread vs. Next Rank_. This indicates by how many points a team would be favored over the next team in the rankings. In the example below, Gonzaga would be a 4.0 favorite over Illinois, Illinois a 1.1 point favorite over Baylor, Baylor a 2.7 point favorite over Iowa, and so on.
![alt text](https://github.com/grdavis/college-basketball-elo/blob/main/Images/default_elo_output.png?raw=true)

The script can be run with the following options:
  * `-h` or `--help`: Displays the help messages for this script
  * `-t` or `--topteams`: Specify with an integer how many of the top teams to output. The default is to display the top 25
  * `-d` or `--date`: Use to see the top teams as of a date in the past. Enter date as a YYYYMMDD integer (e.g. 20190320). The default is to calculate through the last game in the most recent data
  * `-p` or `--period`: The default is to display the Elo ratings change over the last 7 days in the table. Specify an integer number of days to use for that column instead of 7

### How it Works

### Methodology and Performance
