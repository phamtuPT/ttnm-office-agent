"""Tool Word (python-docx). TV2 mở rộng: bảng, định dạng từ khoá, tìm-thay thế, Track Changes/Comment, ..."""
import copy
import re
from datetime import datetime, timezone

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm
from docx.text.paragraph import Paragraph
from pydantic import BaseModel, Field

from . import omml
from .assets import asset_path
from .registry import ToolCtx, ToolError, tool

FILE = Field(description="Tên tệp .docx trong phiên")


def _paragraph(doc, index: int):
    paras = doc.paragraphs
    if not 0 <= index < len(paras):
        raise ToolError(f"Chỉ số đoạn {index} không tồn tại (tài liệu có {len(paras)} đoạn, đánh số từ 0)")
    return paras[index]


def _check_selection(ctx: ToolCtx, index: int) -> None:
    sel = ctx.selection
    if sel and sel.paragraphs is not None and index not in sel.paragraphs:
        raise ToolError(f"Đoạn {index} nằm ngoài các đoạn người dùng chọn {sel.paragraphs}")


class InspectArgs(BaseModel):
    file: str = FILE
    start: int = Field(0, description="Đoạn bắt đầu (từ 0)")
    limit: int = Field(100, description="Số đoạn tối đa trả về")


def para_text(p) -> str:
    """Chữ của đoạn như khi chấp nhận mọi đề xuất (gồm chữ trong <w:ins>, bỏ chữ trong <w:del>)."""
    return "".join(t.text or "" for t in p._p.xpath(".//w:t[not(ancestor::w:del)]"))


_MATH_TAGS = {qn("m:oMath"), qn("m:oMathPara")}


def _markup(el) -> str:
    out = []
    for c in el:
        if c.tag == qn("m:oMathPara"):
            out.append("$$" + omml.to_latex(c) + "$$")
        elif c.tag == qn("m:oMath"):
            out.append("$" + omml.to_latex(c) + "$")
        elif c.tag == qn("w:r"):
            out += [t.text or "" for t in c.iter(qn("w:t"))]
            out += ["\t" for _ in c.iter(qn("w:tab"))]
        elif c.tag in (qn("w:ins"), qn("w:hyperlink"), qn("w:smartTag"), qn("w:sdt"), qn("w:sdtContent"),
                       qn("w:fldSimple")):
            out.append(_markup(c))
    return "".join(out)


def para_markup(p) -> str:
    """Chữ của đoạn kèm công thức dạng LaTeX: $...$ trong dòng, $$...$$ đứng riêng (giữ nguyên khi viết lại)."""
    return _markup(p._p)


def document_equations(path) -> list[dict]:
    """Mọi công thức trong thân tài liệu theo thứ tự xuất hiện (cả trong bảng) — để giao diện vẽ lại bằng KaTeX."""
    body = Document(path).element.body
    return [{"latex": omml.to_latex(m), "display": m.getparent().tag == qn("m:oMathPara")}
            for m in body.iter(qn("m:oMath"))]


def has_equations(p) -> bool:
    return any(c.tag in _MATH_TAGS for c in p._p.iter())


def write_paragraph(p, text: str) -> None:
    """Thay toàn bộ nội dung đoạn, giữ định dạng run đầu. $...$ / $$...$$ → công thức Word thật (OMML)."""
    template = next(iter(p._p.iter(qn("w:r"))), None)
    rpr = template.find(qn("w:rPr")) if template is not None else None
    for c in list(p._p):
        if c.tag != qn("w:pPr"):
            p._p.remove(c)
    try:
        parts = omml.split_math(text)
        if len(parts) == 1 and parts[0][0] == "display":
            p._p.append(omml.latex_to_omml_para(parts[0][1]))
            return
        for kind, value in parts:
            if kind == "text":
                r = OxmlElement("w:r")
                if rpr is not None:
                    r.append(copy.deepcopy(rpr))
                t = OxmlElement("w:t")
                t.set(qn("xml:space"), "preserve")
                t.text = value
                r.append(t)
                p._p.append(r)
            else:  # công thức giữa câu luôn là công thức trong dòng
                p._p.append(omml.latex_to_omml(value))
    except omml.MathError as e:
        raise ToolError(f"{e}. Viết lại công thức LaTeX (ví dụ $\\frac{{a}}{{b}}$, $x^2$, $\\sqrt{{x}}$)")


