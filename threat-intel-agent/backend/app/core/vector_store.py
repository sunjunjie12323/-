import asyncio
from typing import Dict, List, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from loguru import logger

from app.config import settings
from app.core.llm import LLMService


class VectorStore:
    COLLECTION_NAMES = ("intelligence", "entities", "blacktalk")

    def __init__(self, persist_dir: str, llm: LLMService):
        self.persist_dir = persist_dir
        self.llm = llm
        self._client = chromadb.PersistentClient(
            path=persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collections: Dict[str, chromadb.Collection] = {}
        self._lock = asyncio.Lock()
        for name in self.COLLECTION_NAMES:
            self._collections[name] = self._client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
            )
        logger.info(
            f"VectorStore initialized at {persist_dir} "
            f"with collections: {list(self._collections.keys())}"
        )

    def _get_collection(self, collection: str) -> chromadb.Collection:
        if collection not in self._collections:
            raise ValueError(
                f"Unknown collection '{collection}'. "
                f"Available: {list(self._collections.keys())}"
            )
        return self._collections[collection]

    async def _embed(self, text: str) -> List[float]:
        return await self.llm.embed(text)

    async def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        return await self.llm.embed_batch(texts)

    async def add_intelligence(self, intel_id: str, content: str, metadata: dict):
        try:
            embedding = await self._embed(content)
            async with self._lock:
                self._collections["intelligence"].add(
                    ids=[intel_id],
                    embeddings=[embedding],
                    documents=[content],
                    metadatas=[metadata],
                )
            logger.debug(f"Added intelligence vector: {intel_id}")
        except Exception as exc:
            logger.error(f"Failed to add intelligence vector {intel_id}: {exc}")
            raise

    async def search_intelligence(
        self,
        query: str,
        n_results: int = 10,
        filter: Optional[dict] = None,
    ) -> List[dict]:
        try:
            query_embedding = await self._embed(query)
            kwargs = {
                "query_embeddings": [query_embedding],
                "n_results": n_results,
            }
            if filter:
                kwargs["where"] = filter
            async with self._lock:
                results = self._collections["intelligence"].query(**kwargs)
            return self._format_results(results)
        except Exception as exc:
            logger.error(f"Failed to search intelligence: {exc}")
            return []

    async def add_entity(self, entity_id: str, content: str, metadata: dict):
        try:
            embedding = await self._embed(content)
            async with self._lock:
                self._collections["entities"].add(
                    ids=[entity_id],
                    embeddings=[embedding],
                    documents=[content],
                    metadatas=[metadata],
                )
            logger.debug(f"Added entity vector: {entity_id}")
        except Exception as exc:
            logger.error(f"Failed to add entity vector {entity_id}: {exc}")
            raise

    async def search_entities(
        self,
        query: str,
        n_results: int = 10,
    ) -> List[dict]:
        try:
            query_embedding = await self._embed(query)
            async with self._lock:
                results = self._collections["entities"].query(
                    query_embeddings=[query_embedding],
                    n_results=n_results,
                )
            return self._format_results(results)
        except Exception as exc:
            logger.error(f"Failed to search entities: {exc}")
            return []

    async def add_blacktalk(self, term_id: str, content: str, metadata: dict):
        try:
            embedding = await self._embed(content)
            async with self._lock:
                self._collections["blacktalk"].add(
                    ids=[term_id],
                    embeddings=[embedding],
                    documents=[content],
                    metadatas=[metadata],
                )
            logger.debug(f"Added blacktalk vector: {term_id}")
        except Exception as exc:
            logger.error(f"Failed to add blacktalk vector {term_id}: {exc}")
            raise

    async def search_blacktalk(
        self,
        query: str,
        n_results: int = 10,
    ) -> List[dict]:
        try:
            query_embedding = await self._embed(query)
            async with self._lock:
                results = self._collections["blacktalk"].query(
                    query_embeddings=[query_embedding],
                    n_results=n_results,
                )
            return self._format_results(results)
        except Exception as exc:
            logger.error(f"Failed to search blacktalk: {exc}")
            return []

    async def delete(self, collection: str, ids: List[str]):
        try:
            col = self._get_collection(collection)
            async with self._lock:
                col.delete(ids=ids)
            logger.debug(f"Deleted {len(ids)} items from {collection}")
        except Exception as exc:
            logger.error(f"Failed to delete from {collection}: {exc}")
            raise

    async def count(self, collection: str) -> int:
        try:
            col = self._get_collection(collection)
            async with self._lock:
                return col.count()
        except Exception as exc:
            logger.error(f"Failed to count {collection}: {exc}")
            return 0

    async def persist(self):
        try:
            logger.info("VectorStore persisted to disk (auto-persist by PersistentClient)")
        except Exception as exc:
            logger.error(f"Failed to persist VectorStore: {exc}")

    def _format_results(self, results: dict) -> List[dict]:
        formatted = []
        if not results or not results.get("ids") or not results["ids"][0]:
            return formatted
        ids = results["ids"][0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        for i in range(len(ids)):
            item = {
                "id": ids[i],
                "document": documents[i] if i < len(documents) else None,
                "metadata": metadatas[i] if i < len(metadatas) else {},
                "distance": distances[i] if i < len(distances) else None,
            }
            formatted.append(item)
        return formatted
