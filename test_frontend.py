from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})

    errors = []
    page.on("pageerror", lambda err: errors.append(str(err)))

    print("=" * 60)
    print("1. LOGIN PAGE TEST")
    print("=" * 60)

    page.goto("http://localhost:3002/login")
    page.wait_for_load_state("networkidle")
    page.screenshot(path="/tmp/01_login_page.png", full_page=True)
    print(f"  Login page loaded, title: {page.title()}")

    username_input = page.locator('input#username, input[placeholder*="用户名"], input[type="text"]').first
    password_input = page.locator('input#password, input[placeholder*="密码"], input[type="password"]').first
    login_button = page.locator('button[type="submit"], button:has-text("登录")').first

    if username_input.count() == 0:
        print("  ❌ Username input not found!")
    else:
        username_input.fill("admin")
        print("  ✅ Username filled")

    if password_input.count() == 0:
        print("  ❌ Password input not found!")
    else:
        password_input.fill("admin123")
        print("  ✅ Password filled")

    if login_button.count() == 0:
        print("  ❌ Login button not found!")
    else:
        login_button.click()
        print("  ✅ Login button clicked")

    page.wait_for_timeout(3000)
    page.wait_for_load_state("networkidle")
    current_url = page.url
    print(f"  Current URL after login: {current_url}")

    if "/login" not in current_url:
        print("  ✅ Login successful - redirected away from login page")
    else:
        print("  ❌ Login failed - still on login page")
        page.screenshot(path="/tmp/01_login_failed.png", full_page=True)

    page.screenshot(path="/tmp/02_after_login.png", full_page=True)

    print("\n" + "=" * 60)
    print("2. DASHBOARD PAGE TEST")
    print("=" * 60)

    page.wait_for_timeout(2000)
    page.wait_for_load_state("networkidle")
    page.screenshot(path="/tmp/03_dashboard.png", full_page=True)

    stats_cards = page.locator('.ant-card, .ant-statistic, [class*="stat"]').all()
    print(f"  Stats cards found: {len(stats_cards)}")

    page_text = page.inner_text("body")
    for keyword in ["情报", "威胁", "PIR", "黑话", "图谱"]:
        if keyword in page_text:
            print(f"  ✅ Dashboard contains '{keyword}'")
        else:
            print(f"  ⚠️ Dashboard missing '{keyword}'")

    print("\n" + "=" * 60)
    print("3. INTELLIGENCE PAGE TEST")
    print("=" * 60)

    intel_link = page.locator('a[href*="/intelligence"], span:has-text("情报"), a:has-text("情报")').first
    if intel_link.count() > 0:
        intel_link.click()
        page.wait_for_timeout(2000)
        page.wait_for_load_state("networkidle")
        page.screenshot(path="/tmp/04_intelligence.png", full_page=True)
        print(f"  Intelligence page URL: {page.url}")

        table_rows = page.locator('.ant-table-row, tr[data-row-key]').all()
        print(f"  Table rows found: {len(table_rows)}")

        search_input = page.locator('input[placeholder*="搜索"], input[placeholder*="搜索"]').first
        if search_input.count() > 0:
            search_input.fill("诈骗")
            page.wait_for_timeout(1500)
            page.screenshot(path="/tmp/05_intelligence_search.png", full_page=True)
            print("  ✅ Search executed")
        else:
            print("  ⚠️ Search input not found")
    else:
        print("  ❌ Intelligence link not found in navigation")

    print("\n" + "=" * 60)
    print("4. GRAPH VIEW PAGE TEST")
    print("=" * 60)

    graph_link = page.locator('a[href*="/graph"], span:has-text("图谱"), a:has-text("图谱")').first
    if graph_link.count() > 0:
        graph_link.click()
        page.wait_for_timeout(3000)
        page.wait_for_load_state("networkidle")
        page.screenshot(path="/tmp/06_graph.png", full_page=True)
        print(f"  Graph page URL: {page.url}")
    else:
        print("  ❌ Graph link not found in navigation")

    print("\n" + "=" * 60)
    print("5. BLACKTALK PAGE TEST")
    print("=" * 60)

    bt_link = page.locator('a[href*="/blacktalk"], span:has-text("黑话"), a:has-text("黑话")').first
    if bt_link.count() > 0:
        bt_link.click()
        page.wait_for_timeout(2000)
        page.wait_for_load_state("networkidle")
        page.screenshot(path="/tmp/07_blacktalk.png", full_page=True)
        print(f"  BlackTalk page URL: {page.url}")

        decode_input = page.locator('textarea, input[placeholder*="解码"], input[placeholder*="输入"]').first
        if decode_input.count() > 0:
            decode_input.fill("他在跑分，用猫池洗白")
            page.wait_for_timeout(1000)
            decode_button = page.locator('button:has-text("解码"), button:has-text("Decode")').first
            if decode_button.count() > 0:
                decode_button.click()
                page.wait_for_timeout(2000)
                page.screenshot(path="/tmp/08_blacktalk_decode.png", full_page=True)
                print("  ✅ Decode executed")
            else:
                print("  ⚠️ Decode button not found")
        else:
            print("  ⚠️ Decode input not found")
    else:
        print("  ❌ BlackTalk link not found")

    print("\n" + "=" * 60)
    print("6. PIR PAGE TEST")
    print("=" * 60)

    pir_link = page.locator('a[href*="/pir"], span:has-text("PIR"), a:has-text("PIR")').first
    if pir_link.count() > 0:
        pir_link.click()
        page.wait_for_timeout(2000)
        page.wait_for_load_state("networkidle")
        page.screenshot(path="/tmp/09_pir.png", full_page=True)
        print(f"  PIR page URL: {page.url}")
    else:
        print("  ❌ PIR link not found")

    print("\n" + "=" * 60)
    print("7. REPORTS PAGE TEST")
    print("=" * 60)

    report_link = page.locator('a[href*="/report"], span:has-text("报告"), a:has-text("报告")').first
    if report_link.count() > 0:
        report_link.click()
        page.wait_for_timeout(2000)
        page.wait_for_load_state("networkidle")
        page.screenshot(path="/tmp/10_reports.png", full_page=True)
        print(f"  Reports page URL: {page.url}")
    else:
        print("  ❌ Reports link not found")

    print("\n" + "=" * 60)
    print("8. LOGOUT TEST")
    print("=" * 60)

    logout_button = page.locator('button:has-text("退出"), button:has-text("登出"), [class*="logout"]').first
    if logout_button.count() > 0:
        logout_button.click()
        page.wait_for_timeout(2000)
        page.wait_for_load_state("networkidle")
        current_url = page.url
        if "/login" in current_url:
            print("  ✅ Logout successful - redirected to login")
        else:
            print(f"  ⚠️ After logout URL: {current_url}")
    else:
        print("  ⚠️ Logout button not found (might be in dropdown)")

    print("\n" + "=" * 60)
    print("BROWSER ERRORS")
    print("=" * 60)
    if errors:
        for err in errors:
            print(f"  ❌ {err[:200]}")
    else:
        print("  ✅ No page errors")

    browser.close()
    print("\nTest complete. Screenshots saved to /tmp/01-10_*.png")
