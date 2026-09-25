"""Flask 接口测试（需要安装 flask；未安装时自动跳过）。"""

import unittest

try:
    from app import app
except ImportError:  # pragma: no cover
    app = None


@unittest.skipIf(app is None, "flask 未安装，跳过接口测试")
class TestApi(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_index_page(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("反复".encode(), resp.data)

    def test_expand_ok(self):
        resp = self.client.post(
            "/api/expand", json={"input": "1\n|: 2\n3 :|x2"}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual([m["number"] for m in data["measures"]], [1, 2, 3, 2, 3])

    def test_expand_validation_error(self):
        resp = self.client.post("/api/expand", json={"input": "1\n1"})
        data = resp.get_json()
        self.assertFalse(data["ok"])
        self.assertEqual(data["errors"][0]["line"], 2)

    def test_expand_bad_request(self):
        resp = self.client.post("/api/expand", json={})
        self.assertEqual(resp.status_code, 400)

    def test_csv_download(self):
        resp = self.client.post("/api/csv", json={"input": "|: 1\n2 :|x2"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/csv", resp.content_type)
        self.assertIn("attachment", resp.headers["Content-Disposition"])
        text = resp.data.decode("utf-8-sig")
        rows = text.strip().split("\r\n")
        self.assertEqual(rows[0], "演奏序号,原小节编号,源行号")
        self.assertEqual(rows[1], "1,1,1")
        self.assertEqual(rows[2], "2,2,2")
        self.assertEqual(rows[3], "3,1,1")
        self.assertEqual(len(rows), 5)

    def test_csv_error_returns_json(self):
        resp = self.client.post("/api/csv", json={"input": "1 :|x2"})
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.get_json()["ok"])


if __name__ == "__main__":
    unittest.main()
