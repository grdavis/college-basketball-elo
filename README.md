[![daily-predictions](https://github.com/grdavis/college-basketball-elo/actions/workflows/daily_predictions.yml/badge.svg)](https://github.com/grdavis/college-basketball-elo/actions/workflows/daily_predictions.yml)
[![weekly-rankings](https://github.com/grdavis/college-basketball-elo/actions/workflows/weekly_rankings.yml/badge.svg)](https://github.com/grdavis/college-basketball-elo/actions/workflows/weekly_rankings.yml)
# college-basketball-elo
### [Latest Daily Predictions](https://grdavis.github.io/college-basketball-elo/)
Inspired by the folks at [FiveThirtyEight](https://fivethirtyeight.com/) who leverage [Elo rating systems](https://en.wikipedia.org/wiki/Elo_rating_system) to make their [NBA](https://projects.fivethirtyeight.com/2021-nba-predictions/) and [NFL](https://projects.fivethirtyeight.com/2020-nfl-predictions/) predictions, I created my own version of the Elo rating system for NCAA Men's College Basketball. You can use scripts in this repository to see team ratings, predict individual games, predict tournaments, or even simulate entire tournaments thousands of times as of any date in the last 14 years. This documentation walks through usage, methodology, tuning, and performance.

This version of the Elo rating system is primarily based on FiveThirtyEight's [NBA methodology](https://fivethirtyeight.com/features/how-we-calculate-nba-elo-ratings/) with some tuning adjustments. Game log data goes back to the start of the 2010 season. [Sports Reference](https://www.sports-reference.com/cbb/) was the data source through the 22-23 season, but has been switched to [Scores and Odds](https://www.scoresandodds.com/ncaab) to start the 23-24 season. Similarly, historical spreads data came from [SportsBookReviewsOnline](https://www.sportsbookreviewsonline.com/scoresoddsarchives/ncaabasketball/ncaabasketballoddsarchives.htm) through the 22-23 season, but will come from Scores and Odds moving forward. 

Using GitHub Actions, every morning, `predictions.py` is run to make predictions for that day's college basketball games. In addition to the Elo model's spread predictions, the output is also enriched by scraping the latest spreads from [Scores and Odds](https://www.scoresandodds.com/ncaab). Another workflow runs every Monday during the season to produce a top 50 ranking of teams. The outputs of both of these workflows can be found in the [Outputs](https://github.com/grdavis/college-basketball-elo/tree/main/Outputs) folder.

## Usage
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

#### predictions.py
This script allows you to make a number of different types of predictions using the Elo model. You can predict all scheduled games on a future day, ad-hoc individual matchups, populate a traditional bracket with picks, or simulate a tournament to get each team's chances of making it to each round. Similar to elo.py, you have the option to specify a historical date of interest along with a number of other options depending on the desired functionality.

###### Example 1
```
python3 predictions.py -F '20210327'
```
This example demonstrates the default functionality of the script. This will return predictions for all games scheduled according to [Scores and Odds](https://www.scoresandodds.com/ncaab) on the date specified date with the `-F` flag. If no date is specified (`python3 predictions.py`) predictions will be made based on today's schedule. The output is a Plotly table showing each matchup, each team's win probability, and predicted spread. There is also an indicator for whether or not the game is played at a neutral site as sourced from [TeamRankings](https://www.teamrankings.com/ncb/schedules/season/). If the specified date is not today, the output will not have any information in the live spreads column. The output tables are saved in the `Outputs` folder as a csv for further examination. Running this script before 3/27/2021, we can use the latest version of the model to predict the outcomes of games scheduled for that day:
![alt text](https://github.com/grdavis/college-basketball-elo/blob/main/Images/future_game_predictions.png?raw=true)
You can also quickly see what the model would have picked for all games on a day in the past by setting `-F` to the date of the games and `-d` to the date on which the predictions would have been made. This is how you can quickly see what the model would have picked for every game on 3/22/2021 based on what we knew through 3/21/2021:
```
python3 predictions.py -F '20210322' -d '20210321'
```

###### Example 2
```
python3 predictions.py -G 'UConn' 'Maryland' -n
```
In this example we want to predict the result of the first round matchup in the 2021 NCAA Tournament between UConn and Maryland. No date is specified, so the model will update the data through games completed yesterday and simulate as if this game is played tomorrow (which it is at the time of writing). The `-n` flag indicates the game is played at a neutral site, so no home-court advantage is applied to UConn. This returns that UConn is favored by 2.5 points (Vegas says 3):
```
Ratings through 20210319
UConn vs. Maryland @ neutral site
UConn 59% -2.5 Maryland 41% 2.5
```
The advantage of this use over the default `predictions.py` functionality is you can predict the results of a hypothetical matchup or one that is not scheduled on our games data source yet.

###### Example 3
```
python3 predictions.py -P 'Data/tournament_results_2021.csv' -m 1
```
In this example, we want the model to predict the outcomes of a tournament with the matchups specified in `tournament_results_2021.csv` by selecting the team it thinks is most likely to win each of the 63 games in a traditional March Madness tournament. `tournament_results_2021.csv` must have a power of 2 (e.g. 64, 32, 128) team names in its first column in matchup order. Row 1 plays row 2. The winner of that matchup plays the winner of row 3 vs. row 4, and so on until there is only 1 team remaining. It does not matter what is actually in `tournament_results_2021.csv` outside of that first column. The script will predict a bracket from that starting point. The `-m` flag specifies how the model should determine the winner of each matchup. In this case, `1` tells the model to always select the team that is favored by Elo rating. `0` would tell the model to choose probabilistically (default) and `2` would choose randomly. 

As an output, you will see your original first column, then half the number of teams in the second column, a quarter in the third, and so on until a column has just 1 name. A team that advances from one column to the next is deemed to have won their matchup. The last team remaining (in the rightmost column) is the champion. Next to each team name will be the percent probability that this team won their previous matchup. In this example, you see Gonzaga is predicted as the 2021 champion and had a 64% chance of winning their matchup with Illinois in the finals. If `-m` was set to `0`, Gonzaga would have a 64% chance of being picked to win this matchup. Instead, since `-m` was set to `1`, Gonzaga was picked automatically because their Elo rating is greater than Illinois'. The output tables are saved in the `Outputs` folder as a csv for further examination.
![alt text](https://github.com/grdavis/college-basketball-elo/blob/main/Images/bracket_pred_current_output.png?raw=true)

###### Example 4
```
python3 predictions.py -S 'Data/tournament_results_2019.csv' 10000 -d '20190320'
```
In this example, we are simulating 10,000 possible outcomes for the 2019 March Madness tournament based on the Elo ratings from 3/20/2019 (the day before the tournament started). The `-d` flag, which is optional, was used here to roll the ratings back to the specific date where we would have made the predictions prior to the 2019 tournament. If it was not specified, the simulations would be for the 2019 tournament matchups, but with today's Elo ratings (which are not as favorable to Duke, for example). The `-d` flag can also be used with the functionality demonstrated in examples 1, 2, and 3. 

As an output you will see one column for each round of the tournament a team could possibly make it to - including being named champion. Each row tells us in what share of simulations that team made it to the corresponding round. For example, in ~63% of simulations, Virginia made it to the Elite 8. In ~15%, they won the whole thing (which they did end up doing). The output is sorted by this final column. The winners of each matchup in each simulation are chosen probabilistically. The output tables are saved in the `Outputs` folder as a csv for further examination. 
![alt text](https://github.com/grdavis/college-basketball-elo/blob/main/Images/historical_simulation_output.png?raw=true)

For completeness, `predictions.py` can be run with the following options:
  * `-h` or `--help`: Displays the help messages for this script
  * `-F` or `--ForecastDate`: Use if trying to predict games for a particular date in the future, set `-F` equal to the day you want to predict. If games are scheduled on our games data source, the output will be predictions for all games. `-F` can also be used on dates in the past, just make sure to also specify `-d` - the day through which the model is allowed to use information in making its predictions. Enter date as YYYYMMDD (e.g. 20190315).
  * `-G` or `--GamePredictor`: Use this to predict a single game. Supply a home team and an away team - both as strings. Use `-n` flag to indicate a neutral site. This can be used in conjunction with the `-d` flag to make predictions as they would have been made in the past
  * `-n` or `--neutral`: If provided and using `--GamePredictor`, this will indicate the matchup should be simulated as if the teams are at a neutral location. No advantage will be given to the home team (the first team listed)
  * `-S` or `SimMode`: Use this to run monte carlo simulations for a tournament and see in what share of simulations a team makes it to each round. Enter the filename storing the tournament participants as a string and an integer number of simulations to run. Don't forget to use `-d` if predicting this tournament as of a date in the past
  * `-d` or `--dateSim`: Specify a date in the past on which to make predictions. `-d` can be thought of as the "stop short" date. The model will freeze Elo ratings on the date specified to simulate what it would be like to make predictions as of that date. Enter date as a YYYYMMDD integer (e.g. 20190320). If not specified, the default is to calculate through the last game in the most recent data. `-d` can be specified at any time (making future/past game predictions for a day, single game predictions, single bracket predictions, or simulating bracket outcomes)
  * `-P` or `--PredictBracket`: Use to predict results of a tournament (i.e. generate a single bracket). Enter the filename storing the tournament participants in the first column. Use the `-m` flag to specify how each matchup should be decided. Don't forget to use `-d` if predicting this tournament as of a date in the past
  * `-m` or `--mode`: By default, the winner for each matchup in a tournament prediction is selected probabilistically (mode 0). Use `1` to have the model always pick the 'better' team according to Elo ratings. Use `2` to decide each matchup with a coinflip (random selection)
  * `-r` or `--round`: When using `-P` or `-S`, optionally specify which round of the tournament file to start making predictions from (e.g. 0 = predict advancements from the 0th column onwards in the tournament file)

## Methodology
The methodology for Elo rating systems is discussed in much more detail in several sources on the web, including the [Elo rating systems](https://en.wikipedia.org/wiki/Elo_rating_system) Wikipedia page. This particular implementation was most closely guided by FiveThirtyEight methodologies for the [NBA](https://fivethirtyeight.com/features/how-we-calculate-nba-elo-ratings/) and [NFL](https://fivethirtyeight.com/methodology/how-our-nfl-predictions-work/).

Elo ratings are useful for addressing differences in strength of schedule. When you get to the end of the season and see a 22-6 team playing a 14-1 team, your instinct might be to think the 14-1 team is favored. They lost only one game all season. However, that 14-1 Colgate team only played 5 different opponents all season - and none of them are particularly challenging opponents. Meanwhile, that 22-6 Arkansas team lost several games, but also played one of the tougher schedules in the country - including 4 games against top-25 teams. Fortunately, Elo accounts for these differences. Colgate's wins don't earn them that many Elo points because they mostly played inferior opponents. Arkansas' wins earned them a lot of points because they were against some teams where they were not expected to win. Thus, Arkansas is heavily favored in their matchup with Colgate.

In a particular matchup, the difference in ratings can be used to predict both a win probability and a point spread. At the time of writing (Spring 2021), Arkansas' Elo rating is 2032 while Colgate's is 1849. The difference in ratings is +183 for Arkansas. We can calculate win probability as: 
```
1 / (1 + 10**(-elo_spread/400))
```
Arkansas' win probability is 74% when we plug in +183 for `elo_spread`. Using -183 for `elo_spread`, we find that Colgate's win probability is 26% `(100% - 74%)`. To convert this difference in Elo ratings to a point spread we can divide +183 by **-24.78**. This tells us Arkansas is a -7.4 point favorite (Vegas says -8.5). 

An important part of any sporting event is home-court advantage. Teams receive an automatic boost of **+82** Elo points when they are at home. This implies a 3.31-point advantage `(82/24.78)` at home. No advantage is applied when games are played at neutral locations.

One major advantage of an Elo system is its simplicity. Elo ratings are updated simply by the final results of games. Teams with higher Elo ratings are perceived as better than teams with lower ratings. A team's rating changes after every game they play. The rating goes up after a win and down after a loss. There are two factors that determine by how much it goes up or down:
1. Elo Difference - A win over an opponent with an Elo rating that is much higher than yours is more meaningful than a win over a team you are rated much higher than and expected to beat. Essentially, bigger upset wins are worth more. On the flipside, more surprising losses to much worse teams will cost more rating points.
2. Margin of Victory (MoV) - A win by 20+ points is more meaningful than a 1-point win. The more you win by, the more points you are rewarded for the win. On the flipside, the more you lose by, the more points you can expect to lose. The **Margin-of-Victory multiplier** is calculated as:
```
((MoV + 2.5)**.7) / (6 + .006 * elo_margin)
```
The best way to summarize how Elo ratings get adjusted, is to assume that they are constantly trying to converge on accuracy. They want to change as little as possible. If a result is surprising according to the ratings, then the ratings were clearly very wrong, so they should make dramatic changes. However, if the result is about what is expected, there won't be much to adjust. The ratings are close to accurate.

The full formula for updating a team's rating is best understood with an example. Let's consider the SEC championship between Alabama and LSU on 3/14/2021. Alabama's Elo rating was 1923 at the time, and LSU's was 1828. We can calculate Alabama's win probability at this neutral-site game is 63%. The final score was Alabama 80, LSU 79. To adjust Alabama, we find that the Elo difference was +95 `(1923 - 1828)` and the MoV was +1. Using the formula above, we find the Margin-of-Victory multiplier to be 0.37. We also need a constant called a K-factor that influences how much each game should adjust the ratings. Our optimal K-factor for every game is **47**. Putting it all together:
```
winner_change_in_elo = k_factor * MoV_multiplier * (1 - winner_win_probability)
+6 = 47 * 0.37 * (1 - 0.63)
```
We adjust Alabama's rating up 6 points to 1929 and LSU's down by 6 to 1822. Alabama still gets points for winning the game. However, they were expected to win by even more than they did (the model had them at 3.8-point favorites), so they don't get that many points. In contrast, we can look at Georgetown's 73-48 win over Creighton in the Big East Championship on 3/13/2021. Georgetown was a major underdog: 1726 Elo rating vs. 1876 with a win probability of 30%. Not only did they pull of the upset (according to the model), but they won by _a lot_. Thus, the model adjusted heavily:
```
winner_change_in_elo = k_factor * MoV_multiplier * (1 - winner_win_probability)
+47 = 47 * 1.47 * (1 - 0.30)
```

Elo ratings are meant to be a closed system. Upon initialization, each team starts at an Elo rating of **1500**. The total number of points in the system should not change (1500 * the total number of teams at the start). Therefore, the number of points gained by the winner of a game equals the number of points lost by the loser of the game. In practice, the total number of points in this system does not remain constant because new teams are constantly joining. Some make the jump to D1 from lower divisions, or sometimes D1 schools expand their schedules to non-D1 teams. These late-joiners we should assume are not very good. Thus, they start with an Elo rating of **985** (i.e. they are automatically 21-point underdogs against an average opponent). As noted in [this issue](https://github.com/grdavis/college-basketball-elo/issues/8), teams that have recently elevated to D1 may not actually be this bad, but the model doesn't have enough data on them yet. That will even out over time, but in their nascency, we should not trust predictions involving these teams. We also drop teams from the system at the end of the season if they played less than **10** D1 games. If they re-emerge in a game next season, they will start at **985** again.

In most Elo systems, there is some adjustment made at the end of every season to revert teams back to average. It makes sense that as some players graduate and new players come in, we should be less confident in our current rating for a team. Really good teams should be adjusted down a litte. Really bad teams should be adjusted up a little. FiveThirtyEight, for example, starts every new season by taking `0.75 * end_of_season_rating + 0.25 * league_average_rating` in the NBA. Their NBA new season carryover is 0.75. A wrinkle in this model is that instead of pushing teams towards the overall average rating, we push them towards the average rating _within their conference_. The NBA has parity amongst its teams and the league is relatively small (compared to the 300+ teams in the NCAAB model). Generally, there are large gaps in skill levels not only across teams, but also across entire conferences. With this in mind, the NCAA new season carryover in my Elo model is **0.64** (`0.64 * end_of_season_rating + 0.36 * conference_average_rating`). This is discussed further in the tuning section.

## Tuning and Performance
The primary variables subject to tuning were the K-factor, Home-Court Advantage, and New Season Carryover. Secondary variables subject to tuning were the MoV multiplier equation, and the starting Elo rating for new teams joining the system. The primary loss function used for tuning was the [Brier score](https://en.wikipedia.org/wiki/Brier_score). Essentially, this is the sum of the squared difference between predicted win probability and result for every game in the dataset. The result is 1 for a win and 0 for a loss. So if the model gives a team a 70% win probability and they win, the Brier score is `(1 - 0.70)^2 = 0.09`. However, if they lose, the score is 0.49. The goal in the tuning process was to minimize the average Brier score. In every simulation, I don't start tracking Brier until after the 3rd season to give the model some time to instantiate.

Throughout tuning, I narrowed in on optimal values of **47**, **+82**, and **0.64** for the primary variables: K-factor, Home-Court Advantage, and New Season Carryover. **These key are updated frequently whenever I go through the tuning process, so documentation may not be up to date.** See the top of `elo.py` for the latest model inputs. 

All three inputs were surprising in their own way. A K-factor of 47 is much larger than the NBA K-factor of 20. This implies that momentum plays a bigger role in college basketball than in the NBA. A larger K-factor encourages larger swings in Elo rating after every game. This could also be a side effect of having much greater Elo rating matchup disparities than exist in the NBA. The range of Elo values is much larger in NCAAB, so the size of jumps is larger as well. A home-court advantage of +82 implies only a 3.31-point advantage at home - which is less than what the data indicates. From 2010 to 2020, the average NCAA home advantage was 7.1 points, while the NBA was 2.8. Perhaps this number is inflated due to a long right tail of dominant home victories by D1 teams that tend to host more blowout games instead of traveling to blow someone out. For example, Harvard (mid-to-bottom-tier D1) always hosts MIT (mid-tier D3) as part of a friendly rivalry where Harvard always wins by a million. The game is _never_ played at MIT. Games like these are outliers that skew the 7.1-point advantage up while the Elo model discovers that for the _majority_ of games +82 is appropriate. Lastly, a season carryover of 0.64 is lower than the NBA carryover. This makes sense as there is probably much more turnover on these NCAAB teams. Players graduate, transfer, or move on to the NBA every year. I expected the carryover value to be even lower. However, teams tend to be consistent in their recruiting. So a team like Duke that loses several star players every year is also probably bringing in several equally-talented stars next year to replace them. Maybe it makes sense that they aren't hurt much by the turnover. In addition, the other component in the reversion is the conference-average Elo. The ACC, compared to most other conferences, has a very strong Elo. As an example, Duke's Elo goes from 1948 at the end of the 21-22 season to 1887 to start the 22-23 season `(1948 * 0.64 + 1745 ACC average * 0.36 = 1875)`. 

Secondary tuning of the starting elo for new teams narrowed in on **985**. Lastly, I made minor adjustments to FiveThirtyEight's MoV multiplier equation to reflect the fact that MoV in college games is usually more than in NBA games. After some tinkering, I landed on the MoV multiplier equation explained above that essentially dampens the impact of MoV a little more than the NBA equation:
![alt text](https://github.com/grdavis/college-basketball-elo/blob/main/Images/MoV_selection.png?raw=true)

The plot below shows the average Brier score, the error function to minimize in tuning, per season over the last 7 years. It is a good sign that the error remains relatively stable over time. The slight uptick in error coincides with Covid. It looks like these disruptions have not not become a trend of increasing error over time.
![alt text](https://github.com/grdavis/college-basketball-elo/blob/main/Images/brier_over_time_20250201.png?raw=true)

As mentioned in the methodology section, Elo ratings are meant to be a closed system. Ideally, the total number of points in the system does not change. However, so many new teams join the system that the total number of points is not stable over time. For the most part, this is shown to be the case. The average Elo rating for each team is ~1500. When many teams enter the Elo rating system with their default 985 rating and play just one game (i.e. the MITs of the NCAA world who enter the system just to play one game against Harvard every year) the average rating gets pulled down. To combat this, the model eliminates teams who played less than 10 games in a season at the end of every season. The next time those teams have a Division 1 games, they will need to rejoin the system as a new 985-point team. These new teams in the system help explain why the most recent seasons see a dip in the average Elo rating.
![alt text](https://github.com/grdavis/college-basketball-elo/blob/main/Images/end_of_season_elo_20250201.png?raw=true)

The chart below shows the Elo rating distribution as of games through 1/31/2025. This chart shows a distribution centered close to 1500, which is what we should expect for well-sorted teams. 1500 is supposed to be the average. As expected, some teams really distinguish themselves in the long right tail (Auburn in this snapshot).
![alt text](https://github.com/grdavis/college-basketball-elo/blob/main/Images/elo_distribution_20250201.png?raw=true)

In order to predict point spreads from Elo ratings, we need to determined how many points of Elo difference equal 1 point of final score difference. To do this, I plotted Elo rating differences versus the average resulting score difference in those games. The size of the bubbles is proportional to the number of games in the dataset had that Elo difference. It's a good sign that a clear trend emerges in this plot. Towards the left and right tails of the plot, you can see some curvature. But, for the majority of games, a straight line can help explain the relationship. I fit a linear regression to the middle 80% of the data. In general, the slope of this line indicates that every 24.78 points of Elo difference corresponds to a 1 point difference in predicted point spread. In other words, a team that is 50 Elo points better should be favored by about 2 points in the game. The graph indicates we can confidently convert Elo point differences to point spreads up until the Elo difference is about 300, which is a spread of about 12 points.
![alt text](https://github.com/grdavis/college-basketball-elo/blob/main/Images/elo_to_point_spread_20250201.png?raw=true)

Hypothetically, if one was to use this Elo model for gambling, you would want to know how often you could beat vegas by making model-informed bets. That is to say, if the model predicts the game will be closer than Vegas, you would bet on the underdog. And if the model predicts the point differential to be greater than Vegas, you would bet on the favorite. Naturally, the Elo model and Vegas don't always agree with one another. One theory to take advantage of this difference is to only bet on games where the Elo/Vegas spread difference is greater than a certain threshold. Below, tracking the blue line, you see that Elo-informed picks are more and more likely to "win" their bet as the absolute difference between Elo and Vegas spreads increases. However, as you increase your trigger threshold, there are fewer and fewer games meeting the criteria on which to bet (red line). If you did not have some kind of trigger threshold and tried to bet on every game, you would still win 50% of the time - pretty good. The problem is sportsbooks trying to keep some money for themselves with a [vig](https://en.wikipedia.org/wiki/Vigorish). In reality, to break even, you typically need to win 52.38% of the time or more (green line). Making Elo-informed bets only crosses this threshold for games where the Elo/Vegas absolute difference is 7.25 or more. Only 4.3% of games in the database met this criteria, but it is exciting to see the win percentage crosses the threshold at all! A huge shoutout to [SportsBookReviewsOnline](https://www.sportsbookreviewsonline.com/scoresoddsarchives/ncaabasketball/ncaabasketballoddsarchives.htm) for supplying the historical data that made this possible. (This is not gambling advice - please bet responsibly)
![alt text](https://github.com/grdavis/college-basketball-elo/blob/main/Images/elo_spread_win_rate_ALL_20250201.png?raw=true)

Lastly, to visualize the accuracy of the Elo model's predictions, I plotted predicted win probability versus actual win percentage. For example, there have been 1,626 games in the dataset (Fall 2010 - Winter 2025) where the model predicted a team's win probability was ~55% (rounded to the nearest 1%). In reality, 897 of those teams won their games. That is a win percentage of 55.2% `(897/1626)` - which means the model's prediction was about right. Over time, teams given an X% chance of winning should win about X% of their games. This plot shows that relationship to be mostly true. Plotted with a linear line of best fit, the R-Squared value is ~0.99.
![alt text](https://github.com/grdavis/college-basketball-elo/blob/main/Images/prediction_accuracy_20250201.png?raw=true)

## Other Functionality
To recreate any of these visualizations or re-tune the model, refer to the `tuning.py` file.
