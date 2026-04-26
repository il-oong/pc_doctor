"""HTML report generator."""
from __future__ import annotations

import html
import time
from pathlib import Path

from utils.format import timestamp

from .checks import Severity
from .score import HealthSummary

_SEVERITY_COLOR = {
    Severity.HEALTHY: "#2BB673",
    Severity.WARNING: "#F5A623",
    Severity.CRITICAL: "#E5484D",
    Severity.UNKNOWN: "#8FA0B0",
}


def _score_color(score: int) -> str:
    if score >= 90:
        return _SEVERITY_COLOR[Severity.HEALTHY]
    if score >= 70:
        return _SEVERITY_COLOR[Severity.WARNING]
    return _SEVERITY_COLOR[Severity.CRITICAL]


def to_html(summary: HealthSummary) -> str:
    now = timestamp(summary.finished_at)
    sc = summary.score
    sc_color = _score_color(sc)

    rows = ""
    recs_html = ""
    for r in summary.results:
        c = _SEVERITY_COLOR.get(r.severity, "#8FA0B0")
        sev = r.severity.label_ko
        rows += (
            f"<tr>"
            f"<td>{html.escape(r.icon)} {html.escape(r.title)}</td>"
            f"<td style='color:{c};font-weight:600'>{sev}</td>"
            f"<td style='font-weight:600;color:{_score_color(r.score)}'>{r.score}</td>"
            f"<td>{html.escape(r.summary)}</td>"
            f"</tr>\n"
        )
        for rec in r.recommendations:
            text = rec.text if hasattr(rec, "text") else str(rec)
            label = getattr(rec, "action_label", None)
            tag = (
                f" <span style='font-size:11px;color:#2E7DD7;background:#E6F0FB;"
                f"padding:2px 8px;border-radius:6px;margin-left:6px'>"
                f"조치: {html.escape(label)}</span>"
            ) if label else ""
            recs_html += (
                f"<li><strong>{html.escape(r.title)}</strong>: "
                f"{html.escape(text)}{tag}</li>\n"
            )

    if not recs_html:
        recs_html = "<li>모든 항목이 정상입니다. 권장 조치가 없습니다.</li>"

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>PC Doctor 진단 리포트 — {now}</title>
<style>
  body{{font-family:'Segoe UI',system-ui,sans-serif;background:#F7FAFC;color:#1F2D3D;margin:0;padding:24px}}
  .card{{background:#fff;border:1px solid #E3EAF1;border-radius:12px;padding:24px;margin-bottom:20px;box-shadow:0 1px 2px rgba(15,23,42,.04)}}
  h1{{color:#2E7DD7;margin:0 0 4px}}
  .score{{font-size:72px;font-weight:800;line-height:1;color:{sc_color}}}
  .label{{font-size:13px;color:#5A6B7B;margin-bottom:16px}}
  table{{width:100%;border-collapse:collapse}}
  th,td{{text-align:left;padding:10px 12px;border-bottom:1px solid #EEF3F7;font-size:14px}}
  th{{font-size:12px;color:#5A6B7B;text-transform:uppercase;letter-spacing:.04em}}
  ul{{padding-left:20px;line-height:1.8}}
  .footer{{font-size:12px;color:#8FA0B0;margin-top:12px}}
</style>
</head>
<body>
<div class="card">
  <h1>🩺 PC Doctor 진단 리포트</h1>
  <div class="label">환자: {html.escape(summary.results[-1].metrics.get('hostname', 'Unknown') if summary.results else 'Unknown')}</div>
  <div class="score">{sc}</div>
  <div class="label">종합 헬스 스코어 / 100 &nbsp;·&nbsp; {html.escape(summary.severity.label_ko)} &nbsp;·&nbsp; {now}</div>
  <p style="color:#5A6B7B">{html.escape(summary.headline)}</p>
</div>

<div class="card">
  <h2 style="margin-top:0;font-size:16px;color:#2E7DD7">📋 바이탈 사인</h2>
  <table>
    <tr><th>항목</th><th>상태</th><th>점수</th><th>요약</th></tr>
    {rows}
  </table>
</div>

<div class="card">
  <h2 style="margin-top:0;font-size:16px;color:#2E7DD7">💊 처방전 (Recommendations)</h2>
  <ul>
    {recs_html}
  </ul>
</div>

<p class="footer">진단 시각: {now} &nbsp;·&nbsp; 소요: {summary.duration_ms}ms &nbsp;·&nbsp; PC Doctor</p>
</body>
</html>"""


def save_html(summary: HealthSummary, path: str | Path | None = None) -> Path:
    if path is None:
        reports_dir = Path.home() / ".pc_doctor" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        fname = f"report_{int(summary.finished_at)}.html"
        path = reports_dir / fname
    path = Path(path)
    path.write_text(to_html(summary), encoding="utf-8")
    return path
