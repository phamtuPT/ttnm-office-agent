/** Màn hình chào khi chưa mở tệp: giới thiệu ngắn + các việc mẫu (đề xuất mục 3.3) bấm để điền sẵn yêu cầu. */

export const SCENARIOS = [
  { title: "Lập bảng tính", tag: "xlsx", text: "Tạo bảng doanh thu 12 tháng, có dòng tổng và biểu đồ cột",
    desc: "Công thức SUM, định dạng số và biểu đồ gốc gắn với vùng dữ liệu." },
  { title: "Sửa đúng vùng chọn", tag: "xlsx", text: "Tô đỏ các giá trị âm",
    desc: "Kéo chọn vùng ô trên khung xem trước rồi gửi — trợ lý chỉ sửa trong vùng đó." },
  { title: "Phân tích & báo cáo", tag: "docx", text: "Chạy hồi quy doanh thu theo chi phí quảng cáo và viết báo cáo Word có bảng kết quả và hình minh hoạ",
    desc: "Phân tích bằng pandas/statsmodels trong sandbox, rồi soạn báo cáo." },
  { title: "Làm slide", tag: "pptx", text: "Làm 5 slide giới thiệu sản phẩm, thiết kế gọn, có ghi chú thuyết trình",
    desc: "Slide 16:9, tự xem lại ảnh slide để sửa chữ tràn và chồng lấn." },
  { title: "Rà soát, dịch, so sánh", tag: "docx", text: "Rà soát tài liệu, đề xuất sửa bằng Track Changes và ghi nhận xét",
    desc: "Đề xuất sửa để bạn Chấp nhận/Từ chối trong Word, dịch giữ định dạng, so sánh phiên bản." },
  { title: "Từ ảnh ra tài liệu", tag: "img", text: "Chuyển ảnh hoá đơn này thành bảng Excel và tính tổng",
    desc: "Đính kèm ảnh chụp bảng giá, hoá đơn, công văn — trợ lý đọc và dựng thành tệp sửa được." },
];

export function Hero({ onPick, onUpload, providerLabel }: { onPick: (text: string) => void; onUpload: (f: FileList) => void; providerLabel: string }) {
  return (
    <section className="hero" aria-labelledby="hero-title">
      <div className="stamp" aria-hidden>BTL / 2026</div>
      <p className="eyebrow">Tương tác người máy · Trợ lý AI đa phương thức</p>
      <h1 id="hero-title">office<span className="dotc">.</span>agent<span className="dotc">.</span></h1>
      <div className="lead">
        <p>Sẽ thế nào nếu chỉ cần <em>nói điều bạn cần</em>, rồi tệp Word, Excel, PowerPoint thật tự được tạo và sửa xong?</p>
        <p>Gõ, nói hoặc gửi ảnh. Trợ lý lập kế hoạch, làm trực tiếp trên tệp, giữ định dạng gốc — xem trước ngay bên cạnh, và mọi yêu cầu đều hoàn tác được bằng một nhấp.</p>
      </div>
      <div className="hero-actions">
        <label className="btn solid">
          Tải tệp lên
          <input type="file" accept=".xlsx,.docx,.pptx" multiple hidden
            onChange={(e) => { if (e.target.files) onUpload(e.target.files); e.target.value = ""; }} />
        </label>
        <button className="btn primary" onClick={() => onPick(SCENARIOS[0].text)}>Thử tạo bảng tính mẫu</button>
        <span className="pill"><span className="dot" /> Mô hình: {providerLabel}</span>
      </div>
      <div className="stats">
        <div className="stat"><b>03</b><span>định dạng Office</span></div>
        <div className="stat"><b>40+</b><span>thao tác trên tệp</span></div>
        <div className="stat"><b>20</b><span>thế hệ sao lưu</span></div>
        <div className="stat"><b>01</b><span>nhấp để hoàn tác</span></div>
      </div>
      <div className="section-title">
        <span className="slashes">//</span><h3>Việc mẫu</h3><span className="count">{SCENARIOS.length}</span>
      </div>
      <div className="cards">
        {SCENARIOS.map((s, i) => (
          <button key={s.title} className="card" onClick={() => onPick(s.text)} style={{ animationDelay: `${i * 60}ms` }}>
            <span className="num" aria-hidden>{String(i + 1).padStart(2, "0")}</span>
            <h4>{s.title}</h4>
            <p>{s.desc}</p>
            <span className="meta">
              <span className={`kind ${s.tag === "img" ? "docx" : s.tag}`}>{s.tag === "img" ? "ảnh" : s.tag}</span>
              bấm để điền sẵn yêu cầu
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}
