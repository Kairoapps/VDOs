"""Self-contained HTML dashboard built from the latest analysis result (no external assets)."""
from __future__ import annotations

import html
import json
from pathlib import Path

from . import analysis, config

PLAT = {"instagram": "IG", "tiktok": "TT", "youtube": "YT"}
STATUS_LABEL = {"available": "Available", "cooling": "Cooling down", "needs_edit": "Needs edit", "exhausted": "Used up",
                "retired": "Retired", "unusable": "Unusable"}
LEVEL = {"healthy": ("good", "Healthy"), "heads_up": ("warning", "Heads-up"), "urgent": ("critical", "Urgent"),
         "empty": ("critical", "Empty")}
DIM_TITLES = {"topic_format": "Video type (topic × format)", "format": "Format", "hook_type": "Hook",
              "caption_style": "Caption style", "music_mood": "Music mood", "track": "Track",
              "length_bucket": "Length", "time_slot": "Time slot", "hashtag_set": "Hashtag set"}

CSS = """
:root{--surface:#fcfcfb;--page:#f9f9f7;--ink:#0b0b0b;--ink2:#52514e;--muted:#8a8984;--grid:#e6e5e0;--bar:#2a78d6;--bar-weak:#b7d3f6;
--good:#0ca30c;--warning:#fab219;--critical:#d03b3b}
@media (prefers-color-scheme:dark){:root{--surface:#1a1a19;--page:#0d0d0d;--ink:#f0efec;--ink2:#c3c2b7;--muted:#8f8e86;--grid:#2e2e2c;--bar:#3987e5;--bar-weak:#184f95}}
*{box-sizing:border-box}body{margin:0;background:var(--page);color:var(--ink);font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif}
main{max-width:1180px;margin:0 auto;padding:28px 20px 60px}h1{font-size:22px;margin:0 0 4px}h2{font-size:15px;margin:0 0 12px}
.sub{color:var(--ink2);margin-bottom:22px}.grid{display:grid;gap:14px}.g4{grid-template-columns:repeat(auto-fit,minmax(200px,1fr))}
.g2{grid-template-columns:repeat(auto-fit,minmax(340px,1fr))}.card{background:var(--surface);border:1px solid var(--grid);border-radius:12px;padding:16px 18px}
.tile .v{font-size:32px;font-weight:650;font-variant-numeric:tabular-nums}.tile .l{color:var(--ink2);font-size:13px}
.badge{display:inline-flex;align-items:center;gap:6px;font-size:12px;color:var(--ink2)}.dot{width:9px;height:9px;border-radius:50%}
.row{display:grid;grid-template-columns:150px 1fr 70px;align-items:center;gap:10px;padding:3px 0}
.row .k{color:var(--ink2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.row .n{color:var(--muted);font-size:12px;text-align:right;font-variant-numeric:tabular-nums}
.track{height:14px;position:relative}.fill{height:100%;border-radius:0 4px 4px 0;background:var(--bar)}.fill.weak{background:var(--bar-weak)}
.row:hover .fill{filter:brightness(1.1)}.row{cursor:default}.note{color:var(--muted);font-size:12px;margin-top:8px}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--grid);font-size:13px}
th{color:var(--ink2);font-weight:600;cursor:pointer;user-select:none;white-space:nowrap}tr:hover td{background:color-mix(in srgb,var(--bar) 6%,transparent)}
.section{margin-top:22px}.filters{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px}.filters button{border:1px solid var(--grid);background:var(--surface);color:var(--ink2);border-radius:999px;padding:4px 10px;cursor:pointer;font-size:12px}
.filters button.on{border-color:var(--bar);color:var(--ink)}ul{margin:0;padding-left:18px}
"""


def _e(x) -> str:
    return html.escape("" if x is None else str(x))


