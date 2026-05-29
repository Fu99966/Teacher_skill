from __future__ import annotations

import pytest

from teacher_agent.deepseek_client import DeepSeekError
from teacher_agent.lesson_generator import LessonGenerationError, draft_lesson_document_fields_with_source


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


def test_strict_ai_empty_object_raises_after_retry(monkeypatch):
    monkeypatch.setattr("teacher_agent.lesson_generator.is_deepseek_configured", lambda: True)
    monkeypatch.setattr("teacher_agent.lesson_generator.chat_json", lambda *args, **kwargs: {})

    with pytest.raises(LessonGenerationError) as exc:
        draft_lesson_document_fields_with_source(
            "语文",
            "四年级",
            "桂林山水",
            "教材内容",
            template_fields=["lesson_title", "teaching_goals"],
            strict_ai=True,
        )

    assert "lesson_title" in str(exc.value)
    assert "teaching_goals" in str(exc.value)


def test_non_strict_ai_empty_object_backfills(monkeypatch):
    monkeypatch.setattr("teacher_agent.lesson_generator.is_deepseek_configured", lambda: True)
    monkeypatch.setattr("teacher_agent.lesson_generator.chat_json", lambda *args, **kwargs: {})

    fields, backend = draft_lesson_document_fields_with_source(
        "语文",
        "四年级",
        "桂林山水",
        "教材内容",
        template_fields=["lesson_title", "teaching_goals"],
        strict_ai=False,
    )

    assert backend == "deepseek_with_local_backfill"
    assert fields["lesson_title"] == "桂林山水"
    assert fields["teaching_goals"]
