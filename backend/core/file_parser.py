"""
文件解析器
负责将 PDF、PPT 等文件转换为图像供 AI 分析
"""
import fitz  # PyMuPDF
from PIL import Image
import io
import os
from pathlib import Path
from typing import List, Dict, Any


def process_pdf_file(
    file_obj,
    output_dir: Path,
    page_range: tuple = (0, -1),  # (start_page, end_page)
    prefix: str = "",
) -> List[str]:
    """
    从 PDF 文件提取图像

    Args:
        file_obj: 文件对象
        output_dir: 输出目录
        page_range: 页码范围 (从 0 开始)

    Returns:
        提取的图像路径列表
    """
    image_paths = []
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 打开 PDF
        doc = fitz.open(stream=file_obj.read(), filetype="pdf")

        # 遍历指定页码范围
        start_page = max(0, min(page_range[0], doc.page_count - 1))
        end_page = min(page_range[1], doc.page_count - 1) if page_range[1] != -1 else doc.page_count - 1

        for page_num in range(start_page, end_page + 1):
            page = doc.load_page(page_num)
            # 渲染页面为像素数据
            mat = fitz.Matrix(2, 2)  # 2 倍放大
            pix = page.get_pixmap(matrix=mat)

            # 保存为 PNG 图像
            filename = f"{prefix}page_{page_num + 1}.png"
            image_path = output_dir / filename

            # 使用 PIL 处理并保存
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            img.save(image_path, "PNG")
            image_paths.append(str(image_path))

        doc.close()
        return image_paths

    except Exception as e:
        print(f"PDF 解析失败：{e}")
        raise


def process_image_file(file_obj, output_dir: Path) -> str:
    """
    处理单一图像文件

    Args:
        file_obj: 文件对象
        output_dir: 输出目录

    Returns:
        保存的图像路径
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # 保存原始文件
    filename = file_obj.filename or "image.png"
    save_path = output_dir / filename
    save_path.parent.mkdir(parents=True, exist_ok=True)

    with open(save_path, "wb") as f:
        f.write(file_obj.read())

    return str(save_path)


def process_ppt_file(file_obj, output_dir: Path) -> List[str]:
    """
    从 PPT 文件提取图像
    注意：python-pptx 主要处理文本内容，对于含图像/图表的 PPT
    需要先转换为 PDF 或直接使用.presentation库提取
    """
    # 简化处理：这里提示需要使用 presentation 库
    # 实际项目中可使用：python-pptx + presentation 或直接转 PDF
    print("PPT 处理需要 installation 'presentation' 库")
    return []


def validate_spectrum_image(image_path: str) -> Dict[str, Any]:
    """
    验证谱图图像质量

    Args:
        image_path: 图像路径

    Returns:
        验证结果
    """
    from PIL import Image as PILImage
    import numpy as np

    try:
        img = PILImage.open(image_path)
        width, height = img.size

        # 存储为numpy数组
        img_array = np.array(img)

        # 基本检查
        checks = {
            "valid": True,
            "width": width,
            "height": height,
            "format": img.format,
            "issues": []
        }

        # 检查尺寸是否过小的边缘图像
        if min(width, height) < 100:
            checks["issues"].append("图像尺寸过小")
            checks["valid"] = False

        # 检查是否为黑白图像（可能缺少坐标轴）
        if len(img_array.shape) == 2:
            checks["black_white"] = True
        else:
            checks["black_white"] = False

        return checks

    except Exception as e:
        return {
            "valid": False,
            "error": str(e)
        }
