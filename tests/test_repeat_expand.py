"""核心展开逻辑单元测试（不依赖 Flask）。

运行：python3 -m unittest discover -s tests -v
"""

import unittest

from repeat_expand import expand_text, parse, expand, ExpansionOverflow


def numbers(result):
    return [m["number"] for m in result["measures"]]


def lines(result):
    return [m["line"] for m in result["measures"]]


class TestBasicExpansion(unittest.TestCase):
    def test_plain_sequence(self):
        r = expand_text("1\n2\n3")
        self.assertTrue(r["ok"])
        self.assertEqual(numbers(r), [1, 2, 3])
        self.assertEqual(lines(r), [1, 2, 3])
        self.assertEqual([m["seq"] for m in r["measures"]], [1, 2, 3])
        self.assertEqual(r["total"], 3)

    def test_simple_repeat(self):
        r = expand_text("1\n|: 2\n3 :|x2\n4")
        self.assertTrue(r["ok"])
        self.assertEqual(numbers(r), [1, 2, 3, 2, 3, 4])
        self.assertEqual(lines(r), [1, 2, 3, 2, 3, 4])

    def test_nested_repeat(self):
        text = "1\n|: 2\n|: 3\n4 :|x2\n5 :|x3\n6"
        r = expand_text(text)
        self.assertTrue(r["ok"])
        inner = [3, 4, 3, 4]
        outer = [2] + inner + [5]
        self.assertEqual(numbers(r), [1] + outer * 3 + [6])
        self.assertEqual(r["total"], 20)

    def test_single_line_repeat(self):
        r = expand_text("|: 5 :|x3")
        self.assertTrue(r["ok"])
        self.assertEqual(numbers(r), [5, 5, 5])

    def test_blank_and_comment_lines_ignored(self):
        r = expand_text("# 注释\n\n1\n   \n#|: 2\n2")
        self.assertTrue(r["ok"])
        self.assertEqual(numbers(r), [1, 2])
        self.assertEqual(lines(r), [3, 6])

    def test_fullwidth_chars(self):
        r = expand_text("｜： 1\n2 ：｜x2")
        self.assertTrue(r["ok"])
        self.assertEqual(numbers(r), [1, 2, 1, 2])

    def test_whitespace_tolerance(self):
        r = expand_text("  |:   7  \n 8   :|  x2 ")
        self.assertTrue(r["ok"])
        self.assertEqual(numbers(r), [7, 8, 7, 8])


class TestValidation(unittest.TestCase):
    def assert_error_at(self, text, line, needle=""):
        r = expand_text(text)
        self.assertFalse(r["ok"])
        self.assertNotIn("overflow", r)
        msgs = [e["message"] for e in r["errors"]]
        self.assertTrue(
            any(f"第 {line} 行" in m for m in msgs),
            f"期望第 {line} 行报错，实际：{msgs}",
        )
        if needle:
            self.assertTrue(
                any(needle in m for m in msgs),
                f"期望错误包含 {needle!r}，实际：{msgs}",
            )

    def test_duplicate_number(self):
        self.assert_error_at("1\n2\n1", 3, "重复")

    def test_unmatched_end(self):
        self.assert_error_at("1 :|x2", 1, "没有匹配的反复起点")

    def test_unclosed_start(self):
        self.assert_error_at("|: 1\n2", 1, "缺少对应的反复终点")

    def test_unclosed_outer_start(self):
        r = expand_text("|: 1\n|: 2\n3 :|x2")
        self.assertFalse(r["ok"])
        # 内层已配对，仅剩第 1 行的外层起点未闭合
        self.assertEqual(r["errors"][0]["line"], 1)

    def test_times_out_of_range(self):
        self.assert_error_at("|: 1\n2 :|x1", 2, "2～9")
        self.assert_error_at("|: 1\n2 :|x10", 2, "2～9")

    def test_missing_end_times(self):
        self.assert_error_at("|: 1\n2 :|", 2, ":|xN")

    def test_garbage_line(self):
        self.assert_error_at("1\nhello\n3", 2, "格式错误")

    def test_zero_number(self):
        self.assert_error_at("0", 1, "不小于 1")

    def test_empty_input(self):
        r = expand_text("   \n# 只有注释\n")
        self.assertFalse(r["ok"])
        self.assertIn("输入为空", r["errors"][0]["message"])

    def test_multiple_errors_collected(self):
        # 行级解析错误会一次性全部报出（配对校验在无解析错误后才进行）
        r = expand_text("abc\n1\n1")
        self.assertFalse(r["ok"])
        self.assertEqual(len(r["errors"]), 2)
        self.assertEqual([e["line"] for e in r["errors"]], [1, 3])


class TestOverflow(unittest.TestCase):
    def test_nested_overflow_points_to_innermost_repeat_line(self):
        # 9^4 = 6561 > 5000
        text = "|: 1\n|: 2\n|: 3\n|: 4\n5 :|x9\n6 :|x9\n7 :|x9\n8 :|x9"
        r = expand_text(text)
        self.assertFalse(r["ok"])
        self.assertTrue(r["overflow"])
        self.assertEqual(r["line"], 5)  # 最内层反复终点所在行
        self.assertIn("5000", r["message"])

    def test_plain_overflow_points_to_measure_line(self):
        text = "\n".join(str(i) for i in range(1, 5002))
        r = expand_text(text)
        self.assertFalse(r["ok"])
        self.assertTrue(r["overflow"])
        self.assertEqual(r["line"], 5001)

    def test_exactly_at_limit_ok(self):
        text = "\n".join(str(i) for i in range(1, 5001))
        r = expand_text(text)
        self.assertTrue(r["ok"])
        self.assertEqual(r["total"], 5000)

    def test_custom_limit(self):
        r = expand_text("|: 1\n2 :|x9", limit=5)
        self.assertFalse(r["ok"])
        self.assertTrue(r["overflow"])
        self.assertEqual(r["line"], 2)


class TestParseTree(unittest.TestCase):
    def test_parse_returns_tree(self):
        roots, errors = parse("|: 1\n2 :|x2")
        self.assertEqual(errors, [])
        self.assertEqual(len(roots), 1)
        group = roots[0]
        self.assertEqual(group.times, 2)
        self.assertEqual(group.start_line, 1)
        self.assertEqual(group.end_line, 2)
        self.assertEqual([m.number for m in group.children], [1, 2])

    def test_expand_directly(self):
        roots, _ = parse("|: 1\n2 :|x2")
        out = expand(roots, limit=10)
        self.assertEqual([m.number for m in out], [1, 2, 1, 2])
        with self.assertRaises(ExpansionOverflow):
            expand(roots, limit=3)


if __name__ == "__main__":
    unittest.main()
