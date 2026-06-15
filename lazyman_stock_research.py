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

## import Dash
import dash_bootstrap_components as dbc
import dash
from dash import dcc
from dash import html
from dash import dash_table
from dash.dependencies import Input, Output, State
import time
import plotly.io as pio
pio.renderers.default='notebook'

import requests
from requests.exceptions import ConnectionError
from bs4 import BeautifulSoup

# Add caching and rate limiting
from functools import lru_cache
import threading

# Global cache for market data with timestamps
market_data_cache = {}
cache_lock = threading.Lock()
CACHE_DURATION = 60  # Cache data for 60 seconds

# Circuit breaker for API failures
api_failure_count = {}
API_FAILURE_THRESHOLD = 3
API_COOLDOWN_PERIOD = 300  # 5 minutes cooldown after failures


def get_info(ticker):
    try:
        # Handle empty or invalid ticker
        if not ticker or ticker.strip() == '':
            raise ValueError("Empty ticker provided")
            
        ## Company Information & Company Description
        ticker_obj = yf.Ticker(ticker)
        company_overview = ticker_obj.info
        
        # Check if we got valid data
        if not company_overview or 'symbol' not in company_overview:
            raise ValueError(f"No data found for ticker {ticker}")

        def get_peratio():
            trailing_eps = company_overview.get('trailingEps')
            prev_close = company_overview.get('regularMarketPreviousClose')
            if trailing_eps is None or prev_close is None or trailing_eps <= 0:
                return 'N/A'
            else:
                return "%.2f" % float(prev_close / trailing_eps)
        def get_psratio():
            ps_ratio = company_overview.get('priceToSalesTrailing12Months')
            if ps_ratio is None:
                return 'N/A'
            else:
                return "%.2f" % float(ps_ratio)
        def get_pbratio():
            pb_ratio = company_overview.get('priceToBook')
            if pb_ratio is None:
                return 'N/A'
            else:
                return "%.2f" % float(pb_ratio)


        data = [
        ['Symbol'               , company_overview.get('symbol', 'N/A')],
        ['Name'                 , company_overview.get('longName', 'N/A')],
        ['Sector'               , company_overview.get('sector', 'N/A')],
        ['Industry'             , company_overview.get('industry', 'N/A')],
        ['Market Cap'            , format(int(company_overview.get('marketCap', 0)), ',')+' '+company_overview.get('currency', 'USD') if company_overview.get('marketCap') else 'N/A'],
        ['Price52WeekHigh'      , "%.2f" % float(company_overview.get('fiftyTwoWeekHigh', 0)) +' '+company_overview.get('currency', 'USD') if company_overview.get('fiftyTwoWeekHigh') else 'N/A'],
        ['Price52WeekLow'       , "%.2f" % float(company_overview.get('fiftyTwoWeekLow', 0))  +' '+company_overview.get('currency', 'USD') if company_overview.get('fiftyTwoWeekLow') else 'N/A'],
        ['Price To Earning Ratio'  , get_peratio()],
        ['Price To Sales Ratio TTM' , get_psratio()],
        ['Price To Book Ratio'     , get_pbratio()]
        ]

        company_info  = pd.DataFrame(data, columns = ['Indicator','Value'])
        company_desc  = company_overview.get('longBusinessSummary', 'No business summary available.')

        return company_info, company_desc

    except Exception as e:
        print(f"Error getting info for ticker {ticker}: {e}")
        data = [
        ['Symbol'               , ''],
        ['Name'                 , ''],
        ['Sector'               , ''],
        ['Industry'             , ''],
        ['MarketCap'            , ''],
        ['Price52WeekHigh'      , ''],
        ['Price52WeekLow'       , ''],
        ['PriceToEarningRatio'  , ''],
        ['PriceToSalesRatioTTM' , ''],
        ['PriceToBookRatio'     , '']
        ]

        company_info  = pd.DataFrame(data, columns = ['Indicator','Value'])
        company_desc  = ''

        return company_info, company_desc


def fundamentals_prep(ticker, period):
    try:
        ## Starting Tables
        ticker = yf.Ticker(ticker)
        if period == 'Yearly':
            income_statement = ticker.incomestmt.transpose()
            balance_sheet    = ticker.balancesheet.transpose()
            cash_flow        = ticker.cashflow.transpose()
        elif period == 'Quarterly':
            income_statement = ticker.quarterly_incomestmt.transpose()
            balance_sheet    = ticker.quarterly_balancesheet.transpose()
            cash_flow        = ticker.quarterly_cashflow.transpose()
        else:
            income_statement,balance_sheet,cash_flow = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        income_statement = income_statement.rename_axis('fiscalDateEnding').reset_index(inplace=False)
        balance_sheet    = balance_sheet.rename_axis('fiscalDateEnding').reset_index(inplace=False)
        cash_flow        = cash_flow.rename_axis('fiscalDateEnding').reset_index(inplace=False)

        income_statement['fiscalDateEnding'] = income_statement['fiscalDateEnding'].dt.strftime('%Y-%m-%d')
        balance_sheet['fiscalDateEnding']    = balance_sheet['fiscalDateEnding'].dt.strftime('%Y-%m-%d')
        cash_flow['fiscalDateEnding']        = cash_flow['fiscalDateEnding'].dt.strftime('%Y-%m-%d')

        ## Querry the Currency Unit
        currency = ticker.info['financialCurrency']

        ## Convert all None value to '0'
        income_statement = income_statement.fillna(value = 0)
        balance_sheet    = balance_sheet.fillna(value = 0)
        cash_flow        = cash_flow.fillna(value = 0)

        ## Income Statement Data processing
        IncomeStatement = income_statement[['fiscalDateEnding','Total Revenue','Cost Of Revenue',
                                        'Gross Profit','Operating Income','Net Income']].iloc[:8]
        IncomeStatement[['Total Revenue','Cost Of Revenue','Gross Profit',
                         'Operating Income','Net Income']] = IncomeStatement[['Total Revenue','Cost Of Revenue','Gross Profit',
                                                                              'Operating Income','Net Income']].astype(float)

        IncomeStatement['Gross Margin']     = IncomeStatement['Gross Profit']/IncomeStatement['Total Revenue']
        IncomeStatement['Operating Margin'] = IncomeStatement['Operating Income']/IncomeStatement['Total Revenue']
        IncomeStatement['Net Profit Margin'] = IncomeStatement['Net Income']/IncomeStatement['Total Revenue']

        ## Balance Sheet Data processing
        BalanceSheet = balance_sheet[['fiscalDateEnding','Total Assets','Total Liabilities Net Minority Interest','Stockholders Equity','Cash And Cash Equivalents',
                                      'Current Assets','Current Liabilities']].iloc[:8]
        BalanceSheet[['Total Assets','Total Liabilities Net Minority Interest','Stockholders Equity','Cash And Cash Equivalents',
                      'Current Assets','Current Liabilities']] = BalanceSheet[['Total Assets','Total Liabilities Net Minority Interest','Stockholders Equity','Cash And Cash Equivalents',
                                                                                          'Current Assets','Current Liabilities']].astype(float)
        BalanceSheet.columns = ['fiscalDateEnding','Total Assets','Total Liab','Total Stockholder Equity','Cash',
                                      'Total Current Assets','Total Current Liabilities']

        BalanceSheet['Cash Ratio'] = BalanceSheet['Cash']/BalanceSheet['Total Current Liabilities']
        BalanceSheet['Current Ratio'] = BalanceSheet['Total Current Assets']/BalanceSheet['Total Current Liabilities']



        ## Cash Flow Data processing
        CashFlow = cash_flow[['fiscalDateEnding','Operating Cash Flow','Investing Cash Flow',
                              'Financing Cash Flow','Capital Expenditure']].iloc[:8]
        CashFlow[['Operating Cash Flow','Investing Cash Flow',
                  'Financing Cash Flow','Capital Expenditure']] = CashFlow[['Operating Cash Flow','Investing Cash Flow',
                                                                                              'Financing Cash Flow','Capital Expenditure']].astype(float)
        CashFlow.columns = ['fiscalDateEnding','Total Cash From Operating Activities','Total Cashflows From Investing Activities',
                              'Total Cash From Financing Activities','Capital Expenditures']

        CashFlow['Free Cash Flow'] = CashFlow['Total Cash From Operating Activities'] + CashFlow['Capital Expenditures']
        CashFlow['OperatingCashflow/SalesRatio'] = CashFlow['Total Cash From Operating Activities']/IncomeStatement['Total Revenue']



        return IncomeStatement, BalanceSheet, CashFlow, currency
    except:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), ''

