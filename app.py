"""Flask 入口：乐谱反复段展开 Web 应用。

路由：
    GET  /            页面
    POST /api/expand  JSON {"input": "..."} -> 展开结果或行级错误
    POST /api/csv     JSON {"input": "..."} -> 同内容 CSV 下载
"""

import csv
import io
import os

from flask import Flask, Response, jsonify, request, send_from_directory

from repeat_expand import DEFAULT_LIMIT, expand_text

app = Flask(__name__, static_folder="static", static_url_path="")

MAX_INPUT_CHARS = 200_000


def get_limit() -> int:
    """展开上限，可用环境变量 MAX_MEASURES 覆盖（默认 5000）。"""
    try:
        return max(1, int(os.environ.get("MAX_MEASURES", DEFAULT_LIMIT)))
    except ValueError:
        return DEFAULT_LIMIT


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


def _read_input():
    data = request.get_json(silent=True)
    if not data or not isinstance(data.get("input"), str):
        return None
    return data["input"]


def _input_error(message: str, status: int = 400):
    return jsonify({"ok": False, "errors": [{"line": 0, "message": message}]}), status


@app.post("/api/expand")
def api_expand():
    text = _read_input()
    if text is None:
        return _input_error('请求格式错误：需要 JSON 体 {"input": "..."}')
    if len(text) > MAX_INPUT_CHARS:
        return _input_error(f"输入过长（超过 {MAX_INPUT_CHARS} 字符）")
    return jsonify(expand_text(text, get_limit()))


@app.post("/api/csv")
def api_csv():
    text = _read_input()
    if text is None:
        return _input_error('请求格式错误：需要 JSON 体 {"input": "..."}')
    if len(text) > MAX_INPUT_CHARS:
        return _input_error(f"输入过长（超过 {MAX_INPUT_CHARS} 字符）")
    result = expand_text(text, get_limit())
    if not result.get("ok"):
        return jsonify(result), 400

    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(["演奏序号", "原小节编号", "源行号"])
    for m in result["measures"]:
        writer.writerow([m["seq"], m["number"], m["line"]])
    # 加 BOM 便于 Excel 直接打开中文表头
    return Response(
        "\ufeff" + buf.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="expanded_measures.csv"'
        },
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
