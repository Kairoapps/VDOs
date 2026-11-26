"""Self-contained HTML dashboard built from the latest analysis result (no external assets)."""
from __future__ import annotations

import html
import json
from pathlib import Path

from . import analysis, config

PLAT = {"instagram": "IG", "tiktok": "TikTok", "youtube": "YT", "facebook": "FB"}
STATUS_LABEL = {"available": "Available", "cooling": "Cooling down", "needs_edit": "Needs edit", "exhausted": "Used up",
                "retired": "Retired", "unusable": "Unusable"}
LEVEL = {"healthy": ("good", "Healthy"), "heads_up": ("warning", "Heads-up"), "urgent": ("critical", "Urgent"),
         "empty": ("critical", "Empty")}
DIM_TITLES = {"topic_format": "Video type", "format": "Format", "hook_type": "Opening",
              "caption_style": "Caption style", "title_style": "Title style", "caption_text": "On-screen title", "music_mood": "Music mood",
              "track": "Track", "length_bucket": "Length", "time_slot": "Posting time", "hashtag_set": "Hashtag set (test)",
              "angle": "Content angle", "title_emoji": "Emojis in title", "cta_mode": "CTA timing", "cta_text": "CTA wording",
              "cta_color": "CTA colour", "sound": "Alarm sound", "sound_type": "Sound type", "speed_level": "Speed level",
              "speed": "Speed", "hashtag_count": "Hashtag count", "post_caption_style": "Post caption style",
              "post_emoji": "Emojis in post caption"}
# Every test the system runs, grouped for the "All A/B tests" grid.
GROUPS = [("Video", ["topic_format", "angle", "length_bucket", "speed_level", "speed"]),
          ("Title", ["title_style", "title_emoji", "caption_text"]),
          ("Sound", ["sound_type", "sound"]),
          ("Call to action", ["cta_mode", "cta_color", "cta_text"]),
          ("Posting", ["time_slot", "hashtag_set", "post_caption_style", "post_emoji"])]
LEADERS = ["topic_format", "angle", "title_style", "title_emoji", "sound_type", "cta_mode", "cta_color", "speed_level",
           "length_bucket", "time_slot", "hashtag_set", "post_caption_style"]

