"""
知识库初始化脚本（重置版）
清除并重新导入 materials + chemicals 集合
"""
import json
from pathlib import Path
import chromadb
from chromadb.config import Settings

KNOWLEDGE_DIR = Path(__file__).parent


def _get_client():
    chroma_dir = str(KNOWLEDGE_DIR.parent / "chroma_db")
    return chromadb.PersistentClient(
        path=chroma_dir,
        settings=Settings(anonymized_telemetry=False),
    )


def seed_materials(client):
    data = json.loads((KNOWLEDGE_DIR / "materials.json").read_text(encoding="utf-8"))

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
                "source": "materials",
            }],
        )
        print(f"  [材料] 导入：{mat_id}")

    print(f"  → 共导入 {len(data)} 种聚合物材料\n")


def seed_chemicals(client):
    data = json.loads((KNOWLEDGE_DIR / "chemicals.json").read_text(encoding="utf-8"))

    try:
        client.delete_collection("chemicals")
        print("旧 chemicals 集合已清除")
    except Exception:
        pass

    col = client.create_collection(
        name="chemicals",
        metadata={"description": "添加剂/化学品FTIR指纹库"},
    )

    for chem_id, chem in data.items():
        peaks = chem.get("ftir_peaks", [])
        peak_str = "；".join(
            f"{p['wavenumber']} cm⁻¹ {p['assignment']}（{p['intensity']}）"
            for p in peaks
        )

        doc = (
            f"化学品：{chem_id} | {', '.join(chem.get('common_names', []))}\n"
            f"类别：{chem.get('category', '')}\n"
            f"FTIR特征峰（{len(peaks)}条）：{peak_str}\n"
            f"识别特征：{chem.get('识别特征', '')}\n"
            f"应用场景：{chem.get('应用场景', '')}\n"
            f"常见宿主材料：{', '.join(chem.get('常见宿主材料', []))}"
        )

        col.add(
            documents=[doc],
            ids=[chem_id],
            metadatas=[{
                "category": chem.get("category", ""),
                "peak_count": len(peaks),
                "source": "chemicals",
            }],
        )
        print(f"  [化学品] 导入：{chem_id}")

    print(f"  → 共导入 {len(data)} 种化学品/添加剂\n")


def seed_failure_modes(client):
    data = json.loads((KNOWLEDGE_DIR / "failure_modes.json").read_text(encoding="utf-8"))

    try:
        client.delete_collection("failure_modes")
        print("旧 failure_modes 集合已清除")
    except Exception:
        pass

    col = client.create_collection(
        name="failure_modes",
        metadata={"description": "失效模式特征库"},
    )

    for mode_id, mode in data.items():
        ftir = mode.get("ftir_changes", {})
        new_peaks = ftir.get("new_peaks", [])
        def fmt_peak(p):
            if isinstance(p, dict):
                return f"{p.get('wavenumber', '')} cm⁻¹ {p.get('assignment', '')}"
            return str(p)

        new_peak_str = "；".join(fmt_peak(p) for p in new_peaks)
        weakened_list = ftir.get("weakened_peaks", [])
        weakened = "；".join(fmt_peak(p) for p in weakened_list)
        dsc = mode.get("dsc_changes", {})
        tga = mode.get("tga_changes", {})

        doc = (
            f"失效模式：{mode_id} | {mode.get('name', '')}\n"
            f"材料范围：{', '.join(mode.get('materials', []))}\n"
            f"机理：{mode.get('mechanism', '')}\n"
            f"FTIR新增峰：{new_peak_str}\n"
            f"FTIR减弱峰：{weakened}\n"
            f"DSC变化：Tm={dsc.get('tm_shift', '')}；Tg={dsc.get('tg_shift', '')}\n"
            f"TGA变化：{tga.get('onset_shift', '')} 残留={tga.get('residue_change', '')}\n"
            f"置信度说明：{mode.get('confidence_notes', '')}"
        )

        col.add(
            documents=[doc],
            ids=[mode_id],
            metadatas=[{
                "materials": ", ".join(mode.get("materials", [])),
                "source": "failure_modes",
            }],
        )
        print(f"  [失效模式] 导入：{mode_id}")

    print(f"  → 共导入 {len(data)} 种失效模式\n")


def main():
    client = _get_client()
    seed_materials(client)
    seed_chemicals(client)
    seed_failure_modes(client)
    print("OK: 知识库初始化完成")


if __name__ == "__main__":
    main()
