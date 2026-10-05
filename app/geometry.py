"""二维刚体配准与轮廓几何校验（毫米制）。

仅使用平移 + 旋转（不允许缩放/镜像）将陶片局部坐标系下的闭合轮廓
放置到世界坐标系。对应标记点用最小二乘拟合最优刚体变换。
"""
from __future__ import annotations

import math

from shapely.geometry import LineString, Point, Polygon
from shapely.validation import explain_validity

MAX_ERROR_MM = 1.0        # 同组对应点误差上限（毫米）
OVERLAP_AREA_TOL = 1e-6   # 轮廓内部重叠面积容差（mm²）
MARKER_DIST_TOL = 1e-6    # 标记重合判定距离（mm）
EDGE_TOL_MM = 1e-6        # 边缘标记到轮廓边界的距离容差（mm）
CLOSE_TOL = 1e-9          # 闭合重复点判定容差


class GeometryError(ValueError):
    """几何校验失败（轮廓自交、标记重合等）。"""


def dist(p, q) -> float:
    return math.hypot(p[0] - q[0], p[1] - q[1])


# ---------------------------------------------------------------- 轮廓

def normalize_contour(points) -> list[tuple[float, float]]:
    """去除闭合重复点与连续重复点，返回浮点坐标列表。"""
    pts = [(float(p[0]), float(p[1])) for p in points]
    while len(pts) > 1 and dist(pts[0], pts[-1]) < CLOSE_TOL:
        pts.pop()
    cleaned: list[tuple[float, float]] = []
    for p in pts:
        if not cleaned or dist(p, cleaned[-1]) > CLOSE_TOL:
            cleaned.append(p)
    return cleaned


def validate_contour(points) -> list[tuple[float, float]]:
    """校验闭合轮廓：至少 3 个有效顶点、面积非零、无自交。"""
    if not isinstance(points, (list, tuple)) or len(points) < 3:
        raise GeometryError("闭合轮廓至少需要 3 个顶点")
    pts = normalize_contour(points)
    if len(pts) < 3:
        raise GeometryError("轮廓有效顶点不足 3 个（存在重复点）")
    poly = Polygon(pts)
    if not poly.is_valid:
        reason = explain_validity(poly)
        if poly.area <= CLOSE_TOL:
            raise GeometryError(f"轮廓无效（自交或顶点共线面积为零）：{reason}")
        raise GeometryError(f"轮廓自交：{reason}")
    return pts


# ---------------------------------------------------------------- 标记

def validate_markers(markers_a, markers_b):
    """校验对应标记：数量一致、每片至少 2 处、同片标记不重合。"""
    if len(markers_a) != len(markers_b):
        raise GeometryError(
            f"两片陶片的标记数量必须一致（当前 {len(markers_a)} 对 {len(markers_b)}）")
    if len(markers_a) < 2:
        raise GeometryError("每片陶片至少需要 2 处对应边缘标记")
    out = []
    for label, ms in (("甲", markers_a), ("乙", markers_b)):
        pts = [(float(m[0]), float(m[1])) for m in ms]
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                if dist(pts[i], pts[j]) < MARKER_DIST_TOL:
                    raise GeometryError(
                        f"标记重合：{label}片第 {i + 1} 处与第 {j + 1} 处标记位置相同")
        out.append(pts)
    return out[0], out[1]


def validate_side_markers(markers, contour) -> list[tuple[float, float]]:
    """校验单侧修订标记（轮廓修订时使用）：

    至少 2 处、同片标记不重合、每个标记位于给定闭合轮廓的边缘
    （到边界距离 ≤ EDGE_TOL_MM，顶点与边上点均可）。
    """
    pts = [(float(m[0]), float(m[1])) for m in markers]
    if len(pts) < 2:
        raise GeometryError("每片陶片至少需要 2 处对应边缘标记")
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            if dist(pts[i], pts[j]) < MARKER_DIST_TOL:
                raise GeometryError(
                    f"标记重合：本片第 {i + 1} 处与第 {j + 1} 处标记位置相同")
    boundary = LineString(list(contour) + [contour[0]])
    off = [i + 1 for i, p in enumerate(pts)
           if boundary.distance(Point(p)) > EDGE_TOL_MM]
    if off:
        which = "、".join(str(i) for i in off)
        raise GeometryError(
            f"新标记必须位于修订后的轮廓边缘：第 {which} 处标记不在轮廓边缘上")
    return pts