CSS = """
:root{--surface:#ffffff;--page:#f6f6f3;--ink:#121212;--ink2:#55544f;--muted:#8a8984;--grid:#e7e6e1;--bar:#2a78d6;--bar-weak:#c4dbf6;
--good:#0ca30c;--warning:#e09b00;--critical:#d03b3b;--accent:#2BFF4F;--chip:#efeee9}
@media (prefers-color-scheme:dark){:root{--surface:#191918;--page:#0e0e0d;--ink:#f0efec;--ink2:#c3c2b7;--muted:#8f8e86;--grid:#2c2c2a;
--bar:#4a93ea;--bar-weak:#1d4f88;--chip:#262624}}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--page);color:var(--ink);font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif}
main{max-width:1180px;margin:0 auto;padding:24px 16px 64px}
header{display:flex;flex-wrap:wrap;align-items:baseline;justify-content:space-between;gap:8px;margin-bottom:6px}
h1{font-size:24px;margin:0;letter-spacing:-.01em}h2{font-size:18px;margin:34px 0 12px;letter-spacing:-.01em}h3{font-size:14px;margin:0 0 10px}
.sub{color:var(--ink2);font-size:13px}
nav{position:sticky;top:0;z-index:5;background:color-mix(in srgb,var(--page) 92%,transparent);backdrop-filter:blur(6px);
 display:flex;gap:6px;overflow-x:auto;padding:10px 0;margin:8px 0 4px;border-bottom:1px solid var(--grid)}
nav a{white-space:nowrap;text-decoration:none;color:var(--ink2);font-size:13px;padding:5px 11px;border-radius:999px;background:var(--chip)}
nav a:hover{color:var(--ink)}
.grid{display:grid;gap:12px}.g4{grid-template-columns:repeat(auto-fit,minmax(190px,1fr))}
.g3{grid-template-columns:repeat(auto-fit,minmax(300px,1fr))}.g2{grid-template-columns:repeat(auto-fit,minmax(340px,1fr))}
.card{background:var(--surface);border:1px solid var(--grid);border-radius:14px;padding:16px 18px;min-width:0}
.tile .v{font-size:30px;font-weight:680;font-variant-numeric:tabular-nums;margin:2px 0}.tile .l{color:var(--ink2);font-size:13px}
.badge{display:inline-flex;align-items:center;gap:6px;font-size:12px;color:var(--ink2)}.dot{width:9px;height:9px;border-radius:50%;flex:none}
.row{display:grid;grid-template-columns:minmax(90px,40%) 1fr 74px;align-items:center;gap:10px;padding:4px 0}
.row .k{color:var(--ink2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.row .n{color:var(--muted);font-size:12px;text-align:right;font-variant-numeric:tabular-nums}
.track{height:14px;background:color-mix(in srgb,var(--grid) 55%,transparent);border-radius:4px}
.fill{height:100%;border-radius:4px;background:var(--bar)}.fill.weak{background:var(--bar-weak)}
.note{color:var(--muted);font-size:12px;margin-top:8px}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--grid);font-size:13px;vertical-align:top}
th{color:var(--ink2);font-weight:600;cursor:pointer;user-select:none;white-space:nowrap}
tr:hover td{background:color-mix(in srgb,var(--bar) 6%,transparent)}.scroll{overflow-x:auto}
.leaders{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px}
.leader{background:var(--surface);border:1px solid var(--grid);border-radius:12px;padding:12px 14px}
.leader .d{color:var(--muted);font-size:12px}.leader .w{font-weight:650;font-size:15px;margin:2px 0;overflow-wrap:anywhere}
.leader .s{font-size:12px;color:var(--ink2)}
.tag{display:inline-block;font-size:11px;padding:1px 7px;border-radius:999px;background:var(--chip);color:var(--ink2);margin-left:4px}
.tag.ok{background:color-mix(in srgb,var(--good) 18%,transparent);color:var(--good)}
.video{display:flex;flex-direction:column;gap:6px}.video .t{font-weight:600;overflow-wrap:anywhere}
.video .meta{display:flex;flex-wrap:wrap;gap:4px}.rank{font-size:12px;color:var(--muted)}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-top:4px}.stats div{background:var(--chip);border-radius:8px;padding:6px 8px}
.stats b{display:block;font-size:15px;font-variant-numeric:tabular-nums}.stats span{font-size:11px;color:var(--muted)}
.links a{font-size:12px;color:var(--bar);margin-right:8px}
.swatch{display:inline-block;width:12px;height:12px;border-radius:3px;border:1px solid var(--grid);vertical-align:-1px;margin-right:6px}
.filters{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px}
.filters button{border:1px solid var(--grid);background:var(--surface);color:var(--ink2);border-radius:999px;padding:4px 10px;cursor:pointer;font-size:12px}
.filters button.on{border-color:var(--bar);color:var(--ink)}ul{margin:0;padding-left:18px}
.how{color:var(--ink2);font-size:13px;margin:-4px 0 12px}
"""


def _e(x) -> str:
    return html.escape("" if x is None else str(x))


def _label(v) -> str:
    return str(v).replace("|", " × ")


def _bars(rows: list[dict], limit: int = 8, swatch: bool = False) -> str:
    if not rows:
        return '<div class="note">No scored posts yet.</div>'
    out = []
    for r in rows[:limit]:
        cls = "fill" if r["enough"] else "fill weak"
        label = _label(r["value"])
        tip = f"{label}: median score {r['median']} from {r['n']} posts" + ("" if r["enough"] else " (not enough data yet)")
        sw = f'<span class="swatch" style="background:{_e(r["value"])}"></span>' if swatch and str(r["value"]).startswith("#") else ""
        out.append(f'<div class="row" title="{_e(tip)}"><div class="k">{sw}{_e(label)}</div>'
                   f'<div class="track"><div class="{cls}" style="width:{max(2, min(100, r["median"])):.1f}%"></div></div>'
                   f'<div class="n">{r["median"]:.0f} · n={r["n"]}</div></div>')
    return "".join(out)


def _cover(inv: dict) -> str:
    from datetime import date
    f = lambda x: date.fromisoformat(x).strftime("%a %b %-d")
    if not inv.get("covered_through"):
        return "Nothing can post today"
    out = f"Covered through {f(inv['covered_through'])}"
    if inv.get("first_gap"):
        out += f" · first gap {f(inv['first_gap'])}"
    return _e(out)


