import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

// Liên kết mở tab mới; HTML thô trong câu trả lời bị bỏ qua (skipHtml) để không chạy nội dung lạ
const COMPONENTS: Components = {
  a: ({ node: _node, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer" />,
  table: ({ node: _node, ...props }) => (
    <div className="md-table"><table {...props} /></div>
  ),
};

const INLINE: Components = { ...COMPONENTS, p: ({ node: _node, ...props }) => <span {...props} /> };

/** Hiển thị Markdown (in đậm, mã, danh sách, bảng) trong trả lời của trợ lý. */
export function Markdown({ text, inline = false }: { text: string; inline?: boolean }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={inline ? INLINE : COMPONENTS} skipHtml>
      {text}
    </ReactMarkdown>
  );
}
