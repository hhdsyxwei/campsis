# data_adapter.py
# Backtrader data adapter for DataNest integration

import backtrader as bt
import pandas as pd
from Ingredient.DataNest.dm_daily import DailyDataManager
from KitchenBase.logger_config import get_logger

logger = get_logger(__name__)


class StockData(bt.feeds.PandasData):
    params = (
        ("datetime", 0),
        ("open", 1),
        ("high", 2),
        ("low", 3),
        ("close", 4),
        ("volume", 5),
        ("openinterest", -1),
    )

    def __init__(self, dataname=None, name=None, **kwargs):
        if dataname is not None:
            kwargs["dataname"] = dataname
        if name is not None:
            kwargs["name"] = name
        super().__init__(**kwargs)


class DataCache:
    def __init__(self):
        self._cache = {}

    def get(self, key):
        return self._cache.get(key)

    def set(self, key, value):
        self._cache[key] = value

    def clear(self):
        self._cache.clear()


class BacktraderDataAdapter:
    def __init__(self, db_conn):
        self.daily_manager = DailyDataManager(db_conn)
        self.cache = DataCache()

    def get_stock_data(self, stock_code, start_date, end_date):
        logger.info(f"Getting price data for {stock_code} from {start_date} to {end_date}")
        df = self.daily_manager.get_price_data(stock_code, start_date, end_date)

        if df.empty:
            logger.warning(f"No data found for {stock_code}")
            return None

        df = df.rename(columns={"date": "datetime"})
        df["datetime"] = pd.to_datetime(df["datetime"])

        required_columns = ["datetime", "open", "high", "low", "close", "volume"]
        for col in required_columns:
            if col not in df.columns:
                logger.error(f"Missing required column: {col}")
                return None

        df = df[required_columns]

        data = StockData(dataname=df)

        logger.info(f"Created data feed for {stock_code} with {len(df)} bars")
        return data

    def get_multiple_stocks(self, stock_codes, start_date, end_date):
        datas = []
        for stock_code in stock_codes:
            data = self.get_stock_data(stock_code, start_date, end_date)
            if data:
                datas.append(data)
        logger.info(f"Created {len(datas)} data feeds out of {len(stock_codes)} requested")
        return datas

    def clear_cache(self):
        self.cache.clear()
        logger.info("Data cache cleared")
