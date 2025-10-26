from stock_metadata_fetcher import StockMetaDataFetcher

def test_api_calls():
    api_key = "RMHG7PHKL60I5W5V"
    ticker = "AAPL"  # 测试股票
    
    print(f"starting to test {ticker} API calls...") 
    
    # 创建实例（这会触发所有API调用）
    fetcher = StockMetaDataFetcher(ticker, api_key)
    
    print(f"✅ done! total {fetcher.api_call_count} API calls")

if __name__ == "__main__":
    test_api_calls()