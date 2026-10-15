"""Chay bo cau hoi, xuat bang chi so, DO khi khong dat nguong.

Vi sao ton tai: khong co eval thi moi thay doi prompt deu la doan mo. Doi mot chu
trong SYSTEM_PROMPT co the lam chat luong tut ma khong ai nhan ra trong hai tuan.

HAI KHUNG DO, chay cung mot luot
--------------------------------
Khung cu (docs/plan-thi-cong.md muc 10) — re, khong doc tai lieu:

    Recall@5 > 0,85 · Faithfulness > 0,9 · Latency p95 < 5s

Khung RAGAS (bat bang --ragas) — bon chi so, moi cai bat mot kieu hong khac:

    Context Recall     ngu canh co DU de dung nen dap an chuan khong
    Context Precision  trong nhung gi lay ve, bao nhieu la dung viec, va co xep tren khong
    Faithfulness       bot co bia khong  (ban DEM Y, khac ban cho diem tong o faithfulness.py)
    Answer Relevance   cau tra loi co dung trong tam cau hoi khong

Bon cai nay KHONG dung `chunk_id`, nen chung song qua moi lan nap lai kho — trong hai
ngay 10-11/09/2026 da phai anh xa lai `expected_chunk_ids` hai lan.

HAI DUONG ONG, chon bang --qua-cong-cu
--------------------------------------
Mac dinh (TANG TRUY HOI): day thang cau hoi vao `knowledge.search`. Re, tat dinh, va
do dung mot thu — duong tim kiem.

`--qua-cong-cu` (TRO LY THAT): chay qua `handle_message`, tuc model TU VIET truy van
roi moi goi `search_knowledge_base`. Do dung thu production lam.

Khac biet KHONG nho. Voi cau "Mon nao dung pho mai va mi ong":

    mac dinh       truy van = "Mon nao dung pho mai va mi ong"   (nguyen van tieng Viet)
    qua-cong-cu    truy van = "dishes that use cheese and pasta" (model tu dich)

Ban sua ngay 10/09 nam DUNG o buoc model tu dich do, nen che do mac dinh khong nhin
thay no. Do 11/09: cung cau g031, mac dinh cho ctx_recall 0,00 con chay dau-cuoi thi
lay dung ca hai chunk dap an. Hai nhom `giao_tap_hop` va `xuyen_ngon_ngu` o che do mac
dinh la CAN DUOI, khong phai chat luong that.

Doi lai, che do qua cong cu:
  - Recall@5 dung typed provenance cua tool: K chunk ID unique dau tien theo thu tu
    tool call/result. Metadata thieu/loi/khong goi tool giu unknown; retrieval empty
    da do cho Recall=0. Khong parse ID/scope/version tu van ban trich dan.
  - Do tre do CA LUOT, gom moi vong ReAct. Con so nay moi la do tre nguoi dung cam
    nhan, nhung no khong so sanh duoc voi cac lan chay o che do mac dinh.
  - On hon: model co the goi cong cu nhieu lan, hoac khong goi lan nao.

CHAY TON TIEN THAT. Them final-answer judge de do claims/no-answer; so call tuy
applicability, va Answer Relevance con goi embedding. Chay
nightly va khi PR dung vao prompt/, knowledge/, llm/models.py — khong phai moi commit.

Chay:
    uv run python -m evals.runner                              bo cu, khung cu
    uv run python -m evals.runner evals/dataset/golden.jsonl --ragas
    uv run python -m evals.runner evals/dataset/golden.jsonl --ragas --qua-cong-cu
"""

import argparse
import asyncio
import dataclasses
import hashlib
import json
import sys
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from adapters.cli.normalize import normalize_cli_input
from agents.domain.knowledge import RetrievalEvidence
from agents.domain.thread import ThreadScope
from agents.pipeline.handle_message import handle_message
from agents.pipeline.stages.generate import CONFIG_ERROR_TEXT, FALLBACK_TEXT
from agents.ports.channel import ChannelPort
from agents.ports.llm import CallContext, ToolCall
from agents.ports.tool import ToolDefinition, ToolPort, ToolResult
from agents.prompt.builder import render_knowledge
from agents.prompt.context import ContextInput, build_context
from config import get_settings
from infra.db import close_db
from infra.logger import get_logger
from infra.redis_client import close_redis
from knowledge.retrieve.service import knowledge
from llm.models import MODELS
from llm.openai_client import llm
from main.container import build_deps

from .corpus_contract import check_corpus, corpus_fingerprint
from .dataset_contract import (
    MINIMUM_TOTAL,
    annotation_deficits,
    check_review,
    coverage_deficits,
    load_and_validate,
    split_for_id,
)
from .metrics.answer_relevance import judge_answer_relevance
from .metrics.claim_faithfulness import judge_claim_faithfulness
from .metrics.context_precision import judge_context_precision
from .metrics.context_recall import judge_context_recall
from .metrics.faithfulness import judge_faithfulness
from .metrics.final_answer import judge_final_answer
from .metrics.latency import percentile
from .metrics.recall import recall_at_k
from .run_artifact import (
    METRICS,
    build_artifact,
    config_hash,
    no_answer_summary,
    source_identity,
    write_artifact,
)

DEFAULT_DATASET = Path(__file__).resolve().parent / "dataset" / "qa.jsonl"

#: Ma thoat. CI phan biet ba truong hop nay, va do la ly do chung khac nhau:
#:   0  dat het nguong
#:   1  TRUOT — co van de that, phai xem
#:   2  chua co du lieu de chay (dataset con la dong mau) — KHONG phai loi
EXIT_DAT = 0
EXIT_TRUOT = 1
EXIT_CHUA_CO_DU_LIEU = 2

