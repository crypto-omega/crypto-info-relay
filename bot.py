# main.py
import os
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


# --- 核心处理函数 ---
@telegram_client.on(events.NewMessage(chats=TELEGRAM_CHANNELS))
async def handle_new_telegram_message(event):
    logging.info(f"--- [事件触发] 从 Telegram 频道: {event.chat.title if event.chat else event.chat_id} 收到新消息 ---")

    try:
        discord_channel = discord_client.get_channel(DISCORD_CHANNEL_ID)
        if not discord_channel:
            logging.error(f"[错误] 未能在 Discord 中找到 ID 为 {DISCORD_CHANNEL_ID} 的频道。")
            return

        channel_title = event.chat.title if event.chat else f"ID: {event.chat_id}"
        logging.info(f"消息来源频道: '{channel_title}'")

        forward_header = f"**【消息来源: {channel_title}】**\n\n"
        message_text = event.message.text
        
        if message_text:
            full_message = forward_header + message_text
            logging.info("检测到文本消息，准备转发...")
            await discord_channel.send(full_message)
            logging.info("[成功] 文本消息已成功转发到 Discord。")
        
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

