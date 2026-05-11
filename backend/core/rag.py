"""
RAG 向量检索模块
使用 ChromaDB PersistentClient 进行本地知识检索
"""
import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional
from pathlib import Path


class VectorRetriever:
    """ChromaDB 向量检索客户端"""

    def __init__(self, persist_dir: Optional[str] = None):
        if persist_dir is None:
            persist_dir = str(Path(__file__).parent.parent / "chroma_db")
        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        self._material_collection = None
        self._failure_collection = None
        self._ensure_collections_exist()

    def _ensure_collections_exist(self):
        existing = {c.name for c in self.client.list_collections()}
        if "materials" not in existing:
            self.client.create_collection(
                name="materials",
                metadata={"description": "材料特征峰指纹数据库"},
            )
        if "failure_modes" not in existing:
            self.client.create_collection(
                name="failure_modes",
                metadata={"description": "失效模式特征知识数据库"},
            )

    @property
    def materials_collection(self):
        if self._material_collection is None:
            self._material_collection = self.client.get_collection("materials")
        return self._material_collection

    @property
    def failure_collection(self):
        if self._failure_collection is None:
            self._failure_collection = self.client.get_collection("failure_modes")
        return self._failure_collection

    def search(
        self,
        query: str,
        material_filter: Optional[str] = None,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """执行材料知识向量检索"""
        results = self.materials_collection.query(
            query_texts=[query],
            n_results=min(top_k * 2, 10),
            include=["metadatas", "documents", "distances"],
        )

        if not results or not results.get("ids"):
            return []

        search_results = []
        for i, doc_id in enumerate(results["ids"][0]):
            document = results["documents"][0][i]
            metadata = results["metadatas"][0][i]
            distance = results["distances"][0][i]

            if material_filter and metadata:
                if material_filter.lower() not in metadata.get("material_name", "").lower():
                    continue

            search_results.append({
                "material_id": doc_id,
                "document": document,
                "distance": distance,
                "metadata": metadata,
                "snippet": document[:500] + "..." if len(document) > 500 else document,
            })

        return search_results[:top_k]

    def search_failure_modes(
        self,
        query: str,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """检索失效模式知识"""
        results = self.failure_collection.query(
            query_texts=[query],
            n_results=top_k,
            include=["metadatas", "documents", "distances"],
        )

        if not results or not results.get("ids"):
            return []

        return [
            {
                "failure_id": results["ids"][0][i],
                "document": results["documents"][0][i],
                "distance": results["distances"][0][i],
                "metadata": results["metadatas"][0][i],
                "snippet": results["documents"][0][i][:400] + "...",
            }
            for i in range(len(results["ids"][0]))
        ]

    def list_materials(self) -> List[str]:
        """列出知识库中所有材料 ID"""
        result = self.materials_collection.get(limit=100)
        return result.get("ids", [])

    def get_material_by_id(self, material_id: str) -> Optional[Dict[str, Any]]:
        """按 ID 获取材料详情"""
        data = self.materials_collection.get(
            ids=[material_id],
            include=["documents", "metadatas"],
        )
        if data and data.get("documents"):
            return {
                "id": material_id,
                "document": data["documents"][0],
                "metadata": data["metadatas"][0],
            }
        return None
