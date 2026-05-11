import base64
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from PIL import Image
import pytest

from core.analyzer import AnalysisOrchestrator


@pytest.fixture
def test_image(tmp_path) -> str:
    """创建一个最小测试图像并返回路径"""
    img = Image.new("RGB", (200, 100), color=(255, 255, 255))
    path = tmp_path / "test_ir.png"
    img.save(path, "PNG")
    return str(path)


@pytest.fixture
def orchestrator():
    with patch("core.rag.chromadb.PersistentClient"):
        return AnalysisOrchestrator(api_key="test-key")


def test_encode_image_returns_base64_and_media_type(orchestrator, test_image):
    data, media_type = orchestrator._encode_image(test_image)
    decoded = base64.b64decode(data)
    assert len(decoded) > 0
    assert media_type == "image/png"


def test_encode_image_jpeg_media_type(orchestrator, tmp_path):
    img = Image.new("RGB", (50, 50))
    path = tmp_path / "test.jpg"
    img.save(path, "JPEG")
    _, media_type = orchestrator._encode_image(str(path))
    assert media_type == "image/jpeg"


def test_build_vision_messages_structure(orchestrator, test_image):
    messages = orchestrator._build_vision_messages([test_image], "请分析这张谱图")
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    content = messages[0]["content"]
    assert content[0]["type"] == "image"
    assert content[0]["source"]["type"] == "base64"
    assert content[0]["source"]["media_type"] == "image/png"
    assert content[-1]["type"] == "text"
    assert content[-1]["text"] == "请分析这张谱图"


def test_build_vision_messages_multiple_images(orchestrator, test_image):
    messages = orchestrator._build_vision_messages([test_image, test_image], "对比分析")
    content = messages[0]["content"]
    image_blocks = [c for c in content if c["type"] == "image"]
    assert len(image_blocks) == 2


@pytest.mark.asyncio
async def test_analyze_stream_yields_text(orchestrator, test_image):
    """模拟 Claude API，验证 analyze_stream 能逐块 yield 文本"""
    mock_stream = MagicMock()
    mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
    mock_stream.__aexit__ = AsyncMock(return_value=False)

    async def fake_text_stream():
        for chunk in ["分析结果：", "PP 材料，", "特征峰 2917 cm⁻¹"]:
            yield chunk

    mock_stream.text_stream = fake_text_stream()

    mock_async_client = MagicMock()
    mock_async_client.messages.stream.return_value = mock_stream

    orchestrator._async_client = mock_async_client

    chunks = []
    async for chunk in orchestrator.analyze_stream(
        images=[test_image],
        analysis_type="general",
        material_hint="PP",
    ):
        chunks.append(chunk)

    assert len(chunks) == 3
    assert "2917" in "".join(chunks)
