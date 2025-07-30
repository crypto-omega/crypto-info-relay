from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import logging
import time

GATE_ANNOUNCEMENT_URL = "https://www.gate.com/zh/announcements"
GATE_HOST = "https://www.gate.com"

def create_driver(headless: bool = False,
                  user_data_dir: str = "~/.config/selenium-profile",
                  use_proxy: bool = True,
                  proxy_address: str = "172.25.49.1:7890"):
    from selenium.webdriver.chrome.options import Options

    options = Options()
    options.add_argument(f"--user-data-dir={user_data_dir}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--start-maximized")

    if headless:
        options.add_argument("--headless=new")

    # ✅ 设置 User-Agent
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/115.0.0.0 Safari/537.36"
    )

    # ✅ 添加本地代理（默认启用）
    if use_proxy:
        options.add_argument(f'--proxy-server=http://{proxy_address}')

    try:
        driver = webdriver.Chrome(options=options)

        # ✅ 绕过 navigator.webdriver 检测
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                  get: () => undefined
                });
            """
        })

        return driver
    except Exception as e:
        logging.error("❌ 启动 ChromeDriver 时出错: %s", e)
        raise

def wait_and_scroll(driver):
    try:
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CLASS_NAME, "text-subtitle")))
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)  # 等待加载更多
    except TimeoutException:
        logging.warning("⚠️ 页面加载等待超时")

def parse_announcements(driver):
    items = driver.find_elements(By.CSS_SELECTOR, "a[href^='/zh/announcements/article/']")
    logging.info("📰 共找到公告数: %d", len(items))
    announcements = []
    for a in items:
        try:
            lines = a.text.strip().splitlines()
            title = lines[-3].strip() if len(lines) > 0 else ""
            time_text = lines[-2].strip() if len(lines) > 2 else ""
            link = a.get_attribute("href")
            announcements.append({
                "title": title,
                "time": time_text,
                "link": link
            })
        except Exception as e:
            logging.warning("⚠️ 跳过异常公告元素: %s", e)
    return announcements

def scrape_announcements(headless=False):
    driver = create_driver(headless=headless)
    try:
        logging.info("🌐 打开公告页面: %s", GATE_ANNOUNCEMENT_URL)
        driver.get(GATE_ANNOUNCEMENT_URL)
        wait_and_scroll(driver)
        announcements = parse_announcements(driver)
        return announcements
    except Exception as e:
        logging.error("❌ 爬取 Gate 公告时出错: %s", e)
        return []
    finally:
        driver.quit()

# 调试用：运行一次并输出结果
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    results = scrape_announcements(headless=False)  # 第一次建议 headless=False 登录
    for r in results:
        print(f"{r['time']} - {r['title']} - {r['link']}")
