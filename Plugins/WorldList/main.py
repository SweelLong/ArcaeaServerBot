import sqlite3
import os
import io
from typing import List, Tuple, Dict
from PIL import Image, ImageDraw, ImageFont
import ncatbot
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import BaseMessage
from ncatbot.utils import get_log
LOG = get_log("WorldList")
bot = CompatibleEnrollment
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) 
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(BASE_DIR))) 
DATABASE_PATH = os.path.join(PARENT_DIR, "ArkanaServer\\database\\arcaea_database.db")
OUTPUT_PATH = os.path.join(BASE_DIR, "output.png") 
class WorldList(BasePlugin):
    name = "WorldList"
    version = "1.0.0"
    author = "08nx/Swiro"
    description = "玩家排行榜插件，支持PTT榜和#值榜"
    dependencies = {}

    async def handle_rank_command(self, msg: BaseMessage):
        """处理排行榜查询命令"""
        parts = msg.raw_message.split()
        # 解析参数，默认#榜
        rank_type = "2"  # 1: PTT榜, 2: #值榜
        if len(parts) >= 2:
            arg = parts[1].strip().lower()
            if arg in ["1", "ptt"]:
                rank_type = "1"
            elif arg in ["2", "#"]:
                rank_type = "2"

        # 检查数据库文件是否存在
        if not os.path.exists(DATABASE_PATH):
            return await msg.reply(f"数据库文件不存在，请检查路径: {DATABASE_PATH}")

        # 连接数据库并获取数据
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()

            if rank_type == "1":  # PTT榜
                cursor.execute("SELECT name, rating_ptt FROM user ORDER BY rating_ptt DESC LIMIT 40")
                users = cursor.fetchall()
                data = [(name, (ptt / 100)) for name, ptt in users]
                title = "Arkana POTENTIAL Rankings"
                value_label = "PTT"
            else:  # #值榜
                # 从best_score表获取所有记录
                cursor.execute("""
                    SELECT user_id, score, song_id, difficulty, 
                           shiny_perfect_count, perfect_count, near_count, miss_count, rating
                    FROM best_score
                """)
                best_scores = cursor.fetchall()

                # 获取所有歌曲定数
                song_ids = set(score[2] for score in best_scores)
                chart_data = {}
                if song_ids:
                    placeholders = ','.join('?' for _ in song_ids)
                    cursor.execute(f"""
                        SELECT song_id, rating_ftr, rating_byn, rating_etr
                        FROM chart WHERE song_id IN ({placeholders})
                    """, list(song_ids))
                    charts = cursor.fetchall()
                    for chart in charts:
                        song_id = chart[0]
                        chart_data[song_id] = {
                            "ftr": chart[1],
                            "byn": chart[2],
                            "etr": chart[3]
                        }

                # 计算每个用户的#值
                user_scores: Dict[int, float] = {}
                for score in best_scores:
                    user_id, score_val, song_id, difficulty, sp, p, n, m, _ = score

                    song_ratings = chart_data.get(song_id)
                    if not song_ratings:
                        continue

                    # 根据难度选择定数
                    if difficulty == 2:
                        chart_rating = song_ratings["ftr"]
                    elif difficulty == 3:
                        chart_rating = song_ratings["byn"]
                    elif difficulty == 4:
                        chart_rating = song_ratings["etr"]
                    else:
                        continue

                    # 计算#值
                    total_notes = p + n + m
                    if total_notes > 0:
                        acc_ratio = sp / total_notes
                        acc_component = max(0, min(acc_ratio - 0.9, 0.095))
                    else:
                        acc_component = 0

                    score_ratio = score_val / 10000000
                    score_component = max(0, min(score_ratio - 0.99, 0.01))

                    k = 100
                    song_value = k * chart_rating * (acc_component + 28.5 * score_component)
                    user_scores[user_id] = user_scores.get(user_id, 0.0) + song_value

                # 排序取前200名并获取用户名
                sorted_users = sorted(user_scores.items(), key=lambda x: x[1], reverse=True)[:200]
                user_ids = [user[0] for user in sorted_users]
                data = []

                if user_ids:
                    placeholders = ','.join('?' for _ in user_ids)
                    cursor.execute(f"SELECT user_id, name FROM user WHERE user_id IN ({placeholders})", user_ids)
                    user_names = {row[0]: row[1] for row in cursor.fetchall()}

                    data = [
                        (user_names.get(user_id, f"未知玩家({user_id})"), score)
                        for user_id, score in sorted_users
                    ]

                title = "Arkana #VALUE Rankings"
                value_label = "#"

            conn.close()

            if not data:
                return await msg.reply("未找到用户数据，请确认数据库中有记录")
            image = self.generate_rank_image(data, title, value_label, rank_type)
            image.save(OUTPUT_PATH, format='PNG')
            reply_msg = ncatbot.core.MessageChain()
            reply_msg += ncatbot.core.Image(OUTPUT_PATH)
            return await msg.api.post_group_msg(group_id=msg.group_id, rtf=reply_msg)

        except Exception as e:
            LOG.error(f"处理排行榜时出错: {str(e)}")
            return await msg.reply(f"查询失败: {str(e)}")

    def generate_rank_image(self, data: List[Tuple[str, float]], title: str, value_label: str, rank_type: str) -> Image.Image:
        """生成排行榜图片，带有白色透明圆角和简约风格设计"""
        # 图片尺寸设置 - 增大尺寸以适应更大字体
        width = 700
        header_height = 140
        item_height = 80
        margin = 20
        footer_height = 40  # 底部版权区域高度
        total_height = header_height + len(data) * item_height + margin * 2 + footer_height

        # 创建带透明通道的图像 - 简约白色透明风格
        img = Image.new('RGBA', (width, total_height), (255, 255, 255, 0))  # 完全透明背景
        draw = ImageDraw.Draw(img)

        # 绘制主背景（带圆角，白色半透明）
        bg_radius = 20  # 增大圆角半径
        main_bg_rect = [margin, margin, width - margin, total_height - margin - footer_height]
        draw.rounded_rectangle(main_bg_rect, radius=bg_radius, fill=(255, 255, 255, 230))  # 白色半透明

        # 加载字体（尝试加载指定字体，失败则使用默认字体）
        try:
            path = os.path.join(BASE_DIR, "DingTalk JinBuTi.ttf")
            title_font = ImageFont.truetype(path, 44)  # 增大标题字体
            rank_font = ImageFont.truetype(path, 36)   # 增大排名字体
            name_font = ImageFont.truetype(path, 32)   # 增大名称字体
            value_font = ImageFont.truetype(path, 28)  # 增大数值字体
            footer_font = ImageFont.truetype(path, 16) # 增大页脚字体
        except:
            # 加载默认字体并增大尺寸
            title_font = ImageFont.load_default(size=44)
            rank_font = ImageFont.load_default(size=36)
            name_font = ImageFont.load_default(size=32)
            value_font = ImageFont.load_default(size=28)
            footer_font = ImageFont.load_default(size=16)

        # 绘制标题背景（带圆角顶部，更浅的色调）
        title_bg_height = 120
        title_bg_rect = [margin, margin, width - margin, margin + title_bg_height]
        draw.rounded_rectangle(title_bg_rect, radius=bg_radius, 
                            fill=(240, 240, 240, 240),  # 更浅的背景
                            corners=(True, True, False, False))

        # 绘制标题（居中）
        title_width = draw.textlength(title, font=title_font)
        draw.text(((width - title_width) // 2, margin + 20),
                title, fill=(50, 50, 50), font=title_font)  # 深灰色文字

        # 绘制副标题
        subtitle = f"Top {len(data)} - {value_label}"
        subtitle_width = draw.textlength(subtitle, font=name_font)
        draw.text(((width - subtitle_width) // 2, margin + 75),
                subtitle, fill=(80, 80, 80), font=name_font)  # 中灰色文字

        # 绘制每个用户条目
        for idx, (name, value) in enumerate(data):
            y_pos = margin + header_height + idx * item_height

            # 条目背景色 (简约的灰白交替)
            bg_color = (255, 255, 255, 200) if idx % 2 == 0 else (245, 245, 245, 200)
            draw.rectangle([margin, y_pos, width - margin, y_pos + item_height], fill=bg_color)

            # 排名数字和颜色
            rank = idx + 1
            rank_color = (50, 50, 50)  # 默认深灰色
            if rank == 1:
                rank_color = (255, 184, 28)  # 金色
            elif rank == 2:
                rank_color = (169, 169, 169)  # 银色
            elif rank == 3:
                rank_color = (205, 127, 50)  # 铜色

            # 排名文本
            if rank_type == "1":
                rank_text = f"No.{rank}"
                draw.text((margin + 60, y_pos + item_height // 2),
                        rank_text, fill=rank_color, font=rank_font, anchor="mm")
            else:
                rank_text = f"#{rank}"
                draw.text((margin + 50, y_pos + item_height // 2),
                        rank_text, fill=rank_color, font=rank_font, anchor="mm")

            # 玩家名称（处理过长名称）
            max_name_width = width - 2 * margin - 200
            display_name = name
            while draw.textlength(display_name + "...", font=name_font) > max_name_width and len(display_name) > 1:
                display_name = display_name[:-1]
            if len(name) != len(display_name):
                display_name += "..."

            draw.text((width // 2, y_pos + item_height // 2),
                    display_name, fill=(50, 50, 50), font=name_font, anchor="mm")

            # 数值显示
            value_text = f"{value:.2f}" if isinstance(value, float) else str(value)
            draw.text((width - margin - 60, y_pos + item_height // 2),
                    value_text, fill=(50, 50, 50), font=value_font, anchor="mm")

            # 添加分割线
            if idx < len(data) - 1:
                draw.line([(margin, y_pos + item_height), (width - margin, y_pos + item_height)],
                        fill=(220, 220, 220), width=2)

        # 添加底部版权信息
        copyright_text = "Copyright © 2025 08Nx. Modified by Swiro."
        copyright_width = draw.textlength(copyright_text, font=footer_font)
        draw.text(((width - copyright_width) // 2, total_height - footer_height + 10),
                copyright_text, fill=(120, 120, 120), font=footer_font)

        # 创建圆角遮罩，使整体图像边缘更平滑
        mask = Image.new('L', (width, total_height), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([margin//2, margin//2, width - margin//2, total_height - margin//2], 
                                radius=bg_radius + 5, fill=255)
        img.putalpha(mask)

        return img

    async def on_load(self):
        """插件加载时注册命令"""
        self.register_user_func(
            "/rank",
            self.handle_rank_command,
            description="查询玩家排行榜",
            prefix="/rank",
            usage="""
            /rank [类型] - 查询排行榜
            类型参数：
            1 或 ptt - 显示PTT排行榜
            2 或 #   - 显示#值排行榜（默认）
            """,
            examples=[
                "/rank",          # 显示默认#值榜
                "/rank ptt",      # 显示PTT榜
                "/rank #"         # 显示#值榜
            ],
            tags=["user"]
        )
        LOG.info(f"{self.name} 插件已加载，版本: {self.version}")