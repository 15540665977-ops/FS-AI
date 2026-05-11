"""
Web 搜索模块 - Tavily API 集成
用于联网搜索技术文献和材料 TDS
"""
import requests
from typing import List, Dict, Any, Optional


class WebSearchClient:
    """
    Tavily 联网搜索客户端
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化 Web 搜索客户端

        Args:
            api_key: Tavily API key (从环境变量 TAVILY_API_KEY 读取)
        """
        self.api_key = api_key or self._get_api_key_from_env()
        self.base_url = "https://api.tavily.com/search"

        if not self.api_key:
            print("警告：Tavily API key 未配置，联网搜索功能将不可用")
            print("请设置环境变量 TAVILY_API_KEY")

    def _get_api_key_from_env(self) -> Optional[str]:
        """
        从环境变量获取 API key
        """
        import os
        import os as os_module
        return os_module.environ.get("TAVILY_API_KEY")

    def search(
        self,
        query: str,
        max_results: int = 5,
        include_images: bool = False,
        include_domains: List[str] | None = None
    ) -> Dict[str, Any]:
        """
        执行网络搜索

        Args:
            query: 搜索关键词
            max_results: 返回结果数量
            include_images: 是否包含图片结果
            include_domains: 限定的域名列表

        Returns:
            搜索结果字典
        """
        try:
            if not self.api_key:
                return {"results": [], "query": query}
            params = {
                "query": query,
                "max_results": max_results,
                "include_images": include_images
            }

            if include_domains:
                params["include_domains"] = include_domains

            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.api_key
            }

            response = requests.post(
                self.base_url,
                json=params,
                headers=headers,
                timeout=8
            )

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            print(f"网络搜索失败：{e}")
            return {
                "error": str(e),
                "results": [],
                "query": query
            }

    def search_with_context(
        self,
        query: str,
        context_type: str = "technical"
    ) -> Dict[str, Any]:
        """
        执行带有上下文搜索

        Args:
            query: 搜索关键词
            context_type: 搜索上下文类型 (technical/materials/safety)

        Returns:
            搜索结果
        """
        params = {
            "query": query,
            "max_results": 5,
            "search_depth": "advanced"
        }

        if context_type == "technical":
            # 技术文献搜索
            params["include_domains"] = ["polymer.org", "hydrocarbonprocessing.com", "rossscientific.com"]
            params["topic_specificity"] = "high"
        elif context_type == "materials":
            # 材料 TDS/MSDS 搜索
            params["include_domains"] = ["polymer-world.com", "tppsinc.com", "bostongroup.com"]
        elif context_type == "safety":
            # 安全规范搜索
            params["include_domains"] = ["dotgov.gov", "odot.gov", "eurlectra.eu"]

        headers = {
            "x-api-key": self.api_key
        }

        response = requests.post(
            self.base_url,
            json=params,
            headers=headers,
            timeout=30
        )

        response.raise_for_status()
        return response.json()

    def extract_technical_info(
        self,
        material_name: str,
        property_type: str = "ftir_peaks"
    ) -> List[Dict[str, Any]]:
        """
        从搜索结果中提取技术信息

        Args:
            material_name: 材料名称
            property_type: 技术信息类型 (ftir_peaks, thermal, chemical)

        Returns:
            提取的技术信息列表
        """
        search_queries = {
            "ftir_peaks": f"{material_name} FTIR spectrum characteristic peaks",
            "thermal": f"{material_name} DSC TGA thermal properties",
            "chemical": f"{material_name} chemical structure composition",
            "general": f"{material_name} technical datasheet"
        }

        query = search_queries.get(property_type, search_queries["general"])

        results = self.search(query=query, max_results=3)

        # 提取结果内容
        extracted_info = []
        for result in results.get("results", []):
            extracted_info.append({
                "source": result.get("url", "未知"),
                "title": result.get("title", ""),
                "snippet": result.get("content", "")[:500],
                "score": result.get("score", 0)
            })

        return extracted_info