def fundamentals_tables(ticker, period):

    IncomeStatement, BalanceSheet, CashFlow, currency = fundamentals_prep(ticker, period)

    ## df1, df2, df3 are the three tables used for Most recnet Quarter Fundamental Part
    if IncomeStatement.empty:
        df1 = df2 = df3 = pd.DataFrame()

    else:
        df1 = pd.DataFrame(columns=['KPI','Value'])
        last_incomestatement = IncomeStatement.iloc[0][1:]
        for key, value in enumerate(last_incomestatement):
            if key<=4 and abs(value) > 100000000:
                value_conv = format(int("%.0f" % (value/1000000)),',') + ' M'
            elif key<=4 and abs(value) <= 100000000:
                value_conv = format(int("%.0f" % value),',')
            else:
                value_conv = "{:.1%}".format(value)
            row = {'KPI':last_incomestatement.index[key],'Value':value_conv}
            df1 = pd.concat([df1,pd.DataFrame([row])], ignore_index = True)
        df1['KPI'] = ['Total Revenue','Cost Of Revenue','Gross Profit','Operating Income','Net Income','Gross Margin','Operating Margin','Net Profit Margin']

        df2 = pd.DataFrame(columns=['KPI','Value'])
        last_balancesheet = BalanceSheet.iloc[0][1:]
        for key, value in enumerate(last_balancesheet):
            if key<=5 and abs(value) > 100000000:
                value_conv = format(int("%.0f" % (value/1000000)),',') + ' M'
            elif key<=5 and abs(value) <= 100000000:
                value_conv = format(int("%.0f" % value),',')
            else:
                value_conv = "%.2f" % value
            row = {'KPI':last_balancesheet.index[key],'Value':value_conv}
            df2 = pd.concat([df2,pd.DataFrame([row])], ignore_index = True)
        df2['KPI'] = ['Total Assets','Total Liabilities','Total Shareholder Equity','Cash And Cash Equivalents','Total Current Assets','Total Current Liabilities','Cash Ratio','Current Ratio']

        df3 = pd.DataFrame(columns=['KPI','Value'])
        last_cashflow = CashFlow.iloc[0][1:]
        for key, value in enumerate(last_cashflow):
            if key<=4 and abs(value) > 100000000:
                value_conv = format(int("%.0f" % (value/1000000)),',') + ' M'
            elif key<=4 and abs(value) <= 100000000:
                value_conv = format(int("%.0f" % value),',')
            else:
                value_conv = "%.2f" % value
            row = {'KPI':last_cashflow.index[key],'Value':value_conv}
            df3 = pd.concat([df3,pd.DataFrame([row])], ignore_index = True)
        df3['KPI'] = ['Operating Cash flow','Cash Flow From Investment','Cash Flow From Financing','Capital Expenditures','Free Cash Flow','Operating Cash Flow/Sales Ratio']

    return IncomeStatement, BalanceSheet, CashFlow, df1, df2, df3, currency

def make_dash_table(df):
    """ Return a dash definition of an HTML table for a Pandas dataframe """
    table = []
    for index, row in df.iterrows():
        html_row = []
        for i in range(len(row)):
            html_row.append(html.Td([row[i]]))
        table.append(html.Tr(html_row))
    return table


## Figures Part

def incomestatement_bar(df):
    return {
        'data': [go.Bar(
            x=df['fiscalDateEnding'],
            y=df['Total Revenue'],
            marker={
                "color": "#17991C",
                "line": {
                    "color": "rgb(255, 255, 255)",
                    "width": 2,
                },
            },
            name="Total Revenue"
        ), go.Bar(
            x=df['fiscalDateEnding'],
            y=df['Gross Profit'],
            marker={
                "color": "#DDDE2F",
                "line": {
                    "color": "rgb(255, 255, 255)",
                    "width": 2,
                },
            },
            name="Gross Profit"
        ), go.Bar(
            x=df['fiscalDateEnding'],
            y=df['Operating Income'],
            marker={
                "color": "#36FFF9",
                "line": {
                    "color": "rgb(255, 255, 255)",
                    "width": 2,
                },
            },
            name="Operating Income"
        ), go.Bar(
            x=df['fiscalDateEnding'],
            y=df['Net Income'],
            marker={
                "color": "#38AFF5",
                "line": {
                    "color": "rgb(255, 255, 255)",
                    "width": 2,
                },
            },
            name="Net Income"
        ) ],
        "layout": go.Layout(
            autosize=True,
            bargap=0.35,
            font={"family": "Raleway", "size": 10},
            height=300,
            width=600,
            legend={
                "x": -0.09,
                "y": -0.19,
                "orientation": "h",
                "yanchor": "top",
                "font": {"size": 13}
            },
            margin={
                "r": 0,
                "t": 20,
                "b": 10,
                "l": 10,
            },
            showlegend=True,
            title="",
            hovermode="closest",
            xaxis={
                "autorange": True,
                "showline": True,
                "title": "As of Fiscal Ending Date",
                "type": "category",
            },
            yaxis={
                "autorange": True,
                ## "range": [0, 22.9789473684],
                "showgrid": True,
                "showline": True,
                "title": "",
                "type": "linear",
                "zeroline": False,
            },
        )
    }


def incomestatement_line(df):
    return {
        'data': [go.Scatter(
            x=df['fiscalDateEnding'],
            y=df['Gross Margin'],
            mode='lines+markers',
            line={"color": "#DDDE2F"},
            ##markers = {"color": "#17991C"},
            name="Gross Margin"
        ), go.Scatter(
            x=df['fiscalDateEnding'],
            y=df['Operating Margin'],
            mode='lines+markers',
            line={"color": "#36FFF9"},
            ##markers = {"color": "#17991C"},
            name="Operating Margin"
        ), go.Scatter(
            x=df['fiscalDateEnding'],
            y=df['Net Profit Margin'],
            mode='lines+markers',
            line={"color": "#38AFF5"},
            ##markers = {"color": "#17991C"},
            name="Net Profit Margin"
        ) ],
        "layout": go.Layout(
            autosize=True,
            font={"family": "Raleway", "size": 10},
            height=300,
            width=400,
            legend={
                "x": -0.09,
                "y": -0.19,
                "orientation": "h",
                "yanchor": "top",
                "font": {"size": 13}
            },
            margin={
                "r": 0,
                "t": 20,
                "b": 10,
                "l": 10,
            },
            showlegend=True,
            title="",
            hovermode="closest",
            xaxis={
                "autorange": True,
                "showline": True,
                "title": "As of Fiscal Ending Date",
                "type": "category",
            },
            yaxis={
                "autorange": True,
                ## "range": [0, 22.9789473684],
                "showgrid": True,
                "showline": True,
                "title": "",
                "type": "linear",
                "zeroline": True,
                "zerolinecolor": "Grey",
                "tickformat": ".0%"
            },
        )
    }

def balancesheet_stackbar(df):
    trace_1 = go.Bar(
        x = df['fiscalDateEnding'],
        y = df['Total Liab'],
        marker={
        "color": "#FFC112",
        "line": {
                "color": "rgb(255, 255, 255)",
                "width": 2,
                },
            },
        name = 'Total Liabilities'
    )
    trace_2 = go.Bar(
        x = df['fiscalDateEnding'],
        y = df['Total Stockholder Equity'],
        marker={
        "color": "#17991C",
        "line": {
                "color": "rgb(255, 255, 255)",
                "width": 2,
                },
            },
        name = 'Total Stockholder Equity'
    )


    trace = [trace_1, trace_2]
    layout = go.Layout(
            title = '',
            barmode='stack',
            autosize=True,
            bargap=0.35,
            font={"family": "Raleway", "size": 10},
            height=300,
            width=600,
            legend={
                "x": -0.09,
                "y": -0.19,
                "orientation": "h",
                "yanchor": "top",
                "font": {"size": 13}
            },
            margin={
                "r": 0,
                "t": 20,
                "b": 10,
                "l": 10,
            },
            showlegend=True,
            hovermode="closest",
            xaxis={
                "autorange": True,
                "showline": True,
                "title": "As of Fiscal Ending Date",
                "type": "category",
            },
            yaxis={
                "autorange": True,
                ## "range": [0, 22.9789473684],
                "showgrid": True,
                "showline": True,
                "title": "Total Assets",
                "type": "linear",
                "zeroline": False,
            },
    )
    return {
        'data': trace,
        "layout": layout
    }


