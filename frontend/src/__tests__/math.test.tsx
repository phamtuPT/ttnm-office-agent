import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Markdown } from "../components/Markdown";
import { MathText, markdownWithMath, splitMath } from "../components/MathText";

describe("công thức toán", () => {
  it("tách $...$ giống backend, không nhầm giá tiền", () => {
    expect(splitMath("Diện tích $S = \\pi r^2$.")).toEqual([
      { kind: "text", value: "Diện tích " },
      { kind: "inline", value: "S = \\pi r^2" },
      { kind: "text", value: "." },
    ]);
    expect(splitMath("$$x^2 = 4$$")).toEqual([{ kind: "display", value: "x^2 = 4" }]);
    expect(splitMath("Giá $100 và $200").every((p) => p.kind === "text")).toBe(true);
    expect(markdownWithMath("Giá $100 và $x$")).toBe("Giá \\$100 và $x$");
  });

  it("chat hiển thị công thức bằng KaTeX, giá tiền vẫn là chữ", () => {
    const { container } = render(<Markdown text={"Nghiệm $x = \\frac{1}{2}$, giá $100 và $200."} />);
    expect(container.querySelectorAll(".katex")).toHaveLength(1);
    expect(container.textContent).toContain("giá $100 và $200");
  });

  it("dàn ý Word hiện công thức", () => {
    const { container } = render(<MathText text={"$$\\sqrt{2}$$"} />);
    expect(container.querySelector(".math-display .katex")).not.toBeNull();
  });
});

describe("thẻ thay đổi tệp", () => {
  it("gộp nhiều thay đổi cùng tệp, cùng phiên bản trong một lượt", async () => {
    const { addChange } = await import("../useChatSocket");
    const c = (version: number, summary: string) => ({ kind: "change" as const, fileId: "f", fileName: "a.docx", version, summary });
    let items = addChange([{ kind: "text", role: "user", text: "làm đi" }], c(2, "1 đoạn"));
    items = addChange(items, c(2, "3 đoạn"));
    expect(items.filter((x) => x.kind === "change")).toEqual([c(2, "3 đoạn")]);
    items = addChange([...items, { kind: "text", role: "user", text: "tiếp" }], c(3, "1 đoạn"));
    expect(items.filter((x) => x.kind === "change")).toHaveLength(2);
  });
});
