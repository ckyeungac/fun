
# coding: utf-8

# # Extract Stock Information using Selenium

# In[11]:


from selenium import webdriver
import time
import sys, os
from collections import namedtuple
from collections import deque
import time
import datetime
import numpy as np
from threading import Thread
from math import sqrt
import csv

# used for ploting the candle plot
from plotly import __version__
from plotly.offline import download_plotlyjs, init_notebook_mode, plot, iplot
import plotly.graph_objs as go
from plotly import figure_factory as FF
from plotly import tools

# adding current directory into environment path
# required for selenium chrome
os.environ["PATH"] += os.pathsep + './'


# In[12]:


curr_trade_price = 30000
change_choices = range(-5, 6)
def simulate_trade():
    global curr_trade_price
    trade_list = []
    for _ in range(np.random.choice([1,2,3])):
        today = datetime.datetime.now()
        trade_time = '{}:{}:{}'.format(today.hour, today.minute, today.second)
        trade_change = np.random.choice(change_choices)
        trade_price = curr_trade_price + trade_change
        curr_trade_price = trade_price
        trade = Trade(trade_time, trade_price, trade_change, 1, 1, 100)
        trade_list.append(trade)
        time.sleep(0.5)
        print(trade)
    return trade_list


# In[13]:


Trade = namedtuple('Trade', ['time', 'price', 'change', 'precentage_change', 'single_volumn', 'total_volumn'])

# fixed the width of the candlestick
# add the average line
## i-th points = the average price of trading up to time i


def to_datetime_obj(trade_time):
    today = datetime.datetime.now()
    result = datetime.datetime.strptime(trade_time, '%H:%M:%S')
    result = result.replace(year=today.year, month=today.month, day=today.day)
    return result

    
    
class Stock(object):
    def __init__(self, time_interval=1):
        # initialize the browser
        print("Openning browser...")
        print("Connecting to http://m.3x.com.tw/app_future.php...")
        self.driver = webdriver.Chrome() # using Chrome to fetch data
        self.driver.get("http://m.3x.com.tw/app_future.php") # data source     
        self.id_list = ['detail_ul_{}'.format(i) for i in range(11)]
        
        today = datetime.datetime.now()
        self.start_time = today.replace(second=0, microsecond=0)
        num_data_points = 90
        
        # define OHLC data variable for plotting candles
        self.open_data = [0] * num_data_points
        self.high_data = [0] * num_data_points
        self.low_data = [0] * num_data_points
        self.close_data = [0] * num_data_points
        
        self.time_interval = datetime.timedelta(minutes=time_interval)
        self.datetime_data = [self.start_time+datetime.timedelta(minutes=i) for i in range(num_data_points)]
        
        self.curr_open = self.curr_high = self.curr_low = self.curr_close = 0
        self.curr_datetime = datetime.datetime.now()
        self.next_datetime = self.curr_datetime + self.time_interval
        self.datetime_data[-1] = self.curr_datetime
        
        # define data for the bar chat
        self.volumn_data = [0] * num_data_points
        
        # define data for the average, sd price
        self.price_avg_data = [0] * num_data_points
        self.price_std_data = [0] * num_data_points
        self.price_avg = 0
        self.price_std = 0
        self.volumn_sum = 0
        
        # initize the trades records
        self.trades = deque(maxlen=30)
        
        # layout setting
        self.y_max = 30500
        self.y_min = 29500
        
        
    def init_candle_value(self):
        print("initialize the candle plot value")
        trade_list = self.get_live_trade_data()
        
        today = datetime.datetime.now()
        self.start_time = today.replace(second=0, microsecond=0)
        if len(trade_list) > 0:
            # update OHLC
            trade = trade_list[0]
            trade_time = to_datetime_obj(trade.time)
            trade_price = float(trade.price)
            trade_volumn = float(trade.single_volumn)
            
            time_diff = trade_time - self.start_time
            idx = time_diff.seconds // 60

            self.curr_open = self.curr_high = self.curr_low = self.curr_close = trade_price
            self.open_data[idx] = self.curr_open
            self.high_data[idx] = self.curr_high
            self.low_data[idx] = self.curr_low
            self.close_data[idx] = self.curr_close
            
            # update volumn bar
            self._update_volumn_data(trade)
            
            # update average plot
            self._update_avg_std_data(trade)
    
            # layout setting
            self.y_max = trade_price + 50
            self.y_min = trade_price - 50
        else:
            print("No trade found in the web. using the simulation data...")
        print("="*30)


    def get_live_trade_data(self):
        curr_trade_list = []
        for id_tag in self.id_list:
            targets = self.driver.find_elements_by_id(id_tag)
            for data in targets:
                items = data.find_elements_by_tag_name("li")
                try:
                    # extract the trade record
                    trade = Trade(*[item.text for item in items])
                    
                    # if the trade is not in the trade lists, append it and print it out
                    if trade not in list(self.trades):
                        self.trades.append(trade)
                        # print("時間: {}, 現價: {}, 漲跌: {}, %: {}, 單量: {}, 總量: {}".format(
                        #     trade.time,
                        #     trade.price,
                        #     trade.change,
                        #     trade.precentage_change,
                        #     trade.single_volumn,
                        #     trade.total_volumn
                        # ))
                        curr_trade_list.append(trade)
                    else:
                        for trade in curr_trade_list[::-1]:
                            print("時間: {}, 現價: {}, 漲跌: {}, %: {}, 單量: {}, 總量: {}".format(
                                trade.time,
                                trade.price,
                                trade.change,
                                trade.precentage_change,
                                trade.single_volumn,
                                trade.total_volumn
                            ))
                            sys.stdout.flush()
                        return curr_trade_list
                except:
                    continue
        return curr_trade_list
    
    def _update_OHLC_data(self, trade):
        trade_time = to_datetime_obj(trade.time) # str: 'hh:mm:ss'
        trade_price = float(trade.price) # str: 'xxxxx.xx'
        trade_volumn = float(trade.single_volumn) # str: 'xxxxx'
        
        # update current candle data
        time_diff = trade_time - self.start_time
        idx = idx_tmp = time_diff.seconds // 60
        if self.open_data[idx] == 0:
            self.curr_high = 0
            self.curr_low = 10000000
            while self.close_data[idx_tmp] == 0:
                idx_tmp -= 1
            self.open_data[idx] = self.close_data[idx_tmp]


        self.curr_high = max(self.curr_high, trade_price)
        self.curr_low = min(self.curr_low, trade_price)
        self.curr_close = trade_price
        self.high_data[idx] = self.curr_high
        self.low_data[idx] = self.curr_low
        self.close_data[idx] = self.curr_close
