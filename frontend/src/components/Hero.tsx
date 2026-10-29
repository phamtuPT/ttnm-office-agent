/** Màn hình chào khi chưa mở tệp: giới thiệu ngắn + các việc mẫu (đề xuất mục 3.3) bấm để điền sẵn yêu cầu. */

export const SCENARIOS = [
  { title: "Lập bảng tính", tag: "xlsx", text: "Tạo bảng doanh thu 12 tháng, có dòng tổng và biểu đồ cột",
    desc: "Công thức SUM, định dạng số và biểu đồ gốc gắn với vùng dữ liệu." },
  { title: "Sửa đúng vùng chọn", tag: "xlsx", text: "Tô đỏ các giá trị âm",
    desc: "Kéo chọn vùng ô trên khung xem trước trước khi gửi — trợ lý chỉ sửa trong vùng đó." },
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
      <p className="eyebrow"><b>office</b> agent / trợ lý văn phòng đa phương thức</p>
      <h1 id="hero-title">Nói điều bạn cần, <em>tệp Office thật</em> sẽ được làm xong.</h1>
      <p className="lead">
        Giao việc bằng chữ, giọng nói hoặc ảnh. Trợ lý lập kế hoạch, tạo hoặc sửa trực tiếp tệp Word, Excel,
        PowerPoint — giữ nguyên định dạng gốc, xem trước ngay bên phải, và mọi yêu cầu đều hoàn tác được bằng một nhấp.
      </p>
      <div className="hero-actions">
        <label className="btn primary">
          Tải tệp lên
          <input type="file" accept=".xlsx,.docx,.pptx" multiple hidden
            onChange={(e) => { if (e.target.files) onUpload(e.target.files); e.target.value = ""; }} />
        </label>
        <button className="btn" onClick={() => onPick(SCENARIOS[0].text)}>Thử tạo bảng tính mẫu</button>
        <span className="pill"><span className="dot" /> Mô hình: {providerLabel}</span>
      </div>
      <div className="stats">
        <div className="stat"><b>3</b><span>định dạng Office</span></div>
        <div className="stat"><b>40+</b><span>thao tác trên tệp</span></div>
        <div className="stat"><b>20</b><span>thế hệ sao lưu / tệp</span></div>
        <div className="stat"><b>1</b><span>nhấp để hoàn tác</span></div>
      </div>
      <div className="section-title">
        <span className="eyebrow">//</span><h3>Việc mẫu</h3><span className="dim" style={{ fontSize: 13 }}>bấm để điền sẵn vào ô soạn</span>
      </div>
      <div className="cards">
        {SCENARIOS.map((s, i) => (
          <button key={s.title} className="card" onClick={() => onPick(s.text)}>
            <span className="num" aria-hidden>{String(i + 1).padStart(2, "0")}</span>
            <h4>{s.title}</h4>
            <p>{s.desc}</p>
            <span className="tags"><span className={`kind ${s.tag === "img" ? "docx" : s.tag}`}>{s.tag === "img" ? "ảnh" : s.tag}</span></span>
          </button>
        ))}
      </div>
    </section>
  );
}