# ---------------------------------------------------------------- 刚体变换

def fit_rigid(src, dst) -> tuple[float, float, float]:
    """最小二乘拟合旋转+平移 T，使 T(src[i]) ≈ dst[i]。

    返回 (tx, ty, theta)：world = R(theta) · p + (tx, ty)。
    要求 src 至少含 2 个不重合的点（调用前已由 validate_markers 保证）。
    """
    n = len(src)
    csx = sum(p[0] for p in src) / n
    csy = sum(p[1] for p in src) / n
    cdx = sum(p[0] for p in dst) / n
    cdy = sum(p[1] for p in dst) / n
    a = b = 0.0
    for (sx, sy), (dx, dy) in zip(src, dst):
        px, py = sx - csx, sy - csy
        qx, qy = dx - cdx, dy - cdy
        a += px * qx + py * qy
        b += px * qy - py * qx
    theta = math.atan2(b, a)
    c, s = math.cos(theta), math.sin(theta)
    tx = cdx - (c * csx - s * csy)
    ty = cdy - (s * csx + c * csy)
    return (tx, ty, theta)


def apply_pose(point, pose) -> tuple[float, float]:
    """将局部坐标点经位姿 (x, y, theta) 变换到世界坐标。"""
    x, y, th = pose
    c, s = math.cos(th), math.sin(th)
    return (c * point[0] - s * point[1] + x, s * point[0] + c * point[1] + y)


def compose_pose(outer, inner) -> tuple[float, float, float]:
    """先应用 inner 位姿再应用 outer 变换（整体移动一组时使用）。"""
    tx, ty, phi = outer
    x, y, th = inner
    c, s = math.cos(phi), math.sin(phi)
    return (c * x - s * y + tx, s * x + c * y + ty, th + phi)


def contour_world(contour, pose) -> list[tuple[float, float]]:
    return [apply_pose(p, pose) for p in contour]


def pair_errors(markers_a, markers_b, pose_a, pose_b) -> list[float]:
    """每对对应标记在世界坐标下的距离误差（毫米）。"""
    errs = []
    for ma, mb in zip(markers_a, markers_b):
        errs.append(dist(apply_pose(ma, pose_a), apply_pose(mb, pose_b)))
    return errs


# ---------------------------------------------------------------- 碰撞

def find_overlaps(placed) -> list[tuple]:
    """检查世界坐标轮廓两两是否内部重叠（允许共边/共点，不允许面积重叠）。

    placed: [(key, name, world_contour)]，返回
    [(key1, key2, name1, name2, area_mm2)]。
    """
    polys = [(key, name, Polygon(contour)) for key, name, contour in placed]
    overlaps = []
    for i in range(len(polys)):
        for j in range(i + 1, len(polys)):
            area = polys[i][2].intersection(polys[j][2]).area
            if area > OVERLAP_AREA_TOL:
                overlaps.append((polys[i][0], polys[j][0],
                                 polys[i][1], polys[j][1], area))
    return overlaps


# ---------------------------------------------------------------- 整体校准（最小二乘）

def _solve_linear(A, b) -> list[float]:
    """高斯-若尔当消元（列主元）解稠密线性方程组 A x = b（小规模，k≤数百）。"""
    n = len(A)
    M = [list(A[i]) + [b[i]] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[pivot][col]) < 1e-14:
            continue                    # 理论上不会出现：连通组约束满秩
        if pivot != col:
            M[col], M[pivot] = M[pivot], M[col]
        q = M[col][col]
        for j in range(col, n + 1):
            M[col][j] /= q
        for r in range(n):
            if r == col:
                continue
            f = M[r][col]
            if f:
                for j in range(col, n + 1):
                    M[r][j] -= f * M[col][j]
    return [M[i][n] for i in range(n)]