def _pending(p) -> dict | None:
    deleted = "".join(t.text or "" for t in p._p.xpath(".//w:delText"))
    inserted = "".join(t.text or "" for t in p._p.xpath(".//w:ins//w:t"))
    return {"old": deleted[:300], "new": inserted[:300]} if deleted or inserted else None


@tool("word_inspect", "Xem dàn ý tài liệu: các đoạn văn kèm chỉ số, style và nội dung (cắt ở 300 ký tự); "
      "công thức toán hiện dạng LaTeX $...$ (trong dòng) hoặc $$...$$ (riêng dòng); "
      "đoạn có đề xuất Track Changes đang chờ duyệt có thêm pending_suggestion. Luôn gọi trước khi sửa.",
      InspectArgs, kind="docx")
def word_inspect(args: InspectArgs, ctx: ToolCtx) -> dict:
    doc = Document(ctx.path)
    paras = doc.paragraphs
    items = []
    for i, p in enumerate(paras[args.start:args.start + args.limit], start=args.start):
        item = {"index": i, "style": p.style.name, "text": para_markup(p)[:300]}
        if (pending := _pending(p)) is not None:
            item["pending_suggestion"] = pending  # đề xuất Track Changes chờ người dùng duyệt
        items.append(item)
    return {"total_paragraphs": len(paras), "tables": len(doc.tables), "comments": len(list(doc.comments)),
            "paragraphs": items}


class ReplaceArgs(BaseModel):
    file: str = FILE
    index: int = Field(description="Chỉ số đoạn cần thay (từ 0)")
    text: str = Field(description="Nội dung mới của cả đoạn. Công thức toán viết LaTeX: $...$ trong dòng, "
                                  "cả đoạn là $$...$$ (công thức riêng dòng)")


@tool("word_replace_paragraph", "Thay toàn bộ nội dung một đoạn văn, giữ định dạng của run đầu tiên. "
      "$...$ / $$...$$ thành công thức toán Word thật.", ReplaceArgs, kind="docx", writes=True)
def word_replace_paragraph(args: ReplaceArgs, ctx: ToolCtx) -> dict:
    _check_selection(ctx, args.index)
    doc = Document(ctx.path)
    write_paragraph(_paragraph(doc, args.index), args.text)
    doc.save(ctx.path)
    return {"replaced": args.index}


class ParagraphSpec(BaseModel):
    text: str = Field(description="Nội dung; công thức toán viết LaTeX $...$ hoặc cả đoạn $$...$$")
    style: str | None = Field(None, description="'Title', 'Heading 1'..'Heading 3', 'List Bullet', 'List Number'; "
                                                "bỏ trống = Normal")


class InsertArgs(BaseModel):
    file: str = FILE
    after_index: int = Field(description="Chèn sau đoạn này; -1 để chèn lên đầu tài liệu")
    paragraphs: list[ParagraphSpec] = Field(
        description="Các đoạn chèn theo thứ tự — gộp TẤT CẢ đoạn cần chèn vào MỘT lần gọi. Công thức toán viết "
                    "LaTeX: $...$ trong dòng; cả đoạn là $$...$$ → công thức riêng dòng, căn giữa")


@tool("word_insert_paragraph", "Chèn một hoặc nhiều đoạn văn liên tiếp (đề mục, danh sách, công thức toán "
      "$...$ / $$...$$). Tài liệu trống thì nội dung bắt đầu từ đoạn đầu tiên.", InsertArgs, kind="docx", writes=True)
