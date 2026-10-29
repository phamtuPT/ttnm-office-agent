"""Tool Word (python-docx). TV2 mở rộng: bảng, định dạng từ khoá, tìm-thay thế, Track Changes/Comment, ..."""
from docx import Document
from docx.oxml import OxmlElement
from docx.shared import Cm
from docx.text.paragraph import Paragraph
from pydantic import BaseModel, Field

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


@tool("word_inspect", "Xem dàn ý tài liệu: các đoạn văn kèm chỉ số, style và nội dung (cắt ở 300 ký tự). "
      "Luôn gọi trước khi sửa.", InspectArgs, kind="docx")
def word_inspect(args: InspectArgs, ctx: ToolCtx) -> dict:
    doc = Document(ctx.path)
    paras = doc.paragraphs
    items = [{"index": i, "style": p.style.name, "text": p.text[:300]}
             for i, p in enumerate(paras[args.start:args.start + args.limit], start=args.start)]
    return {"total_paragraphs": len(paras), "tables": len(doc.tables), "paragraphs": items}


class ReplaceArgs(BaseModel):
    file: str = FILE
    index: int = Field(description="Chỉ số đoạn cần thay (từ 0)")
    text: str = Field(description="Nội dung mới của cả đoạn")


@tool("word_replace_paragraph", "Thay toàn bộ nội dung một đoạn văn, giữ định dạng của run đầu tiên.",
      ReplaceArgs, kind="docx", writes=True)
def word_replace_paragraph(args: ReplaceArgs, ctx: ToolCtx) -> dict:
    _check_selection(ctx, args.index)
    doc = Document(ctx.path)
    p = _paragraph(doc, args.index)
    if p.runs:
        p.runs[0].text = args.text
        for r in p.runs[1:]:
            r._r.getparent().remove(r._r)
    else:
        p.add_run(args.text)
    doc.save(ctx.path)
    return {"replaced": args.index}


class InsertArgs(BaseModel):
    file: str = FILE
    after_index: int = Field(description="Chèn sau đoạn này; -1 để chèn lên đầu tài liệu")
    text: str
    style: str | None = Field(None, description="Tên style, ví dụ 'Heading 1', 'List Bullet'. Bỏ trống = Normal")


@tool("word_insert_paragraph", "Chèn một đoạn văn mới.", InsertArgs, kind="docx", writes=True)
def word_insert_paragraph(args: InsertArgs, ctx: ToolCtx) -> dict:
    _check_selection(ctx, args.after_index)
    doc = Document(ctx.path)
    try:
        if args.after_index == -1:
            if doc.paragraphs:
                doc.paragraphs[0].insert_paragraph_before(args.text, args.style)
            else:
                doc.add_paragraph(args.text, args.style)
        else:
            anchor = _paragraph(doc, args.after_index)
            new_p = OxmlElement("w:p")
            anchor._p.addnext(new_p)
            para = Paragraph(new_p, anchor._parent)
            para.add_run(args.text)
            if args.style:
                para.style = args.style
    except KeyError:
        raise ToolError(f"Tài liệu không có style '{args.style}'")
    doc.save(ctx.path)
    return {"inserted_after": args.after_index}


class ParagraphSpec(BaseModel):
    text: str
    style: str | None = Field(None, description="'Title', 'Heading 1'..'Heading 3', 'List Bullet', 'List Number'; "
                                                "bỏ trống = Normal")


class CreateArgs(BaseModel):
    file: str = Field(description="Tên tệp mới, đuôi .docx")
    paragraphs: list[ParagraphSpec] = Field(description="Nội dung theo thứ tự")


@tool("word_create_document", "Tạo tài liệu Word mới có đề mục, đoạn văn, danh sách.", CreateArgs,
      kind="docx", creates=True)
def word_create_document(args: CreateArgs, ctx: ToolCtx) -> dict:
    doc = Document()
    for p in args.paragraphs:
        try:
            doc.add_paragraph(p.text, p.style)
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
