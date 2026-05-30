"""Tests for agent repair functionality."""
from pathlib import Path

from teacher_agent.agent_core.repair import diagnose_failure, repair_state
from teacher_agent.agent_core.state import AgentRunState

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
REAL_TEMPLATE = FIXTURE_DIR / "教案模板.docx"


def test_diagnose_empty_fields():
    state = AgentRunState(
        session_id="repair-1", status="failed",
        task={"subject": "语文"}, current_node="evaluate_delivery",
        next_action="", fields={},
        errors=["交付检查失败"],
    )
    diag = diagnose_failure(state)
    assert diag["repairable"]
    assert any("fields 为空" in i for i in diag["issues"])


def test_diagnose_filled_non_empty_zero():
    state = AgentRunState(
        session_id="repair-2", status="failed",
        task={"subject": "语文"}, current_node="evaluate_delivery",
        next_action="", fields={"lesson_title": "测试"},
        export_result={"fill_report": {"filled_non_empty_count": 0, "filled_fields": []}},
    )
    diag = diagnose_failure(state)
    assert diag["repairable"]
    assert any("filled_non_empty_count" in i for i in diag["issues"])


def test_repair_fills_missing_fields():
    state = AgentRunState(
        session_id="repair-3", status="failed",
        task={"subject": "物联网", "grade": "24物联网1班", "title": "传感器基础", "class_hour": "2课时"},
        current_node="evaluate_delivery", next_action="",
        fields={"lesson_title": "", "teaching_goals": "", "teaching_key_difficult": ""},
        export_result={},
        errors=["Word未写入非空字段"],
    )
    state = repair_state(state)
    assert state.status in ("fields_generated", "failed")
    if state.status == "fields_generated":
        non_empty = sum(1 for v in (state.fields or {}).values() if str(v or "").strip())
        assert non_empty > 0, "Repair should produce non-empty fields"


def test_repair_respects_max_retries():
    state = AgentRunState(
        session_id="repair-4", status="failed",
        task={}, current_node="evaluate_delivery", next_action="",
        fields={}, retry_count=2, max_retries=1,
    )
    state = repair_state(state)
    assert state.status == "failed"


def test_evaluator_delivery_checks():
    from teacher_agent.agent_core.evaluator import evaluate_delivery
    report = evaluate_delivery(
        fields={}, output_path=None, download_url=None,
        template_analysis=None, fill_report=None,
    )
    assert "delivery_checks" in report
    assert not report["passed"]


def test_evaluator_pedagogy_checks():
    from teacher_agent.agent_core.evaluator import evaluate_pedagogy_quality
    report = evaluate_pedagogy_quality(
        fields={
            "teaching_goals": "理解传感器基础概念和分类，能分析传感器在物联网中的应用。掌握传感器选型方法。",
            "teaching_key_difficult": "重点：传感器分类与工作原理。难点：传感器信号与物联网系统的关系。",
            "teaching_process": "一、导入：展示智能家居案例。\n二、新授：讲解概念。\n三、练习：分析传感器模块。\n四、总结。",
            "teaching_method": "案例教学法 + 任务驱动 + 小组讨论",
            "homework": "基础：整理笔记。提升：完成实验报告。拓展：设计一个传感器应用场景。",
            "reflection": "关注学生能否将传感器与实际物联网项目关联，下节课增加动手环节。",
        },
        task={"subject": "物联网", "class_type": "新授课"},
    )
    assert "pedagogy_checks" in report
    assert "score" in report
    assert report["score"] >= 60, f"Score {report['score']} too low for good content"
