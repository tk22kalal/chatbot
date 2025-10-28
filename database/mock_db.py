"""Mock database for testing without MongoDB"""
import random
import json
import os
from threading import Lock

DATA_FILE = 'mock_database.json'
file_lock = Lock()

def load_data_from_file():
    """Load data from JSON file"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load database file: {e}")
    return {}

def save_data_to_file(data):
    """Save data to JSON file"""
    try:
        with file_lock:
            with open(DATA_FILE, 'w') as f:
                json.dump(data, f, indent=2, default=str)
    except Exception as e:
        print(f"Warning: Failed to save database file: {e}")

class MockCollection:
    def __init__(self, collection_name, parent_db):
        self.collection_name = collection_name
        self.parent_db = parent_db
        self.data = {}
        self._id_counter = 0
    
    def insert_one(self, doc):
        if '_id' not in doc:
            self._id_counter += 1
            doc['_id'] = f"mock_{self._id_counter}_{random.randint(1000, 9999)}"
        self.data[doc['_id']] = doc
        self.parent_db.save()
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
        if doc:
            self.parent_db.save()
    
    def delete_one(self, query):
        _id = query.get('_id')
        if _id and _id in self.data:
            del self.data[_id]
            self.parent_db.save()
    
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
    
    def delete_many(self, query):
        """Delete multiple documents matching query"""
        to_delete = []
        for doc_id, doc in self.data.items():
            match = True
            for key, value in query.items():
                if key.startswith('$'):
                    continue
                if doc.get(key) != value:
                    match = False
                    break
            if match:
                to_delete.append(doc_id)
        
        for doc_id in to_delete:
            del self.data[doc_id]
        
        if to_delete:
            self.parent_db.save()
        
        return len(to_delete)

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
        self.db_data = load_data_from_file()
        self._load_collections()
    
    def _load_collections(self):
        """Load collections from file data"""
        for collection_name, collection_data in self.db_data.items():
            collection = MockCollection(collection_name, self)
            collection.data = collection_data
            self.collections[collection_name] = collection
    
    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = MockCollection(name, self)
            self.db_data[name] = {}
        return self.collections[name]
    
    def save(self):
        """Save all collections to file"""
        for name, collection in self.collections.items():
            self.db_data[name] = collection.data
        save_data_to_file(self.db_data)