def word_insert_paragraph(args: InsertArgs, ctx: ToolCtx) -> dict:
    if not args.paragraphs:
        raise ToolError("Cần ít nhất một đoạn")
    _check_selection(ctx, args.after_index)
    doc = Document(ctx.path)
    paras = doc.paragraphs
    # Tài liệu mới chỉ có một đoạn trống → điền vào đó thay vì để lại dòng trống thừa
    blank = len(paras) == 1 and not para_markup(paras[0]).strip() and not doc.tables
    prev = None  # đoạn vừa chèn: đoạn sau nối tiếp nó
    for i, spec in enumerate(args.paragraphs):
        try:
            if i == 0 and not paras:
                para = doc.add_paragraph("")  # tài liệu chưa có đoạn nào: after_index nào cũng là đầu tài liệu
            elif i == 0 and blank:
                para = paras[0]
            elif i == 0 and args.after_index == -1:
                para = paras[0].insert_paragraph_before("") if paras else doc.add_paragraph("")
            else:
                anchor = prev if prev is not None else _paragraph(doc, args.after_index)
                new_p = OxmlElement("w:p")
                anchor._p.addnext(new_p)
                para = Paragraph(new_p, anchor._parent)
            if spec.style:
                para.style = spec.style
        except KeyError:
            raise ToolError(f"Tài liệu không có style '{spec.style}'")
        write_paragraph(para, spec.text)
        prev = para
    doc.save(ctx.path)
    return {"inserted_after": args.after_index, "paragraphs": len(args.paragraphs)}


class CreateArgs(BaseModel):
    file: str = Field(description="Tên tệp mới, đuôi .docx")
    paragraphs: list[ParagraphSpec] = Field(description="Nội dung theo thứ tự")


@tool("word_create_document", "Tạo tài liệu Word mới có đề mục, đoạn văn, danh sách, công thức toán.",
      CreateArgs, kind="docx", creates=True)
def word_create_document(args: CreateArgs, ctx: ToolCtx) -> dict:
    doc = Document()
    for p in args.paragraphs:
        try:
            write_paragraph(doc.add_paragraph("", p.style), p.text)
        except KeyError:
            raise ToolError(f"Không có style '{p.style}'")
    doc.save(ctx.path)
    return {"created": args.file, "paragraphs": len(args.paragraphs)}


class InsertImageArgs(BaseModel):
    file: str = FILE
    image: str = Field(description="Tên ảnh người dùng đã gửi, xem [Ảnh đính kèm], ví dụ anh-1.png")
    after_index: int = Field(description="Chèn sau đoạn này; -1 để chèn lên đầu")
    width_cm: float = Field(12, description="Chiều rộng ảnh (cm)")


@tool("word_insert_image", "Chèn ảnh người dùng đã gửi vào tài liệu Word.", InsertImageArgs, kind="docx", writes=True)
def word_insert_image(args: InsertImageArgs, ctx: ToolCtx) -> dict:
    img = asset_path(ctx, args.image)
    _check_selection(ctx, args.after_index)
    doc = Document(ctx.path)
    para = doc.add_paragraph()
    para.add_run().add_picture(str(img), width=Cm(args.width_cm))
    # add_paragraph thêm vào cuối → dời về đúng vị trí
    if args.after_index == -1 and len(doc.paragraphs) > 1:
        doc.paragraphs[0]._p.addprevious(para._p)
    elif args.after_index >= 0:
        _paragraph(doc, args.after_index)._p.addnext(para._p)
    doc.save(ctx.path)
    return {"inserted": args.image}


AUTHOR = "Trợ lý AI"


def _move_after(doc, element, after_index: int) -> None:
    """Phần tử vừa thêm ở cuối tài liệu → dời tới sau đoạn after_index (-1 = đầu tài liệu)."""
    if after_index == -1:
        doc.paragraphs[0]._p.addprevious(element)
    else:
        _paragraph(doc, after_index)._p.addnext(element)


