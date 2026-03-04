#!/usr/bin/env python3
from __future__ import annotations

import html
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import List
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
PROBLEMS_DIR = ROOT / "problems"
HOST = "127.0.0.1"
PORT = int(os.environ.get("JUDGE_PORT", "8000"))

VALID_DIR_RE = re.compile(r"^[A-Za-z0-9_-]+$")


@dataclass
class TestCase:
    name: str
    input_path: Path
    output_path: Path


@dataclass
class Problem:
    dir_name: str
    problem_id: str
    title: str
    time_limit_sec: float
    compare: str
    statement_md: str
    tests: List[TestCase]


@dataclass
class CaseResult:
    name: str
    status: str
    elapsed_ms: int
    stdout: str
    stderr: str
    expected: str


def normalize_trim(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip(" \t") for line in text.split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def compare_output(expected: str, actual: str, mode: str) -> bool:
    if mode == "exact":
        return expected == actual
    if mode == "trim":
        return normalize_trim(expected) == normalize_trim(actual)
    if mode == "tokens":
        return expected.split() == actual.split()
    return expected == actual


def discover_tests(tests_dir: Path) -> List[TestCase]:
    inputs = sorted(tests_dir.glob("in*.txt"))
    cases = []
    for input_path in inputs:
        suffix = input_path.stem[2:]
        output_path = tests_dir / f"out{suffix}.txt"
        if output_path.exists():
            cases.append(TestCase(name=input_path.name, input_path=input_path, output_path=output_path))
    return cases


def load_problem(problem_dir: Path) -> Problem | None:
    if not problem_dir.is_dir() or not VALID_DIR_RE.match(problem_dir.name):
        return None

    meta_path = problem_dir / "meta.json"
    statement_path = problem_dir / "statement.md"
    tests_dir = problem_dir / "tests"
    if not (meta_path.exists() and statement_path.exists() and tests_dir.is_dir()):
        return None

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        problem = Problem(
            dir_name=problem_dir.name,
            problem_id=str(meta["id"]),
            title=str(meta["title"]),
            time_limit_sec=float(meta["time_limit_sec"]),
            compare=str(meta["compare"]),
            statement_md=statement_path.read_text(encoding="utf-8"),
            tests=discover_tests(tests_dir),
        )
        if problem.compare not in {"exact", "trim", "tokens"}:
            return None
        return problem
    except Exception:
        return None


def load_problems() -> List[Problem]:
    if not PROBLEMS_DIR.exists():
        return []
    problems = []
    for d in sorted(PROBLEMS_DIR.iterdir()):
        problem = load_problem(d)
        if problem:
            problems.append(problem)
    return problems


def run_case(code: str, case: TestCase, time_limit_sec: float) -> CaseResult:
    case_input = case.input_path.read_text(encoding="utf-8")
    expected = case.output_path.read_text(encoding="utf-8")

    with tempfile.TemporaryDirectory(prefix="judge_") as tmpdir:
        script_path = Path(tmpdir) / "main.py"
        script_path.write_text(code, encoding="utf-8")

        start = time.perf_counter()
        try:
            completed = subprocess.run(
                [sys.executable, str(script_path)],
                input=case_input,
                text=True,
                capture_output=True,
                timeout=time_limit_sec,
                encoding="utf-8",
                errors="replace",
            )
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            if completed.returncode != 0:
                status = "RE"
            else:
                status = "OK"
            return CaseResult(
                name=case.name,
                status=status,
                elapsed_ms=elapsed_ms,
                stdout=completed.stdout,
                stderr=completed.stderr,
                expected=expected,
            )
        except subprocess.TimeoutExpired as e:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return CaseResult(
                name=case.name,
                status="TLE",
                elapsed_ms=elapsed_ms,
                stdout=e.stdout or "",
                stderr=e.stderr or "",
                expected=expected,
            )


def judge(problem: Problem, code: str) -> tuple[str, List[CaseResult]]:
    results = []
    for case in problem.tests:
        result = run_case(code, case, problem.time_limit_sec)
        if result.status == "OK":
            result.status = "AC" if compare_output(result.expected, result.stdout, problem.compare) else "WA"
        results.append(result)
        if result.status != "AC":
            verdict = "NG"
            return verdict, results
    return "AC", results


def markdown_as_pre(md: str) -> str:
    return f"<pre class='statement'>{html.escape(md)}</pre>"


def build_starter_code(problem: Problem | None) -> str:
    if problem is None:
        return ""
    if problem.problem_id == "001_add":
        return "A, B = map(int, input().split())\n# この下からコードを書こう\n"
    return "# この下からコードを書こう\n"


def render_page(problems: List[Problem], selected: str = "", code: str = "", verdict: str = "", results: List[CaseResult] | None = None) -> str:
    options = []
    selected_problem = None
    for p in problems:
        is_selected = " selected" if p.dir_name == selected else ""
        options.append(f"<option value='{html.escape(p.dir_name)}'{is_selected}>{html.escape(p.problem_id)} - {html.escape(p.title)}</option>")
        if p.dir_name == selected:
            selected_problem = p
    if selected_problem is None and problems:
        selected_problem = problems[0]
        selected = selected_problem.dir_name

    if not code:
        code = build_starter_code(selected_problem)

    statement_html = markdown_as_pre(selected_problem.statement_md) if selected_problem else "<p>問題がありません。</p>"
    compare_mode = selected_problem.compare if selected_problem else "-"

    table_rows = ""
    if results:
        for r in results:
            details = ""
            if r.status == "WA":
                details = (
                    f"<details><summary>diff / stdout</summary>"
                    f"<p><b>expected</b></p><pre>{html.escape(r.expected)}</pre>"
                    f"<p><b>actual</b></p><pre>{html.escape(r.stdout)}</pre></details>"
                )
            elif r.status in {"RE", "TLE"}:
                details = (
                    f"<details><summary>stderr / stdout</summary>"
                    f"<p><b>stderr</b></p><pre>{html.escape(r.stderr)}</pre>"
                    f"<p><b>stdout</b></p><pre>{html.escape(r.stdout)}</pre></details>"
                )
            table_rows += (
                f"<tr><td>{html.escape(r.name)}</td><td>{r.status}</td><td>{r.elapsed_ms}</td></tr>"
                f"<tr><td colspan='3'>{details}</td></tr>"
            )

    verdict_class = "verdict-ac" if verdict == "AC" else "verdict-ng"
    verdict_label = "💮 せいかい！" if verdict == "AC" else "💪 もういちど やってみよう！"
    verdict_html = f"<h2 class='verdict {verdict_class}'>{verdict_label}</h2>" if verdict else ""
    return f"""<!doctype html>
<html lang='ja'><head><meta charset='utf-8'><title>Robo Offline Judge</title>
<style>
:root {{
  --bg: #fffaf2;
  --card: #ffffff;
  --text: #374151;
  --mint: #b9f4d1;
  --sky: #d6ecff;
  --peach: #ffe2c4;
  --line: #f4c585;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  font-family: "Hiragino Maru Gothic ProN", "Yu Gothic", "Meiryo", sans-serif;
  color: var(--text);
  background: radial-gradient(circle at top, #fffdf8 0%, var(--bg) 65%);
}}
.page {{ max-width: 980px; margin: 0 auto; padding: 18px; }}
.header {{
  background: linear-gradient(135deg, var(--sky), #f4f9ff);
  border: 3px solid #8cc8ff;
  border-radius: 22px;
  padding: 18px;
  margin-bottom: 16px;
}}
h1 {{ margin: 0; font-size: 34px; }}
.subtitle {{ margin: 8px 0 0; font-size: 18px; }}
.card {{
  background: var(--card);
  border: 3px solid var(--line);
  border-radius: 20px;
  padding: 16px;
  margin-bottom: 14px;
  box-shadow: 0 6px 0 rgba(244, 197, 133, 0.35);
}}
label, h3 {{ font-size: 22px; margin: 8px 0; }}
select, button {{ font-size: 20px; border-radius: 12px; border: 2px solid #8cc8ff; padding: 8px 12px; }}
select {{ background: #f8fdff; }}
.compare {{ background: var(--mint); border-radius: 14px; padding: 8px 12px; font-size: 18px; display: inline-block; }}
textarea {{
  width: 100%;
  min-height: 280px;
  font-family: "M PLUS Rounded 1c", "Consolas", monospace;
  font-size: 18px;
  border-radius: 14px;
  border: 3px solid #8cc8ff;
  padding: 12px;
  background: #fcfeff;
}}
button {{
  margin-top: 10px;
  background: linear-gradient(180deg, #ffd797, var(--peach));
  border: 2px solid #f9a048;
  font-weight: bold;
  cursor: pointer;
}}
.statement {{
  background: #fffef8;
  border: 2px dashed #8cc8ff;
  border-radius: 14px;
  padding: 12px;
  white-space: pre-wrap;
  font-size: 17px;
  line-height: 1.6;
}}
.verdict {{
  border-radius: 16px;
  padding: 10px 14px;
  text-align: center;
  font-size: 28px;
}}
.verdict-ac {{ background: #c8f7d7; border: 3px solid #41ba70; }}
.verdict-ng {{ background: #ffe3cc; border: 3px solid #ff8a3d; }}
table {{ border-collapse: separate; border-spacing: 0; width: 100%; background: #fff; border: 3px solid #8cc8ff; border-radius: 14px; overflow: hidden; }}
td, th {{ border-bottom: 1px solid #c9e5ff; padding: 8px; vertical-align: top; font-size: 17px; }}
th {{ background: #eaf5ff; }}
tr:last-child td {{ border-bottom: 0; }}
</style></head>
<body>
<div class='page'>
<div class='header'>
<h1>🐣 やさしい Python ジャッジ</h1>
<p class='subtitle'>しょうがっこう ていがくねんむけ 🌈 じぶんのペースで チャレンジしよう！</p>
</div>
<form method='post' action='/submit'>
<div class='card'>
<label>問題選択</label><br>
<select name='problem_dir'>{''.join(options)}</select>
<p class='compare'>くらべかた: <b>{html.escape(compare_mode)}</b></p>
<h3>問題文</h3>{statement_html}
</div>
<div class='card'>
<h3>コード入力</h3>
<textarea name='code'>{html.escape(code)}</textarea><br>
<button type='submit'>🚀 ていしゅつして チェック！</button>
</div>
</form>
{verdict_html}
<div class='card'>
<table>
<tr><th>テスト</th><th>けっか</th><th>じかん(ms)</th></tr>
{table_rows}
</table>
</div>
</div>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _respond_html(self, content: str, status: int = 200) -> None:
        body = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/":
            self._respond_html("<h1>Not Found</h1>", status=HTTPStatus.NOT_FOUND)
            return
        problems = load_problems()
        self._respond_html(render_page(problems))

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/submit":
            self._respond_html("<h1>Not Found</h1>", status=HTTPStatus.NOT_FOUND)
            return

        length = int(self.headers.get("Content-Length", "0"))
        payload = self.rfile.read(length).decode("utf-8", errors="replace")
        form = parse_qs(payload)
        problem_dir = form.get("problem_dir", [""])[0]
        code = form.get("code", [""])[0]

        problems = load_problems()
        problem = next((p for p in problems if p.dir_name == problem_dir), None)
        if problem is None:
            self._respond_html(render_page(problems, code=code, verdict="NG"))
            return

        verdict, results = judge(problem, code)
        self._respond_html(render_page(problems, selected=problem_dir, code=code, verdict=verdict, results=results))


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Judge started: http://{HOST}:{PORT}/")
    server.serve_forever()


if __name__ == "__main__":
    main()
