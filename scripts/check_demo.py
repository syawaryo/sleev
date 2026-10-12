"""Browser acceptance checks for the static demo (serve frontend/dist on 4173).

python scripts/check_demo.py
Requires the locally installed Playwright and Chromium.
"""
import json
import os
import re
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp/demo-qa"
OUT.mkdir(parents=True, exist_ok=True)
URL = os.environ.get("DEMO_URL", "http://127.0.0.1:4173/")


def main():
    snapshot = json.loads((ROOT / "frontend/public/demo/manifest.json").read_text(encoding="utf-8"))
    entity_counts = {}
    for floor in snapshot["floors"]:
        entities = json.loads((ROOT / "frontend/public/demo" / floor["entitiesFile"]).read_text(encoding="utf-8"))
        assert len(entities["entities"]) == entities["summary"]["entity_count"]
        assert sum(entities["summary"]["type_count"].values()) == len(entities["entities"])
        entity_counts[floor["id"]] = len(entities["entities"])
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1024, "height": 768}, has_touch=True, device_scale_factor=1)
        page = context.new_page()
        errors, api_calls = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("request", lambda req: api_calls.append(req.url) if "/api/" in req.url else None)
        page.goto(URL)
        expect(page.get_by_role("region", name="チェック結果一覧")).to_be_visible()
        assert page.get_by_role("tab").all_text_contents() == ["チェック結果", "図面", "チェック観点", "図面データ"]
        expect(page.get_by_text("オフライン利用準備済み")).to_be_visible(timeout=60000)
        assert page.get_by_text("チェック実行", exact=True).count() == 0
        assert page.locator("[data-check-id]").count() == 13
        assert page.locator('[data-check-id="6"]').get_by_text("未判定・対象なし").count() == 1
        assert page.locator("aside").count() == 0
        assert page.locator("header").bounding_box()["height"] < 60
        assert page.locator(".check-list").bounding_box()["width"] == 1024
        page.get_by_role("tab", name="チェック観点", exact=True).click()
        expect(page.get_by_role("tabpanel", name="チェック観点", exact=True)).to_be_visible()
        assert page.locator(".criteria-table tbody tr").count() == 13
        assert page.get_by_role("dialog").count() == 0
        page.get_by_role("tab", name="チェック結果", exact=True).click()
        page.screenshot(path=str(OUT / "01-results.png"))

        # A real NG takes us to its sleeve and the correct checklist item.
        page.get_by_role("button", name="#9の図面を見る", exact=True).click()
        expect(page.locator(".drawing-sidebar").get_by_text("チェック結果", exact=True)).to_be_visible()
        expect(page.locator(".drawing-panel svg")).to_be_visible()
        page.screenshot(path=str(OUT / "02-drawing-ng.png"))
        selected_viewbox = page.locator(".drawing-panel svg").get_attribute("viewBox")
        criterion_link = page.get_by_role("button", name="チェック観点 #9を見る", exact=True)
        assert criterion_link.bounding_box()["width"] > 230
        assert criterion_link.bounding_box()["height"] > 60
        # The rule text and even the card's padding are part of the target.
        criterion_link.click(position={"x": 5, "y": 5})
        expect(page.get_by_role("tab", name="チェック観点", exact=True)).to_have_attribute("aria-selected", "true")
        expect(page.locator("#criterion-9")).to_be_focused()
        expect(page.locator("#criterion-9")).to_have_attribute("aria-current", "true")
        page.screenshot(path=str(OUT / "03-criterion.png"))
        page.get_by_role("tab", name="図面", exact=True).click()
        expect(page.locator(".drawing-panel svg")).to_be_visible()
        expect(page.locator(".drawing-panel svg")).to_have_attribute("viewBox", selected_viewbox)
        assert page.locator(".drawing-sidebar").bounding_box()["width"] == 300

        # Overview, actual touch pan + pinch, and explicit zoom controls.
        page.get_by_role("button", name="← 図面の要約", exact=True).click()
        expect(page.get_by_text("図面の要約", exact=True)).to_be_visible()
        svg = page.locator(".drawing-panel svg").first
        box = svg.bounding_box()
        x, y = box["x"] + box["width"] * 0.3, box["y"] + box["height"] * 0.5
        cdp = context.new_cdp_session(page)
        before = svg.get_attribute("viewBox")
        cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y, "id": 1}]})
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x+60, "y": y+30, "id": 1}]})
        cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        expect(svg).not_to_have_attribute("viewBox", before)
        before_width = float(svg.get_attribute("viewBox").split()[2])
        cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y, "id": 1}, {"x": x+80, "y": y, "id": 2}]})
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x-30, "y": y, "id": 1}, {"x": x+110, "y": y, "id": 2}]})
        cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        page.wait_for_function("(width) => Number(document.querySelector('.drawing-panel svg').getAttribute('viewBox').split(' ')[2]) < width", arg=before_width)
        page.get_by_role("button", name="全体表示", exact=True).click()
        page.screenshot(path=str(OUT / "04-overview.png"))

        # OK-only checks expose both the drawing shortcut and individual rows.
        page.get_by_role("tab", name="チェック結果", exact=True).click()
        page.get_by_role("button", name="OK", exact=True).click()
        group = page.locator('[data-check-id="5"]')
        group.get_by_role("button", name="#5 勾配記載", exact=True).click()
        expect(group.locator("tr").first).to_be_visible()
        group.locator("tr").first.click()
        expect(svg).to_be_visible()

        # All source entities are counted, including the unclassified group.
        page.get_by_role("tab", name="図面データ", exact=True).click()
        expect(page.get_by_text("図面から読み取った線・文字・スリーブなどの要素を、種類ごとに確認できます。", exact=True)).to_be_visible()
        expect(page.get_by_text(f'{entity_counts["1f"]:,} 件', exact=True)).to_be_visible()
        assert sum(page.locator("[data-entity-count]").evaluate_all("els => els.map(el => Number(el.dataset.entityCount))")) == entity_counts["1f"]
        page.get_by_role("button", name="衛生スリーブ", exact=True).click()
        expect(page.locator('[data-group="スリーブ_衛生"] [data-layer]').first).to_be_visible()
        page.screenshot(path=str(OUT / "07-drawing-data.png"))
        search = page.get_by_placeholder("検索 (レイヤー名・テキスト・タイプ)")
        search.fill("TEXT")
        expect(page.locator("[data-layer]").first).to_be_visible()
        search.fill("no-such-layer-123456")
        expect(page.get_by_text("該当するデータがありません", exact=True)).to_be_visible()
        search.fill("")
        page.get_by_role("tab", name="チェック結果", exact=True).focus()
        page.keyboard.press("End")
        expect(page.get_by_role("tab", name="図面データ", exact=True)).to_be_focused()
        page.keyboard.press("ArrowLeft")
        expect(page.get_by_role("tab", name="チェック観点", exact=True)).to_have_attribute("aria-selected", "true")

        # A fresh reload while offline needs no analysis server or user rerun.
        page.wait_for_function("navigator.serviceWorker.controller !== null")
        context.set_offline(True)
        page.reload()
        expect(page.get_by_role("region", name="チェック結果一覧")).to_be_visible()
        page.get_by_role("button", name=re.compile(r"^2階床スリーブ図[.]dxf")).click()
        page.get_by_role("tab", name="図面", exact=True).click()
        expect(page.locator(".drawing-panel svg")).to_be_visible()
        expect(page.locator(".drawing-stats")).to_contain_text("281")
        page.get_by_role("button", name="干渉を調べる下階壁", exact=True).click()
        expect(page.get_by_role("button", name="干渉を調べる下階壁", exact=True)).to_have_attribute("aria-pressed", "true")
        page.screenshot(path=str(OUT / "05-offline-2f.png"))
        page.get_by_role("tab", name="図面データ", exact=True).click()
        expect(page.get_by_text(f'{entity_counts["2f"]:,} 件', exact=True)).to_be_visible()
        assert sum(page.locator("[data-entity-count]").evaluate_all("els => els.map(el => Number(el.dataset.entityCount))")) == entity_counts["2f"]
        page.get_by_role("button", name=re.compile(r"^1階床スリーブ図[.]dxf")).click()
        expect(page.get_by_text(f'{entity_counts["1f"]:,} 件', exact=True)).to_be_visible()
        assert not errors, errors
        assert not api_calls, api_calls
        context.close()

        # Missing/zero target data must never become 'all OK'.
        empty = json.loads((ROOT / "frontend/public/demo/manifest.json").read_text(encoding="utf-8"))
        empty["floors"][0]["sleeves"] = []
        empty["floors"][0]["results"] = []
        context = browser.new_context(viewport={"width": 1024, "height": 768}, service_workers="block")
        page = context.new_page()
        page.route("**/demo/manifest.json", lambda route: route.fulfill(json=empty))
        page.goto(URL)
        expect(page.get_by_text("読み取れたスリーブは0件です。判定対象がないため、OKとは判定していません。", exact=True)).to_be_visible()
        assert page.get_by_text("全て OK", exact=True).count() == 0
        assert page.get_by_text("未判定・対象なし", exact=True).count() == 13
        page.screenshot(path=str(OUT / "06-zero-targets.png"))
        context.close()

        # A failed drawing can be retried without losing the selected floor.
        context = browser.new_context(viewport={"width": 1024, "height": 768}, service_workers="block")
        page = context.new_page()
        page.route("**/demo/2f-*.json", lambda route: route.fulfill(status=503, body="temporarily unavailable"))
        page.goto(URL)
        page.get_by_role("button", name=re.compile(r"^2階床スリーブ図[.]dxf")).click()
        page.get_by_role("tab", name="図面", exact=True).click()
        expect(page.get_by_role("alert")).to_contain_text("503")
        page.unroute("**/demo/2f-*.json")
        page.get_by_role("button", name="再読み込み", exact=True).click()
        expect(page.locator(".drawing-panel svg")).to_be_visible()
        expect(page.locator(".drawing-stats")).to_contain_text("281")
        page.route("**/demo/*-entities-*.json", lambda route: route.fulfill(status=503, body="temporarily unavailable"))
        page.get_by_role("tab", name="図面データ", exact=True).click()
        expect(page.get_by_role("alert")).to_contain_text("503")
        page.unroute("**/demo/*-entities-*.json")
        page.get_by_role("button", name="再読み込み", exact=True).click()
        expect(page.get_by_text(f'{entity_counts["2f"]:,} 件', exact=True)).to_be_visible()
        browser.close()
    print("PASS: four tabs, whole-card criterion navigation, drawing position preserved, full entity counts/search, keyboard tabs, offline floor/data switching, NG/OK navigation, touch pan/pinch, zero targets, drawing/data retry, no API calls or browser errors")


if __name__ == "__main__":
    main()
