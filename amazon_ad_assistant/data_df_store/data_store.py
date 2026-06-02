# data_store.py
import pandas as pd

class DataStore:
    """单例数据存储，保存所有上传的 DataFrame"""
    _instance = None
    _data = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def set(self, key: str, df: pd.DataFrame):
        self._data[key] = df

    def get(self, key: str) -> pd.DataFrame:
        return self._data.get(key, None)

    def clear(self):
        self._data.clear()

# 全局单例实例
store = DataStore()