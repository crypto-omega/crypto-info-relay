# main.py
import os
import re
import asyncio
import logging
from dotenv import load_dotenv
from telethon import TelegramClient, events
import discord

# --- 日志设置 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# --- 加载环境变量 ---
load_dotenv()
logging.info("成功加载 .env 文件中的环境变量。")

# --- TELEGRAM 设置 (用户账户模式) ---
TELEGRAM_API_ID = os.getenv('TELEGRAM_API_ID')
TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH')
telegram_channel_ids_str = os.getenv('TELEGRAM_CHANNEL_IDS')

if not all([TELEGRAM_API_ID, TELEGRAM_API_HASH, telegram_channel_ids_str]):
    logging.error("TELEGRAM_API_ID, TELEGRAM_API_HASH 或 TELEGRAM_CHANNEL_IDS 缺失！请检查 .env 文件。")
    exit()

channels_input = [item.strip() for item in telegram_channel_ids_str.split(',')]
TELEGRAM_CHANNELS = []
for channel in channels_input:
    try:
        TELEGRAM_CHANNELS.append(int(channel))
    except ValueError:
        TELEGRAM_CHANNELS.append(channel)
logging.info(f"将要监控的 Telegram 频道: {TELEGRAM_CHANNELS}")


# --- DISCORD 设置 ---
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
DISCORD_CHANNEL_ID_STR = os.getenv('DISCORD_CHANNEL_ID')

if not all([DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID_STR]):
    logging.error("一个或多个 Discord 环境变量缺失！请检查 .env 文件。")
    exit()

try:
    DISCORD_CHANNEL_ID = int(DISCORD_CHANNEL_ID_STR)
    logging.info(f"将要转发到的 Discord 频道 ID: {DISCORD_CHANNEL_ID}")
except ValueError:
    logging.error("DISCORD_CHANNEL_ID 格式错误。请确保它是一个纯数字。")
    exit()

DISCORD_AIRDROP_CHANNEL_ID_STR = os.getenv('DISCORD_AIRDROP_CHANNEL_ID')

if not DISCORD_AIRDROP_CHANNEL_ID_STR:
    logging.warning("DISCORD_AIRDROP_CHANNEL_ID 未设置，空投频道转发功能将被禁用。")
    DISCORD_AIRDROP_CHANNEL_ID = None
else:
    try:
        DISCORD_AIRDROP_CHANNEL_ID = int(DISCORD_AIRDROP_CHANNEL_ID_STR)
        logging.info(f"空投专用转发频道 ID: {DISCORD_AIRDROP_CHANNEL_ID}")
    except ValueError:
        logging.error("DISCORD_AIRDROP_CHANNEL_ID 格式错误。")
        DISCORD_AIRDROP_CHANNEL_ID = None

DISCORD_TRADE_CHANNEL_ID_STR = os.getenv('DISCORD_TRADE_CHANNEL_ID')

if not DISCORD_TRADE_CHANNEL_ID_STR:
    logging.warning("DISCORD_AIRDROP_CHANNEL_ID 未设置，空投频道转发功能将被禁用。")
    DISCORD_TRADE_CHANNEL_ID = None
else:
    try:
        DISCORD_TRADE_CHANNEL_ID = int(DISCORD_TRADE_CHANNEL_ID_STR)
        logging.info(f"合约专用转发频道 ID: {DISCORD_TRADE_CHANNEL_ID}")
    except ValueError:
        logging.error("DISCORD_TRADE_CHANNEL_ID 格式错误。")
        DISCORD_TRADE_CHANNEL_ID = None



# --- 会话文件路径设置 (Session Path Setup) ---
SESSION_NAME = 'user_session'
# 从 .env 文件读取 SESSION_PATH，如果未设置，则默认为当前目录 '.'
SESSION_PATH = os.getenv('SESSION_PATH', '.') 
full_session_path = os.path.join(SESSION_PATH, SESSION_NAME)

# 确保会话文件所在的目录存在
session_directory = os.path.dirname(full_session_path)
if session_directory:
    os.makedirs(session_directory, exist_ok=True)
    logging.info(f"Telegram 会话文件将保存在: {os.path.abspath(full_session_path)}.session")


# --- 客户端初始化 ---
# 将完整的会话路径传递给 TelegramClient
telegram_client = TelegramClient(full_session_path, TELEGRAM_API_ID, TELEGRAM_API_HASH)
intents = discord.Intents.default()
intents.message_content = True 
discord_client = discord.Client(intents=intents)


# --- 重点字段 ----
AIRDROP_FILTER_KEYWORDS = ["空投", "交易挑战", "瓜分"]
PATTERN = r"上线\w+U本位永续合约"


