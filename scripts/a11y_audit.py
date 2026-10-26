"""Automated accessibility audit of a running Pitchside page (not a substitute for a screen reader).

    pip install playwright && playwright install chromium     (once)
    .venv\\Scripts\\python scripts\\a11y_audit.py [url]       default: http://127.0.0.1:8000/

Checks, in several page states: document language and title, one h1 and heading order, landmarks,
names for every control, duplicate ids, dangling aria references, table headers, tab order with
visible focus outlines, minimum target size (24px), colour contrast (WCAG AA) in the normal and
high-contrast themes, and reflow with no sideways page scroll at 320px with larger text.
Against a deployed app with a model configured, a few steps wait for real model calls.
"""

import json
import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"

JS_CONTRAST = r"""
() => {
  const parse = c => { const m = c.match(/rgba?\(([^)]+)\)/); if(!m) return null; const p = m[1].split(',').map(Number); return {r:p[0],g:p[1],b:p[2],a:p.length>3?p[3]:1}; };
  const lum = ({r,g,b}) => { const f = v => { v/=255; return v<=0.03928? v/12.92 : Math.pow((v+0.055)/1.055,2.4)}; return 0.2126*f(r)+0.7152*f(g)+0.0722*f(b); };
  const bgOf = el => { let e = el; while (e) { const c = parse(getComputedStyle(e).backgroundColor); if (c && c.a > 0.9) return c; e = e.parentElement; } return {r:15,g:23,b:32,a:1}; };
  const out = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const seen = new Set();
  while (walker.nextNode()) {
    const n = walker.currentNode; if (!n.textContent.trim()) continue;
    const el = n.parentElement; if (!el || seen.has(el)) continue; seen.add(el);
    const cs = getComputedStyle(el); const r = el.getBoundingClientRect();
    if (cs.visibility === 'hidden' || cs.display === 'none' || r.width === 0 || r.height === 0) continue;
    if (el.closest("[hidden]") || el.closest(".sr-only") || el.classList.contains("skip")) continue;
    const fg = parse(cs.color), bg = bgOf(el); if (!fg) continue;
    const l1 = lum(fg), l2 = lum(bg), ratio = (Math.max(l1,l2)+0.05)/(Math.min(l1,l2)+0.05);
    const px = parseFloat(cs.fontSize), bold = parseInt(cs.fontWeight) >= 700;
    const need = (px >= 24 || (px >= 18.66 && bold)) ? 3 : 4.5;
    if (ratio < need) out.push({text: n.textContent.trim().slice(0,40), ratio: Math.round(ratio*100)/100, need, color: cs.color, bg: `rgb(${bg.r},${bg.g},${bg.b})`});
  }
  return out;
}
"""
JS_STRUCT = r"""
() => {
  const issues = [];
  const name = el => (el.getAttribute('aria-label') || (el.labels && el.labels[0] && el.labels[0].textContent) || el.textContent || el.value || '').trim().replace(/\s+/g,' ');
  if (!document.documentElement.lang) issues.push('html has no lang');
  if (!document.title) issues.push('no <title>');
  const ids = {}; document.querySelectorAll('[id]').forEach(e => { ids[e.id] = (ids[e.id]||0)+1; });
  Object.entries(ids).filter(([k,v]) => v>1).forEach(([k]) => issues.push('duplicate id ' + k));
  document.querySelectorAll('input,select,textarea').forEach(e => { if (!name(e)) issues.push('control without a name: ' + (e.id||e.name||e.type)); });
  document.querySelectorAll('button').forEach(e => { if (!name(e)) issues.push('button without a name: ' + e.id); });
  document.querySelectorAll('[aria-describedby],[aria-labelledby]').forEach(e => { (e.getAttribute('aria-describedby')||e.getAttribute('aria-labelledby')).split(' ').forEach(id => { if (!document.getElementById(id)) issues.push('dangling aria ref ' + id); }); });
  document.querySelectorAll('table').forEach(t => { if (!t.querySelector('th')) issues.push('table without headers'); });
  const hs = [...document.querySelectorAll('h1,h2,h3,h4')].map(h => +h.tagName[1]);
  for (let i=1;i<hs.length;i++) if (hs[i]-hs[i-1] > 1) issues.push('heading level jump ' + hs[i-1] + '->' + hs[i]);
  if (document.querySelectorAll('h1').length !== 1) issues.push('expected one h1, found ' + document.querySelectorAll('h1').length);
  if (!document.querySelector('main')) issues.push('no <main> landmark');
  const live = [...document.querySelectorAll('[aria-live],[role=status],[role=alert]')].map(e => e.id + ':' + (e.getAttribute('aria-live')||e.getAttribute('role')));
  return {issues, headings: [...document.querySelectorAll('h1,h2,h3')].map(h => h.tagName + ' ' + h.textContent.trim().slice(0,45)), live,
          landmarks: [...document.querySelectorAll('header,main,nav,footer,section[aria-labelledby]')].map(e => e.tagName.toLowerCase() + (e.getAttribute('aria-labelledby') ? '['+e.getAttribute('aria-labelledby')+']' : ''))};
}
"""
JS_FOCUS = r"""
() => { const e = document.activeElement; if (!e || e === document.body) return null;
  const cs = getComputedStyle(e); const r = e.getBoundingClientRect();
  return {tag: e.tagName.toLowerCase(), id: e.id, label: (e.getAttribute('aria-label') || (e.labels && e.labels[0] && e.labels[0].textContent) || e.textContent || e.value || '').trim().replace(/\s+/g,' ').slice(0,50),
          outline: cs.outlineStyle + ' ' + cs.outlineWidth, w: Math.round(r.width), h: Math.round(r.height), visible: r.width>0 && r.height>0}; }
"""

