"""Shop data access: Firestore in production, an in-memory twin for dev and tests.

Layout (all under shops/{shopId}):
  products/{sku}            stock, price, supplier, shelf description, names in 4 languages
  suppliers/{id}            distributor name, lead time, WhatsApp number
  daily_sales/{YYYY-MM-DD}  {"date": ..., "units": {sku: count}}
  regulars/{id}             regular customers and when they last came in
  scans/{id}                shelf-photo counts awaiting the shopkeeper's confirmation
  orders/{id}               supplier orders: draft -> approved -> received / cancelled
  activity/{id}             the shop's timeline
"""

import copy
import threading
import uuid
from datetime import UTC, datetime
from typing import Any, Protocol

Where = tuple[str, str, Any] | list[tuple[str, str, Any]]


def now() -> datetime:
    return datetime.now(UTC)


class Store(Protocol):
    backend: str

    def get_shop(self, shop_id: str) -> dict | None: ...
    def put_shop(self, shop_id: str, data: dict) -> None: ...
    def update_shop(self, shop_id: str, fields: dict) -> None: ...
    def get(self, shop_id: str, collection: str, doc_id: str) -> dict | None: ...
    def put(self, shop_id: str, collection: str, doc_id: str, data: dict) -> None: ...
    def put_many(self, shop_id: str, collection: str, docs: dict[str, dict]) -> None: ...
    def create(self, shop_id: str, collection: str, data: dict) -> str: ...
    def update(self, shop_id: str, collection: str, doc_id: str, fields: dict) -> None: ...
    def increment(self, shop_id: str, collection: str, doc_id: str, field: str, amount: int) -> None: ...
    def list(
        self,
        shop_id: str,
        collection: str,
        *,
        where: Where | None = None,
        order_by: str | None = None,
        descending: bool = False,
        limit: int | None = None,
    ) -> list[dict]: ...
    def clear_shop(self, shop_id: str, collections: tuple[str, ...]) -> None: ...


def _matches(doc: dict, where: Where | None) -> bool:
    if where is None:
        return True
    if isinstance(where, list):
        return all(_matches(doc, clause) for clause in where)
    field, op, value = where
    current = doc.get(field)
    if op == "==":
        return current == value
    if op == ">=":
        return current is not None and current >= value
    if op == "<=":
        return current is not None and current <= value
    if op == "in":
        return current in value
    raise ValueError(f"Unsupported operator {op}")


class MemoryStore:
    backend = "memory"

    def __init__(self) -> None:
        self._shops: dict[str, dict] = {}
        self._docs: dict[tuple[str, str], dict[str, dict]] = {}
        self._lock = threading.RLock()

    def _coll(self, shop_id: str, collection: str) -> dict[str, dict]:
        return self._docs.setdefault((shop_id, collection), {})

    def get_shop(self, shop_id: str) -> dict | None:
        with self._lock:
            shop = self._shops.get(shop_id)
            return copy.deepcopy(shop) if shop else None

    def put_shop(self, shop_id: str, data: dict) -> None:
        with self._lock:
            self._shops[shop_id] = copy.deepcopy(data)

    def update_shop(self, shop_id: str, fields: dict) -> None:
        with self._lock:
            self._shops.setdefault(shop_id, {}).update(copy.deepcopy(fields))

    def get(self, shop_id: str, collection: str, doc_id: str) -> dict | None:
        with self._lock:
            doc = self._coll(shop_id, collection).get(doc_id)
            return {**copy.deepcopy(doc), "id": doc_id} if doc is not None else None

    def put(self, shop_id: str, collection: str, doc_id: str, data: dict) -> None:
        with self._lock:
            self._coll(shop_id, collection)[doc_id] = copy.deepcopy(data)

    def put_many(self, shop_id: str, collection: str, docs: dict[str, dict]) -> None:
        with self._lock:
            for doc_id, data in docs.items():
                self._coll(shop_id, collection)[doc_id] = copy.deepcopy(data)

    def create(self, shop_id: str, collection: str, data: dict) -> str:
        doc_id = uuid.uuid4().hex[:20]
        self.put(shop_id, collection, doc_id, data)
        return doc_id

    def update(self, shop_id: str, collection: str, doc_id: str, fields: dict) -> None:
        with self._lock:
            docs = self._coll(shop_id, collection)
            if doc_id not in docs:
                raise KeyError(doc_id)
            docs[doc_id].update(copy.deepcopy(fields))

    def increment(self, shop_id: str, collection: str, doc_id: str, field: str, amount: int) -> None:
        with self._lock:
            doc = self._coll(shop_id, collection)[doc_id]
            doc[field] = doc.get(field, 0) + amount

    def list(self, shop_id, collection, *, where=None, order_by=None, descending=False, limit=None):
        with self._lock:
            docs = [
                {**copy.deepcopy(data), "id": doc_id}
                for doc_id, data in self._coll(shop_id, collection).items()
                if _matches(data, where)
            ]
        if order_by:
            docs.sort(key=lambda doc: doc.get(order_by) or "", reverse=descending)
        return docs[:limit] if limit else docs

    def clear_shop(self, shop_id: str, collections: tuple[str, ...]) -> None:
        with self._lock:
            for collection in collections:
                self._docs.pop((shop_id, collection), None)


