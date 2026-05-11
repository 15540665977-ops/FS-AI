from unittest.mock import MagicMock, patch
from core.rag import VectorRetriever

def _mock_retriever():
    """创建一个不真正连接 ChromaDB 的 VectorRetriever。"""
    with patch("chromadb.PersistentClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.list_collections.return_value = []
        mock_client.create_collection.return_value = MagicMock()

        mock_collection = MagicMock()
        mock_collection.get.return_value = {"ids": ["pp", "pe", "pa6"]}
        mock_collection.query.return_value = {
            "ids": [["pp"]],
            "documents": [["PP 特征峰 2917 cm⁻¹"]],
            "distances": [[0.1]],
            "metadatas": [[{"material_type": "plastic"}]],
        }
        mock_client.get_collection.return_value = mock_collection

        retriever = VectorRetriever()
        retriever._material_collection = mock_collection
        retriever._failure_collection = mock_collection
        return retriever

def test_list_materials_returns_list():
    r = _mock_retriever()
    result = r.list_materials()
    assert isinstance(result, list)
    assert "pp" in result

def test_search_returns_results():
    r = _mock_retriever()
    results = r.search("聚丙烯特征峰", top_k=1)
    assert len(results) == 1
    assert "material_id" in results[0]
    assert "snippet" in results[0]