#       self.datetime_data[-1] = self.curr_datetime

        # update yaxis range
        if self.y_max < trade_price:
            self.y_max = trade_price 
        elif self.y_min > trade_price:
            self.y_min = trade_price
        
    
    def _update_volumn_data(self, trade):
        trade_time = to_datetime_obj(trade.time) # str: 'hh:mm:ss'
        trade_price = float(trade.price) # str: 'xxxxx.xx'
        trade_volumn = float(trade.single_volumn) # str: 'xxxxx'
        
        time_diff = trade_time - self.start_time
        idx = idx_tmp = time_diff.seconds // 60
        
        # update bar chart
        self.volumn_data[idx] += trade_volumn
        
    
    def _update_avg_std_data(self, trade):
        trade_time = to_datetime_obj(trade.time) # str: 'hh:mm:ss'
        trade_price = float(trade.price) # str: 'xxxxx.xx'
        trade_volumn = float(trade.single_volumn) # str: 'xxxxx'
        
        time_diff = trade_time - self.start_time
        idx = idx_tmp = time_diff.seconds // 60
        
        prev_avg = self.price_avg
        prev_std = self.price_std
        prev_vol = self.volumn_sum
        
        # finding average and standard deviation
        curr_vol = prev_vol + trade_volumn
        curr_avg = prev_avg + (trade_volumn/curr_vol) * (trade_price - prev_avg)
        curr_var = (prev_vol * (prev_std**2 + prev_avg**2)) + (trade_volumn * trade_price**2)
        curr_var /= curr_vol
        curr_var -= curr_avg**2
        curr_std = sqrt(curr_var)
        
        # update data
        self.price_avg = curr_avg
        self.price_std = curr_std
        self.volumn_sum = curr_vol
        
        self.price_avg_data[idx] = curr_avg
        self.price_std_data[idx] = curr_std
        
    
    def update_plot_data(self, trade_list):    
        for trade in trade_list[::-1]:
            self._update_OHLC_data(trade)
            self._update_volumn_data(trade)
            self._update_avg_std_data(trade)

            
    def get_candle_plot(self):
        # ref: https://plot.ly/~jackp/17421/plotly-candlestick-chart-in-python/
        INCREASING_COLOR = '#009900'
        DECREASING_COLOR = '#ff0000'
        
        layout = go.Layout(
            plot_bgcolor = '#fafafa',
            yaxis = dict( domain = [0, 0.2], showticklabels = True ),
            yaxis2 = dict( domain = [0.25, 0.8], range=[self.y_min, self.y_max] ),
            legend = dict( orientation = 'h', y=0.9, x=0.3, yanchor='bottom' ),
            margin = dict( t=40, b=40, r=40, l=40 ),
            boxgroupgap = 0.0,
            boxgap = 0.0,
            title='Volume: {0}, Avg: {1:.2f}, Std: {2:.3f}'.format(
                    self.volumn_sum,
                    self.price_avg, 
                    self.price_std,
                )
        )
        
        # ADD candlestick
        candle_trace = go.Candlestick(
            open = self.open_data,
            high = self.high_data,
            low = self.low_data,
            close = self.close_data,
            x = self.datetime_data,
            yaxis = 'y2',
            name = 'Candlestick',
            # increasing = dict(line=dict(color=INCREASING_COLOR)),
            # decreasing = dict(line=dict(color=DECREASING_COLOR)),
        )
        
        # Add average and std plot
        datetime_data = np.array(self.datetime_data)
        price_avg_data = np.array(self.price_avg_data)
        price_std_data = np.array(self.price_std_data)
        
        target_idx = (price_avg_data != 0)
        datetime_data = datetime_data[target_idx]
        price_avg_data = price_avg_data[target_idx]
        price_std_data = price_std_data[target_idx]
        # print('total volume: ', self.volumn_sum)
        # print('price avg:', self.price_avg)
        # print('price std:', self.price_std)
        price_avg_trace = go.Scatter(
            x=datetime_data,
            y=price_avg_data,
            mode='lines',
            line=dict(width=1.5),
            marker=dict(color='#0099ff'),
            yaxis='y2',
            name='Price Average',
            opacity=0.8,
        )
        
        price_std_1p_data = price_avg_data + price_std_data
        price_std_1p_trace = go.Scatter(
            x=datetime_data,
            y=price_std_1p_data,
            mode='lines',
            line=dict(width=1),
            marker=dict(color='#555555'),
            yaxis='y2',
            name='Price +1 std',
            opacity=0.3,
            hoverinfo='none',
        )
        
        price_std_2p_data = price_avg_data + (price_std_data * 2.0)
        price_std_2p_trace = go.Scatter(
            x=datetime_data,
            y=price_std_2p_data,
            mode='lines',
            line=dict(width=1),
            marker=dict(color='#555555'),
            yaxis='y2',
            name='Price +2 std',
            opacity=0.3,
            hoverinfo='none',
        )
        
        price_std_1n_data = price_avg_data - price_std_data
        price_std_1n_trace = go.Scatter(
            x=datetime_data,
            y=price_std_1n_data,
            mode='lines',
            line=dict(width=1),
            marker=dict(color='#555555'),
            yaxis='y2',
            name='Price -1 std',
            opacity=0.3,
            hoverinfo='none',
        )
        
        price_std_2n_data = price_avg_data - (price_std_data * 2.0)
        price_std_2n_trace = go.Scatter(
            x=datetime_data,
            y=price_std_2n_data,
            mode='lines',
            line=dict(width=1),
            marker=dict(color='#555555'),
            yaxis='y2',
            name='Price -2 std',
            opacity=0.3,
            hoverinfo='none',
        )
        
        # setting volumn bar chart color
        colors = []
        for i in range(len(self.close_data)):
            if self.close_data[i] >= self.open_data[i]:
                colors.append(INCREASING_COLOR)
            else:
                colors.append(DECREASING_COLOR)
                
        volumn_trace = go.Bar(
            x=self.datetime_data,
            y=self.volumn_data,
            marker=dict(color=colors),
            yaxis='y',
            name='Volume'
        )
        
        data = [candle_trace, 
                price_avg_trace, 
                price_std_1p_trace, 
                price_std_1n_trace, 
                price_std_2p_trace,
                price_std_2n_trace,
                volumn_trace]
        fig = go.Figure(data=data, layout=layout)
#         iplot(fig, validate=False)
        plot(fig, 'stock plot')


def save_trade_to_csv(trade_list):
    today = datetime.date.today()
    data_dir = './data'
    filename = 'trades_{}{}{}.csv'.format(today.year, today.month, today.day)
    filepath = os.path.join(data_dir, filename)
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    with open(filepath, 'a') as f:
        w = csv.writer(f)
        w.writerows(
                [
                    (trade.time,
                    trade.price,
                    trade.change,
                    trade.precentage_change,
                    trade.single_volumn,
                    trade.total_volumn)
                    for trade in trade_list[::-1]
                ]
            )


# In[14]:
x = Stock()
x.init_candle_value()
while True:
    trade_list = x.get_live_trade_data()
    x.update_plot_data(trade_list)
    x.get_candle_plot()
    save_trade_to_csv(trade_list)

