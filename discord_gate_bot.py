import re
import asyncio
import datetime
import logging
import os
from discord.ext import tasks, commands
import discord
from dotenv import load_dotenv
from selenium import webdriver
from gate_scraper import scrape_announcements

# --- 加载 .env ---
load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_ANNOUNCEMENTS_CHANNEL_ID", 0))
KEYWORDS = [k.strip().lower() for k in os.getenv("KEYWORDS", "").split(",") if k.strip()]  # ← 这里放你想过滤的关键词
SENT_LINKS_FILE = os.getenv("DISCORD_SESSION_PATH")
CHECK_INTERVAL_MINUTES = 5
START_HOUR = 8
END_HOUR = 24

if not DISCORD_BOT_TOKEN or not DISCORD_CHANNEL_ID or not KEYWORDS:
    raise ValueError("❌ .env 配置不完整，请检查 DISCORD_BOT_TOKEN、DISCORD_CHANNEL_ID 和 KEYWORDS")

# --- 日志 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 去重缓存 ---
sent_links = set()


def normalize(s):
    # 小写
    s = s.lower()
    # 去除所有非字母数字
    s = re.sub(r'[^a-z0-9]', '', s)
    return s

def load_sent_links():
    if os.path.exists(SENT_LINKS_FILE):
        with open(SENT_LINKS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                sent_links.add(line.strip())
        logging.info(f"✅ 已加载本地缓存链接，共 {len(sent_links)} 条。")
    else:
        logging.info("⚠️ 本地缓存文件不存在，将创建新的。")


def save_sent_link(link):
    with open(SENT_LINKS_FILE, "a", encoding="utf-8") as f:
        f.write(link + "\n")


# --- 持久 Selenium 浏览器 ---
driver = None


def init_driver():
    global driver
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-images")
    options.add_argument("--blink-settings=imagesEnabled=false")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)
    logging.info("✅ ChromeDriver 启动成功。")

# --- Discord Bot ---
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    logging.info(f"🤖 Bot 已登录: {bot.user}")
    load_sent_links()
    init_driver()
    check_gate_announcements.start()

@tasks.loop(minutes=CHECK_INTERVAL_MINUTES)
async def check_gate_announcements():
    now = datetime.datetime.now()
    if START_HOUR <= now.hour < END_HOUR:
        logging.info(f"⏰ {now.strftime('%H:%M')} - 开始检查公告")
        try:
            results = scrape_announcements(driver)
        except Exception as e:
            logging.error(f"❌ 爬取 Gate 公告时出错: {e}")
            return

        channel = bot.get_channel(DISCORD_CHANNEL_ID)
        if channel is None:
            logging.error(f"❌ 未找到 Discord 频道 ID: {DISCORD_CHANNEL_ID}")
            return

        # for date, title, link in results:
        for item_dict in results:
            link = item_dict["link"]
            date = item_dict["time"]
            title = item_dict["title"]
            # print(f"DEBUG公告: {date} - {title} - {link}")
            if link in sent_links:
                continue
            # print(f"title: {title}")
            title_lower = title.lower()

            for keyword in KEYWORDS:
                if keyword in title_lower:
            # if "gate" in title_lower and "alpha" in title_lower:

                    print("✅ 匹配成功，准备发送到 Discord")
                    sent_links.add(link)
                    save_sent_link(link)
                    message = (
                        f"📢 **Gate 公告命中关键词！**\n\n"
                        f"**标题：** {title}\n"
                        f"**时间：** {date}\n"
                        f"**链接：** {link}"
                    )
                    try:
                        await channel.send(message)
                        logging.info(f"✅ 已发送到 Discord: {title}")
                    except Exception as e:
                        logging.error(f"❌ 发送到 Discord 时出错: {e}")
                    break
    else:
        logging.info(f"🛑 当前时间 {now.strftime('%H:%M')} 不在活跃时段（{START_HOUR}:00 - {END_HOUR}:00）")

@check_gate_announcements.before_loop
async def before_check():
    await bot.wait_until_ready()
    logging.info("🔄 Bot 已就绪，开始定时任务")

if __name__ == "__main__":
    bot.run(DISCORD_BOT_TOKEN)