# --- 把 Markdown 链接转为裸链接 ----
def convert_markdown_links_to_plain_urls(text: str) -> str:
    # 将 [文字](链接) 替换为 文字 + 空格 + 链接. 如果文字和链接相同，则只保留链接.
    def replace_link(match):
        text, url = match.groups()
        if text == url:
            return url
        return f'{text} {url}'

    pattern = r'\[([^\]]+)\]\((https?://[^\)]+)\)'
    return re.sub(pattern, replace_link, text)

# --- 核心处理函数 ---
@telegram_client.on(events.NewMessage(chats=TELEGRAM_CHANNELS))
async def handle_new_telegram_message(event):
    logging.info(f"--- [事件触发] 从 Telegram 频道: {event.chat.title if event.chat else event.chat_id} 收到新消息 ---")

    try:
        discord_channel = discord_client.get_channel(DISCORD_CHANNEL_ID)
        airdrop_channel = discord_client.get_channel(DISCORD_AIRDROP_CHANNEL_ID)
        trade_channel = discord_client.get_channel(DISCORD_TRADE_CHANNEL_ID)
        if not discord_channel:
            logging.error(f"[错误] 未能在 Discord 中找到 ID 为 {DISCORD_CHANNEL_ID} 的频道。")
            return

        channel_title = event.chat.title if event.chat else f"ID: {event.chat_id}"
        logging.info(f"消息来源频道: '{channel_title}'")

        forward_header = f"**【消息来源: {channel_title}】**\n\n"
        message_text = event.message.text
        
        if message_text:
            cleaned_message_text = convert_markdown_links_to_plain_urls(message_text)
            full_message = forward_header + cleaned_message_text
            logging.info("检测到文本消息，准备转发...")
            await discord_channel.send(full_message)
            logging.info("[成功] 文本消息已成功转发到 Discord。")
            # 检查是否需要转发到空投频道
            if DISCORD_AIRDROP_CHANNEL_ID and any(
                    keyword.lower() in cleaned_message_text.lower() for keyword in AIRDROP_FILTER_KEYWORDS):
                logging.info(f"[匹配] 检测到关键词，额外转发到空投频道 ({DISCORD_AIRDROP_CHANNEL_ID})")
                if airdrop_channel:
                    await airdrop_channel.send(full_message)
                else:
                    logging.error(f"[错误] 未能在 Discord 中找到 ID 为 {DISCORD_AIRDROP_CHANNEL_ID} 的空投频道。")

            # 检测是否需要发送到合约频道
            if DISCORD_TRADE_CHANNEL_ID and re.search(PATTERN, cleaned_message_text):
                logging.info("[匹配] 检测到上线U本位永续合约消息，准备额外转发到 C 频道")
                if trade_channel:
                    # processed = process_msg(cleaned_message_text)
                    processed_message = forward_header + cleaned_message_text
                    await trade_channel.send(processed_message)
                else:
                    logging.error(f"[错误] 未能在 Discord 中找到 ID 为 {DISCORD_TRADE_CHANNEL_ID} 的频道。")
                

        
        if event.message.media:
            logging.info("检测到媒体文件，准备处理...")
            if not message_text:
                await discord_channel.send(forward_header)

            logging.info("开始从 Telegram 下载媒体文件...")
            file_path = await event.message.download_media()
            logging.info(f"媒体文件已成功下载到: {file_path}")

            try:
                logging.info("开始向 Discord 上传文件...")
                with open(file_path, 'rb') as f:
                    discord_file = discord.File(f)
                    await discord_channel.send(file=discord_file)
                logging.info("[成功] 媒体文件已成功转发到 Discord。")
            except discord.errors.HTTPException as e:
                if e.status == 413:
                    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                    logging.error(f"[错误] 文件转发失败！文件大小 ({file_size_mb:.2f} MB) 可能超过了 Discord 的限制。")
                    await discord_channel.send(f"**【转发失败】**\n来自 **{channel_title}** 的文件过大，无法上传。")
                else:
                    logging.error(f"[错误] 上传文件到 Discord 时发生 HTTP 错误: {e}")
            finally:
                logging.info(f"清理本地临时文件: {file_path}")
                os.remove(file_path)

    except Exception as e:
        logging.exception(f"[严重错误] 在处理消息转发时发生未知异常: {e}")


@discord_client.event
async def on_ready():
    logging.info(f"--- Discord Bot 已准备就绪 (Logged in as {discord_client.user}) ---")
    logging.info("机器人现在可以转发消息了。")

async def main():
    discord_task = asyncio.create_task(discord_client.start(DISCORD_BOT_TOKEN))
    
    await telegram_client.start()
    logging.info("--- Telegram 用户端已成功登录 ---")
    logging.info(f"监控 {len(TELEGRAM_CHANNELS)} 个 Telegram 频道。")
    
    await asyncio.gather(discord_task, telegram_client.run_until_disconnected())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("程序被手动停止。")

