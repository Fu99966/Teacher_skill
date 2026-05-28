from __future__ import annotations

import pytest

from teacher_agent.deepseek_client import DeepSeekError
from teacher_agent.lesson_generator import draft_lesson_document_fields_with_source


def test_strict_ai_without_api_raises(monkeypatch):
    monkeypatch.setattr("teacher_agent.lesson_generator.is_deepseek_configured", lambda: False)

    with pytest.raises(DeepSeekError):
        draft_lesson_document_fields_with_source(
            "语文",
            "四年级",
            "桂林山水",
            "教材内容",
            template_fields=["lesson_title", "warm_up"],
            strict_ai=True,
        )


def test_non_strict_without_api_fallback(monkeypatch):
    monkeypatch.setattr("teacher_agent.lesson_generator.is_deepseek_configured", lambda: False)

    fields, backend = draft_lesson_document_fields_with_source(
        "语文",
        "四年级",
        "桂林山水",
        "教材内容",
        template_fields=["lesson_title", "warm_up", "assessment"],
        strict_ai=False,
    )

    assert backend == "local_fallback"
    assert list(fields) == ["lesson_title", "warm_up", "assessment"]
    assert fields["lesson_title"] == "桂林山水"
    assert fields["warm_up"]
