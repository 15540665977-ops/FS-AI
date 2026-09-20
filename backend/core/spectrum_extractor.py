"""
谱图曲线提取器 v2
使用 PIL + numpy 从谱图图像中提取曲线数据和峰位，无需 OpenCV / scipy。
支持 FTIR（透过率/吸光度）、TGA、DSC 谱图图像。

v2 改进：
  - 曲线提取从梯度法改为最暗像素法，避免误抓坐标轴线
  - 突出度阈值从 4% 降至 1.5%，检测弱峰/肩峰
  - 新增肩峰检测（二阶导数拐点法）
  - 新增强度分级（很强/强/中/弱）
  - 提取摘要更详细，区分主峰与肩峰，明确提示 Claude 分析未标注峰
"""
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont


# ──────────────────────────────────────────────────────────────────────────────
# 纯 numpy 信号处理工具函数
# ──────────────────────────────────────────────────────────────────────────────

def _gaussian_smooth(arr: np.ndarray, sigma: float = 2.0) -> np.ndarray:
    """对一维数组做高斯平滑（用 numpy 卷积实现）"""
    size = max(3, int(4 * sigma) | 1)
    x = np.arange(size) - size // 2
    kernel = np.exp(-x ** 2 / (2 * sigma ** 2))
    kernel /= kernel.sum()
    padded = np.pad(arr, size // 2, mode="edge")
    return np.convolve(padded, kernel, mode="valid")[: len(arr)]


def _find_local_minima(
    y: np.ndarray, min_prominence: float, min_distance: int
) -> list[dict]:
    """
    纯 numpy 局部极小值检测（适合 FTIR 透过率谱的吸收谷检测）。
    同时计算突出度（prominence）和半峰宽（FWHM）。
    """
    n = len(y)
    candidates = []
    for i in range(1, n - 1):
        if y[i] < y[i - 1] and y[i] < y[i + 1]:
            candidates.append(i)

    results = []
    for p in candidates:
        left_max = float(np.max(y[: p + 1]))
        right_max = float(np.max(y[p:]))
        key_height = min(left_max, right_max)
        prominence = key_height - float(y[p])

        if prominence < min_prominence:
            continue

        # 半峰宽
        half_level = float(y[p]) + prominence * 0.5
        lw = p
        for j in range(p - 1, max(0, p - n // 2), -1):
            if y[j] >= half_level:
                lw = j
                break
        rw = p
        for j in range(p + 1, min(n, p + n // 2)):
            if y[j] >= half_level:
                rw = j
                break

        results.append({
            "px": p,
            "value": float(y[p]),
            "prominence": prominence,
            "width_px": max(1, rw - lw),
            "left_edge": lw,
            "right_edge": rw,
        })

    results.sort(key=lambda r: -r["prominence"])
    filtered: list[dict] = []
    for r in results:
        if all(abs(r["px"] - f["px"]) >= min_distance for f in filtered):
            filtered.append(r)
    return sorted(filtered, key=lambda r: r["px"])


def _find_local_maxima(
    y: np.ndarray, min_prominence: float, min_distance: int
) -> list[dict]:
    """局部极大值检测（用于 FTIR 吸光度谱）"""
    peaks = _find_local_minima(-y, min_prominence, min_distance)
    for p in peaks:
        p["value"] = -p["value"]
    return peaks


# ──────────────────────────────────────────────────────────────────────────────
# 主提取类
# ──────────────────────────────────────────────────────────────────────────────

class SpectrumExtractor:
    """
    从谱图图像中提取曲线特征与峰位（v2）。
    全程只依赖 Pillow 和 numpy，不需要 OpenCV / scipy。
    """

    def extract_and_annotate(
        self, image_path: str, output_dir: Optional[str] = None
    ) -> dict:
        """
        主入口：提取曲线 → 检测峰 → 生成标注图 → 格式化摘要。
        """
        try:
            img = Image.open(image_path).convert("RGB")
            arr_rgb = np.array(img, dtype=np.float32)
            h, w = arr_rgb.shape[:2]
            gray = arr_rgb.mean(axis=2)

            # 背景亮暗检测
            corner_h, corner_w = max(1, h // 10), max(1, w // 10)
            corners = [
                gray[:corner_h, :corner_w],
                gray[:corner_h, -corner_w:],
                gray[-corner_h:, :corner_w],
                gray[-corner_h:, -corner_w:],
            ]
            bg_mean = float(np.mean([c.mean() for c in corners]))
            dark_bg = bg_mean < 128.0

            bounds = self._estimate_plot_bounds(gray, dark_bg)
            curve, valid = self._extract_curve_profile(gray, bounds, dark_bg)
            if not valid or len(curve) < 30:
                return self._fallback(image_path, "曲线变化量不足")

            spec_type = self._infer_spectrum_type(curve)
            axis_info = self._estimate_axis(spec_type, bounds)

            # 用轻平滑做峰检测（保留更多细节）
            sigma_light = max(1.5, len(curve) / 600.0)
            smoothed = _gaussian_smooth(curve, sigma=sigma_light)

            all_peaks = self._detect_peaks(smoothed, spec_type, axis_info)
            all_peaks = self._classify_peak_types(all_peaks, smoothed)

            ann_path: Optional[str] = None
            if output_dir and all_peaks:
                ann_path = self._draw_annotated_image(
                    img, all_peaks, bounds, axis_info, output_dir, image_path
                )

            summary = self._format_summary(spec_type, axis_info, all_peaks, smoothed)

            return {
                "spectrum_type": spec_type,
                "axis_info": axis_info,
                "peaks": all_peaks,
                "curve_stats": {
                    "min_val": float(np.min(smoothed)),
                    "max_val": float(np.max(smoothed)),
                    "range": float(np.max(smoothed) - np.min(smoothed)),
                },
                "annotated_path": ann_path,
                "summary_text": summary,
            }

        except Exception as exc:
            return self._fallback(image_path, str(exc))

    # ──────────────────────────────────────────────────────────────────────
    # 绘图区域估计
    # ──────────────────────────────────────────────────────────────────────

    def _estimate_plot_bounds(self, gray: np.ndarray, dark_bg: bool) -> dict:
        """估计谱图绘图区域的像素边界"""
        h, w = gray.shape
        L = int(w * 0.13)
        R = int(w * 0.96)
        T = int(h * 0.06)
        B = int(h * 0.86)

        threshold = 80.0 if not dark_bg else 180.0
        for y in range(min(B, h - 1), max(T, 0), -1):
            row = gray[y, L:R]
            dark_ratio = float(np.mean(row < threshold if not dark_bg else row > threshold))
            if dark_ratio > 0.45:
                B = y
                break

        for x in range(L, min(R, w)):
            col = gray[T:B, x]
            dark_ratio = float(np.mean(col < threshold if not dark_bg else col > threshold))
            if dark_ratio > 0.25:
                L = x
                break

        if R - L < 50 or B - T < 30:
            L, R, T, B = int(w * 0.13), int(w * 0.96), int(h * 0.06), int(h * 0.86)

        return {"left": L, "right": R, "top": T, "bottom": B,
                "width": R - L, "height": B - T}

    # ──────────────────────────────────────────────────────────────────────
    # 曲线轮廓提取（v2：最暗像素法 + 边缘排除 + 中位数滤波）
    # ──────────────────────────────────────────────────────────────────────

    def _extract_curve_profile(
        self, gray: np.ndarray, bounds: dict, dark_bg: bool
    ) -> tuple[np.ndarray, bool]:
        """
        v2 核心改进：
        - 亮底暗线：用 argmin（最暗像素 = 曲线），比梯度法更准确
        - 排除底部边缘（x 轴线）和顶部边缘（图题）
        - 移动中位数滤除坐标轴文字/网格线造成的跳变点
        """
        L, R, T, B = bounds["left"], bounds["right"], bounds["top"], bounds["bottom"]
        h_plot = B - T
        if h_plot <= 0 or R <= L:
            return np.array([]), False

        # 排除靠近坐标轴的边缘像素
        margin_top    = max(2, int(h_plot * 0.04))
        margin_bottom = max(4, int(h_plot * 0.07))
        T_s = T + margin_top
        B_s = B - margin_bottom
        h_s = B_s - T_s

        if h_s < 10:
            return np.array([]), False

        curve_y = []
        for x in range(L, R):
            col = gray[T_s:B_s, x].astype(float)
            if dark_bg:
                y_pos = int(np.argmax(col))   # 亮线
            else:
                y_pos = int(np.argmin(col))   # 暗线（曲线本体）
            norm = 1.0 - (y_pos + margin_top) / max(h_plot - 1, 1)
            curve_y.append(float(np.clip(norm, 0.0, 1.0)))

        curve = np.array(curve_y, dtype=float)
        # 移动中位数滤波：去除坐标轴文字/网格线造成的孤立跳变点
        curve = self._median_filter_1d(curve, window=5)

        smoothed = _gaussian_smooth(curve, sigma=2.0)
        variation = float(np.std(smoothed))
        # v2：降低有效性阈值（0.015 → 0.008）
        return curve, variation > 0.008

    @staticmethod
    def _median_filter_1d(arr: np.ndarray, window: int = 5) -> np.ndarray:
        """用移动中位数滤除孤立跳变点"""
        half = window // 2
        result = arr.copy()
        for i in range(half, len(arr) - half):
            result[i] = float(np.median(arr[i - half: i + half + 1]))
        return result

    # ──────────────────────────────────────────────────────────────────────
    # 谱图类型推断
    # ──────────────────────────────────────────────────────────────────────

    def _infer_spectrum_type(self, curve: np.ndarray) -> str:
        first_half = float(np.mean(curve[: len(curve) // 2]))
        second_half = float(np.mean(curve[len(curve) // 2:]))
        if first_half - second_half > 0.30:
            return "tga"
        p90 = float(np.percentile(curve, 90))
        if p90 > 0.55:
            return "ftir_transmittance"
        if p90 < 0.45:
            return "ftir_absorbance"
        return "ftir_transmittance"

    # ──────────────────────────────────────────────────────────────────────
    # 轴标定
    # ──────────────────────────────────────────────────────────────────────

    def _estimate_axis(self, spec_type: str, bounds: dict) -> dict:
        px_w = bounds["right"] - bounds["left"]
        if spec_type == "ftir_transmittance":
            return {"x_unit": "cm⁻¹", "x_min": 400, "x_max": 4000,
                    "x_reversed": True,
                    "y_unit": "%T", "y_min": 0.0, "y_max": 100.0,
                    "plot_width_px": px_w, "confidence": "assumed"}
        if spec_type == "ftir_absorbance":
            return {"x_unit": "cm⁻¹", "x_min": 400, "x_max": 4000,
                    "x_reversed": True,
                    "y_unit": "Abs", "y_min": 0.0, "y_max": 2.0,
                    "plot_width_px": px_w, "confidence": "assumed"}
        if spec_type == "tga":
            return {"x_unit": "°C", "x_min": 25, "x_max": 700,
                    "x_reversed": False,
                    "y_unit": "wt%", "y_min": 0.0, "y_max": 100.0,
                    "plot_width_px": px_w, "confidence": "assumed"}
        return {"x_unit": "°C", "x_min": -80, "x_max": 400,
                "x_reversed": False,
                "y_unit": "mW/mg", "y_min": None, "y_max": None,
                "plot_width_px": px_w, "confidence": "assumed"}

    # ──────────────────────────────────────────────────────────────────────
    # 峰检测（v2：阈值降低，检测更多峰，增加肩峰）
    # ──────────────────────────────────────────────────────────────────────

    def _detect_peaks(
        self, smoothed: np.ndarray, spec_type: str, axis_info: dict
    ) -> list[dict]:
        n = len(smoothed)
        if n == 0:
            return []

        y_range = float(np.max(smoothed) - np.min(smoothed))
        # v2：阈值从 4% 降至 1.5%，最小值从 0.015 降至 0.008
        min_prom = max(y_range * 0.015, 0.008)
        # v2：最小间隔收紧，允许检测密集峰
        min_dist = max(4, n // 70)

        if spec_type == "ftir_transmittance":
            raw = _find_local_minima(smoothed, min_prom, min_dist)
        elif spec_type == "ftir_absorbance":
            raw = _find_local_maxima(smoothed, min_prom, min_dist)
        elif spec_type == "tga":
            grad = np.gradient(smoothed)
            raw = _find_local_minima(grad, min_prom * 0.3, min_dist)
        else:
            min_raw = _find_local_minima(smoothed, min_prom, min_dist)
            max_raw = _find_local_maxima(smoothed, min_prom, min_dist)
            raw = sorted(min_raw + max_raw, key=lambda r: r["px"])

        peaks = [self._px_to_physical(p, axis_info, smoothed) for p in raw]

        # 补充肩峰检测（二阶导数拐点法）
        shoulders = self._detect_inflection_shoulders(smoothed, peaks, axis_info)
        peaks = sorted(peaks + shoulders, key=lambda p: p["pixel_x"])
        return peaks

    def _detect_inflection_shoulders(
        self,
        smoothed: np.ndarray,
        existing_peaks: list[dict],
        axis_info: dict,
    ) -> list[dict]:
        """
        通过二阶导数拐点检测肩峰。
        在已有峰的两侧斜坡上找二阶导数符号变化，识别未被 _find_local_minima 捕获的肩峰。
        """
        n = len(smoothed)
        if n < 20 or not existing_peaks:
            return []

        d1 = np.gradient(smoothed)
        d2 = np.gradient(d1)
        d2_std = float(np.std(d2))
        if d2_std < 1e-8:
            return []

        existing_px = {p["pixel_x"] for p in existing_peaks}
        min_gap = max(6, n // 80)

        shoulders = []
        for i in range(2, n - 2):
            # 二阶导数符号变化 = 拐点
            if d2[i - 1] * d2[i + 1] < 0 and abs(d2[i]) > d2_std * 0.4:
                # 必须在已有峰附近（峰的斜坡上）
                nearest_dist = min(abs(i - px) for px in existing_px)
                max_neighbor = max(15, n // 12)
                if nearest_dist < max_neighbor and nearest_dist >= min_gap:
                    if all(abs(i - px) >= min_gap for px in existing_px):
                        prom_est = abs(d2[i]) / (d2_std + 1e-9) * 0.05
                        fake = {
                            "px": i,
                            "value": float(smoothed[i]),
                            "prominence": prom_est,
                            "width_px": max(4, min_gap),
                            "left_edge": max(0, i - min_gap // 2),
                            "right_edge": min(n - 1, i + min_gap // 2),
                        }
                        phys = self._px_to_physical(fake, axis_info, smoothed)
                        phys["is_shoulder"] = True
                        shoulders.append(phys)
                        existing_px.add(i)

        return shoulders

    def _classify_peak_types(
        self, peaks: list[dict], smoothed: np.ndarray
    ) -> list[dict]:
        """将峰分类为主峰 / 肩峰 / 弱峰，并添加强度标签。"""
        if not peaks:
            return peaks

        max_prom = max((p["prominence_rel"] for p in peaks), default=1.0)

        for p in peaks:
            if p.get("is_shoulder"):
                p["peak_type"] = "shoulder"
            elif p["prominence_rel"] < max_prom * 0.12:
                p["peak_type"] = "weak"
            else:
                p["peak_type"] = "main"

            ratio = p["prominence_rel"] / (max_prom + 1e-9)
            if ratio >= 0.6:
                p["intensity"] = "很强"
            elif ratio >= 0.3:
                p["intensity"] = "强"
            elif ratio >= 0.12:
                p["intensity"] = "中"
            else:
                p["intensity"] = "弱"

        return peaks

    def _px_to_physical(
        self, p: dict, axis_info: dict, smoothed: np.ndarray
    ) -> dict:
        """将像素坐标的峰信息转换为物理坐标"""
        px_w = axis_info["plot_width_px"]
        rel = p["px"] / max(px_w - 1, 1)

        ax = axis_info
        x_span = ax["x_max"] - ax["x_min"]
        x_val = ax["x_max"] - rel * x_span if ax["x_reversed"] else ax["x_min"] + rel * x_span

        y_max = ax.get("y_max") or 1.0
        y_min = ax.get("y_min") or 0.0
        y_phys = p["value"] * (y_max - y_min) + y_min
        width_phys = max(1, int(p["width_px"] / max(px_w - 1, 1) * x_span))

        return {
            "x_val": int(round(x_val)),
            "x_unit": ax["x_unit"],
            "y_val": round(float(y_phys), 1),
            "y_unit": ax["y_unit"],
            "width": width_phys,
            "prominence_rel": round(p["prominence"] * 100.0, 1),
            "pixel_x": p["px"],
            "pixel_left": p.get("left_edge", p["px"]),
            "pixel_right": p.get("right_edge", p["px"]),
            "shape": self._classify_shape(smoothed, p),
            "is_shoulder": p.get("is_shoulder", False),
            "peak_type": "main",
            "intensity": "中",
        }

    def _classify_shape(self, curve: np.ndarray, peak: dict) -> str:
        """峰形分类：narrow / medium / broad，+ _asymmetric 后缀"""
        n = len(curve)
        w_rel = peak["width_px"] / max(n, 1)
        shape = "narrow" if w_rel < 0.025 else ("medium" if w_rel < 0.06 else "broad")

        hw = max(1, peak["width_px"] // 2)
        p = peak["px"]
        left_seg = curve[max(0, p - hw): p]
        right_seg = curve[p: min(n, p + hw)]
        if len(left_seg) > 1 and len(right_seg) > 1:
            ls = float(np.std(left_seg))
            rs = float(np.std(right_seg))
            if (ls + rs) > 1e-6 and abs(ls - rs) / (ls + rs) > 0.35:
                shape += "_asymmetric"
        return shape

    # ──────────────────────────────────────────────────────────────────────
    # 标注图生成（v2：主峰红，肩峰橙，弱峰灰黄，FWHM 蓝线）
    # ──────────────────────────────────────────────────────────────────────

    def _draw_annotated_image(
        self,
        img: Image.Image,
        peaks: list[dict],
        bounds: dict,
        axis_info: dict,
        output_dir: str,
        orig_path: str,
    ) -> Optional[str]:
        try:
            ann = img.copy().convert("RGBA")
            overlay = Image.new("RGBA", ann.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)

            L, T, B = bounds["left"], bounds["top"], bounds["bottom"]

            try:
                font_small = ImageFont.truetype("arial.ttf", 10)
            except Exception:
                font_small = ImageFont.load_default()

            COLOR_MAIN     = (220,  50,  50, 210)
            COLOR_SHOULDER = (230, 130,  20, 200)
            COLOR_WEAK     = (150, 150,  30, 170)
            COLOR_FWHM     = ( 60, 120, 240, 150)

            main_peaks  = [p for p in peaks if p.get("peak_type") == "main"]
            other_peaks = [p for p in peaks if p.get("peak_type") != "main"]

            for i, p in enumerate(main_peaks[:25]):
                px = L + p["pixel_x"]
                if not (L <= px <= bounds["right"]):
                    continue
                y = T
                while y < B:
                    draw.line([(px, y), (px, min(y + 4, B))], fill=COLOR_MAIN, width=1)
                    y += 7
                ly = T + 4 + (i % 7) * 11
                draw.text((max(px - 14, L), ly), str(p["x_val"]),
                          fill=(200, 40, 40, 240), font=font_small)
                # FWHM 横线
                y_mid = T + int(bounds["height"] * 0.6)
                pl = L + p["pixel_left"]
                pr = L + p["pixel_right"]
                if pl < pr:
                    draw.line([(pl, y_mid), (pr, y_mid)], fill=COLOR_FWHM, width=2)

            for p in other_peaks[:15]:
                px = L + p["pixel_x"]
                if not (L <= px <= bounds["right"]):
                    continue
                col = COLOR_SHOULDER if p.get("peak_type") == "shoulder" else COLOR_WEAK
                y = T
                while y < B:
                    draw.line([(px, y), (px, min(y + 2, B))], fill=col, width=1)
                    y += 5
                draw.text((max(px - 10, L), T + bounds["height"] - 16),
                          f"~{p['x_val']}", fill=col, font=font_small)

            main_cnt  = sum(1 for p in peaks if p.get("peak_type") == "main")
            other_cnt = len(peaks) - main_cnt
            note = f"主峰{main_cnt}+肩峰/弱峰{other_cnt} ±20~50{axis_info['x_unit']}"
            draw.text((L, max(0, T - 14)), note, fill=(80, 80, 200, 200), font=font_small)

            merged = Image.alpha_composite(ann, overlay).convert("RGB")
            stem = Path(orig_path).stem
            out_path = Path(output_dir) / f"{stem}_annotated.png"
            merged.save(str(out_path), "PNG")
            return str(out_path)

        except Exception:
            return None

    # ──────────────────────────────────────────────────────────────────────
    # 文本摘要（v2：分主峰/肩峰/弱峰，含强度，明确要求分析未标注峰）
    # ──────────────────────────────────────────────────────────────────────

    def _format_summary(
        self,
        spec_type: str,
        axis_info: dict,
        peaks: list[dict],
        curve: np.ndarray,
    ) -> str:
        _type_cn = {
            "ftir_transmittance": "FTIR 透过率谱",
            "ftir_absorbance":    "FTIR 吸光度谱",
            "tga":                "TGA 热重曲线",
            "dsc":                "DSC 热分析曲线",
        }
        _shape_cn = {
            "narrow":            "窄·对称",
            "medium":            "中等宽度",
            "broad":             "宽",
            "narrow_asymmetric": "窄·有肩峰",
            "medium_asymmetric": "中等·有肩峰",
            "broad_asymmetric":  "宽·有肩峰",
        }

        x_unit = axis_info["x_unit"]
        y_unit = axis_info["y_unit"]
        main_peaks  = [p for p in peaks if p.get("peak_type") == "main"]
        other_peaks = [p for p in peaks if p.get("peak_type") != "main"]

        lines = [
            "╔══════════════════════════════════════════════════════════╗",
            "║   图像曲线自动提取数据 v2（含未标注峰）— 优先参考         ║",
            "╚══════════════════════════════════════════════════════════╝",
            f"推断谱图类型：{_type_cn.get(spec_type, spec_type)}",
            f"X 轴估算范围：{axis_info['x_min']}–{axis_info['x_max']} {x_unit}（标准假设）",
            f"共检测到吸收特征：{len(peaks)} 个  "
            f"（主峰 {len(main_peaks)}，肩峰/弱峰 {len(other_peaks)}）",
            "",
            "★ 分析要求：请逐一核对以下所有峰（含图中【未标注】的峰），",
            "  不得仅依赖图中可见的文字标签，未标注峰同样需要归属与解读。",
            "",
        ]

        if main_peaks:
            lines.append(f"━━ 主峰 ({len(main_peaks)} 个) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            lines.append(
                f"{'#':>3}  {'峰位':>8}  {'纵坐标':>9}  {'半峰宽':>7}  {'强度':>4}  峰形"
            )
            lines.append("─" * 60)
            for i, p in enumerate(main_peaks[:30], 1):
                shape_str = _shape_cn.get(p["shape"], p["shape"])
                lines.append(
                    f"{i:>3}  {p['x_val']:>5}{x_unit:3}  "
                    f"{p['y_val']:>7.1f}{y_unit:3}  "
                    f"~{p['width']:>4}{x_unit:3}  "
                    f"{p['intensity']:>4}  {shape_str}"
                )

        if other_peaks:
            lines.append("")
            lines.append(
                f"━━ 肩峰 / 弱峰（图中可能未标注，{len(other_peaks)} 个）━━━━━━━━━━"
            )
            lines.append(
                f"{'#':>3}  {'峰位':>8}  {'纵坐标':>9}  {'强度':>4}  峰形"
            )
            lines.append("─" * 48)
            for i, p in enumerate(other_peaks[:20], 1):
                shape_str = _shape_cn.get(p["shape"], p["shape"])
                lines.append(
                    f"{i:>3}  {p['x_val']:>5}{x_unit:3}  "
                    f"{p['y_val']:>7.1f}{y_unit:3}  "
                    f"{p['intensity']:>4}  {shape_str}"
                )

        if not peaks:
            lines.append("（未检测到显著峰——请以 AI 视觉分析为主）")

        lines += [
            "",
            f"⚠ 峰位精度约 ±20–50 {x_unit}（像素级估算，不如图中标注值精确）",
            "⚠ 上表用于发现未标注峰；图中已标注的数值以其为准",
        ]
        return "\n".join(lines)

    # ──────────────────────────────────────────────────────────────────────
    # 回退结果
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def _fallback(image_path: str, reason: str = "") -> dict:
        msg = "【图像曲线提取失败】"
        if reason:
            msg += f"原因：{reason}。"
        msg += "将完全依赖 AI 视觉分析。"
        return {
            "spectrum_type": "unknown",
            "axis_info": {},
            "peaks": [],
            "curve_stats": {},
            "annotated_path": None,
            "summary_text": msg,
        }
