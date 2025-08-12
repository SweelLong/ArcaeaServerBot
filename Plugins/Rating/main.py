import datetime
import sqlite3
import os
import io
import re
import math
import asyncio
import glob  # 新增：用于查找图片文件
from typing import List, Tuple, Dict, Optional
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import ncatbot
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import BaseMessage
from ncatbot.utils import get_log

LOG = get_log("Rating")
bot = CompatibleEnrollment

# 路径配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(BASE_DIR)))
# 数据库路径（根据实际环境调整）
DATABASE_PATH = os.path.join(PARENT_DIR, "ArkanaServer\\database\\arcaea_database.db")
# 曲绘来源路径列表（优先级从高到低）
ILLUSTRATION_PATH = [
    os.path.join(PARENT_DIR, "ArkanaServer\\database\\songs\\"),  # 曲绘来源路径1：服务器文件夹
    os.path.join(PARENT_DIR, "ArkanaBundler\\assets\\songs\\")     # 曲绘来源路径2：热更新包文件夹
]
# 输出图片路径
OUTPUT_PATH = os.path.join(BASE_DIR, "output.png")


class Rating(BasePlugin):
    name = "Rating"
    version = "1.0.0"
    author = "08NX."
    description = "曲目定数查询插件，支持查询指定定数的所有曲目"
    dependencies = {}

    async def handle_rating_command(self, msg: BaseMessage):
        """处理定数查询命令"""
        # 解析命令参数
        raw_msg = msg.raw_message.strip()
        # 提取定数参数（命令格式：/rating [定数]）
        match = re.match(r"^/rating\s+(.+)$", raw_msg)
        if not match:
            return await msg.reply("命令格式错误！正确格式：/rating [定数，如9.5]")
        
        rating_arg = match.group(1).strip()
        
        # 验证输入格式
        if not re.match(r"^\d{1,2}(\.\d)?$", rating_arg):
            return await msg.reply("输入的定数格式有误哦！请输入正确的定数（如9.5）")
        
        # 转换为浮点数和数据库整数格式
        try:
            rating_float = float(rating_arg)
            rating_int = int(rating_float * 10)
        except ValueError:
            return await msg.reply("定数转换失败，请检查输入")
        
        # 检查数据库文件是否存在
        if not os.path.exists(DATABASE_PATH):
            return await msg.reply(f"数据库文件不存在，请检查路径: {DATABASE_PATH}")
        
        # 执行查询并生成图片
        try:
            # 异步执行数据库查询和图片生成
            loop = asyncio.get_running_loop()
            records = await loop.run_in_executor(None, self.query_database, rating_int)
            
            if not records:
                return await msg.reply(f"未找到定数为 {rating_float:.1f} 的谱面")
            
            # 生成图片
            image = await loop.run_in_executor(None, self.create_image, records, rating_float)
            
            image.save(OUTPUT_PATH, format='PNG')
            
            # 构造回复消息
            reply_msg = ncatbot.core.MessageChain()
            reply_msg += ncatbot.core.Image(OUTPUT_PATH)
            if hasattr(msg, 'group_id'):
                return await msg.api.post_group_msg(group_id=msg.group_id, rtf=reply_msg)
            else:
                return await msg.api.post_private_msg(user_id=msg.user_id, rtf=reply_msg)

        except Exception as e:
            LOG.error(f"处理定数查询时出错: {str(e)}")
            return await msg.reply(f"查询失败: {str(e)}")

    def query_database(self, rating_int: int) -> List[Tuple]:
        """查询数据库获取匹配的谱面记录"""
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        try:
            # 查询所有符合定数要求的谱面（包含不同难度）
            cursor.execute("""
            SELECT song_id, 
                   name,
                   'ftr' as difficulty
            FROM chart
            WHERE rating_ftr = ?
            UNION ALL
            SELECT song_id, 
                   name,
                   'byn' as difficulty
            FROM chart
            WHERE rating_byn = ?
            UNION ALL
            SELECT song_id, 
                   name,
                   'etr' as difficulty
            FROM chart
            WHERE rating_etr = ?
            """, (rating_int, rating_int, rating_int))
            
            records = cursor.fetchall()
            return records
            
        except sqlite3.OperationalError as e:
            # 兼容没有name字段的数据库结构
            if "no such column: name" in str(e):
                cursor.execute("""
                SELECT song_id, 
                       song_id as name,
                       'ftr' as difficulty
                FROM chart
                WHERE rating_ftr = ?
                UNION ALL
                SELECT song_id, 
                       song_id as name,
                       'byn' as difficulty
                FROM chart
                WHERE rating_byn = ?
                UNION ALL
                SELECT song_id, 
                       song_id as name,
                       'etr' as difficulty
                FROM chart
                WHERE rating_etr = ?
                """, (rating_int, rating_int, rating_int))
                
                return cursor.fetchall()
            else:
                raise
        finally:
            conn.close()

    def get_text_width(self, draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
        """获取文本宽度（兼容不同Pillow版本）"""
        try:
            return draw.textlength(text, font=font)
        except AttributeError:
            return draw.textsize(text, font=font)[0]

    def truncate_text(self, draw: ImageDraw.ImageDraw, text: str, max_width: int, font: ImageFont.FreeTypeFont) -> str:
        """截断文本以适应指定宽度（单行）"""
        if not text:
            return ""
        
        text_width = self.get_text_width(draw, text, font)
        if text_width <= max_width:
            return text
        
        # 为省略号预留空间
        ellipsis = "..."
        ellipsis_width = self.get_text_width(draw, ellipsis, font)
        max_text_width = max_width - ellipsis_width
        
        # 逐步截断文本
        truncated = text
        while truncated and self.get_text_width(draw, truncated, font) > max_text_width:
            truncated = truncated[:-1]
        
        return truncated + ellipsis if truncated else ellipsis

    def format_song_name(self, name: str) -> str:
        """格式化曲目名称（移除特殊符号）"""
        if not name:
            return "Unknown Song"
        
        # 移除特殊符号
        name = name.replace('"', '').replace("'", "")
        
        # 简化长名称
        if len(name) > 30:
            simplified = re.sub(r'\([^)]*\)', '', name)
            simplified = re.sub(r'\[[^\]]*\]', '', simplified)
            simplified = simplified.strip()
            
            if simplified and len(simplified) < len(name):
                return simplified
        
        return name

    def create_image(self, records: List[Tuple], rating: float) -> Image.Image:
        """创建定数查询结果图片"""
        # 图片基础参数
        WIDTH = 950
        ITEM_SIZE = 200  # 曲绘大小
        TITLE_HEIGHT = 40  # 曲目标题区域高度
        SHADOW_SIZE = 10  # 阴影大小
        ITEM_HEIGHT = ITEM_SIZE + TITLE_HEIGHT + SHADOW_SIZE  # 每个项目总高度
        ITEMS_PER_ROW = 4
        HEADER_HEIGHT = 80  # 增加标题栏高度以适应更大字体
        MARGIN = 20
        
        # 计算图片高度（预留底部版权信息空间）
        rows = math.ceil(len(records) / ITEMS_PER_ROW)
        height = HEADER_HEIGHT + (ITEM_HEIGHT + MARGIN) * rows + MARGIN + 30  # 额外+30用于版权信息
        
        # 创建白色背景图片
        img = Image.new('RGB', (WIDTH, height), 'white')
        draw = ImageDraw.Draw(img)
        
        # 绘制顶部标题栏
        for y in range(10):
            r = int(30 + 100 * y * 8 / HEADER_HEIGHT)
            g = int(60 + 40 * y * 8 / HEADER_HEIGHT)
            b = int(100 + 100 * y * 8 / HEADER_HEIGHT)
            draw.line((0, y, WIDTH, y), fill=(r, g, b))
        
        # 加载指定字体（钉钉进步体）
        font_path = os.path.join(BASE_DIR, "ShangguSans-Bold.ttf")
        try:
            title_font = ImageFont.truetype(font_path, 44)  # 标题字体
            rank_font = ImageFont.truetype(font_path, 36)   # 定数字体
            name_font = ImageFont.truetype(font_path, 32)   # 曲目标题字体
            footer_font = ImageFont.truetype(font_path, 16) # 页脚字体
        except Exception as e:
            LOG.error(f"加载字体失败: {str(e)}")
            #  fallback到默认字体
            title_font = ImageFont.load_default()
            rank_font = ImageFont.load_default()
            name_font = ImageFont.load_default()
            footer_font = ImageFont.load_default()
        
        # 绘制主标题
        title = "Arkana Constant Sheet"
        draw.text((MARGIN, (HEADER_HEIGHT - 20) // 2), 
                 title, fill=(0, 0, 0), font=title_font)
        
        # 绘制定数信息
        level_text = f"Level {rating:.1f}"
        level_x = WIDTH - self.get_text_width(draw, level_text, rank_font) - MARGIN
        draw.text((level_x, (HEADER_HEIGHT - 20) // 2), 
                 level_text, fill=(0, 0, 0), font=rank_font)
        
        # 处理每个曲目的显示
        for idx, (song_id, song_name, difficulty) in enumerate(records):
            row = idx // ITEMS_PER_ROW
            col = idx % ITEMS_PER_ROW
            
            # 计算位置
            x = MARGIN + col * (ITEM_SIZE + SHADOW_SIZE + MARGIN)
            y = HEADER_HEIGHT + MARGIN + row * (ITEM_HEIGHT + MARGIN)
            
            # 加载曲绘（从多个来源路径查找）
            song_img = None
            for path in ILLUSTRATION_PATH:
                # 检查带dl_前缀的文件夹
                dl_folder = os.path.join(path, f"dl_{song_id}")
                if os.path.exists(dl_folder):
                    jpg_files = glob.glob(os.path.join(dl_folder, "*.[jJ][pP][gG]"))
                    if jpg_files:
                        try:
                            song_img = Image.open(jpg_files[0])
                            song_img = song_img.resize((ITEM_SIZE, ITEM_SIZE))
                            break
                        except Exception as e:
                            LOG.warning(f"加载曲绘 {jpg_files[0]} 失败: {str(e)}")
                
                # 检查不带dl_前缀的文件夹
                normal_folder = os.path.join(path, song_id)
                if os.path.exists(normal_folder):
                    jpg_files = glob.glob(os.path.join(normal_folder, "*.[jJ][pP][gG]"))
                    if jpg_files:
                        try:
                            song_img = Image.open(jpg_files[0])
                            song_img = song_img.resize((ITEM_SIZE, ITEM_SIZE))
                            break
                        except Exception as e:
                            LOG.warning(f"加载曲绘 {jpg_files[0]} 失败: {str(e)}")
            
            # 如果未找到曲绘，使用占位图
            if song_img is None:
                LOG.warning(f"未找到曲绘，song_id: {song_id}")
                song_img = Image.new('RGB', (ITEM_SIZE, ITEM_SIZE), (240, 240, 240))
                d = ImageDraw.Draw(song_img)
                d.text((10, 10), "No Image", fill='gray', font=name_font)
            
            # 添加曲绘到图片
            img.paste(song_img, (x, y))
            
            # 设置难度阴影颜色
            if difficulty == 'ftr':
                color = (75, 0, 130)  # 深紫色
            elif difficulty == 'byn':
                color = (220, 20, 60)  # 红色
            elif difficulty == 'etr':
                color = (128, 128, 128)  # 灰色
            else:
                color = (0, 0, 0)  # 黑色
            
            # 绘制阴影
            # 水平阴影
            draw.rectangle([
                x + 30, 
                y + ITEM_SIZE + 5, 
                x + ITEM_SIZE + SHADOW_SIZE, 
                y + ITEM_SIZE + SHADOW_SIZE + 5
            ], fill=color)
            
            # 垂直阴影
            draw.rectangle([
                x + ITEM_SIZE + 5, 
                y + 30, 
                x + ITEM_SIZE + SHADOW_SIZE + 5, 
                y + ITEM_SIZE + 15
            ], fill=color)
            
            # 绘制曲目标题
            title_y = y + ITEM_SIZE + SHADOW_SIZE
            title_text = self.format_song_name(song_name)
            max_width = ITEM_SIZE + SHADOW_SIZE - 20
            
            # 截断标题文本
            truncated_text = self.truncate_text(draw, title_text, max_width, name_font)
            
            # 计算文本位置
            text_x = x + 28
            text_y = title_y + (TITLE_HEIGHT - 20) // 2
            
            # 绘制标题
            draw.text((text_x, text_y), truncated_text, fill='black', font=name_font)
        
        # 绘制版权信息
        copyright_text = "Copyright © 2025 08Nx. All rights reserved. - " + str(datetime.datetime.now())
        copyright_x = MARGIN
        copyright_y = height - 25  # 底部上方25像素
        draw.text((copyright_x, copyright_y), copyright_text, fill=(100, 100, 100), font=footer_font)
        
        # 保存图片到输出路径
        img.save(OUTPUT_PATH, format='PNG')
        
        return img

    async def on_load(self):
        """插件加载时注册命令"""
        self.register_user_func(
            "/rating",
            self.handle_rating_command,
            description="查询Arcaea指定定数的曲目",
            prefix="/rating",
            usage="""
            /rating [定数] - 查询指定定数的所有曲目
            定数格式：1-12之间的数字，支持一位小数（如9.5）
            """,
            examples=[
                "/rating 9.5",    # 查询定数9.5的曲目
                "/rating 10",     # 查询定数10.0的曲目
            ],
            tags=["user"]
        )
        LOG.info(f"{self.name} 插件已加载，版本: {self.version}")