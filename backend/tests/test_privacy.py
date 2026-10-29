import logging

from app.privacy.pii import Anonymizer
from app.privacy.secrets import RedactSecretsFilter, redact


def test_masks_common_pii_and_restores():
    a = Anonymizer()
    text = ("Liên hệ an.nguyen@cty.vn hoặc 0912 345 678, +84 912.345.679; web https://cty.vn/lien-he; "
            "thẻ 4111 1111 1111 1111; mã đơn 1234567890123")
    masked = a.mask_text(text)
    for secret in ("an.nguyen@cty.vn", "0912 345 678", "+84 912.345.679", "https://cty.vn/lien-he", "4111 1111 1111 1111"):
        assert secret not in masked
    assert "1234567890123" in masked  # không qua kiểm tra Luhn → không phải số thẻ
    assert a.unmask_text(masked) == text


def test_same_value_same_tag_and_tags_untouched():
    a = Anonymizer()
    t1 = a.mask_text("x@y.vn")
    assert a.mask_text("gửi x@y.vn nhé") == f"gửi {t1} nhé"
    assert a.mask_text(t1) == t1


def test_mask_nested_objects():
    a = Anonymizer()
    m = a.mask({"rows": [["Tên", "x@y.vn"]], "n": 3})
    assert m["n"] == 3 and m["rows"][0][1].startswith("⟦EMAIL_")
    assert a.unmask(m) == {"rows": [["Tên", "x@y.vn"]], "n": 3}


def test_secrets_redacted_in_logs(caplog):
    key = "AIza" + "x" * 35
    assert key not in redact(f"key={key}")
    logger = logging.getLogger("test-secrets")
    logger.addFilter(RedactSecretsFilter())
    with caplog.at_level(logging.INFO, logger="test-secrets"):
        logger.info("gọi với %s", "sk-" + "a" * 30)
    assert "sk-aaaa" not in caplog.text and "[ĐÃ CHE]" in caplog.text