class TableArgs(BaseModel):
    file: str = FILE
    after_index: int = Field(description="Chèn sau đoạn này; -1 để chèn lên đầu")
    rows: list[list[str]] = Field(description="Dữ liệu bảng, dòng đầu là tiêu đề")
    style: str = Field("Table Grid", description="Style bảng, ví dụ 'Table Grid', 'Light Grid Accent 1'")


@tool("word_insert_table", "Chèn bảng vào tài liệu Word (dòng đầu in đậm làm tiêu đề).", TableArgs,
      kind="docx", writes=True)
def word_insert_table(args: TableArgs, ctx: ToolCtx) -> dict:
    if not args.rows or not args.rows[0]:
        raise ToolError("Bảng cần ít nhất một dòng và một cột")
    _check_selection(ctx, args.after_index)
    doc = Document(ctx.path)
    ncols = max(len(r) for r in args.rows)
    table = doc.add_table(rows=len(args.rows), cols=ncols)
    try:
        table.style = args.style
    except KeyError:
        table.style = "Table Grid"
    for i, row in enumerate(args.rows):
        for j in range(ncols):
            cell = table.cell(i, j)
            cell.text = str(row[j]) if j < len(row) else ""
            if i == 0:
                for r in cell.paragraphs[0].runs:
                    r.bold = True
    if doc.paragraphs:
        _move_after(doc, table._tbl, args.after_index)
    doc.save(ctx.path)
    return {"table": f"{len(args.rows)}x{ncols}"}


def _replace_in_paragraph(p, find: str, repl: str, match_case: bool) -> int:
    """Thay trong từng run để giữ định dạng; chuỗi nằm vắt qua nhiều run thì gộp vào run đầu."""
    def norm(s):
        return s if match_case else s.lower()
    count = 0
    for r in p.runs:
        if norm(find) in norm(r.text):
            n = norm(r.text).count(norm(find))
            if match_case:
                r.text = r.text.replace(find, repl)
            else:
                out, src, i = [], r.text, 0
                while (j := src.lower().find(find.lower(), i)) != -1:
                    out += [src[i:j], repl]
                    i = j + len(find)
                r.text = "".join(out) + src[i:]
            count += n
    if count == 0 and norm(find) in norm(p.text) and p.runs:  # vắt qua nhiều run
        text = p.text
        n = norm(text).count(norm(find))
        if match_case:
            text = text.replace(find, repl)
        else:
            out, i = [], 0
            while (j := text.lower().find(find.lower(), i)) != -1:
                out += [text[i:j], repl]
                i = j + len(find)
            text = "".join(out) + text[i:]
        p.runs[0].text = text
        for r in p.runs[1:]:
            r._r.getparent().remove(r._r)
        count += n
    return count


def _all_paragraphs(doc):
    yield from doc.paragraphs
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                yield from cell.paragraphs


class ReplaceItem(BaseModel):
    find: str
    replace: str


class FindReplaceArgs(BaseModel):
    file: str = FILE
    items: list[ReplaceItem] = Field(description="Các cặp tìm → thay, áp dụng theo thứ tự")
    match_case: bool = False


@tool("word_find_replace", "Tìm và thay hàng loạt trong toàn tài liệu (cả trong bảng), giữ định dạng chữ.",
      FindReplaceArgs, kind="docx", writes=True)
def word_find_replace(args: FindReplaceArgs, ctx: ToolCtx) -> dict:
    doc = Document(ctx.path)
    paras = list(_all_paragraphs(doc))
    if ctx.selection and ctx.selection.paragraphs is not None:
        paras = [p for i, p in enumerate(doc.paragraphs) if i in ctx.selection.paragraphs]
    counts = {it.find: sum(_replace_in_paragraph(p, it.find, it.replace, args.match_case) for p in paras)
              for it in args.items if it.find}
    doc.save(ctx.path)
    return {"replaced": counts}


class RewriteItem(BaseModel):
    index: int
    text: str


