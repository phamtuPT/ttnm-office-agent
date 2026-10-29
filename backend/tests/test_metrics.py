from app.media.ocr import cer, table_cell_accuracy, wer


def test_wer_ignores_format_but_counts_real_errors():
    assert wer("Tạo bảng mười hai tháng, quý ba", "tạo bảng 12 tháng quý 3.") == 0
    assert wer("giữ nguyên ngày 15/01/2026", "Giữ nguyên ngày 15 tháng 01 năm 2026.") == 0
    assert wer("Hoàn tác lần sửa vừa rồi", "Hoàn tất lần sửa vừa rồi") == 1 / 6  # nhận nhầm một từ
    assert wer("làm năm slide", "làm năm slide") == 0  # "năm" có thể là số 5 hoặc "năm 2026": giữ nguyên


def test_cer_and_table_accuracy():
    assert cer("Hoá đơn  số 12", "Hoá đơn số 12") == 0  # khoảng trắng thừa không tính
    assert round(cer("abcd", "abce"), 2) == 0.25
    assert table_cell_accuracy([["a", "b"], ["c", "d"]], [["a", "b"], ["c", "x"]]) == 0.75
