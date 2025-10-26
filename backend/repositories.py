from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Optional, Dict, Any
from datetime import datetime
import pandas as pd
from models import StockListModel, StockMetadataModel

class StockListRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.stock_list

    async def create_stock_list(self, stocks_data: List[Dict[str, Any]]) -> bool:
        """Create stock list from DataFrame"""
        try:
            # Clear existing data
            await self.collection.delete_many({})
            
            # Insert new data
            documents = []
            for _, row in stocks_data.iterrows():
                # Clean market_cap value to ensure it's JSON-compliant
                market_cap = row.get('Market_Cap')
                if market_cap is not None and isinstance(market_cap, (int, float)):
                    # Check for NaN, Inf, -Inf
                    if pd.isna(market_cap) or pd.isinf(market_cap):
                        market_cap = None
                
                doc = {
                    'symbol': row['Symbol'],
                    'name': row['Name'],
                    'exchange': row['Exchange'],
                    'market_cap': market_cap,
                    'created_at': datetime.now(),
                    'updated_at': datetime.now()
                }
                documents.append(doc)
            
            if documents:
                await self.collection.insert_many(documents)
                print(f"✅ Successfully inserted {len(documents)} stocks into database")
                return True
            return False
            
        except Exception as e:
            print(f"❌ Error creating stock list: {e}")
            return False

    async def get_all_stocks(self) -> List[StockListModel]:
        """Get all stocks from database"""
        try:
            cursor = self.collection.find({})
            stocks = []
            async for doc in cursor:
                doc['id'] = str(doc['_id'])
                stocks.append(StockListModel(**doc))
            return stocks
        except Exception as e:
            print(f"❌ Error getting stocks: {e}")
            return []

    async def get_stock_by_symbol(self, symbol: str) -> Optional[StockListModel]:
        """Get stock by symbol"""
        try:
            doc = await self.collection.find_one({'symbol': symbol})
            if doc:
                doc['id'] = str(doc['_id'])
                return StockListModel(**doc)
            return None
        except Exception as e:
            print(f"❌ Error getting stock by symbol: {e}")
            return None

class StockMetadataRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.stock_metadata

    async def create_or_update_stock_metadata(self, ticker: str, metadata: Dict[str, Any]) -> bool:
        """Create or update stock metadata"""
        try:
            # Convert pandas DataFrames to dict for MongoDB storage
            processed_metadata = self._process_metadata_for_storage(metadata)
            
            document = {
                'ticker': ticker,
                'last_updated': datetime.now(),
                **processed_metadata
            }
            
            # Use upsert to create or update
            result = await self.collection.replace_one(
                {'ticker': ticker},
                document,
                upsert=True
            )
            
            if result.upserted_id or result.modified_count > 0:
                print(f"✅ Successfully saved metadata for {ticker}")
                return True
            return False
            
        except Exception as e:
            print(f"❌ Error saving metadata for {ticker}: {e}")
            return False

    async def get_stock_metadata(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get stock metadata by ticker"""
        try:
            doc = await self.collection.find_one({'ticker': ticker})
            if doc:
                # Remove MongoDB _id field
                doc.pop('_id', None)
                return doc
            return None
        except Exception as e:
            print(f"❌ Error getting metadata for {ticker}: {e}")
            return None

    async def get_all_tickers(self) -> List[str]:
        """Get all tickers from metadata collection"""
        try:
            cursor = self.collection.find({}, {'ticker': 1})
            tickers = []
            async for doc in cursor:
                tickers.append(doc['ticker'])
            return tickers
        except Exception as e:
            print(f"❌ Error getting tickers: {e}")
            return []

    def _process_metadata_for_storage(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Convert pandas DataFrames to dict for MongoDB storage"""
        processed = {}
        
        for key, value in metadata.items():
            if key == 'company_overview':
                processed[key] = value
            elif key == 'stock_fundamental':
                processed[key] = self._process_fundamental_data(value)
            elif key == 'stock_technical_data':
                processed[key] = self._process_technical_data(value)
            else:
                processed[key] = value
                
        return processed

    def _process_fundamental_data(self, fundamental_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process fundamental data for storage"""
        processed = {}
        
        for period in ['annual', 'quarterly']:
            if period in fundamental_data:
                processed[period] = {}
                for statement_type in ['income_statement', 'balance_sheet', 'cash_flow']:
                    if statement_type in fundamental_data[period]:
                        df = fundamental_data[period][statement_type]
                        if isinstance(df, pd.DataFrame) and not df.empty:
                            # Convert DataFrame to dict
                            processed[period][statement_type] = {
                                'data': df.to_dict('records'),
                                'columns': df.columns.tolist(),
                                'index': df.index.tolist()
                            }
                        else:
                            processed[period][statement_type] = {}
        
        return processed

    def _process_technical_data(self, technical_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process technical data for storage"""
        import numpy as np
        
        def convert_to_serializable(obj):
            """Convert numpy arrays and other non-serializable objects to serializable format"""
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, pd.Timestamp):
                return obj.isoformat()
            elif isinstance(obj, dict):
                return {str(k): convert_to_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_to_serializable(item) for item in obj]
            else:
                return obj
        
        processed = {}
        
        for interval, interval_data in technical_data.items():
            processed[interval] = {}
            
            for data_type, data_value in interval_data.items():
                if isinstance(data_value, pd.DataFrame) and not data_value.empty:
                    # Convert DataFrame to dict with string keys
                    processed[interval][data_type] = {
                        'data': data_value.to_dict('records'),
                        'columns': data_value.columns.tolist(),
                        'index': [str(idx) for idx in data_value.index.tolist()]
                    }
                elif isinstance(data_value, dict):
                    # Handle nested dicts (like KDJ, MACD, RSI)
                    processed[interval][data_type] = {}
                    for sub_key, sub_value in data_value.items():
                        if isinstance(sub_value, pd.Series) and not sub_value.empty:
                            # Convert Series to dict with string keys
                            series_dict = {}
                            for idx, val in sub_value.items():
                                series_dict[str(idx)] = convert_to_serializable(val)
                            processed[interval][data_type][sub_key] = {
                                'data': series_dict,
                                'index': [str(idx) for idx in sub_value.index.tolist()]
                            }
                        else:
                            # Handle numpy arrays and other non-serializable objects
                            processed[interval][data_type][sub_key] = convert_to_serializable(sub_value)
                else:
                    processed[interval][data_type] = convert_to_serializable(data_value)
        
        return processed