def balancesheet_line(df):
    return {
        'data': [go.Scatter(
            x=df['fiscalDateEnding'],
            y=df['Cash Ratio'],
            mode='lines+markers',
            line={"color": "#FF1414"},
            ##markers = {"color": "#17991C"},
            name="Cash Ratio"
        ), go.Scatter(
            x=df['fiscalDateEnding'],
            y=df['Current Ratio'],
            mode='lines+markers',
            line={"color": "#FFAD1C"},
            ##markers = {"color": "#17991C"},
            name="Current Ratio "
        ) ],
        "layout": go.Layout(
            autosize=True,
            font={"family": "Raleway", "size": 10},
            height=300,
            width=400,
            legend={
                "x": -0.09,
                "y": -0.19,
                "orientation": "h",
                "yanchor": "top",
                "font": {"size": 13}
            },
            margin={
                "r": 0,
                "t": 20,
                "b": 10,
                "l": 10,
            },
            showlegend=True,
            title="",
            hovermode="closest",
            xaxis={
                "autorange": True,
                "showline": True,
                "title": "As of Fiscal Ending Date",
                "type": "category",
            },
            yaxis={
                "autorange": True,
                ## "range": [0, 22.9789473684],
                "showgrid": True,
                "showline": True,
                "title": "",
                "type": "linear",
                "zeroline": True,
                "zerolinecolor": "Grey",
            },
        )
    }

def cashflow_bar(df):
    return {
        'data': [go.Bar(
            x=df['fiscalDateEnding'],
            y=df['Total Cash From Operating Activities'],
            marker={
                "color": "#17991C",
                "line": {
                    "color": "rgb(255, 255, 255)",
                    "width": 2,
                },
            },
            name="Operating Cash Flow"
        ), go.Bar(
            x=df['fiscalDateEnding'],
            y=df['Free Cash Flow'],
            marker={
                "color": "#FFFA5C",
                "line": {
                    "color": "rgb(255, 255, 255)",
                    "width": 2,
                },
            },
            name="Free Cash Flow"
        )],
        "layout": go.Layout(
            autosize=True,
            bargap=0.35,
            font={"family": "Raleway", "size": 10},
            height=300,
            width=600,
            legend={
                "x": -0.09,
                "y": -0.19,
                "orientation": "h",
                "yanchor": "top",
                "font": {"size": 13}
            },
            margin={
                "r": 0,
                "t": 20,
                "b": 10,
                "l": 10,
            },
            showlegend=True,
            title="",
            hovermode="closest",
            xaxis={
                "autorange": True,
                "showline": True,
                "title": "As of Fiscal Ending Date",
                "type": "category",
            },
            yaxis={
                "autorange": True,
                ## "range": [0, 22.9789473684],
                "showgrid": True,
                "showline": True,
                "title": "",
                "type": "linear",
                "zeroline": False,
            },
        )
    }


def cashflow_line(df):
    return {
        'data': [go.Scatter(
            x=df['fiscalDateEnding'],
            y=df['OperatingCashflow/SalesRatio'],
            mode='lines+markers',
            line={"color": "#AAA3FF"},
            ##markers = {"color": "#A61FFF"},
            name="OperatingCashFlow/Sales Ratio"
        ) ],
        "layout": go.Layout(
            autosize=True,
            font={"family": "Raleway", "size": 10},
            height=300,
            width=400,
            legend={
                "x": -0.09,
                "y": -0.19,
                "orientation": "h",
                "yanchor": "top",
                "font": {"size": 13}
            },
            margin={
                "r": 0,
                "t": 20,
                "b": 10,
                "l": 10,
            },
            showlegend=True,
            title="",
            hovermode="closest",
            xaxis={
                "autorange": True,
                "showline": True,
                "title": "As of Fiscal Ending Date",
                "type": "category",
            },
            yaxis={
                "autorange": True,
                ## "range": [0, 22.9789473684],
                "showgrid": True,
                "showline": True,
                "title": "",
                "type": "linear",
                "zeroline": True,
                "zerolinecolor": "Grey",
                "tickformat": ".0%"
            },
        )
    }


## get the tickers and company name lists https://www.nasdaq.com/market-activity/stocks/screener

all_lists = pd.read_csv("https://github.com/tylerjiang1127/Stock-Tickers/blob/main/all_tickers.csv?raw=true", usecols=["Symbol","Name"])

all_lists['Name&Symbol'] = all_lists['Name'] + ' (' + all_lists['Symbol'] + ')'

ticker_options=[
        {'label': all_lists.iloc[i][2], 'value': all_lists.iloc[i][0]} for i in range(len(all_lists))
        ]

## Stock Market Live Prep

# get the realtime price and change for
# NASDAQ/Dow Jones/S&P 500/Russell: IXIC/DJI/GSPC/RUT
def market_index(name_ind):
    try:
        name = name_ind.upper()
        
        # Check cache first
        with cache_lock:
            current_time = time.time()
            cache_key = f"market_{name}"
            
            if cache_key in market_data_cache:
                cached_data, timestamp = market_data_cache[cache_key]
                if current_time - timestamp < CACHE_DURATION:
                    return cached_data
        
        # Add delay to prevent rate limiting
        time.sleep(0.5)
        
        # Use yfinance instead of web scraping for more reliable data
        ticker = yf.Ticker(f"^{name}")
        
        # Check circuit breaker
        failure_key = f"failures_{name}"
        current_time_check = time.time()
        
        if failure_key in api_failure_count:
            failure_count, last_failure_time = api_failure_count[failure_key]
            if failure_count >= API_FAILURE_THRESHOLD:
                if current_time_check - last_failure_time < API_COOLDOWN_PERIOD:
                    print(f"Circuit breaker active for {name}, using fallback")
                    return "N/A", "N/A", "Market Closed"
                else:
                    # Reset circuit breaker after cooldown
                    api_failure_count[failure_key] = (0, current_time_check)
        
        # Try to get basic info first with timeout
        try:
            hist = ticker.history(period="5d", interval="1d")
            # Reset failure count on success
            if failure_key in api_failure_count:
                api_failure_count[failure_key] = (0, current_time_check)
        except Exception as e:
            print(f"Rate limited or error for {name}: {e}")
            # Increment failure count
            if failure_key in api_failure_count:
                count, _ = api_failure_count[failure_key]
                api_failure_count[failure_key] = (count + 1, current_time_check)
            else:
                api_failure_count[failure_key] = (1, current_time_check)
            return "N/A", "N/A", "Market Closed"
        
        if hist.empty or len(hist) < 2:
            return "N/A", "N/A", "Market Closed"
            
        current_price = hist['Close'].iloc[-1]
        prev_price = hist['Close'].iloc[-2]
        change = current_price - prev_price
        change_percent = (change / prev_price) * 100
        
        # Format the values
        price = f"{current_price:.2f}"
        change_str = f"{change:+.2f} ({change_percent:+.2f}%)"
        
        # Determine market status (simplified)
        from pytz import timezone
        eastern = timezone('US/Eastern')
        now = dt.datetime.now(eastern)
        # Market is typically open 9:30 AM - 4:00 PM ET on weekdays
        if now.weekday() < 5 and (now.hour > 9 or (now.hour == 9 and now.minute >= 30)) and now.hour < 16:
            market_status = "Market Open"
        else:
            market_status = "At Close"
        
        result = (price, change_str, market_status)
        
        # Cache the result
        with cache_lock:
            market_data_cache[cache_key] = (result, current_time)
            
        return result
        
    except Exception as e:
        print(f"Error getting market data for {name_ind}: {e}")
        return "N/A", "N/A", "Market Closed"

def update_market_index():
    index_list = ['IXIC','DJI','GSPC','RUT']
    column_names = ['Name', 'Price', 'Change', 'Status']
    df = pd.DataFrame(columns = column_names)
    
    # Check if we have recent cached data for all indices
    with cache_lock:
        current_time = time.time()
        all_cached = True
        cached_results = {}
        
        for ind in index_list:
            cache_key = f"market_{ind}"
            if cache_key in market_data_cache:
                cached_data, timestamp = market_data_cache[cache_key]
                if current_time - timestamp < CACHE_DURATION:
                    cached_results[ind] = cached_data
                else:
                    all_cached = False
            else:
                all_cached = False
        
        # If all data is cached and fresh, use cached data
        if all_cached:
            for ind in index_list:
                price, change, market_status = cached_results[ind]
                row = pd.DataFrame([[ind, price, change, market_status]], columns = column_names)
                df = pd.concat([df,row], ignore_index = True)
            return df
    
    # Otherwise, fetch new data with delays
    for i, ind in enumerate(index_list):
        try:
            # Add progressive delay to spread out API calls
            if i > 0:
                time.sleep(2)  # 2 second delay between each index
                
            price, change, market_status = market_index(ind)
            row = pd.DataFrame([[ind, price, change, market_status]], columns = column_names)
            df = pd.concat([df,row], ignore_index = True)
        except Exception as e:
            print(f"Error updating market index for {ind}: {e}")
            # Add default row if there's an error
            row = pd.DataFrame([[ind, "N/A", "N/A", "Market Closed"]], columns = column_names)
            df = pd.concat([df,row], ignore_index = True)
    
    return df