problems = []
def note(state, kind, detail): problems.append((state, kind, detail))

with sync_playwright() as pw:
    b = pw.chromium.launch(); page = b.new_page(viewport={"width": 1000, "height": 900})
    page.set_default_timeout(60000)
    page.goto(URL)

    s = page.evaluate(JS_STRUCT)
    print("HEADINGS:"); [print("  ", h) for h in s["headings"]]
    print("LANDMARKS:", s["landmarks"]); print("LIVE REGIONS:", s["live"])
    for i in s["issues"]: note("initial", "structure", i)

    # tab order, first pass
    print("\nTAB ORDER (initial page):")
    page.evaluate("document.activeElement && document.activeElement.blur()")
    seen = []
    for i in range(30):
        page.keyboard.press("Tab"); f = page.evaluate(JS_FOCUS)
        if not f: break
        seen.append(f)
        print(f"  {i+1:2} {f['tag']:7} {f['label']!r:55} outline={f['outline']}")
        if not f["visible"]: note("initial", "focus", f"focused element not visible: {f['label']}")
        if f["outline"].startswith("none") or f["outline"].startswith("0"): note("initial", "focus", f"no focus outline: {f['label']}")
        if min(f["w"], f["h"]) < 24: note("initial", "target size", f"{f['label']} is {f['w']}x{f['h']}px")
        if f["label"] == "" : note("initial", "name", f"focusable without a name: {f['id']}")

    # states
    def audit(state):
        for c in page.evaluate(JS_CONTRAST): note(state, "contrast", c)
        for i in page.evaluate(JS_STRUCT)["issues"]: note(state, "structure", i)

    audit("initial")
    page.click("#load"); page.wait_for_selector("#items li"); audit("recap standard")
    for prof in ("deaf", "blind", "deafblind"):
        page.check(f'input[name="profile"][value="{prof}"]'); audit(f"recap {prof}")
    page.check('input[name="profile"][value="standard"]')
    page.check('input[name="depth"][value="analyst"]'); page.select_option("#story", "red_card_swing")
    page.wait_for_function("document.querySelector('#verdict').textContent.includes('analyst')"); audit("analyst red-card")
    page.select_option("#fault", "wrong_minute"); page.wait_for_function("document.querySelector('#trace-details').open"); audit("fault demo")
    page.select_option("#fault", "")
    page.click("#rp-start"); page.wait_for_function("!document.querySelector('#rp-controls').hidden"); audit("simulated feed")
    page.click("#contrast"); audit("high contrast")
    page.click("#contrast")
    # larger text and narrow screen
    for _ in range(2): page.click("#bigger")
    page.set_viewport_size({"width": 320, "height": 800})
    sw = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
    print("\nREFLOW at 320px with larger text: scrollWidth/clientWidth =", sw)
    if sw[0] > sw[1] + 1:
        wide = page.evaluate("[...document.querySelectorAll('body *')].filter(e => e.getBoundingClientRect().right > document.documentElement.clientWidth + 1 && getComputedStyle(e).position !== 'fixed').slice(0,6).map(e => e.tagName.toLowerCase() + '#' + e.id + '.' + e.className)")
        note("320px + large text", "reflow", f"horizontal scroll; wide elements: {wide}")

    # radio keyboard behaviour
    page.set_viewport_size({"width": 1000, "height": 900})
    page.focus('input[name="profile"][value="standard"]'); page.keyboard.press("ArrowDown")
    print("Arrow key on profile radios selects:", page.evaluate("document.querySelector('input[name=profile]:checked').value"))

    b.close()

# collapse duplicates
seen = {}
for st, kind, detail in problems:
    key = (kind, json.dumps(detail, sort_keys=True) if isinstance(detail, dict) else detail)
    seen.setdefault(key, []).append(st)
print(f"\nPROBLEMS FOUND: {len(seen)}")
for (kind, detail), states in seen.items():
    print(f"- [{kind}] {detail}   (in: {', '.join(sorted(set(states)))})")

sys.exit(1 if seen else 0)