def _num(x) -> str:
    x = float(x or 0)
    return f"{x / 1000:.1f}k" if x >= 10000 else f"{x:,.0f}"


def _video(i: int, s: dict, cfg) -> str:
    links = "".join(f'<a href="{_e(u)}" target="_blank" rel="noopener">{_e(PLAT.get(p, p))} ↗</a>'
                    for p, u in (s.get("urls") or {}).items())
    per = " · ".join(f"{PLAT.get(k, k)} {_num(v)}" for k, v in s["views"].items())
    tags = "".join(f'<span class="tag">{_e(t)}</span>' for t in
                   [_label(s["topic_format"]), s.get("angle"), s.get("title_style"), s.get("sound_type"), s.get("speed"),
                    "CTA " + str(s.get("cta_mode")), s.get("hashtag_set"), s.get("time_slot")] if t and t != "none")
    watch = f'{s["watch"]:.0f}%' if s.get("watch") is not None else "—"
    return (f'<div class="card video"><div class="rank">#{i} · score {s["score"]:.0f}/100 · {_e(s["scheduled_at"][:10])}</div>'
            f'<div class="t">{_e(s.get("caption_text") if s.get("caption_text") not in (None, "none") else s["variant_id"])}</div>'
            f'<div class="meta">{tags}</div>'
            f'<div class="stats"><div><b>{_num(s.get("total_views"))}</b><span>views</span></div>'
            f'<div><b>{watch}</b><span>avg watched</span></div><div><b>{_num(s.get("comments"))}</b><span>comments</span></div>'
            f'<div><b>{_num(s.get("shares"))}</b><span>shares+saves</span></div></div>'
            f'<div class="note" style="margin:0">{_e(per)} · {_e(s["variant_id"])}</div><div class="links">{links}</div></div>')


