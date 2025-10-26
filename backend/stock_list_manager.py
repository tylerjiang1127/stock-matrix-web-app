import requests
import pandas as pd
import time
from typing import List, Dict, Any

class StockListManager:
    def __init__(self, max_stocks=None):
        self.max_stocks = max_stocks
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
            # Test NASDAQ API
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
                    time.sleep(1)  # Avoid requests too fast
                
                if exchange_stocks:
                    stocks_df = pd.DataFrame(exchange_stocks)
                    stocks_df['exchange'] = exchange.upper()
                    all_stocks.append(stocks_df)
            
            if not all_stocks:
                raise Exception("No stock data retrieved")
            
            # Merge data
            df = pd.concat(all_stocks, ignore_index=True)
            
            # Clean data
            required_columns = ['symbol', 'name', 'exchange']
            optional_columns = ['marketCap', 'volume']
            
            # Ensure required columns exist
            for col in required_columns:
                if col not in df.columns:
                    raise Exception(f"Required column '{col}' not found in data")
            
            # Select and rename columns
            columns_to_keep = required_columns + [col for col in optional_columns if col in df.columns]
            df = df[columns_to_keep]
            
            # Rename columns
            column_mapping = {
                'symbol': 'Symbol',
                'name': 'Name',
                'exchange': 'Exchange',
                'marketCap': 'Market_Cap'
            }
            df = df.rename(columns={col: column_mapping[col] for col in df.columns if col in column_mapping})
            df['Market_Cap'] = pd.to_numeric(df['Market_Cap'].str.replace(',', ''), errors='coerce')
            
            # Sort by market cap and limit if max_stocks is specified
            df_sorted = df.sort_values(by='Market_Cap', ascending=False)
            
            if self.max_stocks:
                df_sorted = df_sorted.head(self.max_stocks)
                print(f"\nSuccessfully retrieved {len(df_sorted)} stocks (limited to {self.max_stocks})")
            else:
                print(f"\nSuccessfully retrieved {len(df_sorted)} stocks")
            
            return df_sorted
            
        except Exception as e:
            print(f"\nError in get_stock_list: {str(e)}")
            print("Full error details:")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()


if __name__ == "__main__":
    stock_list_manager = StockListManager()
    stock_list = stock_list_manager.stock_list
    print(stock_list.head())
    print(f"Total stocks: {len(stock_list)}")