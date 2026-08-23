#!/usr/bin/env python3
"""Standalone deterministic WTE /lanes/ renderer.

Compute helper for the private WTE branch. It consumes a frozen publication
contract and emits static nested index.html pages. It never evaluates personal
eligibility and it only displays route names plus official-source links.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.request
from pathlib import Path

SITE = "https://wheretoemigrate.io"
SCOPE = "SEO/content only; never personal eligibility or quiz matching"
NOINDEX = {"supporting_noindex", "structural_only_unsupported_market", "hold_not_publish"}
BUILD_DATE = "2026-08-23"

STYLE = r'''<style id="migration-content-css">
.mc{--fs:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;--fd:Georgia,"Times New Roman",serif;--fm:"SFMono-Regular",Consolas,monospace;--ink:#0c2e2b;--muted:#5a6470;--line:#dfe5e3;--paper:#f7faf9;--card:#fff;--deep:#0c2e2b;--mid:#1a5c50;--accent:#d96b36;margin:0;background:var(--paper);color:var(--ink);font-family:var(--fs);line-height:1.55}.mc *{box-sizing:border-box}.mc a{color:#146354}.mc .wrap{max-width:1120px;margin:auto;padding:0 24px}.mc .top{background:#fff;border-bottom:1px solid var(--line)}.mc .topin{height:66px;display:flex;align-items:center;justify-content:space-between;gap:24px}.mc .brand{font-weight:800;text-decoration:none;color:var(--deep);letter-spacing:-.03em}.mc .brand b{color:var(--accent)}.mc nav{display:flex;gap:18px;font-size:14px}.mc nav a{text-decoration:none;color:#34413f}.mc .hero{background:linear-gradient(145deg,#0c2e2b,#185449);color:#fff;padding:42px 0 64px}.mc .crumb{font-size:13px;margin-bottom:28px;color:#d3e0dd}.mc .crumb a{color:#fff}.mc .eyb{font:700 11px var(--fm);letter-spacing:.15em;text-transform:uppercase;color:#ffb37a;margin-bottom:10px}.mc h1{font:500 clamp(38px,6vw,66px)/1.04 var(--fd);letter-spacing:-.025em;margin:0;max-width:19ch}.mc .lead{max-width:72ch;font-size:18px;color:#dce9e6;margin:18px 0 0}.mc main{padding:44px 0 72px}.mc h2{font:500 31px/1.15 var(--fd);margin:38px 0 10px}.mc h3{font:600 19px/1.25 var(--fd);margin:0 0 8px}.mc p{max-width:78ch}.mc .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px;margin:20px 0 30px}.mc .card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px;box-shadow:0 2px 8px rgba(12,46,43,.04)}.mc a.card{display:block;text-decoration:none;color:var(--ink)}.mc a.card:hover{border-color:#a6c5bd;box-shadow:0 10px 26px rgba(12,46,43,.09)}.mc .tag{display:inline-block;font:700 10px var(--fm);letter-spacing:.09em;text-transform:uppercase;color:#975028;margin-bottom:8px}.mc .muted{color:var(--muted);font-size:14px}.mc .note{border:1px solid #cfe1dc;background:#edf5f3;border-radius:14px;padding:17px 19px;margin:24px 0;color:#364b47}.mc .guard{border-left:4px solid var(--accent);background:#fff7f2;padding:16px 18px;margin:25px 0}.mc .official{display:inline-flex;margin-top:12px;font-weight:700;font-size:13px}.mc .route-meta{font:600 11px var(--fm);color:#6c7774;margin-top:10px}.mc .chips{display:flex;flex-wrap:wrap;gap:9px;margin:20px 0}.mc .chip{border:1px solid var(--line);border-radius:999px;padding:8px 12px;background:#fff;text-decoration:none;font-size:13px;font-weight:650}.mc footer{background:#082824;color:#c9dad6;padding:38px 0;font-size:13px}.mc footer a{color:#fff}.mc .footlinks{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:12px}@media(max-width:650px){.mc .wrap{padding:0 18px}.mc nav{display:none}.mc .hero{padding:34px 0 48px}.mc main{padding-top:34px}}
</style>'''


def esc(x: object) -> str:
    return html.escape(str(x or ""), quote=True)


def slugify(text: str) -> str:
    s = text.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def served(path: str) -> str:
    return path.rstrip("/") + "/"


def read_contract(source: str) -> dict:
    if source.startswith("http://") or source.startswith("https://"):
        with urllib.request.urlopen(source, timeout=45) as r:
            raw = r.read().decode("utf-8")
    else:
        raw = Path(source).read_text(encoding="utf-8")
    return json.loads(raw)


def validate(doc: dict) -> list[dict]:
    if doc.get("scope") != SCOPE:
        raise SystemExit("ABORT: scope guardrail changed")
    if "frozen migration_content_rollout_final_v1" not in str(doc.get("selection_basis") or ""):
        raise SystemExit("ABORT: contract is not based on frozen rollout")
    pages = doc.get("pages") or []
    if len(pages) != 94:
        raise SystemExit(f"ABORT: expected 94 pages, got {len(pages)}")
    paths = [p.get("canonical_path") for p in pages]
    if len(set(paths)) != 94:
        raise SystemExit("ABORT: duplicate canonical_path")
    by_path = {p["canonical_path"]: p for p in pages}
    for p in pages:
        path = p.get("canonical_path") or ""
        if not path.startswith("/lanes/") or path.endswith("/"):
            raise SystemExit(f"ABORT: bad canonical path {path}")
        if p.get("rollout_priority") not in {"P0", "SUPPORT"}:
            raise SystemExit(f"ABORT: invalid priority {path}")
        if p.get("page_type") == "lane_pathway":
            if int(p.get("ready_public_routes") or 0) <= 0:
                raise SystemExit(f"ABORT: no route supply {path}")
            cards = p.get("route_cards") or []
            if not cards:
                raise SystemExit(f"ABORT: no frozen route cards {path}")
            for c in cards:
                if not str(c.get("official_url") or "").startswith("https://"):
                    raise SystemExit(f"ABORT: route without HTTPS official source {path}")
            if path.rsplit("/",1)[0] not in by_path:
                raise SystemExit(f"ABORT: orphan pathway {path}")
    return pages


def breadcrumbs(p: dict, by_path: dict[str,dict]) -> list[tuple[str,str]]:
    out = [("Home", "/")]
    origin_path = "/lanes/from-" + slugify(p["origin_name"])
    if p["page_type"] == "origin_hub":
        out.append((p["origin_name"], served(p["canonical_path"])))
    elif p["page_type"] == "lane_hub":
        if origin_path in by_path: out.append((f"From {p['origin_name']}", served(origin_path)))
        out.append((p["destination_name"], served(p["canonical_path"])))
    else:
        parent = p["canonical_path"].rsplit("/",1)[0]
        if origin_path in by_path: out.append((f"From {p['origin_name']}", served(origin_path)))
        out.append((p["destination_name"], served(parent)))
        out.append((str(p["pathway_key"]).replace("_"," ").title(), served(p["canonical_path"])))
    return out


def head(p: dict, crumbs: list[tuple[str,str]]) -> str:
    path = served(p["canonical_path"])
    url = SITE + path
    robots = "noindex,follow" if p.get("indexation_recommendation") in NOINDEX else "index,follow"
    ld_crumbs = []
    for i,(name,href) in enumerate(crumbs,1):
        full = SITE + href if href.startswith("/") else href
        ld_crumbs.append({"@type":"ListItem","position":i,"name":name,"item":full})
    ld = {"@context":"https://schema.org","@graph":[{"@type":"WebPage","name":p["title"],"url":url,"description":p["meta_description"],"dateModified":BUILD_DATE,"isPartOf":{"@type":"WebSite","name":"whereTOemigrate.io","url":SITE+"/"}},{"@type":"BreadcrumbList","itemListElement":ld_crumbs}]}
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(p['title'])}</title><meta name="description" content="{esc(p['meta_description'])}"><meta name="robots" content="{robots}"><link rel="canonical" href="{url}"><meta property="og:type" content="website"><meta property="og:site_name" content="whereTOemigrate.io"><meta property="og:title" content="{esc(p['title'])}"><meta property="og:description" content="{esc(p['meta_description'])}"><meta property="og:url" content="{url}"><script type="application/ld+json">{json.dumps(ld,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')}</script>{STYLE}</head><body class="mc">'''


def chrome_top() -> str:
    return '''<header class="top"><div class="wrap topin"><a class="brand" href="/">where <b>TO</b> emigrate.io</a><nav><a href="/countries/">Countries</a><a href="/pathways/">Visas</a><a href="/blog/">Blog</a><a href="/reports/">Reports</a></nav></div></header>'''


def chrome_bottom() -> str:
    return '''<footer><div class="wrap"><div class="footlinks"><a href="/methodology/">Methodology</a><a href="/data-sources/">Data sources</a><a href="/editorial-standards/">Editorial standards</a><a href="/limitations/">Limitations</a></div><div>Independent migration research · informational only · not legal advice. Immigration rules change; confirm current requirements with the official authority.</div></div></footer></body></html>'''


def crumb_html(crumbs: list[tuple[str,str]]) -> str:
    bits=[]
    for i,(name,href) in enumerate(crumbs):
        if i == len(crumbs)-1: bits.append(esc(name))
        else: bits.append(f'<a href="{esc(href)}">{esc(name)}</a>')
    return " <span aria-hidden=\"true\">›</span> ".join(bits)


def render_origin(p: dict, pages: list[dict]) -> str:
    lanes = [x for x in pages if x.get("page_type")=="lane_hub" and x.get("origin_iso3")==p.get("origin_iso3")]
    lanes.sort(key=lambda x:(x.get("rollout_priority")!="P0", x.get("destination_name") or ""))
    cards=''.join(f'<a class="card" href="{served(x["canonical_path"])}"><span class="tag">Destination guide</span><h3>{esc(x["destination_name"])}</h3><p class="muted">Explore this migration corridor and the pathway pages WTE has cleared for publication.</p></a>' for x in lanes)
    return f'''<section class="note"><strong>What this page is:</strong> an editorial navigation layer selected from WTE's frozen migration and search-demand model. It is not a personal eligibility recommendation.</section><h2>Destinations in this rollout</h2><p>Use a corridor guide to see the pathway categories and official-source route inventory currently cleared for public display.</p><div class="grid">{cards}</div>'''


def render_lane(p: dict, pages: list[dict]) -> str:
    parent = p["canonical_path"]
    kids=[x for x in pages if x.get("page_type")=="lane_pathway" and x["canonical_path"].rsplit("/",1)[0]==parent]
    kids.sort(key=lambda x:x.get("pathway_key") or "")
    if kids:
        cards=''.join(f'<a class="card" href="{served(x["canonical_path"])}"><span class="tag">{esc(str(x["pathway_key"]).replace("_"," "))}</span><h3>{esc(x["h1"])}</h3><p class="muted">See published destination routes with links to the official authorities.</p></a>' for x in kids)
        body=f'<h2>Pathway guides</h2><p>These pages exist only where WTE currently has a publication-ready destination route inventory for the category.</p><div class="grid">{cards}</div>'
    else:
        dest_slug=slugify(p["destination_name"])
        body=f'<h2>Destination route inventory</h2><p>This corridor is cleared as a destination guide, but no pathway-specific child is in this P0 rollout. Browse the destination&apos;s published immigration routes instead.</p><div class="chips"><a class="chip" href="/countries/{dest_slug}/">Immigration routes for {esc(p["destination_name"])}</a></div>'
    return f'''<section class="note"><strong>Corridor context:</strong> WTE selected this origin → destination pair for editorial coverage. That selection is a content-prioritisation decision, not a claim that people from {esc(p['origin_name'])} qualify for a visa in {esc(p['destination_name'])}.</section>{body}'''


def render_pathway(p: dict) -> str:
    cards=[]
    for r in p.get("route_cards") or []:
        date = r.get("verified_at")
        meta = f'WTE source check: {esc(date)}' if date else 'Official source recorded by WTE'
        cards.append(f'''<article class="card"><span class="tag">Official route</span><h3>{esc(r.get('visa'))}</h3><p class="muted">Route listed in WTE&apos;s publication-ready destination inventory. Check the authority page for current eligibility, conditions and application rules.</p><div class="route-meta">{meta}</div><a class="official" href="{esc(r.get('official_url'))}" rel="noopener noreferrer">Open official source →</a></article>''')
    return f'''<div class="guard"><strong>Nationality is not inferred here.</strong> A route existing in {esc(p['destination_name'])} does not mean an applicant from {esc(p['origin_name'])} qualifies for it. This page is an information index, not an eligibility decision.</div><h2>Published {esc(str(p['pathway_key']).replace('_',' '))} routes in {esc(p['destination_name'])}</h2><p>The cards below deliberately show route identity and the official source rather than restating changing legal thresholds. Confirm the authority&apos;s current rules before acting.</p><div class="grid">{''.join(cards)}</div><section class="note"><strong>Data discipline:</strong> route cards are frozen from WTE records marked ready to publish and backed by an official HTTPS source. No route card on this page asserts that origin nationality satisfies the route.</section>'''


def render(p: dict, pages: list[dict], by_path: dict[str,dict]) -> str:
    crumbs=breadcrumbs(p,by_path)
    kind={"origin_hub":"Origin intelligence","lane_hub":"Migration corridor","lane_pathway":"Pathway inventory"}.get(p["page_type"],"Migration intelligence")
    lead = p["meta_description"]
    if p["page_type"]=="origin_hub": content=render_origin(p,pages)
    elif p["page_type"]=="lane_hub": content=render_lane(p,pages)
    else: content=render_pathway(p)
    return head(p,crumbs)+chrome_top()+f'''<section class="hero"><div class="wrap"><div class="crumb">{crumb_html(crumbs)}</div><div class="eyb">{esc(kind)}</div><h1>{esc(p['h1'])}</h1><p class="lead">{esc(lead)}</p></div></section><main><div class="wrap">{content}<section class="note"><strong>Accuracy notice:</strong> immigration requirements can change without notice. WTE is informational only and does not provide legal advice. Always verify the current rule with the linked official source.</section></div></main>'''+chrome_bottom()


def controller_contract(pages: list[dict]) -> dict:
    rows=[]
    for p in pages:
        noindex=p.get("indexation_recommendation") in NOINDEX
        rows.append({"url":p["canonical_path"],"page_family":"lanes","survival_decision":"KEEP","indexability":"NOINDEX" if noindex else "INDEX","noindex_html":noindex,"canonical_html":SITE+served(p["canonical_path"]),"rollout_state":"DECIDED","source_of_truth":"MIGRATION_CONTENT_ROLLOUT_P0"})
    return {"version":"migration_lanes_controller_p0_v1","rows":rows}


def write_outputs(doc: dict, out_dir: Path) -> list[tuple[str,str]]:
    pages=validate(doc); by_path={p["canonical_path"]:p for p in pages}
    outputs=[]
    for p in pages:
        rel=p["canonical_path"].removeprefix("/lanes/").strip("/")
        path=out_dir.joinpath(*rel.split("/"),"index.html")
        text=render(p,pages,by_path)
        path.parent.mkdir(parents=True,exist_ok=True); path.write_text(text,encoding="utf-8")
        outputs.append((f'deploy/lanes/{rel}/index.html',text))
    return outputs


def emit_tree(path: Path, doc: dict, outputs: list[tuple[str,str]]) -> None:
    ctrl=controller_contract(doc["pages"])
    entries=list(outputs)
    entries.append(("data/runtime/migration_content_contract.json",json.dumps(doc,ensure_ascii=False,indent=2)+"\n"))
    entries.append(("data/runtime/migration_page_controller_contract.json",json.dumps(ctrl,ensure_ascii=False,indent=2)+"\n"))
    entries.append(("scripts/pages/build_migration_content.py",Path(__file__).read_text(encoding="utf-8")))
    with path.open("w",encoding="utf-8") as f:
        for p,c in entries:
            f.write(json.dumps({"path":p,"mode":"100644","type":"blob","content":c},ensure_ascii=False,separators=(",",":"))+"\n")
    print(f"tree entries: {len(entries)}")


def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("--contract",default="data/runtime/migration_content_contract.json"); ap.add_argument("--out-dir",default="deploy/lanes"); ap.add_argument("--emit-tree"); ap.add_argument("--p0",action="store_true"); args=ap.parse_args()
    doc=read_contract(args.contract); outputs=write_outputs(doc,Path(args.out_dir))
    if len(outputs)!=94: raise SystemExit(f"ABORT: rendered {len(outputs)} pages")
    if args.emit_tree: emit_tree(Path(args.emit_tree),doc,outputs)
    print(f"PASS: rendered {len(outputs)} frozen /lanes/ pages")
    return 0
if __name__=="__main__": raise SystemExit(main())
