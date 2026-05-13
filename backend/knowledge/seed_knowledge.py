"""
知识库初始化脚本（重置版）
清除并重新导入 materials 集合
"""
import json
from pathlib import Path
import chromadb
from chromadb.config import Settings


def main():
    data = json.loads((Path(__file__).parent / "materials.json").read_text(encoding="utf-8"))

    chroma_dir = str(Path(__file__).parent.parent / "chroma_db")
    client = chromadb.PersistentClient(
        path=chroma_dir,
        settings=Settings(anonymized_telemetry=False),
    )

    # 删除旧集合后重建
    try:
        client.delete_collection("materials")
        print("旧 materials 集合已清除")
    except Exception:
        pass

    col = client.create_collection(
        name="materials",
        metadata={"description": "材料FTIR/DSC/TGA特征峰指纹库"},
    )

    for mat_id, mat in data.items():
        peaks = mat.get("ftir_peaks", [])
        peak_str = "；".join(
            f"{p['wavenumber']} cm⁻¹ {p['assignment']}（{p['intensity']}）"
            for p in peaks
        )
        dsc = mat.get("dsc_parameters", {})
        tga = mat.get("tga_characteristics", {})

        doc = (
            f"材料：{mat_id} | {', '.join(mat.get('common_names', []))}\n"
            f"类型：{mat.get('material_type', '')}\n"
            f"FTIR特征峰（{len(peaks)}条）：{peak_str}\n"
            f"DSC参数：Tm={dsc.get('tm_range','')}；Tg={dsc.get('tg_range','')}；ΔHm={dsc.get('delta_h_range','')}\n"
            f"TGA：起始分解={tga.get('onset_decomposition','')}；残留={tga.get('residue','')}\n"
            f"鉴别要点：{mat.get('鉴别要点', '')}\n"
            f"常见混淆：{mat.get('常见混淆', '')}"
        )

        col.add(
            documents=[doc],
            ids=[mat_id],
            metadatas=[{
                "material_type": mat.get("material_type", ""),
                "peak_count": len(peaks),
            }],
        )
        print(f"  导入：{mat_id}")

    print(f"\n完成：共导入 {len(data)} 种材料")


if __name__ == "__main__":
    main()
