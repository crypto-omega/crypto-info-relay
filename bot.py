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
import aiohttp
from bs4 import BeautifulSoup
import json

# --- 加载环境变量 ---
load_dotenv()

# --- 日志设置 ---
# 从环境变量读取调试模式设置
DEBUG_MODE = os.getenv('DEBUG_MODE', 'false').lower() == 'true'
MAX_LEFT_ID = int(os.getenv('MAX_LEFT_ID', '4'))
log_level = logging.DEBUG if DEBUG_MODE else logging.INFO

logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logging.info(f"日志级别设置为: {'DEBUG' if DEBUG_MODE else 'INFO'}")
logging.info("成功加载 .env 文件中的环境变量。")

# --- TELEGRAM 设置 (用户账户模式) ---
TELEGRAM_API_ID = os.getenv('TELEGRAM_API_ID')
TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH')

if not all([TELEGRAM_API_ID, TELEGRAM_API_HASH]):
    logging.error("TELEGRAM_API_ID 或 TELEGRAM_API_HASH 缺失！请检查 .env 文件。")
    exit()

# --- DISCORD 设置 ---
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')

if not all([DISCORD_BOT_TOKEN]):
    logging.error("Discord Bot Token 缺失！请检查 .env 文件。")
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

# --- 把 Markdown 链接转为裸链接 ----
def convert_markdown_links_to_plain_urls(text: str) -> str:
    """
    将 [文字](链接) 替换为链接，并去除链接中的所有查询参数.

    Args:
        text: 包含Markdown链接的输入字符串.

    Returns:
        转换并清理了链接的字符串.
    """
    def replace_link(match: re.Match) -> str:
        """
        根据匹配对象决定替换逻辑.
        """
        link_url = match.group(2)

        # 1. 去除链接中的参数 (? 以及之后的所有内容)
        clean_url = link_url.split('?')[0]
        return clean_url

    # 使用正则表达式查找所有 [文字](链接) 格式的链接
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)', replace_link, text)

# --- 数据模型 ---
@dataclass_json
@dataclass
class Source:
    type: str
    channel_ids: Optional[List[Union[int, str]]] = None
    url_pattern: Optional[str] = None
    start_id: Optional[int] = None
    check_interval: Optional[int] = None

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

