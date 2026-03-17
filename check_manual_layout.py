"""
APS 说明书布局核验脚本
自动检查 config_manual 页面在不同模式下的布局问题
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from web.bootstrap.runtime_probe import probe_health, resolve_healthy_endpoint

# 检查是否有 selenium
try:
    from selenium import webdriver
    from selenium.common.exceptions import NoSuchElementException
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    HAS_SELENIUM = True
except ImportError:
    HAS_SELENIUM = False
    NoSuchElementException = Exception
    print("警告：未安装 selenium，无法进行浏览器自动化测试")
    print("请运行：pip install selenium")

_DEFAULT_BASE_URL = "http://127.0.0.1:5000"


def _has_manual_related_min_width(css_content: str) -> bool:
    patterns = [
        r"\.manual-related-panel\s*,\s*\.manual-related-body\s*\{[^}]*min-width\s*:\s*0\s*;",
        r"\.manual-related-panel\s*\{[^}]*min-width\s*:\s*0\s*;",
    ]
    return any(re.search(pattern, css_content, re.DOTALL) for pattern in patterns)


def _normalize_base_url(base_url: str) -> str:
    normalized = str(base_url or "").strip().rstrip("/")
    return normalized or _DEFAULT_BASE_URL


def _resolve_base_url(explicit_base_url: Optional[str], runtime_dir: Path = REPO_ROOT) -> tuple[str, str]:
    if explicit_base_url and str(explicit_base_url).strip():
        return _normalize_base_url(str(explicit_base_url)), "explicit"
    endpoint = resolve_healthy_endpoint(str(runtime_dir))
    if endpoint is not None:
        return _normalize_base_url(str(endpoint["base_url"])), str(endpoint.get("source") or "runtime_files")
    return _DEFAULT_BASE_URL, "default"


def _server_is_reachable(base_url: str) -> bool:
    return probe_health(_normalize_base_url(base_url), timeout=2.0) is not None


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(description="APS config_manual layout checker.")
    parser.add_argument(
        "--base-url",
        default="",
        help="显式指定浏览器自动化检查使用的 base URL，例如 http://127.0.0.1:5705",
    )
    return parser.parse_args(argv)


def check_layout_via_styles():
    """通过静态分析 CSS 检查布局规则"""
    print("=== 静态 CSS 布局分析 ===\n")

    css_file = REPO_ROOT / "static" / "css" / "ui_contract.css"
    if not css_file.exists():
        print("❌ CSS 文件不存在")
        return False

    css_content = css_file.read_text(encoding="utf-8")

    checks = {
        "左侧目录宽度稳定": ".manual-toc" in css_content and "width: 260px" in css_content,
        "目录固定不滚动": "position: sticky" in css_content and ".manual-toc" in css_content,
        "主列弹性布局": ".manual-main-column" in css_content and "flex: 1" in css_content,
        "page模式包装器": ".manual-wrapper-page" in css_content,
        "相关模块面板最小宽度": _has_manual_related_min_width(css_content),
        "响应式折叠": "@media (max-width: 900px)" in css_content,
    }

    all_pass = True
    for check_name, result in checks.items():
        status = "[OK]" if result else "[FAIL]"
        print(f"{status} {check_name}")
        if not result:
            all_pass = False

    return all_pass


def check_layout_via_browser(base_url: str):
    """通过浏览器自动化检查实际渲染"""
    if not HAS_SELENIUM:
        return None

    base_url_s = _normalize_base_url(base_url)
    if not _server_is_reachable(base_url_s):
        print(f"\n[WARN] 未检测到可用 APS 服务（base_url={base_url_s}），跳过浏览器自动化布局检查")
        return None

    print("\n=== 浏览器自动化布局检查 ===\n")

    test_cases = [
        {
            "name": "Full 模式 - 经典界面",
            "url": f"{base_url_s}/scheduler/config/manual",
            "theme": "v1",
            "mode": "full",
        },
        {
            "name": "Full 模式 - 现代界面",
            "url": f"{base_url_s}/scheduler/config/manual",
            "theme": "v2",
            "mode": "full",
        },
        {
            "name": "Page 模式 (materials) - 经典界面",
            "url": f"{base_url_s}/scheduler/config/manual?page=material.materials_page",
            "theme": "v1",
            "mode": "page",
        },
        {
            "name": "Page 模式 (materials) - 现代界面",
            "url": f"{base_url_s}/scheduler/config/manual?page=material.materials_page",
            "theme": "v2",
            "mode": "page",
        },
        {
            "name": "Page 模式 (config) - 经典界面",
            "url": f"{base_url_s}/scheduler/config/manual?page=scheduler.config_page",
            "theme": "v1",
            "mode": "page",
        },
        {
            "name": "Page 模式 (config) - 现代界面",
            "url": f"{base_url_s}/scheduler/config/manual?page=scheduler.config_page",
            "theme": "v2",
            "mode": "page",
        },
        {
            "name": "Page 模式 (reports) - 经典界面",
            "url": f"{base_url_s}/scheduler/config/manual?page=reports.index",
            "theme": "v1",
            "mode": "page",
        },
        {
            "name": "Page 模式 (reports) - 现代界面",
            "url": f"{base_url_s}/scheduler/config/manual?page=reports.index",
            "theme": "v2",
            "mode": "page",
        },
    ]

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")

    try:
        driver = webdriver.Chrome(options=options)
    except Exception as e:
        print(f"❌ 无法启动 Chrome：{e}")
        print("提示：确保已安装 ChromeDriver 并在 PATH 中")
        return None

    results = []

    try:
        for case in test_cases:
            print(f"\n检查：{case['name']}")
            print(f"  URL: {case['url']}")

            driver.get(case["url"])
            time.sleep(1)

            driver.add_cookie({"name": "aps_ui_mode", "value": case["theme"]})
            driver.refresh()
            time.sleep(1)

            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "manual-wrapper"))
                )
            except Exception:
                print("  [FAIL] 页面加载超时或找不到 .manual-wrapper")
                results.append({**case, "pass": False, "issues": ["页面加载失败"]})
                continue

            issues = []

            try:
                toc = driver.find_element(By.CLASS_NAME, "manual-toc")
                toc_width = toc.size["width"]
                if abs(toc_width - 260) > 10:
                    issues.append(f"目录宽度异常: {toc_width}px (期望 260px)")
            except Exception:
                issues.append("找不到目录元素 .manual-toc")

            if case["mode"] == "page":
                try:
                    main_column = driver.find_element(By.CLASS_NAME, "manual-main-column")
                    content = main_column.find_element(By.CLASS_NAME, "manual-content")

                    try:
                        related_panel = main_column.find_element(By.CLASS_NAME, "manual-related-panel")
                        content_width = content.size["width"]
                        panel_width = related_panel.size["width"]

                        if abs(content_width - panel_width) > 20:
                            issues.append(f"正文与相关模块宽度不一致: {content_width}px vs {panel_width}px")

                        panel_left = related_panel.location["x"]
                        toc_right = toc.location["x"] + toc.size["width"]

                        if panel_left < toc_right + 20:
                            issues.append("相关模块卡片侵入目录区域")
                    except NoSuchElementException:
                        pass
                    except Exception as e:
                        issues.append(f"相关模块面板检查失败: {type(e).__name__}: {e}")

                except Exception:
                    issues.append("找不到主列元素 .manual-main-column")

            try:
                driver.execute_script("window.scrollTo(0, 300);")
                time.sleep(0.5)

                toc_after_scroll = driver.find_element(By.CLASS_NAME, "manual-toc")
                position = driver.execute_script(
                    "return window.getComputedStyle(arguments[0]).position;",
                    toc_after_scroll,
                )
                if position != "sticky":
                    issues.append(f"目录未使用 sticky 定位（实际: {position}）")
            except Exception as e:
                issues.append(f"目录 sticky 检查失败: {type(e).__name__}: {e}")

            if issues:
                print(f"  [FAIL] 发现 {len(issues)} 个问题：")
                for issue in issues:
                    print(f"    - {issue}")
                results.append({**case, "pass": False, "issues": issues})
            else:
                print("  [PASS] 通过所有检查")
                results.append({**case, "pass": True, "issues": []})

    finally:
        driver.quit()

    return results


def main(argv=None):
    args = _parse_args(argv)
    base_url, base_url_source = _resolve_base_url(args.base_url, runtime_dir=REPO_ROOT)
    print("APS 说明书布局核验工具\n")
    print(f"[INFO] 浏览器检查基地址：{base_url}（source={base_url_source}）")
    if base_url_source == "default":
        print("[WARN] 未发现健康的运行时实例，浏览器分支将回退到默认地址。")

    css_ok = check_layout_via_styles()
    browser_results = check_layout_via_browser(base_url)

    print("\n" + "=" * 60)
    print("核验结果汇总")
    print("=" * 60)

    if css_ok:
        print("[OK] CSS 静态规则检查通过")
    else:
        print("[FAIL] CSS 静态规则检查发现问题")

    if browser_results is None:
        print("\n[WARN] 浏览器自动化测试未执行（缺少 selenium / ChromeDriver / 本地 APS 服务）")
        print("\n手动核验清单：")
        print(f"1. 访问 {base_url}/scheduler/config/manual")
        print("2. 切换 v1/v2 界面模式（页面右上角）")
        print("3. 检查：")
        print("   A. 左侧目录列宽 260px 稳定")
        print("   B. 右侧正文与相关模块面板同列同宽")
        print("   C. 相关模块卡片不侵入左侧目录区")
        print("   D. 滚动后布局无抖动")
    elif browser_results:
        passed = sum(1 for r in browser_results if r["pass"])
        total = len(browser_results)
        print(f"\n浏览器测试：{passed}/{total} 通过")

        if passed < total:
            print("\n失败用例：")
            for result in browser_results:
                if not result["pass"]:
                    print(f"\n  {result['name']}")
                    for issue in result["issues"]:
                        print(f"    - {issue}")

        report_file = REPO_ROOT / "evidence" / "manual_layout_check_report.json"
        report_file.parent.mkdir(exist_ok=True)
        report_file.write_text(
            json.dumps(browser_results, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"\n详细报告已保存至：{report_file}")

    ok = css_ok and (browser_results is None or all(result["pass"] for result in browser_results))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