def _bars(rows: list[dict], key: str) -> str:
    if not rows:
        return '<div class="note">No scored posts yet.</div>'
    top = max((r["median"] for r in rows), default=1) or 1
    out = []
    for r in rows[:8]:
        w = 100 * r["median"] / max(100, top)
        cls = "fill" if r["enough"] else "fill weak"
        label = r["value"].replace("|", " × ")
        tip = f"{label}: median score {r['median']} from {r['n']} posts" + ("" if r["enough"] else " (not enough data yet)")
        out.append(f'<div class="row" title="{_e(tip)}"><div class="k">{_e(label)}</div>'
                   f'<div class="track"><div class="{cls}" style="width:{w:.1f}%"></div></div>'
                   f'<div class="n">{r["median"]:.0f} · n={r["n"]}</div></div>')
    return "".join(out)


def build(result: dict | None = None, out: Path | None = None) -> Path:
    cfg = config.load()
    r = result or analysis.weekly(write=False)
    inv = r["inventory"]
    lvl_color, lvl_label = LEVEL[inv["level"]]
    sent = sum(x["n"] for x in r["week_posts"] if x["status"] == "sent")
    failed = sum(x["n"] for x in r["week_posts"] if x["status"] == "error")
    sched = sum(x["n"] for x in r["week_posts"] if x["status"] == "scheduled")
    tiles = f"""
<div class="grid g4">
 <div class="card tile"><div class="l">Days of clips left</div><div class="v">{inv['days']}</div>
  <span class="badge"><span class="dot" style="background:var(--{lvl_color})"></span>{lvl_label}{' · record ~' + str(inv['clips_needed']) + ' clips' if inv['clips_needed'] else ''}</span></div>
 <div class="card tile"><div class="l">Active clips</div><div class="v">{inv['active_clips']}</div><span class="badge">{inv['remaining_uses']} uses left</span></div>
 <div class="card tile"><div class="l">Posts sent (7 days)</div><div class="v">{sent}</div><span class="badge">{sched} scheduled</span></div>
 <div class="card tile"><div class="l">Failed posts (7 days)</div><div class="v">{failed}</div>
  <span class="badge"><span class="dot" style="background:var(--{'good' if failed == 0 else 'critical'})"></span>{'None' if failed == 0 else 'Check Buffer'}</span></div>
</div>"""
    dims = "".join(f'<div class="card"><h2>{_e(DIM_TITLES[d])}</h2>{_bars(r["ranking"].get(d, []), d)}</div>'
                   for d in ["topic_format", "format", "hook_type", "caption_style", "music_mood", "length_bucket", "time_slot", "hashtag_set"])
    e = r["experiment"]
    exp_rows = "".join(f"<tr><td>{_e(a['arm'])}</td><td>{_e(a['median'])}</td><td>{a['n']}</td></tr>" for a in e.get("arms", []))
    exp = (f'<div class="card"><h2>Experiment: {_e(e.get("active"))}</h2>'
           f'<table><thead><tr><th>Arm</th><th>Median score</th><th>Posts</th></tr></thead><tbody>{exp_rows}</tbody></table>'
           f'<div class="note">{_e(e.get("recommendation", ""))}</div></div>')

    def post_rows(items):
        return "".join(f"<tr><td>{_e(s['variant_id'])}</td><td>{_e(s['topic'])} × {_e(s['format'])}</td><td>{_e(s['hook_type'])}</td>"
                       f"<td>{_e(s['caption_style'])}</td><td>{_e(s['music_mood'])}</td><td>{s['score']:.0f}</td>"
                       f"<td>{_e(', '.join(PLAT.get(k, k) + ' ' + str(int(v)) for k, v in s['views'].items()))}</td></tr>" for s in items) \
            or '<tr><td colspan="7" class="note">No scored posts this week.</td></tr>'
    head = "<tr><th>Variant</th><th>Type</th><th>Hook</th><th>Captions</th><th>Music</th><th>Score</th><th>Views</th></tr>"
    tops = (f'<div class="card"><h2>Top posts (7 days)</h2><table><thead>{head}</thead><tbody>{post_rows(r["top5"])}</tbody></table></div>'
            f'<div class="card"><h2>Bottom posts (7 days)</h2><table><thead>{head}</thead><tbody>{post_rows(r["bottom5"])}</tbody></table></div>')
    clip_rows = "".join(
        f'<tr data-status="{c["status"]}"><td>{_e(c["id"])}</td><td>{_e(c["topic"])}</td><td>{_e(c["format"] or "")}</td>'
        f'<td>{c["uses"]} / {c["cap"]}{" ★" if c["evergreen"] else ""}</td><td>{_e(c["last_used"] or "—")}</td>'
        f'<td>{_e(c["next_eligible"] or "—")}</td><td>{_e(STATUS_LABEL.get(c["status"], c["status"]))}</td><td>{c["variants"]}</td></tr>'
        for c in r["clips"])
    statuses = sorted({c["status"] for c in r["clips"]})
    filt = '<button class="on" data-f="all">All</button>' + "".join(
        f'<button data-f="{s}">{_e(STATUS_LABEL.get(s, s))}</button>' for s in statuses)
    library = (f'<div class="card section"><h2>Clip library</h2><div class="filters">{filt}</div>'
               f'<table id="clips"><thead><tr><th>Clip</th><th>Topic</th><th>Format</th><th>Uses</th><th>Last used</th>'
               f'<th>Next eligible</th><th>Status</th><th>Variants</th></tr></thead><tbody>{clip_rows}</tbody></table>'
               '<div class="note">★ evergreen (cap raised). Click a header to sort.</div></div>')
    shot = "".join(f"<li>{_e(s)}</li>" for s in r["shot_list"]) or "<li>Not enough data yet</li>"
    retired = "".join(f"<li>{_e(x['clip'])} ({_e(x.get('topic'))})</li>" for x in r["retired_this_week"]) or "<li>None</li>"
    side = (f'<div class="card"><h2>Record more like this</h2><ul>{shot}</ul></div>'
            f'<div class="card"><h2>Retired this week</h2><ul>{retired}</ul></div>')
    js = """
document.querySelectorAll('#clips th').forEach((th,i)=>th.onclick=()=>{const tb=th.closest('table').tBodies[0];
const rows=[...tb.rows];const dir=th.dataset.d=th.dataset.d==='1'?'-1':'1';
rows.sort((a,b)=>a.cells[i].innerText.localeCompare(b.cells[i].innerText,undefined,{numeric:true})*dir).forEach(r=>tb.appendChild(r));});
document.querySelectorAll('.filters button').forEach(b=>b.onclick=()=>{document.querySelectorAll('.filters button').forEach(x=>x.classList.remove('on'));
b.classList.add('on');document.querySelectorAll('#clips tbody tr').forEach(tr=>tr.style.display=(b.dataset.f==='all'||tr.dataset.status===b.dataset.f)?'':'none');});
"""
    doc = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>VDOs dashboard</title><style>{CSS}</style></head><body><main>
<h1>VDOs dashboard</h1><div class="sub">Updated {_e(r['generated_at'][:16].replace('T', ' '))} UTC · {r['n_scored_slots']} scored slots (last 30 days) · scores are 0–100, ranked within each platform</div>
{tiles}
<div class="section grid g2">{side}</div>
<h2 class="section">What's working</h2><div class="grid g2">{dims}</div>
<div class="note">Light bars = fewer than {cfg['analysis']['min_posts_per_value']} posts, not trusted yet. Hover a bar for details.</div>
<div class="section grid g2">{exp}</div>
<div class="section grid">{tops}</div>
{library}
</main><script>{js}</script></body></html>"""
    out = out or cfg.path("reports") / "dashboard.html"
    out.write_text(doc)
    (cfg.path("reports") / "dashboard.json").write_text(json.dumps(r, indent=1, default=str))
    return out