def poses_sse(poses: dict, corrs: list[tuple]) -> float:
    """全部对应点在世界坐标下的误差平方和 Σ‖T_u(p)−T_v(q)‖²（mm²）。"""
    sse = 0.0
    for u, p, v, q in corrs:
        wu = apply_pose(p, poses[u])
        wv = apply_pose(q, poses[v])
        dx, dy = wu[0] - wv[0], wu[1] - wv[1]
        sse += dx * dx + dy * dy
    return sse


def calibrate_poses(poses: dict, corrs: list[tuple], fixed_id,
                    max_iter: int = 50, tol: float = 1e-12):
    """以 fixed_id 为锚点（位姿保持不变），对其余碎片仅以平移+旋转做联合
    最小二乘，共同降低全部对应点的误差平方和::

        E = Σ ‖R(θ_u)·p + t_u − (R(θ_v)·q + t_v)‖²

    - poses: {fid: (x, y, theta)}，锚点以外为待调碎片（初值取当前位姿，
      从当前位姿附近寻优，不会发生翻转/缩放）；
    - corrs: [(uid, (px, py), vid, (qx, qy))]，即各有效关系展开的成对标记；
    - Levenberg–Marquardt（解析雅可比，仅在误差下降时接受步长）。

    返回 (new_poses, sse_before, sse_after, iterations)；new_poses 含组内
    全部碎片，锚点位姿原样保留。
    """
    others = sorted(fid for fid in poses if fid != fixed_id)
    base = {fid: 3 * i for i, fid in enumerate(others)}

    x0: list[float] = []
    for fid in others:
        x0.extend(poses[fid])

    def unpack(par):
        out = {fixed_id: poses[fixed_id]}
        for i, fid in enumerate(others):
            out[fid] = (par[3 * i], par[3 * i + 1], par[3 * i + 2])
        return out

    def cost(par):
        return poses_sse(unpack(par), corrs)

    sse_before = cost(x0)
    x = x0
    lam = 1e-3
    iters = 0
    for it in range(1, max_iter + 1):
        iters = it
        cur = unpack(x)
        k = len(x)
        H = [[0.0] * k for _ in range(k)]
        g = [0.0] * k
        for u, p, v, q in corrs:
            wu = apply_pose(p, cur[u])
            wv = apply_pose(q, cur[v])
            ex, ey = wu[0] - wv[0], wu[1] - wv[1]
            # 残差 e = T_u(p) − T_v(q) 对各片 (tx, ty, theta) 的雅可比列
            entries = []
            cu, su = math.cos(cur[u][2]), math.sin(cur[u][2])
            if u != fixed_id:
                entries.append((base[u],
                                (1.0, 0.0), (0.0, 1.0),
                                (-su * p[0] - cu * p[1],
                                 cu * p[0] - su * p[1])))
            cv, sv = math.cos(cur[v][2]), math.sin(cur[v][2])
            if v != fixed_id:
                entries.append((base[v],
                                (-1.0, 0.0), (0.0, -1.0),
                                (sv * q[0] + cv * q[1],
                                 -cv * q[0] + sv * q[1])))
            for bi, j0, j1, j2 in entries:
                for oi, jo in enumerate((j0, j1, j2)):
                    g[bi + oi] += jo[0] * ex + jo[1] * ey
                    for bj, k0, k1, k2 in entries:
                        for oj, jn in enumerate((k0, k1, k2)):
                            H[bi + oi][bj + oj] += jo[0] * jn[0] + jo[1] * jn[1]
        Hd = [row[:] for row in H]
        for i in range(k):
            Hd[i][i] += lam * (H[i][i] if H[i][i] > 1e-18 else 1e-18)
        delta = _solve_linear(Hd, [-gi for gi in g])
        x_new = [x[i] + delta[i] for i in range(k)]
        cur_sse = cost(x)
        sse_new = cost(x_new)
        if sse_new < cur_sse:
            improved = cur_sse - sse_new
            x = x_new
            if improved <= tol * max(1.0, sse_new):
                break
            lam = max(lam * 0.5, 1e-12)
        else:
            lam *= 5.0
            if lam > 1e12:
                break
    return unpack(x), sse_before, cost(x), iters
