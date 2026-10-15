"""CHAM TAY — hieu chuan nguoi cham bang NGUOI. Buoc 3-4 cua docs/plan-danh-gia-tong-the.md.

    uv run python ops/cham_tay.py           # bat dau / tiep tuc cham
    uv run python ops/cham_tay.py --do      # do tuong quan sau khi cham xong

VI SAO CAN. Toan bo cot "noi dung" cua evals/runner_tho.py hien la MODEL CHAM MODEL. Ta
neo no bang ca dao va van xuoi, nhung ca hai diem neo do cung do chinh model dinh vi.
Chua ai biet `ngon ngu 6,00` co tuong ung voi cam nhan cua nguoi doc khong.

Day la manh DUY NHAT cua bo danh gia ma may khong tu dung duoc.

--------------------------------------------------------------------------------
BA QUY TAC CUA PHEP NAY, va vi sao pha mot cai la hong ca phep
--------------------------------------------------------------------------------

1. GIAU DIEM MAY. Thay diem may truoc thi diem nguoi bi keo theo no, va ta do duoc
   "nguoi co dong y voi may khong" thay vi "may co dung khong". Hai cau hoi khac nhau.

2. TRON NEO, GIAU NHAN. Ca dao va van xuoi di lan vao giua, khong noi cai nao la cai
   nao. Biet truoc la ca dao thi diem bi keo theo ky vong — va ta mat luon cai moc.

3. NGAU NHIEN CO HAT GIONG. Thu tu hien bai co dinh theo hat giong, de cham dang do roi
   nghi va quay lai van ra dung thu tu do.

BA MUC, KHONG PHAI SAU. `nhip` thi may chi kiem duoc mot phan; `y nghia` va `cam xuc`
kho nhat quan khi cham tay. Ba muc o day la ba muc co khoang cach LON NHAT toi ca dao,
tuc ba muc dang tin cay hoa nhat.
"""

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

GOC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GOC / "src"))

SO_KET_QUA = GOC / "evals" / "tho" / "so_ket_qua.jsonl"
RA = GOC / "evals" / "tho" / "cham_tay.jsonl"
BAI_DA_SINH = GOC / "evals" / "tho" / "bai_da_sinh.jsonl"

#: Hat giong co dinh — xem quy tac 3.
HAT_GIONG = 20260915

#: Ba muc cham tay. Thang 0-10 het, ke ca `sang_tao` (may cham /5) — de nguoi khong
#: phai doi thang giua cac muc. Quy doi khi DO tuong quan, khong quy doi khi cham.
MUC: tuple[tuple[str, str], ...] = (
    ("ngon_ngu", "có chữ nào bị nhét vào CHỈ ĐỂ ép vần không? (0 = đầy chữ vô nghĩa)"),
    ("hinh_anh", "có hình ảnh thật, cụ thể, gợi được không? (0 = toàn sáo ngữ)"),
    ("sang_tao", "có gì mới không, hay chỉ lặp cái ai cũng viết được?"),
)

NEO_TREN: tuple[str, ...] = (
    "Công cha như núi Thái Sơn\nNghĩa mẹ như nước trong nguồn chảy ra\n"
    "Một lòng thờ mẹ kính cha\nCho tròn chữ hiếu mới là đạo con",
    "Anh đi anh nhớ quê nhà\nNhớ canh rau muống nhớ cà dầm tương\n"
    "Nhớ ai dãi nắng dầm sương\nNhớ ai tát nước bên đường hôm nao",
    "Trong đầm gì đẹp bằng sen\nLá xanh bông trắng lại chen nhị vàng\n"
    "Nhị vàng bông trắng lá xanh\nGần bùn mà chẳng hôi tanh mùi bùn",
)
NEO_DUOI: tuple[str, ...] = (
    "Hôm nay trời nắng đẹp lắm\nTôi đi ra chợ mua rau\n"
    "Rau hôm nay hơi đắt một chút\nNhưng mà vẫn phải mua thôi",
    "Hà Nội có nhiều đường phố\nMùa thu thì lá rụng nhiều\n"
    "Người ta hay đi chơi hồ\nTrời se lạnh vào buổi tối",
)


#: Mot ban ghi cham tay. Khai ro de mypy kiem duoc phep cong diem o `do_tuong_quan`.
BanGhi = dict[str, Any]


def _doc_jsonl(p: Path) -> list[BanGhi]:
    if not p.exists():
        return []
    return [json.loads(d) for d in p.read_text(encoding="utf-8").splitlines() if d.strip()]


