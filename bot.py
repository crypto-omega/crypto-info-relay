# main.py
import os
import re
import asyncio
import logging
from dataclasses import dataclass
from typing import List, Optional, Union
from dotenv import load_dotenv
import yaml
from telethon import TelegramClient, events
import discord
from urllib.parse import urlparse
from dataclasses_json import dataclass_json

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

if not all([TELEGRAM_API_ID, TELEGRAM_API_HASH]):
    logging.error("TELEGRAM_API_ID 或 TELEGRAM_API_HASH 缺失！请检查 .env 文件。")
    exit()

DESTINATION_TELEGRAM_GROUP_ID_STR = os.getenv('DESTINATION_TELEGRAM_GROUP_ID')
DESTINATION_TELEGRAM_GROUP_ID = None
if DESTINATION_TELEGRAM_GROUP_ID_STR:
    try:
        DESTINATION_TELEGRAM_GROUP_ID = int(DESTINATION_TELEGRAM_GROUP_ID_STR)
        logging.info(f"将要转发到的目标 Telegram 群组 ID: {DESTINATION_TELEGRAM_GROUP_ID}")
    except ValueError:
        logging.error("DESTINATION_TELEGRAM_GROUP_ID 格式错误。请确保它是一个纯数字。")
        DESTINATION_TELEGRAM_GROUP_ID = None
else:
    logging.warning("DESTINATION_TELEGRAM_GROUP_ID 未设置，Telegram 群组转发功能将被禁用。")


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
PATTERN = r"上线.*U本位永续合约"


# --- 把 Markdown 链接转为裸链接 ----
def convert_markdown_links_to_plain_urls(text: str) -> str:
    """
    将 [文字](链接) 替换为 文字 + 空格 + 链接，并去除链接中的所有查询参数.
    如果去除参数后的链接与文字相同, 则只保留链接.

    Args:
        text: 包含Markdown链接的输入字符串.

    Returns:
        转换并清理了链接的字符串.
    """
    def replace_link(match: re.Match) -> str:
        """
        根据匹配对象决定替换逻辑.
        """
        link_text = match.group(1)
        link_url = match.group(2)

        # 1. 去除链接中的参数 (? 以及之后的所有内容)
        clean_url = link_url.split('?')[0]

        # 2. 如果文字和清理后的链接相同, 则只返回清理后的链接
        if link_text == clean_url:
            return clean_url
        # 否则, 返回 "文字 清理后的链接"
        else:
            return f'{link_text} {clean_url}'

    # 使用正则表达式查找所有 [文字](链接) 格式的链接
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)', replace_link, text)

# --- 数据模型 ---
@dataclass_json
@dataclass
class Source:
    type: str
    channel_ids: List[Union[int, str]]

@dataclass_json
@dataclass
class Filter:
    type: str
    words: Optional[List[str]] = None
    pattern: Optional[str] = None

@dataclass_json
@dataclass
class Destination:
    type: str
    channel_id: Optional[int] = None
    group_id: Optional[int] = None

@dataclass_json
@dataclass
class Rule:
    name: str
    source: Source
    filters: List[Filter]
    destinations: List[Destination]

@dataclass_json
@dataclass
class Config:
    rules: List[Rule]

def load_config(config_path: str) -> Config:
    """从YAML文件加载配置"""
    with open(config_path, 'r', encoding='utf-8') as f:
        config_dict = yaml.safe_load(f)
    return Config.from_dict(config_dict)

def check_message_matches_filter(message_text: str, filter_config: Filter) -> bool:
    """检查消息是否匹配过滤器规则"""
    if filter_config.type == "ALL":
        return True
    elif filter_config.type == "keywords" and filter_config.words:
        return any(word.lower() in message_text.lower() for word in filter_config.words)
    elif filter_config.type == "regex" and filter_config.pattern:
        return bool(re.search(filter_config.pattern, message_text))
    return False

def get_matching_destinations(message_text: str, rule: Rule) -> List[Destination]:
    """获取匹配规则的目标渠道列表"""
    for filter_config in rule.filters:
        if check_message_matches_filter(message_text, filter_config):
            return rule.destinations
    return []


# --- 全局变量 ---
CONFIG: Optional[Config] = None
discord_client: Optional[discord.Client] = None
telegram_client: Optional[TelegramClient] = None

# --- 消息处理函数 ---
async def forward_to_discord(message_text: str, media_path: Optional[str], 
                           channel_id: int, source_title: str) -> None:
    """转发消息到Discord"""
    channel = discord_client.get_channel(channel_id)
    if not channel:
        logging.error(f"[错误] 未能在 Discord 中找到 ID 为 {channel_id} 的频道。")
        return

    forward_header = f"**【消息来源: {source_title}】**\n\n"
    
    if message_text:
        full_message = forward_header + convert_markdown_links_to_plain_urls(message_text)
        await channel.send(full_message)
        logging.info(f"[成功] 文本消息已转发到 Discord 频道 {channel_id}")

    if media_path:
        if not message_text:
            await channel.send(forward_header)
        try:
            with open(media_path, 'rb') as f:
                discord_file = discord.File(f)
                await channel.send(file=discord_file)
            logging.info(f"[成功] 媒体文件已转发到 Discord 频道 {channel_id}")
        except discord.errors.HTTPException as e:
            if e.status == 413:
                file_size_mb = os.path.getsize(media_path) / (1024 * 1024)
                logging.error(f"[错误] 文件转发失败！文件大小 ({file_size_mb:.2f} MB) 超过限制。")
                await channel.send(f"**【转发失败】**\n来自 **{source_title}** 的文件过大，无法上传。")
            else:
                logging.error(f"[错误] 上传文件到 Discord 时发生 HTTP 错误: {e}")