## get the 1minute level data for the most recent trading day
def live_price_df(name):
    try:
        # Handle empty or None ticker names
        if not name or name.strip() == '':
            print(f"Empty ticker name provided")
            return pd.DataFrame(), pd.DataFrame()
        
        # Check cache first for live data
        with cache_lock:
            current_time = time.time()
            cache_key = f"live_{name}"
            
            if cache_key in market_data_cache:
                cached_data, timestamp = market_data_cache[cache_key]
                # Use shorter cache for live data (30 seconds)
                if current_time - timestamp < 30:
                    return cached_data
        
        # Add delay to prevent rate limiting
        time.sleep(1)
            
        step = 0
        ticker = yf.Ticker(name)
        today = dt.datetime.today()

        start = today
        end   = start + dt.timedelta(days = 1)
        start_date, end_date = start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
        
        try:
            df = ticker.history(start=start_date, end=end_date, interval="1m")
        except Exception as e:
            print(f"Failed to get ticker '{name}' reason: {e}")
            # Return cached data if available, else empty
            with cache_lock:
                if cache_key in market_data_cache:
                    return market_data_cache[cache_key][0]
            return pd.DataFrame(), pd.DataFrame()
            
        ## use step to judge whether the ticker is valid or not, if ticker is not a issue we use this while function to find the last trade day data
        while df.empty:
            start, end = start - dt.timedelta(days = 1), end - dt.timedelta(days = 1)
            start_date, end_date = start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
            try:
                df = ticker.history(start=start_date, end=end_date, interval="1m")
            except Exception as e:
                print(f"${name}: possibly delisted; no price data found  (1m {start_date} -> {end_date})")
            step = step+1
            if step > 5:
                break

        prev_start = start - dt.timedelta(days = 1)
        prev_end   = prev_start + dt.timedelta(days = 1)
        prev_start_date, prev_end_date = prev_start.strftime("%Y-%m-%d"), prev_end.strftime("%Y-%m-%d")
        
        try:
            prev_df = ticker.history(start=prev_start_date, end=prev_end_date, interval="1m")
        except Exception as e:
            print(f"Error getting previous day data for {name}: {e}")
            prev_df = pd.DataFrame()
            
        ## if the ticker has issue, the step must >5, then prev_df will be set empty; if the ticker is not issue, we use while function to find the pre available trade day data
        while prev_df.empty:
            if step > 5:
                break
            else:
                prev_start, prev_end = prev_start - dt.timedelta(days = 1), prev_end - dt.timedelta(days = 1)
                prev_start_date, prev_end_date = prev_start.strftime("%Y-%m-%d"), prev_end.strftime("%Y-%m-%d")
                try:
                    prev_df = ticker.history(start=prev_start_date, end=prev_end_date, interval="1m")
                except Exception as e:
                    print(f"${name}: possibly delisted; no price data found  (1m {prev_start_date} -> {prev_end_date})")
                prev_attempts += 1

        result = (df, prev_df)
        
        # Cache the result
        with cache_lock:
            market_data_cache[cache_key] = (result, current_time)
            
        return result
        
    except Exception as e:
        print(f"Error in live_price_df for ticker '{name}': {e}")
        return pd.DataFrame(), pd.DataFrame()

## set up color difference
def live_price_color(df,prev_df):
    benchmark = prev_df.iloc[-1]['Close']
    if df.iloc[-1]['Close']>benchmark:
        color = 'green'
    elif df.iloc[-1]['Close']<benchmark:
        color = 'red'
    else:
        color = 'grey'
    return color

def live_price_fig(ticker):
    df, prev_df = live_price_df(ticker)

    if df.empty is False and prev_df.empty is False:
        line = go.Scatter(
                    x = df.index.strftime("%Y-%m-%d %H:%M:%S"),
                    y = df['Close'],
                    fill = 'tonexty',
                    hovertemplate = '$%{y:.2f}',
                    mode='lines',
                    marker={"color": live_price_color(df,prev_df)},
                    showlegend = False,
                    name = ticker
        )
        benchmark = go.Scatter(
                    x = df.index.strftime("%Y-%m-%d %H:%M:%S"),
                    y = np.array([prev_df.iloc[-1]['Close']]*len(df)),
                    hovertemplate = '$%{y:.2f}',
                    #fillcolor = live_price_color(df,prev_df),
                    mode='lines',
                    line=dict(color='black', dash = 'dash'),
                    showlegend = False,
                    name = "Pre-Day Close"
        )

        fig = go.Figure()
        fig.add_trace(benchmark)
        fig.add_trace(line)
        '''fig.add_shape(type='line',
                        x0=df.index.strftime("%Y-%m-%d %H:%M:%S")[0],
                        y0=prev_df.iloc[-1]['Close'],
                        x1=df.index.strftime("%Y-%m-%d %H:%M:%S")[-1],
                        y1=prev_df.iloc[-1]['Close'],
                        line=dict(color='black', dash = 'dash'),
                        fillcolor = "yellow",
                        xref='x',
                        yref='y'
        )'''

        fig.update_layout(
                          plot_bgcolor = '#DEDEDE',
                          hovermode="x unified",
                          xaxis = dict(
                                        showspikes = True,
                                        showgrid = True,
                                        spikemode = 'across',
                                        spikesnap = 'hovered data'
                                      ),
                          yaxis=dict(
                                      showspikes = True,
                                      showgrid = True,
                                      spikemode = 'across',
                                      spikesnap = 'hovered data',
                                      tickformat="$,.2f"))
    else:
        fig = go.Figure()
        fig.update_layout(title = 'Please Search a Valid Stock',
                          plot_bgcolor = '#DEDEDE',
                          hovermode="x unified",
                          xaxis = dict(
                                        showspikes = True,
                                        showgrid = True,
                                        spikemode = 'across',
                                        spikesnap = 'hovered data'
                                      ),
                          yaxis=dict(
                                      showspikes = True,
                                      showgrid = True,
                                      spikemode = 'across',
                                      spikesnap = 'hovered data',
                                      tickformat="$,.2f"))

    return fig

def market_index_style(change):
    green_style = {'color' : 'green', 'font-size': '15px', 'font-weight': 'bold'}
    red_style   = {'color' : 'red', 'font-size': '15px', 'font-weight': 'bold'}
    grey_style   = {'color' : 'grey', 'font-size': '15px', 'font-weight': 'bold'}
#     if change[0] == '-':
#         return red_style
#     elif change[0] == '+':
#         return green_style
    if '-' in change:
        return red_style
    elif '+' in change:
        return green_style
    else:
        return grey_style


cards = [
        # NASDAQ Part
        dbc.Card(
            dbc.CardBody(
                [
                    html.Div("NASDAQ",
                           style = {'color' : 'black', 'font-size': '1.8rem', 'font-weight': 'bold'}),
                    html.Div(id="nasdaq_price"),
                    html.Div(id="nasdaq_change"),
                ]
            ),
            className="attributes_card three columns"),

        # DJI Part
        dbc.Card(
            dbc.CardBody(
                [
                    html.Div("DOW JONES",
                           style = {'color' : 'black', 'font-size': '1.8rem', 'font-weight': 'bold'}),
                    html.Div(id="dji_price"),
                    html.Div(id="dji_change"),
                ]
            ),
            className="attributes_card three columns"),

        # S&P Part
        dbc.Card(
            dbc.CardBody(
                [
                    html.Div("S&P 500",
                           style = {'color' : 'black', 'font-size': '1.8rem', 'font-weight': 'bold'}),
                    html.Div(id="sp_price"),
                    html.Div(id="sp_change"),
                ]
            ),
            className="attributes_card three columns"),

        # Russell 2000 Part
        dbc.Card(
            dbc.CardBody(
                [
                    html.Div("Russell 2000",
                           style = {'color' : 'black', 'font-size': '1.8rem', 'font-weight': 'bold'}),
                    html.Div(id="rut_price"),
                    html.Div(id="rut_change"),
                ]
            ),
            className="attributes_card three columns"),
    ]



