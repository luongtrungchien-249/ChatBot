"""Chi so cua bo eval. Moi file mot chi so.

Khung cu — re, khong doc tai lieu:

    recall.py        Recall@5 — chunk dung co nam trong top 5 khong. Muc tieu > 0,85
    faithfulness.py  LLM-as-judge cho DIEM TONG — co bam tai lieu khong. Muc tieu > 0,9
    latency.py       p95 toan duong ong. Muc tieu < 5s

Khung RAGAS — bat bang `--ragas`, bon chi so, moi cai bat mot kieu hong khac:

    context_recall.py      ngu canh co DU de dung nen dap an chuan khong
    context_precision.py   lay ve co dung viec khong, va co xep len tren khong
    claim_faithfulness.py  nhu faithfulness nhung DEM TUNG Y thay vi cho diem tong
    answer_relevance.py    cau tra loi co dung trong tam cau hoi khong

    _cham.py               phan van chuyen dung chung (goi model, doc phan quyet)

Bon chi so RAGAS KHONG dung `chunk_id`, nen chung song qua moi lan nap lai kho —
`expected_chunk_ids` da phai anh xa lai hai lan trong hai ngay 10-11/09/2026.

Tach moi chi so mot file chu khong gop mot: doi cach do mot chi so khong duoc lam
thay doi so lieu cua cac chi so kia, neu khong thi khong so sanh duoc voi lan chay
truoc. `_cham.py` la ngoai le co chu y — no chi lo viec goi model va doc ket qua, con
LUAT CHAM va CACH GOP DIEM thi moi chi so tu giu lay.
"""
