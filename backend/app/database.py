import os
import datetime
from typing import Dict, Any, List

# Global in-memory data store with zero persistence
IN_MEMORY_DB = {
    "users": {},
    "stories": {},
    "jobs": {},
    "next_user_id": 1,
    "next_story_id": 1,
    "next_job_id": 1
}

class BinaryExpression:
    def __init__(self, field_name: str, op: str, value: Any):
        self.field_name = field_name
        self.op = op
        self.value = value

    def match(self, item: Any) -> bool:
        val = getattr(item, self.field_name, None)
        if self.op == "==":
            return val == self.value
        elif self.op == "!=":
            return val != self.value
        return False

class ModelAttribute:
    def __init__(self, field_name: str):
        self.field_name = field_name
        self.is_desc = False

    def __eq__(self, other):
        return BinaryExpression(self.field_name, "==", other)

    def __ne__(self, other):
        return BinaryExpression(self.field_name, "!=", other)

    def desc(self):
        obj = ModelAttribute(self.field_name)
        obj.is_desc = True
        return obj

def desc(col):
    if hasattr(col, "desc"):
        return col.desc()
    return col

class Query:
    def __init__(self, model_class, session):
        self.model_class = model_class
        self.session = session
        self.filters = []
        self.order_by_col = None

    def filter(self, *criterion):
        for c in criterion:
            self.filters.append(c)
        return self

    def filter_by(self, **kwargs):
        for k, v in kwargs.items():
            self.filters.append((k, v))
        return self

    def order_by(self, col_attr):
        self.order_by_col = col_attr
        return self

    def _get_items(self):
        model_name = self.model_class.__name__.lower()
        collection_name = "stories" if model_name == "story" else f"{model_name}s"
        db_dict = self.session.db_data.setdefault(collection_name, {})
        items = []
        for d in db_dict.values():
            obj = self.model_class.from_dict(d)
            self.session.tracked[(model_name, obj.id)] = obj
            items.append(obj)
        return items

    def _apply_filters(self, items):
        filtered_items = []
        for item in items:
            match = True
            for f in self.filters:
                if isinstance(f, tuple):
                    k, v = f
                    if getattr(item, k, None) != v:
                        match = False
                        break
                elif isinstance(f, BinaryExpression):
                    if not f.match(item):
                        match = False
                        break
            if match:
                filtered_items.append(item)
        return filtered_items

    def all(self) -> List[Any]:
        items = self._get_items()
        items = self._apply_filters(items)
        if self.order_by_col:
            descending = getattr(self.order_by_col, "is_desc", False)
            field = getattr(self.order_by_col, "field_name", "created_at")
            
            def get_sort_key(x):
                val = getattr(x, field, None)
                if isinstance(val, datetime.datetime):
                    return val
                elif isinstance(val, str):
                    try:
                        return datetime.datetime.fromisoformat(val)
                    except ValueError:
                        return datetime.datetime.min
                return datetime.datetime.min

            items.sort(key=get_sort_key, reverse=descending)
        return items

    def first(self) -> Any:
        items = self.all()
        return items[0] if items else None

    def delete(self):
        items = self.all()
        for item in items:
            self.session.delete(item)

class Session:
    def __init__(self):
        self.db_data = IN_MEMORY_DB
        self._to_add = []
        self._to_delete = []
        self.tracked = {}

    def query(self, model_class):
        return Query(model_class, self)

    def add(self, obj):
        self._to_add.append(obj)

    def delete(self, obj):
        self._to_delete.append(obj)

    def commit(self):
        # 1. Process explicit additions
        for obj in self._to_add:
            model_name = obj.__class__.__name__.lower()
            if not obj.id:
                if model_name == "user":
                    obj.id = self.db_data["next_user_id"]
                    self.db_data["next_user_id"] += 1
                elif model_name == "story":
                    obj.id = self.db_data["next_story_id"]
                    self.db_data["next_story_id"] += 1
                elif model_name == "job":
                    obj.id = self.db_data["next_job_id"]
                    self.db_data["next_job_id"] += 1
            self.tracked[(model_name, obj.id)] = obj
        self._to_add.clear()

        # 2. Update db_data from tracked objects
        for (model_name, obj_id), obj in self.tracked.items():
            collection_name = "stories" if model_name == "story" else f"{model_name}s"
            self.db_data[collection_name][str(obj_id)] = obj.to_dict()

        # 3. Process explicit deletions
        for obj in self._to_delete:
            model_name = obj.__class__.__name__.lower()
            collection_name = "stories" if model_name == "story" else f"{model_name}s"
            if str(obj.id) in self.db_data[collection_name]:
                del self.db_data[collection_name][str(obj.id)]
            self.tracked.pop((model_name, obj.id), None)
        self._to_delete.clear()

    def refresh(self, obj):
        model_name = obj.__class__.__name__.lower()
        collection_name = "stories" if model_name == "story" else f"{model_name}s"
        if obj.id:
            data = self.db_data[collection_name].get(str(obj.id))
            if data:
                fresh = obj.__class__.from_dict(data)
                for k, v in fresh.__dict__.items():
                    setattr(obj, k, v)

    def close(self):
        pass

    def expire_all(self):
        pass

class MockEngine:
    def connect(self):
        return self
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
    def dispose(self):
        pass

engine = MockEngine()
Base = type("Base", (), {"metadata": type("Metadata", (), {"create_all": lambda self, bind=None: None})()})

def SessionLocal():
    return Session()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def flag_modified(obj, attr_name):
    pass
