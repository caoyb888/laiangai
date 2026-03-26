"""
脱敏模块单元测试
见 CLAUDE.md §8.1：services/desensitizer.py 覆盖率 ≥ 95%
"""
import pytest
from app.services.desensitizer import Desensitizer, DesensitizedChunk


@pytest.fixture
def d() -> Desensitizer:
    return Desensitizer()


class TestDesensitizer:

    def test_company_name_replaced(self, d: Desensitizer) -> None:
        result = d.desensitize("甲方：莱芜钢铁集团有限公司，负责供货")
        assert "莱芜钢铁" not in result.text
        assert "[企业名称]" in result.text
        assert result.is_desensitized is True   # 必须为 True，见 CLAUDE.md §4.1

    def test_contract_no_replaced(self, d: Desensitizer) -> None:
        result = d.desensitize("合同编号：HT-2026-001")
        assert "HT-2026-001" not in result.text
        assert "[合同编号]" in result.text

    def test_phone_replaced(self, d: Desensitizer) -> None:
        result = d.desensitize("联系方式：13800138000")
        assert "13800138000" not in result.text
        assert "[联系方式]" in result.text

    def test_amount_replaced(self, d: Desensitizer) -> None:
        result = d.desensitize("合同总价人民币1500万元")
        assert "1500万元" not in result.text
        assert "[金额]" in result.text

    def test_id_card_replaced(self, d: Desensitizer) -> None:
        result = d.desensitize("身份证号：370101199001011234")
        assert "370101199001011234" not in result.text

    def test_bank_account_replaced(self, d: Desensitizer) -> None:
        result = d.desensitize("账户：6222000012345678")
        assert "6222000012345678" not in result.text

    def test_person_name_replaced(self, d: Desensitizer) -> None:
        result = d.desensitize("甲方代表：张三，乙方代表：李四")
        assert "张三" not in result.text
        assert "[姓名]" in result.text

    def test_normal_text_unchanged(self, d: Desensitizer) -> None:
        text = "本合同共十条，按照相关法规执行。"
        result = d.desensitize(text)
        assert result.text == text  # 无敏感信息时不改变内容

    def test_is_desensitized_always_true(self, d: Desensitizer) -> None:
        """所有情况下 is_desensitized 必须为 True，见 CLAUDE.md §4.1"""
        result = d.desensitize("")
        assert result.is_desensitized is True

    def test_original_length_recorded(self, d: Desensitizer) -> None:
        text = "联系方式：13800138000"
        result = d.desensitize(text)
        assert result.original_length == len(text)

    def test_returns_desensitized_chunk_type(self, d: Desensitizer) -> None:
        result = d.desensitize("任意文本")
        assert isinstance(result, DesensitizedChunk)

    def test_multiple_sensitive_fields_all_replaced(self, d: Desensitizer) -> None:
        text = "甲方：莱芜钢铁集团，代表：张三，电话：13812345678，账号：6222001234567890"
        result = d.desensitize(text)
        assert "莱芜钢铁" not in result.text
        assert "张三" not in result.text
        assert "13812345678" not in result.text
        assert "6222001234567890" not in result.text

    def test_fixed_telephone_replaced(self, d: Desensitizer) -> None:
        result = d.desensitize("联系电话：0531-12345678")
        assert "0531-12345678" not in result.text
        assert "[联系方式]" in result.text

    def test_email_replaced(self, d: Desensitizer) -> None:
        result = d.desensitize("邮箱：contract@laigangsteel.com")
        assert "contract@laigangsteel.com" not in result.text

    def test_laigang_company_name_replaced(self, d: Desensitizer) -> None:
        result = d.desensitize("甲方：莱钢集团有限公司")
        assert "莱钢集团" not in result.text
        assert "[企业名称]" in result.text


class TestDesensitizeBatch:

    def test_batch_returns_same_length(self) -> None:
        d = Desensitizer()
        texts = ["文本一", "联系：13800138000", ""]
        results = d.desensitize_batch(texts)
        assert len(results) == 3
        assert all(r.is_desensitized for r in results)

    def test_batch_each_item_desensitized(self) -> None:
        d = Desensitizer()
        texts = ["甲方：莱芜钢铁集团", "身份证：370101199001011234", "无敏感信息"]
        results = d.desensitize_batch(texts)
        assert "[企业名称]" in results[0].text
        assert "370101199001011234" not in results[1].text
        assert results[2].text == "无敏感信息"

    def test_batch_empty_list(self) -> None:
        d = Desensitizer()
        results = d.desensitize_batch([])
        assert results == []

    def test_batch_all_is_desensitized_true(self) -> None:
        d = Desensitizer()
        texts = ["内容一", "内容二", "内容三"]
        results = d.desensitize_batch(texts)
        assert all(r.is_desensitized is True for r in results)
