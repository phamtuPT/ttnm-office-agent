import type { ConfirmRequest } from "../types";
import { TOOL_LABELS } from "../types";

export function ConfirmDialog({ req, onAnswer }: { req: ConfirmRequest; onAnswer: (ok: boolean) => void }) {
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
      <div className="modal">
        <h3 id="confirm-title">Xác nhận thao tác</h3>
        <p>
          Trợ lý muốn thực hiện <b>{TOOL_LABELS[req.tool] ?? req.tool}</b>. Bạn vẫn có thể hoàn tác sau đó.
        </p>
        <pre>{JSON.stringify(req.args, null, 2)}</pre>
        <div className="modal-actions">
          <button className="btn" onClick={() => onAnswer(false)}>Từ chối</button>
          <button className="btn danger" onClick={() => onAnswer(true)} autoFocus>Đồng ý</button>
        </div>
      </div>
    </div>
  );
}
