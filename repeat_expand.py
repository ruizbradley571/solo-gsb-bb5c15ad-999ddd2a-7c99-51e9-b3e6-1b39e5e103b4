"""乐谱反复段展开核心逻辑。

输入语法（逐行）：
    [|:] 小节编号 [:|xN]
- `|:`   写在编号前，表示反复起点；
- `:|xN` 写在编号后，表示反复终点，N 为反复遍数（2～9）；
- 反复段允许嵌套；
- 空行与以 `#` 开头的行会被忽略；
- 兼容全角字符「｜」「：」「ｘ／Ｘ」。

校验：起止配对、小节编号唯一性；格式错误定位到输入行。
展开：按嵌套层级展开为实际演奏顺序，超过上限（默认 5000 小节）即停止，
并指出导致超限的源行（正在展开的最内层反复终点所在行；无反复时为当前小节行）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

DEFAULT_LIMIT = 5000
MIN_TIMES = 2
MAX_TIMES = 9

_LINE_RE = re.compile(
    r"^\s*(?P<open>\|:)?\s*(?P<num>\d+)\s*"
    r"(?P<close>:\|\s*[xX]\s*(?P<times>\d+))?\s*$"
)

# 全角 -> 半角归一化
_TRANS = str.maketrans({
    "｜": "|",
    "：": ":",
    "Ｘ": "x",
    "ｘ": "x",
    "　": " ",
})


@dataclass
class Measure:
    """一个待演奏的小节。number 为原小节编号，line_no 为源行号。"""

    number: int
    line_no: int


@dataclass
class RepeatGroup:
    """一个反复段（可嵌套）。children 为 Measure / RepeatGroup 列表。"""

    start_line: int
    children: list = field(default_factory=list)
    times: int = 0
    end_line: int = 0


@dataclass
class InputError:
    line_no: int
    message: str


class ExpansionOverflow(Exception):
    """展开小节数超过上限。line_no 为导致超限的源行。"""

    def __init__(self, line_no: int, count: int, is_repeat_line: bool):
        super().__init__(f"expansion overflow at source line {line_no}")
        self.line_no = line_no
        self.count = count
        self.is_repeat_line = is_repeat_line


def _parse_line(raw: str, line_no: int):
    """解析单行。

    返回 (start, number, times)；空行 / 注释行返回 None；出错返回 InputError。
    """
    text = raw.translate(_TRANS).strip()
    if not text or text.startswith("#"):
        return None

    m = _LINE_RE.match(text)
    if m:
        number = int(m.group("num"))
        if number < 1:
            return InputError(line_no, "小节编号必须是不小于 1 的整数")
        times = m.group("times")
        if times is not None:
            t = int(times)
            if not (MIN_TIMES <= t <= MAX_TIMES):
                return InputError(
                    line_no, f"反复次数 x{t} 超出范围，N 必须为 {MIN_TIMES}～{MAX_TIMES}"
                )
            times = t
        return (bool(m.group("open")), number, times)

    # 尽量给出有针对性的错误提示
    if not re.search(r"\d", text):
        hint = "缺少小节编号"
    elif ":|" in text:
        hint = "反复终点应写作「:|xN」（N 为 2～9），例如 12:|x3"
    elif "|:" in text and not text.startswith("|:"):
        hint = "反复起点「|:」必须写在编号之前"
    else:
        hint = "格式应为「[|:] 小节编号 [:|xN]」"
    return InputError(line_no, f"格式错误：{hint}")


def parse(text: str):
    """解析全部输入并校验。

    返回 (roots, errors)：roots 为顶层元素列表（Measure / RepeatGroup）。
    errors 非空时 roots 为空列表。
    """
    roots: list = []
    errors: list[InputError] = []
    parsed = []  # (line_no, start, number, times)
    seen: dict[int, int] = {}  # 小节编号 -> 首次出现的行号

    for line_no, raw in enumerate(text.splitlines(), start=1):
        result = _parse_line(raw, line_no)
        if result is None:
            continue
        if isinstance(result, InputError):
            errors.append(result)
            continue
        start, number, times = result
        if number in seen:
            errors.append(
                InputError(line_no, f"小节编号 {number} 与第 {seen[number]} 行重复")
            )
            continue
        seen[number] = line_no
        parsed.append((line_no, start, number, times))

    if errors:
        return [], errors

    # 组装嵌套结构并校验起止配对（栈式括号匹配）
    stack: list[tuple[RepeatGroup, list]] = []
    current = roots
    for line_no, start, number, times in parsed:
        if start:
            group = RepeatGroup(start_line=line_no)
            current.append(group)
            stack.append((group, current))
            current = group.children
        current.append(Measure(number, line_no))
        if times is not None:
            if not stack:
                errors.append(
                    InputError(
                        line_no, f"反复终点「:|x{times}」之前没有匹配的反复起点「|:」"
                    )
                )
            else:
                group, parent = stack.pop()
                group.times = times
                group.end_line = line_no
                current = parent

    for group, _parent in stack:
        errors.append(
            InputError(group.start_line, "反复起点「|:」缺少对应的反复终点「:|xN」")
        )

    if errors:
        return [], errors
    return roots, []


def expand(roots: list, limit: int = DEFAULT_LIMIT) -> list[Measure]:
    """按嵌套层级展开为实际演奏顺序。

    展开结果超过 limit 时抛出 ExpansionOverflow，并指出导致超限的源行。
    使用显式栈迭代，避免深层嵌套触发递归上限。
    """
    out: list[Measure] = []
    # 帧: [子元素列表, 下一索引, 剩余遍数, 反复终点行号(0 表示非反复帧)]
    stack = [[roots, 0, 1, 0]]
    active_ends: list[int] = []  # 当前正在展开的反复终点行号（内层在后）

    while stack:
        frame = stack[-1]
        children, idx, remaining, end_line = frame
        if idx >= len(children):
            if remaining > 1:  # 开始下一遍反复
                frame[1] = 0
                frame[2] = remaining - 1
                continue
            stack.pop()
            if end_line:
                active_ends.pop()
            continue
        frame[1] = idx + 1
        node = children[idx]
        if isinstance(node, Measure):
            out.append(node)
            if len(out) > limit:
                if active_ends:
                    raise ExpansionOverflow(active_ends[-1], len(out), True)
                raise ExpansionOverflow(node.line_no, len(out), False)
        else:
            stack.append([node.children, 0, node.times, node.end_line])
            active_ends.append(node.end_line)
    return out


def expand_text(text: str, limit: int = DEFAULT_LIMIT) -> dict:
    """处理整段输入，返回给前端 / API 使用的字典。"""
    roots, errors = parse(text)
    if errors:
        return {
            "ok": False,
            "errors": [
                {"line": e.line_no, "message": f"第 {e.line_no} 行：{e.message}"}
                for e in errors
            ],
        }
    if not roots:
        return {
            "ok": False,
            "errors": [{"line": 0, "message": "输入为空，请至少输入一行小节编号"}],
        }

    try:
        measures = expand(roots, limit)
    except ExpansionOverflow as ov:
        if ov.is_repeat_line:
            cause = f"导致超限的是第 {ov.line_no} 行的反复终点「:|xN」"
        else:
            cause = f"展开到第 {ov.line_no} 行的小节时总数超限"
        return {
            "ok": False,
            "overflow": True,
            "line": ov.line_no,
            "limit": limit,
            "message": f"展开超过 {limit} 小节上限，已停止；{cause}",
        }

    return {
        "ok": True,
        "total": len(measures),
        "measures": [
            {"seq": i, "number": m.number, "line": m.line_no}
            for i, m in enumerate(measures, start=1)
        ],
    }
