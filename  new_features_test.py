### Yahoo Finanace
import yfinance as yf
import plotly
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime as dt
from datetime import datetime, timedelta
import pandas as pd
import talib
import numpy as np
from dateutil.relativedelta import *
from pytz import timezone
from itertools import compress
import time
import requests
from collections import defaultdict


## Stock List Manager
## Get most updated stock list from NASDAQ, NYSE, AMEX. Run every day at 12:00 AM EST
class StockListManager:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        self.stock_list = self.get_stock_list()

    def test_api_connection(self, url):
        """Test the connection to the API"""
        try:
            print(f"Testing connection to: {url}")
            response = requests.get(url, headers=self.headers, timeout=10)
            print(f"Response status code: {response.status_code}")
            print(f"Response headers: {response.headers}")
            
            if response.status_code == 200:
                data = response.json()
                print("Successfully parsed JSON response")
                return data
            else:
                print(f"Error response content: {response.text[:200]}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            return None
        except ValueError as e:
            print(f"JSON parsing error: {e}")
            return None

    def get_stocks_from_exchange(self, base_url, exchange, limit=1000, offset=0):
        """Get stock data from a specific exchange, supports pagination"""
        url = f"{base_url}?tableonly=true&exchange={exchange}&limit={limit}&offset={offset}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code != 200:
                print(f"Error fetching {exchange} stocks at offset {offset}. Status code: {response.status_code}")
                return None, 0
            
            data = response.json()
            if not data['data'] or not data['data']['table'] or not data['data']['table']['rows']:
                print(f"No data found for {exchange} at offset {offset}")
                return None, 0
            
            return data['data']['table']['rows']
            
        except Exception as e:
            print(f"Error fetching {exchange} stocks at offset {offset}: {e}")
            return None, 0
            
    def get_stock_list(self):
        """Get stock list from NASDAQ website"""
        try:
            # 测试 NASDAQ API
            print("\nTesting NASDAQ API...")
            base_url = "https://api.nasdaq.com/api/screener/stocks"
            test_data = self.test_api_connection(f"{base_url}?tableonly=true&exchange=nasdaq&limit=25")
            
            if not test_data:
                raise Exception("Failed to connect to NASDAQ API")
            
            exchanges = ['nasdaq', 'nyse', 'amex']
            all_stocks = []
            
            for exchange in exchanges:
                print(f"\nFetching {exchange.upper()} stocks...")
                offset = 0
                limit = 1000
                exchange_stocks = []
                
                while True:
                    stocks = self.get_stocks_from_exchange(base_url, exchange, limit, offset)
                    
                    if not stocks:
                        break
                    
                    exchange_stocks.extend(stocks)
                    print(f"Retrieved {len(exchange_stocks)} stocks from {exchange.upper()}")
                    
                    if len(stocks) < limit:
                        break
                    
                    offset += limit
                    time.sleep(1)  # 避免请求过快
                
                if exchange_stocks:
                    stocks_df = pd.DataFrame(exchange_stocks)
                    stocks_df['exchange'] = exchange.upper()
                    all_stocks.append(stocks_df)
            
            if not all_stocks:
                raise Exception("No stock data retrieved")
            
            # 合并数据
            df = pd.concat(all_stocks, ignore_index=True)
            
            # 清理数据
            required_columns = ['symbol', 'name', 'exchange']
            optional_columns = ['marketCap', 'volume']
            
            # 确保必需的列存在
            for col in required_columns:
                if col not in df.columns:
                    raise Exception(f"Required column '{col}' not found in data")
            
            # 选择并重命名列
            columns_to_keep = required_columns + [col for col in optional_columns if col in df.columns]
            df = df[columns_to_keep]
            
            # 重命名列
            column_mapping = {
                'symbol': 'Symbol',
                'name': 'Name',
                'exchange': 'Exchange',
                'marketCap': 'Market_Cap',
                'volume': 'Volume'
            }
            df = df.rename(columns={col: column_mapping[col] for col in df.columns if col in column_mapping})
            
            print(f"\nSuccessfully retrieved {len(df)} stocks")
            return df
            
        except Exception as e:
            print(f"\nError in get_stock_list: {str(e)}")
            print("Full error details:")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()


class StockMetaDataFetcher:
    def __init__(self, ticker, alpha_vantage_api_key):
        self.ticker = ticker
        self.api_key = alpha_vantage_api_key
        
        # Alpha Vantage interval mapping
        self.av_interval_mapping = {
            '1m': '1min',
            '5m': '5min', 
            '15m': '15min',
            '30m': '30min',
            '60m': '60min',
            '1d': 'daily',
            '1wk': 'weekly',
            '1mo': 'monthly'
        }
        
        # Get stock data for all intervals from Alpha Vantage and compile into a dictionary
        self.stock_metadata = {
            'company_overview': {},
            'stock_fundamental': {
                'annual': {
                    'income_statement': pd.DataFrame(),
                    'balance_sheet': pd.DataFrame(),
                    'cash_flow': pd.DataFrame()
                },
                'quarterly': {
                    'income_statement': pd.DataFrame(),
                    'balance_sheet': pd.DataFrame(),
                    'cash_flow': pd.DataFrame()
                }
            },
            'stock_technical_data': defaultdict(lambda: defaultdict(dict)),
        }

 
        self._fetch_company_overview()
        self._fetch_fundamental_data()
        for interval in self.av_interval_mapping.keys():
            self._fetch_stock_price_data(interval)
            self.moving_average_algorithm(interval, 'sma')
            self.moving_average_algorithm(interval, 'ema')
            self.moving_average_algorithm(interval, 'wma')
            self.moving_average_algorithm(interval, 'dema')
            self.moving_average_algorithm(interval, 'tema')
            self.moving_average_algorithm(interval, 'kama')
            self.macd_formula(interval)
            self.rsi_formula(interval)
            self.kdj_formula(interval)
            self.candlestick_pattern_signal(interval)
    

    def _fetch_stock_price_data(self, interval):
        """Fetch historical data from Alpha Vantage API"""
        
        base_url = "https://www.alphavantage.co/query"
        
        # Determine function and parameters based on interval
        if interval in ['1m', '5m', '15m', '30m', '60m']:
            function = 'TIME_SERIES_INTRADAY'
            params = {
                'function': function,
                'symbol': self.ticker,
                'interval': self.av_interval_mapping[interval],
                'apikey': self.api_key,
                'outputsize': 'full'  # Get more data
            }
                
        elif interval == '1d':
            function = 'TIME_SERIES_DAILY'
            params = {
                'function': function,
                'symbol': self.ticker,
                'apikey': self.api_key,
                'outputsize': 'full'  # Get 5+ years of data
            }
            
        elif interval == '1wk':
            function = 'TIME_SERIES_WEEKLY'
            params = {
                'function': function,
                'symbol': self.ticker,
                'apikey': self.api_key
            }
            
        elif interval == '1mo':
            function = 'TIME_SERIES_MONTHLY'
            params = {
                'function': function,
                'symbol': self.ticker,
                'apikey': self.api_key
            }
        else:
            raise ValueError(f"Unsupported interval: {interval}")
        
        # Make API request with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"Fetching {self.ticker} data (attempt {attempt + 1})...")
                response = requests.get(base_url, params=params, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                
                # Check for API errors
                if 'Error Message' in data:
                    raise Exception(f"Alpha Vantage Error: {data['Error Message']}")
                
                if 'Note' in data:
                    if attempt < max_retries - 1:
                        print("API call frequency limit reached, waiting...")
                        time.sleep(60)  # Wait 1 minute
                        continue
                    else:
                        raise Exception("API call frequency limit reached")
                
                # Parse the data
                df = self._parse_stock_price_data_response(data, interval)
                
                if df.empty:
                    raise Exception("No data returned from Alpha Vantage")
                
                print(f"Successfully fetched {len(df)} data points for {self.ticker}")
                self.stock_metadata['stock_technical_data'][interval]['stock_price'] = df

                return
                
            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(5)  # Wait before retry
                else:
                    raise e
    
    def _parse_stock_price_data_response(self, data, interval):
        """Parse Alpha Vantage API response to DataFrame with improved error handling"""
        try:
            time_series_key = None
            possible_keys = [
                'Time Series (Daily)',
                'Time Series (1min)',
                'Time Series (5min)',
                'Time Series (15min)',
                'Time Series (30min)',
                'Time Series (60min)',
                'Weekly Time Series',
                'Monthly Time Series'
            ]
            
            for key in possible_keys:
                if key in data:
                    time_series_key = key
                    break
            
            if not time_series_key:
                available_keys = list(data.keys())
                print(f"Available keys: {available_keys}")
                raise Exception(f"No recognized time series key found. Available: {available_keys}")
            
            time_series = data[time_series_key]
            
            if not time_series:
                raise Exception("Time series data is empty")
            
            print(f"Found {len(time_series)} data points in {time_series_key}")
            
            # Convert to DataFrame
            df_data = []
            for timestamp, values in time_series.items():
                try:
                    row = {
                        'Datetime': pd.to_datetime(timestamp),
                        'Open': float(values['1. open']),
                        'High': float(values['2. high']),
                        'Low': float(values['3. low']),
                        'Close': float(values['4. close']),
                        'Volume': int(values['5. volume'])
                    }
                    df_data.append(row)
                except (KeyError, ValueError) as e:
                    print(f"Error parsing data point {timestamp}: {e}")
                    continue
            
            if not df_data:
                raise Exception("No valid data points could be parsed")
            
            df = pd.DataFrame(df_data)
            df.set_index('Datetime', inplace=True)
            df.sort_index(inplace=True)  # Sort by date ascending
            
            print(f"Successfully parsed {len(df)} data points")
            df_filtered = self._filter_data_by_interval(df, interval)
            print(f"After filtering: {len(df_filtered)} data points")
        
            return df_filtered
            
        except Exception as e:
            print(f"Error in _parse_stock_price_data_response: {e}")
            return pd.DataFrame()

    def _filter_data_by_interval(self, df, interval):
        """Filter data to match yfinance period logic"""
        
        if df.empty:
            return df
        
        now = datetime.now()
        
        if interval in ['1d', '1wk', '1mo', '3mo']:
            # For daily and above, get 5 years of data
            start_date = now - timedelta(days=5*365)
            df = df[df.index >= start_date]
            
        elif interval in ['30m', '60m']:
            # For 30m and 60m, get 1 month of data
            start_date = now - timedelta(days=30)
            df = df[df.index >= start_date]
            
        elif interval in ['5m', '15m']:
            # For 5m and 15m, get 5 days of data
            start_date = now - timedelta(days=5)
            df = df[df.index >= start_date]
            
        elif interval == '1m':
            # For 1m, get 1 day of data
            start_date = now - timedelta(days=1)
            df = df[df.index >= start_date]
        
        return df
    
    def _fetch_company_overview(self):
        """Fetch company overview from Alpha Vantage"""
        
        base_url = "https://www.alphavantage.co/query"
        params = {
            'function': 'OVERVIEW',
            'symbol': self.ticker,
            'apikey': self.api_key
        }
        
        try:
            response = requests.get(base_url, params=params, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            
            if 'Symbol' not in data:
                print(f"Warning: No company overview data for {self.ticker}")
                return {'symbol': self.ticker}
            
            # Convert Alpha Vantage format to yfinance-like format
            company_info = {
                'symbol': data.get('Symbol', self.ticker),
                'longName': data.get('Name', 'N/A'),
                'sector': data.get('Sector', 'N/A'),
                'industry': data.get('Industry', 'N/A'),
                'marketCap': self._safe_int(data.get('MarketCapitalization', 0)),
                'trailingEps': self._safe_float(data.get('EPS', 0)),
                'priceToSalesTrailing12Months': self._safe_float(data.get('PriceToSalesRatioTTM', 0)),
                'priceToBook': self._safe_float(data.get('PriceToBookRatio', 0)),
                'fiftyTwoWeekHigh': self._safe_float(data.get('52WeekHigh', 0)),
                'fiftyTwoWeekLow': self._safe_float(data.get('52WeekLow', 0)),
                'currency': data.get('Currency'),  # Alpha Vantage typically returns USD
                'longBusinessSummary': data.get('Description', 'No description available.')
            }
            
            self.stock_metadata['company_overview'] = company_info
            
        except Exception as e:
            print(f"Error fetching company overview for {self.ticker}: {e}")
            self.stock_metadata['company_overview'] = {'symbol': self.ticker}
    
    def _safe_float(self, value):
        """Safely convert value to float"""
        try:
            if value == 'None' or value == '' or value is None:
                return 0.0
            return float(value)
        except (ValueError, TypeError):
            return 0.0
    
    def _safe_int(self, value):
        """Safely convert value to int"""
        try:
            if value == 'None' or value == '' or value is None:
                return 0
            return int(float(value))
        except (ValueError, TypeError):
            return 0

    ## Moving Average Algorithm
    def moving_average_algorithm(self, interval, ma_type):
        """
        Calculate moving average values according to the different intervals
        """
        ma_type_mapping = {
        'sma': 0,   # Simple Moving Average
        'ema': 1,   # Exponential Moving Average
        'wma': 2,   # Weighted Moving Average
        'dema': 3,  # Double Exponential Moving Average
        'tema': 4,  # Triple Exponential Moving Average
        'trima': 5, # Triangular Moving Average
        'kama': 6,  # Kaufman Adaptive Moving Average
        }
        # convert ma_type to integer
        if isinstance(ma_type, str):
            ma_type_int = ma_type_mapping.get(ma_type.lower())
            if ma_type_int is None:
                raise ValueError(f"Unsupported ma_type: {ma_type}")
        else:
            ma_type_int = ma_type

        params = {
            '1m': {'ma_period':[5, 10, 20, 30, 60, 120], 
                   'bbands_period':20, 
                   'bbands_std_up':2.2, 
                   'bbands_std_dn':2.0,
                   'bbands_overb_threshold': 0.85, 
                   'bbands_overs_threshold': 0.15
                   },
            '5m': {'ma_period':[6, 12, 24, 36, 72, 144], 
                   'bbands_period':18, 
                   'bbands_std_up':2.1, 
                   'bbands_std_dn':2.1,
                   'bbands_overb_threshold': 0.83, 
                   'bbands_overs_threshold': 0.17
                   },
            '15m': {'ma_period':[4, 8, 16, 24, 48, 96], 
                    'bbands_period':15, 
                    'bbands_std_up':2.0, 
                    'bbands_std_dn':2.0,
                    'bbands_overb_threshold': 0.80, 
                    'bbands_overs_threshold': 0.20
                    },
            '30m': {'ma_period':[3, 6, 12, 18, 36, 72], 
                    'bbands_period':12, 
                    'bbands_std_up':1.9, 
                    'bbands_std_dn':1.9,
                    'bbands_overb_threshold': 0.80, 
                    'bbands_overs_threshold': 0.20
                    },
            '60m': {'ma_period':[3, 5, 8, 13, 21, 34], 
                    'bbands_period':10, 
                    'bbands_std_up':1.8, 
                    'bbands_std_dn':1.8,
                    'bbands_overb_threshold': 0.80, 
                    'bbands_overs_threshold': 0.20
                    },
            '1d': {'ma_period':[5, 10, 20, 30, 60, 120, 250], 
                   'bbands_period':20, 
                   'bbands_std_up':2, 
                   'bbands_std_dn':2,
                   'bbands_overb_threshold': 0.80, 
                   'bbands_overs_threshold': 0.20
                   },
            '1wk': {'ma_period':[5, 10, 20, 30, 60], 
                    'bbands_period':18, 
                    'bbands_std_up':2.1, 
                    'bbands_std_dn':2.1,
                    'bbands_overb_threshold': 0.75, 
                    'bbands_overs_threshold': 0.25
                    },
            '1mo': {'ma_period':[3, 5, 10, 12, 24, 36], 
                    'bbands_period':10, 
                    'bbands_std_up':2.3, 
                    'bbands_std_dn':2.3,
                    'bbands_overb_threshold': 0.75, 
                    'bbands_overs_threshold': 0.25
                    },
            '3mo': {'ma_period':[2, 4, 8, 12, 16], 
                    'bbands_period':6, 
                    'bbands_std_up':2.4, 
                    'bbands_std_dn':2.4,
                    'bbands_overb_threshold': 0.70, 
                    'bbands_overs_threshold': 0.30
                    }
        }

        df = self.stock_metadata['stock_technical_data'][interval]['stock_price']
        if interval not in params:
            raise ValueError(f"Unsupported interval: {interval}")
        
        output_df = pd.DataFrame()
        # calculate the moving average
        for ma_period in params[interval]['ma_period']:
            output_df[f'{ma_period}'] = talib.MA(df['Close'], timeperiod=ma_period, matype=ma_type_int)
        
        # calculate the bollinger bands
        output_df['bbands_upper'], output_df['bbands_middle'], output_df['bbands_lower'] = talib.BBANDS(df['Close'], 
                                                                                                        timeperiod=params[interval]['bbands_period'], 
                                                                                                        nbdevup=params[interval]['bbands_std_up'], 
                                                                                                        nbdevdn=params[interval]['bbands_std_dn'],
                                                                                                        matype = ma_type_int)

        # calculate price position within bollinger bands (0-1)
        output_df['bbands_position'] = np.where(
            output_df['bbands_upper'].isna() | output_df['bbands_lower'].isna(), np.nan,
            np.where(df['Close'] >= output_df['bbands_upper'], 1.0,
            np.where(df['Close'] <= output_df['bbands_lower'], 0.0,
                    (df['Close'] - output_df['bbands_lower']) / (output_df['bbands_upper'] - output_df['bbands_lower'])))
        )
        
        # generate overbought/oversold signal
        output_df['bbands_overbs_signal'] = np.where(
            output_df['bbands_position'].isna(), 0,
            np.where(output_df['bbands_position'] >= params[interval]['bbands_overb_threshold'], -1,
            np.where(output_df['bbands_position'] <= params[interval]['bbands_overs_threshold'], 1, 0))
        )

        output_df.drop(['bbands_middle', 'bbands_position'], axis=1, inplace=True)

        self.stock_metadata['stock_technical_data'][interval][ma_type] = output_df

    ## KDJ Formula (Stochastic Oscillator)
    def kdj_formula(self, interval):
        """
        Calculate KDJ values according to the different intervals
        """
        df = self.stock_metadata['stock_technical_data'][interval]['stock_price']
        H, L, C = df['High'], df['Low'], df['Close']
        params = {
            # High Frequency trading intervals
            '1m': {
                'fastk_period': 5,
                'slowk_period': 2,
                'slowd_period': 2,
                'overbought': 85,
                'oversold': 15
            },
            '5m': {
                'fastk_period': 7,
                'slowk_period': 3,
                'slowd_period': 3,
                'overbought': 83,
                'oversold': 17
            },
            '15m': {
                'fastk_period': 9,
                'slowk_period': 3,
                'slowd_period': 3,
                'overbought': 80,
                'oversold': 20
            },
            '30m': {
                'fastk_period': 9,
                'slowk_period': 3,
                'slowd_period': 3,
                'overbought': 80,
                'oversold': 20
            },
            '60m': {
                'fastk_period': 9,
                'slowk_period': 3,
                'slowd_period': 3,
                'overbought': 80,
                'oversold': 20
            },
            # 日线及以上参数
            '1d': {
                'fastk_period': 9,
                'slowk_period': 3,
                'slowd_period': 3,
                'overbought': 80,
                'oversold': 20
            },
            '1wk': {
                'fastk_period': 7,
                'slowk_period': 3,
                'slowd_period': 3,
                'overbought': 75,
                'oversold': 25
            },
            '1mo': {
                'fastk_period': 5,
                'slowk_period': 3,
                'slowd_period': 3,
                'overbought': 75,
                'oversold': 25
            },
            '3mo': {
                'fastk_period': 5,
                'slowk_period': 3,
                'slowd_period': 3,
                'overbought': 70,
                'oversold': 30
            }
        }
        if interval not in params:
            raise ValueError(f"Unsupported interval: {interval}")
        
        low_list = L.rolling(params[interval]['fastk_period']).min()
        high_list = H.rolling(params[interval]['fastk_period']).max()
        rsv = 100 * ((C - low_list) / (high_list - low_list)).values

        ## initialize k0, d0
        k0 = 50
        d0 = 50

        k_factor = 1/params[interval]['slowk_period']
        d_factor = 1/params[interval]['slowd_period']

        ## calculate k, d, j
        k_list = []
        for v in rsv:
            if v == v:  # 检查是否为nan
                k0 = k_factor * v + (1 - k_factor) * k0
                k_list.append(k0)
            else:
                k_list.append(np.nan)

        d_list = []
        for k in k_list:
            if k == k:  # 检查是否为nan
                d0 = d_factor * k + (1 - d_factor) * d0
                d_list.append(d0)
            else:
                d_list.append(np.nan)
        
        j_list = [3 * k - 2 * d for k, d in zip(k_list, d_list)]

        ## convert to series
        k_series = pd.Series(k_list, index=df.index, name='K')
        d_series = pd.Series(d_list, index=df.index, name='D')
        j_series = pd.Series(j_list, index=df.index, name='J')

        # generate the kdj cross signal - golden cross is 1 and death cross is -1
        kdj_cross_signal = np.where(k_series.notna() & d_series.notna() & (k_series > d_series) & (k_series.shift(1) <= d_series.shift(1)), 1,
                            np.where(k_series.notna() & d_series.notna() & (k_series < d_series) & (k_series.shift(1) >= d_series.shift(1)), -1, 0))
        ## confirm the final kdj overbought and oversold signal
        kdj_overbs_signal = np.where(k_series.notna() & d_series.notna() & (k_series > params[interval]['overbought']) & (d_series > params[interval]['overbought']), -1, 0)
        kdj_overbs_signal = np.where(k_series.notna() & d_series.notna() & (k_series < params[interval]['oversold']) & (d_series < params[interval]['oversold']), 1, kdj_overbs_signal)

        self.stock_metadata['stock_technical_data'][interval]['kdj'] = {
            'k': k_series,
            'd': d_series,
            'j': j_series,
            'kdj_cross_signal': kdj_cross_signal,
            'kdj_overbs_signal': kdj_overbs_signal
        }

    
    ## MACD Formula (Moving Average Convergence Divergence)
    def macd_formula(self, interval):
        """
        Calculate MACD values according to the different intervals
        """
        params = {
            # High Frequency trading intervals
            '1m': {
                'fastperiod': 6,
                'slowperiod': 13,
                'signalperiod': 4
            },
            '5m': {
                'fastperiod': 8,
                'slowperiod': 17,
                'signalperiod': 5
            },
            '15m': {
                'fastperiod': 10,
                'slowperiod': 21,
                'signalperiod': 7
            },
            '30m': {
                'fastperiod': 10,
                'slowperiod': 23,
                'signalperiod': 8
            },
            '60m': {
                'fastperiod': 12,
                'slowperiod': 26,
                'signalperiod': 9
            },
            # 日线及以上参数
            '1d': {
                'fastperiod': 12,
                'slowperiod': 26,
                'signalperiod': 9
            },
            '1wk': {
                'fastperiod': 8,
                'slowperiod': 17,
                'signalperiod': 7
            },
            '1mo': {
                'fastperiod': 6,
                'slowperiod': 13,
                'signalperiod': 6
            },
            '3mo': {
                'fastperiod': 4,
                'slowperiod': 8,
                'signalperiod': 3
            }
        }
        df = self.stock_metadata['stock_technical_data'][interval]['stock_price']
        if interval not in params:
            raise ValueError(f"Unsupported interval: {interval}")
        
        macd, macd_signal_line, macd_hist = talib.MACD(df['Close'], fastperiod=params[interval]['fastperiod'], slowperiod=params[interval]['slowperiod'], signalperiod=params[interval]['signalperiod'])
        macd_hist = macd_hist*2

        # convert to pandas Series
        macd = pd.Series(macd, index=df.index)
        macd_signal_line = pd.Series(macd_signal_line, index=df.index)
        macd_hist = pd.Series(macd_hist, index=df.index)

        ## generate the macd cross signal 
        ## -- golden cross above 0-axis is 2 (strong buy) and golden cross below 0-axis is 1 (reversal buy)
        ## -- death cross above 0-axis is -1 (take profit) and death cross below 0-axis is -2 (strong sell)
        macd_cross_signal = np.where((macd > 0) & (macd.shift(1).notna()) & (macd_signal_line.shift(1).notna()) & (macd > macd_signal_line) & (macd.shift(1) <= macd_signal_line.shift(1)), 2,
                            np.where((macd > 0) & (macd.shift(1).notna()) & (macd_signal_line.shift(1).notna()) & (macd < macd_signal_line) & (macd.shift(1) >= macd_signal_line.shift(1)), -1, 0))
        macd_cross_signal = np.where((macd < 0) & (macd.shift(1).notna()) & (macd_signal_line.shift(1).notna()) & (macd > macd_signal_line) & (macd.shift(1) <= macd_signal_line.shift(1)), 1,
                            np.where((macd < 0) & (macd.shift(1).notna()) & (macd_signal_line.shift(1).notna()) & (macd < macd_signal_line) & (macd.shift(1) >= macd_signal_line.shift(1)), -2, macd_cross_signal))

        self.stock_metadata['stock_technical_data'][interval]['macd'] = {
            'macd': macd,
            'macd_signal_line': macd_signal_line,
            'macd_hist': macd_hist,
            'macd_cross_signal': macd_cross_signal
        }
    
    ## RSI Formula (Relative Strength Index)
    def rsi_formula(self, interval):
        """
        Calculate RSI values according to the different intervals
        """
        params = {
            # High Frequency trading intervals
            '1m': {
                'timeperiod': 9,
                'overbought': 75,
                'oversold': 25
            },
            '5m': {
                'timeperiod': 11,
                'overbought': 73,
                'oversold': 27
            },
            '15m': {
                'timeperiod': 12,
                'overbought': 72,
                'oversold': 28
            },
            '30m': {
                'timeperiod': 13,
                'overbought': 71,
                'oversold': 29
            },
            '60m': {
                'timeperiod': 14,
                'overbought': 70,
                'oversold': 30
            },
            # 日线及以上参数
            '1d': {
                'timeperiod': 14,
                'overbought': 70,
                'oversold': 30
            },
            '1wk': {
                'timeperiod': 10,
                'overbought': 65,
                'oversold': 35
            },
            '1mo': {
                'timeperiod': 8,
                'overbought': 65,
                'oversold': 35
            },
            '3mo': {
                'timeperiod': 6,
                'overbought': 60,
                'oversold': 40
            }
        }
        df = self.stock_metadata['stock_technical_data'][interval]['stock_price']
        if interval not in params:
            raise ValueError(f"Unsupported interval: {interval}")
        
        rsi = talib.RSI(df['Close'], timeperiod=params[interval]['timeperiod'])
        rsi = pd.Series(rsi, index=df.index)
        rsi_overbs_signal = np.where(rsi.notna() & (rsi > params[interval]['overbought']), -1,
                            np.where(rsi.notna() & (rsi < params[interval]['oversold']), 1, 0))
        self.stock_metadata['stock_technical_data'][interval]['rsi'] = {
            'rsi': rsi,
            'rsi_overbs_signal': rsi_overbs_signal
        }

    ## Candlestick Pattern Algorithm
    def candlestick_pattern_signal(self, interval):
        """
        Calculate candlestick pattern signal
        """
        df = self.stock_metadata['stock_technical_data'][interval]['stock_price']
        major_patterns = {
            'CDLENGULFING': 'Engulfing Pattern',
            # Two-candle pattern
            # Bullish: Second green candle's body completely engulfs previous red candle's body
            # Bearish: Second red candle's body completely engulfs previous green candle's body
            # Strong reversal signal when appearing at support/resistance levels
            
            'CDLHARAMI': 'Harami Pattern',
            # Two-candle pattern
            # Second candle's body is completely contained within first candle's body
            # Bullish: Large red candle followed by small green candle
            # Bearish: Large green candle followed by small red candle
            # Indicates potential trend reversal or consolidation
            
            'CDLDOJI': 'Doji',
            # Single candle pattern
            # Opening and closing prices are nearly equal
            # Long shadows indicate market indecision
            # Significant when appearing after strong trends
            
            'CDLHAMMER': 'Hammer',
            # Single candle pattern
            # Small body at the top, long lower shadow
            # Little or no upper shadow
            # Bullish reversal signal at bottom of downtrend
            
            'CDLSHOOTINGSTAR': 'Shooting Star'
            # Single candle pattern
            # Small body at the bottom, long upper shadow
            # Little or no lower shadow
            # Bearish reversal signal at top of uptrend
        }

        reversal_patterns = {
            'CDLENGULFING': 'Engulfing Pattern',  # As described above
            
            'CDLEVENINGSTAR': 'Evening Star',
            # Three-candle pattern
            # 1. Strong green candle
            # 2. Small body candle with gap up
            # 3. Strong red candle closing deep into first candle
            # Major bearish reversal signal at market tops
            
            'CDLMORNINGSTAR': 'Morning Star',
            # Three-candle pattern
            # 1. Strong red candle
            # 2. Small body candle with gap down
            # 3. Strong green candle closing deep into first candle
            # Major bullish reversal signal at market bottoms
            
            'CDLHAMMER': 'Hammer',  # As described above
            
            'CDLSHOOTINGSTAR': 'Shooting Star'  # As described above
        }

        continuation_patterns = {
            'CDLHARAMI': 'Harami Pattern',  # As described above
            
            'CDLMARUBOZU': 'Marubozu',
            # Single candle pattern
            # No or very small shadows (wicks)
            # Green Marubozu: Strong buying pressure
            # Red Marubozu: Strong selling pressure
            # Indicates trend strength and potential continuation
            
            'CDL3WHITESOLDIERS': 'Three White Soldiers',
            # Three-candle pattern
            # Three consecutive green candles
            # Each opens within previous body
            # Each closes at or near its high
            # Strong bullish continuation signal
            
            'CDL3BLACKCROWS': 'Three Black Crows'
            # Three-candle pattern
            # Three consecutive red candles
            # Each opens within previous body
            # Each closes at or near its low
            # Strong bearish continuation signal
        }

        op = df['Open'].astype(float)
        hi = df['High'].astype(float)
        lo = df['Low'].astype(float)
        cl = df['Close'].astype(float)
        output_df = pd.DataFrame(index=df.index)
        for pattern_func in major_patterns.keys():
            pattern_result = getattr(talib, pattern_func)(op, hi, lo, cl)
            pattern_result = pattern_result.fillna(0)
            output_df[pattern_func] = np.where(pattern_result > 0, 1,
                                                np.where(pattern_result < 0, -1, 0))
        
        output_df['cdl_pattern_signal'] = output_df.sum(axis=1)
        self.stock_metadata['stock_technical_data'][interval]['cdl_pattern'] = output_df

    ## Fetch Fundamental Data from Alpha Vantage
    def _fetch_fundamental_data(self):
        """get fundamentals data from alpha vantage"""
        try:
            print(f"Fetching fundamental data for {self.ticker}...")
            
            # get annual and quarterly financial data
            income_statement_annual, income_statement_quarterly = self._fetch_income_statement()
            balance_sheet_annual, balance_sheet_quarterly = self._fetch_balance_sheet()
            cash_flow_annual, cash_flow_quarterly = self._fetch_cash_flow()
            
            # process and store financial data
            self.stock_metadata['stock_fundamental'] = {
                'annual': {
                    'income_statement': income_statement_annual,
                    'balance_sheet': balance_sheet_annual,
                    'cash_flow': cash_flow_annual
                },
                'quarterly': {
                    'income_statement': income_statement_quarterly,
                    'balance_sheet': balance_sheet_quarterly,
                    'cash_flow': cash_flow_quarterly
                }
            }
            
            print(f"✅ Successfully fetched fundamental data for {self.ticker}")
            
        except Exception as e:
            print(f"Error fetching fundamental data for {self.ticker}: {e}")
            self.stock_metadata['stock_fundamental'] = {
                'annual': {'income_statement': pd.DataFrame(), 'balance_sheet': pd.DataFrame(), 'cash_flow': pd.DataFrame()},
                'quarterly': {'income_statement': pd.DataFrame(), 'balance_sheet': pd.DataFrame(), 'cash_flow': pd.DataFrame()}
            }

    def _fetch_income_statement(self):
        """get income statement data"""
        base_url = "https://www.alphavantage.co/query"
        function = 'INCOME_STATEMENT'
        
        params = {
            'function': function,
            'symbol': self.ticker,
            'apikey': self.api_key
        }
        
        try:
            response = requests.get(base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if 'Error Message' in data:
                raise Exception(f"Alpha Vantage Error: {data['Error Message']}")
            
            if 'Note' in data:
                print("API call frequency limit reached for income statement")
                return pd.DataFrame()
            
            # parse data
            annual_reports = data.get('annualReports', [])
            quarterly_reports = data.get('quarterlyReports', [])
            
            if not annual_reports and not quarterly_reports:
                return pd.DataFrame(), pd.DataFrame()
            
            # convert to DataFrame
            annual_df = pd.DataFrame(annual_reports)
            quarterly_df = pd.DataFrame(quarterly_reports)
            
            # process date column
            if 'fiscalDateEnding' in annual_df.columns:
                annual_df['fiscalDateEnding'] = pd.to_datetime(annual_df['fiscalDateEnding'])
                annual_df = annual_df.sort_values('fiscalDateEnding', ascending=False)
            if 'fiscalDateEnding' in quarterly_df.columns:
                quarterly_df['fiscalDateEnding'] = pd.to_datetime(quarterly_df['fiscalDateEnding'])
                quarterly_df = quarterly_df.sort_values('fiscalDateEnding', ascending=False)
            
            # convert numeric columns
            numeric_columns = [
                'totalRevenue', 'costOfRevenue', 'grossProfit', 
                'operatingIncome', 'netIncome', 'ebitda'
            ]
            
            for col in numeric_columns:
                if col in annual_df.columns:
                    annual_df[col] = pd.to_numeric(annual_df[col], errors='coerce').fillna(0)
                if col in quarterly_df.columns:
                    quarterly_df[col] = pd.to_numeric(quarterly_df[col], errors='coerce').fillna(0)
            
            return annual_df.head(8), quarterly_df.head(8)  # get recent 8 reporting periods
            
        except Exception as e:
            print(f"Error fetching income statement: {e}")
            return pd.DataFrame(), pd.DataFrame()

    def _fetch_balance_sheet(self):
        """get balance sheet data"""
        base_url = "https://www.alphavantage.co/query"
        function = 'BALANCE_SHEET'
        
        params = {
            'function': function,
            'symbol': self.ticker,
            'apikey': self.api_key
        }
        
        try:
            ##time.sleep(12)  # Alpha Vantage rate limit: 5 requests per minute
            response = requests.get(base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if 'Error Message' in data:
                raise Exception(f"Alpha Vantage Error: {data['Error Message']}")
            
            if 'Note' in data:
                print("API call frequency limit reached for balance sheet")
                return pd.DataFrame()
            
            # parse data
            annual_reports = data.get('annualReports', [])
            quarterly_reports = data.get('quarterlyReports', [])
            
            if not annual_reports and not quarterly_reports:
                return pd.DataFrame(), pd.DataFrame()
            
            # convert to DataFrame
            annual_df = pd.DataFrame(annual_reports)
            quarterly_df = pd.DataFrame(quarterly_reports)
            
            # process date column
            if 'fiscalDateEnding' in annual_df.columns:
                annual_df['fiscalDateEnding'] = pd.to_datetime(annual_df['fiscalDateEnding'])
                annual_df = annual_df.sort_values('fiscalDateEnding', ascending=False)
            if 'fiscalDateEnding' in quarterly_df.columns:
                quarterly_df['fiscalDateEnding'] = pd.to_datetime(quarterly_df['fiscalDateEnding'])
                quarterly_df = quarterly_df.sort_values('fiscalDateEnding', ascending=False)
            
            # convert numeric columns
            numeric_columns = [
                'totalAssets', 'totalLiabilities', 'totalShareholderEquity',
                'cashAndCashEquivalentsAtCarryingValue', 'currentAssets', 'currentLiabilities'
            ]
            
            for col in numeric_columns:
                if col in annual_df.columns:
                    annual_df[col] = pd.to_numeric(annual_df[col], errors='coerce').fillna(0)
                if col in quarterly_df.columns:
                    quarterly_df[col] = pd.to_numeric(quarterly_df[col], errors='coerce').fillna(0)
            
            return annual_df.head(8), quarterly_df.head(8)
            
        except Exception as e:
            print(f"Error fetching balance sheet: {e}")
            return pd.DataFrame(), pd.DataFrame()

    def _fetch_cash_flow(self):
        """get cash flow data"""
        base_url = "https://www.alphavantage.co/query"
        function = 'CASH_FLOW'
        
        params = {
            'function': function,
            'symbol': self.ticker,
            'apikey': self.api_key
        }
        
        try:
            ##time.sleep(12)  # Alpha Vantage rate limit: 5 requests per minute
            response = requests.get(base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if 'Error Message' in data:
                raise Exception(f"Alpha Vantage Error: {data['Error Message']}")
            
            if 'Note' in data:
                print("API call frequency limit reached for cash flow")
                return pd.DataFrame()
            
            # parse data
            annual_reports = data.get('annualReports', [])
            quarterly_reports = data.get('quarterlyReports', [])
            
            if not annual_reports and not quarterly_reports:
                return pd.DataFrame(), pd.DataFrame()
            
            # convert to DataFrame
            annual_df = pd.DataFrame(annual_reports)
            quarterly_df = pd.DataFrame(quarterly_reports)
            
            # process date column
            if 'fiscalDateEnding' in annual_df.columns:
                annual_df['fiscalDateEnding'] = pd.to_datetime(annual_df['fiscalDateEnding'])
                annual_df = annual_df.sort_values('fiscalDateEnding', ascending=False)
            if 'fiscalDateEnding' in quarterly_df.columns:
                quarterly_df['fiscalDateEnding'] = pd.to_datetime(quarterly_df['fiscalDateEnding'])
                quarterly_df = quarterly_df.sort_values('fiscalDateEnding', ascending=False)
            
            # convert numeric columns
            numeric_columns = [
                'operatingCashflow', 'cashflowFromInvestment', 
                'cashflowFromFinancing', 'capitalExpenditures'
            ]
            
            for col in numeric_columns:
                if col in annual_df.columns:
                    annual_df[col] = pd.to_numeric(annual_df[col], errors='coerce').fillna(0)
                if col in quarterly_df.columns:
                    quarterly_df[col] = pd.to_numeric(quarterly_df[col], errors='coerce').fillna(0)
            
            return annual_df.head(8), quarterly_df.head(8)  # get recent 8 reporting periods
            
        except Exception as e:
            print(f"Error fetching cash flow: {e}")
            return pd.DataFrame(), pd.DataFrame()

    def fundamentals_prep(self, period='Yearly'):
        """
        process fundamentals data - replace the original fundamentals_prep function
        period: 'Yearly' or 'Quarterly'
        """
        try:
            # select annual or quarterly data
            period_key = 'annual' if period == 'Yearly' else 'quarterly'
            
            if 'stock_fundamental' not in self.stock_metadata:
                return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), 'USD'
            
            fund_data = self.stock_metadata['stock_fundamental'][period_key]
            
            # get original data
            income_statement = fund_data['income_statement'].copy()
            balance_sheet = fund_data['balance_sheet'].copy()
            cash_flow = fund_data['cash_flow'].copy()
            
            if income_statement.empty or balance_sheet.empty or cash_flow.empty:
                return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), 'USD'
            
            # process income statement data
            IncomeStatement = self._process_income_statement(income_statement)
            
            # process balance sheet data
            BalanceSheet = self._process_balance_sheet(balance_sheet)
            
            # process cash flow data
            CashFlow = self._process_cash_flow(cash_flow, IncomeStatement)
            
            # get currency unit (from company info, default USD)
            currency = self.stock_metadata.get('stock_info', {}).get('currency', 'USD')
            
            return IncomeStatement, BalanceSheet, CashFlow, currency
            
        except Exception as e:
            print(f"Error in fundamentals_prep: {e}")
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), 'USD'

    def _process_income_statement(self, df):
        """process income statement data"""
        try:
            # rename columns to match original logic
            column_mapping = {
                'fiscalDateEnding': 'fiscalDateEnding',
                'totalRevenue': 'Total Revenue',
                'costOfRevenue': 'Cost Of Revenue', 
                'grossProfit': 'Gross Profit',
                'operatingIncome': 'Operating Income',
                'netIncome': 'Net Income'
            }
            
            # select needed columns
            available_cols = [col for col in column_mapping.keys() if col in df.columns]
            processed_df = df[available_cols].copy()
            
            # rename columns
            processed_df = processed_df.rename(columns=column_mapping)
            
            # format date
            if 'fiscalDateEnding' in processed_df.columns:
                processed_df['fiscalDateEnding'] = processed_df['fiscalDateEnding'].dt.strftime('%Y-%m-%d')
            
            # ensure numeric columns are float type
            numeric_cols = ['Total Revenue', 'Cost Of Revenue', 'Gross Profit', 'Operating Income', 'Net Income']
            for col in numeric_cols:
                if col in processed_df.columns:
                    processed_df[col] = pd.to_numeric(processed_df[col], errors='coerce').fillna(0)
            
            # calculate profit margins
            if 'Total Revenue' in processed_df.columns and processed_df['Total Revenue'].sum() != 0:
                processed_df['Gross Margin'] = processed_df['Gross Profit'] / processed_df['Total Revenue']
                processed_df['Operating Margin'] = processed_df['Operating Income'] / processed_df['Total Revenue']
                processed_df['Net Profit Margin'] = processed_df['Net Income'] / processed_df['Total Revenue']
            else:
                processed_df['Gross Margin'] = 0
                processed_df['Operating Margin'] = 0
                processed_df['Net Profit Margin'] = 0
            
            return processed_df
            
        except Exception as e:
            print(f"Error processing income statement: {e}")
            return pd.DataFrame()

    def _process_balance_sheet(self, df):
        """process balance sheet data"""
        try:
            # rename columns
            column_mapping = {
                'fiscalDateEnding': 'fiscalDateEnding',
                'totalAssets': 'Total Assets',
                'totalLiabilities': 'Total Liabilities Net Minority Interest',
                'totalShareholderEquity': 'Stockholders Equity',
                'cashAndCashEquivalentsAtCarryingValue': 'Cash And Cash Equivalents',
                'currentAssets': 'Current Assets',
                'currentLiabilities': 'Current Liabilities'
            }
            
            # select needed columns
            available_cols = [col for col in column_mapping.keys() if col in df.columns]
            processed_df = df[available_cols].copy()
            
            # rename columns
            processed_df = processed_df.rename(columns=column_mapping)
            
            # format date
            if 'fiscalDateEnding' in processed_df.columns:
                processed_df['fiscalDateEnding'] = processed_df['fiscalDateEnding'].dt.strftime('%Y-%m-%d')
            
            # ensure numeric columns are float type
            numeric_cols = ['Total Assets', 'Total Liabilities Net Minority Interest', 'Stockholders Equity', 
                           'Cash And Cash Equivalents', 'Current Assets', 'Current Liabilities']
            for col in numeric_cols:
                if col in processed_df.columns:
                    processed_df[col] = pd.to_numeric(processed_df[col], errors='coerce').fillna(0)
            
            # rename columns to match original logic
            processed_df.columns = ['fiscalDateEnding', 'Total Assets', 'Total Liab', 'Total Stockholder Equity', 
                                   'Cash', 'Total Current Assets', 'Total Current Liabilities']
            
            # calculate ratios
            processed_df['Cash Ratio'] = np.where(
                processed_df['Total Current Liabilities'] != 0,
                processed_df['Cash'] / processed_df['Total Current Liabilities'],
                0
            )
            processed_df['Current Ratio'] = np.where(
                processed_df['Total Current Liabilities'] != 0,
                processed_df['Total Current Assets'] / processed_df['Total Current Liabilities'],
                0
            )
            
            return processed_df
            
        except Exception as e:
            print(f"Error processing balance sheet: {e}")
            return pd.DataFrame()

    def _process_cash_flow(self, df, income_statement):
        """process cash flow data"""
        try:
            # rename columns
            column_mapping = {
                'fiscalDateEnding': 'fiscalDateEnding',
                'operatingCashflow': 'Operating Cash Flow',
                'cashflowFromInvestment': 'Investing Cash Flow',
                'cashflowFromFinancing': 'Financing Cash Flow',
                'capitalExpenditures': 'Capital Expenditure'
            }
            
            # select needed columns
            available_cols = [col for col in column_mapping.keys() if col in df.columns]
            processed_df = df[available_cols].copy()
            
            # rename columns
            processed_df = processed_df.rename(columns=column_mapping)
            
            # format date
            if 'fiscalDateEnding' in processed_df.columns:
                processed_df['fiscalDateEnding'] = processed_df['fiscalDateEnding'].dt.strftime('%Y-%m-%d')
            
            # ensure numeric columns are float type
            numeric_cols = ['Operating Cash Flow', 'Investing Cash Flow', 'Financing Cash Flow', 'Capital Expenditure']
            for col in numeric_cols:
                if col in processed_df.columns:
                    processed_df[col] = pd.to_numeric(processed_df[col], errors='coerce').fillna(0)
            
            # rename columns to match original logic
            processed_df.columns = ['fiscalDateEnding', 'Total Cash From Operating Activities', 
                                   'Total Cashflows From Investing Activities', 'Total Cash From Financing Activities', 
                                   'Capital Expenditures']
            
            # calculate free cash flow
            processed_df['Free Cash Flow'] = (processed_df['Total Cash From Operating Activities'] + 
                                            processed_df['Capital Expenditures'])
            
            # calculate operating cash flow/sales ratio
            if not income_statement.empty and 'Total Revenue' in income_statement.columns:
                # ensure two DataFrames have the same number of rows
                min_rows = min(len(processed_df), len(income_statement))
                if min_rows > 0:
                    revenue = income_statement['Total Revenue'].iloc[:min_rows]
                    operating_cf = processed_df['Total Cash From Operating Activities'].iloc[:min_rows]
                    processed_df['OperatingCashflow/SalesRatio'] = np.where(
                        revenue != 0, operating_cf / revenue, 0
                    )
                else:
                    processed_df['OperatingCashflow/SalesRatio'] = 0
            else:
                processed_df['OperatingCashflow/SalesRatio'] = 0
            
            return processed_df
            
        except Exception as e:
            print(f"Error processing cash flow: {e}")
            return pd.DataFrame()

    def fundamentals_tables(self, period='Yearly'):
        """
        generate fundamentals tables - replace the original fundamentals_tables function
        """
        try:
            IncomeStatement, BalanceSheet, CashFlow, currency = self.fundamentals_prep(period)
            
            # if no data, return empty DataFrame
            if IncomeStatement.empty:
                df1 = df2 = df3 = pd.DataFrame()
            else:
                # process income statement latest data
                df1 = self._create_income_statement_table(IncomeStatement)
                
                # process balance sheet latest data
                df2 = self._create_balance_sheet_table(BalanceSheet)
                
                # process cash flow latest data
                df3 = self._create_cash_flow_table(CashFlow)
            
            return IncomeStatement, BalanceSheet, CashFlow, df1, df2, df3, currency
            
        except Exception as e:
            print(f"Error in fundamentals_tables: {e}")
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), 'USD'

    def _create_income_statement_table(self, df):
        """create income statement summary table"""
        try:
            if df.empty:
                return pd.DataFrame()
            
            table_df = pd.DataFrame(columns=['KPI', 'Value'])
            last_statement = df.iloc[0]  # latest financial data
            
            # define indicators to display
            indicators = [
                ('Total Revenue', 'Total Revenue'),
                ('Cost Of Revenue', 'Cost Of Revenue'), 
                ('Gross Profit', 'Gross Profit'),
                ('Operating Income', 'Operating Income'),
                ('Net Income', 'Net Income'),
                ('Gross Margin', 'Gross Margin'),
                ('Operating Margin', 'Operating Margin'),
                ('Net Profit Margin', 'Net Profit Margin')
            ]
            
            for i, (key, display_name) in enumerate(indicators):
                if key in last_statement:
                    value = last_statement[key]
                    
                    # format values
                    if i <= 4:  # first 5 are amount indicators
                        if abs(value) > 100000000:
                            value_conv = format(int(value/1000000), ',') + ' M'
                        else:
                            value_conv = format(int(value), ',')
                    else:  # last one is ratio indicator
                        value_conv = "{:.1%}".format(value)
                    
                    row = {'KPI': display_name, 'Value': value_conv}
                    table_df = pd.concat([table_df, pd.DataFrame([row])], ignore_index=True)
            
            return table_df
            
        except Exception as e:
            print(f"Error creating income statement table: {e}")
            return pd.DataFrame()

    def _create_balance_sheet_table(self, df):
        """create balance sheet summary table"""
        try:
            if df.empty:
                return pd.DataFrame()
            
            table_df = pd.DataFrame(columns=['KPI', 'Value'])
            last_balance = df.iloc[0]  # latest balance sheet data
            
            # define indicators to display
            indicators = [
                ('Total Assets', 'Total Assets'),
                ('Total Liab', 'Total Liabilities'),
                ('Total Stockholder Equity', 'Total Shareholder Equity'),
                ('Cash', 'Cash And Cash Equivalents'),
                ('Total Current Assets', 'Total Current Assets'),
                ('Total Current Liabilities', 'Total Current Liabilities'),
                ('Cash Ratio', 'Cash Ratio'),
                ('Current Ratio', 'Current Ratio')
            ]
            
            for i, (key, display_name) in enumerate(indicators):
                if key in last_balance:
                    value = last_balance[key]
                    
                    # format values
                    if i <= 5:  # 前6个是金额指标
                        if abs(value) > 100000000:
                            value_conv = format(int(value/1000000), ',') + ' M'
                        else:
                            value_conv = format(int(value), ',')
                    else:  # last one is ratio indicator
                        value_conv = "%.2f" % value
                    
                    row = {'KPI': display_name, 'Value': value_conv}
                    table_df = pd.concat([table_df, pd.DataFrame([row])], ignore_index=True)
            
            return table_df
            
        except Exception as e:
            print(f"Error creating balance sheet table: {e}")
            return pd.DataFrame()

    def _create_cash_flow_table(self, df):
        """create cash flow summary table"""
        try:
            if df.empty:
                return pd.DataFrame()
            
            table_df = pd.DataFrame(columns=['KPI', 'Value'])
            last_cashflow = df.iloc[0]  # latest cash flow data
            
            # define indicators to display
            indicators = [
                ('Total Cash From Operating Activities', 'Operating Cash flow'),
                ('Total Cashflows From Investing Activities', 'Cash Flow From Investment'),
                ('Total Cash From Financing Activities', 'Cash Flow From Financing'),
                ('Capital Expenditures', 'Capital Expenditures'),
                ('Free Cash Flow', 'Free Cash Flow'),
                ('OperatingCashflow/SalesRatio', 'Operating Cash Flow/Sales Ratio')
            ]
            
            for i, (key, display_name) in enumerate(indicators):
                if key in last_cashflow:
                    value = last_cashflow[key]
                    
                    # format values
                    if i <= 4:  # first 5 are amount indicators
                        if abs(value) > 100000000:
                            value_conv = format(int(value/1000000), ',') + ' M'
                        else:
                            value_conv = format(int(value), ',')
                    else:  # last one is ratio indicator
                        value_conv = "%.2f" % value
                    
                    row = {'KPI': display_name, 'Value': value_conv}
                    table_df = pd.concat([table_df, pd.DataFrame([row])], ignore_index=True)
            
            return table_df
            
        except Exception as e:
            print(f"Error creating cash flow table: {e}")
            return pd.DataFrame()



### Stock Analysis Visualization Chart
class StockAnalysisChart:
    def __init__(self, interval, ma_options, tech_ind, stock_metadata):
        #super().__init__(ticker, interval, alpha_vantage_api_key)
        self.interval = interval
        self.ma_options = ma_options
        self.tech_ind = tech_ind
        self.stock_technical_data = stock_metadata['stock_technical_data']
        self.stock_fundamental_data = stock_metadata['company_overview']
        self.interval_ms_convert = {
            '1m': 60000,
            '5m': 300000,
            '15m': 900000,
            '30m': 1800000,
            '60m': 3600000,
        }
        self.av_interval_mapping = {
            '1m': '1min',
            '5m': '5min', 
            '15m': '15min',
            '30m': '30min',
            '60m': '60min',
            '1d': 'daily',
            '1wk': 'weekly',
            '1mo': 'monthly'
        }
        self.ma_color_pool = ['#A83838', '#F09A16', '#EFF048', '#5DF016', '#13C3F0', '#493CF0', '#F000DF']
        self.bbands_color = '#ADD8E6'

        self.fig = self.base_fig_generator()
        self.add_ma_bbands()
        self.add_technical_charts()

    ## set up color difference for Up&Down day price change
    def _vol_color(self, df):
        color = np.array(['green']*len(df))
        color[df['Close']>df['Open']] = 'green'
        color[df['Close']<df['Open']] = 'red'
        color[df['Close']==df['Open']] = 'grey'
        return color
    def _macd_hist_color(self, df):
        color = np.array(['green']*len(df))
        color[df>0] = 'green'
        color[df<0] = 'red'
        color[df==0] = 'grey'
        return color


    ## generate the base chart including candlestick and volume, plus moving average and bollinger bands as optional
    def base_fig_generator(self):
        df = self.stock_technical_data[self.interval]['stock_price']
        ticker_info = self.stock_fundamental_data

        # calculate the height ratio and top margin of each subplot
        heights = [0.6, 0.2, 0.2]  # subplot height ratio
        top_margin = 0          # top margin of each subplot

        # calculate the vertical position of each subplot
        domains = []
        current_position = 0
        for height in heights[::-1]:  # calculate from bottom to top
            domain_start = current_position
            domain_end = current_position + height - top_margin
            domains.append([domain_start, domain_end])
            current_position += height
        domains = domains[::-1]  # reverse to correct order

        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0,
                            #row_width=[0.2, 0.2, 0.6],
                            row_heights=heights,
                            )

        trace_candlestick = go.Candlestick(
                    x = df.reset_index(inplace=False)['Datetime'],
                    open = df['Open'],
                    close = df['Close'],
                    high = df['High'],
                    low = df['Low'],
                    opacity = 0.8,
                    name = '',
                    showlegend=False
                )
        trace_volume = go.Bar(
                            x = df.reset_index(inplace=False)['Datetime'],
                            y = df['Volume'],
                            marker={
                                "color": self._vol_color(df),
                                "line": {
                                    "color": "rgb(255, 255, 255)",
                                    "width": 0.1,
                                }},
                            showlegend = False,
                            name = 'Volume',
                            hovertemplate = 'Volume: %{y:,.3s}<extra></extra>'
                        )
        fig.add_trace(trace_candlestick,row=1,col=1)
        fig.add_trace(trace_volume,row=2,col=1)

        # modify layout
        fig.update_layout(title = '{}'.format(self.stock_fundamental_data['longName']),
                        autosize=True,
                        font={"family": "Raleway", "size": 12},
                        hovermode="x unified",
                        hoverlabel=dict(
                            bgcolor = 'White',
                            bordercolor = '#17991C'
                            ),
                        xaxis = dict(
                                        showspikes = True,
                                        spikemode = 'across+toaxis',
                                        spikesnap = 'data',
                                        spikecolor='rgba(0,0,0,0.3)'  # a semi-transparent black color
                                    ),
                        xaxis2 = dict(
                                        showspikes = True,
                                        spikemode = 'across+toaxis',
                                        spikesnap = 'data',
                                        spikecolor='rgba(0,0,0,0.3)'  # a semi-transparent black color
                                    ),
                        xaxis3 = dict(
                                        showspikes = True,
                                        spikemode = 'across+toaxis',
                                        spikesnap = 'data',
                                        spikecolor='rgba(0,0,0,0.3)'  # a semi-transparent black color
                                    ),
                        yaxis = dict(
                                        showspikes = True,
                                        spikemode = 'across+toaxis',
                                        spikesnap = 'cursor',
                                        spikecolor='rgba(0,0,0,0.3)',  # a semi-transparent black color
                                        domain = domains[0]
                                    ),
                        yaxis2 = dict(
                                        showspikes = True,
                                        spikemode = 'across+toaxis',
                                        spikesnap = 'cursor',
                                        spikecolor='rgba(0,0,0,0.3)',  # a semi-transparent black color
                                        domain = domains[1]
                                    ),
                        yaxis3 = dict(
                                        showspikes = True,
                                        spikemode = 'across+toaxis',
                                        spikesnap = 'cursor',
                                        spikecolor='rgba(0,0,0,0.3)',  # a semi-transparent black color
                                        domain = domains[2]
                                    ),
                        plot_bgcolor = 'White',
                        paper_bgcolor= 'White',
                        height = 1000,
                        width = 1000,
                        bargap = 0.2,
                        )
        # this step is to make the traces match the x-axis
        fig.update_traces(xaxis='x')

        if self.interval == '1d':
            dt_all = pd.date_range(
                start=df.reset_index()['Datetime'].iloc[0].tz_localize(None),
                end=df.reset_index()['Datetime'].iloc[-1].tz_localize(None)
            )

            # retrieve the dates that ARE in the original datset
            dt_obs = [d.tz_localize(None).strftime("%Y-%m-%d") for d in pd.to_datetime(df.reset_index()['Datetime'])]

            # define dates with missing values
            dt_breaks = [d for d in dt_all.strftime("%Y-%m-%d").tolist() if not d in dt_obs]

            fig.update_xaxes(
                            rangebreaks=[dict(values=dt_breaks)],
                            autorange = True,
                            showline = True,
                            #title = "Date",
                            zeroline = True,
                            rangeslider_visible = False,
                            rangeselector = dict(
                            buttons = list([
                                dict(count = 1, label = '1D', step = 'day', stepmode = 'backward'),
                                dict(count = 5, label = '5D', step = 'day', stepmode = 'backward'),
                                dict(count = 1, label = '1M', step = 'month', stepmode = 'backward'),
                                dict(count = 3, label = '3M', step = 'month', stepmode = 'backward'),
                                dict(count = 6, label = '6M', step = 'month', stepmode = 'backward'),
                                dict(count = 1, label = 'YTD', step = 'year', stepmode = 'todate'),
                                dict(count = 1, label = '1Y', step = 'year', stepmode = 'backward'),
                                #dict(count = 5, label = '5Y', step = 'year', stepmode = 'backward'),
                                dict(step = 'all')
                                ])),
                            type="date",
                            showticklabels=True,
                            linewidth=1.5, linecolor='LightGrey',
                            mirror = True,
                            row = 1, col = 1)
        elif self.interval == '1wk' or self.interval == '1mo':
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
                                #dict(count = 5, label = '5Y', step = 'year', stepmode = 'backward'),
                                dict(step = 'all')
                                ])),
                            type="date",
                            showticklabels=True,
                            linewidth=1.5, linecolor='LightGrey',
                            mirror = True,
                            row = 1, col = 1)
        elif self.interval == '3mo':
            fig.update_xaxes(autorange = True,
                            showline = True,
                            #title = "Date",
                            zeroline = True,
                            rangeslider_visible = False,
                            rangeselector = dict(
                            buttons = list([
                                dict(count = 3, label = '3M', step = 'month', stepmode = 'backward'),
                                dict(count = 6, label = '6M', step = 'month', stepmode = 'backward'),
                                dict(count = 1, label = '1Y', step = 'year', stepmode = 'backward'),
                                dict(count = 2, label = '2Y', step = 'year', stepmode = 'backward'),
                                #dict(count = 5, label = '5Y', step = 'year', stepmode = 'backward'),
                                dict(step = 'all')
                                ])),
                            type="date",
                            showticklabels=True,
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


        elif self.interval in ['1m','5m', '15m', '30m', '60m']:
            # build complete timeline from start to end
            dt_all = pd.date_range(
                start=df.reset_index()['Datetime'].iloc[0].tz_localize(None),
                end=df.reset_index()['Datetime'].iloc[-1].tz_localize(None),
                freq=self.av_interval_mapping[self.interval]
            )  # convert '5m' to '5min' etc.

            # retrieve the dates that ARE in the original dataset
            dt_obs = [d.tz_localize(None).strftime("%Y-%m-%d %H:%M:%S") for d in pd.to_datetime(df.reset_index()['Datetime'])]

            # define dates with missing values
            dt_breaks = [d for d in dt_all.strftime("%Y-%m-%d %H:%M:%S").tolist() if not d in dt_obs]

            fig.update_xaxes(rangebreaks=[dict(values=dt_breaks, dvalue=self.interval_ms_convert[self.interval])])
            if self.interval == '1m':
                fig.update_xaxes(autorange=True,
                                showline=True,
                                zeroline=True,
                                rangeslider_visible=False,
                                rangeselector=dict(
                                    buttons=list([
                                        dict(count=15, label='15min', step='minute', stepmode='backward'),
                                        dict(count=30, label='30min', step='minute', stepmode='backward'),
                                        dict(count=1, label='1hr', step='hour', stepmode='backward'),
                                        dict(count=2, label='2hr', step='hour', stepmode='backward'),
                                        dict(count=4, label='4hr', step='hour', stepmode='backward'),
                                        dict(step='all')
                                    ])),
                                type="date",
                                showticklabels=True,
                                linewidth=1.5, linecolor='LightGrey',
                                mirror=True,
                                row=1, col=1)
            elif self.interval in ['5m', '15m']:
                fig.update_xaxes(autorange=True,
                                showline=True,
                                zeroline=True,
                                rangeslider_visible=False,
                                rangeselector=dict(
                                    buttons=list([
                                        dict(count=1, label='1hr', step='hour', stepmode='backward'),
                                        dict(count=2, label='2hr', step='hour', stepmode='backward'),
                                        dict(count=4, label='4hr', step='hour', stepmode='backward'),
                                        dict(count=1, label='1D', step='day', stepmode='backward'),
                                        dict(step='all')
                                    ])),
                                type="date",
                                showticklabels=True,
                                linewidth=1.5, linecolor='LightGrey',
                                mirror=True,
                                row=1, col=1)
            else:
                fig.update_xaxes(autorange=True,
                                showline=True,
                                zeroline=True,
                                rangeslider_visible=False,
                                rangeselector=dict(
                                    buttons=list([
                                        dict(count=1, label='1hr', step='hour', stepmode='backward'),
                                        dict(count=2, label='2hr', step='hour', stepmode='backward'),
                                        dict(count=4, label='4hr', step='hour', stepmode='backward'),
                                        dict(count=1, label='1D', step='day', stepmode='backward'),
                                        dict(count=5, label='5D', step='day', stepmode='backward'),
                                        dict(count=10, label='10D', step='day', stepmode='backward'),
                                        dict(step='all')
                                    ])),
                                type="date",
                                showticklabels=True,
                                linewidth=1.5, linecolor='LightGrey',
                                mirror=True,
                                row=1, col=1)

            fig.update_xaxes(autorange=True,
                            showline=True,
                            type="date",
                            showticklabels=True,
                            linewidth=1.5, linecolor='LightGrey',
                            mirror=True,
                            row=2, col=1)

        ## modify y-axis styles for stock price and volume
        fig.update_yaxes(autorange = True,
                        tickprefix = '$',
                        showgrid = False,
                        gridcolor= 'LightBlue',
                        showline = True,
                        title = "Stock Price",
                        type = 'linear',
                        zeroline = True,
                        linewidth=1.5, linecolor='LightGrey',
                        mirror = True,
                        row = 1, col = 1)
        fig.update_yaxes(autorange = True,
                        #tickprefix = '$',
                        showgrid = False,
                        gridcolor= 'LightBlue',
                        showline = True,
                        title = "Volume",
                        type = 'linear',
                        zeroline = True,
                        zerolinecolor = 'Black',
                        zerolinewidth = 0.5,
                        linewidth=1.5, linecolor='LightGrey',
                        mirror = True,
                        row = 2, col = 1)

        return fig

    ## Add moving average and bollinger bands to the Candlestick main chart
    def add_ma_bbands(self):
        # empty the existing moving average and bollinger bands traces in the main chart before adding new traces
        self.fig.data = [trace for trace in self.fig.data if not(trace.yaxis == 'y' and ('MA' in trace.name or 'BBAND' in trace.name))]
        
        if self.ma_options != '':
            stock_ma_df = self.stock_technical_data[self.interval][self.ma_options]
            for index, col in enumerate(stock_ma_df.columns):
                if col.isdigit():
                    ma_trace = go.Scatter(
                        x = stock_ma_df.reset_index(inplace=False)['Datetime'],
                        y = stock_ma_df[col],
                        mode='lines',
                        line={"color": self.ma_color_pool[index],
                            "width": 0.85},
                        hoverinfo = 'none',
                        showlegend = True,
                        name = self.ma_options.upper()+col+' ('+self.av_interval_mapping[self.interval]+')'
                    )
                    self.fig.add_trace(ma_trace,row=1,col=1)
                elif col == 'bbands_upper':
                    bbands_upper_trace = go.Scatter(
                        x = stock_ma_df.reset_index(inplace=False)['Datetime'],
                        y = stock_ma_df[col],
                        mode='lines',
                        line={"color": self.bbands_color,
                            "width": 1},
                        hoverinfo = 'none',
                        showlegend = True,
                        name = col.upper()
                    )
                    self.fig.add_trace(bbands_upper_trace,row=1,col=1)
                elif col == 'bbands_lower':
                    bbands_lower_trace = go.Scatter(
                        x = stock_ma_df.reset_index(inplace=False)['Datetime'],
                        y = stock_ma_df[col],
                        fill = 'tonexty',
                        fillcolor = 'rgba(173,216,230,0.2)',
                        mode='lines',
                        line={"color": self.bbands_color,
                            "width": 1},
                        hoverinfo = 'none',
                        showlegend = True,
                        name = col.upper()
                    )
                    self.fig.add_trace(bbands_lower_trace,row=1,col=1)


    ## Add Technical Charts to base fig 3rd row (MACD chart/RSI chart/KDJ chart)
    def add_technical_charts(self):
        # empty the 3rd row chart before adding new traces
        self.fig.data = [trace for trace in self.fig.data if not (hasattr(trace, 'yaxis') and trace.yaxis == 'y3')]
        if self.tech_ind == 'macd':
            df = self.stock_technical_data[self.interval]['macd']
            trace_macd_hist = go.Bar(
                        x = df['macd_hist'].reset_index(inplace=False)['Datetime'],
                        y = df['macd_hist'],
                        opacity = 0.6,
                        marker={
                            "color": self._macd_hist_color(df['macd_hist']),
                            "line": {
                                "color": "rgb(255, 255, 255)",
                                "width": 0.1,
                            }
                                },
                        showlegend = False,
                        name = 'MACD Hist'
                        )
            trace_macd = go.Scatter(
                        x = df['macd'].reset_index(inplace=False)['Datetime'],
                        y = df['macd'],
                        mode='lines',
                        line={"color": "orange",
                            "width": 0.85},
                        showlegend = False,
                        name = "MACD Line"
                        )
            trace_macd_signal = go.Scatter(
                        x = df['macd_signal_line'].reset_index(inplace=False)['Datetime'],
                        y = df['macd_signal_line'],
                        mode='lines',
                        line={"color": "deepskyblue",
                            "width": 0.85},
                        showlegend = False,
                        name = "Signal Line"
                        )
            self.fig.add_trace(trace_macd_hist, row=3, col=1)
            self.fig.add_trace(trace_macd, row=3, col=1)
            self.fig.add_trace(trace_macd_signal, row=3, col=1)

            self.fig.update_xaxes(autorange = True,
                            showline = True,
                            type = "date",
                            showticklabels=True,
                            linewidth=1.5, linecolor='LightGrey',
                            mirror = True,
                            row = 3, col = 1)
            self.fig.update_yaxes(autorange = True,
                            showgrid = False,
                            gridcolor= 'LightBlue',
                            showline = True,
                            title = "MACD",
                            type = 'linear',
                            zeroline = True,
                            zerolinecolor = 'Black',
                            zerolinewidth = 0.5,
                            linewidth=1.5, linecolor='LightGrey',
                            mirror = True,
                            row = 3, col = 1)
    
        elif self.tech_ind == 'rsi':
            df = self.stock_technical_data[self.interval]['rsi']
            trace_rsi = go.Scatter(
                        x = df['rsi'].reset_index(inplace=False)['Datetime'],
                        y = df['rsi'],
                        mode='lines',
                        line={"color": "Orange"},
                        showlegend = False,
                        name = "RSI"
                        )
            self.fig.add_trace(trace_rsi, row=3, col=1)
            self.fig.update_xaxes(autorange = True,
                            showline = True,
                            type = "date",
                            showticklabels=True,
                            linewidth=1.5, linecolor='LightGrey',
                            mirror = True,
                            row = 3, col = 1)
            self.fig.update_yaxes(autorange = True,
                            showgrid = True,
                            gridcolor= 'LightGrey',
                            griddash='dash',
                            tickmode='array',
                            tickvals=[20, 50, 80],
                            showline = True,
                            title = "RSI",
                            type = 'linear',
                            zeroline = True,
                            zerolinecolor = 'Black',
                            zerolinewidth = 0.5,
                            linewidth=1.5, linecolor='LightGrey',
                            mirror = True,
                            row = 3, col = 1)

        elif self.tech_ind == 'kdj':
            df = self.stock_technical_data[self.interval]['kdj']
            trace_k = go.Scatter(
                        x = df['k'].reset_index(inplace=False)['Datetime'],
                        y = df['k'],
                        mode='lines',
                        line={"color": "gold",
                            "width": 0.85},
                        showlegend = False,
                        name = "K"
                        )
            trace_d = go.Scatter(
                        x = df['d'].reset_index(inplace=False)['Datetime'],
                        y = df['d'],
                        mode='lines',
                        line={"color": "blue",
                            "width": 0.85},
                        showlegend = False,
                        name = "D"
                        )
            trace_j = go.Scatter(
                        x = df['j'].reset_index(inplace=False)['Datetime'],
                        y = df['j'],
                        mode='lines',
                        line={"color": "purple",
                            "width": 0.85},
                        showlegend = False,
                        name = "J"
                        )
            self.fig.add_trace(trace_k, row=3, col=1)
            self.fig.add_trace(trace_d, row=3, col=1)
            self.fig.add_trace(trace_j, row=3, col=1)

            self.fig.update_xaxes(autorange = True,
                            showline = True,
                            type = "date",
                            showticklabels=True,
                            linewidth=1.5, linecolor='LightGrey',
                            mirror = True,
                            row = 3, col = 1)
            self.fig.update_yaxes(autorange = True,
                            showgrid = True,
                            gridcolor= 'LightGrey',
                            griddash='dash',
                            showline = True,
                            tickmode = 'array',
                            tickvals = [20, 50, 80],
                            title = "KDJ",
                            type = 'linear',
                            zeroline = False,
                            linewidth=1.5, linecolor='LightGrey',
                            mirror = True,
                            row = 3, col = 1)
        ### this step is to make the traces match the x-axis
        self.fig.update_traces(xaxis='x')




class StockMetaDataFetcher_Polygon:
    def __init__(self, ticker, polygon_api_key):
        self.ticker = ticker
        self.api_key = polygon_api_key
        self.base_url = "https://api.polygon.io"
        
        # Polygon.io interval mapping
        self.polygon_interval_mapping = {
            '1m': {'multiplier': 1, 'timespan': 'minute'},
            '5m': {'multiplier': 5, 'timespan': 'minute'}, 
            '15m': {'multiplier': 15, 'timespan': 'minute'},
            '30m': {'multiplier': 30, 'timespan': 'minute'},
            '60m': {'multiplier': 1, 'timespan': 'hour'},
            '1d': {'multiplier': 1, 'timespan': 'day'},
            '1wk': {'multiplier': 1, 'timespan': 'week'},
            '1mo': {'multiplier': 1, 'timespan': 'month'}
        }
        
        # 初始化数据结构
        self.stock_metadata = {
            'company_overview': {},
            'stock_fundamental': {
                'annual': {
                    'income_statement': pd.DataFrame(),
                    'balance_sheet': pd.DataFrame(),
                    'cash_flow': pd.DataFrame()
                },
                'quarterly': {
                    'income_statement': pd.DataFrame(),
                    'balance_sheet': pd.DataFrame(),
                    'cash_flow': pd.DataFrame()
                }
            },
            'stock_technical_data': defaultdict(lambda: defaultdict(dict)),
        }

        # 获取数据
        self._fetch_company_overview()
        self._fetch_fundamental_data()
        
        # 获取所有时间间隔的技术数据
        for interval in self.polygon_interval_mapping.keys():
            self._fetch_stock_price_data(interval)
            self.moving_average_algorithm(interval, 'sma')
            self.moving_average_algorithm(interval, 'ema')
            self.moving_average_algorithm(interval, 'wma')
            self.moving_average_algorithm(interval, 'dema')
            self.moving_average_algorithm(interval, 'tema')
            self.moving_average_algorithm(interval, 'kama')
            self.macd_formula(interval)
            self.rsi_formula(interval)
            self.kdj_formula(interval)
            self.candlestick_pattern_signal(interval)

    def _fetch_stock_price_data(self, interval):
        """从Polygon.io获取股价数据"""
        try:
            print(f"Fetching {self.ticker} price data for interval {interval}...")
            
            # 计算时间范围
            end_date = datetime.now()
            
            # 根据间隔确定数据范围
            if interval in ['1d', '1wk', '1mo']:
                start_date = end_date - timedelta(days=5*365)  # 5年数据
            elif interval in ['30m', '60m']:
                start_date = end_date - timedelta(days=30)     # 1个月数据
            elif interval in ['5m', '15m']:
                start_date = end_date - timedelta(days=5)      # 5天数据
            elif interval == '1m':
                start_date = end_date - timedelta(days=1)      # 1天数据
            else:
                start_date = end_date - timedelta(days=365)    # 默认1年
            
            # 格式化日期
            from_date = start_date.strftime('%Y-%m-%d')
            to_date = end_date.strftime('%Y-%m-%d')
            
            # 构建API请求
            multiplier = self.polygon_interval_mapping[interval]['multiplier']
            timespan = self.polygon_interval_mapping[interval]['timespan']
            
            url = f"{self.base_url}/v2/aggs/ticker/{self.ticker}/range/{multiplier}/{timespan}/{from_date}/{to_date}"
            params = {
                'adjusted': 'true',
                'sort': 'asc',
                'limit': 50000,
                'apikey': self.api_key
            }
            
            # 发送请求
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') != 'OK' or not data.get('results'):
                print(f"No data returned for {self.ticker} ({interval})")
                self.stock_metadata['stock_technical_data'][interval]['stock_price'] = pd.DataFrame()
                return
            
            # 转换为DataFrame
            results = data['results']
            df_data = []
            
            for item in results:
                row = {
                    'Datetime': pd.to_datetime(item['t'], unit='ms'),
                    'Open': float(item['o']),
                    'High': float(item['h']),
                    'Low': float(item['l']),
                    'Close': float(item['c']),
                    'Volume': int(item['v'])
                }
                df_data.append(row)
            
            df = pd.DataFrame(df_data)
            df.set_index('Datetime', inplace=True)
            df.sort_index(inplace=True)
            
            # 应用时间过滤
            df_filtered = self._filter_data_by_interval(df, interval)
            
            # 存储数据
            self.stock_metadata['stock_technical_data'][interval]['stock_price'] = df_filtered
            
            print(f"✅ Successfully fetched {len(df_filtered)} data points for {self.ticker} ({interval})")
            
            # API限制延迟
            time.sleep(0.1)  # Polygon.io免费版每分钟5个请求
            
        except Exception as e:
            print(f"❌ Failed to fetch price data for {self.ticker} ({interval}): {e}")
            self.stock_metadata['stock_technical_data'][interval]['stock_price'] = pd.DataFrame()

    def _filter_data_by_interval(self, df, interval):
        """根据时间间隔过滤数据"""
        if df.empty:
            return df
        
        now = datetime.now()
        
        if interval in ['1d', '1wk', '1mo']:
            # 对于日线及以上，获取5年数据
            start_date = now - timedelta(days=5*365)
            df = df[df.index >= start_date]
            
        elif interval in ['30m', '60m']:
            # 对于30分钟和1小时，获取1个月数据
            start_date = now - timedelta(days=30)
            df = df[df.index >= start_date]
            
        elif interval in ['5m', '15m']:
            # 对于5分钟和15分钟，获取5天数据
            start_date = now - timedelta(days=5)
            df = df[df.index >= start_date]
            
        elif interval == '1m':
            # 对于1分钟，获取1天数据
            start_date = now - timedelta(days=1)
            df = df[df.index >= start_date]
        
        return df

    def _fetch_company_overview(self):
        """从Polygon.io获取公司概览信息"""
        try:
            print(f"Fetching company overview for {self.ticker}...")
            
            # 获取公司详情
            url = f"{self.base_url}/v3/reference/tickers/{self.ticker}"
            params = {'apikey': self.api_key}
            
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') != 'OK' or not data.get('results'):
                print(f"Warning: No company overview data for {self.ticker}")
                self.stock_metadata['company_overview'] = {'symbol': self.ticker}
                return
            
            result = data['results']
            
            # 获取实时报价
            quote_url = f"{self.base_url}/v2/last/trade/{self.ticker}"
            quote_params = {'apikey': self.api_key}
            
            try:
                quote_response = requests.get(quote_url, params=quote_params, timeout=10)
                quote_data = quote_response.json()
                current_price = quote_data.get('results', {}).get('p', 0)
            except:
                current_price = 0
            
            # 转换为yfinance兼容格式
            company_info = {
                'symbol': result.get('ticker', self.ticker),
                'longName': result.get('name', 'N/A'),
                'sector': result.get('sic_description', 'N/A'),
                'industry': result.get('sic_description', 'N/A'),
                'marketCap': result.get('market_cap', 0),
                'currency': result.get('currency_name', 'USD'),
                'country': result.get('locale', 'US'),
                'currentPrice': current_price,
                'shareOutstanding': result.get('weighted_shares_outstanding', 0),
                'weburl': result.get('homepage_url', ''),
                'longBusinessSummary': result.get('description', 'No description available.'),
                'exchange': result.get('primary_exchange', ''),
                'phone': result.get('phone_number', ''),
                'address': result.get('address', {})
            }
            
            self.stock_metadata['company_overview'] = company_info
            print(f"✅ Successfully fetched company overview for {self.ticker}")
            
            time.sleep(0.1)  # API限制延迟
            
        except Exception as e:
            print(f"Warning: Failed to fetch company overview for {self.ticker}: {e}")
            self.stock_metadata['company_overview'] = {'symbol': self.ticker}

    def _fetch_fundamental_data(self):
        """从Polygon.io获取基本面数据"""
        try:
            print(f"Fetching fundamental data for {self.ticker}...")
            
            # Polygon.io的基本面数据需要付费订阅
            # 这里提供框架，如果有付费订阅可以启用
            
            # 获取财务报表 - 需要premium订阅
            # financials_url = f"{self.base_url}/vX/reference/financials"
            # 由于免费版不支持，创建空数据结构
            
            print(f"⚠️ Skipping fundamental data for {self.ticker} (requires premium subscription)")
            
            # 创建空的数据结构
            empty_structure = {
                'balance_sheet': pd.DataFrame(),
                'income_statement': pd.DataFrame(),
                'cash_flow': pd.DataFrame()
            }
            self.stock_metadata['stock_fundamental']['annual'] = empty_structure.copy()
            self.stock_metadata['stock_fundamental']['quarterly'] = empty_structure.copy()
            
        except Exception as e:
            print(f"Warning: Failed to fetch fundamental data for {self.ticker}: {e}")
            empty_structure = {
                'balance_sheet': pd.DataFrame(),
                'income_statement': pd.DataFrame(),
                'cash_flow': pd.DataFrame()
            }
            self.stock_metadata['stock_fundamental']['annual'] = empty_structure.copy()
            self.stock_metadata['stock_fundamental']['quarterly'] = empty_structure.copy()

    def _safe_float(self, value):
        """安全转换为浮点数"""
        try:
            if value == 'None' or value == '' or value is None:
                return 0.0
            return float(value)
        except (ValueError, TypeError):
            return 0.0
    
    def _safe_int(self, value):
        """安全转换为整数"""
        try:
            if value == 'None' or value == '' or value is None:
                return 0
            return int(float(value))
        except (ValueError, TypeError):
            return 0

    # 保留所有原有的技术指标方法（完全不变）
    def moving_average_algorithm(self, interval, ma_type):
        """计算移动平均线值"""
        ma_type_mapping = {
            'sma': 0,   # Simple Moving Average
            'ema': 1,   # Exponential Moving Average
            'wma': 2,   # Weighted Moving Average
            'dema': 3,  # Double Exponential Moving Average
            'tema': 4,  # Triple Exponential Moving Average
            'trima': 5, # Triangular Moving Average
            'kama': 6,  # Kaufman Adaptive Moving Average
        }
        
        # 转换ma_type为整数
        if isinstance(ma_type, str):
            ma_type_int = ma_type_mapping.get(ma_type.lower())
            if ma_type_int is None:
                raise ValueError(f"Unsupported ma_type: {ma_type}")
        else:
            ma_type_int = ma_type

        params = {
            '1m': {'ma_period':[5, 10, 20, 30, 60, 120], 
                   'bbands_period':20, 
                   'bbands_std_up':2.2, 
                   'bbands_std_dn':2.0,
                   'bbands_overb_threshold': 0.85, 
                   'bbands_overs_threshold': 0.15
                   },
            '5m': {'ma_period':[6, 12, 24, 36, 72, 144], 
                   'bbands_period':18, 
                   'bbands_std_up':2.1, 
                   'bbands_std_dn':2.1,
                   'bbands_overb_threshold': 0.83, 
                   'bbands_overs_threshold': 0.17
                   },
            '15m': {'ma_period':[4, 8, 16, 24, 48, 96], 
                    'bbands_period':15, 
                    'bbands_std_up':2.0, 
                    'bbands_std_dn':2.0,
                    'bbands_overb_threshold': 0.80, 
                    'bbands_overs_threshold': 0.20
                    },
            '30m': {'ma_period':[3, 6, 12, 18, 36, 72], 
                    'bbands_period':12, 
                    'bbands_std_up':1.9, 
                    'bbands_std_dn':1.9,
                    'bbands_overb_threshold': 0.80, 
                    'bbands_overs_threshold': 0.20
                    },
            '60m': {'ma_period':[3, 5, 8, 13, 21, 34], 
                    'bbands_period':10, 
                    'bbands_std_up':1.8, 
                    'bbands_std_dn':1.8,
                    'bbands_overb_threshold': 0.80, 
                    'bbands_overs_threshold': 0.20
                    },
            '1d': {'ma_period':[5, 10, 20, 30, 60, 120, 250], 
                   'bbands_period':20, 
                   'bbands_std_up':2, 
                   'bbands_std_dn':2,
                   'bbands_overb_threshold': 0.80, 
                   'bbands_overs_threshold': 0.20
                   },
            '1wk': {'ma_period':[5, 10, 20, 30, 60], 
                    'bbands_period':18, 
                    'bbands_std_up':2.1, 
                    'bbands_std_dn':2.1,
                    'bbands_overb_threshold': 0.75, 
                    'bbands_overs_threshold': 0.25
                    },
            '1mo': {'ma_period':[3, 5, 10, 12, 24, 36], 
                    'bbands_period':10, 
                    'bbands_std_up':2.3, 
                    'bbands_std_dn':2.3,
                    'bbands_overb_threshold': 0.75, 
                    'bbands_overs_threshold': 0.25
                    }
        }

        df = self.stock_metadata['stock_technical_data'][interval]['stock_price']
        if df.empty or interval not in params:
            return
        
        output_df = pd.DataFrame(index=df.index)
        
        # 计算移动平均线
        for ma_period in params[interval]['ma_period']:
            output_df[f'{ma_period}'] = talib.MA(df['Close'], timeperiod=ma_period, matype=ma_type_int)
        
        # 计算布林带
        output_df['bbands_upper'], output_df['bbands_middle'], output_df['bbands_lower'] = talib.BBANDS(
            df['Close'], 
            timeperiod=params[interval]['bbands_period'], 
            nbdevup=params[interval]['bbands_std_up'], 
            nbdevdn=params[interval]['bbands_std_dn'],
            matype=ma_type_int
        )

        # 计算价格在布林带中的位置 (0-1)
        output_df['bbands_position'] = np.where(
            output_df['bbands_upper'].isna() | output_df['bbands_lower'].isna(), np.nan,
            np.where(df['Close'] >= output_df['bbands_upper'], 1.0,
            np.where(df['Close'] <= output_df['bbands_lower'], 0.0,
                    (df['Close'] - output_df['bbands_lower']) / (output_df['bbands_upper'] - output_df['bbands_lower'])))
        )
        
        # 生成超买超卖信号
        output_df['bbands_overbs_signal'] = np.where(
            output_df['bbands_position'].isna(), 0,
            np.where(output_df['bbands_position'] >= params[interval]['bbands_overb_threshold'], -1,
            np.where(output_df['bbands_position'] <= params[interval]['bbands_overs_threshold'], 1, 0))
        )

        output_df.drop(['bbands_middle', 'bbands_position'], axis=1, inplace=True)

        self.stock_metadata['stock_technical_data'][interval][ma_type] = output_df

    def kdj_formula(self, interval):
        """计算KDJ指标"""
        df = self.stock_metadata['stock_technical_data'][interval]['stock_price']
        if df.empty:
            return
            
        H, L, C = df['High'], df['Low'], df['Close']
        params = {
            '1m': {'fastk_period': 5, 'slowk_period': 2, 'slowd_period': 2, 'overbought': 85, 'oversold': 15},
            '5m': {'fastk_period': 7, 'slowk_period': 3, 'slowd_period': 3, 'overbought': 83, 'oversold': 17},
            '15m': {'fastk_period': 9, 'slowk_period': 3, 'slowd_period': 3, 'overbought': 80, 'oversold': 20},
            '30m': {'fastk_period': 9, 'slowk_period': 3, 'slowd_period': 3, 'overbought': 80, 'oversold': 20},
            '60m': {'fastk_period': 9, 'slowk_period': 3, 'slowd_period': 3, 'overbought': 80, 'oversold': 20},
            '1d': {'fastk_period': 9, 'slowk_period': 3, 'slowd_period': 3, 'overbought': 80, 'oversold': 20},
            '1wk': {'fastk_period': 7, 'slowk_period': 3, 'slowd_period': 3, 'overbought': 75, 'oversold': 25},
            '1mo': {'fastk_period': 5, 'slowk_period': 3, 'slowd_period': 3, 'overbought': 75, 'oversold': 25}
        }
        
        if interval not in params:
            return
        
        low_list = L.rolling(params[interval]['fastk_period']).min()
        high_list = H.rolling(params[interval]['fastk_period']).max()
        rsv = 100 * ((C - low_list) / (high_list - low_list)).values

        # 初始化k0, d0
        k0 = 50
        d0 = 50

        k_factor = 1/params[interval]['slowk_period']
        d_factor = 1/params[interval]['slowd_period']

        # 计算k, d, j
        k_list = []
        for v in rsv:
            if v == v:  # 检查是否为nan
                k0 = k_factor * v + (1 - k_factor) * k0
                k_list.append(k0)
            else:
                k_list.append(np.nan)

        d_list = []
        for k in k_list:
            if k == k:  # 检查是否为nan
                d0 = d_factor * k + (1 - d_factor) * d0
                d_list.append(d0)
            else:
                d_list.append(np.nan)
        
        j_list = [3 * k - 2 * d for k, d in zip(k_list, d_list)]

        # 转换为series
        k_series = pd.Series(k_list, index=df.index, name='K')
        d_series = pd.Series(d_list, index=df.index, name='D')
        j_series = pd.Series(j_list, index=df.index, name='J')

        # 生成KDJ交叉信号
        kdj_cross_signal = np.where(k_series.notna() & d_series.notna() & (k_series > d_series) & (k_series.shift(1) <= d_series.shift(1)), 1,
                            np.where(k_series.notna() & d_series.notna() & (k_series < d_series) & (k_series.shift(1) >= d_series.shift(1)), -1, 0))
        
        # 确认最终的KDJ超买超卖信号
        kdj_overbs_signal = np.where(k_series.notna() & d_series.notna() & (k_series > params[interval]['overbought']) & (d_series > params[interval]['overbought']), -1, 0)
        kdj_overbs_signal = np.where(k_series.notna() & d_series.notna() & (k_series < params[interval]['oversold']) & (d_series < params[interval]['oversold']), 1, kdj_overbs_signal)

        self.stock_metadata['stock_technical_data'][interval]['kdj'] = {
            'k': k_series,
            'd': d_series,
            'j': j_series,
            'kdj_cross_signal': kdj_cross_signal,
            'kdj_overbs_signal': kdj_overbs_signal
        }

    def macd_formula(self, interval):
        """计算MACD指标"""
        params = {
            '1m': {'fastperiod': 6, 'slowperiod': 13, 'signalperiod': 4},
            '5m': {'fastperiod': 8, 'slowperiod': 17, 'signalperiod': 5},
            '15m': {'fastperiod': 10, 'slowperiod': 21, 'signalperiod': 7},
            '30m': {'fastperiod': 10, 'slowperiod': 23, 'signalperiod': 8},
            '60m': {'fastperiod': 12, 'slowperiod': 26, 'signalperiod': 9},
            '1d': {'fastperiod': 12, 'slowperiod': 26, 'signalperiod': 9},
            '1wk': {'fastperiod': 8, 'slowperiod': 17, 'signalperiod': 7},
            '1mo': {'fastperiod': 6, 'slowperiod': 13, 'signalperiod': 6}
        }
        
        df = self.stock_metadata['stock_technical_data'][interval]['stock_price']
        if df.empty or interval not in params:
            return
        
        macd, macd_signal_line, macd_hist = talib.MACD(
            df['Close'], 
            fastperiod=params[interval]['fastperiod'], 
            slowperiod=params[interval]['slowperiod'], 
            signalperiod=params[interval]['signalperiod']
        )
        macd_hist = macd_hist * 2

        # 转换为pandas Series
        macd = pd.Series(macd, index=df.index)
        macd_signal_line = pd.Series(macd_signal_line, index=df.index)
        macd_hist = pd.Series(macd_hist, index=df.index)

        # 生成MACD交叉信号
        macd_cross_signal = np.where((macd > 0) & (macd.shift(1).notna()) & (macd_signal_line.shift(1).notna()) & (macd > macd_signal_line) & (macd.shift(1) <= macd_signal_line.shift(1)), 2,
                            np.where((macd > 0) & (macd.shift(1).notna()) & (macd_signal_line.shift(1).notna()) & (macd < macd_signal_line) & (macd.shift(1) >= macd_signal_line.shift(1)), -1, 0))
        macd_cross_signal = np.where((macd < 0) & (macd.shift(1).notna()) & (macd_signal_line.shift(1).notna()) & (macd > macd_signal_line) & (macd.shift(1) <= macd_signal_line.shift(1)), 1,
                            np.where((macd < 0) & (macd.shift(1).notna()) & (macd_signal_line.shift(1).notna()) & (macd < macd_signal_line) & (macd.shift(1) >= macd_signal_line.shift(1)), -2, macd_cross_signal))

        self.stock_metadata['stock_technical_data'][interval]['macd'] = {
            'macd': macd,
            'macd_signal_line': macd_signal_line,
            'macd_hist': macd_hist,
            'macd_cross_signal': macd_cross_signal
        }
    
    def rsi_formula(self, interval):
        """计算RSI指标"""
        params = {
            '1m': {'timeperiod': 9, 'overbought': 75, 'oversold': 25},
            '5m': {'timeperiod': 11, 'overbought': 73, 'oversold': 27},
            '15m': {'timeperiod': 12, 'overbought': 72, 'oversold': 28},
            '30m': {'timeperiod': 13, 'overbought': 71, 'oversold': 29},
            '60m': {'timeperiod': 14, 'overbought': 70, 'oversold': 30},
            '1d': {'timeperiod': 14, 'overbought': 70, 'oversold': 30},
            '1wk': {'timeperiod': 10, 'overbought': 65, 'oversold': 35},
            '1mo': {'timeperiod': 8, 'overbought': 65, 'oversold': 35}
        }
        
        df = self.stock_metadata['stock_technical_data'][interval]['stock_price']
        if df.empty or interval not in params:
            return
        
        rsi = talib.RSI(df['Close'], timeperiod=params[interval]['timeperiod'])
        rsi = pd.Series(rsi, index=df.index)
        rsi_overbs_signal = np.where(rsi.notna() & (rsi > params[interval]['overbought']), -1,
                            np.where(rsi.notna() & (rsi < params[interval]['oversold']), 1, 0))
        
        self.stock_metadata['stock_technical_data'][interval]['rsi'] = {
            'rsi': rsi,
            'rsi_overbs_signal': rsi_overbs_signal
        }

    def candlestick_pattern_signal(self, interval):
        """计算蜡烛图形态信号"""
        df = self.stock_metadata['stock_technical_data'][interval]['stock_price']
        if df.empty:
            return
            
        major_patterns = {
            'CDLENGULFING': 'Engulfing Pattern',
            'CDLHARAMI': 'Harami Pattern',
            'CDLDOJI': 'Doji',
            'CDLHAMMER': 'Hammer',
            'CDLSHOOTINGSTAR': 'Shooting Star'
        }

        op = df['Open'].astype(float)
        hi = df['High'].astype(float)
        lo = df['Low'].astype(float)
        cl = df['Close'].astype(float)
        output_df = pd.DataFrame(index=df.index)
        
        for pattern_func in major_patterns.keys():
            pattern_result = getattr(talib, pattern_func)(op, hi, lo, cl)
            pattern_result = pattern_result.fillna(0)
            output_df[pattern_func] = np.where(pattern_result > 0, 1,
                                                np.where(pattern_result < 0, -1, 0))
        
        output_df['cdl_pattern_signal'] = output_df.sum(axis=1)
        self.stock_metadata['stock_technical_data'][interval]['cdl_pattern'] = output_df

    def fundamentals_prep(self, period='Yearly'):
        """处理基本面数据"""
        try:
            # 由于Polygon.io免费版不支持基本面数据，返回空数据
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), 'USD'
            
        except Exception as e:
            print(f"Error in fundamentals_prep: {e}")
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), 'USD'

    def fundamentals_tables(self, period='Yearly'):
        """生成基本面表格"""
        try:
            # 由于Polygon.io免费版不支持基本面数据，返回空数据
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), 'USD'
            
        except Exception as e:
            print(f"Error in fundamentals_tables: {e}")
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), 'USD'