RECALL_MIN = 0.85
FAITHFULNESS_MIN = 0.9
LATENCY_P95_MAX_MS = 5_000

#: Nguong RAGAS. Lan chay dau 11/09/2026 tren golden.jsonl (50 cau, 46 cham duoc):
#:
#:     Context Recall      0,857
#:     Context Precision   0,801
#:     Faithfulness (y)    0,930
#:     Answer Relevance    0,646   <- KHONG PHAI NGUONG, xem duoi
#:
#: Ba con so dau la nguong muon cua khung RAGAS va lan chay dau vua du vuot. Van con
#: la so muon: mot nguong chua biet no dao dong the nao thi chua noi len dieu gi, nen
#: dung coi viec vuot no la bang chung cho toi khi co vai lan chay.
CONTEXT_RECALL_MIN = 0.85
CONTEXT_PRECISION_MIN = 0.70
CLAIM_FAITHFULNESS_MIN = 0.90
NO_ANSWER_FALSE_ANSWER_MAX = 0.05

#: Answer Relevance KHONG lam cong chan, va day la mot lua chon co ly do.
#:
#: No la cosine giua cau hoi that va cac cau hoi doan nguoc tu cau tra loi. Tri tuyet
#: doi cua cosine phu thuoc MODEL NHUNG va NGON NGU: bo nay 36/50 cau tieng Viet, va
#: 0,646 hoan toan co the la muc binh thuong cua text-embedding-3-large tren tieng
#: Viet chu khong phai dau hieu cau tra loi lac de. Chua ai do dieu do.
#:
#: Dat mot nguong muon roi de job dem do thuong truc thi te hon la khong dat: mot job
#: do mai la mot job khong ai doc nua — chinh workflow evals.yml da viet cau do.
#:
#: DIEU KIEN de no thanh cong chan: co khoang 5 lan chay de biet no dao dong bao
#: nhieu, roi dat nguong duoi muc thap nhat quan sat duoc mot khoang an toan.
ANSWER_RELEVANCE_THAM_KHAO = True

#: So chunk lay ra — Recall@5 nen la 5.
K = 5

_PLACEHOLDER = "VI DU"

_log = get_logger()


@dataclass(frozen=True, slots=True)
class Row:
    id: str
    question: str
    answer: str
    expected_chunk_ids: list[str]
    #: Nhom cau hoi: tra_cuu, giao_tap_hop, quy_trinh, thuoc_tinh, xuyen_ngon_ngu,
    #: ngoai_kho, mo_ho. Bao cao tach theo nhom nay, vi mot trung binh chung giau mat
    #: viec mot NHOM dang hong — do dung la kieu hong da xay ra ngay 10/09/2026.
    loai: str = "khong_phan_loai"
    ngon_ngu: str = ""
    #: Cum tu DAC TRUNG phai xuat hien trong ngu canh. Thay cho `expected_chunk_ids`:
    #: id chet moi lan nap lai, cum tu thi song.
    neo: tuple[str, ...] = ()
    answerable: bool = True
    scope: str = "chung"
    forbidden_claims: tuple[str, ...] = ()
    # Legacy `neo` are contextual anchors, not human-reviewed final-answer claims.
    required_claims: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Outcome:
    row: Row
    #: None requires metric_states to distinguish unknown from not applicable.
    recall: float | None
    faithfulness: float | None
    neo_recall: float | None
    context_recall: float | None
    context_precision: float | None
    claim_faithfulness: float | None
    answer_relevance: float | None
    latency_ms: int
    answer: str
    #: Truy van MODEL TU VIET, chi co o che do --qua-cong-cu. Rong nghia la model
    #: khong goi cong cu lan nao — mot ket qua rat dang doc, khong phai mot cho trong.
    truy_van: tuple[str, ...] = ()
    refused: bool | None = None
    required_claims_recall: float | None = None
    forbidden_claims_rate: float | None = None
    retrieval_scope_violation_rate: float | None = None
    retrieval_version_violation_rate: float | None = None


def metric_states(outcome: Outcome, ragas: bool, qua_cong_cu: bool) -> dict[str, str]:
    """Separate unknown judgments from measurements that do not apply."""
    row = outcome.row
    not_applicable = {
        "recall": not row.answerable,
        "neo_recall": not row.neo,
        "context_recall": not row.answerable,
        "context_precision": not row.answerable,
        "claim_faithfulness": outcome.refused is True,
        "answer_relevance": outcome.refused is True,
        "required_claims_recall": not row.required_claims,
        "forbidden_claims_rate": not row.forbidden_claims,
    }
    disabled = {"context_recall", "context_precision", "claim_faithfulness", "answer_relevance"}
    return {
        name: (
            "measured"
            if getattr(outcome, name) is not None
            else "disabled"
            if not ragas and name in disabled
            else "not_applicable"
            if not_applicable.get(name, False)
            else "unknown"
        )
        for name in METRICS
    }


def evidence_metrics(
    evidence: list[RetrievalEvidence] | None, expected_scope: str
) -> tuple[float | None, float | None]:
    if evidence is None:
        return None, None
    scope = (
        (
            sum(item.doc_scope not in {"chung", expected_scope} for item in evidence)
            / len(evidence)
            if evidence
            else 0.0
        )
        if all(item.doc_scope is not None for item in evidence)
        else None
    )
    version = (
        (sum(item.is_latest is False for item in evidence) / len(evidence) if evidence else 0.0)
        if all(
            item.doc_id is not None and item.doc_version is not None and item.is_latest is not None
            for item in evidence
        )
        else None
    )
    return scope, version