## Pages Layout Create Functions
def fundamental_create_layout(app):
    # Page layouts
    return html.Div(
        [
            dcc.Loading(id = 'loading-output1', children=html.Div(id="show_overview"), type = 'default ', color= "#17991C", fullscreen = False),

            html.Br([]),
            html.Br([]),

            dcc.RadioItems(id = 'Year_Quarter',
                           labelStyle = {"display": "inline-block", 'font-size': '1.2rem'},
                           value = 'Yearly',
                           options = [{'label': 'Yearly View', 'value': 'Yearly'}, {'label': 'Quarterly View', 'value': 'Quarterly'}],
                           className = 'row'),
            dcc.Loading(id = 'loading-output2', children=html.Div(id="show_year_quarter_view"), type = 'default ', color= "#17991C", fullscreen = False),


        ], className = "sub_page")

def technical_create_layout(app):

    return  [html.Div([
                html.P("Select Date Range", className = 'fix_label', style = {'font-size': '2rem','margin-top': '10px'}),
                dcc.DatePickerRange(
                    id='my-date-picker-range',
                    min_date_allowed=dt.date(2000, 1, 1),
                    max_date_allowed=dt.date.today(),
                    initial_visible_month=dt.date.today(), #- relativedelta(years = 1),
                    start_date = dt.date.today() - relativedelta(years = 1),
                    end_date=dt.date.today(),
                    className = 'dcc_compon'
                )
            ], style = {'borderBottom': 'LightGrey solid', 'font-weight': 'bold'}),
            html.Div(
                    [
                        dcc.Loading(dcc.Graph(id = 'technical chart', className = "sub_page"), type = 'default', color= "#17991C", fullscreen = False),

                    ], className = "sub_page")]

def marketlive_create_layout(app):
    return [html.Br([]),
            # Current Date Time
            html.H5(id = 'datetime',
                   style = {'color' : 'Grey', 'font-size': '1.8rem','font-weight': 'bold'}),
            html.Br([]),
            # Current Market Status
            html.H5(id = 'marketstatus',
                   style = {'color' : 'Grey', 'font-size': '1.8rem','font-weight': 'bold'}),
            html.Br([]),
            # Update Indexes Card
            dbc.Container(cards),
            html.Br([]),
            # Update the Live Charts for searched ticker
            html.H5("Stock Live Price", className = "subtitle row", style = {'borderTop': '#17991C solid', 'font-weight': 'bold'}),
            html.Div(
            [
            dcc.Loading(dcc.Graph(id = 'stock live'), type = 'default', color= "#17991C", fullscreen = False),
            ]),
            html.Br([]),
            # Update the Live Charts for All Market Index
            html.H5("U.S. Market Indexes", className = "subtitle row", style = {'borderTop': '#17991C solid', 'font-weight': 'bold'}),
            html.Div([
                      dcc.Loading(dcc.Graph(id = 'NASDAQ',style = {'borderBottom': 'thin lightgrey solid'}), type = 'default', color= "#17991C", fullscreen = False),

                      dcc.Loading(dcc.Graph(id = 'DJI',style = {'borderBottom': 'thin lightgrey solid'}), type = 'default', color= "#17991C", fullscreen = False),

                      dcc.Loading(dcc.Graph(id = 'SP500',style = {'borderBottom': 'thin lightgrey solid'}), type = 'default', color= "#17991C", fullscreen = False),

                      dcc.Loading(dcc.Graph(id = 'RUT2000',style = {'borderBottom': 'thin lightgrey solid'}), type = 'default', color= "#17991C", fullscreen = False),

                     ], ),
        ]



## KDJ Formula
def KDJ(H, L, C, df):
    L9 = L.rolling(9).min()
    H9 = H.rolling(9).max()
    RSV = 100 * ((C - L9) / (H9 - L9)).values

    k0 = 50
    k_out = []
    for j in range(len(RSV)):
        if RSV[j] == RSV[j]: # check for nan
            k0 = 1/3 * RSV[j] + 2/3 * k0
            k_out.append(k0)
        else:
            k_out.append(np.nan)

    d0 = 50
    d_out = []
    for j in range(len(RSV)):
        if k_out[j] == k_out[j]:
            d0 =1/3 * k_out[j] + 2/3 * d0
            d_out.append(d0)
        else:
            d_out.append(np.nan)

    J = (3 * np.array(k_out)) - (2 * np.array(d_out))

    kdj = pd.concat([pd.Series(k_out, name = 'K'), pd.Series(d_out, name = 'D'), pd.Series(J, name = 'J')], axis=1)
    kdj.set_index(df.index, inplace=True)
    return kdj

def get_indicators(df):
    # 创建dataframe
    tech = pd.DataFrame()

    #获取macd
    tech["macd"], tech["macd_signal"], tech["macd_hist"] = talib.MACD(df['Close'])
    tech["macd_hist"] = tech["macd_hist"]*2

    #获取均线(MA5, MA10, MA20, MA30, MA60, MA120, MA250)
    tech["ma5"]   = talib.MA(df["Close"], timeperiod=5)
    tech["ma10"]  = talib.MA(df["Close"], timeperiod=10)
    tech["ma20"]  = talib.MA(df["Close"], timeperiod=20)
    tech["ma30"]  = talib.MA(df["Close"], timeperiod=30)
    tech["ma60"]  = talib.MA(df["Close"], timeperiod=60)
    tech["ma120"] = talib.MA(df["Close"], timeperiod=120)
    tech["ma250"] = talib.MA(df["Close"], timeperiod=250)

    #获取rsi
    tech["rsi"] = talib.RSI(df["Close"])

    #KDJ
    H = df['High']
    L = df['Low']
    C = df['Close']
    kdj = KDJ(H, L, C, df)
    tech["K"] = kdj['K']
    tech["D"] = kdj['D']
    tech["J"] = kdj['J']

    return tech

## set up color difference for Up&Down day price change
def vol_color(df):
    color = np.array(['green']*len(df))
    color[df['Close']>df['Open']] = 'green'
    color[df['Close']<df['Open']] = 'red'
    color[df['Close']==df['Open']] = 'grey'
    return color

def macd_hist_color(tech):
    color = np.array(['green']*len(tech))
    color[tech['macd_hist']>0] = 'green'
    color[tech['macd_hist']<0] = 'red'
    color[tech['macd_hist']==0] = 'grey'
    return color


## Layout Design and Interactive Design

app = dash.Dash(__name__, suppress_callback_exceptions=True)

app.title = "Lazyman Stock Research"

app.layout = html.Div([
    # Interval - Increased intervals to reduce API calls
    dcc.Interval(
        id='interval-component1',
        interval=1*30000, # 30 seconds instead of 5 seconds
        n_intervals=0),
    dcc.Interval(
        id='interval-component2',
        interval=1*1000*180, # 3 minutes instead of 1 minute
        n_intervals=0),
    # Header row
    html.Div(
        [
            html.H2("Lazyman Stock Research", className = "five columns main-title"),
            html.Div([
                html.Br([]),
                html.Br([]),
                html.H5("Created by Tyler Jiang",
                        style = {'color' : '#999999', 'font-size': '1.4rem',
                                 'borderBottom': 'lightgrey solid', 'font-weight': 'bold'})
                     ], className = "five columns"),
            html.Img(src='https://upload.wikimedia.org/wikipedia/en/f/f0/WallStreetBets.png', className = "two column logo"),
        ], className = "row"),
    # Search Bar row
    html.Div(
        [
            html.Div([## dcc.Input(id = 'enter_ticker', placeholder='Enter Ticker here...(eg.AAPL)', value='', type = 'text'),
            dcc.Dropdown(id='enter_ticker',
            options=ticker_options,
            optionHeight=35,                    #height/space between dropdown options
            value='',                    #dropdown value selected automatically when page loads
            disabled=False,                     #disable dropdown value selection
            multi=False,                        #allow multiple dropdown values to be selected
            searchable=True,                    #allow user-searching of dropdown values
            search_value='',                    #remembers the value searched in dropdown
            placeholder='Search the Stock...(eg. enter AAPL or Apple)',     #gray, default text shown when no option is selected
            clearable=True,                     #allow user to removes the selected value
            #style={'width':"50%"},             #use dictionary to define CSS styles of your dropdown,
            # className='select_box',           #activate separate CSS document in assets folder
            # persistence=True,                 #remembers dropdown value. Used with persistence_type
            # persistence_type='memory'         #remembers dropdown value selected until...
            )], className = 'four columns'),
            html.Div([html.Button(id='submit-button', n_clicks=0, children='SEARCH')], className = 'three columns'),

        ], className = "row"),
    # Menu
    html.Div(
        [
            dcc.Link(
                "Stock Market Live Price",
                href="/marketlive",
                className="tab first",
            ),
            dcc.Link(
                "Fundamentals Overview",
                href="/fundamental",
                className="tab",
            ),
            dcc.Link(
                "Technical Charts",
                href="/technical",
                className="tab",
            ),
        ],
        className="row all-tabs", style = {'borderBottom': 'thin #17991C solid'}
    ),

    # Content
    html.Div(
        [dcc.Location(id="url", refresh=False), html.Div(id="page-content")]
    )

], className = "page")

