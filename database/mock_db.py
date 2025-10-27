"""Mock database for testing without MongoDB"""
import random

class MockCollection:
    def __init__(self):
        self.data = {}
        self._id_counter = 0
    
    def insert_one(self, doc):
        if '_id' not in doc:
            self._id_counter += 1
            doc['_id'] = f"mock_{self._id_counter}_{random.randint(1000, 9999)}"
        self.data[doc['_id']] = doc
        return None
    
    def find_one(self, query):
        if not query:
            return None
        
        _id = query.get('_id')
        if _id and _id in self.data:
            return self.data[_id]
        
        for doc in self.data.values():
            match = True
            for key, value in query.items():
                if key == '$or':
                    continue
                if doc.get(key) != value:
                    match = False
                    break
            if match:
                return doc
        return None
    
    def find(self, query=None):
        if query is None:
            query = {}
        results = []
        for doc in self.data.values():
            match = True
            for key, value in query.items():
                if key.startswith('$'):
                    continue
                if doc.get(key) != value:
                    match = False
                    break
            if match:
                results.append(doc)
        return MockCursor(results)
    
    def update_one(self, query, update):
        doc = self.find_one(query)
        if doc and '$set' in update:
            doc.update(update['$set'])
        if doc and '$push' in update:
            for key, value in update['$push'].items():
                if key not in doc:
                    doc[key] = []
                doc[key].append(value)
    
    def delete_one(self, query):
        _id = query.get('_id')
        if _id and _id in self.data:
            del self.data[_id]
    
    def count_documents(self, query):
        return len(list(self.find(query)))
    
    def distinct(self, field, query=None):
        if query is None:
            query = {}
        values = set()
        for doc in self.find(query):
            if field in doc:
                values.add(doc[field])
        return list(values)

class MockCursor:
    def __init__(self, data):
        self.data = data
        self._limit = None
        self._sort_key = None
        self._sort_order = 1
    
    def sort(self, key, order=1):
        self._sort_key = key
        self._sort_order = order
        return self
    
    def limit(self, n):
        self._limit = n
        return self
    
    def __iter__(self):
        data = self.data
        
        if self._sort_key:
            reverse = self._sort_order == -1
            data = sorted(data, key=lambda x: x.get(self._sort_key, 0), reverse=reverse)
        
        if self._limit:
            data = data[:self._limit]
        
        return iter(data)
    
    @property
    def total_count(self):
        return len(self.data)

class MockDatabase:
    def __init__(self):
        self.collections = {}
    
    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = MockCollection()
        return self.collections[name]
