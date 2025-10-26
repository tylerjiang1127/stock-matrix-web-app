### Yahoo Finanace
import yfinance as yf
import plotly
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime as dt
import pandas as pd
import talib
import numpy as np
from dateutil.relativedelta import *
from pytz import timezone
from itertools import compress


ticker = yf.Ticker('BB')
df = ticker.history(start='2021-06-01', end='2022-01-31', interval="1d")
df