# ## New Way to identify the candlestick pattern if one day has multiple patterns
# def recognize_candlestick(df):
#     """
#     Recognizes candlestick patterns and appends 2 additional columns to df;
#     1st - Best Performance candlestick pattern matched by www.thepatternsite.com
#     2nd - # of matched patterns
#     """

#     op = df['Open'].astype(float)
#     hi = df['High'].astype(float)
#     lo = df['Low'].astype(float)
#     cl = df['Close'].astype(float)

#     candle_names = talib.get_function_groups()['Pattern Recognition']

#     # create columns for each candle
#     for candle in candle_names:
#         # below is same as;
#         # df["CDL3LINESTRIKE"] = talib.CDL3LINESTRIKE(op, hi, lo, cl)
#         df[candle] = getattr(talib, candle)(op, hi, lo, cl)


#     df['candlestick_pattern'] = np.nan

#     for index, row in df.iterrows():
#         # no bull/bear signal
#         if sum(row[candle_names]) == 0:
#             df.loc[index,'candlestick_pattern'] = "NO_SIGNAL"
#         # bull pattern found
#         elif sum(row[candle_names]) > 0:
#             df.loc[index,'candlestick_pattern'] = "BULL_SIGNAL"
#         else:
#             df.loc[index,'candlestick_pattern'] = "BEAR_SIGNAL"
    

