"""p95 toan duong ong. Muc tieu < 5s.

TODO(giai-doan-8). So do that ngay 06/09/2026: cau thuong 3,2-4,3s (dat), cau CO
TOOL 12-15s (truot xa, va sat gioi han 15s cua Zalo/Messenger). Do la con so phai
cai thien, khong phai con so de bao cao.
"""


def percentile(values: list[float], p: float) -> float:
    """p95 = percentile(xs, 0.95). Danh sach rong -> 0."""
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(int(p * len(ordered)), len(ordered) - 1)
    return ordered[index]