class RewriteArgs(BaseModel):
    file: str = FILE
    items: list[RewriteItem] = Field(description="Các đoạn cần viết lại (dịch, rút gọn, sửa lỗi...)")
    allow_number_changes: bool = Field(
        False, description="Chỉ đặt true khi NGƯỜI DÙNG yêu cầu đổi số liệu. Mặc định mọi số, ngày, tiền phải giữ "
                           "nguyên đúng từng ký tự (kể cả dấu chấm/phẩy phân cách), kể cả khi dịch.")


# Số, ngày, tiền: "120.000.000", "15/01/2026", "3,5", "08:30"
_NUMBER = re.compile(r"\d+(?:[.,/:\-]\d+)*")


def _lost_equations(p, new: str) -> list[str]:
    """Công thức có trong đoạn cũ mà bản mới không còn (so LaTeX đã bỏ khoảng trắng)."""
    def norm(x: str) -> str:
        return "".join(x.split())
    old = [v for k, v in omml.split_math(para_markup(p)) if k != "text"]
    new_eqs = [norm(v) for k, v in omml.split_math(new) if k != "text"]
    return [e for e in old if norm(e) not in new_eqs]


def _changed_numbers(old: str, new: str) -> list[str]:
    """Các số/ngày có trong đoạn cũ nhưng không còn nguyên dạng trong đoạn mới (bất kể thứ tự)."""
    remaining = _NUMBER.findall(new)
    missing = []
    for n in _NUMBER.findall(old):
        if n in remaining:
            remaining.remove(n)
        else:
            missing.append(n)
    return missing


@tool("word_rewrite_paragraphs", "Viết lại nhiều đoạn một lần (dịch tài liệu, sửa chính tả, đổi giọng văn), "
      "giữ style và định dạng run đầu của từng đoạn. Tự kiểm tra số/ngày/tiền và công thức $...$ không bị đổi.",
      RewriteArgs,
      kind="docx", writes=True)
def word_rewrite_paragraphs(args: RewriteArgs, ctx: ToolCtx) -> dict:
    for it in args.items:
        _check_selection(ctx, it.index)
    doc = Document(ctx.path)
    if not args.allow_number_changes:
        problems = {it.index: miss for it in args.items
                    if (miss := _changed_numbers(para_markup(_paragraph(doc, it.index)), it.text))}
        if problems:
            # Không ghi gì: số liệu sai trong hợp đồng/báo cáo là lỗi nghiêm trọng
            raise ToolError("Số/ngày/tiền bị thay đổi, chưa ghi đoạn nào. Hãy giữ nguyên ĐÚNG từng ký tự (kể cả dấu "
                            f"phân cách hàng nghìn) rồi gọi lại: {problems}")
    lost = {it.index: miss for it in args.items if (miss := _lost_equations(_paragraph(doc, it.index), it.text))}
    if lost:
        raise ToolError(f"Bản viết lại làm mất công thức, chưa ghi đoạn nào: {lost}. Giữ nguyên các $...$ như "
                        "word_inspect trả về (chỉ dịch/sửa phần chữ) rồi gọi lại.")
    for it in args.items:
        write_paragraph(_paragraph(doc, it.index), it.text)
    doc.save(ctx.path)
    return {"rewritten": len(args.items)}


class CommentItem(BaseModel):
    index: int = Field(description="Chỉ số đoạn được nhận xét")
    comment: str = Field(description="Nội dung nhận xét")


class CommentArgs(BaseModel):
    file: str = FILE
    items: list[CommentItem] = Field(description="Các nhận xét — gộp TẤT CẢ nhận xét vào một lần gọi")


@tool("word_add_comment", "Thêm Comment (nhận xét bên lề) vào các đoạn — dùng khi rà soát tài liệu. "
      "Đoạn vừa được đề xuất sửa vẫn nhận xét được.", CommentArgs, kind="docx", writes=True)