#     # clean up candle columns
#     cols_to_drop = candle_names
#     df.drop(cols_to_drop, axis = 1, inplace = True)

#     return df




        ### when interval is 1d, we use 5, 10, 20, 30, 60, 120, 250 days moving average
        # if self.interval == '1d':
        #     ### SMA(simple moving average)
        #     tech_indicators['sma']['5'] = talib.SMA(df['Close'], timeperiod=5)
        #     tech_indicators['sma']['10'] = talib.SMA(df['Close'], timeperiod=10)
        #     tech_indicators['sma']['20'] = talib.SMA(df['Close'], timeperiod=20)
        #     tech_indicators['sma']['30'] = talib.SMA(df['Close'], timeperiod=30)
        #     tech_indicators['sma']['60'] = talib.SMA(df['Close'], timeperiod=60)
        #     tech_indicators['sma']['120'] = talib.SMA(df['Close'], timeperiod=120)
        #     tech_indicators['sma']['250'] = talib.SMA(df['Close'], timeperiod=250)
        #     tech_indicators['sma']['bbands_upper'], tech_indicators['sma']['bbands_middle'], tech_indicators['sma']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)

        #     ### EMA(exponential moving average)
        #     tech_indicators['ema']['5'] = talib.EMA(df['Close'], timeperiod=5)
        #     tech_indicators['ema']['10'] = talib.EMA(df['Close'], timeperiod=10)
        #     tech_indicators['ema']['20'] = talib.EMA(df['Close'], timeperiod=20)
        #     tech_indicators['ema']['30'] = talib.EMA(df['Close'], timeperiod=30)
        #     tech_indicators['ema']['60'] = talib.EMA(df['Close'], timeperiod=60)
        #     tech_indicators['ema']['120'] = talib.EMA(df['Close'], timeperiod=120)
        #     tech_indicators['ema']['250'] = talib.EMA(df['Close'], timeperiod=250)
        #     tech_indicators['ema']['bbands_upper'], tech_indicators['ema']['bbands_middle'], tech_indicators['ema']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=20, nbdevup=2, nbdevdn=2, matype=1)

        #     ### WMA(weighted moving average)
        #     tech_indicators['wma']['5'] = talib.WMA(df['Close'], timeperiod=5)
        #     tech_indicators['wma']['10'] = talib.WMA(df['Close'], timeperiod=10)
        #     tech_indicators['wma']['20'] = talib.WMA(df['Close'], timeperiod=20)
        #     tech_indicators['wma']['30'] = talib.WMA(df['Close'], timeperiod=30)
        #     tech_indicators['wma']['60'] = talib.WMA(df['Close'], timeperiod=60)
        #     tech_indicators['wma']['120'] = talib.WMA(df['Close'], timeperiod=120)
        #     tech_indicators['wma']['250'] = talib.WMA(df['Close'], timeperiod=250)
        #     tech_indicators['wma']['bbands_upper'], tech_indicators['wma']['bbands_middle'], tech_indicators['wma']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=20, nbdevup=2, nbdevdn=2, matype=2)

        #     ### DEMA(double exponential moving average)
        #     tech_indicators['dema']['5'] = talib.DEMA(df['Close'], timeperiod=5)
        #     tech_indicators['dema']['10'] = talib.DEMA(df['Close'], timeperiod=10)
        #     tech_indicators['dema']['20'] = talib.DEMA(df['Close'], timeperiod=20)
        #     tech_indicators['dema']['30'] = talib.DEMA(df['Close'], timeperiod=30) 
        #     tech_indicators['dema']['60'] = talib.DEMA(df['Close'], timeperiod=60)
        #     tech_indicators['dema']['120'] = talib.DEMA(df['Close'], timeperiod=120)
        #     tech_indicators['dema']['250'] = talib.DEMA(df['Close'], timeperiod=250)
        #     tech_indicators['dema']['bbands_upper'], tech_indicators['dema']['bbands_middle'], tech_indicators['dema']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=20, nbdevup=2, nbdevdn=2, matype=3)

        #     ### TEMA(triple exponential moving average)
        #     tech_indicators['tema']['5'] = talib.TEMA(df['Close'], timeperiod=5)
        #     tech_indicators['tema']['10'] = talib.TEMA(df['Close'], timeperiod=10)
        #     tech_indicators['tema']['20'] = talib.TEMA(df['Close'], timeperiod=20)
        #     tech_indicators['tema']['30'] = talib.TEMA(df['Close'], timeperiod=30)
        #     tech_indicators['tema']['60'] = talib.TEMA(df['Close'], timeperiod=60)
        #     tech_indicators['tema']['120'] = talib.TEMA(df['Close'], timeperiod=120)
        #     tech_indicators['tema']['250'] = talib.TEMA(df['Close'], timeperiod=250)
        #     tech_indicators['tema']['bbands_upper'], tech_indicators['tema']['bbands_middle'], tech_indicators['tema']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=20, nbdevup=2, nbdevdn=2, matype=4)

        #     ### KAMA(Kaufman's adaptive moving average)
        #     tech_indicators['kama']['5'] = talib.KAMA(df['Close'], timeperiod=5)
        #     tech_indicators['kama']['10'] = talib.KAMA(df['Close'], timeperiod=10)
        #     tech_indicators['kama']['20'] = talib.KAMA(df['Close'], timeperiod=20)
        #     tech_indicators['kama']['30'] = talib.KAMA(df['Close'], timeperiod=30)
        #     tech_indicators['kama']['60'] = talib.KAMA(df['Close'], timeperiod=60)
        #     tech_indicators['kama']['120'] = talib.KAMA(df['Close'], timeperiod=120)
        #     tech_indicators['kama']['250'] = talib.KAMA(df['Close'], timeperiod=250)
        #     tech_indicators['kama']['bbands_upper'], tech_indicators['kama']['bbands_middle'], tech_indicators['kama']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=20, nbdevup=2, nbdevdn=2, matype=6)

        # ### when interval is 1wk, we use 5, 10, 20, 30, 60 weeks moving average
        # elif self.interval == '1wk':
        #     ### SMA(simple moving average)
        #     tech_indicators['sma']['5'] = talib.SMA(df['Close'], timeperiod=5)
        #     tech_indicators['sma']['10'] = talib.SMA(df['Close'], timeperiod=10)
        #     tech_indicators['sma']['20'] = talib.SMA(df['Close'], timeperiod=20)
        #     tech_indicators['sma']['30'] = talib.SMA(df['Close'], timeperiod=30)
        #     tech_indicators['sma']['60'] = talib.SMA(df['Close'], timeperiod=60)
        #     tech_indicators['sma']['bbands_upper'], tech_indicators['sma']['bbands_middle'], tech_indicators['sma']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=18, nbdevup=2.1, nbdevdn=2.1, matype=0)

        #     ### EMA(exponential moving average)
        #     tech_indicators['ema']['5'] = talib.EMA(df['Close'], timeperiod=5)
        #     tech_indicators['ema']['10'] = talib.EMA(df['Close'], timeperiod=10)
        #     tech_indicators['ema']['20'] = talib.EMA(df['Close'], timeperiod=20)
        #     tech_indicators['ema']['30'] = talib.EMA(df['Close'], timeperiod=30)
        #     tech_indicators['ema']['60'] = talib.EMA(df['Close'], timeperiod=60)
        #     tech_indicators['ema']['bbands_upper'], tech_indicators['ema']['bbands_middle'], tech_indicators['ema']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=18, nbdevup=2.1, nbdevdn=2.1, matype=1)

        #     ### WMA(weighted moving average)
        #     tech_indicators['wma']['5'] = talib.WMA(df['Close'], timeperiod=5)
        #     tech_indicators['wma']['10'] = talib.WMA(df['Close'], timeperiod=10)
        #     tech_indicators['wma']['20'] = talib.WMA(df['Close'], timeperiod=20)
        #     tech_indicators['wma']['30'] = talib.WMA(df['Close'], timeperiod=30)
        #     tech_indicators['wma']['60'] = talib.WMA(df['Close'], timeperiod=60)
        #     tech_indicators['wma']['bbands_upper'], tech_indicators['wma']['bbands_middle'], tech_indicators['wma']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=18, nbdevup=2.1, nbdevdn=2.1, matype=2)

        #     ### DEMA(double exponential moving average)
        #     tech_indicators['dema']['5'] = talib.DEMA(df['Close'], timeperiod=5)
        #     tech_indicators['dema']['10'] = talib.DEMA(df['Close'], timeperiod=10)
        #     tech_indicators['dema']['20'] = talib.DEMA(df['Close'], timeperiod=20)
        #     tech_indicators['dema']['30'] = talib.DEMA(df['Close'], timeperiod=30)
        #     tech_indicators['dema']['60'] = talib.DEMA(df['Close'], timeperiod=60)
        #     tech_indicators['dema']['bbands_upper'], tech_indicators['dema']['bbands_middle'], tech_indicators['dema']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=18, nbdevup=2.1, nbdevdn=2.1, matype=3)

        #     ### TEMA(triple exponential moving average)
        #     tech_indicators['tema']['5'] = talib.TEMA(df['Close'], timeperiod=5)
        #     tech_indicators['tema']['10'] = talib.TEMA(df['Close'], timeperiod=10)
        #     tech_indicators['tema']['20'] = talib.TEMA(df['Close'], timeperiod=20)
        #     tech_indicators['tema']['30'] = talib.TEMA(df['Close'], timeperiod=30)
        #     tech_indicators['tema']['60'] = talib.TEMA(df['Close'], timeperiod=60)
        #     tech_indicators['tema']['bbands_upper'], tech_indicators['tema']['bbands_middle'], tech_indicators['tema']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=18, nbdevup=2.1, nbdevdn=2.1, matype=4)

        #     ### KAMA(Kaufman's adaptive moving average)
        #     tech_indicators['kama']['5'] = talib.KAMA(df['Close'], timeperiod=5)
        #     tech_indicators['kama']['10'] = talib.KAMA(df['Close'], timeperiod=10)
        #     tech_indicators['kama']['20'] = talib.KAMA(df['Close'], timeperiod=20)
        #     tech_indicators['kama']['30'] = talib.KAMA(df['Close'], timeperiod=30)
        #     tech_indicators['kama']['60'] = talib.KAMA(df['Close'], timeperiod=60)
        #     tech_indicators['kama']['bbands_upper'], tech_indicators['kama']['bbands_middle'], tech_indicators['kama']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=18, nbdevup=2.1, nbdevdn=2.1, matype=6)

        # ### when interval is 1mo, we use 3, 5, 10, 12, 24, 36 months moving average
        # elif self.interval == '1mo':
        #     ### SMA(simple moving average)
        #     tech_indicators['sma']['3'] = talib.SMA(df['Close'], timeperiod=3)
        #     tech_indicators['sma']['5'] = talib.SMA(df['Close'], timeperiod=5)
        #     tech_indicators['sma']['10'] = talib.SMA(df['Close'], timeperiod=10)
        #     tech_indicators['sma']['12'] = talib.SMA(df['Close'], timeperiod=12)
        #     tech_indicators['sma']['24'] = talib.SMA(df['Close'], timeperiod=24)
        #     tech_indicators['sma']['36'] = talib.SMA(df['Close'], timeperiod=36)
        #     tech_indicators['sma']['bbands_upper'], tech_indicators['sma']['bbands_middle'], tech_indicators['sma']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=10, nbdevup=2.3, nbdevdn=2.3, matype=0)

        #     ### EMA(exponential moving average)
        #     tech_indicators['ema']['3'] = talib.EMA(df['Close'], timeperiod=3)
        #     tech_indicators['ema']['5'] = talib.EMA(df['Close'], timeperiod=5)
        #     tech_indicators['ema']['10'] = talib.EMA(df['Close'], timeperiod=10)
        #     tech_indicators['ema']['12'] = talib.EMA(df['Close'], timeperiod=12)
        #     tech_indicators['ema']['24'] = talib.EMA(df['Close'], timeperiod=24)
        #     tech_indicators['ema']['36'] = talib.EMA(df['Close'], timeperiod=36)
        #     tech_indicators['ema']['bbands_upper'], tech_indicators['ema']['bbands_middle'], tech_indicators['ema']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=10, nbdevup=2.3, nbdevdn=2.3, matype=1)

        #     ### WMA(weighted moving average)
        #     tech_indicators['wma']['3'] = talib.WMA(df['Close'], timeperiod=3)
        #     tech_indicators['wma']['5'] = talib.WMA(df['Close'], timeperiod=5)
        #     tech_indicators['wma']['10'] = talib.WMA(df['Close'], timeperiod=10)
        #     tech_indicators['wma']['12'] = talib.WMA(df['Close'], timeperiod=12)
        #     tech_indicators['wma']['24'] = talib.WMA(df['Close'], timeperiod=24)
        #     tech_indicators['wma']['36'] = talib.WMA(df['Close'], timeperiod=36)
        #     tech_indicators['wma']['bbands_upper'], tech_indicators['wma']['bbands_middle'], tech_indicators['wma']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=10, nbdevup=2.3, nbdevdn=2.3, matype=2)

        #     ### DEMA(double exponential moving average)
        #     tech_indicators['dema']['3'] = talib.DEMA(df['Close'], timeperiod=3)
        #     tech_indicators['dema']['5'] = talib.DEMA(df['Close'], timeperiod=5)
        #     tech_indicators['dema']['10'] = talib.DEMA(df['Close'], timeperiod=10)
        #     tech_indicators['dema']['12'] = talib.DEMA(df['Close'], timeperiod=12)
        #     tech_indicators['dema']['24'] = talib.DEMA(df['Close'], timeperiod=24)
        #     tech_indicators['dema']['36'] = talib.DEMA(df['Close'], timeperiod=36)
        #     tech_indicators['dema']['bbands_upper'], tech_indicators['dema']['bbands_middle'], tech_indicators['dema']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=10, nbdevup=2.3, nbdevdn=2.3, matype=3)

        #     ### TEMA(triple exponential moving average)
        #     tech_indicators['tema']['3'] = talib.TEMA(df['Close'], timeperiod=3)
        #     tech_indicators['tema']['5'] = talib.TEMA(df['Close'], timeperiod=5)
        #     tech_indicators['tema']['10'] = talib.TEMA(df['Close'], timeperiod=10)
        #     tech_indicators['tema']['12'] = talib.TEMA(df['Close'], timeperiod=12)
        #     tech_indicators['tema']['24'] = talib.TEMA(df['Close'], timeperiod=24)
        #     tech_indicators['tema']['36'] = talib.TEMA(df['Close'], timeperiod=36)
        #     tech_indicators['tema']['bbands_upper'], tech_indicators['tema']['bbands_middle'], tech_indicators['tema']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=10, nbdevup=2.3, nbdevdn=2.3, matype=4)

        #     ### KAMA(Kaufman's adaptive moving average)
        #     tech_indicators['kama']['3'] = talib.KAMA(df['Close'], timeperiod=3)
        #     tech_indicators['kama']['5'] = talib.KAMA(df['Close'], timeperiod=5)
        #     tech_indicators['kama']['10'] = talib.KAMA(df['Close'], timeperiod=10)
        #     tech_indicators['kama']['12'] = talib.KAMA(df['Close'], timeperiod=12)
        #     tech_indicators['kama']['24'] = talib.KAMA(df['Close'], timeperiod=24)
        #     tech_indicators['kama']['36'] = talib.KAMA(df['Close'], timeperiod=36)
        #     tech_indicators['kama']['bbands_upper'], tech_indicators['kama']['bbands_middle'], tech_indicators['kama']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=10, nbdevup=2.3, nbdevdn=2.3, matype=6)
        
        # ### when interval is one 3mo(1 quarter), we use 2, 4, 8, 12, 16 months moving average
        # elif self.interval == '3mo':
        #     ### SMA(simple moving average)
        #     tech_indicators['sma']['2'] = talib.SMA(df['Close'], timeperiod=2)
        #     tech_indicators['sma']['4'] = talib.SMA(df['Close'], timeperiod=4)
        #     tech_indicators['sma']['8'] = talib.SMA(df['Close'], timeperiod=8)
        #     tech_indicators['sma']['12'] = talib.SMA(df['Close'], timeperiod=12)
        #     tech_indicators['sma']['16'] = talib.SMA(df['Close'], timeperiod=16)
        #     tech_indicators['sma']['bbands_upper'], tech_indicators['sma']['bbands_middle'], tech_indicators['sma']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=6, nbdevup=2.4, nbdevdn=2.4, matype=0)

        #     ### EMA(exponential moving average)
        #     tech_indicators['ema']['2'] = talib.EMA(df['Close'], timeperiod=2)
        #     tech_indicators['ema']['4'] = talib.EMA(df['Close'], timeperiod=4)
        #     tech_indicators['ema']['8'] = talib.EMA(df['Close'], timeperiod=8)
        #     tech_indicators['ema']['12'] = talib.EMA(df['Close'], timeperiod=12)
        #     tech_indicators['ema']['16'] = talib.EMA(df['Close'], timeperiod=16)
        #     tech_indicators['ema']['bbands_upper'], tech_indicators['ema']['bbands_middle'], tech_indicators['ema']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=6, nbdevup=2.4, nbdevdn=2.4, matype=1)

        #     ### WMA(weighted moving average)
        #     tech_indicators['wma']['2'] = talib.WMA(df['Close'], timeperiod=2)
        #     tech_indicators['wma']['4'] = talib.WMA(df['Close'], timeperiod=4)
        #     tech_indicators['wma']['8'] = talib.WMA(df['Close'], timeperiod=8)
        #     tech_indicators['wma']['12'] = talib.WMA(df['Close'], timeperiod=12)
        #     tech_indicators['wma']['16'] = talib.WMA(df['Close'], timeperiod=16)
        #     tech_indicators['wma']['bbands_upper'], tech_indicators['wma']['bbands_middle'], tech_indicators['wma']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=6, nbdevup=2.4, nbdevdn=2.4, matype=2)

        #     ### DEMA(double exponential moving average)
        #     tech_indicators['dema']['2'] = talib.DEMA(df['Close'], timeperiod=2)
        #     tech_indicators['dema']['4'] = talib.DEMA(df['Close'], timeperiod=4)
        #     tech_indicators['dema']['8'] = talib.DEMA(df['Close'], timeperiod=8)
        #     tech_indicators['dema']['12'] = talib.DEMA(df['Close'], timeperiod=12)
        #     tech_indicators['dema']['16'] = talib.DEMA(df['Close'], timeperiod=16)
        #     tech_indicators['dema']['bbands_upper'], tech_indicators['dema']['bbands_middle'], tech_indicators['dema']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=6, nbdevup=2.4, nbdevdn=2.4, matype=3)

        #     ### TEMA(triple exponential moving average)
        #     tech_indicators['tema']['2'] = talib.TEMA(df['Close'], timeperiod=2)
        #     tech_indicators['tema']['4'] = talib.TEMA(df['Close'], timeperiod=4)
        #     tech_indicators['tema']['8'] = talib.TEMA(df['Close'], timeperiod=8)
        #     tech_indicators['tema']['12'] = talib.TEMA(df['Close'], timeperiod=12)
        #     tech_indicators['tema']['16'] = talib.TEMA(df['Close'], timeperiod=16)
        #     tech_indicators['tema']['bbands_upper'], tech_indicators['tema']['bbands_middle'], tech_indicators['tema']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=6, nbdevup=2.4, nbdevdn=2.4, matype=4)

        #     ### KAMA(Kaufman's adaptive moving average)
        #     tech_indicators['kama']['2'] = talib.KAMA(df['Close'], timeperiod=2)
        #     tech_indicators['kama']['4'] = talib.KAMA(df['Close'], timeperiod=4)
        #     tech_indicators['kama']['8'] = talib.KAMA(df['Close'], timeperiod=8)
        #     tech_indicators['kama']['12'] = talib.KAMA(df['Close'], timeperiod=12)
        #     tech_indicators['kama']['16'] = talib.KAMA(df['Close'], timeperiod=16)
        #     tech_indicators['kama']['bbands_upper'], tech_indicators['kama']['bbands_middle'], tech_indicators['kama']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=6, nbdevup=2.4, nbdevdn=2.4, matype=6)
        
        # ### when interval is 1m, we use 5, 10, 20, 30, 60, 120 minutes moving average
        # elif self.interval == '1m':
        #     ### SMA(simple moving average)
        #     tech_indicators['sma']['5'] = talib.SMA(df['Close'], timeperiod=5)
        #     tech_indicators['sma']['10'] = talib.SMA(df['Close'], timeperiod=10)
        #     tech_indicators['sma']['20'] = talib.SMA(df['Close'], timeperiod=20)
        #     tech_indicators['sma']['30'] = talib.SMA(df['Close'], timeperiod=30)
        #     tech_indicators['sma']['60'] = talib.SMA(df['Close'], timeperiod=60)
        #     tech_indicators['sma']['120'] = talib.SMA(df['Close'], timeperiod=120)
        #     tech_indicators['sma']['bbands_upper'], tech_indicators['sma']['bbands_middle'], tech_indicators['sma']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=20, nbdevup=2.2, nbdevdn=2.0, matype=0) # slightly widen the upper band because the minute level volatility is large

        #     ### EMA(exponential moving average) 
        #     tech_indicators['ema']['5'] = talib.EMA(df['Close'], timeperiod=5)
        #     tech_indicators['ema']['10'] = talib.EMA(df['Close'], timeperiod=10)
        #     tech_indicators['ema']['20'] = talib.EMA(df['Close'], timeperiod=20)
        #     tech_indicators['ema']['30'] = talib.EMA(df['Close'], timeperiod=30)
        #     tech_indicators['ema']['60'] = talib.EMA(df['Close'], timeperiod=60)
        #     tech_indicators['ema']['120'] = talib.EMA(df['Close'], timeperiod=120)
        #     tech_indicators['ema']['bbands_upper'], tech_indicators['ema']['bbands_middle'], tech_indicators['ema']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=20, nbdevup=2.2, nbdevdn=2.0, matype=1) # slightly widen the upper band because the minute level volatility is large

        #     ### WMA(weighted moving average)
        #     tech_indicators['wma']['5'] = talib.WMA(df['Close'], timeperiod=5)
        #     tech_indicators['wma']['10'] = talib.WMA(df['Close'], timeperiod=10)
        #     tech_indicators['wma']['20'] = talib.WMA(df['Close'], timeperiod=20)
        #     tech_indicators['wma']['30'] = talib.WMA(df['Close'], timeperiod=30)
        #     tech_indicators['wma']['60'] = talib.WMA(df['Close'], timeperiod=60)
        #     tech_indicators['wma']['120'] = talib.WMA(df['Close'], timeperiod=120)
        #     tech_indicators['wma']['bbands_upper'], tech_indicators['wma']['bbands_middle'], tech_indicators['wma']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=20, nbdevup=2.2, nbdevdn=2.0, matype=2) # slightly widen the upper band because the minute level volatility is large

        #     ### DEMA(double exponential moving average)
        #     tech_indicators['dema']['5'] = talib.DEMA(df['Close'], timeperiod=5)
        #     tech_indicators['dema']['10'] = talib.DEMA(df['Close'], timeperiod=10)
        #     tech_indicators['dema']['20'] = talib.DEMA(df['Close'], timeperiod=20)
        #     tech_indicators['dema']['30'] = talib.DEMA(df['Close'], timeperiod=30)
        #     tech_indicators['dema']['60'] = talib.DEMA(df['Close'], timeperiod=60)
        #     tech_indicators['dema']['120'] = talib.DEMA(df['Close'], timeperiod=120)
        #     tech_indicators['dema']['bbands_upper'], tech_indicators['dema']['bbands_middle'], tech_indicators['dema']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=20, nbdevup=2.2, nbdevdn=2.0, matype=3) # slightly widen the upper band because the minute level volatility is large

        #     ### TEMA(triple exponential moving average)
        #     tech_indicators['tema']['5'] = talib.TEMA(df['Close'], timeperiod=5)
        #     tech_indicators['tema']['10'] = talib.TEMA(df['Close'], timeperiod=10)
        #     tech_indicators['tema']['20'] = talib.TEMA(df['Close'], timeperiod=20)
        #     tech_indicators['tema']['30'] = talib.TEMA(df['Close'], timeperiod=30)
        #     tech_indicators['tema']['60'] = talib.TEMA(df['Close'], timeperiod=60)
        #     tech_indicators['tema']['120'] = talib.TEMA(df['Close'], timeperiod=120)
        #     tech_indicators['tema']['bbands_upper'], tech_indicators['tema']['bbands_middle'], tech_indicators['tema']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=20, nbdevup=2.2, nbdevdn=2.0, matype=4) # slightly widen the upper band because the minute level volatility is large

        #     ### KAMA(Kaufman's adaptive moving average)
        #     tech_indicators['kama']['5'] = talib.KAMA(df['Close'], timeperiod=5)
        #     tech_indicators['kama']['10'] = talib.KAMA(df['Close'], timeperiod=10)
        #     tech_indicators['kama']['20'] = talib.KAMA(df['Close'], timeperiod=20)
        #     tech_indicators['kama']['30'] = talib.KAMA(df['Close'], timeperiod=30)
        #     tech_indicators['kama']['60'] = talib.KAMA(df['Close'], timeperiod=60)
        #     tech_indicators['kama']['120'] = talib.KAMA(df['Close'], timeperiod=120)
        #     tech_indicators['kama']['bbands_upper'], tech_indicators['kama']['bbands_middle'], tech_indicators['kama']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=20, nbdevup=2.2, nbdevdn=2.0, matype=6) # slightly widen the upper band because the minute level volatility is large

        # ### when interval is 5m, we use 6, 12, 24, 36, 72, 144 minutes moving average
        # elif self.interval == '5m':
        #     ### SMA(simple moving average)
        #     tech_indicators['sma']['6'] = talib.SMA(df['Close'], timeperiod=6)
        #     tech_indicators['sma']['12'] = talib.SMA(df['Close'], timeperiod=12)
        #     tech_indicators['sma']['24'] = talib.SMA(df['Close'], timeperiod=24)
        #     tech_indicators['sma']['36'] = talib.SMA(df['Close'], timeperiod=36)
        #     tech_indicators['sma']['72'] = talib.SMA(df['Close'], timeperiod=72)
        #     tech_indicators['sma']['144'] = talib.SMA(df['Close'], timeperiod=144)
        #     tech_indicators['sma']['bbands_upper'], tech_indicators['sma']['bbands_middle'], tech_indicators['sma']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=18, nbdevup=2.1, nbdevdn=2.1, matype=0)

        #     ### EMA(exponential moving average)
        #     tech_indicators['ema']['6'] = talib.EMA(df['Close'], timeperiod=6)
        #     tech_indicators['ema']['12'] = talib.EMA(df['Close'], timeperiod=12)
        #     tech_indicators['ema']['24'] = talib.EMA(df['Close'], timeperiod=24)
        #     tech_indicators['ema']['36'] = talib.EMA(df['Close'], timeperiod=36)
        #     tech_indicators['ema']['72'] = talib.EMA(df['Close'], timeperiod=72)
        #     tech_indicators['ema']['144'] = talib.EMA(df['Close'], timeperiod=144)
        #     tech_indicators['ema']['bbands_upper'], tech_indicators['ema']['bbands_middle'], tech_indicators['ema']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=18, nbdevup=2.1, nbdevdn=2.1, matype=1)

        #     ### WMA(weighted moving average)
        #     tech_indicators['wma']['6'] = talib.WMA(df['Close'], timeperiod=6)
        #     tech_indicators['wma']['12'] = talib.WMA(df['Close'], timeperiod=12)
        #     tech_indicators['wma']['24'] = talib.WMA(df['Close'], timeperiod=24)
        #     tech_indicators['wma']['36'] = talib.WMA(df['Close'], timeperiod=36)
        #     tech_indicators['wma']['72'] = talib.WMA(df['Close'], timeperiod=72)
        #     tech_indicators['wma']['144'] = talib.WMA(df['Close'], timeperiod=144)
        #     tech_indicators['wma']['bbands_upper'], tech_indicators['wma']['bbands_middle'], tech_indicators['wma']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=18, nbdevup=2.1, nbdevdn=2.1, matype=2)

        #     ### DEMA(double exponential moving average)
        #     tech_indicators['dema']['6'] = talib.DEMA(df['Close'], timeperiod=6)
        #     tech_indicators['dema']['12'] = talib.DEMA(df['Close'], timeperiod=12)
        #     tech_indicators['dema']['24'] = talib.DEMA(df['Close'], timeperiod=24)
        #     tech_indicators['dema']['36'] = talib.DEMA(df['Close'], timeperiod=36)
        #     tech_indicators['dema']['72'] = talib.DEMA(df['Close'], timeperiod=72)
        #     tech_indicators['dema']['144'] = talib.DEMA(df['Close'], timeperiod=144)
        #     tech_indicators['dema']['bbands_upper'], tech_indicators['dema']['bbands_middle'], tech_indicators['dema']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=18, nbdevup=2.1, nbdevdn=2.1, matype=3)

        #     ### TEMA(triple exponential moving average)
        #     tech_indicators['tema']['6'] = talib.TEMA(df['Close'], timeperiod=6)
        #     tech_indicators['tema']['12'] = talib.TEMA(df['Close'], timeperiod=12)
        #     tech_indicators['tema']['24'] = talib.TEMA(df['Close'], timeperiod=24)
        #     tech_indicators['tema']['36'] = talib.TEMA(df['Close'], timeperiod=36)
        #     tech_indicators['tema']['72'] = talib.TEMA(df['Close'], timeperiod=72)
        #     tech_indicators['tema']['144'] = talib.TEMA(df['Close'], timeperiod=144)
        #     tech_indicators['tema']['bbands_upper'], tech_indicators['tema']['bbands_middle'], tech_indicators['tema']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=18, nbdevup=2.1, nbdevdn=2.1, matype=4)

        #     ### KAMA(Kaufman's adaptive moving average)
        #     tech_indicators['kama']['6'] = talib.KAMA(df['Close'], timeperiod=6)
        #     tech_indicators['kama']['12'] = talib.KAMA(df['Close'], timeperiod=12)
        #     tech_indicators['kama']['24'] = talib.KAMA(df['Close'], timeperiod=24)
        #     tech_indicators['kama']['36'] = talib.KAMA(df['Close'], timeperiod=36)
        #     tech_indicators['kama']['72'] = talib.KAMA(df['Close'], timeperiod=72)
        #     tech_indicators['kama']['144'] = talib.KAMA(df['Close'], timeperiod=144)
        #     tech_indicators['kama']['bbands_upper'], tech_indicators['kama']['bbands_middle'], tech_indicators['kama']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=18, nbdevup=2.1, nbdevdn=2.1, matype=6)
        
        # ### when interval is 15m, we use 4, 8, 16, 24, 48, 96 minutes moving average
        # elif self.interval == '15m':
        #     ### SMA(simple moving average)
        #     tech_indicators['sma']['4'] = talib.SMA(df['Close'], timeperiod=4)
        #     tech_indicators['sma']['8'] = talib.SMA(df['Close'], timeperiod=8)
        #     tech_indicators['sma']['16'] = talib.SMA(df['Close'], timeperiod=16)
        #     tech_indicators['sma']['24'] = talib.SMA(df['Close'], timeperiod=24)
        #     tech_indicators['sma']['48'] = talib.SMA(df['Close'], timeperiod=48)
        #     tech_indicators['sma']['96'] = talib.SMA(df['Close'], timeperiod=96)
        #     tech_indicators['sma']['bbands_upper'], tech_indicators['sma']['bbands_middle'], tech_indicators['sma']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=15, nbdevup=2.0, nbdevdn=2.0, matype=0)

        #     ### EMA(exponential moving average)
        #     tech_indicators['ema']['4'] = talib.EMA(df['Close'], timeperiod=4)
        #     tech_indicators['ema']['8'] = talib.EMA(df['Close'], timeperiod=8)
        #     tech_indicators['ema']['16'] = talib.EMA(df['Close'], timeperiod=16)
        #     tech_indicators['ema']['24'] = talib.EMA(df['Close'], timeperiod=24)
        #     tech_indicators['ema']['48'] = talib.EMA(df['Close'], timeperiod=48)
        #     tech_indicators['ema']['96'] = talib.EMA(df['Close'], timeperiod=96)
        #     tech_indicators['ema']['bbands_upper'], tech_indicators['ema']['bbands_middle'], tech_indicators['ema']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=15, nbdevup=2.0, nbdevdn=2.0, matype=1)

        #     ### WMA(weighted moving average)
        #     tech_indicators['wma']['4'] = talib.WMA(df['Close'], timeperiod=4)
        #     tech_indicators['wma']['8'] = talib.WMA(df['Close'], timeperiod=8)
        #     tech_indicators['wma']['16'] = talib.WMA(df['Close'], timeperiod=16)
        #     tech_indicators['wma']['24'] = talib.WMA(df['Close'], timeperiod=24)
        #     tech_indicators['wma']['48'] = talib.WMA(df['Close'], timeperiod=48)
        #     tech_indicators['wma']['96'] = talib.WMA(df['Close'], timeperiod=96)
        #     tech_indicators['wma']['bbands_upper'], tech_indicators['wma']['bbands_middle'], tech_indicators['wma']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=15, nbdevup=2.0, nbdevdn=2.0, matype=2)

        #     ### DEMA(double exponential moving average)
        #     tech_indicators['dema']['4'] = talib.DEMA(df['Close'], timeperiod=4)
        #     tech_indicators['dema']['8'] = talib.DEMA(df['Close'], timeperiod=8)
        #     tech_indicators['dema']['16'] = talib.DEMA(df['Close'], timeperiod=16)
        #     tech_indicators['dema']['24'] = talib.DEMA(df['Close'], timeperiod=24)
        #     tech_indicators['dema']['48'] = talib.DEMA(df['Close'], timeperiod=48)
        #     tech_indicators['dema']['96'] = talib.DEMA(df['Close'], timeperiod=96)
        #     tech_indicators['dema']['bbands_upper'], tech_indicators['dema']['bbands_middle'], tech_indicators['dema']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=15, nbdevup=2.0, nbdevdn=2.0, matype=3)

        #     ### TEMA(triple exponential moving average)
        #     tech_indicators['tema']['4'] = talib.TEMA(df['Close'], timeperiod=4)
        #     tech_indicators['tema']['8'] = talib.TEMA(df['Close'], timeperiod=8)
        #     tech_indicators['tema']['16'] = talib.TEMA(df['Close'], timeperiod=16)
        #     tech_indicators['tema']['24'] = talib.TEMA(df['Close'], timeperiod=24)
        #     tech_indicators['tema']['48'] = talib.TEMA(df['Close'], timeperiod=48)
        #     tech_indicators['tema']['96'] = talib.TEMA(df['Close'], timeperiod=96)
        #     tech_indicators['tema']['bbands_upper'], tech_indicators['tema']['bbands_middle'], tech_indicators['tema']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=15, nbdevup=2.0, nbdevdn=2.0, matype=4)

        #     ### KAMA(Kaufman's adaptive moving average)
        #     tech_indicators['kama']['4'] = talib.KAMA(df['Close'], timeperiod=4)
        #     tech_indicators['kama']['8'] = talib.KAMA(df['Close'], timeperiod=8)
        #     tech_indicators['kama']['16'] = talib.KAMA(df['Close'], timeperiod=16)
        #     tech_indicators['kama']['24'] = talib.KAMA(df['Close'], timeperiod=24)
        #     tech_indicators['kama']['48'] = talib.KAMA(df['Close'], timeperiod=48)
        #     tech_indicators['kama']['96'] = talib.KAMA(df['Close'], timeperiod=96)
        #     tech_indicators['kama']['bbands_upper'], tech_indicators['kama']['bbands_middle'], tech_indicators['kama']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=15, nbdevup=2.0, nbdevdn=2.0, matype=6)

        # ### when interval is 30m, we use 3, 6, 12, 18, 36, 72 minutes moving average
        # elif self.interval == '30m':
        #     ### SMA(simple moving average)
        #     tech_indicators['sma']['3'] = talib.SMA(df['Close'], timeperiod=3)
        #     tech_indicators['sma']['6'] = talib.SMA(df['Close'], timeperiod=6)
        #     tech_indicators['sma']['12'] = talib.SMA(df['Close'], timeperiod=12)
        #     tech_indicators['sma']['18'] = talib.SMA(df['Close'], timeperiod=18)
        #     tech_indicators['sma']['36'] = talib.SMA(df['Close'], timeperiod=36)
        #     tech_indicators['sma']['72'] = talib.SMA(df['Close'], timeperiod=72)
        #     tech_indicators['sma']['bbands_upper'], tech_indicators['sma']['bbands_middle'], tech_indicators['sma']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=12, nbdevup=1.9, nbdevdn=1.9, matype=0)

        #     ### EMA(exponential moving average)
        #     tech_indicators['ema']['3'] = talib.EMA(df['Close'], timeperiod=3)
        #     tech_indicators['ema']['6'] = talib.EMA(df['Close'], timeperiod=6)
        #     tech_indicators['ema']['12'] = talib.EMA(df['Close'], timeperiod=12)
        #     tech_indicators['ema']['18'] = talib.EMA(df['Close'], timeperiod=18)
        #     tech_indicators['ema']['36'] = talib.EMA(df['Close'], timeperiod=36)
        #     tech_indicators['ema']['72'] = talib.EMA(df['Close'], timeperiod=72)
        #     tech_indicators['ema']['bbands_upper'], tech_indicators['ema']['bbands_middle'], tech_indicators['ema']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=12, nbdevup=1.9, nbdevdn=1.9, matype=1)

        #     ### WMA(weighted moving average)
        #     tech_indicators['wma']['3'] = talib.WMA(df['Close'], timeperiod=3)
        #     tech_indicators['wma']['6'] = talib.WMA(df['Close'], timeperiod=6)
        #     tech_indicators['wma']['12'] = talib.WMA(df['Close'], timeperiod=12)
        #     tech_indicators['wma']['18'] = talib.WMA(df['Close'], timeperiod=18)
        #     tech_indicators['wma']['36'] = talib.WMA(df['Close'], timeperiod=36)
        #     tech_indicators['wma']['72'] = talib.WMA(df['Close'], timeperiod=72)
        #     tech_indicators['wma']['bbands_upper'], tech_indicators['wma']['bbands_middle'], tech_indicators['wma']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=12, nbdevup=1.9, nbdevdn=1.9, matype=2)

        #     ### DEMA(double exponential moving average)
        #     tech_indicators['dema']['3'] = talib.DEMA(df['Close'], timeperiod=3)
        #     tech_indicators['dema']['6'] = talib.DEMA(df['Close'], timeperiod=6)
        #     tech_indicators['dema']['12'] = talib.DEMA(df['Close'], timeperiod=12)
        #     tech_indicators['dema']['18'] = talib.DEMA(df['Close'], timeperiod=18)
        #     tech_indicators['dema']['36'] = talib.DEMA(df['Close'], timeperiod=36)
        #     tech_indicators['dema']['72'] = talib.DEMA(df['Close'], timeperiod=72)
        #     tech_indicators['dema']['bbands_upper'], tech_indicators['dema']['bbands_middle'], tech_indicators['dema']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=12, nbdevup=1.9, nbdevdn=1.9, matype=3)

        #     ### TEMA(triple exponential moving average)
        #     tech_indicators['tema']['3'] = talib.TEMA(df['Close'], timeperiod=3)
        #     tech_indicators['tema']['6'] = talib.TEMA(df['Close'], timeperiod=6)
        #     tech_indicators['tema']['12'] = talib.TEMA(df['Close'], timeperiod=12)
        #     tech_indicators['tema']['18'] = talib.TEMA(df['Close'], timeperiod=18)
        #     tech_indicators['tema']['36'] = talib.TEMA(df['Close'], timeperiod=36)
        #     tech_indicators['tema']['72'] = talib.TEMA(df['Close'], timeperiod=72)
        #     tech_indicators['tema']['bbands_upper'], tech_indicators['tema']['bbands_middle'], tech_indicators['tema']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=12, nbdevup=1.9, nbdevdn=1.9, matype=4)

        #     ### KAMA(Kaufman's adaptive moving average)
        #     tech_indicators['kama']['3'] = talib.KAMA(df['Close'], timeperiod=3)
        #     tech_indicators['kama']['6'] = talib.KAMA(df['Close'], timeperiod=6)
        #     tech_indicators['kama']['12'] = talib.KAMA(df['Close'], timeperiod=12)
        #     tech_indicators['kama']['18'] = talib.KAMA(df['Close'], timeperiod=18)
        #     tech_indicators['kama']['36'] = talib.KAMA(df['Close'], timeperiod=36)
        #     tech_indicators['kama']['72'] = talib.KAMA(df['Close'], timeperiod=72)
        #     tech_indicators['kama']['bbands_upper'], tech_indicators['kama']['bbands_middle'], tech_indicators['kama']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=12, nbdevup=1.9, nbdevdn=1.9, matype=6)

        # ### when interval is 60m, we use 3, 5, 8, 13, 21, 34 minutes moving average
        # elif self.interval == '60m':
        #     ### SMA(simple moving average)
        #     tech_indicators['sma']['3'] = talib.SMA(df['Close'], timeperiod=3)
        #     tech_indicators['sma']['5'] = talib.SMA(df['Close'], timeperiod=5)
        #     tech_indicators['sma']['8'] = talib.SMA(df['Close'], timeperiod=8)
        #     tech_indicators['sma']['13'] = talib.SMA(df['Close'], timeperiod=13)
        #     tech_indicators['sma']['21'] = talib.SMA(df['Close'], timeperiod=21)
        #     tech_indicators['sma']['34'] = talib.SMA(df['Close'], timeperiod=34)
        #     tech_indicators['sma']['bbands_upper'], tech_indicators['sma']['bbands_middle'], tech_indicators['sma']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=10, nbdevup=1.8, nbdevdn=1.8, matype=0)

        #     ### EMA(exponential moving average)
        #     tech_indicators['ema']['3'] = talib.EMA(df['Close'], timeperiod=3)
        #     tech_indicators['ema']['5'] = talib.EMA(df['Close'], timeperiod=5)
        #     tech_indicators['ema']['8'] = talib.EMA(df['Close'], timeperiod=8)
        #     tech_indicators['ema']['13'] = talib.EMA(df['Close'], timeperiod=13)
        #     tech_indicators['ema']['21'] = talib.EMA(df['Close'], timeperiod=21)
        #     tech_indicators['ema']['34'] = talib.EMA(df['Close'], timeperiod=34)
        #     tech_indicators['ema']['bbands_upper'], tech_indicators['ema']['bbands_middle'], tech_indicators['ema']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=10, nbdevup=1.8, nbdevdn=1.8, matype=1)

        #     ### WMA(weighted moving average)
        #     tech_indicators['wma']['3'] = talib.WMA(df['Close'], timeperiod=3)
        #     tech_indicators['wma']['5'] = talib.WMA(df['Close'], timeperiod=5)
        #     tech_indicators['wma']['8'] = talib.WMA(df['Close'], timeperiod=8)
        #     tech_indicators['wma']['13'] = talib.WMA(df['Close'], timeperiod=13)
        #     tech_indicators['wma']['21'] = talib.WMA(df['Close'], timeperiod=21)
        #     tech_indicators['wma']['34'] = talib.WMA(df['Close'], timeperiod=34)
        #     tech_indicators['wma']['bbands_upper'], tech_indicators['wma']['bbands_middle'], tech_indicators['wma']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=10, nbdevup=1.8, nbdevdn=1.8, matype=2)

        #     ### DEMA(double exponential moving average)
        #     tech_indicators['dema']['3'] = talib.DEMA(df['Close'], timeperiod=3)
        #     tech_indicators['dema']['5'] = talib.DEMA(df['Close'], timeperiod=5)
        #     tech_indicators['dema']['8'] = talib.DEMA(df['Close'], timeperiod=8)
        #     tech_indicators['dema']['13'] = talib.DEMA(df['Close'], timeperiod=13)
        #     tech_indicators['dema']['21'] = talib.DEMA(df['Close'], timeperiod=21)
        #     tech_indicators['dema']['34'] = talib.DEMA(df['Close'], timeperiod=34)
        #     tech_indicators['dema']['bbands_upper'], tech_indicators['dema']['bbands_middle'], tech_indicators['dema']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=10, nbdevup=1.8, nbdevdn=1.8, matype=3)

        #     ### TEMA(triple exponential moving average)
        #     tech_indicators['tema']['3'] = talib.TEMA(df['Close'], timeperiod=3)
        #     tech_indicators['tema']['5'] = talib.TEMA(df['Close'], timeperiod=5)
        #     tech_indicators['tema']['8'] = talib.TEMA(df['Close'], timeperiod=8)
        #     tech_indicators['tema']['13'] = talib.TEMA(df['Close'], timeperiod=13)
        #     tech_indicators['tema']['21'] = talib.TEMA(df['Close'], timeperiod=21)
        #     tech_indicators['tema']['34'] = talib.TEMA(df['Close'], timeperiod=34)
        #     tech_indicators['tema']['bbands_upper'], tech_indicators['tema']['bbands_middle'], tech_indicators['tema']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=10, nbdevup=1.8, nbdevdn=1.8, matype=4)

        #     ### KAMA(Kaufman's adaptive moving average)
        #     tech_indicators['kama']['3'] = talib.KAMA(df['Close'], timeperiod=3)
        #     tech_indicators['kama']['5'] = talib.KAMA(df['Close'], timeperiod=5)
        #     tech_indicators['kama']['8'] = talib.KAMA(df['Close'], timeperiod=8)
        #     tech_indicators['kama']['13'] = talib.KAMA(df['Close'], timeperiod=13)
        #     tech_indicators['kama']['21'] = talib.KAMA(df['Close'], timeperiod=21)
        #     tech_indicators['kama']['34'] = talib.KAMA(df['Close'], timeperiod=34)
        #     tech_indicators['kama']['bbands_upper'], tech_indicators['kama']['bbands_middle'], tech_indicators['kama']['bbands_lower'] = talib.BBANDS(df['Close'], timeperiod=10, nbdevup=1.8, nbdevdn=1.8, matype=6)
        
        # else:
        #     print("Invalid interval")





