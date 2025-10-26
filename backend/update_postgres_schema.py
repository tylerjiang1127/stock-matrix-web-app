#!/usr/bin/env python3
"""
Update PostgreSQL schema to include all required moving average columns
"""

import asyncio
from postgres_database import postgres_db

async def update_postgres_schema():
    """Update PostgreSQL tables to include all required MA columns"""
    print("🔄 Updating PostgreSQL schema...")
    
    try:
        await postgres_db.connect()
        
        # Define all possible MA columns for each interval
        ma_columns_by_interval = {
            '1m': ['sma30', 'sma60', 'sma120', 'ema30', 'ema60', 'ema120', 'wma30', 'wma60', 'wma120', 'dema30', 'dema60', 'dema120', 'tema30', 'tema60', 'tema120', 'kama30', 'kama60', 'kama120'],
            '5m': ['sma6', 'sma12', 'sma24', 'sma36', 'sma72', 'sma144', 'ema6', 'ema12', 'ema24', 'ema36', 'ema72', 'ema144', 'wma6', 'wma12', 'wma24', 'wma36', 'wma72', 'wma144', 'dema6', 'dema12', 'dema24', 'dema36', 'dema72', 'dema144', 'tema6', 'tema12', 'tema24', 'tema36', 'tema72', 'tema144', 'kama6', 'kama12', 'kama24', 'kama36', 'kama72', 'kama144'],
            '15m': ['sma4', 'sma8', 'sma16', 'sma24', 'sma48', 'sma96', 'ema4', 'ema8', 'ema16', 'ema24', 'ema48', 'ema96', 'wma4', 'wma8', 'wma16', 'wma24', 'wma48', 'wma96', 'dema4', 'dema8', 'dema16', 'dema24', 'dema48', 'dema96', 'tema4', 'tema8', 'tema16', 'tema24', 'tema48', 'tema96', 'kama4', 'kama8', 'kama16', 'kama24', 'kama48', 'kama96'],
            '30m': ['sma3', 'sma6', 'sma12', 'sma18', 'sma36', 'sma72', 'ema3', 'ema6', 'ema12', 'ema18', 'ema36', 'ema72', 'wma3', 'wma6', 'wma12', 'wma18', 'wma36', 'wma72', 'dema3', 'dema6', 'dema12', 'dema18', 'dema36', 'dema72', 'tema3', 'tema6', 'tema12', 'tema18', 'tema36', 'tema72', 'kama3', 'kama6', 'kama12', 'kama18', 'kama36', 'kama72'],
            '60m': ['sma3', 'sma5', 'sma8', 'sma13', 'sma21', 'sma34', 'ema3', 'ema5', 'ema8', 'ema13', 'ema21', 'ema34', 'wma3', 'wma5', 'wma8', 'wma13', 'wma21', 'wma34', 'dema3', 'dema5', 'dema8', 'dema13', 'dema21', 'dema34', 'tema3', 'tema5', 'tema8', 'tema13', 'tema21', 'tema34', 'kama3', 'kama5', 'kama8', 'kama13', 'kama21', 'kama34'],
            '1d': ['sma30', 'sma60', 'sma120', 'sma250', 'ema30', 'ema60', 'ema120', 'ema250', 'wma30', 'wma60', 'wma120', 'wma250', 'dema30', 'dema60', 'dema120', 'dema250', 'tema30', 'tema60', 'tema120', 'tema250', 'kama30', 'kama60', 'kama120', 'kama250'],
            '1wk': ['sma30', 'sma60', 'ema30', 'ema60', 'wma30', 'wma60', 'dema30', 'dema60', 'tema30', 'tema60', 'kama30', 'kama60'],
            '1mo': ['sma3', 'sma5', 'sma10', 'sma12', 'sma24', 'sma36', 'ema3', 'ema5', 'ema10', 'ema12', 'ema24', 'ema36', 'wma3', 'wma5', 'wma10', 'wma12', 'wma24', 'wma36', 'dema3', 'dema5', 'dema10', 'dema12', 'dema24', 'dema36', 'tema3', 'tema5', 'tema10', 'tema12', 'tema24', 'tema36', 'kama3', 'kama5', 'kama10', 'kama12', 'kama24', 'kama36']
        }
        
        async with postgres_db.pool.acquire() as connection:
            for interval, columns in ma_columns_by_interval.items():
                table_name = f"interval_{interval}_technical"
                print(f"📊 Updating {table_name}...")
                
                for column in columns:
                    try:
                        # Check if column exists
                        check_query = """
                            SELECT column_name 
                            FROM information_schema.columns 
                            WHERE table_name = $1 AND column_name = $2
                        """
                        result = await connection.fetchrow(check_query, table_name, column)
                        
                        if not result:
                            # Add column if it doesn't exist
                            alter_query = f"ALTER TABLE {table_name} ADD COLUMN {column} DECIMAL(15,4);"
                            await connection.execute(alter_query)
                            print(f"  ✅ Added column {column}")
                        else:
                            print(f"  ⚠️ Column {column} already exists")
                            
                    except Exception as e:
                        print(f"  ❌ Error adding column {column}: {e}")
        
        print("🎉 PostgreSQL schema update completed!")
        
    except Exception as e:
        print(f"❌ Error updating schema: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await postgres_db.disconnect()

if __name__ == "__main__":
    asyncio.run(update_postgres_schema())
