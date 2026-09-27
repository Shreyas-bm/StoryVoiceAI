import os
import datetime
import operator
from typing import Dict, Any, List, Optional

# Global in-memory data store with zero persistence
IN_MEMORY_DB: Dict[str, Any] = {
    "users": {},
    "stories": {},
    "jobs": {},
    "next_user_id": 1,
    "next_story_id": 1,
    "next_job_id": 1
}

OPERATORS = {
    "==": operator.eq,
    "!=": operator.ne,
}

def _get_collection_name(model_name: str) -> str:
    return "stories" if model_name == "story" else f"{model_name}s"

class BinaryExpression:
    def __init__(self, field_name: str, op: str, value: Any):
        self.field_name = field_name
        self.op = op
        self.value = value

    def match(self, item: Any) -> bool:
        op_func = OPERATORS.get(self.op)
        if op_func is None:
            return False
        return op_func(getattr(item, self.field_name, None), self.value)

class ModelAttribute:
    def __init__(self, field_name: str):
        self.field_name = field_name
        self.is_desc = False

    def __eq__(self, other: Any) -> BinaryExpression:
        return BinaryExpression(self.field_name, "==", other)

    def __ne__(self, other: Any) -> BinaryExpression:
        return BinaryExpression(self.field_name, "!=", other)

    def desc(self) -> "ModelAttribute":
        obj = ModelAttribute(self.field_name)
        obj.is_desc = True
        return obj

def desc(col: Any) -> Any:
    return col.desc() if hasattr(col, "desc") else col

class Query:
    def __init__(self, model_class: Any, session: "Session"):
        self.model_class = model_class
        self.session = session
        self.filters: List[Any] = []
        self.order_by_col: Optional[ModelAttribute] = None

    def filter(self, *criterion: Any) -> "Query":
        self.filters.extend(criterion)
        return self

    def filter_by(self, **kwargs: Any) -> "Query":
        self.filters.extend(kwargs.items())
        return self

    def order_by(self, col_attr: ModelAttribute) -> "Query":
        self.order_by_col = col_attr
        return self

    def _get_items(self) -> List[Any]:
        model_name = self.model_class.__name__.lower()
        collection_name = _get_collection_name(model_name)
        db_dict = self.session.db_data.setdefault(collection_name, {})
        items = []
        for d in db_dict.values():
            obj = self.model_class.from_dict(d)
            self.session.tracked[(model_name, obj.id)] = obj
            items.append(obj)
        return items

    def _apply_filters(self, items: List[Any]) -> List[Any]:
        def _matches(item: Any, f: Any) -> bool:
            if isinstance(f, tuple):
                k, v = f
                return getattr(item, k, None) == v
            if isinstance(f, BinaryExpression):
                return f.match(item)
            return True

        return [item for item in items if all(_matches(item, f) for f in self.filters)]

    def all(self) -> List[Any]:
        items = self._apply_filters(self._get_items())
        if self.order_by_col:
            descending = getattr(self.order_by_col, "is_desc", False)
            field = getattr(self.order_by_col, "field_name", "created_at")
            
            def get_sort_key(x: Any) -> datetime.datetime:
                val = getattr(x, field, None)
                if isinstance(val, datetime.datetime):
                    return val
                if isinstance(val, str):
                    try:
                        return datetime.datetime.fromisoformat(val)
                    except ValueError:
                        pass
                return datetime.datetime.min

            items.sort(key=get_sort_key, reverse=descending)
        return items

    def first(self) -> Any:
        return next(iter(self.all()), None)

    def delete(self) -> None:
        for item in self.all():
            self.session.delete(item)

class Session:
    def __init__(self):
        self.db_data = IN_MEMORY_DB
        self._to_add: List[Any] = []
        self._to_delete: List[Any] = []
        self.tracked: Dict[tuple, Any] = {}

    def query(self, model_class: Any) -> Query:
        return Query(model_class, self)

    def add(self, obj: Any) -> None:
        self._to_add.append(obj)

    def delete(self, obj: Any) -> None:
        self._to_delete.append(obj)

    def commit(self) -> None:
        # 1. Process explicit additions
        for obj in self._to_add:
            model_name = obj.__class__.__name__.lower()
            if not obj.id:
                key = f"next_{model_name}_id"
                if key in self.db_data:
                    obj.id = self.db_data[key]
                    self.db_data[key] += 1
            self.tracked[(model_name, obj.id)] = obj
        self._to_add.clear()

        # 2. Update db_data from tracked objects
        for (model_name, obj_id), obj in self.tracked.items():
            collection_name = _get_collection_name(model_name)
            self.db_data[collection_name][str(obj_id)] = obj.to_dict()

        # 3. Process explicit deletions
        for obj in self._to_delete:
            model_name = obj.__class__.__name__.lower()
            collection_name = _get_collection_name(model_name)
            self.db_data[collection_name].pop(str(obj.id), None)
            self.tracked.pop((model_name, obj.id), None)
        self._to_delete.clear()

    def refresh(self, obj: Any) -> None:
        model_name = obj.__class__.__name__.lower()
        collection_name = _get_collection_name(model_name)
        if obj.id:
            data = self.db_data[collection_name].get(str(obj.id))
            if data:
                fresh = obj.__class__.from_dict(data)
                for k, v in fresh.__dict__.items():
                    setattr(obj, k, v)

    def close(self) -> None:
        pass

    def expire_all(self) -> None:
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

def SessionLocal() -> Session:
    return Session()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def flag_modified(obj: Any, attr_name: str) -> None:
    pass