def build(result: dict | None = None, out: Path | None = None) -> Path:
    cfg = config.load()
    r = result or analysis.weekly(write=False)
    inv = r["inventory"]
    min_n = cfg["analysis"]["min_posts_per_value"]
    lvl_color, lvl_label = LEVEL[inv["level"]]
    sent = sum(x["n"] for x in r["week_posts"] if x["status"] == "sent")
    failed = sum(x["n"] for x in r["week_posts"] if x["status"] == "error")
    sched = sum(x["n"] for x in r["week_posts"] if x["status"] == "scheduled")
    wt = r.get("week_totals") or {}
    cta_c = [x for x in r.get("cta_comments", []) if x["dim"] == "cta_mode"]
    cta_on = [x for x in cta_c if x["value"] != "none"]
    cta_off = next((x for x in cta_c if x["value"] == "none"), None)

    tiles = f"""
<div class="grid g4">
 <div class="card tile"><div class="l">Views (posts from the last 7 days)</div><div class="v">{_num(wt.get('views'))}</div>
  <span class="badge">{sent} posts sent · {sched} scheduled</span></div>
 <div class="card tile"><div class="l">Comments (last 7 days)</div><div class="v">{_num(wt.get('comments'))}</div>
  <span class="badge">CTA posts: {sum(x['comments'] for x in cta_on)} comments on {sum(x['posts'] for x in cta_on)} posts</span></div>
 <div class="card tile"><div class="l">Days of clips left</div><div class="v">{inv['days']}</div>
  <span class="badge"><span class="dot" style="background:var(--{lvl_color})"></span>{lvl_label} · {_cover(inv)}</span></div>
 <div class="card tile"><div class="l">Active clips</div><div class="v">{inv['active_clips']}</div>
  <span class="badge">{inv['remaining_uses']} uses left{' · record ~' + str(inv['clips_needed']) if inv['clips_needed'] else ''}</span></div>
 <div class="card tile"><div class="l">Failed posts (7 days)</div><div class="v">{failed}</div>
  <span class="badge"><span class="dot" style="background:var(--{'good' if failed == 0 else 'critical'})"></span>{'None' if failed == 0 else 'Check Buffer'}</span></div>
</div>"""

    # Leaders: current best value of every test.
    leaders = []
    for d in LEADERS:
        rows = r["ranking"].get(d, [])
        if not rows:
            continue
        top = rows[0]
        if d == "cta_color" and top["value"] == "none":
            top = next((x for x in rows if x["value"] != "none"), None)
            if not top:
                continue
        ok = '<span class="tag ok">trusted</span>' if top["enough"] else f'<span class="tag">early · n={top["n"]}</span>'
        sw = f'<span class="swatch" style="background:{_e(top["value"])}"></span>' if str(top["value"]).startswith("#") else ""
        leaders.append(f'<div class="leader"><div class="d">{_e(DIM_TITLES.get(d, d))}</div>'
                       f'<div class="w">{sw}{_e(_label(top["value"]))}</div><div class="s">score {top["median"]:.0f} {ok}</div></div>')
    leaders_html = f'<div class="leaders">{"".join(leaders) or "<div class=note>No scored posts yet.</div>"}</div>'

    week = r.get("top_week") or r.get("top5") or []
    videos = "".join(_video(i + 1, s, cfg) for i, s in enumerate(week)) or '<div class="card note">No scored posts this week yet (posts are scored at ~3–7 days old).</div>'

    # Hashtags
    hs = r.get("hashtags") or {}
    def tag_rows(rows):
        return "".join(f'<tr><td>{_e(x["value"])}</td><td>{x["median"]:.0f}</td><td>{_num(x["avg_views"])}</td><td>{x["n"]}</td></tr>'
                       for x in rows[:15]) or '<tr><td colspan="4" class="note">Not enough posts yet.</td></tr>'
    th = "<thead><tr><th>Hashtag</th><th>Score</th><th>Avg views</th><th>Posts</th></tr></thead>"
    arms = cfg["experiments"]["hashtag_set"]["arms"]
    set_rows = r["ranking"].get("hashtag_set", [])
    set_map = {x["value"]: x for x in set_rows}
    test_rows = "".join(
        f'<tr><td><b>{_e(k)}</b><br><span class="note">{_e(" ".join(v))}</span></td>'
        f'<td>{_e(set_map[k]["median"]) if k in set_map else "—"}</td><td>{set_map[k]["n"] if k in set_map else 0}</td></tr>'
        for k, v in sorted(arms.items(), key=lambda kv: -(set_map.get(kv[0], {}).get("median") or -1)))
    hashtags = f"""
<div class="grid g3">
 <div class="card"><h3>Hashtag sets being tested now</h3><div class="scroll"><table><thead><tr><th>Set</th><th>Score</th><th>Posts</th></tr></thead>
  <tbody>{test_rows}</tbody></table></div><div class="note">Each slot gets one set on every platform, rotated evenly. A set needs {min_n}+ posts to be trusted.</div></div>
 <div class="card"><h3>Best single hashtags (last 40 days)</h3><div class="scroll"><table>{th}<tbody>{tag_rows(hs.get('tags', []))}</tbody></table></div>
  <div class="note">All {hs.get('posts', 0)} Buffer posts at least 2 days old, including ones from before the tests. Score = views rank within the platform (0–100).</div></div>
 <div class="card"><h3>Best hashtag combinations (last 40 days)</h3><div class="scroll"><table><thead><tr><th>Combination</th><th>Score</th><th>Avg views</th><th>Posts</th></tr></thead>
  <tbody>{tag_rows(hs.get('sets', []))}</tbody></table></div></div>
</div>"""

    # CTA
    def cta_table(dim, title, swatch=False):
        rows = [x for x in r.get("cta_comments", []) if x["dim"] == dim]
        body = "".join(
            f'<tr><td>{"<span class=swatch style=background:" + _e(x["value"]) + "></span>" if swatch and str(x["value"]).startswith("#") else ""}{_e("no CTA" if x["value"] == "none" else x["value"])}</td>'
            f'<td>{x["posts"]}</td><td>{x["comments"]}</td><td>{x["per_post"]}</td><td>{x["per_1k_views"]}</td></tr>' for x in rows) \
            or '<tr><td colspan="5" class="note">No posts yet.</td></tr>'
        return (f'<div class="card"><h3>{title}</h3><div class="scroll"><table><thead><tr><th>Option</th><th>Posts</th><th>Comments</th>'
                f'<th>/post</th><th>/1k views</th></tr></thead><tbody>{body}</tbody></table></div></div>')
    cta = f"""
<div class="how">Comments the "comment UNSNOOZE" line brings in, per option (posts from the last 30 days, latest numbers).
{('No-CTA posts average ' + str(cta_off['per_post']) + ' comments each.') if cta_off else ''}</div>
<div class="grid g3">{cta_table('cta_mode', 'CTA timing (none / whole video / end)')}{cta_table('cta_color', 'CTA colour', True)}{cta_table('cta_text', 'CTA wording')}</div>"""

    # All tests
    groups = ""
    for gname, dims in GROUPS:
        cards = "".join(f'<div class="card"><h3>{_e(DIM_TITLES.get(d, d))}</h3>{_bars(r["ranking"].get(d, []), swatch=(d == "cta_color"))}</div>'
                        for d in dims if d in r["ranking"])
        groups += f'<h3 style="margin:18px 0 8px;color:var(--ink2)">{_e(gname)}</h3><div class="grid g3">{cards}</div>'

    exps = r["experiment"] if isinstance(r["experiment"], list) else [r["experiment"]]
    exp = ""
    for e in exps or []:
        if e.get("active") == "hashtag_set":
            continue
        exp_rows = "".join(f"<tr><td>{_e(a['arm'])}</td><td>{_e(a['median'] if a['median'] is not None else '—')}</td><td>{a['n']}</td></tr>"
                           for a in sorted(e.get("arms", []), key=lambda a: -(a["median"] or -1)))
        exp += (f'<div class="card"><h3>Posting times being tested</h3><div class="scroll">'
                f'<table><thead><tr><th>Time (ET)</th><th>Score</th><th>Posts</th></tr></thead><tbody>{exp_rows}</tbody></table></div>'
                f'<div class="note">{_e(e.get("recommendation", ""))}</div></div>')

    # Slideshows
    sl = r.get("slideshows") or {}
    def _cmp(d):
        return f'{_num(d["median_views"])} <span class="note">({d["eng_per_1k"]}/1k · n={d["posts"]})</span>' if d else '<span class="note">—</span>'
    vs_rows = "".join(f'<tr><td>{_e(p)}</td><td>{_cmp(x["slideshow"])}</td><td>{_cmp(x["video"])}</td><td>{_e(x["verdict"])}</td></tr>'
                      for p, x in (sl.get("vs_video_30d") or {}).items())
    sl_inv = sl.get("inventory") or {}
    sl_cards = "".join(f'<div class="card"><h3>{_e(t)}</h3>{_bars((sl.get("ranking") or {}).get(d, []))}</div>'
                       for d, t in (("slideshow", "Best slideshows"), ("kind", "One challenge vs several"),
                                    ("time_slot", "Slideshow posting time"), ("post_caption_style", "Slideshow caption style")))
    slideshows = f"""
<div class="grid g3">
 <div class="card"><h3>Slideshow vs video (30 days)</h3><div class="scroll"><table><thead><tr><th>Platform</th><th>Slideshows (median views)</th>
  <th>Videos (median views)</th><th>Verdict</th></tr></thead><tbody>{vs_rows or '<tr><td colspan="4" class="note">No slideshow posts yet.</td></tr>'}</tbody></table></div>
  <div class="note">Posts at least 3 days old. /1k = likes + comments + shares + saves per 1,000 views.</div></div>
 <div class="card tile"><div class="l">Fresh slideshows left</div><div class="v">{sl_inv.get('never_posted', 0)}</div>
  <span class="badge">{sl_inv.get('slideshows', 0)} total · {sl_inv.get('uses_left', 0)} uses left{' · build more' if sl.get('build_more') else ''}</span></div>
</div><div class="grid g3">{sl_cards}</div>"""

    clip_rows = "".join(
        f'<tr data-status="{c["status"]}"><td>{_e(c["id"])}</td><td>{_e(c["topic"])}</td><td>{_e(c.get("angle") or "")}</td>'
        f'<td>{c["uses"]} / {c["cap"]}{" ★" if c["evergreen"] else ""}</td><td>{_e(c["last_used"] or "—")}</td>'
        f'<td>{_e(c["next_eligible"] or "—")}</td><td>{_e(STATUS_LABEL.get(c["status"], c["status"]))}</td><td>{c["variants"]}</td></tr>'
        for c in r["clips"])
    statuses = sorted({c["status"] for c in r["clips"]})
    filt = '<button class="on" data-f="all">All</button>' + "".join(
        f'<button data-f="{s}">{_e(STATUS_LABEL.get(s, s))}</button>' for s in statuses)
    library = (f'<div class="card"><div class="filters">{filt}</div><div class="scroll">'
               f'<table id="clips"><thead><tr><th>Clip</th><th>Challenge</th><th>Angle</th><th>Uses</th><th>Last used</th>'
               f'<th>Next eligible</th><th>Status</th><th>Versions</th></tr></thead><tbody>{clip_rows}</tbody></table></div>'
               '<div class="note">★ evergreen (more uses allowed). Click a header to sort.</div></div>')
    shot = "".join(f"<li>{_e(s)}</li>" for s in r["shot_list"]) or "<li>Not enough data yet</li>"
    retired = "".join(f"<li>{_e(x['clip'])} ({_e(x.get('topic'))})</li>" for x in r["retired_this_week"]) or "<li>None</li>"
    sw = r.get("score_weights") or {}
    how = ("Score = rank within each platform (0–100): " + ", ".join(f"{k.replace('_', ' + ')} {int(v * 100)}%" for k, v in sw.items())
           + ". Watch time comes from Instagram and TikTok only (YouTube doesn't report it through Buffer).") if sw else ""
    js = """
document.querySelectorAll('table').forEach(t=>t.querySelectorAll('th').forEach((th,i)=>th.onclick=()=>{const tb=t.tBodies[0];
const rows=[...tb.rows];const dir=th.dataset.d=th.dataset.d==='1'?'-1':'1';
rows.sort((a,b)=>a.cells[i].innerText.localeCompare(b.cells[i].innerText,undefined,{numeric:true})*dir).forEach(r=>tb.appendChild(r));}));
document.querySelectorAll('.filters button').forEach(b=>b.onclick=()=>{document.querySelectorAll('.filters button').forEach(x=>x.classList.remove('on'));
b.classList.add('on');document.querySelectorAll('#clips tbody tr').forEach(tr=>tr.style.display=(b.dataset.f==='all'||tr.dataset.status===b.dataset.f)?'':'none');});
"""
    doc = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>VDOs dashboard</title><style>{CSS}</style></head><body><main>
