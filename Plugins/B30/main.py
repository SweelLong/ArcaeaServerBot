from ncatbot.plugin import BasePlugin
from ncatbot.core.message import BaseMessage
from ncatbot.core import MessageChain
from ncatbot.core import Image as BotImage
from ncatbot.utils import get_log
import os
import sqlite3
import json 
from PIL import Image as Image, ImageDraw, ImageFont
import glob
import datetime
import math
from typing import List, Dict
# ======================== 全局配置 ========================
LOG = get_log("B30")  # 日志对象
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # 脚本根目录
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(BASE_DIR)))  # 最外层父目录（连接其他项目如ArkanaServer、ArkanaBundler）
DATABASE_PATH = os.path.join(PARENT_DIR, "ArkanaServer\\database\\arcaea_database.db")
ILLUSTRATION_PATH = [
    # 第一个位置的songlist优先级最高，请确保该songlist的内容最新最完整
    os.path.join(PARENT_DIR, "ArkanaServer\\database\\songs\\"),  # 曲绘来源路径1：直接读取隔壁服务器文件夹中的下载歌曲目录
    os.path.join(PARENT_DIR, "ArkanaBundler\\assets\\songs\\")  # 曲绘来源路径2：直接读取制作热更新包的文件夹目录
]
OUTPUT_PATH = os.path.join(BASE_DIR, "output.png")  # 最终输出路径
# 输出图片尺寸
TARGET_SIZE = (1020, 3060)
# 素材文件夹路径
IMG_FOLDER = os.path.join(BASE_DIR, "src")  # 核心素材
AVATAR_FOLDER = os.path.join(PARENT_DIR, "ArkanaBundler\\assets\\char")  # 用户头像
COURSE_FOLDER = os.path.join(IMG_FOLDER, "course")  # 段位框
CLEAR_TYPE_FOLDER = os.path.join(IMG_FOLDER, "clear_type")  # 歌曲评级
RATING_FOLDER = os.path.join(IMG_FOLDER, "rating")  # 头像数字框
# 关键素材路径
BEST30_TITLE = os.path.join(IMG_FOLDER, "best30.png")  # BEST 30标题
OVERFLOW_TITLE = os.path.join(IMG_FOLDER, "overflow.png")  # OVER FLOW标题
BG_PATH = os.path.join(BASE_DIR, "src", "bg.png")  # 背景图路径
SPECIFIC_FONT = [
    os.path.join(BASE_DIR, "src", "DingTalk JinBuTi.ttf"),
    os.path.join(BASE_DIR, "src", "ShangguSans-Bold.ttf")
]  # 字体列表
# 布局参数
CARD_WIDTH = 300  # 卡片宽度
CARD_HEIGHT = 155  # 卡片高度
CARDS_PER_ROW = 3  # 每行卡片数量
CARD_GAP = 30  # 卡片间距
TITLE_PADDING = 30  # 区域标题与卡片间距
TEXT_PADDING = 10  # 文字与卡片边缘间距
class B30(BasePlugin):
    name = "B30"
    version = "6.2.6" 
    author = "SweelLong(Swiro)"
    description = """
    Arkana Best 30 查分插件
    请将ArkanaBot项目、ArkanaServer项目(\database\songs)、ArkanaBundler项目(\assets\songs)放置在同一目录下
    完成上述要求才会自动读取曲绘、数据库等资源
    """
    dependencies = {}