def update_gate_io_start_id(config_path: str, rule_name: str, new_start_id: int):
    """更新config.yaml中Gate.io规则的start_id"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_dict = yaml.safe_load(f)
        
        # 查找并更新对应规则的start_id
        for rule in config_dict.get('rules', []):
            if rule.get('name') == rule_name and rule.get('source', {}).get('type') == 'gate_io':
                old_start_id = rule['source'].get('start_id', 0)
                rule['source']['start_id'] = new_start_id
                logging.info(f"更新规则 '{rule_name}' 的start_id: {old_start_id} -> {new_start_id}")
                
                # 写回文件
                with open(config_path, 'w', encoding='utf-8') as f:
                    yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True, indent=2)
                break
        else:
            logging.warning(f"未找到名为 '{rule_name}' 的Gate.io规则")
            
    except Exception as e:
        logging.error(f"更新start_id时发生错误: {e}")

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
gate_io_last_checked: dict = {}  # Track last checked announcement ID for each rule

# --- 消息处理函数 ---
async def forward_to_discord(message_text: str, channel_id: int, source_title: str) -> None:
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

    logging.info(f"收到来自 {source_title} 的新消息")

    try:
        for rule in CONFIG.rules:
            if rule.source.type != "telegram" or not rule.source.channel_ids:
                continue
            if event.chat_id not in rule.source.channel_ids:
                continue

            destinations = get_matching_destinations(message_text or "", rule)
            for dest in destinations:
                if dest.type == "discord" and dest.channel_id:
                    await forward_to_discord(message_text, dest.channel_id, source_title)
                elif dest.type == "telegram" and dest.group_id:
                    await forward_to_telegram(event.message, dest.group_id)

    finally:
        pass

# --- Gate.io 公告处理函数 ---
async def fetch_gate_io_announcement(session: aiohttp.ClientSession, announcement_id: int) -> Optional[dict]:
    """获取单个Gate.io公告"""
    url = f"https://www.gate.com/zh/announcements/article/{announcement_id}"
    logging.debug(f"正在获取Gate.io公告 {announcement_id}: {url}")
    
    try:
        async with session.get(url) as response:
            logging.debug(f"Gate.io公告 {announcement_id} 响应状态: {response.status}")
            
            if response.status == 200:
                html = await response.text()
                logging.debug(f"成功获取公告 {announcement_id} 的HTML内容，长度: {len(html)}")
                
                soup = BeautifulSoup(html, 'html.parser')
                title_element = soup.find('h3')
                if title_element:
                    title = title_element.get_text(strip=True)
                    logging.debug(f"解析到公告 {announcement_id} 标题: {title}")
                    return {
                        'id': announcement_id,
                        'title': title,
                        'url': url
                    }
                else:
                    logging.warning(f"未找到公告 {announcement_id} 的标题元素")
                    logging.debug(f"公告 {announcement_id} HTML片段: {html[:500]}...")
                    return None
            elif response.status == 404:
                logging.debug(f"公告 {announcement_id} 不存在 (404)")
                return None
            else:
                logging.warning(f"获取公告 {announcement_id} 失败，状态码: {response.status}")
                return None
    except Exception as e:
        logging.error(f"获取Gate.io公告 {announcement_id} 时发生错误: {e}")
        logging.debug(f"公告 {announcement_id} 异常详情", exc_info=True)
        return None

async def check_gate_io_announcements(rule: Rule) -> List[dict]:
    """检查Gate.io新公告"""
    if rule.source.type != "gate_io":
        logging.debug(f"规则 {rule.name} 不是Gate.io类型，跳过")
        return []
    
    rule_id = rule.name
    current_max_id = gate_io_last_checked.get(rule_id, rule.source.start_id or 46450)
    new_announcements = []
    
    logging.info(f"开始检查Gate.io公告 - 规则: {rule_id}, 当前最大ID: {current_max_id}")
    
    async with aiohttp.ClientSession() as session:
        # 检查从当前最大ID+1到当前最大ID+10的公告
        check_range_start = current_max_id + 1
        check_range_end = current_max_id + 11
        logging.debug(f"检查ID范围: {check_range_start} 到 {check_range_end - 1}")
        
        consecutive_missing = 0  # 连续缺失的公告数量
        
        for announcement_id in range(check_range_start, check_range_end):
            logging.debug(f"检查公告ID: {announcement_id}")
            announcement = await fetch_gate_io_announcement(session, announcement_id)
            if announcement:
                new_announcements.append(announcement)
                gate_io_last_checked[rule_id] = announcement_id
                logging.info(f"发现新公告 {announcement_id}: {announcement['title']}")
                consecutive_missing = 0  # 重置连续缺失计数
            else:
                consecutive_missing += 1
                logging.debug(f"公告ID {announcement_id} 不存在，连续缺失: {consecutive_missing}/{MAX_LEFT_ID}")
                if consecutive_missing >= MAX_LEFT_ID:
                    logging.debug(f"连续缺失 {MAX_LEFT_ID} 个公告，停止检查更高ID")
                    break
    
    if new_announcements:
        logging.info(f"规则 {rule_id} 找到 {len(new_announcements)} 个新公告")
    else:
        logging.debug(f"规则 {rule_id} 未找到新公告")
    
    return new_announcements

async def handle_gate_io_announcement(announcement: dict, rule: Rule) -> None:
    """处理Gate.io公告"""
    title = announcement['title']
    url = announcement['url']
    announcement_id = announcement['id']
    source_title = "Gate.io公告"
    
    message_text = f"**{title}**\n\n{url}"
    
    logging.info(f"处理Gate.io公告 {announcement_id}: {title}")
    logging.debug(f"公告URL: {url}")
    
    # 检查是否匹配过滤器
    destinations = get_matching_destinations(title, rule)
    logging.debug(f"规则 {rule.name} 匹配到 {len(destinations)} 个目标")
    
    if not destinations:
        logging.debug(f"公告 {announcement_id} 不匹配任何过滤器，跳过转发")
        return
    
    for i, dest in enumerate(destinations):
        logging.debug(f"处理目标 {i+1}/{len(destinations)}: {dest.type}")
        
        if dest.type == "discord" and dest.channel_id:
            logging.debug(f"转发到Discord频道 {dest.channel_id}")
            await forward_to_discord(message_text, dest.channel_id, source_title)
        elif dest.type == "telegram" and dest.group_id:
            # 对于Telegram，我们需要发送文本消息
            logging.debug(f"转发到Telegram群组 {dest.group_id}")
            try:
                await telegram_client.send_message(dest.group_id, f"【{source_title}】\n\n{message_text}")
                logging.info(f"[成功] Gate.io公告 {announcement_id} 已转发到 Telegram 群组 {dest.group_id}")
            except Exception as e:
                logging.error(f"[错误] 转发Gate.io公告 {announcement_id} 到 Telegram 群组 {dest.group_id} 时发生错误: {e}")
                logging.debug(f"Telegram转发异常详情", exc_info=True)
        else:
            logging.warning(f"无效的目标配置: {dest}")

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

async def gate_io_monitor_task():
    """Gate.io公告监控任务"""
    logging.info("启动Gate.io公告监控任务")
    
    while True:
        try:
            if CONFIG:
                gate_io_rules = [rule for rule in CONFIG.rules if rule.source.type == "gate_io"]
                logging.debug(f"找到 {len(gate_io_rules)} 个Gate.io规则")
                
                if gate_io_rules:
                    for rule in gate_io_rules:
                        logging.debug(f"执行Gate.io规则: {rule.name}")
                        new_announcements = await check_gate_io_announcements(rule)
                        
                        for announcement in new_announcements:
                            await handle_gate_io_announcement(announcement, rule)
                        
                        # 如果有新公告，更新配置文件中的start_id
                        if new_announcements:
                            rule_id = rule.name
                            latest_id = gate_io_last_checked.get(rule_id)
                            if latest_id:
                                update_gate_io_start_id('config.yaml', rule.name, latest_id)
                                logging.info(f"已更新配置文件中规则 '{rule.name}' 的start_id为: {latest_id}")
                    
                    # 使用第一个Gate.io规则的检查间隔，或默认60秒
                    interval = gate_io_rules[0].source.check_interval or 60
                    logging.debug(f"Gate.io监控任务等待 {interval} 秒后继续")
                    await asyncio.sleep(interval)
                else:
                    logging.debug("没有Gate.io规则，等待60秒")
                    await asyncio.sleep(60)  # 没有Gate.io规则时，等待60秒
            else:
                logging.warning("配置未加载，等待10秒后重试")
                await asyncio.sleep(10)  # 如果配置未加载，等待10秒后重试
        except Exception as e:
            logging.error(f"Gate.io监控任务发生错误: {e}")
            logging.debug("Gate.io监控任务异常详情", exc_info=True)
            await asyncio.sleep(30)  # 出错后等待30秒再重试

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

        # 启动Gate.io监控任务
        gate_io_task = asyncio.create_task(gate_io_monitor_task())
        
        # 运行直到断开连接
        await asyncio.gather(
            discord_task,
            telegram_client.run_until_disconnected(),
            gate_io_task
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