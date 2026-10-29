import ReactMarkdown, { type Components } from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import { markdownWithMath } from "./MathText";

// Liên kết mở tab mới; HTML thô trong câu trả lời bị bỏ qua (skipHtml) để không chạy nội dung lạ
const COMPONENTS: Components = {
  a: ({ node: _node, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer" />,
  table: ({ node: _node, ...props }) => (
    <div className="md-table"><table {...props} /></div>
  ),
};

const INLINE: Components = { ...COMPONENTS, p: ({ node: _node, ...props }) => <span {...props} /> };
const KATEX: [typeof rehypeKatex, { throwOnError: boolean }] = [rehypeKatex, { throwOnError: false }];

/** Hiển thị Markdown (in đậm, mã, danh sách, bảng, công thức $...$) trong trả lời của trợ lý. */
export function Markdown({ text, inline = false }: { text: string; inline?: boolean }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[KATEX]}
      components={inline ? INLINE : COMPONENTS} skipHtml>
      {markdownWithMath(text)}
    </ReactMarkdown>
  );
}
