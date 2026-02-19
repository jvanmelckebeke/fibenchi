from pydantic import BaseModel, Field


class SymbolSearchResponse(BaseModel):
    symbol: str = Field(description="Ticker symbol (e.g. AAPL)")
    name: str = Field(description="Company or fund name")
    exchange: str = Field(description="Exchange name (e.g. NasdaqGS)")
    type: str = Field(description="Asset type: stock or etf")