# app = dash.Dash(__name__)
# app.layout = html.Div([
#     dcc.Graph(
#         id="graph",
#         figure=fig,
#         config={
#             "modeBarButtonsToAdd": [
#                 "drawline",           # 直线
#                 "drawopenpath",       # 自由曲线
#                 "drawclosedpath",     # 封闭多边形
#                 "drawcircle",         # 圆形
#                 "drawrect",           # 矩形
#                 "drawtext",           # 文字标注
#                 "eraseshape",         # 橡皮擦
#                 "toggleSpikelines",   # 十字准星
#                 "toggleHover",        # 切换悬停信息
#                 "hoverCompareCartesian", # 比较模式
#             ],
#             "modeBarButtonsToRemove": ["pan", "select2d", "lasso2d"],
#             "displaylogo": False,
#             "scrollZoom": True,       # 允许滚轮缩放
#             "editable": True,         # 允许编辑图表
#             "showEditInChartStudio": True,  # 显示编辑按钮
#             "toImageButtonOptions": {  # 自定义下载图片选项
#                 "format": "png",
#                 "filename": "stock_chart",
#                 "height": 1000,
#                 "width": 1400,
#                 "scale": 2
#             }
#         }
#     )
# ])

# if __name__ == "__main__":
#     app.run_server(debug=True)