class FirestoreStore:
    backend = "firestore"

    def __init__(self, project: str | None, database: str = "(default)") -> None:
        from google.cloud import firestore

        self._firestore = firestore
        self.client = firestore.Client(project=project, database=database)

    def _shop(self, shop_id: str):
        return self.client.collection("shops").document(shop_id)

    def _coll(self, shop_id: str, collection: str):
        return self._shop(shop_id).collection(collection)

    def get_shop(self, shop_id: str) -> dict | None:
        snapshot = self._shop(shop_id).get()
        return snapshot.to_dict() if snapshot.exists else None

    def put_shop(self, shop_id: str, data: dict) -> None:
        self._shop(shop_id).set(data)

    def update_shop(self, shop_id: str, fields: dict) -> None:
        self._shop(shop_id).set(fields, merge=True)

    def get(self, shop_id: str, collection: str, doc_id: str) -> dict | None:
        snapshot = self._coll(shop_id, collection).document(doc_id).get()
        return {**snapshot.to_dict(), "id": snapshot.id} if snapshot.exists else None

    def put(self, shop_id: str, collection: str, doc_id: str, data: dict) -> None:
        self._coll(shop_id, collection).document(doc_id).set(data)

    def put_many(self, shop_id: str, collection: str, docs: dict[str, dict]) -> None:
        items = list(docs.items())
        for start in range(0, len(items), 400):
            batch = self.client.batch()
            for doc_id, data in items[start : start + 400]:
                batch.set(self._coll(shop_id, collection).document(doc_id), data)
            batch.commit()

    def create(self, shop_id: str, collection: str, data: dict) -> str:
        reference = self._coll(shop_id, collection).document()
        reference.set(data)
        return reference.id

    def update(self, shop_id: str, collection: str, doc_id: str, fields: dict) -> None:
        self._coll(shop_id, collection).document(doc_id).update(fields)

    def increment(self, shop_id: str, collection: str, doc_id: str, field: str, amount: int) -> None:
        self._coll(shop_id, collection).document(doc_id).update({field: self._firestore.Increment(amount)})

    def list(self, shop_id, collection, *, where=None, order_by=None, descending=False, limit=None):
        query = self._coll(shop_id, collection)
        if where:
            from google.cloud.firestore_v1.base_query import FieldFilter

            for clause in where if isinstance(where, list) else [where]:
                query = query.where(filter=FieldFilter(*clause))
        if order_by:
            direction = self._firestore.Query.DESCENDING if descending else self._firestore.Query.ASCENDING
            query = query.order_by(order_by, direction=direction)
        if limit:
            query = query.limit(limit)
        return [{**snapshot.to_dict(), "id": snapshot.id} for snapshot in query.stream()]

    def clear_shop(self, shop_id: str, collections: tuple[str, ...]) -> None:
        for collection in collections:
            while True:
                snapshots = list(self._coll(shop_id, collection).limit(400).stream())
                if not snapshots:
                    break
                batch = self.client.batch()
                for snapshot in snapshots:
                    batch.delete(snapshot.reference)
                batch.commit()


def build_store(settings) -> Store:
    if settings.store == "firestore":
        return FirestoreStore(settings.gcp_project, settings.firestore_database)
    return MemoryStore()
