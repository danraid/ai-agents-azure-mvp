import os
class BlobClientPlaceholder:
    def __init__(self):
        self.conn = os.getenv("STORAGE_CONN")

class SearchClientPlaceholder:
    def __init__(self):
        self.service = os.getenv("SEARCH_SERVICE")
        self.index = os.getenv("SEARCH_INDEX", "docs")

class PgClientPlaceholder:
    def __init__(self):
        self.conn = os.getenv("POSTGRES_CONN")
