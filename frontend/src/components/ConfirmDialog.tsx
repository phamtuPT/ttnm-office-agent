import type { ConfirmRequest } from "../types";
import { TOOL_LABELS } from "../types";

/** Hỏi trước thao tác phá huỷ (xoá sheet/slide) hoặc chạy mã phân tích (người dùng đọc được mã trước khi chạy). */
export function ConfirmDialog({ req, onAnswer }: { req: ConfirmRequest; onAnswer: (ok: boolean) => void }) {
  const isCode = req.tool === "run_python";
  const { code, ...rest } = req.args as { code?: string };
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
      <div className={`modal ${isCode ? "wide" : ""}`}>
        <h3 id="confirm-title">{isCode ? "Chạy mã phân tích dữ liệu?" : "Xác nhận thao tác"}</h3>
        {isCode ? (
          <p className="muted">
            Mã dưới đây chạy trong <b>sandbox cách ly, không có mạng</b>, chỉ đọc bản sao các tệp được liệt kê.
            Kết quả (hình, bảng) sẽ được đưa vào phiên để bạn xem trước khi dùng.
          </p>
        ) : (
          <p className="muted">
            Trợ lý muốn thực hiện <b>{TOOL_LABELS[req.tool] ?? req.tool}</b>. Bạn vẫn có thể hoàn tác sau đó.
          </p>
        )}
        {isCode && <pre>{code}</pre>}
        <pre>{JSON.stringify(isCode ? rest : req.args, null, 2)}</pre>
        <div className="modal-actions">
          <button className="btn" onClick={() => onAnswer(false)}>Từ chối</button>
          <button className={`btn ${isCode ? "primary" : "danger"}`} onClick={() => onAnswer(true)} autoFocus>
            {isCode ? "Chạy" : "Đồng ý"}
          </button>
        </div>
      </div>
    </div>
  );
}
