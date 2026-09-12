"""Cong cu `search_knowledge_base` — tra cuu tai lieu noi bo.

Di qua CONG CU chu khong pre-fetch o mot stage rieng: model tu quyet dinh khi nao
can tra tai lieu. Phan loai cung ("cau nay co ve hoi ve quy dinh") vua cung nhac vua
sai o dung nhung ca kho — con model thi doc ca doan hoi thoai truoc do.

Khong khai trong specs() khi CSDL chua co chunk nao. Cung luat voi web_search khi
thieu khoa: cho model thay mot cong cu roi de no tra ve rong lien tuc la day no
bia ra noi dung tai lieu.
"""

from typing import Any

from agents.domain.knowledge import RetrievedChunk
from agents.ports.llm import CallContext
from agents.ports.tool import ToolDefinition, ToolRequirements
from config import get_settings
from infra.db import fetch
from infra.logger import get_logger

_log = get_logger()

#: So chunk lay ra sau rerank. 3-5 la khoang plan chot: it va DUNG, khong nhieu.
_DEFAULT_K = 5

KNOWLEDGE_SEARCH_DEFINITION = ToolDefinition(
    name="search_knowledge_base",
    # CAU HOI NGUOC — sua 10/09/2026, sau khi do dau-cuoi tren bot that.
    #
    # Ban truoc dat menh lenh "goi cong cu TRUOC khi tra loi" o GIUA doan, va noi
    # dieu kien theo SU TU TIN ("ke ca cau ban nghi minh da biet dap an"). Do duoc:
    # voi cau hoi hoi NGUOC tu dac diem ra ten, model phan lon khong goi cong cu lan
    # nao ma tra loi thang tu tri nho, khong nguon.
    #
    #     cau TRA CUU      ("Ga ham bi do can nguyen lieu gi")   4/4 co goi
    #     cau GIAO TAP HOP ("Mon nao co pho mai va mi ong")       1/4 co goi
    #
    # Ba thay doi, do rieng tung cai:
    #   1. Menh lenh len CAU DAU, va bo dieu kien theo su tu tin — model luon tu tin
    #      voi loai cau nay, nen dieu kien do tu vo hieu dung luc can nhat.
    #   2. Goi ten CAM BAY thay vi ta no: "hoi tu dac diem ra ten".
    #   3. Mot VI DU cu the. Do tren chinh du an nay cho thay vi du day manh hon luat.
    #      Vi du CO Y chon mot cap nguyen lieu KHONG nam trong bo do (dau phu + ca
    #      chua): lay dung cau dang do lam vi du la day vet, va con so sau do vo nghia.
    #
    # Ket qua: giao tap hop 1/4 -> 4/4 co goi cong cu, va ca 4 deu lay dung chunk dap
    # an. Nhom tra cuu KHONG tut (3-4/4, dao dong san co). Rieng viec THEM luat cau
    # hoi nguoc ma van de menh lenh o giua chi duoc 2/4 — thu tu cau la mot nua tac
    # dung, khong phai gia vi.
    #
    # Doan nay dai them ~400 ky tu. Do la mo ta cong cu, KHONG nam trong
    # TOKEN_BUDGET["system"] va khong dinh test tran do dai — nhung no van di theo moi
    # request, nen dung coi cho nay la mien phi vo han.
    description=(
        "Tra cứu kho tài liệu mà tổ chức này đã nạp vào hệ thống. "
        "GỌI CÔNG CỤ NÀY TRƯỚC KHI TRẢ LỜI bất cứ câu hỏi có dữ kiện nào. Không có ngoại "
        "lệ vì câu hỏi trông dễ, vì bạn thấy nó giống kiến thức phổ thông, hay vì bạn đã "
        "có sẵn đáp án trong đầu. "
        "Kho có thể chứa BẤT KỲ loại tài liệu nào họ quan tâm: quy định, quy trình, chính "
        "sách, sổ tay, cẩm nang chuyên môn, sách công thức nấu ăn, hướng dẫn kỹ thuật. "
        "BẠN KHÔNG BIẾT TRONG KHO CÓ GÌ CHO TỚI KHI TRA. "
        "Cạm bẫy hay gặp nhất là câu hỏi NGƯỢC — hỏi từ đặc điểm ra tên: \"món nào có X và "
        "Y\", \"tài liệu nào nói về Z\", \"cái nào dùng W\". Ví dụ với \"Món nào có đậu phụ "
        "và cà chua?\": kể ra vài món bạn biết sẵn là trả lời về THẾ GIỚI, trong khi người "
        "dùng đang hỏi trong KHO CỦA HỌ có gì. Từng cái tên bạn kể có thể đúng mà cả câu "
        "trả lời vẫn sai, và nó sẽ không có nguồn. "
        "Cạm bẫy thứ hai, cùng một gốc: câu hỏi về MỘT CON SỐ (\"luộc bao lâu\", \"mấy "
        "độ\", \"bao nhiêu gram\") hay MỘT CÁCH LÀM (\"làm sao để...\", \"xử lý thế nào\"). "
        "Ví dụ với \"Ướp thịt bao lâu cho ngấm?\": loại này trông y hệt kiến thức phổ "
        "thông nên bạn sẽ thấy mình biết thừa — nhưng con số trong tài liệu CỦA HỌ mới "
        "là con số đúng, và nó thường khác con số chung. Vẫn phải tra. "
        "Trả lời từ trí nhớ trong khi tài liệu của họ có sẵn câu trả lời là bỏ phí đúng "
        "thứ họ đã nạp vào. "
        "Không tìm thấy thì công cụ sẽ nói rõ bước tiếp theo. "
        "Riêng tin tức, giá cả, sự kiện đang diễn ra thì dùng thẳng web_search."
    ),
    parameters={
        "type": "object",
        "properties": {
            # LUAT "VIET TRUY VAN TIENG ANH" PHU THUOC CORPUS, KHONG PHAI CHAN LY.
            #
            # Kho hien tai (10/09/2026): mot sach thuan Anh + mot sach song ngu Viet-Anh
            # -> tieng Anh la mau so chung, hoi tieng Anh van tim duoc `khoai so`.
            #
            # Do that tren 6 cau giao tap hop, cung mot bo cau hoi, chi doi ngon ngu
            # truy van:  tieng Viet 2/6  ·  tieng Anh 5/6  ·  tron ca hai 4/6.
            #
            # Corpus that cua mot tro ly noi bo Viet Nam nhieu kha nang la so tay, quy
            # dinh, quy trinh BANG TIENG VIET. Luc do luat nay DAO NGUOC: truy van tieng
            # Anh se khong voi toi tai lieu tieng Viet, va ca BM25 lan vector deu te di.
            #
            # NEN KHI NAP TAI LIEU TIENG VIET VAO: do lai ba bien the tren corpus moi
            # truoc khi tin dong mo ta duoi day. Neu kho thanh da ngon ngu that (co ca
            # Viet thuan lan Anh thuan) thi moi lam "bung hai truy van song song roi hop
            # nhat" — fusion.reciprocal_rank_fusion da nhan list[list[int]] nen them bang
            # xep hang thu ba la chuyen nho. Hom nay chua lam: hop VI u EN do duoc 5/6,
            # DUNG BANG tieng Anh thuan, tuc no khong mua them gi ma ton them mot lan
            # embed va hai truy van CSDL. Xem docs/plan-truy-hoi-xuyen-ngon-ngu.md muc 8.
            #
            # LUAT "TRUY VAN NGAN" — them 10/09/2026, do duoc trong mot phien hai luot.
            #
            # Model co xu huong nhet ca menh lenh vao truy van. Cung mot cau hoi, cung
            # mot kho, chi khac do dai truy van:
            #
            #   "Which dishes contain cheese and pasta?"                       d=0,5619
            #   "... ? Provide common dish names ..., list up to 10."          d=0,6223
            #   "... ? List common dishes that combine cheese and pasta."      d=0,6336
            #
            # Con so cuoi VUOT ca RAG_MAX_DISTANCE=0,63, tuc lan tim tra ve RONG va bot
            # quay sang web roi tra loi tu kien thuc chung. Chu thua trong truy van
            # khong bi bo qua — chung duoc embed y nhu moi chu khac.
            #
            # DA THU LUAT "GIU DUNG MUC CU THE" — VA DA HOAN LAI (10/09/2026).
            #
            # Ly do thu: cau "Mon nao dung pho mai va mi ong" duoc model dich thanh
            # "dishes that use cheese and pasta". `pasta` rong hon `macaroni` mot bac,
            # va chunk `Andrew's Macaroni` rot khoi top 5. Nen da them mot cau bao
            # "giu dung muc cu the, dung khai quat len mot bac".
            #
            # Do ra thi TE HAN HAN: 4/6 -> 2/6. Model khong sieu chinh xac hon; no bat
            # dau CHEN NGUYEN VAN TIENG VIET vao truy van de khoi mat do cu the:
            #
            #     dishes that use cheese and pasta "pho mai" "mi ong"
            #     dishes that include bacon and scallions "thit xong khoi" "hanh la"
            #
            # Tuc dung cai chuoi lai ma muc 4 do duoc la kem hon tieng Anh thuan (4/6
            # so voi 5/6) — mot cau luat keo model sang thang cai bay ma mot cau luat
            # khac ngay ben canh dang cam. Hai luat ve cung mot chuoi thi luat sau de
            # de bep luat truoc, du no khong noi gi ve ngon ngu.
            #
            # De nguyen. Cau "pho mai + mi ong" van truot vi ly do khac, va cho no la
            # tang truy hoi chu khong phai dong mo ta nay.
            "query": {
                "type": "string",
                "description": (
                    "Truy vấn tìm kiếm, VIẾT BẰNG TIẾNG ANH — kể cả khi người dùng hỏi "
                    "bằng tiếng Việt. Lý do: tài liệu trong kho phần lớn là tiếng Anh, và "
                    "một truy vấn tiếng Việt không với tới chúng — nó nằm gần MỌI văn bản "
                    "tiếng Việt hơn là gần đoạn tiếng Anh trả lời đúng câu hỏi, nên đáp án "
                    "đúng không bao giờ được lấy ra. "
                    "Viết thành câu đầy đủ ngữ cảnh, đừng chỉ vài từ khoá rời — nhưng "
                    "NGẮN, tối đa khoảng mười từ, và chỉ gồm thứ cần tìm. Đừng thêm chỉ "
                    "dẫn cho công cụ (\"liệt kê 10 món\", \"kèm mô tả ngắn\", \"trừ những "
                    "món đã kể\"): công cụ không đọc mệnh lệnh, và những chữ thừa đó bị "
                    "tính vào phép so khớp, kéo truy vấn ra xa đoạn cần tìm. "
                    "GIỮ NGUYÊN, KHÔNG DỊCH: mã số (QD-145/2026), tên riêng, tên món hay "
                    "thuật ngữ đặc thù không có từ tương đương — dịch chúng là làm hỏng "
                    "đúng thứ giúp tìm ra tài liệu. Cần thì để cả hai dạng cho riêng từ đó. "
                    "Nhưng đừng viết CẢ CÂU bằng hai thứ tiếng: một chuỗi lai Việt-Anh cho "
                    "kết quả kém hơn hẳn tiếng Anh thuần."
                ),
            },
            # NGUOI TRONG VONG LAP. Tham so nay la duong VE sau khi da hoi nguoi dung.
            #
            # Khong lam thanh mot cong cu rieng: hai cong cu gan giong nhau thi model
            # phai doan xem goi cai nao, va no doan sai o dung luc dang boi roi. Mot
            # cong cu, mot tham so tuy chon, va su co mat cua tham so do la tin hieu.
            "chon": {
                "type": "string",
                "description": (
                    "CHỈ dùng khi lượt trước bạn đã đưa ra danh sách lựa chọn và người "
                    "dùng vừa chọn một mục. Chép NGUYÊN VĂN tên mục họ chọn vào đây, "
                    "kèm nguyên truy vấn tiếng Anh cũ ở `query`. Công cụ sẽ tra sâu và "
                    "rộng hơn quanh mục đó. "
                    "Họ chọn \"Khác\" hoặc nói không phải mục nào ở trên thì đặt "
                    "`chon` là \"khác\": công cụ sẽ tra rộng hơn và bỏ qua những mục "
                    "vừa gợi ý. Không bao giờ tự bịa giá trị cho tham số này."
                ),
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    requirements=ToolRequirements(
        rate_limit="Khong gioi han — truy van chay tren Postgres cua chinh ta",
        cost_per_call="Mot lan embed cau hoi (~$0,000001) + mot lan rerank",
        timeout_ms=10_000,
    ),
    returns="Cac doan tai lieu lien quan, moi doan kem ten tai lieu va muc de trich dan.",
    failure_modes=(
        "Chua nap tai lieu nao -> cong cu khong duoc khai trong specs()",
        "Truy van tieng Viet tren kho tieng Anh -> gom cum theo NGON NGU, dap an dung "
        "khong lot noi top 10 nen rerank khong bao gio thay; description da dan model "
        "viet tieng Anh. Luat nay phu thuoc corpus — xem chu thich o tham so `query`.",
        "Moi ket qua duoi RERANK_MIN_SCORE -> tra ve 'khong tim thay', KHONG phai loi",
        "Rerank hong -> giu thu tu RRF va ghi log ERROR, van tra ve ket qua",
        "Lan tim CHUNG CHUNG (d > RAG_HOI_LAI_TU) -> tra ve DANH SACH LUA CHON chu "
        "khong tra ve noi dung; goi lai voi tham so `chon` de tra sau",
    ),
)

#: CSDL co tai lieu khong. Do luc khoi dong process — xem refresh_availability().
_has_documents = False


async def refresh_availability() -> bool:
    """Dem chunk mot lan luc khoi dong.

    Khong dem o moi lan goi specs(): do la mot cau SQL cho MOI tin nhan de tra loi
    mot cau hoi chi doi sau moi lan nap tai lieu. Nap tai lieu xong thi khoi dong
    lai worker — `cli ingest` co nhac dieu do.
    """
    global _has_documents
    try:
        rows = await fetch("SELECT EXISTS (SELECT 1 FROM kb_chunk) AS co")
        _has_documents = bool(rows[0]["co"]) if rows else False
    except Exception as error:
        # Bang chua ton tai (chua migrate) khong phai su co — chi nghia la chua co gi.
        _log.warning("khong dem duoc kb_chunk, coi nhu chua co tai lieu", err=str(error))
        _has_documents = False
    return _has_documents


def is_knowledge_search_available() -> bool:
    return _has_documents


#: So chunk lay ra o che do TRA SAU, sau khi nguoi dung da chon.
#:
#: Rong hon _DEFAULT_K vi luc nay ta da biet nguoi dung muon gi, nen cai gia cua mot
#: ket qua thua thap han cai gia cua viec hoi ho them mot lan nua.
_K_SAU = 12

#: Do dai trich doan kem theo moi ung vien trong danh sach hoi lai.
#:
#: Ban dau danh sach chi co TEN, kem mot cau cam "ĐỪNG trả lời bằng nội dung các mục
#: này". Do 11/09/2026 cho thay cam do lam hong ca mot lop cau hoi: "Lam sao cho chuoi
#: xanh bot chat?" tra ve danh sach 8 MON AN va hoi nguoi dung chon mot mon — trong khi
#: ho hoi mot KY THUAT, va ca 8 muc deu tra loi giong nhau (ngam chanh va giam). Model
#: khong the nhan ra dieu do, vi no chi nhin thay TEN.
#:
#: 240 ky tu du de thay cac muc co cung noi mot dieu hay khong. 12 ung vien x 240 con
#: cach rat xa tran 12.000 token cua tang `tool`.
_TRICH_DOAN = 240

#: Nguoi dung tra loi "khong phai muc nao o tren". Doi chieu sau khi bo dau va ha
#: chu thuong — model co the chep lai "Khac", "khac", "OTHER"...
_KHAC = frozenset({"khac", "khong phai", "khong", "other", "none", "deu khong"})


def _ten(chunk: RetrievedChunk) -> str:
    """Ten hien cho nguoi dung thay. Muc neu co, khong thi ten tai lieu."""
    return chunk.section or chunk.doc_title


def _la_khac(chon: str) -> bool:
    from agents.policy.injection import fold_diacritics

    return fold_diacritics(chon).strip().lower().strip(".!?") in _KHAC


def _chung_chung(chunks: list[RetrievedChunk], nguong: float) -> bool:
    """Lan tim nay co dang "khong biet chac" khong.

    Doc KHOANG CACH chu khong doc diem rerank: o che do du phong diem la ti le tu
    trung, khong so duoc voi mot nguong co dinh (xem llm/reranker.py). Khoang cach
    cosine thi co hieu chuan ngu nghia trong CA HAI che do rerank.

    Khong tinh duoc khoang cach -> KHONG hoi. "Khong biet" khong duoc bien thanh
    "khong chac": hoi lai ma khong co can cu chi la mot luot lang phi.

    KHONG doi phai co tu hai ung vien tro len. Ban dau co luat do — "mot danh sach
    mot dong khong phai la mot lua chon" — va no SAI theo mot kieu tu che giau:
    truy van cang mo ho thi cang IT doan qua duoc RAG_MAX_DISTANCE, nen dung luc can
    hoi nhat lai la luc chi con mot ung vien, va luat do tu tat tinh nang. Do that:
    truy van dai dong model sinh ra cho d=0,6223 va DUNG MOT doan song sot. Mot dong
    kem dong "Khac" van la mot cau hoi that: "co phai y ban la muc nay khong".
    """
    khoang_cach = [c.distance for c in chunks if c.distance is not None]
    if not khoang_cach:
        return False
    return min(khoang_cach) > nguong


def _danh_sach_lua_chon(chunks: list[RetrievedChunk]) -> str:
    """Van ban di THANG vao prompt, va no phai thang duoc mot luat trong system prompt.

    SYSTEM_PROMPT cam hoi lai gan nhu tuyet doi — luat do them 07/09/2026 sau khi do
    duoc BON luot lien tiep bot chi hoi lai ma khong lam gi. Nen o day khong the chi
    "goi y" hoi: phai noi ro day la ngoai le da duoc cho phep, va vi sao no khac —
    ta CO ung vien co that trong tay, chu khong phai dang hoi vi luoi tra cuu.
    """
    dau: dict[str, str] = {}
    for c in chunks:
        # Giu doan DAU TIEN cua moi ten: `chunks` da xep theo do lien quan nen do
        # la doan gan cau hoi nhat cua muc do.
        dau.setdefault(_ten(c), " ".join(c.content.split())[:_TRICH_DOAN])

    ten = list(dau)
    dong = "\n".join(
        f"{i}. {t}\n   {dau[t]}" for i, t in enumerate(ten, start=1)
    )
    return (
        "KẾT QUẢ KHÔNG CHẮC — tài liệu có vài mục liên quan nhưng không mục nào "
        "khớp hẳn câu hỏi.\n\n"
        "TRƯỚC KHI HỎI LẠI, xét một điều: các mục dưới đây có cùng nói MỘT điều "
        "trả lời được câu hỏi không?\n\n"
        "- CÓ — người dùng hỏi một KỸ THUẬT hay một CÁCH LÀM chung (kiểu "
        "\"làm sao cho bớt chát\", \"khử mùi thế nào\"), và các mục đều nói giống "
        "nhau: TRẢ LỜI LUÔN bằng điều chung đó, nêu nguồn, ĐỪNG hỏi lại. Họ hỏi "
        "CÁCH LÀM, không hỏi món nào — bắt họ chọn một món là hỏi sai thứ.\n"
        "- KHÔNG — các mục là những lựa chọn khác nhau, mỗi mục một đáp án riêng: "
        "đưa NGUYÊN danh sách dưới đây cho người dùng, giữ đúng số thứ tự và đúng "
        "tên và KHÔNG kèm trích đoạn, hỏi đúng một câu ngắn rồi DỪNG lượt này.\n\n"
        "Cả hai nhánh đều KHÔNG được trả lời từ trí nhớ.\n\n"
        f"{dong}\n"
        f"{len(ten) + 1}. Khác — không phải mục nào ở trên\n\n"
        "Nhánh hỏi lại là NGOẠI LỆ đã được cho phép của luật \"làm trước, hỏi sau\": bạn đang cầm "
        "sẵn các mục có thật trong tài liệu, nên đây là một lựa chọn để người dùng "
        "quyết, không phải một câu hỏi thay cho việc tra cứu.\n"
        "Họ chọn xong thì gọi lại search_knowledge_base với `chon` là tên mục họ chọn "
        f"(hoặc \"khác\" nếu họ chọn mục {len(ten) + 1}), và `query` giữ nguyên như lần "
        "này. Lần đó công cụ sẽ trả về nội dung, không hỏi lại nữa."
    )


async def run_knowledge_search(payload: dict[str, Any], ctx: CallContext) -> str:
    query = payload.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("search_knowledge_base can tham so query")

    raw_chon = payload.get("chon")
    chon = raw_chon.strip() if isinstance(raw_chon, str) and raw_chon.strip() else None

    from knowledge.retrieve.service import knowledge

    # Nguoi dung da chon roi thi tra SAU va KHONG bao gio hoi lai. Hoi hai lan lien
    # tiep la dung cai vong lap ma luat 07/09 duoc dung len de chan.
    if chon is not None:
        # "Khac" nghia la khong muc nao dung, nen KHONG dua no vao truy van — no
        # khong phai mot tu khoa, no la mot loi phu dinh. Chi noi rong pham vi.
        truy_van = query if _la_khac(chon) else f"{chon} {query}"
        chunks = await knowledge.search(ctx.scope, truy_van, _K_SAU)
        _log.info(
            "tra sau sau khi nguoi dung chon",
            trace_id=ctx.trace_id,
            khac=_la_khac(chon),
            so_doan=len(chunks),
        )
        return _dinh_dang(chunks) if chunks else _KHONG_TIM_THAY

    # PHAM VI di cung cau hoi, y het hop dong cua memory_fact: mot nhom chi doc
    # duoc tai lieu 'chung' va tai lieu cua chinh no. Truoc day khong co tham so
    # nay — moi nhom doc duoc toan bo moi tai lieu.
    chunks = await knowledge.search(ctx.scope, query, _DEFAULT_K)

    if chunks and _chung_chung(chunks, get_settings().RAG_HOI_LAI_TU):
        gan_nhat = min(c.distance for c in chunks if c.distance is not None)
        # Gom ung vien RONG hon de danh sach dua ra co cai de chon. Top-5 cua mot
        # truy van mo ho thuong bo sot dung thu nguoi dung dinh hoi: do that voi
        # "dishes that use cheese and pasta", k=5 cho 5 muc khong co dap an nao,
        # con k=12 keo duoc CA HAI dap an dung vao danh sach.
        #
        # Ton them mot lan tim, KHONG ton them lan goi API nao: vector cau hoi da
        # nam trong cache `emb:{sha256}` tu lan tim vua roi.
        ung_vien = await knowledge.search(ctx.scope, query, _K_SAU) or chunks
        _log.info(
            "lan tim chung chung — hoi nguoi dung chon",
            trace_id=ctx.trace_id,
            khoang_cach_gan_nhat=round(gan_nhat, 4),
            so_ung_vien=len({_ten(c) for c in ung_vien}),
        )
        return _danh_sach_lua_chon(ung_vien)

    return _dinh_dang(chunks) if chunks else _KHONG_TIM_THAY


#: Cau nay di thang vao prompt, va no la don bay manh nhat cua ca luong: no den DUNG
#: khoanh khac model vua thay ket qua rong. Tach ra hang so vi gio co HAI duong dan
#: toi no: lan tim thuong, va lan tra sau khi nguoi dung da chon.
#:
#: Phan nhanh theo LOAI CAU HOI chu khong theo "co tim thay hay khong", vi hai loai
#: co hai cai gia rat khac nhau:
#:
#:   - Cau hoi noi bo ("chinh sach nghi phep nam"): web tra ve luat lao dong chung —
#:     hop ly, co nguon, va SAI voi to chuc nay. Nguoi dung se hanh dong theo. Te hon
#:     han viec khong tra loi.
#:   - Cau hoi kien thuc chung ("cach lam bun cha"): web dung la cho de tra.
#:
#: Cong cu khong biet cau hoi thuoc loai nao — model thi biet, vi no doc ca doan hoi
#: thoai. Nen o day noi ca hai duong kem LY DO, khong chi ra lenh.
_KHONG_TIM_THAY = (
    "Không tìm thấy đoạn tài liệu nội bộ nào liên quan tới câu hỏi này.\n\n"
    "- Nếu đây là câu hỏi về QUY ĐỊNH / QUY TRÌNH / CHÍNH SÁCH của tổ chức: "
    "nói thẳng là tài liệu hiện có không đề cập và gợi ý hỏi bộ phận phụ trách. "
    "ĐỪNG tra web — web không biết quy định riêng của tổ chức này, và một câu "
    "trả lời chung chung sẽ bị hiểu nhầm thành quy định thật.\n"
    "- Nếu đây là câu hỏi KIẾN THỨC CHUNG (món ăn, cách nấu, thông tin đời "
    "sống, sự kiện bên ngoài): gọi web_search ngay trong lượt này, và khi trả "
    "lời phải nói rõ thông tin lấy từ web chứ không phải từ tài liệu nội bộ.\n\n"
    "Cả hai trường hợp: đừng lấy trí nhớ của bạn ra thay thế."
)


def _dinh_dang(chunks: list[RetrievedChunk]) -> str:
    return "\n\n".join(
        f"[{i}] Nguồn: {c.doc_title}"
        + (f" — mục: {c.section}" if c.section else "")
        + (f" — trang {c.page}" if c.page else "")
        + f"\n{c.content}"
        for i, c in enumerate(chunks, start=1)
    )
