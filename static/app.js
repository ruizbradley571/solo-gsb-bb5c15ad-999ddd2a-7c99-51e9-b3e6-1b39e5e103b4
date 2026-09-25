"use strict";

const inputEl = document.getElementById("input");
const messagesEl = document.getElementById("messages");
const summaryEl = document.getElementById("summary");
const tableEl = document.getElementById("result");
const tbodyEl = tableEl.querySelector("tbody");
const expandBtn = document.getElementById("expandBtn");
const exampleBtn = document.getElementById("exampleBtn");
const clearBtn = document.getElementById("clearBtn");
const csvBtn = document.getElementById("csvBtn");

const EXAMPLE = [
  "# 注释行会被忽略",
  "1",
  "|: 2",
  "|: 3",
  "4 :|x2",
  "5 :|x3",
  "6",
  "|: 7",
  "8 :|x2",
].join("\n");

// 最近一次成功展开的结果（用于下载与页面同内容的 CSV）
let lastRows = null;

function showMessages(html, kind) {
  messagesEl.className = kind || "";
  messagesEl.innerHTML = html || "";
}

function clearResult() {
  lastRows = null;
  csvBtn.disabled = true;
  tableEl.hidden = true;
  tbodyEl.textContent = "";
  summaryEl.textContent = "";
}

async function expand() {
  clearResult();
  showMessages("");
  expandBtn.disabled = true;
  try {
    const resp = await fetch("/api/expand", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input: inputEl.value }),
    });
    const data = await resp.json();

    if (!data.ok) {
      if (data.overflow) {
        showMessages(`<div class="overflow">⚠ ${escapeHtml(data.message)}</div>`, "error");
      } else {
        const items = (data.errors || [])
          .map((e) => `<li>${escapeHtml(e.message)}</li>`)
          .join("");
        showMessages(`<ul class="errors">${items}</ul>`, "error");
      }
      return;
    }

    lastRows = data.measures;
    renderTable(data.measures);
    summaryEl.textContent = `展开成功：共 ${data.total} 小节`;
    csvBtn.disabled = false;
  } catch (err) {
    showMessages(`<div class="overflow">请求失败：${escapeHtml(String(err))}</div>`, "error");
  } finally {
    expandBtn.disabled = false;
  }
}

function renderTable(rows) {
  const frag = document.createDocumentFragment();
  for (const r of rows) {
    const tr = document.createElement("tr");
    for (const key of ["seq", "number", "line"]) {
      const td = document.createElement("td");
      td.textContent = r[key];
      tr.appendChild(td);
    }
    frag.appendChild(tr);
  }
  tbodyEl.textContent = "";
  tbodyEl.appendChild(frag);
  tableEl.hidden = false;
}

function downloadCsv() {
  if (!lastRows) return;
  const lines = ["演奏序号,原小节编号,源行号"];
  for (const r of lastRows) {
    lines.push(`${r.seq},${r.number},${r.line}`);
  }
  // BOM 便于 Excel 识别 UTF-8
  const blob = new Blob(["\ufeff" + lines.join("\r\n")], {
    type: "text/csv;charset=utf-8",
  });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "expanded_measures.csv";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(a.href);
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[c]));
}

expandBtn.addEventListener("click", expand);
csvBtn.addEventListener("click", downloadCsv);
exampleBtn.addEventListener("click", () => {
  inputEl.value = EXAMPLE;
  inputEl.focus();
});
clearBtn.addEventListener("click", () => {
  inputEl.value = "";
  clearResult();
  showMessages("");
  inputEl.focus();
});
inputEl.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
    e.preventDefault();
    expand();
  }
});
