"""连通组整体校准：以一片为锚点，联合最小二乘降低组内对应点误差。

修复师从当前装配选一片陶片作**锚点**，对其所在连通组请求整体校准：
以组内**全部有效关系**的成对边缘标记共同最小化对应点误差平方和
（Σ‖对应点世界坐标差‖²），只调整其余碎片的**平移和旋转**——
锚点位姿、碎片轮廓、标记、关系状态（active / undone_at / created_at）
及连通分组均不变。

预览（evaluate_calibration）只读数据库、不写入，返回：
- 调整前/后每片位姿（x、y、角度与位移量）；
- 逐关系、逐对对应点的调整前/后误差及最大误差，总误差平方和变化；
- 调整后组内轮廓两两内部重叠明细（允许共边/共点）。

仅当**同时**满足以下三条才可确认，否则给出冲突原因并保持现状：
1. 调整后误差总量严格小于调整前（数值噪声不算下降）；
2. 每对对应点误差均 ≤ 1 mm；
3. 组内轮廓内部不重叠。

确认（main.py）在锁与同一事务内用同一锚点重新演算，通过后仅更新非锚点
碎片位姿与组内有效关系的 max_error，重算校验，版本只递增一次并留下
不可改快照（source=calibration）。
"""
from __future__ import annotations

import math

from . import geometry
from .revision import _component

# 总量必须严格下降；小于该阈值（mm²）视为浮点噪声，不算下降
SSE_IMPROVE_EPS = 1e-9


class CalibrationError(Exception):
    """对象级错误（锚点不存在、所在组不足两片），status 为 HTTP 状态码。"""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message

    def detail(self) -> dict:
        return {"message": self.message, "code": self.code}


def evaluate_calibration(d, anchor_id: int) -> dict:
    """演算一次整体校准（只读不写）。

    锚点不存在 → CalibrationError(404, anchor_not_found)；
    锚点所在连通组不足两片 → CalibrationError(400, group_too_small)。
    否则返回完整预览结构（ok 表示是否满足全部确认条件）。
    """
    anchor = d.get_fragment(anchor_id)
    if anchor is None:
        raise CalibrationError(404, "anchor_not_found",
                               f"锚点碎片 #{anchor_id} 不存在")

    comp_ids, comp_rels = _component(d, anchor_id)
    if len(comp_ids) < 2:
        raise CalibrationError(
            400, "group_too_small",
            f"锚点碎片 #{anchor_id} 当前为独立碎片，所在连通组不足两片，"
            "无整体校准对象")

    frags = {f["id"]: f for f in d.all_fragments()}
    poses_before = {fid: (f["x"], f["y"], f["theta"]) for fid, f in frags.items()
                    if fid in comp_ids}

    # 组内全部有效关系的成对边缘标记（局部坐标，随各自位姿变换到世界坐标）
    corrs: list[tuple] = []
    for r in comp_rels:
        for ma, mb in zip(r["markers_a"], r["markers_b"]):
            corrs.append((r["fragment_a"], tuple(ma),
                          r["fragment_b"], tuple(mb)))

    poses_after, sse_before, sse_after, iterations = geometry.calibrate_poses(
        poses_before, corrs, anchor_id)

    rel_rows = []
    for r in sorted(comp_rels, key=lambda x: x["id"]):
        a, b = r["fragment_a"], r["fragment_b"]
        errs_before = geometry.pair_errors(
            r["markers_a"], r["markers_b"], poses_before[a], poses_before[b])
        errs_after = geometry.pair_errors(
            r["markers_a"], r["markers_b"], poses_after[a], poses_after[b])
        rel_rows.append({
            "relation_id": r["id"],
            "fragment_a": a,
            "fragment_b": b,
            "marker_pairs": len(errs_after),
            "errors_before": errs_before,
            "errors_after": errs_after,
            "max_error_before": max(errs_before) if errs_before else 0.0,
            "max_error_after": max(errs_after) if errs_after else 0.0,
            "markers_a": r["markers_a"],
            "markers_b": r["markers_b"],
        })

    # 调整后组内轮廓两两内部重叠（允许共边/共点）
    overlaps = []
    placed = [
        (fid, frags[fid]["name"],
         geometry.contour_world(frags[fid]["contour"], poses_after[fid]))
        for fid in sorted(comp_ids)
    ]
    for id1, id2, name1, name2, area in geometry.find_overlaps(placed):
        overlaps.append({"fragment_a": id1, "fragment_b": id2,
                         "name_a": name1, "name_b": name2,
                         "area_mm2": area})

    conflicts: list[str] = []
    strictly_down = sse_after < sse_before - SSE_IMPROVE_EPS
    if not strictly_down:
        if sse_after >= sse_before - SSE_IMPROVE_EPS and sse_after <= sse_before + SSE_IMPROVE_EPS:
            conflicts.append(
                f"误差总量未严格下降（校准前 {sse_before:.6f} mm²，"
                f"校准后 {sse_after:.6f} mm²，已无整体改善空间）")
        else:
            conflicts.append(
                f"误差总量未下降（校准前 {sse_before:.6f} mm²，"
                f"校准后 {sse_after:.6f} mm²）")

    limit_rows = [row for row in rel_rows
                  if row["max_error_after"] > geometry.MAX_ERROR_MM + 1e-9]
    for row in limit_rows:
        rid = row["relation_id"]
        for i, e in enumerate(row["errors_after"]):
            if e > geometry.MAX_ERROR_MM + 1e-9:
                conflicts.append(
                    f"误差超限：关系 #{rid} 第 {i + 1} 对对应点校准后误差 "
                    f"{e:.3f} mm，超过 {geometry.MAX_ERROR_MM:.0f} mm 限值")

    for o in overlaps:
        conflicts.append(
            f"碰撞：碎片「{o['name_a']}」与「{o['name_b']}」校准后轮廓内部"
            f"重叠 {o['area_mm2']:.2f} mm²")

    fragments = []
    for fid in sorted(comp_ids):
        x0, y0, th0 = poses_before[fid]
        x1, y1, th1 = poses_after[fid]
        fragments.append({
            "fragment_id": fid,
            "name": frags[fid]["name"],
            "anchor": fid == anchor_id,
            "group_id": frags[fid]["group_id"],
            "moved": fid != anchor_id,
            "x_before": x0,
            "y_before": y0,
            "theta_before": th0,
            "x_after": x1,
            "y_after": y1,
            "theta_after": th1,
            "dx": x1 - x0,
            "dy": y1 - y0,
            # 角度变化归一化到 (-π, π]
            "dtheta": ((th1 - th0 + math.pi) % (2 * math.pi)) - math.pi,
        })

    return {
        "ok": not conflicts,
        "anchor_id": anchor_id,
        "fragment_ids": sorted(comp_ids),
        "relation_count": len(comp_rels),
        "iterations": iterations,
        "sse_before": sse_before,
        "sse_after": sse_after,
        "sse_delta": sse_after - sse_before,
        "strictly_improved": strictly_down,
        "fragments": fragments,
        "poses_after": poses_after,
        "relations": rel_rows,
        "overlaps": overlaps,
        "conflicts": conflicts,
    }
