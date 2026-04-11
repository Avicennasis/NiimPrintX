import json
import os
from pathlib import Path
import appdirs
import time


class CacheManager:
    def __init__(self, app_name):
        self.cache_dir = Path(appdirs.user_cache_dir(app_name))
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_cache_path(self, filename):
        return self.cache_dir / filename

    def save_to_cache(self, data, filename):
        cache_path = self.get_cache_path(filename)
        with open(cache_path, 'w') as f:
            json.dump({"timestamp": time.time(), "data": data}, f)

    def load_from_cache(self, filename, expiration_sec=None):
        cache_path = self.get_cache_path(filename)
        if cache_path.exists():
            try:
                with open(cache_path, 'r') as f:
                    cached = json.load(f)
                stored_time = cached["timestamp"]
                data = cached["data"]
                if expiration_sec is None or (time.time() - stored_time) < expiration_sec:
                    return data
            except (json.JSONDecodeError, KeyError, ValueError):
                return None
        return None

    def get_data(self, filename, compute_data_func, expiration_sec=None):
        data = self.load_from_cache(filename, expiration_sec)
        if data is None:
            data = compute_data_func()
            self.save_to_cache(data, filename)
        return data