## Click the Link Interaction
@app.callback(Output("page-content", "children"), [Input("url", "pathname")])
def display_page(pathname):
    if pathname=="/fundamental":
        return fundamental_create_layout(app)
    elif pathname=="/technical":
        return technical_create_layout(app)
    elif pathname=="/marketlive" or pathname is None:
        return marketlive_create_layout(app)
    else:
        return marketlive_create_layout(app)

##
@app.callback(
    Output('show_overview', 'children'),
    [Input('submit-button', 'n_clicks')],
    [State('enter_ticker', 'value')]
)
def update_overview(n_clicks, input_value):
    # Handle empty or None input values
    if not input_value or input_value.strip() == '':
        return html.Div([
            html.H5("Please select a stock ticker to view company information.", 
                   style={'color': 'grey', 'text-align': 'center', 'margin': '50px'})
        ])
    
    input_value = input_value.upper().strip()
    company_info, company_desc = get_info(input_value)

    if company_info.empty:
        return html.Div([
                         html.Div([
                                   html.H5("Company Information", className = "subtitle padded"),
                                   html.Table(make_dash_table(company_info))
                                   ], className = 'five columns'),
                         html.Div([
                                   html.H5("Company Description", className = "subtitle padded"),
                                   html.Div([html.P(company_desc, style={"color": "#ffffff"})], className = 'product')
                                   ], className = 'seven columns')
                         ], className = 'row', style = {'borderBottom': 'thin lightgrey solid'})
    else:
        # Content Row 1 -- Company Information & Company Description
        return html.Div([
                          html.Div([
                                    html.H5("Company Information", className = "subtitle padded"),
                                    html.Table(make_dash_table(company_info))
                                    ], className = 'five columns'),
                          html.Div([
                                    html.H5("Company Description", className = "subtitle padded"),
                                    html.Div([html.P(company_desc, style={"color": "#ffffff"})], className = 'product')
                                    ], className = 'seven columns')
                         ], className = 'row', style = {'borderBottom': 'thin lightgrey solid'})

## get the Yearly/Quarterly View for specific ticker
@app.callback(
    Output('show_year_quarter_view', 'children'),
    [Input('Year_Quarter', 'value')],
    [State('enter_ticker', 'value')],
    suppress_callback_exceptions=True
)
def update_year_quarter_view(Year_Quarter, input_value):
    # Handle empty or None input values
    if not input_value or input_value.strip() == '':
        return []
    
    # Content 2 -- Last Quarter Fundamentals Results
    input_value = input_value.upper().strip()
    IncomeStatement, BalanceSheet, CashFlow, lastquarter1, lastquarter2, lastquarter3, currency = fundamentals_tables(input_value, Year_Quarter)

    if IncomeStatement.empty:
        return []
    else:
        return  [
                html.H5("Most Recent Fundamentals Metrics", className = "subtitle row"),
                html.Div([
                          html.Div([
                                    html.H6("Income Statement (as of {})".format(IncomeStatement.iloc[0][0]), className = "sub_subtitle padded", style = {'font-weight': 'bold'}),
                                    html.Table(make_dash_table(lastquarter1))
                                    ], className = 'four columns'),

                          html.Div([
                                    html.H6("Balance Sheet (as of {})".format(BalanceSheet.iloc[0][0]), className = "sub_subtitle padded", style = {'font-weight': 'bold'}),
                                    html.Table(make_dash_table(lastquarter2))
                                    ], className = 'four columns'),

                          html.Div([
                                    html.H6("Cash Flow (as of {})".format(CashFlow.iloc[0][0]), className = "sub_subtitle padded", style = {'font-weight': 'bold'}),
                                    html.Table(make_dash_table(lastquarter3))
                                    ], className = 'four columns'),
                         ], className = 'row', style = {'borderBottom': 'thin lightgrey solid'}),

                html.Br([]),
                html.Br([]),

                # Content Row 3 -- Past 2 Years Income Statement Figures
                html.H5("Profitability Trend", className = "subtitle row"),
                html.Div([
                          dcc.Graph(id = 'profitability bar',
                                    figure = incomestatement_bar(IncomeStatement.iloc[::-1])
                                    , className = 'seven columns'),

                          dcc.Graph(id = 'profitability line',
                                    figure = incomestatement_line(IncomeStatement.iloc[::-1])
                                    , className = 'five columns'),

                         ], className = 'row', style = {'borderBottom': 'thin lightgrey solid'}),

                html.Br([]),
                html.Br([]),

                # Content Row 4 -- Past 2 Years Debt-Asset Figures
                html.H5("Debt-Asset Trend", className = "subtitle row"),
                html.Div([
                          dcc.Graph(id = 'Debt-Asset bar',
                                    figure = balancesheet_stackbar(BalanceSheet.iloc[::-1])
                                    , className = 'seven columns'),

                          dcc.Graph(id = 'Debt-Asset line',
                                    figure = balancesheet_line(BalanceSheet.iloc[::-1])
                                    , className = 'five columns'),

                         ], className = 'row', style = {'borderBottom': 'thin lightgrey solid'}),

                html.Br([]),
                html.Br([]),

                # Content Row 5 -- Past 2 Years Cash Flow Figures
                html.H5("Cash Flow Trend", className = "subtitle row"),
                html.Div([
                          dcc.Graph(id = 'cashflow bar',
                                    figure = cashflow_bar(CashFlow.iloc[::-1])
                                    , className = 'seven columns'),

                          dcc.Graph(id = 'cashflow line',
                                    figure = cashflow_line(CashFlow.iloc[::-1])
                                    , className = 'five columns'),

                         ], className = 'row', style = {'borderBottom': 'thin lightgrey solid'})
        ]

## after the another search, reset the year/quarter button
@app.callback(Output('Year_Quarter','value'),
             [Input('submit-button','n_clicks')])
def update(reset):
    return 'Yearly'