def dung_bo_cham() -> list[BanGhi]:
    """30 bai cua bot (10 cao / 10 giua / 10 thap theo MAY) + 5 neo, tron lan."""
    bai = _doc_jsonl(BAI_DA_SINH)
    if len(bai) < 30:
        print(
            f"CHUA DU BAI: co {len(bai)}, can >= 30.\n\n"
            "  uv run python evals/runner_tho.py --luu-bai\n\n"
            "Lan chay danh gia phai duoc luu bai lai thi moi cham tay duoc.",
            file=sys.stderr,
        )
        return []

    co_diem = [b for b in bai if isinstance(b.get("may"), dict) and b["may"]]
    co_diem.sort(key=lambda b: sum(b["may"].values()), reverse=True)
    n = len(co_diem)
    giua = n // 2
    chon = co_diem[:10] + co_diem[giua - 5 : giua + 5] + co_diem[-10:]

    bo: list[BanGhi] = [
        {"id": f"bot-{i}", "loai": "bot", "tho": b["tho"], "may": b["may"]}
        for i, b in enumerate(chon)
    ]
    bo += [
        {"id": f"tren-{i}", "loai": "neo_tren", "tho": t, "may": None}
        for i, t in enumerate(NEO_TREN)
    ]
    bo += [
        {"id": f"duoi-{i}", "loai": "neo_duoi", "tho": t, "may": None}
        for i, t in enumerate(NEO_DUOI)
    ]

    random.Random(HAT_GIONG).shuffle(bo)
    return bo


def cham() -> int:
    bo = dung_bo_cham()
    if not bo:
        return 2

    xong = {str(x["id"]) for x in _doc_jsonl(RA)}
    con = [b for b in bo if str(b["id"]) not in xong]
    if not con:
        print(f"Đã chấm hết {len(bo)} bài.\n\n  uv run python ops/cham_tay.py --do")
        return 0

    print(f"Chấm tay — còn {len(con)}/{len(bo)} bài.  Ctrl+C để dừng, chạy lại sẽ tiếp.")
    print("Mỗi mục cho điểm 0-10. Gõ 'b' để bỏ qua một bài.\n")

    RA.parent.mkdir(parents=True, exist_ok=True)
    for i, b in enumerate(con, 1):
        print("=" * 66)
        print(f"[{i}/{len(con)}]")
        print("=" * 66)
        print(b["tho"])
        print()
        diem: dict[str, float] = {}
        bo_qua = False
        for ma, hoi in MUC:
            while True:
                try:
                    tra = input(f"  {ma:<10} 0-10  ({hoi})\n  > ").strip().lower()
                except EOFError:
                    # Chay khong co terminal (CI, pipe, cong cu tu dong). Bao ro thay vi
                    # nem traceback — va noi luon vi sao viec nay khong tu dong hoa duoc.
                    print(
                        "\n\nKHONG CO TERMINAL — cong cu nay cho NGUOI go diem.\n\n"
                        "    uv run python ops/cham_tay.py\n\n"
                        "Khong tu dong hoa duoc, va do la CHU DICH: ca phep hieu chuan "
                        "ton tai\nde thoat khoi viec model cham model.",
                        file=sys.stderr,
                    )
                    return 2
                except KeyboardInterrupt:
                    print("\n\nDung lai. Chay lai se tiep dung cho.")
                    return 0
                if tra == "b":
                    bo_qua = True
                    break
                try:
                    v = float(tra.replace(",", "."))
                except ValueError:
                    print("  -> nhập một số 0-10, hoặc 'b'")
                    continue
                if 0.0 <= v <= 10.0:
                    diem[ma] = v
                    break
                print("  -> phải trong 0-10")
            if bo_qua:
                break
        if bo_qua:
            print("  (bỏ qua)\n")
            continue
        with RA.open("a", encoding="utf-8", newline="\n") as f:
            f.write(
                json.dumps({"id": b["id"], "loai": b["loai"], "nguoi": diem}, ensure_ascii=False)
                + "\n"
            )
        print()
    print(f"Xong. Đã ghi vào {RA.relative_to(GOC)}\n\n  uv run python ops/cham_tay.py --do")
    return 0


