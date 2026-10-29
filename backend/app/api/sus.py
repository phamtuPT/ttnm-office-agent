"""Phiếu SUS (System Usability Scale) cho buổi thử nghiệm với người dùng — đề xuất mục 8.2, mục tiêu ≥ 70 điểm."""
import csv
import io
import statistics

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import current_user, require_admin
from ..db import SusResponse, User
from .deps import get_db, iso

router = APIRouter(prefix="/api/sus", tags=["sus"])

# 10 câu SUS chuẩn (Brooke, 1996), bản tiếng Việt. Câu lẻ tích cực, câu chẵn tiêu cực.
QUESTIONS = [
    "Tôi nghĩ rằng tôi sẽ muốn dùng hệ thống này thường xuyên.",
    "Tôi thấy hệ thống phức tạp một cách không cần thiết.",
    "Tôi thấy hệ thống dễ sử dụng.",
    "Tôi nghĩ rằng tôi cần người có chuyên môn kỹ thuật giúp thì mới dùng được hệ thống này.",
    "Tôi thấy các chức năng của hệ thống được kết hợp với nhau tốt.",
    "Tôi thấy hệ thống có quá nhiều chỗ không nhất quán.",
    "Tôi nghĩ hầu hết mọi người sẽ học cách dùng hệ thống này rất nhanh.",
    "Tôi thấy hệ thống rất rườm rà khi sử dụng.",
    "Tôi cảm thấy rất tự tin khi dùng hệ thống.",
    "Tôi phải học nhiều thứ trước khi có thể bắt đầu dùng hệ thống này.",
]


def sus_score(answers: list[int]) -> float:
    """Câu lẻ: điểm − 1; câu chẵn: 5 − điểm; tổng × 2,5 → thang 0–100."""
    return sum((a - 1) if i % 2 == 0 else (5 - a) for i, a in enumerate(answers)) * 2.5


class SusIn(BaseModel):
    answers: list[int] = Field(min_length=10, max_length=10)
    participant: str = Field("", max_length=100)
    comment: str = Field("", max_length=4000)


@router.get("/questions")
def questions():
    return {"questions": QUESTIONS, "scale": ["Hoàn toàn không đồng ý", "Không đồng ý", "Trung lập", "Đồng ý",
                                              "Hoàn toàn đồng ý"]}


@router.post("")
def submit(body: SusIn, db: Session = Depends(get_db), user: User | None = Depends(current_user)):
    if any(not 1 <= a <= 5 for a in body.answers):
        raise HTTPException(422, "Mỗi câu chọn từ 1 đến 5")
    r = SusResponse(user_id=user.id if user else None, participant=body.participant.strip(), answers=body.answers,
                    score=sus_score(body.answers), comment=body.comment.strip())
    db.add(r)
    db.commit()
    return {"id": r.id, "score": r.score}


@router.get("/summary")
def summary(db: Session = Depends(get_db), _admin=Depends(require_admin)):
    rows = db.query(SusResponse).order_by(SusResponse.created_at).all()
    scores = [r.score for r in rows]
    return {
        "n": len(rows),
        "mean": round(statistics.mean(scores), 1) if scores else None,
        "sd": round(statistics.stdev(scores), 1) if len(scores) > 1 else None,
        "min": min(scores, default=None), "max": max(scores, default=None),
        "target": 70, "meets_target": bool(scores) and statistics.mean(scores) >= 70,
        "per_question": [round(statistics.mean(r.answers[i] for r in rows), 2) if rows else None for i in range(10)],
        "responses": [{"participant": r.participant, "score": r.score, "comment": r.comment,
                       "created_at": iso(r.created_at)} for r in rows],
    }


@router.get("/export.csv")
def export(db: Session = Depends(get_db), _admin=Depends(require_admin)):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["participant", *[f"Q{i}" for i in range(1, 11)], "score", "comment", "created_at"])
    for r in db.query(SusResponse).order_by(SusResponse.created_at):
        w.writerow([r.participant, *r.answers, r.score, r.comment, iso(r.created_at)])
    # BOM để Excel mở đúng tiếng Việt
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="sus.csv"'})