# ======================== 辅助函数 ========================
    def get_best_font(size: int, planB: bool = False) -> ImageFont.FreeTypeFont:
        """加载指定字号的字体"""
        if planB:
            return ImageFont.truetype(SPECIFIC_FONT[1], size)
        return ImageFont.truetype(SPECIFIC_FONT[0], size)
    def load_image(path: str, size: tuple = None, keep_aspect: bool = True) -> Image.Image:
        """高清加载图片"""
        if not os.path.exists(path):
            return None
        try:
            img = Image.open(path).convert("RGBA")
            if size:
                if keep_aspect:
                    img.thumbnail(size, Image.Resampling.LANCZOS)
                else:
                    img = img.resize(size, Image.Resampling.LANCZOS)
            return img
        except Exception as e:
            LOG.error(f"加载失败: {path} → {e}")
            return None
    def format_score(score: int) -> str:
        """分数格式化（10001102 → 10'001'102）"""
        s = str(score)[::-1]
        return "'".join([s[i:i+3] for i in range(0, len(s), 3)])[::-1] or "0"
    def get_rating_box_img(rating_ptt: str) -> str:
        """根据 rating_ptt 获取对应的数字框图片"""
        rating_value = float(rating_ptt)
        if rating_value <= 3.49:
            return "rating_0.png"
        elif rating_value <= 6.99:
            return "rating_1.png"
        elif rating_value <= 9.99:
            return "rating_2.png"
        elif rating_value <= 10.99:
            return "rating_3.png"
        elif rating_value <= 11.99:
            return "rating_4.png"
        elif rating_value <= 12.49:
            return "rating_5.png"
        elif rating_value <= 12.99:
            return "rating_6.png"
        else:
            return "rating_7.png"
    
    def get_difficulty_str(self, difficulty: int) -> str:
        """获取难度字符串"""
        if difficulty == 0:
            self.DIFF_COLOR = (35, 199, 217)
            return "PAST"
        elif difficulty == 1:
            self.DIFF_COLOR = (35, 217, 69)
            return "PRESENT"
        elif difficulty == 2:
            self.DIFF_COLOR = (255, 83, 195)
            return "FUTURE"
        elif difficulty == 3:
            self.DIFF_COLOR = (217, 35, 35)
            return "BEYOND"
        elif difficulty == 4:
            self.DIFF_COLOR = (80, 0, 107)
            return "ETERNAL"
    def get_difficulty_rating(difficulty: int) -> str:
        """获取难度评级字符串"""
        if difficulty == 0:
            return "rating_pst"
        elif difficulty == 1:
            return "rating_prs"
        elif difficulty == 2:
            return "rating_ftr"
        elif difficulty == 3:
            return "rating_byn"
        elif difficulty == 4:
            return "rating_etr"
    def get_clear_type(clear_type: int) -> str:
        """获取歌曲的难度类型"""
        if clear_type == 0:
            return "fail.png"
        elif clear_type == 1:
            return "normal.png"
        elif clear_type == 2:
            return "full.png"
        elif clear_type == 3:
            return "pure.png"
        elif clear_type == 4:
            return "easy.png"
        elif clear_type == 5:
            return "hard.png"
        elif clear_type == 6:
            return "pure.png"
    # ======================== 核心绘制逻辑 ========================
    def draw_user_info(draw: ImageDraw.ImageDraw, user: Dict, bg: Image.Image, y: int) -> int:
        """绘制用户信息区域（头像、数字框、名称、ID、PTT）"""
        course_bg = B30.load_image(os.path.join(COURSE_FOLDER, user['course']), (400, 60))
        if course_bg:
            bg.paste(course_bg, (145, y + 50), course_bg)
        draw.text((200, y + 60), user["name"], font=B30.get_best_font(30), fill=(255, 255, 255))
        avatar = B30.load_image(os.path.join(AVATAR_FOLDER, user["avatar"]), (150, 150))
        if avatar:
            bg.paste(avatar, (30, y + 10), avatar)
        RATING_BOX = os.path.join(RATING_FOLDER, B30.get_rating_box_img(user['rating_ptt']))
        rating_box = B30.load_image(RATING_BOX, (75, 75))
        if rating_box:
            bg.paste(rating_box, (120, y + 90), rating_box)
        # ======================红色描边=======================
        rank = user["rank"]
        font_level = B30.get_best_font(30) 
        stroke_color = (197, 41, 7 )
        main_color = (255, 255, 255)
        offsets = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
        for ox, oy in offsets:
            draw.text((135 + ox, y + 15 + oy), rank, font=font_level, fill=stroke_color)
        draw.text((135, y + 15), rank, font=font_level, fill=main_color)
        # -----------------------------------------------------
        # ======================紫色描边=======================
        level_text = user["rating_ptt"]
        font_level = B30.get_best_font(24) 
        stroke_color = (150, 50, 200)
        main_color = (255, 255, 255)
        offsets = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
        for ox, oy in offsets:
            draw.text((135 + ox, y + 115 + oy), level_text, font=font_level, fill=stroke_color)
        draw.text((135, y + 115), level_text, font=font_level, fill=main_color)
        # -----------------------------------------------------
        draw.text((200, y + 120), f"ID: {user['id']}", font=B30.get_best_font(26), fill=(255, 255, 255))
        # 绘制 PTT 信息（右侧）
        ptt_x = 750
        draw.text((ptt_x, y + 20), f"Max : {user['max_ptt']}", font=B30.get_best_font(36), fill=(255, 255, 255))
        draw.text((ptt_x, y + 60), f"B30 : {user['b30_ptt']}", font=B30.get_best_font(36), fill=(255, 255, 255))
        draw.text((ptt_x, y + 100), f"R10 : {user['r10_ptt']}", font=B30.get_best_font(36), fill=(255, 255, 255))
        return y + 180  # 返回下一个区域的起始Y坐标
    def draw_song_section(draw: ImageDraw.ImageDraw, bg: Image.Image, songs: List[Dict], title_path: str, start_y: int) -> int:
        """绘制歌曲区域（BEST 30 / OVER FLOW）"""
        # 加载区域标题图
        title_img = B30.load_image(title_path, (250, 50))
        if title_img:
            bg.paste(title_img, (TARGET_SIZE[0] // 2 - title_img.width // 2, start_y), title_img)
            start_y += title_img.height + TITLE_PADDING
        # 计算卡片布局
        song_count = len(songs)
        rows = math.ceil(song_count / CARDS_PER_ROW)
        for row in range(rows):
            for col in range(CARDS_PER_ROW):
                idx = row * CARDS_PER_ROW + col
                if idx >= song_count:
                    break  # 处理最后一行不足的情况
                song = songs[idx]
                # 卡片坐标
                x = 30 + col * (CARD_WIDTH + CARD_GAP)
                y = start_y + row * (CARD_HEIGHT + CARD_GAP)
                # 绘制卡片背景
                card_bg = Image.new("RGBA", (CARD_WIDTH, CARD_HEIGHT), (0, 0, 0, 0))
                card_draw = ImageDraw.Draw(card_bg)
                card_draw.rounded_rectangle([(0, 0), (CARD_WIDTH, CARD_HEIGHT)], radius=20, fill=(255, 255, 255, 128) )
                bg.paste(card_bg, (x, y), card_bg)
                # 加载曲绘
                illustration = B30.load_image(song["illustration_path"], (115, 115), keep_aspect=False)
                if illustration:
                    bg.paste(illustration, (x + 10, y + 10), illustration)
                # 绘制歌曲信息
                y_text = y + CARD_HEIGHT - 25
                # 歌曲名
                song_name = song["song_name"][:25] + "..." if len(song["song_name"]) > 25 else song["song_name"]
                draw.text((x + TEXT_PADDING, y_text), song_name, font=B30.get_best_font(16, True), fill=(0, 0, 0))
                y_text += 20
                # 单曲顺序
                # ======================紫色描边=======================
                level_text = song['order']
                font_level = B30.get_best_font(16) 
                stroke_color = (150, 50, 200)
                main_color = (255, 255, 255)
                offsets = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
                for ox, oy in offsets:
                    draw.text((x + TEXT_PADDING + CARD_WIDTH - 50 + ox, y_text - CARD_HEIGHT + 20 + oy), level_text, font=font_level, fill=stroke_color)
                draw.text((x + TEXT_PADDING + CARD_WIDTH - 50, y_text - CARD_HEIGHT + 20), level_text, font=font_level, fill=main_color)
                # -----------------------------------------------------
                # 难度
                draw.text((x + TEXT_PADDING + 120, y_text - CARD_HEIGHT + 20), song["difficulty"] + f"[{song['chart_const']}]", font=B30.get_best_font(14), fill=song['diff_color'])
                y_text += 20
                # 分数
                draw.text((x + TEXT_PADDING + 120, y_text - CARD_HEIGHT + 20), B30.format_score(song["score"]), font=B30.get_best_font(26), fill=(255, 255, 255))
                y_text += 30
                # 单曲评级
                draw.text((x + TEXT_PADDING + 120, y_text - CARD_HEIGHT + 20), song["rating"], font=B30.get_best_font(14), fill=(255, 255, 255))
                y_text += 20
                # 小P
                draw.text((x + TEXT_PADDING + 120, y_text - CARD_HEIGHT + 20), f"P/{song['pm_num']}({song['delta_pm_num']})", font=B30.get_best_font(14), fill=(213, 0, 255))
                y_text += 20
                # FAR
                draw.text((x + TEXT_PADDING + 120, y_text - CARD_HEIGHT + 20), f"F/{song['far_num']}", font=B30.get_best_font(14), fill=(255, 211, 0 ))
                # LOST
                draw.text((x + TEXT_PADDING + 120 + 40, y_text - CARD_HEIGHT + 20), f"L/{song['lost_num']}", font=B30.get_best_font(14), fill=(152, 4, 4))
                # 绘制评级图标（rank 文件夹）
                rating_img = B30.load_image(os.path.join(CLEAR_TYPE_FOLDER, song['clear_type']), (80, 80))
                if rating_img:
                    bg.paste(rating_img, (x + CARD_WIDTH - 70, y + CARD_HEIGHT - 65), rating_img)
        return start_y + rows * (CARD_HEIGHT + CARD_GAP) + TITLE_PADDING  # 返回下一个区域的Y坐标
    # ======================== 主函数 ========================
    def generate_rating_card(user: Dict, song_data: Dict) -> None:
        # 1. 初始化背景
        bg = B30.load_image(BG_PATH, size=TARGET_SIZE, keep_aspect=False)
        if not bg:
            bg = Image.new("RGB", TARGET_SIZE, (255, 255, 255))  # 背景缺失时用白色
        draw = ImageDraw.Draw(bg)
        # 2. 绘制用户信息区域
        current_y = B30.draw_user_info(draw, user, bg, y=20)
        # 3. 绘制 BEST 30 区域
        current_y = B30.draw_song_section(draw, bg, song_data["b30"], BEST30_TITLE, current_y)
        # 4. 绘制 OVER FLOW 区域
        current_y = B30.draw_song_section(draw, bg, song_data["overflow"], OVERFLOW_TITLE, current_y)
        # 5. 绘制底部生成信息
        now = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        draw.text(
            (TARGET_SIZE[0] // 2, TARGET_SIZE[1] - 40),
            f"The rating card is generated by SweelLong(Swiro). Generate at {now}. \n Copyright © 2025 SweelLong(Swiro) All rights reserved. Only for player in Arkana.",
            font=B30.get_best_font(16),
            fill=(255, 255, 255),
            anchor="mm"
        )
        # 6. 保存高清图片
        bg.convert("RGB").save(OUTPUT_PATH, quality=95)
        LOG.info(f"✅ 图片已保存至: {OUTPUT_PATH}")
        #bg.show()
    # ======================== 插件入口 ========================
    async def on_load(self):
        """插件初始化"""
        self.register_user_func(
            "/b30", 
            self.b30, 
            prefix="/b30", 
            description="查询Arkana Best30和R10成绩（含谱面/曲绘信息）",
            usage="/b30 - 显示Best30和最近30首成绩中的前10首的网格卡片式成绩，包含谱面设计、曲绘设计和难度值",
            examples=["/b30"],
            tags=["user"]
        )
        LOG.info(f"{self.name} 插件已加载，版本: {self.version}")
    async def b30(self, msg: BaseMessage):
        """处理/b30命令，发送分区域的卡片"""
        # 获取QQ号
        QQ_ID = str(msg.user_id)
        email = QQ_ID + "@qq.com"
        tmp_data = dict()
        # user表查询
        with sqlite3.connect(DATABASE_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM (SELECT
                           user_id, 
                           name, 
                           user_code,
                           rating_ptt, 
                           email, 
                           character_id,
                           is_char_uncapped,
                           is_char_uncapped_override,
                           RANK() OVER (ORDER BY rating_ptt DESC) AS rank
                           FROM user
                           ) WHERE email = ?
                           """, (email,))
            tmp_data = dict(cursor.fetchone())
        # 获取user_id现在什么都可以查询了
        user_id = tmp_data["user_id"]
        user_info = {
            "id": tmp_data["user_code"],
            "name": tmp_data["name"],
            "rank": f"# {tmp_data['rank']}",
            "avatar": str(tmp_data["character_id"]) + ("u_icon.png" if not tmp_data["is_char_uncapped_override"] and tmp_data["is_char_uncapped"] else "_icon.png"),
            "rating_ptt": str(round(tmp_data["rating_ptt"] / 100, 2)),
        }
        # 读取course表
        with sqlite3.connect(DATABASE_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT course_id FROM user_course WHERE user_id = ? ORDER BY course_id DESC LIMIT 1", (user_id,))
            """
            if not cursor.fetchone():
                user_info["course"] = "26.png"
            else:
                user_info["course"] = cursor.fetchone()["course_id"] + ".png"
            """
            user_info["course"] = "26.png" # 暂不支持指定段位框哦
        # 加载songlist
        song_jacket_path = {}
        song_difficulties_info = {}
        slst_path = ""
        for path in ILLUSTRATION_PATH:
            if os.path.exists(os.path.join(path, "songlist")):
                slst_path = os.path.join(path, "songlist")
                break
        with open(slst_path, "r", encoding="utf-8") as f:
            slst_data = json.load(f)["songs"]
            for song in slst_data:
                difDict = dict()
                for diff in song["difficulties"]:
                    difDict[diff["ratingClass"]] = (diff["rating"], diff.get("ratingPlus", False))
                song_difficulties_info[song["id"]] = difDict
                jacket_path = ""
                for path in ILLUSTRATION_PATH:
                    if os.path.exists(os.path.join(path, "dl_" + song["id"])):
                        jacket_path = glob.glob(os.path.join(path, "dl_" + song["id"], "*.[jJ][pP][gG]"))
                        if jacket_path:
                            song_jacket_path[song["id"]] = jacket_path[0]
                    elif os.path.exists(os.path.join(path, song["id"])):
                        jacket_path = glob.glob(os.path.join(path, song["id"], "*.[jJ][pP][gG]"))
                        if jacket_path:
                            song_jacket_path[song["id"]] = jacket_path[0]
                    if jacket_path:
                        break
        # Best 30 歌曲列表
        b30 = []
        b30sum = 0
        with sqlite3.connect(DATABASE_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                        SELECT song_id, difficulty, rating, MAX(score) score, name, best_clear_type, perfect_count, shiny_perfect_count, near_count, miss_count, rating_pst, rating_prs, rating_ftr, rating_byn, rating_etr
                        FROM best_score NATURAL JOIN chart
                        WHERE user_id = ?
                        GROUP BY song_id, difficulty
                        ORDER BY rating DESC 
                        LIMIT 30
                    """, (user_id,))
            for idx, row in enumerate(cursor.fetchall()):
                tmp_data = dict(row)
                diffInfo = song_difficulties_info.get(tmp_data["song_id"], {}).get(tmp_data["difficulty"], (0, False))
                b30.append({
                    "order": f"# {idx + 1}",
                    "song_name": tmp_data["name"],
                    "difficulty": f"{B30.get_difficulty_str(self, tmp_data["difficulty"])} {diffInfo[0]}{'+' if diffInfo[1] else ''}",
                    "diff_color": self.DIFF_COLOR,
                    "clear_type": B30.get_clear_type(tmp_data["best_clear_type"]),
                    "score": tmp_data["score"],
                    "chart_const": round(float(tmp_data[B30.get_difficulty_rating(tmp_data['difficulty'])]) / 10, 1),
                    "rating": str(round(float(tmp_data["rating"]), 2)),
                    "pm_num": str(tmp_data["perfect_count"]),
                    "delta_pm_num": str(tmp_data["shiny_perfect_count"] - tmp_data["perfect_count"]),
                    "far_num": str(tmp_data["near_count"]),
                    "lost_num": str(tmp_data["miss_count"]),
                    "illustration_path": song_jacket_path.get(tmp_data["song_id"], "")
                })
                b30sum += float(tmp_data["rating"])
        # Over Flow 歌曲列表
        overflow = []
        overflowsum = 0
        with sqlite3.connect(DATABASE_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                        SELECT song_id, difficulty, rating, MAX(score) score, name, clear_type, perfect_count, shiny_perfect_count, near_count, miss_count, rating_pst, rating_prs, rating_ftr, rating_byn, rating_etr
                        FROM recent30 NATURAL JOIN chart
                        WHERE user_id = ?
                        GROUP BY song_id, difficulty
                        ORDER BY rating DESC 
                        LIMIT 10
                    """, (user_id,))
            for idx, row in enumerate(cursor.fetchall()):
                tmp_data = dict(row)
                diffInfo = song_difficulties_info.get(tmp_data["song_id"], {}).get(tmp_data["difficulty"], (0, False))
                overflow.append({
                    "order": f"# {idx + 1}",
                    "song_name": tmp_data["name"],
                    "difficulty": f"{B30.get_difficulty_str(self, tmp_data["difficulty"])} {diffInfo[0]}{'+' if diffInfo[1] else ''}",
                    "diff_color": self.DIFF_COLOR,
                    "clear_type": B30.get_clear_type(tmp_data["clear_type"]),
                    "score": tmp_data["score"],
                    "chart_const": round(float(tmp_data[B30.get_difficulty_rating(tmp_data['difficulty'])]) / 10, 1),
                    "rating": str(round(float(tmp_data["rating"]), 2)),
                    "pm_num": str(tmp_data["perfect_count"]),
                    "delta_pm_num": str(tmp_data["shiny_perfect_count"] - tmp_data["perfect_count"]),
                    "far_num": str(tmp_data["near_count"]),
                    "lost_num": str(tmp_data["miss_count"]),
                    "illustration_path": song_jacket_path.get(tmp_data["song_id"], "")
                })
                overflowsum += float(tmp_data["rating"])
        # 计算总评分
        user_info["max_ptt"] = str(round((b30sum + overflowsum) / 40, 2))
        user_info["b30_ptt"] = str(round(b30sum / 30, 2))
        user_info["r10_ptt"] = str(round(overflowsum / 10, 2))
        # 调用生成函数
        B30.generate_rating_card(user_info, {"b30": b30, "overflow": overflow})
        # 生成并发送图片
        try:
            if hasattr(msg, "group_id"):
                return await self.api.post_group_msg(msg.group_id, rtf=MessageChain(BotImage(OUTPUT_PATH)))
            else:
                return await msg.reply(BotImage(OUTPUT_PATH))
        except Exception as e:
            LOG.error(f"图片生成失败: {str(e)}")
            return await msg.reply(text="成绩卡片生成失败，请稍后再试")