## get the technical charts based on the ticker
@app.callback(
    Output('technical chart', 'figure'),
    [Input('submit-button', 'n_clicks')],
    [State('enter_ticker', 'value'), State('my-date-picker-range','start_date'), State('my-date-picker-range','end_date')],
    suppress_callback_exceptions=True
)
def update_chart(n_clicks, input_value, start_date, end_date):
    # Handle empty or None input values
    if not input_value or input_value.strip() == '':
        fig = go.Figure()
        fig.update_layout(title='Please select a stock ticker to view technical chart',
                         plot_bgcolor='White', paper_bgcolor='White')
        return fig
        
    input_value = input_value.upper().strip()
    ticker = yf.Ticker(input_value)

    ## set up timeframe
    start_date_object, end_date_object = dt.date.fromisoformat(start_date), dt.date.fromisoformat(end_date)
    end_date_object = end_date_object + dt.timedelta(days=1)
    start_date, end_date = start_date_object.strftime("%Y-%m-%d"), end_date_object.strftime("%Y-%m-%d")

    ## get the historical stock data for this ticker and also this ticker's info
    df = ticker.history(start=start_date, end=end_date, interval="1d")
    ticker_info = ticker.info

    ## get the technical
    tech_ind = get_indicators(df)


    trace_1 = go.Candlestick(
                x = df.reset_index(inplace=False)['Date'],
                open = df['Open'],
                close = df['Close'],
                high = df['High'],
                low = df['Low'],
                showlegend = False,
                name = ''
            )
    trace_1_ma5 = go.Scatter(
                x = df.reset_index(inplace=False)['Date'],
                y = tech_ind['ma5'],
                mode='lines',
                line={"color": "#A83838",
                      "width": 0.85},
                showlegend = True,
                name = "MA5"
    )
    trace_1_ma10 = go.Scatter(
                x = df.reset_index(inplace=False)['Date'],
                y = tech_ind['ma10'],
                mode='lines',
                line={"color": "#F09A16",
                      "width": 0.85},
                showlegend = True,
                name = "MA10"
    )
    trace_1_ma20 = go.Scatter(
                x = df.reset_index(inplace=False)['Date'],
                y = tech_ind['ma20'],
                mode='lines',
                line={"color": "#EFF048",
                     "width": 0.85},
                showlegend = True,
                name = "MA20"
    )
    trace_1_ma30 = go.Scatter(
                x = df.reset_index(inplace=False)['Date'],
                y = tech_ind['ma30'],
                mode='lines',
                line={"color": "#5DF016",
                     "width": 0.85},
                showlegend = True,
                name = "MA30"
    )
    trace_1_ma60 = go.Scatter(
                x = df.reset_index(inplace=False)['Date'],
                y = tech_ind['ma60'],
                mode='lines',
                line={"color": "#13C3F0",
                     "width": 0.85},
                showlegend = True,
                name = "MA60"
    )
    trace_1_ma120 = go.Scatter(
                x = df.reset_index(inplace=False)['Date'],
                y = tech_ind['ma120'],
                mode='lines',
                line={"color": "#493CF0",
                     "width": 0.85},
                showlegend = True,
                name = "MA120"
    )
    trace_1_ma250 = go.Scatter(
                x = df.reset_index(inplace=False)['Date'],
                y = tech_ind['ma250'],
                mode='lines',
                line={"color": "#F000DF",
                     "width": 0.85},
                showlegend = True,
                name = "MA250"
    )



    trace_2 = go.Bar(
                x = df.reset_index(inplace=False)['Date'],
                y = df['Volume'],
                marker={
                    "color": vol_color(df),
                    "line": {
                        "color": "rgb(255, 255, 255)",
                        "width": 0.1,
                    }},
                showlegend = False,
                name = 'Volume'
            )


    trace_3 = go.Scatter(
                x = df.reset_index(inplace=False)['Date'],
                y = tech_ind['rsi'],
                mode='lines',
                line={"color": "Orange"},
                showlegend = False,
                name = "RSI"
    )

    trace_4a = go.Bar(
                x = df.reset_index(inplace=False)['Date'],
                y = tech_ind['macd_hist'],
                width = 10,
                marker={
                    "color": macd_hist_color(tech_ind),
                    "line": {
                        "color": "rgb(255, 255, 255)",
                        "width": 0,
                    }
                        },
                showlegend = False,
                name = 'MACD Hist'
                )
    trace_4b = go.Scatter(
                x = df.reset_index(inplace=False)['Date'],
                y = tech_ind['macd'],
                mode='lines',
                line={"color": "orange",
                      "width": 0.85},
                showlegend = False,
                name = "MACD"
                )
    trace_4c = go.Scatter(
                x = df.reset_index(inplace=False)['Date'],
                y = tech_ind['macd_signal'],
                mode='lines',
                line={"color": "deepskyblue",
                      "width": 0.85},
                showlegend = False,
                name = "MACD_Signal"
                )

    trace_5a = go.Scatter(
                x = df.reset_index(inplace=False)['Date'],
                y = tech_ind['K'],
                mode='lines',
                line={"color": "gold",
                      "width": 0.85},
                showlegend = False,
                name = "K"
                )
    trace_5b = go.Scatter(
                x = df.reset_index(inplace=False)['Date'],
                y = tech_ind['D'],
                mode='lines',
                line={"color": "blue",
                      "width": 0.85},
                showlegend = False,
                name = "D"
                )
    trace_5c = go.Scatter(
                x = df.reset_index(inplace=False)['Date'],
                y = tech_ind['J'],
                mode='lines',
                line={"color": "purple",
                      "width": 0.85},
                showlegend = False,
                name = "J"
                )
    trace_5_line20 = go.Scatter(
                x = df.reset_index(inplace=False)['Date'],
                y = np.array(len(df)*[20]),
                mode='lines',
                line={"color": "grey",
                      "width": 1,
                     "dash": "dash"},
                showlegend = False,
                name = ""
                )
    trace_5_line50 = go.Scatter(
                x = df.reset_index(inplace=False)['Date'],
                y = np.array(len(df)*[50]),
                mode='lines',
                line={"color": "grey",
                      "width": 1,
                     "dash": "dash"},
                showlegend = False,
                name = ""
                )
    trace_5_line80 = go.Scatter(
                x = df.reset_index(inplace=False)['Date'],
                y = np.array(len(df)*[80]),
                mode='lines',
                line={"color": "grey",
                      "width": 1,
                      "dash": "dash"},
                showlegend = False,
                name = ""
                )

    fig = make_subplots(rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                        row_width=[0.12, 0.1, 0.08, 0.12, 0.38]
                        #specs=[[{"rowspan": 3}],
                              #[None],
                              #[None],
                              #[{"rowspan": 2}],
                              #[None],
                              #[{}],
                              #[{}]]
                              )

    fig.add_trace(trace_1,row=1,col=1)
    fig.add_trace(trace_1_ma5,row=1,col=1)
    fig.add_trace(trace_1_ma10,row=1,col=1)
    fig.add_trace(trace_1_ma20,row=1,col=1)
    fig.add_trace(trace_1_ma30,row=1,col=1)
    fig.add_trace(trace_1_ma60,row=1,col=1)
    fig.add_trace(trace_1_ma120,row=1,col=1)
    fig.add_trace(trace_1_ma250,row=1,col=1)

    fig.add_trace(trace_4a,row=2,col=1)
    fig.add_trace(trace_4b,row=2,col=1)
    fig.add_trace(trace_4c,row=2,col=1)

    fig.add_trace(trace_2,row=3,col=1)
    fig.add_trace(trace_3,row=4,col=1)

    fig.add_trace(trace_5a,row=5,col=1)
    fig.add_trace(trace_5b,row=5,col=1)
    fig.add_trace(trace_5c,row=5,col=1)
    fig.add_trace(trace_5_line20,row=5,col=1)
    fig.add_trace(trace_5_line50,row=5,col=1)
    fig.add_trace(trace_5_line80,row=5,col=1)

    # build complete timepline from start date to end date
    dt_all = pd.date_range(start=df.reset_index()['Date'].iloc[0],end=df.reset_index()['Date'].iloc[-1])

    # retrieve the dates that ARE in the original datset
    dt_obs = [d.strftime("%Y-%m-%d") for d in pd.to_datetime(df.reset_index()['Date'])]

    # define dates with missing values
    dt_breaks = [d for d in dt_all.strftime("%Y-%m-%d").tolist() if not d in dt_obs]

    fig.update_xaxes(rangebreaks=[dict(values=dt_breaks)])
    fig.update_layout(title = '{}'.format(ticker_info['shortName']),
                      autosize=True,
                      font={"family": "Raleway", "size": 12},
                      hovermode="x unified",
                      hoverlabel=dict(bgcolor = 'White',
                                      bordercolor = '#17991C',
                                      ),
                      xaxis = dict(
                                    showspikes = True,
                                    showgrid = True,
                                    spikemode = 'across+toaxis',
                                    spikesnap = 'cursor'
                                  ),
                      plot_bgcolor = 'White',
                      paper_bgcolor= 'White',
                      height = 1400,
                      width = 1000,
                     )
    # fig.update_xaxes(matches='x')
    fig.update_traces(xaxis='x',
                      opacity = 0.8,
                      hoverinfo = "all",
                      )

    fig.update_xaxes(autorange = True,
                     showline = True,
                     #title = "Date",
                     zeroline = True,
                     rangeslider_visible = False,
                     rangeselector = dict(
                     buttons = list([
                     dict(count = 1, label = '1M', step = 'month', stepmode = 'backward'),
                     dict(count = 3, label = '3M', step = 'month', stepmode = 'backward'),
                     dict(count = 6, label = '6M', step = 'month', stepmode = 'backward'),
                     dict(count = 1, label = 'YTD', step = 'year', stepmode = 'todate'),
                     dict(count = 1, label = '1Y', step = 'year', stepmode = 'backward'),
                     dict(step = 'all')])),
                     type="date",
                     showticklabels=True,
                     linewidth=1.5, linecolor='LightGrey',
                     mirror = True,
                     row = 1, col = 1)
    fig.update_yaxes(autorange = True,
                     tickprefix = '$',
                     showgrid = True,
                     gridcolor= 'LightBlue',
                     showline = True,
                     title = "Stock Price",
                     type = 'linear',
                     zeroline = True,
                     linewidth=1.5, linecolor='LightGrey',
                     mirror = True,
                     row = 1, col = 1)

    fig.update_xaxes(autorange = True,
                     showline = True,
                     #title = "Date",
                     type = "date",
                     showticklabels=True,
                     linewidth=1.5, linecolor='LightGrey',
                     mirror = True,
                     row = 2, col = 1)
    fig.update_yaxes(autorange = True,
                     #tickprefix = '$',
                     showgrid = True,
                     gridcolor= 'LightBlue',
                     showline = True,
                     title = "MACD",
                     type = 'linear',
                     zeroline = True,
                     zerolinecolor = 'Black',
                     zerolinewidth = 0.5,
                     linewidth=1.5, linecolor='LightGrey',
                     mirror = True,
                     row = 2, col = 1)

    fig.update_xaxes(autorange = True,
                     showline = True,
                     #title = "Date",
                     type = "date",
                     showticklabels=True,
                     linewidth=1.5, linecolor='LightGrey',
                     mirror = True,
                     row = 3, col = 1)
    fig.update_yaxes(autorange = True,
                     #tickprefix = '$',
                     showgrid = True,
                     gridcolor= 'LightBlue',
                     showline = True,
                     title = "Volume",
                     type = 'linear',
                     zeroline = True,
                     zerolinecolor = 'Black',
                     zerolinewidth = 0.5,
                     linewidth=1.5, linecolor='LightGrey',
                     mirror = True,
                     row = 3, col = 1)

    fig.update_xaxes(autorange = True,
                     showline = True,
                     #title = "Date",
                     type = "date",
                     showticklabels=True,
                     linewidth=1.5, linecolor='LightGrey',
                     mirror = True,
                     row = 4, col = 1)
    fig.update_yaxes(autorange = True,
                     #tickprefix = '$',
                     showgrid = True,
                     gridcolor= 'LightBlue',
                     showline = True,
                     title = "RSI",
                     type = 'linear',
                     zeroline = True,
                     zerolinecolor = 'Black',
                     zerolinewidth = 0.5,
                     linewidth=1.5, linecolor='LightGrey',
                     mirror = True,
                     row = 4, col = 1)

    fig.update_xaxes(autorange = True,
                     showline = True,
                     #title = "Date",
                     type = "date",
                     showticklabels=True,
                     linewidth=1.5, linecolor='LightGrey',
                     mirror = True,
                     row = 5, col = 1)
    fig.update_yaxes(autorange = True,
                     #tickprefix = '$',
                     showgrid = False,
                     #gridcolor= 'LightBlue',
                     showline = True,
                     tickmode = 'array',
                     tickvals = [20, 50, 80],
                     title = "KDJ",
                     type = 'linear',
                     zeroline = False,
                     #zerolinecolor = 'Black',
                     #zerolinewidth = 0.5,
                     linewidth=1.5, linecolor='LightGrey',
                     mirror = True,
                     row = 5, col = 1)
    return fig

