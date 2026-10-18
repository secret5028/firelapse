"""소방 시트(1:1 mm, 건축 외부참조 포함) ↔ 건축 평면 DWG 정렬: 선 래스터 템플릿 매칭(이동), 2단계(100→20mm)."""
import numpy as np, cv2
def raster(segs, lo, hi, res, th=1):
    W_ = int((hi[0] - lo[0]) / res) + 1; H_ = int((hi[1] - lo[1]) / res) + 1
    img = np.zeros((H_, W_), np.uint8)
    for x0, y0, x1, y1 in segs:
        cv2.line(img, (int((x0 - lo[0]) / res), int((hi[1] - y0) / res)), (int((x1 - lo[0]) / res), int((hi[1] - y1) / res)), 255, th)
    return img
def align(arch, fire, res=(100, 20)):
    """arch, fire: (N,4) 선분 mm. 반환 (dx,dy, 점수): fire = arch + (dx,dy)"""
    a = np.asarray(arch, float); f = np.asarray(fire, float)
    alo = np.percentile(a[:, [0, 1]], 0.5, 0); ahi = np.percentile(a[:, [0, 1]], 99.5, 0)
    flo = f[:, [0, 1]].min(0); fhi = f[:, [0, 1]].max(0)
    r = res[0]
    A = cv2.dilate(raster(a, alo, ahi, r), np.ones((3, 3), np.uint8)).astype(np.float32)
    F = cv2.dilate(raster(f, flo, fhi, r), np.ones((3, 3), np.uint8)).astype(np.float32)
    if A.shape[0] > F.shape[0] or A.shape[1] > F.shape[1]:
        pad = ((0, max(0, A.shape[0] - F.shape[0]) + 2), (0, max(0, A.shape[1] - F.shape[1]) + 2)); F = np.pad(F, pad)
    m = cv2.matchTemplate(F, A, cv2.TM_CCORR_NORMED); _, sc, _, (u, v) = cv2.minMaxLoc(m)
    dx = flo[0] + u * r - alo[0]; dy = (fhi[1] - v * r) - ahi[1]
    # 정밀: 20mm, ±300mm 범위
    r2 = res[1]; pad = 400
    A2 = cv2.dilate(raster(a, alo, ahi, r2), np.ones((3, 3), np.uint8)).astype(np.float32)
    lo2 = alo + (dx - pad, dy - pad); hi2 = ahi + (dx + pad, dy + pad)
    sel = f[(f[:, 0] > lo2[0] - 1000) & (f[:, 0] < hi2[0] + 1000) & (f[:, 1] > lo2[1] - 1000) & (f[:, 1] < hi2[1] + 1000)]
    F2 = cv2.dilate(raster(sel, lo2, hi2, r2), np.ones((3, 3), np.uint8)).astype(np.float32)
    m2 = cv2.matchTemplate(F2, A2, cv2.TM_CCORR_NORMED); _, sc2, _, (u2, v2) = cv2.minMaxLoc(m2)
    dx2 = lo2[0] + u2 * r2 - alo[0]; dy2 = (hi2[1] - v2 * r2) - ahi[1]
    return dx2, dy2, sc2, sc


def align_blocks(A, F, tol=50.0):
    """같은 이름 블록 삽입점 집합으로 이동량 추정(기둥 번호 등 건축 외부참조 블록). A,F: {base_name: [(x,y)...]} (mm)
    반환 (dx,dy, 일치 개수, 평균 오차) — 일치 4개 미만이면 None"""
    best = None
    keys = [k for k in A if k in F]
    PA = [(k, np.array(A[k])) for k in keys]; PF = {k: np.array(F[k]) for k in keys}
    for k, a_ in PA:
        for a in a_[:6]:
            for f in PF[k][:12]:
                d = f - a; n = 0; err = []
                for k2, a2 in PA:
                    m = np.min(np.hypot(*(PF[k2][None, :, :] - (a2 + d)[:, None, :]).transpose(2, 0, 1)), axis=1)
                    n += int((m < tol).sum()); err += list(m[m < tol])
                if best is None or n > best[2] or (n == best[2] and np.mean(err) < best[3]):
                    best = (float(d[0]), float(d[1]), n, float(np.mean(err)) if err else 99.0)
    return best if best and best[2] >= 4 else None
