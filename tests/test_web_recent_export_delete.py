from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_recent_exports_have_download_and_confirmed_delete_controls():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "web" / "static" / "app.js").read_text(encoding="utf-8")

    assert "最近导出" in html
    assert "删除" in script
    assert "下载" in script
    assert "确定删除这份教案吗？删除后文件将无法下载。" in script
    assert 'method: "DELETE"' in script
    assert "/api/history/" in script
    assert "已删除导出文件。" in script
    assert "loadHistory()" in script
    assert "showToast" in script