## Update the Live data for Searched Stock and Market Index

@app.callback([Output('nasdaq_price', 'children'), Output('nasdaq_change', 'children'),
               Output('dji_price', 'children')   , Output('dji_change', 'children'),
               Output('sp_price', 'children')    , Output('sp_change', 'children'),
               Output('rut_price', 'children')   , Output('rut_change', 'children'),
               Output('nasdaq_price', 'style')   , Output('nasdaq_change', 'style'),
               Output('dji_price', 'style')      , Output('dji_change', 'style'),
               Output('sp_price', 'style')       , Output('sp_change', 'style'),
               Output('rut_price', 'style')      , Output('rut_change', 'style'),
               Output('datetime', 'children')    , Output('marketstatus','children')],
               Input('interval-component1', 'n_intervals'),
               suppress_callback_exceptions=True)
def update_indexes(n):
    df = update_market_index()
    nasdaq_price  = df.iloc[0][1]
    nasdaq_change = df.iloc[0][2]
    dji_price     = df.iloc[1][1]
    dji_change    = df.iloc[1][2]
    sp_price      = df.iloc[2][1]
    sp_change     = df.iloc[2][2]
    rut_price     = df.iloc[3][1]
    rut_change    = df.iloc[3][2]

    nasdaq_price_style, nasdaq_change_style = market_index_style(nasdaq_change), market_index_style(nasdaq_change)
    dji_price_style   , dji_change_style    = market_index_style(dji_change), market_index_style(dji_change)
    sp_price_style    , sp_change_style     = market_index_style(sp_change), market_index_style(sp_change)
    rut_price_style   , rut_change_style    = market_index_style(rut_change), market_index_style(rut_change)

    eastern = timezone('US/Eastern')
    current_time_adj = dt.datetime.now(eastern).strftime("%A, %b %d, %Y, %I:%M %p")
    current_time_adj = current_time_adj+' (EST)'

    if df.iloc[0][3][:8].upper() == "AT CLOSE":
        marketstatus = "Market Status: AT CLOSE"
    else:
        marketstatus = "Market Status: AT OPEN"

    return nasdaq_price, nasdaq_change, dji_price, dji_change, sp_price, sp_change, rut_price, rut_change, nasdaq_price_style, nasdaq_change_style, dji_price_style, dji_change_style, sp_price_style, sp_change_style, rut_price_style, rut_change_style, current_time_adj, marketstatus

@app.callback(
    Output('stock live', 'figure'),
    [Input('submit-button', 'n_clicks'), Input('interval-component2', 'n_intervals')],
    [State('enter_ticker', 'value')],
    suppress_callback_exceptions=True
)
def stock_live_chart(n_clicks, n, input_value):
    # Handle empty or None input values
    if not input_value or input_value.strip() == '':
        fig = go.Figure()
        fig.update_layout(title='Please Search a Valid Stock',
                          plot_bgcolor='#DEDEDE',
                          hovermode="x unified",
                          xaxis=dict(showspikes=True, showgrid=True, spikemode='across', spikesnap='hovered data'),
                          yaxis=dict(showspikes=True, showgrid=True, spikemode='across', spikesnap='hovered data', tickformat="$,.2f"))
        return fig
        
    input_value = input_value.upper().strip()
    df, prev_df = live_price_df(input_value)
    fig = go.Figure()
    if df.empty is False and prev_df.empty is False:
        ticker = yf.Ticker(input_value)
        ticker_info = ticker.info
        line = go.Scatter(
                    x = df.index.strftime("%Y-%m-%d %H:%M:%S"),
                    y = df['Close'],
                    fill = 'tonexty',
                    hovertemplate = '$%{y:.2f}',
                    mode='lines',
                    marker={"color": live_price_color(df,prev_df)},
                    showlegend = False,
                    name = input_value
        )
        benchmark = go.Scatter(
                    x = df.index.strftime("%Y-%m-%d %H:%M:%S"),
                    y = np.array([prev_df.iloc[-1]['Close']]*len(df)),
                    hovertemplate = '$%{y:.2f}',
                    #fillcolor = live_price_color(df,prev_df),
                    mode='lines',
                    line=dict(color='black', dash = 'dash'),
                    showlegend = False,
                    name = "Pre-Day Close"
        )

        fig.add_trace(benchmark)
        fig.add_trace(line)
        fig.update_layout(title = "<b>{}<b>".format(ticker_info['shortName']),
                          plot_bgcolor = '#DEDEDE',
                          hovermode="x unified",
                          xaxis = dict(
                                        showspikes = True,
                                        showgrid = True,
                                        spikemode = 'across',
                                        spikesnap = 'hovered data'
                                      ),
                          yaxis=dict(
                                      showspikes = True,
                                      showgrid = True,
                                      spikemode = 'across',
                                      spikesnap = 'hovered data',
                                      tickformat="$,.2f"))
    else:
        fig.update_layout(title = 'Please Search a Valid Stock',
                          plot_bgcolor = '#DEDEDE',
                          hovermode="x unified",
                          xaxis = dict(
                                        showspikes = True,
                                        showgrid = True,
                                        spikemode = 'across',
                                        spikesnap = 'hovered data'
                                      ),
                          yaxis=dict(
                                      showspikes = True,
                                      showgrid = True,
                                      spikemode = 'across',
                                      spikesnap = 'hovered data',
                                      tickformat="$,.2f"))

    return fig


@app.callback([Output('NASDAQ', 'figure')  , Output('DJI', 'figure'),
               Output('SP500', 'figure')   , Output('RUT2000', 'figure')],
               Input('interval-component2', 'n_intervals'),
               suppress_callback_exceptions=True)
def update_indexes(n):
    fig1 = live_price_fig("^IXIC")
    fig1.update_layout(title = "<b>NASDAQ Index<b>")

    fig2 = live_price_fig("^DJI")
    fig2.update_layout(title = "<b>DJI Index<b>")

    fig3 = live_price_fig("^GSPC")
    fig3.update_layout(title = "<b>S&P500 Index<b>")

    fig4 = live_price_fig("^RUT")
    fig4.update_layout(title = "<b>Russell2000 Index<b>")

    return fig1, fig2, fig3, fig4

app.index_string = """<!DOCTYPE html>
<html>
    <head>
        <!-- Global site tag (gtag.js) - Google Analytics -->
        <script async src="https://www.googletagmanager.com/gtag/js?id=UA-196446572-1"></script>
        <script>
            window.dataLayer = window.dataLayer || [];
            function gtag(){dataLayer.push(arguments);}
            gtag('js', new Date());

            gtag('config', 'UA-196446572-1', { 'anonymize_ip': true });
        </script>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>"""

if __name__ == '__main__':
     app.run_server(debug=True)