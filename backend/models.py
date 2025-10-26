from pydantic import BaseModel, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema
from datetime import datetime
from typing import Dict, List, Any, Optional
from bson import ObjectId

class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetJsonSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_plain_validator_function(cls.validate)

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        return {"type": "string"}

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)

class StockListModel(BaseModel):
    id: Optional[PyObjectId] = None
    symbol: str
    name: str
    exchange: str
    market_cap: Optional[float] = None
    volume: Optional[int] = None
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()

    class Config:
        populate_by_name = True  # 修改：从 allow_population_by_field_name
        arbitrary_types_allowed = True
        # 移除 json_encoders，在 Pydantic V2 中不需要

class StockMetadataModel(BaseModel):
    id: Optional[PyObjectId] = None
    ticker: str
    last_updated: datetime = datetime.now()
    
    # Company overview data
    company_overview: Dict[str, Any] = {}
    
    # Stock fundamental data
    stock_fundamental: Dict[str, Any] = {
        'annual': {
            'income_statement': {},
            'balance_sheet': {},
            'cash_flow': {}
        },
        'quarterly': {
            'income_statement': {},
            'balance_sheet': {},
            'cash_flow': {}
        }
    }
    
    # Stock technical data
    stock_technical_data: Dict[str, Any] = {}

    class Config:
        populate_by_name = True  # 修改：从 allow_population_by_field_name
        arbitrary_types_allowed = True
        # 移除 json_encoders