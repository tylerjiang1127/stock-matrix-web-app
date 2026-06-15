import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime, timedelta
from collections import defaultdict
import talib
from typing import Dict, Any, List, Optional
import finnhub
import gc  # For garbage collection


class StockMetaDataFetcher:
    def __init__(self, ticker, alpha_vantage_api_key, fetch_price=True):
        self.ticker = ticker
        self.api_key = alpha_vantage_api_key
        self.api_call_count = 0
        
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

        # Note: Fundamental data (overview, income statement, etc.) is now fetched on-demand
        # to speed up initialization. Only price data is fetched by default if fetch_price is True.
        
        if fetch_price:
            for interval in self.av_interval_mapping.keys():
                # Add small delay to avoid "Burst pattern detected" (limit 5 req/sec)
                # 0.5s delay guarantees max 2 req/sec per thread
                time.sleep(0.5) 
                
                self._fetch_stock_price_data(interval)
                
                # Check if stock price data is available before calculating technical indicators
                stock_price_df = self.stock_metadata['stock_technical_data'][interval].get('stock_price')
                if stock_price_df is None or stock_price_df.empty or 'Close' not in stock_price_df.columns:
                    print(f"⚠️ Skipping technical indicators for {self.ticker} {interval} (no price data)")
                    continue
                
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
            function = 'TIME_SERIES_DAILY_ADJUSTED'
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
                self.api_call_count += 1
                data = response.json()
                
                # Check for API errors
                if 'Error Message' in data:
                    error_msg = data['Error Message']
                    # Check if it's an "Invalid API call" - stock may not support this interval
                    if 'Invalid API call' in error_msg:
                        print(f"⚠️ {self.ticker} {interval} data not available from Alpha Vantage (not supported)")
                        # Store empty DataFrame to indicate data is not available
                        self.stock_metadata['stock_technical_data'][interval]['stock_price'] = pd.DataFrame()
                        return
                    raise Exception(f"Alpha Vantage Error: {error_msg}")
                
                if 'Note' in data or 'Information' in data:
                    msg = data.get('Note') or data.get('Information')
                    msg_str = str(msg).lower()
                    
                    # Case 1: Rate Limit Hit (Frequency, Daily Limit, or Burst Limit)
                    if 'call frequency' in msg_str or 'daily' in msg_str or 'burst' in msg_str:
                        if attempt < max_retries - 1:
                            print(f"⚠️ API Rate Limit Hit: {msg[:100]}...")
                            # For burst limit, 60s is overkill, but safe. 
                            # If it's just burst, maybe wait shorter? 
                            # But distinguishing is hard, let's stick to safe wait.
                            wait_time = 10 if 'burst' in msg_str else 60
                            print(f"Waiting {wait_time} seconds before retry...")
                            time.sleep(wait_time) 
                            continue
                        else:
                            raise Exception(f"API call frequency limit reached: {msg}")
                    
                    # Case 2: Premium Restriction or Other Info
                    else:
                        # Log it clearly so user can see it
                        print(f"ℹ️ API Information Received for {self.ticker} {interval}: {msg}")
                        # For premium users, 'Information' shouldn't happen unless it's an error
                        # We won't auto-downgrade yet, but we will print it.
                        raise Exception(f"API returned Information: {msg}")
                
                # Parse the data
                df = self._parse_stock_price_data_response(data, interval)
                
                if df.empty:
                    print(f"⚠️ No data returned from Alpha Vantage for {self.ticker} {interval}")
                    self.stock_metadata['stock_technical_data'][interval]['stock_price'] = pd.DataFrame()
                    return
                
                print(f"Successfully fetched {len(df)} data points for {self.ticker}")
                self.stock_metadata['stock_technical_data'][interval]['stock_price'] = df

                return
                
            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(5)  # Wait before retry
                else:
                    # After all retries failed, store empty DataFrame
                    print(f"❌ All attempts failed for {self.ticker} {interval}, skipping this interval")
                    self.stock_metadata['stock_technical_data'][interval]['stock_price'] = pd.DataFrame()
                    return
    
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
                'Monthly Time Series',
                'Time Series (Daily) Adjusted'
            ]
            
            for key in possible_keys:
                if key in data:
                    time_series_key = key
                    break
            
            if not time_series_key:
                available_keys = list(data.keys())
                print(f"Available keys: {available_keys}")
                if 'Information' in data:
                    print(f"ℹ️ API Information Message (in parse): {data['Information']}")
                raise Exception(f"No recognized time series key found. Available: {available_keys}")
            
            time_series = data[time_series_key]
            
            if not time_series:
                raise Exception("Time series data is empty")
            
            print(f"Found {len(time_series)} data points in {time_series_key}")
            
            # Convert to DataFrame
            df_data = []
            for timestamp, values in time_series.items():
                try:
                    # check if it is adjusted data format
                    if '5. adjusted close' in values:
                        # 计算调整因子
                        original_close = float(values['4. close'])
                        adjusted_close = float(values['5. adjusted close'])
                        adjustment_factor = adjusted_close / original_close
                        
                        # apply the same adjustment factor to all prices
                        row = {
                            'Datetime': pd.to_datetime(timestamp),
                            'Open': float(values['1. open']) * adjustment_factor,
                            'High': float(values['2. high']) * adjustment_factor,
                            'Low': float(values['3. low']) * adjustment_factor,
                            'Close': adjusted_close,
                            'Volume': int(values['6. volume'])
                        }
                    else:
                        # use normal price (minute data etc.)
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
            df.sort_index(inplace=True)
            
            print(f"Successfully parsed {len(df)} data points")
            
            # ⚡ CRITICAL FIX: Apply filtering based on interval type
            # - Minute/Hour data: Filter to reduce database size
            # - Daily and above: Keep all historical data
            if interval in ['1m', '5m', '15m', '30m', '60m']:
                # For intraday data, apply filtering
                df_filtered = self._filter_data_by_interval(df, interval)
                print(f"   ⚡ Filtered to {len(df_filtered)} data points for {interval}")
                return df_filtered  # ✅ Return filtered data
            else:
                # For daily and above, keep all data
                print(f"   📊 Keeping all {len(df)} historical data points for {interval}")
                return df  # ✅ Return all data
            
        except Exception as e:
            print(f"Error in _parse_stock_price_data_response: {e}")
            return pd.DataFrame()

    def _filter_data_by_interval(self, df, interval):
        """Filter data based on interval type to optimize database storage
        
        Strategy:
        - Intraday data (minutes/hours): Filter to keep only recent data
        - This method should ONLY be called for intraday intervals
        - Daily and above intervals keep all data (not filtered)
        """
        
        if df.empty:
            return df
        
        now = datetime.now()
        
        # ⚡ Intraday filtering logic
        if interval in ['30m', '60m']:
            # For 30m and 60m, keep 1 month of data
            start_date = now - timedelta(days=30)
            df = df[df.index >= start_date]
            
        elif interval in ['5m', '15m']:
            # For 5m and 15m, keep 5 days of data
            start_date = now - timedelta(days=5)
            df = df[df.index >= start_date]
            
        elif interval == '1m':
            # For 1m, keep 1 day of data
            start_date = now - timedelta(days=1)
            df = df[df.index >= start_date]
        
        return df
    
    def fetch_company_overview(self):
        """Fetch company overview from Alpha Vantage (Public method for on-demand fetching)"""
        
        base_url = "https://www.alphavantage.co/query"
        params = {
            'function': 'OVERVIEW',
            'symbol': self.ticker,
            'apikey': self.api_key
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.get(base_url, params=params, timeout=15)
                response.raise_for_status()
                self.api_call_count += 1
                data = response.json()
                
                # Check for Rate Limit / Information
                if 'Note' in data or 'Information' in data:
                    msg = data.get('Note') or data.get('Information')
                    msg_str = str(msg).lower()
                    
                    if 'call frequency' in msg_str or 'daily' in msg_str or 'burst' in msg_str:
                        if attempt < max_retries - 1:
                            wait_time = 10 if 'burst' in msg_str else 60
                            print(f"⚠️ API Rate Limit Hit (Overview): {msg[:100]}... Waiting {wait_time}s")
                            time.sleep(wait_time)
                            continue
                        else:
                            print(f"❌ API rate limit reached for Overview: {msg}")
                            return {'symbol': self.ticker}
                    else:
                        print(f"ℹ️ API Information (Overview): {msg}")
                
                if 'Symbol' not in data:
                    if attempt < max_retries - 1:
                        print(f"Warning: No Symbol in response for {self.ticker}, retrying...")
                        time.sleep(2)
                        continue
                    print(f"Warning: No company overview data for {self.ticker}")
                    return {'symbol': self.ticker}
                
                # DEBUG: Print available keys to confirm data arrival
                print(f"DEBUG: Alpha Vantage OVERVIEW keys for {self.ticker}: {list(data.keys())}")
                # DEBUG: Print a few values to verify
                debug_keys = ['PERatio', 'MarketCapitalization', 'EPS', 'RevenueTTM', 'ProfitMargin']
                print(f"DEBUG: Sample values: { {k: data.get(k) for k in debug_keys} }")
                
                # convert Alpha Vantage format to yfinance-like format with professional metrics
                company_info = {
                    'symbol': data.get('Symbol', self.ticker),
                    'longName': data.get('Name', 'N/A'),
                    'exchange': data.get('Exchange', 'N/A'),
                    'sector': data.get('Sector', 'N/A'),
                    'industry': data.get('Industry', 'N/A'),
                    'country': data.get('Country', 'N/A'),
                    'fiscalYearEnd': data.get('FiscalYearEnd', 'N/A'),
                    'currency': data.get('Currency', 'USD'),
                    'longBusinessSummary': data.get('Description', 'No description available.'),
                    
                    # Valuation Metrics
                    'marketCap': self._safe_int(data.get('MarketCapitalization', 0)),
                    'ebitda': self._safe_int(data.get('EBITDA', 0)),
                    'peRatio': self._safe_float(data.get('PERatio', 0)),
                    'forwardPE': self._safe_float(data.get('ForwardPE', 0)),
                    'pegRatio': self._safe_float(data.get('PEGRatio', 0)),
                    'bookValue': self._safe_float(data.get('BookValue', 0)),
                    'dividendPerShare': self._safe_float(data.get('DividendPerShare', 0)),
                    'dividendYield': self._safe_float(data.get('DividendYield', 0)),
                    
                    # Profitability Metrics
                    'eps': self._safe_float(data.get('EPS', 0)),
                    'revenueTTM': self._safe_int(data.get('RevenueTTM', 0)),
                    'grossProfitTTM': self._safe_int(data.get('GrossProfitTTM', 0)),
                    'dilutedEPSTTM': self._safe_float(data.get('DilutedEPSTTM', 0)),
                    'profitMargin': self._safe_float(data.get('ProfitMargin', 0)),
                    'operatingMarginTTM': self._safe_float(data.get('OperatingMarginTTM', 0)),
                    'returnOnAssetsTTM': self._safe_float(data.get('ReturnOnAssetsTTM', 0)),
                    'returnOnEquityTTM': self._safe_float(data.get('ReturnOnEquityTTM', 0)),
                    
                    # Price Statistics
                    'beta': self._safe_float(data.get('Beta', 0)),
                    '52WeekHigh': self._safe_float(data.get('52WeekHigh', 0)),
                    '52WeekLow': self._safe_float(data.get('52WeekLow', 0)),
                    '50DayMovingAverage': self._safe_float(data.get('50DayMovingAverage', 0)),
                    '200DayMovingAverage': self._safe_float(data.get('200DayMovingAverage', 0)),
                    'analystTargetPrice': self._safe_float(data.get('AnalystTargetPrice', 0)),
                    'priceToSalesRatioTTM': self._safe_float(data.get('PriceToSalesRatioTTM', 0)),
                    'priceToBookRatio': self._safe_float(data.get('PriceToBookRatio', 0)),
                    'evToRevenue': self._safe_float(data.get('EVToRevenue', 0)),
                    'evToEBITDA': self._safe_float(data.get('EVToEBITDA', 0)),
                }
                
                self.stock_metadata['company_overview'] = company_info
                # Break loop on success
                break
            
            except Exception as e:
                print(f"Error fetching company overview for {self.ticker}: {e}")
                if attempt == max_retries - 1:
                    self.stock_metadata['company_overview'] = {'symbol': self.ticker}
    
    def _safe_float(self, value):
        """Safely convert value to float, return None if invalid"""
        try:
            if value == 'None' or value == '' or value is None or value == '-':
                return None
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def _safe_int(self, value):
        """Safely convert value to int, return None if invalid"""
        try:
            if value == 'None' or value == '' or value is None or value == '-':
                return None
            return int(float(value))
        except (ValueError, TypeError):
            return None

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

        # ✅ OPTIMIZED MA PERIODS - Each interval has its own optimized MA periods
        # This design matches professional trading practices where different timeframes require different MA periods
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
            # daily and above parameters
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
            if v == v:  # check if it is nan
                k0 = k_factor * v + (1 - k_factor) * k0
                k_list.append(k0)
            else:
                k_list.append(np.nan)

        d_list = []
        for k in k_list:
            if k == k:  # check if it is nan
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
            # daily and above parameters
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
            # daily and above parameters
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
    def fetch_fundamental_data(self):
        """get fundamentals data from alpha vantage (Public method for on-demand fetching)"""
        try:
            print(f"Fetching fundamental data for {self.ticker}...")
            
            # get annual and quarterly financial data
            # Add delays between API calls to avoid rate limiting
            income_statement_annual, income_statement_quarterly = self._fetch_income_statement()
            
            time.sleep(0.1)  # Wait 0.1 second between API calls to avoid burst limits
            
            balance_sheet_annual, balance_sheet_quarterly = self._fetch_balance_sheet()
            
            time.sleep(0.1)  # Wait 0.1 second between API calls to avoid burst limits
            
            cash_flow_annual, cash_flow_quarterly = self._fetch_cash_flow()
            
            # Process the data to convert field names to standard format
            # This ensures consistent field names for frontend display
            processed_income_annual = self._process_income_statement(income_statement_annual) if not income_statement_annual.empty else pd.DataFrame()
            processed_income_quarterly = self._process_income_statement(income_statement_quarterly) if not income_statement_quarterly.empty else pd.DataFrame()
            
            processed_balance_annual = self._process_balance_sheet(balance_sheet_annual) if not balance_sheet_annual.empty else pd.DataFrame()
            processed_balance_quarterly = self._process_balance_sheet(balance_sheet_quarterly) if not balance_sheet_quarterly.empty else pd.DataFrame()
            
            processed_cash_annual = self._process_cash_flow(cash_flow_annual, processed_income_annual) if not cash_flow_annual.empty else pd.DataFrame()
            processed_cash_quarterly = self._process_cash_flow(cash_flow_quarterly, processed_income_quarterly) if not cash_flow_quarterly.empty else pd.DataFrame()
            
            # process and store financial data (with processed field names)
            self.stock_metadata['stock_fundamental'] = {
                'annual': {
                    'income_statement': processed_income_annual,
                    'balance_sheet': processed_balance_annual,
                    'cash_flow': processed_cash_annual
                },
                'quarterly': {
                    'income_statement': processed_income_quarterly,
                    'balance_sheet': processed_balance_quarterly,
                    'cash_flow': processed_cash_quarterly
                }
            }
            
            print(f"✅ Successfully fetched and processed fundamental data for {self.ticker}")
            
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
            self.api_call_count += 1
            data = response.json()
            
            if 'Error Message' in data:
                raise Exception(f"Alpha Vantage Error: {data['Error Message']}")
            
            if 'Note' in data or 'Information' in data:
                msg = data.get('Note') or data.get('Information')
                print(f"⚠️ API rate limit for income statement: {msg}")
                return pd.DataFrame(), pd.DataFrame()  # Return TWO empty DataFrames
            
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
            response = requests.get(base_url, params=params, timeout=30)
            response.raise_for_status()
            self.api_call_count += 1
            data = response.json()
            
            if 'Error Message' in data:
                raise Exception(f"Alpha Vantage Error: {data['Error Message']}")
            
            if 'Note' in data or 'Information' in data:
                msg = data.get('Note') or data.get('Information')
                print(f"⚠️ API rate limit for balance sheet: {msg}")
                return pd.DataFrame(), pd.DataFrame()  # Return TWO empty DataFrames
            
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
                'cashAndCashEquivalentsAtCarryingValue', 'totalCurrentAssets', 'totalCurrentLiabilities',
                'currentAssets', 'currentLiabilities'  # Handle both naming conventions
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
            response = requests.get(base_url, params=params, timeout=30)
            response.raise_for_status()
            self.api_call_count += 1
            data = response.json()
            
            if 'Error Message' in data:
                raise Exception(f"Alpha Vantage Error: {data['Error Message']}")
            
            if 'Note' in data or 'Information' in data:
                msg = data.get('Note') or data.get('Information')
                print(f"⚠️ API rate limit for cash flow: {msg}")
                return pd.DataFrame(), pd.DataFrame()  # Return TWO empty DataFrames
            
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
            if df.empty:
                return pd.DataFrame()
            
            # Create a new DataFrame with renamed columns
            processed_df = pd.DataFrame()
            
            # Map Alpha Vantage columns to our standard names (handle multiple possible names)
            column_mappings = {
                'fiscalDateEnding': 'fiscalDateEnding',
                'totalAssets': 'Total Assets',
                'totalLiabilities': 'Total Liab',
                'totalShareholderEquity': 'Total Stockholder Equity',
                'cashAndCashEquivalentsAtCarryingValue': 'Cash',
                # Handle both naming conventions for current assets/liabilities
                'currentAssets': 'Total Current Assets',
                'totalCurrentAssets': 'Total Current Assets',
                'currentLiabilities': 'Total Current Liabilities',
                'totalCurrentLiabilities': 'Total Current Liabilities'
            }
            
            # Copy each column if it exists (later mappings override earlier ones for same target)
            for orig_col, new_col in column_mappings.items():
                if orig_col in df.columns:
                    processed_df[new_col] = df[orig_col].copy()
            
            # format date
            if 'fiscalDateEnding' in processed_df.columns:
                try:
                    processed_df['fiscalDateEnding'] = pd.to_datetime(processed_df['fiscalDateEnding']).dt.strftime('%Y-%m-%d')
                except:
                    pass  # Keep original if conversion fails
            
            # ensure numeric columns are float type
            numeric_cols = ['Total Assets', 'Total Liab', 'Total Stockholder Equity', 
                           'Cash', 'Total Current Assets', 'Total Current Liabilities']
            for col in numeric_cols:
                if col in processed_df.columns:
                    processed_df[col] = pd.to_numeric(processed_df[col], errors='coerce').fillna(0)
            
            # calculate ratios if we have the required columns
            if 'Total Current Liabilities' in processed_df.columns and 'Cash' in processed_df.columns:
                processed_df['Cash Ratio'] = np.where(
                    processed_df['Total Current Liabilities'] != 0,
                    processed_df['Cash'] / processed_df['Total Current Liabilities'],
                    0
                )
            
            if 'Total Current Liabilities' in processed_df.columns and 'Total Current Assets' in processed_df.columns:
                processed_df['Current Ratio'] = np.where(
                    processed_df['Total Current Liabilities'] != 0,
                    processed_df['Total Current Assets'] / processed_df['Total Current Liabilities'],
                    0
                )
            
            return processed_df
            
        except Exception as e:
            print(f"Error processing balance sheet: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()

    def _process_cash_flow(self, df, income_statement):
        """process cash flow data"""
        try:
            if df.empty:
                return pd.DataFrame()
            
            # Create a new DataFrame with renamed columns
            processed_df = pd.DataFrame()
            
            # Map Alpha Vantage columns to our standard names
            column_mapping = {
                'fiscalDateEnding': 'fiscalDateEnding',
                'operatingCashflow': 'Total Cash From Operating Activities',
                'cashflowFromInvestment': 'Total Cashflows From Investing Activities',
                'cashflowFromFinancing': 'Total Cash From Financing Activities',
                'capitalExpenditures': 'Capital Expenditures'
            }
            
            # Copy each column if it exists
            for orig_col, new_col in column_mapping.items():
                if orig_col in df.columns:
                    processed_df[new_col] = df[orig_col].copy()
            
            # format date
            if 'fiscalDateEnding' in processed_df.columns:
                try:
                    processed_df['fiscalDateEnding'] = pd.to_datetime(processed_df['fiscalDateEnding']).dt.strftime('%Y-%m-%d')
                except:
                    pass  # Keep original if conversion fails
            
            # ensure numeric columns are float type
            numeric_cols = ['Total Cash From Operating Activities', 'Total Cashflows From Investing Activities', 
                           'Total Cash From Financing Activities', 'Capital Expenditures']
            for col in numeric_cols:
                if col in processed_df.columns:
                    processed_df[col] = pd.to_numeric(processed_df[col], errors='coerce').fillna(0)
            
            # calculate free cash flow if we have the required columns
            if 'Total Cash From Operating Activities' in processed_df.columns and 'Capital Expenditures' in processed_df.columns:
                processed_df['Free Cash Flow'] = (processed_df['Total Cash From Operating Activities'] + 
                                                processed_df['Capital Expenditures'])
            
            # calculate operating cash flow/sales ratio
            if ('Total Cash From Operating Activities' in processed_df.columns and 
                not income_statement.empty and 'Total Revenue' in income_statement.columns):
                # ensure two DataFrames have the same number of rows
                min_rows = min(len(processed_df), len(income_statement))
                if min_rows > 0:
                    revenue = income_statement['Total Revenue'].iloc[:min_rows].values
                    operating_cf = processed_df['Total Cash From Operating Activities'].iloc[:min_rows].values
                    ratio = np.where(revenue != 0, operating_cf / revenue, 0)
                    # Pad with zeros if processed_df is longer
                    if len(processed_df) > min_rows:
                        ratio = np.append(ratio, np.zeros(len(processed_df) - min_rows))
                    processed_df['OperatingCashflow/SalesRatio'] = ratio
                else:
                    processed_df['OperatingCashflow/SalesRatio'] = 0
            else:
                processed_df['OperatingCashflow/SalesRatio'] = 0
            
            return processed_df
            
        except Exception as e:
            print(f"Error processing cash flow: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()
    
    def fetch_news_sentiment(self, limit=50):
        """
        Fetch news sentiment data for the ticker (last 24 hours)
        
        Args:
            limit: Maximum number of articles to fetch (default 50)
        
        Returns:
            Dictionary with sentiment data and news articles
        """
        try:
            print(f"Fetching news sentiment for {self.ticker}...")
            
            # Calculate time range for last 24 hours
            from datetime import datetime, timedelta
            time_to = datetime.now()
            time_from = time_to - timedelta(hours=24)
            
            url = "https://www.alphavantage.co/query"
            params = {
                "function": "NEWS_SENTIMENT",
                "tickers": self.ticker,
                "apikey": self.api_key,
                "limit": limit,
                "sort": "LATEST"
                # Note: time_from and time_to may not be supported by all API tiers
                # Remove them if they cause issues, API will return latest articles
            }
            
            # Try with time range first, but don't fail if it doesn't work
            try:
                params["time_from"] = time_from.strftime("%Y%m%dT%H%M")
                params["time_to"] = time_to.strftime("%Y%m%dT%H%M")
            except:
                pass  # If time formatting fails, continue without time filters
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            self.api_call_count += 1
            data = response.json()
            
            print(f"DEBUG: News sentiment API response keys: {list(data.keys())}")
            
            if "Error Message" in data:
                print(f"Error fetching news sentiment: {data['Error Message']}")
                return {
                    "average_sentiment_score": 0,
                    "average_sentiment_label": "Neutral",
                    "total_articles": 0,
                    "articles": []
                }
            
            if "Note" in data or "Information" in data:
                msg = data.get("Note") or data.get("Information")
                print(f"⚠️ API rate limit for news sentiment: {msg}")
                return {
                    "average_sentiment_score": 0,
                    "average_sentiment_label": "Neutral",
                    "total_articles": 0,
                    "articles": []
                }
            
            # Process articles
            articles = data.get("feed", [])
            print(f"DEBUG: Total articles from API: {len(articles)}")
            
            # Filter articles from last 24 hours
            filtered_articles = []
            for article in articles:
                time_published = article.get("time_published", "")
                if time_published:
                    try:
                        # Format: "20241217T143000"
                        article_time = datetime.strptime(time_published, "%Y%m%dT%H%M%S")
                        if article_time >= time_from:
                            filtered_articles.append(article)
                    except:
                        # If parsing fails, include the article anyway
                        filtered_articles.append(article)
                else:
                    # If no time, include it (might be recent)
                    filtered_articles.append(article)
            
            print(f"DEBUG: Articles after 24h filter: {len(filtered_articles)}")
            
            # Calculate weighted average sentiment score for this ticker using relevance_score as weight
            weighted_sum = 0.0
            total_weight = 0.0
            processed_articles = []
            
            for article in filtered_articles:
                # Get ticker-specific sentiment
                ticker_sentiments = article.get("ticker_sentiment", [])
                found_ticker = False
                
                for ts in ticker_sentiments:
                    if ts.get("ticker") == self.ticker:
                        found_ticker = True
                        score = ts.get("ticker_sentiment_score")
                        relevance = float(ts.get("relevance_score", 0))
                        
                        if score:
                            score_float = float(score)
                            # Use relevance_score as weight (if relevance is 0, use a small default weight to avoid division by zero)
                            weight = relevance if relevance > 0 else 0.1
                            weighted_sum += score_float * weight
                            total_weight += weight
                        
                        # Process article data
                        processed_articles.append({
                            "title": article.get("title", "No title"),
                            "url": article.get("url", ""),
                            "source": article.get("source", "Unknown"),
                            "time_published": article.get("time_published", ""),
                            "summary": article.get("summary", ""),
                            "banner_image": article.get("banner_image", ""),
                            "sentiment_score": float(score) if score else 0,
                            "sentiment_label": ts.get("ticker_sentiment_label", "Neutral"),
                            "relevance_score": relevance
                        })
                        break
                
                # If no ticker-specific sentiment found, use overall sentiment with lower weight
                if not found_ticker and len(processed_articles) < limit:
                    overall_score = article.get("overall_sentiment_score")
                    if overall_score:
                        score_float = float(overall_score)
                        # Use a lower default weight (0.3) for overall sentiment since it's less relevant
                        weight = 0.3
                        weighted_sum += score_float * weight
                        total_weight += weight
                    
                    processed_articles.append({
                        "title": article.get("title", "No title"),
                        "url": article.get("url", ""),
                        "source": article.get("source", "Unknown"),
                        "time_published": article.get("time_published", ""),
                        "summary": article.get("summary", ""),
                        "banner_image": article.get("banner_image", ""),
                        "sentiment_score": float(overall_score) if overall_score else 0,
                        "sentiment_label": article.get("overall_sentiment_label", "Neutral"),
                        "relevance_score": 0
                    })
            
            print(f"DEBUG: Processed articles with sentiment: {len(processed_articles)}")
            print(f"DEBUG: Weighted sum: {weighted_sum:.4f}, Total weight: {total_weight:.4f}")
            
            # Calculate weighted average sentiment
            avg_score = weighted_sum / total_weight if total_weight > 0 else 0
            
            # Determine sentiment label
            if avg_score >= 0.35:
                sentiment_label = "Bullish"
            elif avg_score >= 0.15:
                sentiment_label = "Somewhat-Bullish"
            elif avg_score >= -0.15:
                sentiment_label = "Neutral"
            elif avg_score >= -0.35:
                sentiment_label = "Somewhat-Bearish"
            else:
                sentiment_label = "Bearish"
            
            result = {
                "average_sentiment_score": round(avg_score, 4),
                "average_sentiment_label": sentiment_label,
                "total_articles": len(processed_articles),
                "articles": processed_articles
            }
            
            print(f"✅ Successfully fetched {len(processed_articles)} news articles for {self.ticker} (avg sentiment: {avg_score:.4f})")
            return result
            
        except Exception as e:
            print(f"Error fetching news sentiment for {self.ticker}: {e}")
            import traceback
            traceback.print_exc()
            return {
                "average_sentiment_score": 0,
                "average_sentiment_label": "Neutral",
                "total_articles": 0,
                "articles": []
            }

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