async def forward_to_telegram(message: events.NewMessage.Event, group_id: int) -> None:
    """转发消息到Telegram群组"""
    try:
        await telegram_client.forward_messages(group_id, message)
        logging.info(f"[成功] 消息已转发到 Telegram 群组 {group_id}")
    except Exception as e:
        logging.error(f"[错误] 转发消息到 Telegram 群组 {group_id} 时发生错误: {e}")

async def handle_new_telegram_message(event: events.NewMessage.Event) -> None:
    """处理新的Telegram消息"""
    if not CONFIG:
        logging.error("配置未加载，无法处理消息")
        return

    # 更健壮地获取 source_title
    if event.chat:
        if hasattr(event.chat, "title") and event.chat.title:
            source_title = event.chat.title
        elif hasattr(event.chat, "username") and event.chat.username:
            source_title = event.chat.username
        elif hasattr(event.chat, "first_name") or hasattr(event.chat, "last_name"):
            source_title = f"{getattr(event.chat, 'first_name', '')} {getattr(event.chat, 'last_name', '')}".strip()
        else:
            source_title = f"ID: {event.chat_id}"
    else:
        source_title = f"ID: {event.chat_id}"
    message_text = event.message.text
    media_path = None

    logging.info(f"收到来自 {source_title} 的新消息")

    if event.message.media:
        media_path = await event.message.download_media()
        logging.info(f"媒体文件已下载到: {media_path}")

    try:
        for rule in CONFIG.rules:
            if event.chat_id not in rule.source.channel_ids:
                continue

            destinations = get_matching_destinations(message_text or "", rule)
            for dest in destinations:
                if dest.type == "discord" and dest.channel_id:
                    await forward_to_discord(message_text, media_path, 
                                          dest.channel_id, source_title)
                elif dest.type == "telegram" and dest.group_id:
                    await forward_to_telegram(event.message, dest.group_id)

    finally:
        if media_path and os.path.exists(media_path):
            os.remove(media_path)
            logging.info(f"清理临时文件: {media_path}")

# --- 初始化函数 ---
async def initialize_clients():
    """初始化 Telegram 和 Discord 客户端"""
    global telegram_client, discord_client, CONFIG

    # 加载配置
    try:
        CONFIG = load_config('config.yaml')
        logging.info("成功加载配置文件")
    except Exception as e:
        logging.error(f"加载配置文件失败: {e}")
        return False

    # 初始化 Discord 客户端
    intents = discord.Intents.default()
    intents.message_content = True
    discord_client = discord.Client(intents=intents)

    # 初始化 Telegram 客户端
    SESSION_NAME = 'user_session'
    SESSION_PATH = os.getenv('SESSION_PATH', '.')
    full_session_path = os.path.join(SESSION_PATH, SESSION_NAME)

    telegram_client = TelegramClient(
        full_session_path,
        int(os.getenv('TELEGRAM_API_ID')),
        os.getenv('TELEGRAM_API_HASH')
    )

    # 设置事件处理器
    telegram_client.add_event_handler(
        handle_new_telegram_message,
        events.NewMessage()
    )

    @discord_client.event
    async def on_ready():
        logging.info(f"Discord Bot 已登录为 {discord_client.user}")

    return True

async def main():
    """主程序入口"""
    # 加载环境变量
    load_dotenv()

    # 检查必要的环境变量
    required_env_vars = ['TELEGRAM_API_ID', 'TELEGRAM_API_HASH', 'DISCORD_BOT_TOKEN']
    if not all(os.getenv(var) for var in required_env_vars):
        logging.error("缺少必要的环境变量，请检查 .env 文件")
        return

    # 初始化客户端
    if not await initialize_clients():
        return

    try:
        # 启动客户端
        discord_task = asyncio.create_task(
            discord_client.start(os.getenv('DISCORD_BOT_TOKEN'))
        )
        
        await telegram_client.start()
        logging.info("Telegram 客户端已登录")
        
        # 预加载对话列表
        await telegram_client.get_dialogs()
        logging.info("Telegram 对话列表已加载")

        # 运行直到断开连接
        await asyncio.gather(
            discord_task,
            telegram_client.run_until_disconnected()
        )
    except Exception as e:
        logging.error(f"运行时发生错误: {e}")
    finally:
        # 清理资源
        if telegram_client and telegram_client.is_connected():
            await telegram_client.disconnect()
        if discord_client and not discord_client.is_closed():
            await discord_client.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("程序被手动停止。")
    except Exception as e:
        logging.error(f"程序异常退出: {e}")