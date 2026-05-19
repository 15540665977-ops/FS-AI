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


@pytest.mark.asyncio
async def test_extract_peaks_structured_parses_valid_json(orchestrator, test_image):
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text=(
        '{"suggested_material": "PP", "observed_peaks": ['
        '{"wavenumber": 2920, "assignment": "CH2 stretch", "intensity": "强"}]}'
    ))]
    with patch.object(orchestrator, 'async_client') as mock_client:
        mock_client.messages.create = AsyncMock(return_value=mock_resp)
        result = await orchestrator.extract_peaks_structured([test_image], "PP material analysis")
    assert result["suggested_material"] == "PP"
    assert len(result["observed_peaks"]) == 1
    assert result["observed_peaks"][0]["wavenumber"] == 2920
    assert result["observed_peaks"][0]["intensity"] == "强"


@pytest.mark.asyncio
async def test_extract_peaks_structured_returns_empty_on_api_error(orchestrator, test_image):
    with patch.object(orchestrator, 'async_client') as mock_client:
        mock_client.messages.create = AsyncMock(side_effect=Exception("API timeout"))
        result = await orchestrator.extract_peaks_structured([test_image], "text")
    assert result == {"suggested_material": None, "observed_peaks": []}


@pytest.mark.asyncio
async def test_extract_peaks_structured_returns_empty_on_bad_json(orchestrator, test_image):
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text="这不是JSON，是普通文字")]
    with patch.object(orchestrator, 'async_client') as mock_client:
        mock_client.messages.create = AsyncMock(return_value=mock_resp)
        result = await orchestrator.extract_peaks_structured([test_image], "text")
    assert result == {"suggested_material": None, "observed_peaks": []}


@pytest.mark.asyncio
async def test_extract_peaks_structured_filters_invalid_wavenumbers(orchestrator, test_image):
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text=(
        '{"suggested_material": null, "observed_peaks": ['
        '{"wavenumber": "not-a-number", "assignment": "bad", "intensity": "强"},'
        '{"wavenumber": 1735, "assignment": "C=O ester", "intensity": "很强"}]}'
    ))]
    with patch.object(orchestrator, 'async_client') as mock_client:
        mock_client.messages.create = AsyncMock(return_value=mock_resp)
        result = await orchestrator.extract_peaks_structured([test_image], "text")
    assert result["suggested_material"] is None
    assert len(result["observed_peaks"]) == 1
    assert result["observed_peaks"][0]["wavenumber"] == 1735


def test_joint_prompt_contains_cross_correlation(orchestrator):
    """联合分析提示词应包含交叉关联分析步骤"""
    text = orchestrator._build_prompt_text("joint", None, None, "", "", "")
    assert "交叉关联" in text
    assert "FTIR" in text
    assert "DSC" in text
    assert "TGA" in text


def test_joint_prompt_contains_identify_step(orchestrator):
    """联合分析提示词应包含图像识别步骤"""
    text = orchestrator._build_prompt_text("joint", None, None, "", "", "")
    assert "识别" in text
    assert "同一材料" in text


def test_joint_prompt_does_not_use_general_instruction(orchestrator):
    """joint 类型不应落入通用分析的 else 分支"""
    text = orchestrator._build_prompt_text("joint", None, None, "", "", "")
    # general branch ends with: "请分析上传的谱图，识别材料类型..."
    assert "请分析上传的谱图，识别材料类型" not in text


def test_general_prompt_unchanged_after_joint_added(orchestrator):
    """新增 joint 分支后通用分析提示词不受影响"""
    text = orchestrator._build_prompt_text("general", None, None, "", "", "")
    assert "请分析上传的谱图，识别材料类型" in text
