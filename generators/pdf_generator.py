"""HTML -> PDF via headless Chrome (selenium, already a project dependency).

Chrome's printToPDF renders the same HTML/CSS the career-ops
generate-resume.mjs uses, so no LibreOffice or extra installs are needed.
"""
import base64
import os

from generators.resume_html import render_resume_html, render_cover_letter_html

_driver = None


def _find_chromedriver():
    """Same lookup as main.py init_browser(): newest cached chromedriver,
    falling back to webdriver-manager, then selenium-manager."""
    import sys
    from pathlib import Path
    plat_dir = {"win32": "win64", "darwin": "mac64"}.get(sys.platform, "linux64")
    exe = "chromedriver.exe" if sys.platform == "win32" else "chromedriver"
    cache = Path(os.path.expanduser("~")) / ".cache" / "selenium" / "chromedriver" / plat_dir
    drivers = sorted(cache.glob(f"*/{exe}")) if cache.exists() else []
    if drivers:
        return str(drivers[-1])
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        return ChromeDriverManager().install()
    except Exception:
        return None


def _get_driver():
    global _driver
    if _driver is None:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service as ChromeService
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--log-level=3")
        driver_path = _find_chromedriver()
        if driver_path:
            _driver = webdriver.Chrome(service=ChromeService(driver_path), options=options)
        else:
            _driver = webdriver.Chrome(options=options)
    return _driver


def close_driver():
    global _driver
    if _driver is not None:
        try:
            _driver.quit()
        except Exception:
            pass
        _driver = None


def html_to_pdf(html: str, pdf_path: str) -> str:
    """Write html to a sibling .html file, print it to PDF via Chrome CDP."""
    html_path = os.path.splitext(pdf_path)[0] + ".html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    driver = _get_driver()
    driver.get("file:///" + os.path.abspath(html_path).replace("\\", "/"))
    result = driver.execute_cdp_cmd("Page.printToPDF", {
        "paperWidth": 8.5,
        "paperHeight": 11,
        "marginTop": 0.4,
        "marginBottom": 0.4,
        "marginLeft": 0.4,
        "marginRight": 0.4,
        "printBackground": True,
    })
    with open(pdf_path, "wb") as f:
        f.write(base64.b64decode(result["data"]))
    os.remove(html_path)  # PDF is the deliverable; HTML is an intermediate
    return pdf_path


def generate_resume_pdf(payload: dict, output_dir: str) -> str:
    pdf_path = os.path.join(output_dir, f"{payload['meta']['filename_base']}.pdf")
    return html_to_pdf(render_resume_html(payload), pdf_path)


def generate_cover_letter_pdf(payload: dict, output_dir: str) -> str:
    pdf_path = os.path.join(output_dir,
                            f"{payload['meta']['filename_base']}_CoverLetter.pdf")
    return html_to_pdf(render_cover_letter_html(payload), pdf_path)
