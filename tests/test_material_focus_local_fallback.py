from __future__ import annotations

from teacher_agent.lesson_generator import JSON_FIELD_NAMES, draft_lesson_document_fields_with_source


def test_local_fallback_uses_material_focus_beyond_material_basis(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    material = (
        "课程标准：学生需要掌握 LoRa 无线通信、MQTT 消息发布订阅、传感器数据采集、边缘网关数据上传。\n"
        "实训任务：使用温湿度传感器采集数据，通过 MQTT 上传到物联网平台，并分析 QoS 0/1 差异。"
    )

    fields, backend = draft_lesson_document_fields_with_source(
        "物联网",
        "24级物联网班",
        "物联网通信基础",
        material,
        "2课时",
        "实验课",
        "探究式",
        "常规混合水平",
        "标准",
        JSON_FIELD_NAMES,
        False,
    )

    assert backend == "local_fallback"
    combined = "\n".join(
        [
            fields["teaching_goals"],
            fields["teaching_process"],
            fields["homework"],
        ]
    )
    assert "MQTT" in combined
    assert "传感器数据采集" in combined
    assert "物联网平台" in combined or "边缘网关" in combined
    assert "资料聚焦" in fields["teaching_process"]
    assert "资料关联任务" in fields["homework"]


def test_prompt_like_material_is_not_used_as_material_focus(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    prompt_like_material = "帮我生成一份 24级物联网班 PCB板设计课的 32课时的教案"

    fields, backend = draft_lesson_document_fields_with_source(
        "物联网",
        "24级物联网班",
        "PCB板设计",
        prompt_like_material,
        "32课时",
        "项目实训课",
        "项目式教学",
        "常规混合水平",
        "标准",
        JSON_FIELD_NAMES,
        False,
    )

    assert backend == "local_fallback"
    text = "\n".join(fields.values())
    assert "帮我生成一份" not in text
    assert "教材依据：帮我生成" not in text