<header><h1>Unsnooze videos</h1><div class="sub">Updated {_e(r['generated_at'][:16].replace('T', ' '))} UTC · {r['n_scored_slots']} scored posts (30 days)</div></header>
<nav><a href="#top">Overview</a><a href="#videos">Top videos</a><a href="#leaders">What's winning</a><a href="#slideshows">Slideshows</a><a href="#hashtags">Hashtags</a>
<a href="#cta">CTA &amp; comments</a><a href="#tests">All A/B tests</a><a href="#clips">Clips</a></nav>
<section id="top">{tiles}
<div class="grid g2" style="margin-top:12px"><div class="card"><h3>Record more like this</h3><ul>{shot}</ul></div>
<div class="card"><h3>Retired this week</h3><ul>{retired}</ul></div></div></section>
<h2 id="videos">Best videos this week</h2><div class="grid g3">{videos}</div>
<h2 id="leaders">What's winning right now</h2><div class="how">The best option in every test. "Early" = fewer than {min_n} posts, so it can still change.</div>{leaders_html}
<h2 id="slideshows">Slideshows</h2>{slideshows}
<h2 id="hashtags">Hashtags</h2>{hashtags}
<h2 id="cta">CTA &amp; comments</h2>{cta}
<h2 id="tests">All A/B tests</h2><div class="how">{_e(how)} Light bars = fewer than {min_n} posts. Each version picks every option at random,
weighted toward what's winning (70%) while still testing the rest (30%).</div>{groups}
<div class="grid g2" style="margin-top:12px">{exp}</div>
<h2 id="clips">Clip library</h2>{library}
</main><script>{js}</script></body></html>"""
    out = out or cfg.path("reports") / "dashboard.html"
    out.write_text(doc)
    (cfg.path("reports") / "dashboard.json").write_text(json.dumps(r, indent=1, default=str))
    return out