def word_add_comment(args: CommentArgs, ctx: ToolCtx) -> dict:
    from docx.text.run import Run

    if not args.items:
        raise ToolError("Cần ít nhất một nhận xét")
    doc = Document(ctx.path)
    for it in args.items:
        p = _paragraph(doc, it.index)
        # Gồm cả run nằm trong <w:ins>/<w:del> của Track Changes (p.runs bỏ qua chúng)
        runs = [Run(r, p) for r in p._p.iter(qn("w:r"))]
        if not runs:
            raise ToolError(f"Đoạn {it.index} trống, không gắn nhận xét được")
        doc.add_comment(runs, text=it.comment, author=AUTHOR, initials="AI")
    doc.save(ctx.path)
    return {"commented": [it.index for it in args.items]}


def _tracked(tag: str, rid: int):
    el = OxmlElement(tag)
    el.set(qn("w:id"), str(rid))
    el.set(qn("w:author"), AUTHOR)
    el.set(qn("w:date"), datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    return el


class SuggestItem(BaseModel):
    index: int = Field(description="Chỉ số đoạn cần đề xuất sửa")
    text: str = Field(description="Nội dung đề xuất thay cho cả đoạn")


class SuggestArgs(BaseModel):
    file: str = FILE
    items: list[SuggestItem] = Field(description="Các đề xuất — gộp TẤT CẢ đề xuất vào một lần gọi")


@tool("word_suggest_edit", "Đề xuất sửa các đoạn dưới dạng Track Changes (chữ cũ gạch đi, chữ mới chèn vào) để "
      "người dùng Chấp nhận/Từ chối trong Word. Không sửa thẳng nội dung.", SuggestArgs, kind="docx", writes=True)
def word_suggest_edit(args: SuggestArgs, ctx: ToolCtx) -> dict:
    if not args.items:
        raise ToolError("Cần ít nhất một đề xuất")
    for it in args.items:
        _check_selection(ctx, it.index)
    doc = Document(ctx.path)
    for it in args.items:
        _suggest(doc, it.index, it.text)
    doc.save(ctx.path)
    return {"suggested": [it.index for it in args.items]}


def _suggest(doc, index: int, text: str) -> None:
    p = _paragraph(doc, index)
    if _pending(p) is not None:
        raise ToolError(f"Đoạn {index} đã có đề xuất sửa đang chờ duyệt — dùng word_add_comment để góp ý thêm")
    if has_equations(p) or omml.has_math(text):
        raise ToolError(f"Đoạn {index} có công thức toán — Track Changes không áp dụng cho công thức; "
                        "dùng word_add_comment để góp ý, hoặc word_replace_paragraph nếu người dùng muốn sửa thẳng")
    runs = list(p.runs)
    if not runs:
        raise ToolError(f"Đoạn {index} trống — dùng word_replace_paragraph thay vì đề xuất sửa")
    base = 9000 + index * 10
    deleted = _tracked("w:del", base)
    runs[0]._r.addprevious(deleted)
    for r in runs:
        deleted.append(r._r)  # chuyển run cũ vào <w:del>, đổi w:t → w:delText
        for t in r._r.findall(qn("w:t")):
            t.tag = qn("w:delText")
    inserted = _tracked("w:ins", base + 1)
    new_r = copy.deepcopy(runs[0]._r)
    for child in list(new_r):
        if child.tag != qn("w:rPr"):
            new_r.remove(child)
    t = OxmlElement("w:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text
    new_r.append(t)
    inserted.append(new_r)
    deleted.addnext(inserted)


class CopyStyleArgs(BaseModel):
    file: str = FILE
    source: str = Field(description="Tệp .docx mẫu trong phiên (lấy phong cách từ tệp này)")
    page_setup: bool = Field(True, description="Chép cả khổ giấy, hướng giấy và lề trang")
    reset_direct_formatting: bool = Field(
        False, description="Xoá phông/cỡ/màu chữ và giãn dòng gõ tay trong tệp đích để kiểu chữ mới có hiệu lực "
                           "(giữ in đậm/nghiêng/gạch chân)")


_DIRECT_RUN = ("w:rFonts", "w:sz", "w:szCs", "w:color")
_DIRECT_PARA = ("w:spacing", "w:ind", "w:jc")


@tool("word_copy_style", "Sao chép phong cách của một tài liệu Word khác sang tệp này: kiểu chữ (Normal, Heading, "
      "Title, danh sách, bảng), phông chữ chủ đề, khổ giấy và lề. Dùng khi người dùng muốn định dạng 'giống tài liệu "
      "mẫu'. Nội dung giữ nguyên.", CopyStyleArgs, kind="docx", writes=True)
def word_copy_style(args: CopyStyleArgs, ctx: ToolCtx) -> dict:
    from docx.opc.constants import RELATIONSHIP_TYPE as RT

    from .session_files import session_file

    if args.source == args.file:
        raise ToolError("Tệp mẫu phải khác tệp đang sửa")
    src = Document(session_file(ctx, args.source, "docx"))
    doc = Document(ctx.path)
    dst_styles, src_styles = doc.styles.element, src.styles.element

    # Định dạng mặc định của cả tài liệu (phông, cỡ chữ, giãn dòng)
    src_defaults = src_styles.find(qn("w:docDefaults"))
    if src_defaults is not None:
        old = dst_styles.find(qn("w:docDefaults"))
        if old is not None:
            old.addprevious(copy.deepcopy(src_defaults))
            dst_styles.remove(old)
        else:
            dst_styles.insert(0, copy.deepcopy(src_defaults))

    existing = {s.get(qn("w:styleId")): s for s in dst_styles.findall(qn("w:style"))}
    copied = []
    for style in src_styles.findall(qn("w:style")):
        sid = style.get(qn("w:styleId"))
        new = copy.deepcopy(style)
        # Kiểu danh sách trỏ tới định nghĩa đánh số (numbering.xml) của tệp mẫu → giữ đánh số của tệp đích
        new_ppr = new.find(qn("w:pPr"))
        num = new_ppr.find(qn("w:numPr")) if new_ppr is not None else None
        if num is not None:
            new_ppr.remove(num)
            old_ppr = existing[sid].find(qn("w:pPr")) if sid in existing else None
            old_num = old_ppr.find(qn("w:numPr")) if old_ppr is not None else None
            if old_num is not None:
                new_ppr.insert(0, copy.deepcopy(old_num))
        if sid in existing:
            existing[sid].addprevious(new)
            dst_styles.remove(existing[sid])
        else:
            dst_styles.append(new)
        copied.append(sid)

    # Phông "chủ đề" (+Body, +Headings) mà kiểu chữ tham chiếu nằm trong theme
    try:
        doc.part.part_related_by(RT.THEME)._blob = src.part.part_related_by(RT.THEME).blob
        theme = True
    except KeyError:
        theme = False

    if args.page_setup and src.sections:
        s0 = src.sections[0]
        for sec in doc.sections:
            sec.orientation, sec.page_width, sec.page_height = s0.orientation, s0.page_width, s0.page_height
            sec.left_margin, sec.right_margin = s0.left_margin, s0.right_margin
            sec.top_margin, sec.bottom_margin = s0.top_margin, s0.bottom_margin

    cleared = 0
    if args.reset_direct_formatting:
        for el in doc.element.body.iter(qn("w:rPr"), qn("w:pPr")):  # gồm cả w:rPr của dấu đoạn
            names = _DIRECT_RUN if el.tag == qn("w:rPr") else _DIRECT_PARA
            for name in names:
                for child in el.findall(qn(name)):
                    el.remove(child)
                    cleared += 1
    doc.save(ctx.path)
    return {"styles_copied": len(copied), "theme_fonts": theme, "page_setup": args.page_setup,
            "direct_formatting_removed": cleared}