def _spearman(a: list[float], b: list[float]) -> float:
    """Tuong quan hang Spearman. Tu viet de khong them phu thuoc."""

    def hang(xs: list[float]) -> list[float]:
        sap = sorted(range(len(xs)), key=lambda i: xs[i])
        r = [0.0] * len(xs)
        i = 0
        while i < len(sap):
            j = i
            while j + 1 < len(sap) and xs[sap[j + 1]] == xs[sap[i]]:
                j += 1
            tb = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[sap[k]] = tb
            i = j + 1
        return r

    ra, rb = hang(a), hang(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    tu = sum((x - ma) * (y - mb) for x, y in zip(ra, rb, strict=True))
    mau = (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5
    return tu / mau if mau else 0.0


def do_tuong_quan() -> int:
    nguoi = {str(x["id"]): x for x in _doc_jsonl(RA)}
    bo = {str(b["id"]): b for b in dung_bo_cham()}
    if not nguoi:
        print("CHUA CHAM GI. Chay: uv run python ops/cham_tay.py", file=sys.stderr)
        return 2

    print("=" * 70)
    print(f"TUONG QUAN NGUOI vs MAY — {len(nguoi)} bai da cham")
    print("=" * 70)

    cap = [(nguoi[i], bo[i]) for i in nguoi if i in bo and bo[i]["loai"] == "bot"]
    if len(cap) < 10:
        print(f"  chi {len(cap)} bai cua bot — can >= 10 de do tuong quan", file=sys.stderr)
    else:
        print(f"\n  {'muc':<12}{'Spearman':>10}{'n':>6}   ket luan")
        for ma, _ in MUC:
            # `sang_tao` may cham /5, nguoi cham /10 -> Spearman la tuong quan HANG nen
            # khong can quy doi thang.
            a = [float(x["nguoi"][ma]) for x, _ in cap]
            b = [float(y["may"][ma]) for _, y in cap]
            r = _spearman(a, b)
            if r >= 0.6:
                kl = "DUNG DUOC"
            elif r >= 0.3:
                kl = "chi de XEP HANG"
            else:
                kl = "KHONG DO DUNG THU"
            print(f"  {ma:<12}{r:>10.2f}{len(a):>6}   {kl}")

    print("\n  NEO — nguoi co tach duoc ba nhom khong:")
    for loai, ten in (("neo_tren", "ca dao"), ("bot", "bot"), ("neo_duoi", "van xuoi")):
        d = [
            sum(float(v) for v in x["nguoi"].values())
            for i, x in nguoi.items()
            if i in bo and bo[i]["loai"] == loai
        ]
        if d:
            print(f"    {ten:<10} {sum(d) / len(d):6.2f}/30   (n={len(d)})")
    print("\n  Neu nguoi KHONG tach duoc ba nhom thi chinh bai toan dang mo ho,")
    print("  chu khong phai nguoi cham sai.")
    return 0


def main() -> int:
    for luong in (sys.stdout, sys.stderr):
        if hasattr(luong, "reconfigure"):
            luong.reconfigure(encoding="utf-8", errors="replace")
    bo = argparse.ArgumentParser(description="Cham tay de hieu chuan nguoi cham")
    bo.add_argument("--do", action="store_true", help="do tuong quan sau khi cham xong")
    bo.add_argument("--prepare-round", type=Path, help="thu muc moi cho vong cham an nguon")
    bo.add_argument("--round-id", help="ID bat buoc khi tao round; khong tu gan ngay cu")
    bo.add_argument("--candidate-pool", type=Path, help="JSONL curated/proposed candidate input")
    bo.add_argument("--require-balanced", action="store_true", help="6 categories x10, 3 forms x10")
    bo.add_argument("--review-round", type=Path)
    bo.add_argument("--reviewer-one", type=Path)
    bo.add_argument("--reviewer-two", type=Path)
    bo.add_argument("--machine-repeat", type=Path, help="JSONL id/scores cua luot judge lap")
    bo.add_argument(
        "--machine-first", type=Path, help="JSONL first judge run; leaves originals intact"
    )
    bo.add_argument("--machine-config-sha256", help="Hash of locked judge/config/scale")
    bo.add_argument("--attest-same-judge-config", action="store_true")
    bo.add_argument("--attest-independent-human-reviewers", action="store_true")
    bo.add_argument("--report-output", type=Path, help="New content-free report; refuses overwrite")
    bo.add_argument(
        "--score-round", type=Path, help="cham sau chieu tu blind.json, khong xem diem may"
    )
    bo.add_argument("--reviewer-id", help="ma nguoi cham; chi luu SHA-256")
    bo.add_argument(
        "--reviewer-kind", choices=("human", "agent"), help="Explicit identity declaration"
    )
    bo.add_argument(
        "--judgments-output", type=Path, help="JSONL rieng cua nguoi cham; co the tiep tuc"
    )
    args = bo.parse_args()
    if args.prepare_round or args.review_round or args.score_round:
        sys.path.insert(0, str(GOC))
        from evals.human_review import (
            CANDIDATE_CATEGORIES,
            DIMENSIONS,
            SUPPORTED_FORMS,
            calibration_report,
            prepare_round,
            reviewer_identity,
            validate_judgments,
        )

        try:
            if args.score_round:
                if not args.reviewer_id or not args.judgments_output:
                    raise ValueError("can --reviewer-id va --judgments-output rieng")
                if args.reviewer_kind != "human":
                    raise ValueError(
                        "--reviewer-kind human required; agents are not human reviewers"
                    )
                import hashlib

                reviewer_id = hashlib.sha256(args.reviewer_id.encode()).hexdigest()
                blind = json.loads((args.score_round / "blind.json").read_text(encoding="utf-8"))
                expected = {str(row["id"]) for row in blind}
                if len(expected) != len(blind) or len(blind) < 60:
                    raise ValueError("round needs 60 distinct poems")
                if any(
                    hashlib.sha256(row["tho"].strip().encode()).hexdigest() != row["id"]
                    for row in blind
                ):
                    raise ValueError("blinded poem changed")
                rubric_bytes = (args.score_round / "rubric.json").read_bytes()
                rubric = json.loads(rubric_bytes)
                anchors = rubric.get("anchors")
                if (
                    not isinstance(anchors, dict)
                    or set(anchors) != set(DIMENSIONS)
                    or any(
                        not isinstance(values, list)
                        or len(values) != 5
                        or any(not isinstance(value, str) or not value for value in values)
                        for values in anchors.values()
                    )
                ):
                    raise ValueError("round rubric requires five anchors for six dimensions")
                public_hashes = {
                    "blind_sha256": hashlib.sha256(
                        (args.score_round / "blind.json").read_bytes()
                    ).hexdigest(),
                    "rubric_sha256": hashlib.sha256(rubric_bytes).hexdigest(),
                }
                previous = _doc_jsonl(args.judgments_output)
                if previous:
                    reviewer_identity(previous)
                if any(row.get("reviewer_id") != reviewer_id for row in previous):
                    raise ValueError("output belongs to another reviewer")
                if any(
                    row.get(name) != value
                    for row in previous
                    for name, value in public_hashes.items()
                ):
                    raise ValueError("output belongs to a different blind round/rubric snapshot")
                completed = {str(row["id"]) for row in previous}
                validate_judgments(previous, completed)
                if not completed <= expected:
                    raise ValueError("output contains IDs outside this round")
                print("Rubric 1-5: các ví dụ chỉ minh hoạ; chấm toàn bài, không đoán nguồn.")
                for dimension in DIMENSIONS:
                    print(f"\n{dimension}:")
                    for score, anchor in enumerate(anchors[dimension], 1):
                        print(f"  {score}: {anchor}")
                for row in blind:
                    if row["id"] in completed:
                        continue
                    print(f"\n{len(completed) + 1}/{len(blind)}\n{row['tho']}\n")
                    scores: dict[str, float] = {}
                    for dimension in DIMENSIONS:
                        while True:
                            answer = input(f"{dimension} (1-5, q de dung): ").strip()
                            if answer.casefold() == "q":
                                return 0
                            try:
                                value = float(answer)
                                validate_judgments(
                                    [{"id": row["id"], "scores": dict.fromkeys(DIMENSIONS, value)}],
                                    {row["id"]},
                                )
                            except ValueError:
                                print("Can diem huu han 1-5.")
                                continue
                            scores[dimension] = value
                            break
                    record = {
                        "id": row["id"],
                        "scores": scores,
                        "reviewer_id": reviewer_id,
                        "reviewer_kind": "human",
                        **public_hashes,
                    }
                    # Append only COMPLETE judgments; interrupted poems are retried.
                    with args.judgments_output.open("a", encoding="utf-8") as output:
                        output.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
                    completed.add(row["id"])
                print(
                    f"Completed {len(completed)} judgments declared by one human; "
                    "independence pending"
                )
                return 0
            if args.prepare_round:
                if not args.round_id:
                    raise ValueError("--prepare-round requires --round-id")
                count = prepare_round(
                    args.candidate_pool or BAI_DA_SINH,
                    args.prepare_round,
                    args.round_id,
                    category_minimums=dict.fromkeys(CANDIDATE_CATEGORIES, 10)
                    if args.require_balanced
                    else None,
                    form_minimums=dict.fromkeys(SUPPORTED_FORMS, 10)
                    if args.require_balanced
                    else None,
                )
                print(f"Prepared {count} poems")
                return 0
            if not args.reviewer_one or not args.reviewer_two:
                raise ValueError("can hai file cham doc lap")
            if args.reviewer_one.resolve() == args.reviewer_two.resolve():
                raise ValueError("hai nguoi cham phai co file rieng")
            blind = json.loads((args.review_round / "blind.json").read_text(encoding="utf-8"))
            expected = {str(row["id"]) for row in blind}
            private = json.loads((args.review_round / "private.json").read_text(encoding="utf-8"))
            import hashlib

            records = private["records"]
            if len(expected) != len(blind) or set(records) != expected:
                raise ValueError("round ID mismatch or duplicate")
            for row in blind:
                if hashlib.sha256(row["tho"].strip().encode()).hexdigest() != row["id"]:
                    raise ValueError("blinded poem changed")
                if row["tho"] != records[row["id"]]["tho"]:
                    raise ValueError("private/blind poem mismatch")
            first_rows, second_rows = _doc_jsonl(args.reviewer_one), _doc_jsonl(args.reviewer_two)
            public_hashes = {
                "blind_sha256": hashlib.sha256(
                    (args.review_round / "blind.json").read_bytes()
                ).hexdigest(),
                "rubric_sha256": hashlib.sha256(
                    (args.review_round / "rubric.json").read_bytes()
                ).hexdigest(),
            }
            if any(
                row.get(name) != value
                for row in [*first_rows, *second_rows]
                for name, value in public_hashes.items()
            ):
                raise ValueError("review files do not match blind round/rubric snapshot")
            first_identity, second_identity = (
                reviewer_identity(first_rows),
                reviewer_identity(second_rows),
            )
            if first_identity == second_identity:
                raise ValueError("two different human reviewer identities are required")
            first = validate_judgments(first_rows, expected)
            second = validate_judgments(second_rows, expected)
            machine = {key: records[key].get("may") for key in expected}
            machine_rows = []
            if args.machine_first:
                machine_rows = _doc_jsonl(args.machine_first)
                machine = {str(row["id"]): row.get("scores") for row in machine_rows}
                if len(machine_rows) != len(machine):
                    raise ValueError("duplicate first-run IDs")
            repeated = None
            runs = []
            if args.machine_repeat:
                runs = _doc_jsonl(args.machine_repeat)
                repeated = {str(row["id"]): row.get("scores") for row in runs}
                if len(runs) != len(repeated):
                    raise ValueError("duplicate repeat IDs")
            config_verified = bool(
                args.machine_config_sha256
                and len(args.machine_config_sha256) == 64
                and all(character in "0123456789abcdef" for character in args.machine_config_sha256)
                and machine_rows
                and runs
                and all(
                    row.get("judge_config_sha256") == args.machine_config_sha256
                    for row in [*machine_rows, *runs]
                )
            )
            if args.attest_same_judge_config and not config_verified:
                raise ValueError(
                    "same-config attestation requires matching first/repeat config metadata"
                )
            report = calibration_report(
                first,
                second,
                machine,
                repeated,
                same_judge_config_attested=args.attest_same_judge_config and config_verified,
                categories={
                    key: str(records[key].get("category", "unclassified")) for key in expected
                },
            )
            report.update(round_id=private["round_id"], source_sha256=private["source_sha256"])
            report["review_files_sha256"] = [
                hashlib.sha256(path.read_bytes()).hexdigest()
                for path in (args.reviewer_one, args.reviewer_two)
            ]
            report.update(
                human_review_declared=True,
                independent_human_reviewers_attested=args.attest_independent_human_reviewers,
                identity_or_independence_verified_by_tool=False,
                machine_config_verified=config_verified,
                e7_accepted=False,
                **public_hashes,
            )
            rendered = json.dumps(report, allow_nan=False)
            if args.report_output:
                with args.report_output.open("x", encoding="utf-8") as output:
                    output.write(rendered + "\n")
            print(rendered)
            return 0
        except (ValueError, OSError, KeyError, TypeError) as error:
            print(str(error), file=sys.stderr)
            return 2
    return do_tuong_quan() if args.do else cham()


if __name__ == "__main__":
    sys.exit(main())
