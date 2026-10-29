import { BarChart3, CheckCircle2, Download, Send } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";
import { api } from "../api";
import { type BarProps, TopBar } from "../components/TopBar";
import type { SusSummary } from "../types";

/** Phiếu SUS (10 câu, thang 1–5) cho buổi thử nghiệm với người dùng — đề xuất mục 8.2. */
export function SusPage({ bar, onError }: { bar: BarProps; onError: (m: string) => void }) {
  const [qs, setQs] = useState<{ questions: string[]; scale: string[] } | null>(null);
  const [answers, setAnswers] = useState<(number | null)[]>(Array(10).fill(null));
  const [participant, setParticipant] = useState("");
  const [comment, setComment] = useState("");
  const [result, setResult] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.susQuestions().then(setQs).catch((e) => onError(e.message));
  }, []);

  const missing = answers.map((a, i) => (a === null ? i + 1 : 0)).filter(Boolean);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (missing.length) return;
    setBusy(true);
    try {
      setResult((await api.submitSus(answers as number[], participant, comment)).score);
    } catch (err) {
      onError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="app">
      <TopBar bar={bar} activeId={null} />
      <div className="surface">
        <main className="home-main">
          <div className="home-inner sus">
            <header className="phead">
              <p className="eyebrow">Đánh giá mức độ dễ dùng (SUS)</p>
              <h1 className="title">Phiếu đánh giá trải nghiệm</h1>
            </header>
            {result !== null ? (
              <section className="card sus-done" aria-live="polite">
                <CheckCircle2 size={28} aria-hidden />
                <h2>Cảm ơn bạn đã góp ý</h2>
                <p>Điểm SUS của phiếu này: <b>{result}</b> / 100.</p>
                <div className="row">
                  <button className="btn" onClick={() => { setResult(null); setAnswers(Array(10).fill(null)); setParticipant(""); setComment(""); }}>
                    Phiếu mới
                  </button>
                  <a className="btn" href="#/sus/ket-qua"><BarChart3 size={16} aria-hidden /> Xem tổng hợp</a>
                </div>
              </section>
            ) : !qs ? <p className="hint">Đang tải…</p> : (
              <form className="card sus-form" onSubmit={submit}>
                <p className="muted">Chọn mức đồng ý với từng câu sau khi đã dùng thử hệ thống (1 = hoàn toàn không đồng ý,
                  5 = hoàn toàn đồng ý). Không cần ghi tên thật.</p>
                <label className="field">Mã người tham gia (ví dụ P01)
                  <input value={participant} onChange={(e) => setParticipant(e.target.value)} maxLength={100} />
                </label>
                <ol className="sus-list">
                  {qs.questions.map((q, i) => (
                    <li key={i}>
                      <fieldset>
                        <legend className="sr-only">{q}</legend>
                        <span className="q" aria-hidden>{q}</span>
                        <div className="likert">
                          {qs.scale.map((label, v) => (
                            <label key={v} title={label} className={answers[i] === v + 1 ? "on" : ""}>
                              <input type="radio" name={`q${i}`} value={v + 1} checked={answers[i] === v + 1}
                                onChange={() => setAnswers((a) => a.map((x, j) => (j === i ? v + 1 : x)))}
                                aria-label={`${v + 1} — ${label}`} />
                              <span aria-hidden>{v + 1}</span>
                            </label>
                          ))}
                        </div>
                      </fieldset>
                    </li>
                  ))}
                </ol>
                <div className="likert-legend" aria-hidden><span>{qs.scale[0]}</span><span>{qs.scale[4]}</span></div>
                <label className="field">Nhận xét thêm (không bắt buộc)
                  <textarea rows={3} value={comment} onChange={(e) => setComment(e.target.value)} maxLength={4000} />
                </label>
                {missing.length > 0 && <p className="muted">Còn {missing.length} câu chưa chọn: {missing.join(", ")}.</p>}
                <button className="btn solid" type="submit" disabled={busy || missing.length > 0}>
                  <Send size={16} aria-hidden /> Gửi phiếu
                </button>
              </form>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}

/** Tổng hợp SUS: số phiếu, điểm trung bình so với mục tiêu ≥ 70, điểm từng câu, xuất CSV. */
export function SusResultsPage({ bar, onError }: { bar: BarProps; onError: (m: string) => void }) {
  const [s, setS] = useState<SusSummary | null>(null);
  useEffect(() => {
    api.susSummary().then(setS).catch((e) => onError(e.message));
  }, []);
  return (
    <div className="app">
      <TopBar bar={bar} activeId={null} />
      <div className="surface">
        <main className="home-main">
          <div className="home-inner sus">
            <header className="phead">
              <p className="eyebrow">Đánh giá mức độ dễ dùng (SUS)</p>
              <h1 className="title">Kết quả SUS</h1>
            </header>
            {!s ? <p className="hint">Đang tải…</p> : (
              <>
                <div className="sus-stats">
                  <div className="card"><small>Số phiếu</small><b>{s.n}</b></div>
                  <div className="card"><small>Điểm trung bình</small><b>{s.mean ?? "—"}</b></div>
                  <div className="card"><small>Độ lệch chuẩn</small><b>{s.sd ?? "—"}</b></div>
                  <div className={`card ${s.meets_target ? "ok" : "warn"}`}><small>Mục tiêu ≥ {s.target}</small>
                    <b>{s.n ? (s.meets_target ? "Đạt" : "Chưa đạt") : "—"}</b></div>
                </div>
                <section className="card">
                  <h2 className="section-heading">Điểm trung bình từng câu (1–5)</h2>
                  <ol className="sus-bars">
                    {s.per_question.map((v, i) => (
                      <li key={i}>
                        <span>Câu {i + 1}{i % 2 ? " (tiêu cực)" : ""}</span>
                        <span className="bar"><span style={{ width: `${((v ?? 0) / 5) * 100}%` }} /></span>
                        <b>{v ?? "—"}</b>
                      </li>
                    ))}
                  </ol>
                </section>
                <div className="row">
                  <a className="btn" href={api.susExportUrl} download><Download size={16} aria-hidden /> Xuất CSV</a>
                  <a className="btn" href="#/sus">Mở phiếu đánh giá</a>
                </div>
              </>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
