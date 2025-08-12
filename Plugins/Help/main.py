from ncatbot.plugin import BasePlugin
from ncatbot.core.message import BaseMessage
from ncatbot.core import MessageChain
from ncatbot.core import Image as BotImage
from ncatbot.utils import get_log
import os
import re
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
# ====================全局配置====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
URL = "https://user.swiro.top/"
FONT_PATH = os.path.join(BASE_DIR, "DingTalk JinBuTi.ttf")
OUTPUT_PATH = os.path.join(BASE_DIR, "output.png")
PANEL_PADDING = 40
CONTENT_FONT_SIZE = 18
CODE_FONT_SIZE = 16
LINE_SPACING = 15
PANEL_RADIUS = 15
PANEL_COLOR = (255, 255, 255, 220) 
TITLE_FONT_SIZE = 24
FOOTER_FONT_SIZE = 14
TITLE_TEXT = "指令列表 - 群机器人使用帮助"
FOOTER_TEXT = f"Copyright 2025 © Swiro - 帮助：内容爬取自{URL}"
TITLE_COLOR = (30, 30, 180)
FOOTER_COLOR = (100, 100, 100)
TITLE_SPACING = 20
FOOTER_SPACING = 15
CODE_STYLE = {
    'bg_color': (225, 225, 225, 225),
    'padding': (2, 6),
    'border_radius': 4,
    'font_size': CODE_FONT_SIZE
}
LOG = get_log("Help")  # 日志对象
class Help(BasePlugin):
    name = "Help"
    version = "1.0.0" 
    author = "SweelLong(Swiro)"
    description = "帮助指令查询插件"
    dependencies = {}
    async def on_load(self):
        """插件初始化"""
        self.register_user_func(
            "/help", 
            self.help, 
            prefix="/help", 
            description="帮助指令查询插件",
            usage="/help - 显示帮助信息",
            examples=["/help"],
            tags=["user"]
        )
        LOG.info(f"{self.name} 插件已加载，版本: {self.version}")

    async def help(self, msg: BaseMessage):
        soup = BeautifulSoup(requests.get(URL).content, "html.parser")
        content_lines = next((
            [line.strip() for line in str(section.select_one("p")).split('\n')[2:-2] if line.strip()]
            for section in soup.select(".rule-section")
            if section.select_one(".rule-title").get_text(strip=True) == "群机器人"
        ), ['未找到相关内容'])
        processed_lines = []
        for line in content_lines:
            processed_line = re.sub(r'<br\s*/?>', '\n', line)
            processed_line = processed_line.replace('⭐', '#')
            for sub_line in processed_line.split('\n'):
                if sub_line.strip():
                    processed_lines.append(sub_line.strip())
        content_lines = processed_lines
        parsed_lines = []
        for line in content_lines:
            parts = re.findall(r'(<code>.*?</code>|<span class="rule-note">.*?</span>|[^<]+)', line)
            parsed_line = []
            for part in parts:
                if not part: continue
                if part.startswith('<code>'):
                    parsed_line.append(('code', part[6:-7].strip()))
                elif part.startswith('<span class="rule-note">'):
                    parsed_line.append(('note', part[24:-7].strip()))
                else:
                    parsed_line.append(('text', part))
            parsed_lines.append(parsed_line)
        content_font = ImageFont.truetype(FONT_PATH, CONTENT_FONT_SIZE)
        code_font = ImageFont.truetype(FONT_PATH, CODE_STYLE['font_size'])
        title_font = ImageFont.truetype(FONT_PATH, TITLE_FONT_SIZE)
        footer_font = ImageFont.truetype(FONT_PATH, FOOTER_FONT_SIZE)
        # 计算图片尺寸
        temp_img = Image.new("RGBA", (1, 1))
        temp_draw = ImageDraw.Draw(temp_img)
        # 计算标题尺寸
        title_bbox = temp_draw.textbbox((0, 0), TITLE_TEXT, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        title_height = title_bbox[3] - title_bbox[1]
        # 计算版权信息尺寸
        footer_bbox = temp_draw.textbbox((0, 0), FOOTER_TEXT, font=footer_font)
        footer_width = footer_bbox[2] - footer_bbox[0]
        footer_height = footer_bbox[3] - footer_bbox[1]
        # 计算正文最大宽度和总高度
        max_width = 0
        total_height = 0
        for parsed_line in parsed_lines:
            line_width = 0
            max_height = 0
            for part_type, content in parsed_line:
                font = code_font if part_type == 'code' else content_font
                bbox = temp_draw.textbbox((0, 0), content, font=font)
                width = bbox[2]
                height = bbox[3] - bbox[1]
                if part_type == 'code':
                    width += CODE_STYLE['padding'][1] * 2
                    height += CODE_STYLE['padding'][0] * 2
                line_width += width
                max_height = max(max_height, height)
            max_width = max(max_width, line_width)
            total_height += max_height + LINE_SPACING
        # 计算总宽度和总高度
        total_width = max(max_width, title_width, footer_width) + 2 * PANEL_PADDING
        total_height = (2 * PANEL_PADDING + title_height + TITLE_SPACING + total_height + FOOTER_SPACING + footer_height)
        # 创建透明背景图片
        final_img = Image.new("RGBA", (total_width, total_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(final_img)
        # 绘制透明圆角面板
        draw.rounded_rectangle([(0, 0), (total_width, total_height)], PANEL_RADIUS, fill=PANEL_COLOR)
        # 绘制标题
        title_x = (total_width - title_width) // 2
        draw.text((title_x, PANEL_PADDING), TITLE_TEXT, font=title_font, fill=TITLE_COLOR)
        # 绘制正文
        x = PANEL_PADDING
        y = PANEL_PADDING + title_height + TITLE_SPACING
        for parsed_line in parsed_lines:
            current_x = x
            max_height = 0
            for part_type, content in parsed_line:
                if part_type == 'code':
                    # 绘制代码块
                    pad_y, pad_x = CODE_STYLE['padding']
                    bbox = draw.textbbox((0, 0), content, font=code_font)
                    text_width = bbox[2]
                    text_height = bbox[3] - bbox[1]
                    # 绘制代码背景
                    bg_x2 = current_x + text_width + pad_x * 2
                    bg_y2 = y + text_height + pad_y * 2
                    draw.rounded_rectangle(
                        [(current_x, y), (bg_x2, bg_y2)],
                        CODE_STYLE['border_radius'],
                        fill=CODE_STYLE['bg_color']
                    )
                    # 绘制代码文本
                    draw.text((current_x + pad_x, y + pad_y), content, font=code_font, fill=(0, 0, 0))
                    current_x = bg_x2
                    max_height = max(max_height, bg_y2 - y)
                else:
                    # 绘制普通文本或注释
                    color = (200, 30, 30) if part_type == 'note' else (0, 0, 0)
                    bbox = draw.textbbox((0, 0), content, font=content_font)
                    text_width = bbox[2]
                    text_height = bbox[3] - bbox[1]
                    draw.text((current_x, y), content, font=content_font, fill=color)
                    current_x += text_width
                    max_height = max(max_height, text_height)
            y += max_height + LINE_SPACING
        # 绘制版权信息
        footer_x = (total_width - footer_width) // 2
        draw.text((footer_x, y + FOOTER_SPACING), FOOTER_TEXT, font=footer_font, fill=FOOTER_COLOR)
        # 保存结果
        final_img.convert("RGB").save(OUTPUT_PATH, quality=95)
        LOG.info(f"图片已生成: {OUTPUT_PATH} ({total_width}x{total_height})")
        try:
            if hasattr(msg, "group_id"):
                await self.api.post_group_msg(msg.group_id, rtf=MessageChain(BotImage(OUTPUT_PATH)))
            else:
                await self.api.post_private_msg(msg.user_id, rtf=MessageChain(BotImage(OUTPUT_PATH)))
        except Exception as e:
            LOG.error(f"图片生成失败: {str(e)}")
            await msg.reply(text="成绩卡片生成失败，请稍后再试")