def load_dataset(dataset: Path) -> list[Row]:
    if not dataset.exists():
        return []
    rows: list[Row] = []
    records = load_and_validate(dataset)
    raw = [
        json.loads(line)
        for line in dataset.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    for record, data in zip(records, raw, strict=True):
        if record.scope != "chung":
            # The live pipeline creates an isolated CLI thread per question.
            # Do not silently test another namespace or touch production memory.
            raise ValueError("scoped eval requires an isolated corpus/scope fixture")
        rows.append(
            Row(
                id=record.id,
                question=record.question,
                answer=record.expected_answer,
                expected_chunk_ids=list(record.expected_chunk_ids),
                loai=record.category,
                ngon_ngu=str(data.get("ngon_ngu") or ""),
                neo=record.required_claims,
                answerable=record.answerable,
                scope=record.scope,
                forbidden_claims=record.forbidden_claims,
                required_claims=(record.required_claims if "required_claims" in data else ()),
            )
        )
    return rows


def is_placeholder(rows: list[Row]) -> bool:
    return all(_PLACEHOLDER in r.question for r in rows) if rows else True


def la_cau_fallback(answer: str) -> bool:
    """Bot tra ve cau XIN LOI mac dinh thay vi mot cau tra loi that.

    Cham cau do nhu mot cau tra loi te se cho ra mot bao cao sai mot cach TU TIN.

    Da xay ra that 11/09/2026: `DAILY_BUDGET_USD=2` can giua lan chay, va 27 cau LIEN
    TIEP tu g026 den het deu nhan cau fallback. Bao cao in ra Context Recall 0,438 va
    `giao_tap_hop` 0,000 — trong y het mot hoi quy tham khoc, trong khi khong co gi
    hong ca. Cung mot lop loi voi APITimeoutError da chan o main().

    So sanh TIEN TO chu khong so sanh ca chuoi: `_finish()` noi them
    INCOMPLETE_SUFFIX vao duoi khi dung giua chung.
    """
    dau = answer.strip()
    return any(dau.startswith(mau[:40]) for mau in (FALLBACK_TEXT, CONFIG_ERROR_TEXT))


def neo_trong_ngu_canh(neo: tuple[str, ...] | list[str], context: str) -> float | None:
    """Ti le cum tu dac trung xuat hien trong ngu canh. Khong co neo -> None.

    Deterministic va MIEN PHI: khong goi model, khong dung chunk_id. Day la luoi an
    toan cho Context Recall — khi nguoi cham LLM va phep dem chu noi hai dieu khac
    nhau thi it nhat ta biet ma di nhin.
    """
    if not neo:
        return None
    gon = " ".join(context.split()).lower()
    return sum(1 for n in neo if " ".join(n.split()).lower() in gon) / len(neo)


class _KenhGom(ChannelPort):
    """Kenh gia: gom moi thu bot gui ra thay vi in len man hinh."""

    #: Khong cat tin: bo eval cham tren TOAN BO cau tra loi. Cat theo gioi han cua
    #: Zalo se lam nguoi cham thay mot cau cut duoi va cham no la thieu can cu.
    max_message_chars = 1_000_000

    def __init__(self) -> None:
        self.text = ""

    async def typing(self, scope: ThreadScope) -> None:
        return None

    async def send(self, scope: ThreadScope, text: str, reply_to: str | None = None) -> None:
        self.text += text


class _CongCuGhiLai:
    """Boc `ToolPort` de ghi lai model goi cong cu gi, voi truy van nao, tra ve gi.

    BOC chu khong va de: `Deps.tools` la mot `ToolPort`, tuc mot cho noi da duoc thiet
    ke san. Va de len noi tam cua `tools/registry.py` thi bo eval se gan chat vao chi
    tiet ben trong cua no, va se vo im lang khi ai do doi chi tiet do.
    """

    def __init__(self, that: ToolPort) -> None:
        self._that = that
        #: (ten cong cu, truy van model tu viet) — de bao cao noi ro no da hoi gi.
        self.goi: list[tuple[str, str]] = []
        #: Van ban cong cu tra ve. DAY moi la "ngu canh" o che do nay: dung thu model
        #: nhin thay, khong phai mot ban ghep lai tu chunk.
        self.ket_qua: list[str] = []
        self.evidence: list[RetrievalEvidence] = []
        self.retrieval_observed = False
        self.retrieval_unknown = False

    def specs(self) -> tuple[ToolDefinition, ...]:
        return self._that.specs()

    async def call_many(
        self, calls: tuple[ToolCall, ...], ctx: CallContext
    ) -> tuple[ToolResult, ...]:
        for c in calls:
            self.goi.append((c.name, str(c.input.get("query") or "")))
        ket_qua = await self._that.call_many(calls, ctx)
        self.ket_qua.extend(r.content for r in ket_qua if r.ok)
        for result in ket_qua:
            if result.name != "search_knowledge_base":
                continue
            if not result.ok or result.evidence is None:
                self.retrieval_unknown = True
            else:
                self.retrieval_observed = True
                self.evidence.extend(result.evidence)
        return ket_qua


async def run_one_qua_cong_cu(row: Row, ragas: bool) -> Outcome:
    """Chay qua `handle_message` — dung duong ma production di.

    Khac `run_one`: o day MODEL tu viet truy van. Do la buoc ma ban sua ngay 10/09
    nam vao, va la buoc che do mac dinh khong he di qua.
    """
    trace_id = str(uuid.uuid4())
    kenh = _KenhGom()
    deps = await build_deps(kenh)
    ghi = _CongCuGhiLai(deps.tools)
    deps = dataclasses.replace(deps, tools=ghi)

    # thread_id RIENG cho moi cau: chung thread thi cau truoc thanh lich su cua cau
    # sau, va bo eval se do them mot bien khong ai dinh do.
    #
    # sender_id cung rieng, va day la mot cai bay that chu khong phai phong xa: bo
    # chan tan suat dem theo NGUOI GUI (RL_USER_PER_MIN, mac dinh 10/phut) con CLI thi
    # dung dung mot sender_id co dinh. O toc do hien tai (~4 cau/phut) thi chua cham,
    # nhung hom nao API nhanh len — hoac bo cau dai ra — thi bo eval se lang le do bo
    # chan tan suat thay vi do chat luong, va cau tra loi bi chan se bi cham nhu mot
    # cau tra loi te.
    msg = dataclasses.replace(
        normalize_cli_input(row.question),
        thread_id=f"eval-{row.id}-{trace_id[:8]}",
        sender_id=f"eval-{row.id}",
        trace_id=trace_id,
    )

    started = time.monotonic()
    await handle_message(msg, deps)
    latency_ms = int((time.monotonic() - started) * 1000)

    answer = kenh.text
    context = "\n\n".join(ghi.ket_qua)

    # Bot KHONG tra loi gi ca. Cham mot chuoi rong nhu the no la mot cau tra loi te
    # se cho ra mot bao cao sai mot cach TU TIN — dung kieu hong ma ca tai lieu nay
    # chong. Nem loi de no roi vao muc "khong chay duoc", duoc dem rieng.
    #
    # Nguyen nhan hay gap nhat KHONG phai model: `DM_POLICY` mac dinh la "pairing",
    # ma che do nay sinh thread_id moi cho moi cau, nen tang truy cap chan sach. Tren
    # may co .env dat DM_POLICY=open thi khong thay gi, tren CI thi chan het 50 cau.
    if la_cau_fallback(answer):
        raise RuntimeError(
            "bot tra ve cau fallback — het ngan sach ngay (DAILY_BUDGET_USD), "
            "deadline, hoac loi upstream. KHONG phai van de chat luong."
        )

    if not answer.strip():
        raise RuntimeError(
            "bot khong tra loi gi — kiem tra DM_POLICY (can 'open' cho eval), "
            "allowlist, hoac bo chan tan suat"
        )

    faithfulness = await judge_faithfulness(row.question, answer, context, trace_id)
    final = await judge_final_answer(answer, row.required_claims, row.forbidden_claims, trace_id)

    context_recall = context_precision = claim_faith = answer_rel = None
    if ragas:
        if row.answer and row.answerable:
            context_recall = await judge_context_recall(row.answer, context, trace_id)
        # Cat lai thanh tung ket qua cong cu: Context Precision cham theo TUNG DOAN,
        # va o day mot "doan" la mot lan goi cong cu.
        if row.answerable:
            context_precision = (
                await judge_context_precision(row.question, ghi.ket_qua, trace_id)
                if ghi.ket_qua
                else 0.0
            )
        if final.refused is not True:
            claim_faith = await judge_claim_faithfulness(answer, context, trace_id)
            answer_rel = await judge_answer_relevance(row.question, answer, trace_id)

    evidence = ghi.evidence if ghi.retrieval_observed and not ghi.retrieval_unknown else None
    scope_rate, version_rate = evidence_metrics(evidence, row.scope)
    recall = (
        recall_at_k(
            list(dict.fromkeys(item.chunk_id for item in evidence)), row.expected_chunk_ids, K
        )
        if evidence is not None and row.answerable and row.expected_chunk_ids
        else None
    )

    return Outcome(
        row=row,
        # First K unique chunks in tool-call/result order, from typed provenance.
        recall=recall,
        faithfulness=faithfulness,
        neo_recall=neo_trong_ngu_canh(row.neo, context),
        context_recall=context_recall,
        context_precision=context_precision,
        claim_faithfulness=claim_faith,
        answer_relevance=answer_rel,
        latency_ms=latency_ms,
        answer=answer,
        truy_van=tuple(q for _, q in ghi.goi if q),
        refused=final.refused,
        required_claims_recall=final.required_claims_recall,
        forbidden_claims_rate=final.forbidden_claims_rate,
        retrieval_scope_violation_rate=scope_rate,
        retrieval_version_violation_rate=version_rate,
    )


async def run_one(row: Row, ragas: bool) -> Outcome:
    trace_id = str(uuid.uuid4())
    scope = ThreadScope(platform="cli", thread_id=f"eval-{row.id}")
    ctx = CallContext(scope=scope, sender_id="eval", trace_id=trace_id)

    started = time.monotonic()
    chunks = await knowledge.search(scope, row.question, K)
    envelope = build_context(
        ContextInput(question=row.question, is_group=False, chunks=tuple(chunks)), _log
    )
    result = await llm.reply(
        system=envelope.system,
        messages=envelope.messages,
        max_tokens=MODELS["reply"].max_tokens,
        # `or "low"`: `ModelConfig.effort` thanh tuy chon tu khi co model tu host
        # (Gemma khong co `reasoning_effort`). Route `reply` luon chay tren OpenAI.
        effort=MODELS["reply"].effort or "low",
        ctx=ctx,
    )
    latency_ms = int((time.monotonic() - started) * 1000)

    # Cham TREN DUNG khoi tai lieu ma bot da nhin thay — cung mot ham render, khong
    # phai mot ban ghep lai.
    #
    # Da troi that: ban dau chi noi cac `content` lai voi nhau, tuc la bo mat ten tai
    # lieu va ten muc. Cau tra loi co trich dan '(theo So tay 2026, muc Chinh sach
    # hoan tien)' bi nguoi cham coi la chi tiet khong kiem chung duoc va cham 0,5 —
    # sai o phia NGUOI CHAM chu khong phai o bot. Va vi no cham deu moi cau nen ket
    # qua trong rat giong mot phep do that.
    context = render_knowledge(tuple(chunks))
    faithfulness = await judge_faithfulness(row.question, result.text, context, trace_id)
    final = await judge_final_answer(
        result.text, row.required_claims, row.forbidden_claims, trace_id
    )

    # Retrieval recall does not apply to an unanswerable row. Missing annotation
    # on an answerable row is unknown and fails the measured gate.
    if row.expected_chunk_ids:
        recall: float | None = recall_at_k([c.chunk_id for c in chunks], row.expected_chunk_ids, K)
    else:
        # No ground-truth relevant chunk means retrieval recall is undefined,
        # not perfect. No-answer precision/recall requires separate judgments.
        recall = None

    context_recall = context_precision = claim_faith = answer_rel = None
    if ragas:
        # Cau `ngoai_kho` khong co y nao de truy trong dap an chuan.
        if row.answer and row.answerable:
            context_recall = await judge_context_recall(row.answer, context, trace_id)
        # Cau `ngoai_kho` KHONG co doan nao lien quan de ma xep dung thu tu — diem
        # thap o do la hanh vi DUNG, khong phai chat luong kem. Do that 11/09 sau khi
        # bat luat cung: nhom nay tut con 0,250 chi vi bot BAT DAU chiu di tra, tuc
        # chi so phat dung cai vua sua duoc.
        if row.answerable:
            context_precision = (
                await judge_context_precision(row.question, [c.content for c in chunks], trace_id)
                if chunks
                else 0.0
            )
        if final.refused is not True:
            claim_faith = await judge_claim_faithfulness(result.text, context, trace_id)
            answer_rel = await judge_answer_relevance(row.question, result.text, trace_id)

    evidence = [
        RetrievalEvidence(
            chunk_id=chunk.chunk_id,
            doc_id=chunk.doc_id,
            doc_version=chunk.doc_version,
            doc_scope=chunk.doc_scope,
            is_latest=chunk.is_latest,
        )
        for chunk in chunks
    ]
    scope_rate, version_rate = evidence_metrics(evidence, row.scope)

    return Outcome(
        row=row,
        recall=recall,
        faithfulness=faithfulness,
        neo_recall=neo_trong_ngu_canh(row.neo, context),
        context_recall=context_recall,
        context_precision=context_precision,
        claim_faithfulness=claim_faith,
        answer_relevance=answer_rel,
        latency_ms=latency_ms,
        answer=result.text,
        refused=final.refused,
        required_claims_recall=final.required_claims_recall,
        forbidden_claims_rate=final.forbidden_claims_rate,
        retrieval_scope_violation_rate=scope_rate,
        retrieval_version_violation_rate=version_rate,
    )


def _cho_phep_in_tieng_viet() -> None:
    """Console Windows mac dinh la cp1252 va nem UnicodeEncodeError khi in tieng Viet."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def trung_binh(xs: list[float | None]) -> tuple[float | None, int]:
    """Trung binh cua nhung gia tri CHAM DUOC, kem so cau da bo qua.

    Tra ve ca so bo qua chu khong chi tra ve trung binh: mot chi so 0,95 tren 4/50 cau
    va 0,95 tren 50/50 cau la hai su that rat khac nhau, va bao cao phai noi duoc.
    """
    co = [x for x in xs if x is not None]
    if not co:
        return None, len(xs)
    return sum(co) / len(co), len(xs) - len(co)


def _dong(ten: str, gia_tri: float | None, nguong: float, bo_qua: int, lon_hon: bool) -> bool:
    if gia_tri is None:
        print(f"  ----  {ten:<20}        —   (khong cau nao cham duoc)")
        return False
    dat = gia_tri > nguong if lon_hon else gia_tri < nguong
    ghi_chu = f"   (nguong {nguong}" + (f", bo qua {bo_qua}" if bo_qua else "") + ")"
    print(f"  {'DAT ' if dat else 'TRUOT'} {ten:<20} {gia_tri:>7.3f}{ghi_chu}")
    return dat


def _metric_gate(
    outcomes: list[Outcome],
    name: str,
    threshold: float,
    ragas: bool,
    qua_cong_cu: bool,
    *,
    at_most: bool = False,
) -> bool:
    states = [metric_states(outcome, ragas, qua_cong_cu)[name] for outcome in outcomes]
    if "unknown" in states:
        return False
    values = [
        float(getattr(outcome, name)) for outcome in outcomes if getattr(outcome, name) is not None
    ]
    if not values:
        return bool(states) and all(state in {"not_applicable", "disabled"} for state in states)
    mean = sum(values) / len(values)
    return mean <= threshold if at_most else mean > threshold


def measured_quality_gate(outcomes: list[Outcome], ragas: bool, qua_cong_cu: bool) -> bool:
    if not outcomes:
        return False
    required = [("recall", RECALL_MIN), ("faithfulness", FAITHFULNESS_MIN)]
    if ragas:
        required += [
            ("context_recall", CONTEXT_RECALL_MIN),
            ("context_precision", CONTEXT_PRECISION_MIN),
            ("claim_faithfulness", CLAIM_FAITHFULNESS_MIN),
        ]
    if not all(_metric_gate(outcomes, name, value, ragas, qua_cong_cu) for name, value in required):
        return False
    if any(
        outcome.required_claims_recall != 1.0 for outcome in outcomes if outcome.row.required_claims
    ) or any(
        outcome.forbidden_claims_rate != 0.0 for outcome in outcomes if outcome.row.forbidden_claims
    ):
        return False
    # Evidence violations always fail; absent metadata stays explicitly unknown
    # and blocks release acceptance even when other measured gates pass.
    if any(
        value is not None and value != 0
        for outcome in outcomes
        for value in (
            outcome.retrieval_scope_violation_rate,
            outcome.retrieval_version_violation_rate,
        )
    ):
        return False
    no_answer = no_answer_summary(
        [
            {"answerable": outcome.row.answerable, "refused": outcome.refused}
            for outcome in outcomes
        ],
        len(outcomes),
    )
    if no_answer["unknown"] or no_answer["false_positive"]:
        return False
    if no_answer["false_answer_rate"] is not None and (
        no_answer["false_answer_rate"] > NO_ANSWER_FALSE_ANSWER_MAX
    ):
        return False
    return (
        percentile([float(outcome.latency_ms) for outcome in outcomes], 0.95) < LATENCY_P95_MAX_MS
    )


def report(outcomes: list[Outcome], ragas: bool, qua_cong_cu: bool = False) -> bool:
    """In bang chi so. True = dat het nguong."""
    # NOI RO dang do duong nao. Hai che do cho ra hai bo so KHONG so sanh duoc voi
    # nhau, va mot bang chi so khong ghi minh do cai gi la mot bang de bi doc nham.
    duong = (
        "TRO LY THAT (qua cong cu, model tu viet truy van)"
        if qua_cong_cu
        else ("TANG TRUY HOI (cau hoi vao thang knowledge.search)")
    )
    print(f"{len(outcomes)} cau  ·  do duong: {duong}" + chr(10))

    if not outcomes:
        return False
    recall, bo_recall = trung_binh([o.recall for o in outcomes])
    faith, bo_faith = trung_binh([o.faithfulness for o in outcomes])
    p95 = percentile([float(o.latency_ms) for o in outcomes], 0.95)

    _dong("Recall@5", recall, RECALL_MIN, bo_recall, True)
    _dong("Faithfulness", faith, FAITHFULNESS_MIN, bo_faith, True)
    _dong("Latency p95 (ms)", p95, float(LATENCY_P95_MAX_MS), 0, False)

    neo_r, _ = trung_binh([o.neo_recall for o in outcomes])
    if neo_r is not None:
        print(f"  ....  {'Neo trong ngu canh':<20} {neo_r:>7.3f}   (tham khao, khong phai nguong)")

    if ragas:
        print(chr(10) + "RAGAS:")
        for ten, xs, nguong in (
            ("Context Recall", [o.context_recall for o in outcomes], CONTEXT_RECALL_MIN),
            ("Context Precision", [o.context_precision for o in outcomes], CONTEXT_PRECISION_MIN),
            ("Faithfulness (y)", [o.claim_faithfulness for o in outcomes], CLAIM_FAITHFULNESS_MIN),
        ):
            gia_tri, bo = trung_binh(xs)
            _dong(ten, gia_tri, nguong, bo, True)

        rel, bo_rel = trung_binh([o.answer_relevance for o in outcomes])
        if rel is not None:
            ghi_chu = f" (bo qua {bo_rel})" if bo_rel else ""
            print(
                f"  ....  {'Answer Relevance':<20} {rel:>7.3f}   "
                f"(tham khao, chua hieu chuan{ghi_chu})"
            )
        missing_judgments = [
            o
            for o in outcomes
            if (o.claim_faithfulness is None and o.refused is not True)
            or (o.row.answerable and (o.context_recall is None or o.context_precision is None))
        ]
        if missing_judgments:
            print(f"  TRUOT missing required RAGAS judgments: {len(missing_judgments)}")

    no_answer = no_answer_summary(
        [{"answerable": o.row.answerable, "refused": o.refused} for o in outcomes], len(outcomes)
    )
    print(f"  No-answer: {json.dumps(no_answer, sort_keys=True)}")
    for name in ("required_claims_recall", "forbidden_claims_rate"):
        value, missing = trung_binh([getattr(outcome, name) for outcome in outcomes])
        print(f"  Final {name}: {value}; unmeasured/not-applicable={missing}")

    if qua_cong_cu:
        khong_goi = [o for o in outcomes if not o.truy_van]
        print(
            chr(10)
            + f"  Model tu viet truy van: {len(outcomes) - len(khong_goi)}/{len(outcomes)} cau"
        )
        if khong_goi:
            # KHONG goi cong cu lan nao la mot ket qua dang doc, khong phai cho trong:
            # do chinh la kieu hong da chiem 3/4 cau giao tap hop ngay 10/09.
            print(f"  KHONG goi cong cu ({len(khong_goi)}): {[o.row.id for o in khong_goi]}")

    _theo_loai(outcomes, ragas)

    kem = [
        o
        for o in outcomes
        if (o.faithfulness is not None and o.faithfulness < FAITHFULNESS_MIN)
        or (o.recall is not None and o.recall < RECALL_MIN)
        or (o.context_recall is not None and o.context_recall < CONTEXT_RECALL_MIN)
    ]
    if kem:
        print(chr(10) + "Cau keo diem xuong:")
        for o in kem[:12]:
            r = "  —  " if o.recall is None else f"{o.recall:.2f}"
            cr = "  —  " if o.context_recall is None else f"{o.context_recall:.2f}"
            print(
                f"  [{o.row.id}] {o.row.loai:<14} recall={r} ctx_recall={cr} faith={o.faithfulness}"
            )

    categories: dict[str, list[Outcome]] = defaultdict(list)
    for outcome in outcomes:
        categories[outcome.row.loai].append(outcome)
    category_pass = {
        category: measured_quality_gate(items, ragas, qua_cong_cu)
        for category, items in categories.items()
    }
    print(f"  Category measured gates: {json.dumps(category_pass, sort_keys=True)}")
    return measured_quality_gate(outcomes, ragas, qua_cong_cu) and all(category_pass.values())


def _theo_loai(outcomes: list[Outcome], ragas: bool) -> None:
    """Tach chi so theo NHOM cau hoi.

    Mot trung binh chung giau mat viec mot nhom dang hong. Do khong phai gia thiet:
    ngay 10/09/2026 bo eval bao Recall@5 = 0,886 trong khi lop cau "mon nao co X va Y"
    dang o 0/4 — vi lop do chi chiem 3/25 cau nen no chim trong trung binh.
    """
    nhom: dict[str, list[Outcome]] = defaultdict(list)
    for o in outcomes:
        nhom[o.row.loai].append(o)
    if len(nhom) < 2:
        return

    print(chr(10) + "Theo loai cau hoi:")
    print(f"  {'loai':<16} {'n':>3}  {'faith':>6} {'ctx_rec':>8} {'ctx_prec':>9} {'neo':>6}")
    for loai in sorted(nhom):
        os_ = nhom[loai]
        f, _ = trung_binh([o.faithfulness for o in os_])
        cr, _ = trung_binh([o.context_recall for o in os_])
        cp, _ = trung_binh([o.context_precision for o in os_])
        neo, _ = trung_binh([o.neo_recall for o in os_])

        def s(x: float | None) -> str:
            return "     —" if x is None else f"{x:>6.3f}"

        print(
            f"  {loai:<16} {len(os_):>3}  {s(f)} {s(cr):>8} {s(cp):>9} {s(neo):>6}"
            if ragas
            else f"  {loai:<16} {len(os_):>3}  {s(f)} {'':>8} {'':>9} {s(neo):>6}"
        )


def run_config(ragas: bool, qua_cong_cu: bool, split: str) -> dict[str, Any]:
    settings = get_settings()
    reply = MODELS["reply"]
    judge = MODELS["summarize"]
    return {
        **source_identity(Path(__file__).resolve().parent.parent),
        "split": split,
        "ragas": ragas,
        "pipeline": "tool" if qua_cong_cu else "retrieval",
        "reply_model": reply.id,
        "reply_max_tokens": reply.max_tokens,
        "reply_effort": reply.effort,
        "reply_endpoint_sha256": hashlib.sha256(
            (reply.base_url or "default-openai").encode()
        ).hexdigest(),
        "judge_model": judge.id,
        "judge_max_tokens": judge.max_tokens,
        "judge_effort": judge.effort,
        "judge_endpoint_sha256": hashlib.sha256(
            (judge.base_url or "default-openai").encode()
        ).hexdigest(),
        "embedding_provider": settings.EMBEDDING_PROVIDER,
        "embedding_model": settings.EMBEDDING_MODEL,
        "embedding_dimensions": settings.EMBEDDING_DIM,
        "rerank_provider": settings.RERANK_PROVIDER,
        "rerank_model": settings.RERANK_MODEL,
        "rerank_min_score": settings.RERANK_MIN_SCORE,
        "rag_max_distance": settings.RAG_MAX_DISTANCE,
        "top_k": K,
        "metric_definition_version": 2,
        "tool_recall_policy": "first_k_unique_evidence_in_call_order",
        "thresholds": {
            "recall": RECALL_MIN,
            "faithfulness": FAITHFULNESS_MIN,
            "context_recall": CONTEXT_RECALL_MIN,
            "context_precision": CONTEXT_PRECISION_MIN,
            "claim_faithfulness": CLAIM_FAITHFULNESS_MIN,
            "latency_p95_ms": LATENCY_P95_MAX_MS,
            "no_answer_false_answer_max": NO_ANSWER_FALSE_ANSWER_MAX,
        },
        "react_max_iterations": settings.REACT_MAX_ITERATIONS,
        "react_deadline_ms": settings.REACT_DEADLINE_MS,
    }


def locked_config_hash(config: dict[str, Any]) -> str:
    return config_hash(
        {
            key: value
            for key, value in config.items()
            if key not in {"commit", "worktree_dirty", "split"}
        }
    )


async def main() -> int:
    _cho_phep_in_tieng_viet()
    parser = argparse.ArgumentParser(
        description="Paid eval; development only unless test explicitly confirmed"
    )
    parser.add_argument("dataset", nargs="?", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--ragas", action="store_true")
    parser.add_argument("--qua-cong-cu", action="store_true")
    parser.add_argument("--split", choices=("development", "test"), default="development")
    parser.add_argument("--confirm-test", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--review-manifest", type=Path)
    parser.add_argument("--print-config", action="store_true", help="Offline config and lock hash")
    args = parser.parse_args()
    dataset, ragas, qua_cong_cu = args.dataset, args.ragas, args.qua_cong_cu
    config = run_config(ragas, qua_cong_cu, args.split)
    if args.print_config:
        print(
            json.dumps({"config": config, "locked_eval_config_sha256": locked_config_hash(config)})
        )
        return EXIT_DAT
    if args.split == "test" and not args.confirm_test:
        print("Test split requires --confirm-test after configuration is locked.", file=sys.stderr)
        return EXIT_TRUOT
    if args.output and args.output.exists():
        print("Artifact already exists; use a new path.", file=sys.stderr)
        return EXIT_TRUOT

    try:
        dataset_hash = hashlib.sha256(dataset.read_bytes()).hexdigest()
        rows = load_dataset(dataset)
        all_records = load_and_validate(dataset)
        review = check_review(
            dataset,
            all_records,
            args.review_manifest,
            locked_config_hash(config) if args.split == "test" else None,
        )
    except (ValueError, OSError) as error:
        print(f"Dataset khong hop le: {error}", file=sys.stderr)
        return EXIT_CHUA_CO_DU_LIEU if "placeholder" in str(error) else EXIT_TRUOT
    if not rows:
        print(f"Khong co cau nao trong {dataset}.", file=sys.stderr)
        return EXIT_CHUA_CO_DU_LIEU

    deficits = coverage_deficits(all_records)
    readiness = {
        "total": len(all_records),
        "minimum_total": MINIMUM_TOTAL,
        "coverage_deficits": deficits,
        "annotation_deficits": annotation_deficits(all_records),
        "review": review,
        "ready": len(all_records) >= MINIMUM_TOTAL
        and not deficits
        and not annotation_deficits(all_records)
        and review["attested"],
    }
    if args.split == "test" and not readiness["ready"]:
        print(
            "Test split requires complete coverage and reviewed, locked dataset.", file=sys.stderr
        )
        return EXIT_CHUA_CO_DU_LIEU

    rows = [row for row in rows if split_for_id(row.id) == args.split]
    if not rows:
        print(f"No questions in {args.split} split.", file=sys.stderr)
        return EXIT_CHUA_CO_DU_LIEU

    if is_placeholder(rows):
        # KHONG tra ve 0. Mot bo eval chay tren du lieu mau roi bao "dat" con te hon
        # khong co eval: no cho ta niem tin ma no khong he kiem chung dieu gi.
        print(
            "qa.jsonl mới chỉ có dòng mẫu. Cần 50 câu VIẾT TAY từ tài liệu thật "
            "(xem docs/plan-thi-cong.md section 10).",
            file=sys.stderr,
        )
        return EXIT_CHUA_CO_DU_LIEU

    try:
        selected_ids = {row.id for row in rows}
        records = [record for record in load_and_validate(dataset) if record.id in selected_ids]
        checked = await check_corpus(records)
        if checked.exit_code:
            print(
                f"Corpus preflight rejected: {len(checked.issues)} metadata/annotation issues.",
                file=sys.stderr,
            )
            return checked.exit_code
        if hashlib.sha256(dataset.read_bytes()).hexdigest() != dataset_hash:
            print("Dataset changed during preflight; no provider calls made.", file=sys.stderr)
            return EXIT_TRUOT
        # Tuan tu, khong gather: chay song song lam so do do tre vo nghia, ma do tre
        # la mot trong cac nguong.
        #
        # MOT cau hong khong duoc vut ca luot chay. Do that 10/09/2026: hai lan chay
        # lien tiep deu chet o mot `APITimeoutError` giua chung, va ca hai lan deu mat
        # sach ket qua cua nhung cau da chay xong — tuc da tra tien cho chung roi ma
        # khong doc duoc gi. Voi mot job nightly thi do la kieu hong te nhat: no chi
        # can mot lan mang chap la khong bao gio co so lieu.
        outcomes: list[Outcome] = []
        hong: list[tuple[str, str]] = []
        for row in rows:
            try:
                chay = run_one_qua_cong_cu if qua_cong_cu else run_one
                outcomes.append(await chay(row, ragas))
            except Exception as error:
                hong.append((row.id, type(error).__name__))
                _log.error("cau eval that bai, bo qua", cau=row.id, error_type=type(error).__name__)

        dat = report(outcomes, ragas, qua_cong_cu) if outcomes else False
        if hong:
            print(chr(10) + f"KHONG CHAY DUOC {len(hong)}/{len(rows)} cau:")
            for cau, loi in hong:
                print(f"  [{cau}] {loi}")
            print("  (su co ha tang, KHONG tinh vao cac chi so tren)")
        try:
            after = await corpus_fingerprint()
        except Exception as error:
            after = None
            print(f"Final corpus metadata unavailable ({type(error).__name__}).", file=sys.stderr)
        try:
            dataset_stable = hashlib.sha256(dataset.read_bytes()).hexdigest() == dataset_hash
        except OSError as error:
            dataset_stable = False
            print(f"Final dataset unavailable ({type(error).__name__}).", file=sys.stderr)
        try:
            source_stable = (
                source_identity(Path(__file__).resolve().parent.parent)["source_sha256"]
                == config["source_sha256"]
            )
        except Exception as error:
            source_stable = False
            print(f"Final source identity unavailable ({type(error).__name__}).", file=sys.stderr)
        stable = checked.fingerprint == after and dataset_stable and source_stable
        if not stable:
            print(
                "Dataset/corpus/source changed or could not be verified; run cannot pass.",
                file=sys.stderr,
            )
        if args.output:
            measurements = [
                {
                    "id": o.row.id,
                    "category": o.row.loai,
                    "latency_ms": o.latency_ms,
                    "answerable": o.row.answerable,
                    "refused": o.refused,
                    "metric_states": metric_states(o, ragas, qua_cong_cu),
                    **{name: getattr(o, name) for name in METRICS},
                }
                for o in outcomes
            ]
            artifact = build_artifact(
                selected=[{"id": row.id, "category": row.loai} for row in rows],
                outcomes=measurements,
                failures=[{"id": key, "error_type": kind} for key, kind in hong],
                dataset_sha256=dataset_hash,
                corpus_before=checked.fingerprint,
                corpus_after=after,
                config=config,
                measured_gate_passed=dat,
                dataset_stable=dataset_stable,
                source_stable=source_stable,
                dataset_readiness=readiness,
                category_gate_passed={
                    category: measured_quality_gate(
                        [outcome for outcome in outcomes if outcome.row.loai == category],
                        ragas,
                        qua_cong_cu,
                    )
                    and not any(
                        row.loai == category and row.id in {key for key, _ in hong} for row in rows
                    )
                    for category in {row.loai for row in rows}
                },
            )
            write_artifact(args.output, artifact)
        return EXIT_DAT if dat and not hong and stable else EXIT_TRUOT
    except Exception as error:
        print(f"Eval failed ({type(error).__name__}).", file=sys.stderr)
        return EXIT_TRUOT
    finally:
        await close_db()
        await close_redis()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
