from ncatbot.plugin import BasePlugin
from ncatbot.core.message import BaseMessage
from ncatbot.core import MessageChain
from ncatbot.core import Image as BotImage
from ncatbot.utils import get_log
import os
import sqlite3
import json 
import glob
from datetime import datetime
from PIL import Image, ImageDraw, ImageFilter, ImageFont
# ---------------------- 配置信息 ----------------------
LOG = get_log("RecentPlay")  # 日志对象
BASE_PATH = os.path.dirname(os.path.abspath(__file__)) 
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(BASE_PATH)))
DATABASE_PATH = os.path.join(PARENT_DIR, "ArkanaServer\\database\\arcaea_database.db")  
LOG.info("RecentPlay 数据库路径：%s", DATABASE_PATH)
SLST_PATH = os.path.join(PARENT_DIR, "ArkanaServer\\database\\songs\\songlist")  
OUTPUT_PATH = os.path.join(BASE_PATH, "output.png")  
IMG_PATH = os.path.join(BASE_PATH, "src")  
ILLUSTRATION_PATH = [
    # 第一个位置的songlist优先级最高，请确保该songlist的内容最新最完整
    os.path.join(PARENT_DIR, "ArkanaServer\\database\\songs\\"),  # 曲绘来源路径1：直接读取隔壁服务器文件夹中的下载歌曲目录
    os.path.join(PARENT_DIR, "ArkanaBundler\\assets\\songs\\")  # 曲绘来源路径2：直接读取制作热更新包的文件夹目录
]
FONT_PATH = os.path.join(IMG_PATH, "DingTalk JinBuTi.ttf")
FONT_UTF8_PATH = os.path.join(IMG_PATH, "ShangguSans-Bold.ttf")    
class RecentPlay(BasePlugin):
    name = "RecentPlay"
    version = "6.2.6"
    author = "SweelLong(Swiro)"
    description = "显示最近游玩的曲目信息"
    dependencies = {}
    @staticmethod
    def get_font(size, allow_utf8=False):
        """获取字体"""
        if allow_utf8:
            return ImageFont.truetype(FONT_UTF8_PATH, size)
        return ImageFont.truetype(FONT_PATH, size)
    @staticmethod
    def load_image(path, size=None, alpha=True):
        """加载图像"""
        img = Image.open(path)
        if alpha and img.mode != "RGBA":
            img = img.convert("RGBA")
        if size:
            img = img.resize(size, Image.Resampling.LANCZOS)
            img = img.filter(ImageFilter.UnsharpMask(radius=0.5, percent=100, threshold=3))
        return img
    @staticmethod
    def load_processed_image(background, img_path, position, size):
        """加载并处理图像"""
        img = Image.open(img_path)
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        if size:
            img = img.resize(size, Image.Resampling.LANCZOS)
            img = img.filter(ImageFilter.UnsharpMask(radius=0.3, percent=80, threshold=5))
            r, g, b, a = img.split()
            a = a.point(lambda x: 0 if x < 30 else 255)
            img = Image.merge("RGBA", (r, g, b, a))
        r, g, b, a = img.split()
        mask = a
        background.paste(img, position, mask)
        return background
    @staticmethod
    def draw_text_with_shadow(draw, pos, text, font, main_color, shadow_color, shadow_offset=(2, 2)):
        """绘制带阴影的文本"""
        x, y = pos
        draw.text((x + shadow_offset[0], y + shadow_offset[1]), text, font=font, fill=shadow_color)
        draw.text((x, y), text, font=font, fill=main_color)
    @staticmethod
    def get_diff_text(diff):
        """获取难度文本"""
        if diff == 0:
            return "Past"
        elif diff == 1:
            return "Present"
        elif diff == 2:
            return "Future"
        elif diff == 3:
            return "Beyond"
        elif diff == 4:
            return "Eternal"
    @staticmethod
    def get_diff_small_text(diff):
        """获取难度小文本"""
        if diff == 0:
            return "rating_pst"
        elif diff == 1:
            return "rating_prs"
        elif diff == 2:
            return "rating_ftr"
        elif diff == 3:
            return "rating_byn"
        elif diff == 4:
            return "rating_etr"
    @staticmethod
    def format_score(score: int) -> str:
        """分数格式化（10001102 → 10'001'102）"""
        s = str(score)[::-1]
        if len(s) <= 8:
            s = s.ljust(8, "0")
        return "'".join([s[i:i+3] for i in range(0, len(s), 3)])[::-1] or "0"
    @staticmethod
    def get_grade(score: int) -> str:
        """获取等级"""
        if score >= 9900000:
            return "EX+"
        elif score >= 9800000:
            return "EX"
        elif score >= 9500000:
            return "AA"
        elif score >= 9200000:
            return "A"
        elif score >= 8900000:
            return "B"
        elif score >= 8600000:
            return "C"
        else:
            return "D"
    @staticmethod
    def get_illustration_path(song_id):
        """获取曲绘路径"""
        for path in ILLUSTRATION_PATH:
            if os.path.exists(os.path.join(path, "dl_" + song_id)):
                jacket_path = glob.glob(os.path.join(path, "dl_" + song_id, "*.[jJ][pP][gG]"))
                if jacket_path:
                    return jacket_path[0]
            elif os.path.exists(os.path.join(path, song_id)):
                jacket_path = glob.glob(os.path.join(path, song_id, "*.[jJ][pP][gG]"))
                if jacket_path:
                    return jacket_path[0]
    @staticmethod
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
    @staticmethod
    def get_clear_type(clear_type: int) -> str:
        """获取歌曲的连击类型"""
        if clear_type == 0:
            return "clear_fail.png"
        elif clear_type == 1:
            return "clear_normal.png"
        elif clear_type == 2:
            return "clear_full.png"
        elif clear_type == 3:
            return "clear_pure.png"
        elif clear_type == 6:
            return "clear_pure.png"
        else:
            return "clear_normal.png"
    async def on_load(self):
        """插件初始化"""
        self.register_user_func(
            "/recent", 
            self.recent, 
            prefix="/recent", 
            description="查询Arkana最近游玩的歌曲的成绩（含谱面/曲绘信息）",
            usage="/recent - 显示最近游玩的歌曲的成绩",
            examples=["/recent"],
            tags=["user"]
        )
        LOG.info(f"{self.name} 插件已加载，版本: {self.version}")
    async def recent(self, msg: BaseMessage):
        """处理/recent命令，发送分区域的卡片"""
        qq_id = str(msg.sender.user_id)
        with sqlite3.connect(DATABASE_PATH, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""SELECT * FROM 
                           (
                            SELECT *, ROW_NUMBER() OVER(ORDER BY rating_ptt DESC) AS rank FROM 
                            user 
                            NATURAL JOIN 
                            (SELECT song_id, name song_name, rating_pst, rating_prs, rating_ftr, rating_byn, rating_etr FROM chart)
                           ) WHERE email = ? 
                           ORDER BY rank;""", (qq_id + "@qq.com",))
            info = cursor.fetchone()
            if not info:
                LOG.error("玩家不存在")
                await msg.reply("玩家不存在")
                return
            player_name = info["name"]
            hash_number = str(info["rank"])
            potential = str(info["rating_ptt"] / 100)
            diff = info["difficulty"]
            difficulty = self.get_diff_text(diff)
            song_name = info["song_name"]
            artist = "UNKNOWN"
            constant = "UNKNOWN"
            max_recall = str(datetime.fromtimestamp(int(info["time_played"]) / 1000).strftime("%Y-%m-%d %H:%M:%S"))
            hp_value = str(info["health"])
            score_current = self.format_score(info["score"])
            score_pb = str(round(info[self.get_diff_small_text(diff)] / 10, 1)) + " > "
            score_diff = str(round(info["rating"], 5))
            grade = self.get_grade(info["score"])
            pure = str(info["shiny_perfect_count"])
            pure_add = f"({info["shiny_perfect_count"] - info["perfect_count"]})"
            far = str(info["near_count"])
            lost = str(info["miss_count"])
            this_illustration_path = self.get_illustration_path(info["song_id"])
            rating_box_img = self.get_rating_box_img(info["rating_ptt"] / 100)
            clear_type_imgge = self.get_clear_type(info["clear_type"])
            avatar_image = str(info["character_id"]) + ("u_icon.png" if not info["is_char_uncapped_override"] and info["is_char_uncapped"] else "_icon.png")
            character_imgae = str(info["character_id"]) + ("u.png" if not info["is_char_uncapped_override"] and info["is_char_uncapped"] else ".png")
            with open(os.path.join(SLST_PATH), "r", encoding="utf-8") as f:
                json_data = json.load(f)["songs"]
                for song in json_data:
                    if song["id"] == info["song_id"]:
                        if song_name == "UNKNOWN":
                            song_name = song["title_localized"]["en"]
                        artist = song["artist"]
                        this_diff = song["difficulties"]
                        for this in this_diff:
                            if this["ratingClass"] == diff:
                                constant = (str(this["rating"]) + ("+" if this.get("ratingPlus", False) else ""))
                                jacketDesigner = this.get("jacketDesigner", "")
                                chartDesigner = this.get("chartDesigner", "")
                                break
                        break
        ## 创建基础画布
        background = self.load_image(os.path.join(IMG_PATH, "bg.png"), size=(1440, 900))
        bg_w, bg_h = background.size
        draw = ImageDraw.Draw(background)
        ## 顶部栏背景
        top_bar_bg = self.load_image(os.path.join(IMG_PATH, "topbar", "top_bar_bg.png"))
        top_bar_right = self.load_image(os.path.join(IMG_PATH, "topbar", "top_bar_bg_right.png"))
        background.paste(top_bar_bg, (0, 0), top_bar_bg)
        background.paste(top_bar_right, (bg_w - top_bar_right.width, 0), top_bar_right)
        ## 用户名与课程横幅
        course_banner = self.load_image(os.path.join(IMG_PATH, "banner", "26.png"), size=(350, top_bar_bg.height - 20))
        background.paste(course_banner, (400, 0), course_banner)
        self.draw_text_with_shadow(
            draw, (550 - len(player_name) // 2 * 15, 5), player_name, self.get_font(30), 
            (255, 255, 255), (0, 0, 0, 128)
        )
        ## 头像框
        #avatar_border = self.load_image(os.path.join(IMG_PATH, "topbar", "char_icon_border.png"), size=(120, 120))
        #background.paste(avatar_border, (680, -25), avatar_border)
        ## 排行榜框
        hash_mark_box = self.load_image(os.path.join(IMG_PATH, "topbar", "usercell_shape_bg.png"), size=(220, 165))
        background.paste(hash_mark_box, (653, -53), hash_mark_box)
        ## 头像
        avatar_icon = self.load_image(os.path.join(PARENT_DIR, "ArkanaBundler\\assets\\char", avatar_image), size=(110, 110))
        background.paste(avatar_icon, (680, -25), avatar_icon)
        ## 排行标记与数值
        hash_mark = self.load_image(os.path.join(IMG_PATH, "topbar", "hash.png"), size=(15, 15))
        background.paste(hash_mark, (785, 3), hash_mark)
        self.draw_text_with_shadow(
            draw, (798, -2), hash_number, self.get_font(20), 
            (255, 255, 255), (0, 0, 0, 128)
        )
        ## 结果文本
        self.draw_text_with_shadow(
            draw, (20, 2), "© Swiro", self.get_font(30), 
            (0, 0, 0), (255, 255, 255, 180)
        )
        ## 同步标记
        sync_mark = self.load_image(os.path.join(IMG_PATH, "top_button_settings.png"), size=(100, top_bar_bg.height - 20))
        background.paste(sync_mark, (210, 0), sync_mark)
        sync_mark = self.load_image(os.path.join(IMG_PATH, "topbar", "cloud_sync.png"), size=(55, 55), alpha=True)
        background.paste(sync_mark, (230, -5), sync_mark)
        self.draw_text_with_shadow(
            draw, (235, 10), "最近", self.get_font(22), 
            (255, 255, 255), (0, 0, 0, 128)
        )
        ## 残片与记忆源点
        fragment_bg = self.load_image(os.path.join(IMG_PATH, "frag_diamond_topplus.png"), size=(115, top_bar_bg.height - 20))
        memory_bg = self.load_image(os.path.join(IMG_PATH, "memory_diamond.png"), size=(115, top_bar_bg.height - 20))
        background.paste(fragment_bg, (1050, 0), fragment_bg)
        self.draw_text_with_shadow(
            draw, (1100, 15), "-", self.get_font(22), 
            (255, 255, 255), (0, 0, 0, 128)
        )
        self.draw_text_with_shadow(
            draw, (990, 10), "残片", self.get_font(22), 
            (0, 0, 0), (255, 255, 255)
        )
        background.paste(memory_bg, (1300, 0), memory_bg)
        self.draw_text_with_shadow(
            draw, (1350, 15), "-", self.get_font(22), 
            (173, 216, 230), (0, 0, 0, 128)  # 浅蓝色
        )
        self.draw_text_with_shadow(
            draw, (1200, 10), "虚实构想", self.get_font(22), 
            (0, 0, 0), (255, 255, 255)
        )
        ## 主背景横幅
        main_banner = self.load_image(os.path.join(IMG_PATH, "res_banner.png"), size=(1440, 700))
        background.paste(main_banner, (0, 100), main_banner)
        ## 其他信息
        self.draw_text_with_shadow(
            draw, (25, 120), "最近游玩记录", self.get_font(30, True), 
            (255, 255, 255), (0, 0, 0, 180)
        )
        self.draw_text_with_shadow(
            draw, (25, 150), "画师：" + jacketDesigner, self.get_font(30, True), 
            (255, 255, 255), (0, 0, 0, 180)
        )
        self.draw_text_with_shadow(
            draw, (25, 180), "谱师：" + chartDesigner, self.get_font(30, True), 
            (255, 255, 255), (0, 0, 0, 180)
        )
        ## 歌曲名与艺术家
        self.draw_text_with_shadow(
            draw, (background.width // 2 - len(song_name) * 12, 120), song_name, self.get_font(48, True), 
            (255, 255, 255), (0, 0, 0, 180)
        )
        self.draw_text_with_shadow(
            draw, (background.width // 2 - len(artist) * 4, 180), artist, self.get_font(30, True), 
            (255, 255, 255), (0, 0, 0, 180)
        )
        ## 角色立绘
        character = self.load_image(os.path.join(PARENT_DIR, "ArkanaBundler\\assets\\char\\1080", character_imgae), size=(1350, 1350))
        background.paste(character, (bg_w  // 3 + 120, 50), character)
        ## 潜力值
        potential_border = self.load_image(os.path.join(IMG_PATH, "rating", rating_box_img), size=(65, 65))
        background.paste(potential_border, (750, 30), potential_border)
        self.draw_text_with_shadow(
            draw, (780 - len(potential) * 5, 48), potential, self.get_font(21), 
                (255, 255, 255), (0, 0, 0, 128), shadow_offset=(-2, -2)
        )
        ## 底部按钮
        background = self.load_processed_image(background, os.path.join(IMG_PATH, "back.png"), (0, 826), (240, 76))
        self.draw_text_with_shadow(
            draw, (80, 836), "返回", self.get_font(25), 
            (118, 126, 140), (0, 0, 0)
        )
        background = self.load_processed_image(background, os.path.join(IMG_PATH, "mid_button.png"), (625, 826), (240, 76))
        self.draw_text_with_shadow(
            draw, (715, 836), "分享", self.get_font(25), 
            (118, 126, 140), (0, 0, 0)
        )
        background = self.load_processed_image(background, os.path.join(IMG_PATH, "retry.png"), (1200, 826), (240, 76))
        self.draw_text_with_shadow(
            draw, (1310, 836), "重试", self.get_font(25), 
            (118, 126, 140), (0, 0, 0)
        )
        # 曲绘
        illustration = self.load_image(os.path.join(this_illustration_path), size=(400, 400))
        background.paste(illustration, (50, 350), illustration)
        ## 难度与MAX RECALL
        max_recall_bg = self.load_image(os.path.join(IMG_PATH, f"max-recall-{difficulty.lower()}.png"), size=(300, 84))
        background.paste(max_recall_bg, (10, 250), max_recall_bg)
        ## 难度数值
        draw.text((50, 270), constant, font=self.get_font(33), 
                  fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0))  
        self.draw_text_with_shadow(
            draw, (120, 265), difficulty, self.get_font(23), 
            (70, 56, 88), (0, 0, 0, 128)
        )
        ## MAX RECALL文本 -> 似乎拿不到，修改为查分时间
        self.draw_text_with_shadow(
            draw, (120, 295), "TIME", self.get_font(22), 
            (70, 56, 88), (0, 0, 0, 128)
        )
        self.draw_text_with_shadow(
            draw, (180, 295), max_recall, self.get_font(22), 
            (70, 56, 88), (0, 0, 0, 128)
        )
        ## 清除类型标识
        clear_type = self.load_image(os.path.join(IMG_PATH, "clearType", clear_type_imgge), size=(600, 65))
        background.paste(clear_type, (420, 270), clear_type)
        ## HP条
        hp_base = self.load_image(os.path.join(IMG_PATH, "hpBar", "hp_base.png"), size=(32, 400))
        try:
            hp_bar = self.load_image(os.path.join(IMG_PATH, "hpBar", "hp_bar_clear.png"), size=(32, int(int(hp_value) * 4)))
        except:
            hp_bar = self.load_image(os.path.join(IMG_PATH, "hpBar", "hp_bar_clear.png"), size=(32, 4))
        hp_grid = self.load_image(os.path.join(IMG_PATH, "hpBar", "hp_grid.png"), size=(32, 400))
        background.paste(hp_base, (450, 350), hp_base)
        background.paste(hp_bar, (450, 350 + 400 - int(int(hp_value) * 4)), hp_bar)
        background.paste(hp_grid, (450, 350), hp_grid)
        ## HP数值
        self.draw_text_with_shadow(
            draw, (495 - len(hp_value) * 15, 345), hp_value, self.get_font(16), 
            (255, 255, 255), (0, 0, 0, 128)
        )
        ## 分数面板
        score_panel = self.load_image(os.path.join(IMG_PATH, "res_rating.png"), size=(525, 299))
        background.paste(score_panel, (482, 331), score_panel)
        ## 当前分数
        self.draw_text_with_shadow(
            draw, (640 - len(score_current) * 7, 365), score_current, self.get_font(60), 
            (255, 255, 255), (0, 0, 0)
        )
        ## 历史最佳与差值
        self.draw_text_with_shadow(
            draw, (705 - len(score_pb) * 3, 453), score_pb, self.get_font(25), 
            (255, 255, 255), (0, 0, 0)
        )
        self.draw_text_with_shadow(
            draw, (785 - len(score_diff) * 3, 453), score_diff, self.get_font(25), 
            (255, 255, 255), (0, 0, 0)
        )
        ## 评级
        grade_img = self.load_image(os.path.join(IMG_PATH, "grade", f"{grade}.png"), size=(180, 180))
        background.paste(grade_img, (620, 460), grade_img)
        ## PURE
        pure_icon = self.load_image(os.path.join(IMG_PATH, "pure-count.png"), size=(180, 33))
        background.paste(pure_icon, (600, 625), pure_icon)
        self.draw_text_with_shadow(
            draw, (720, 625), pure, self.get_font(20), 
            (255, 255, 255), (0, 0, 0)
        )
        self.draw_text_with_shadow(
            draw, (785, 625), pure_add, self.get_font(20), 
            (255, 255, 255), (0, 0, 0)
        )
        self.draw_text_with_shadow(
            draw, (635, 625), "PURE", self.get_font(22), 
            (255, 255, 255), (0, 0, 0)
        )
        ## FAR
        far_icon = self.load_image(os.path.join(IMG_PATH, "far-count.png"), size=(180, 33))
        background.paste(far_icon, (600, 665), far_icon)
        self.draw_text_with_shadow(
            draw, (720, 665), far, self.get_font(20), 
            (255, 255, 255), (0, 0, 0)
        )
        self.draw_text_with_shadow(
            draw, (640, 665), "FAR", self.get_font(22), 
            (255, 255, 255), (0, 0, 0)
        )
        ## LOST
        lost_icon = self.load_image(os.path.join(IMG_PATH, "lost-count.png"), size=(180, 33))
        background.paste(lost_icon, (600, 705), lost_icon)
        self.draw_text_with_shadow(
            draw, (720, 705), lost, self.get_font(20), 
            (255, 255, 255), (0, 0, 0)
        )
        self.draw_text_with_shadow(
            draw, (635, 705), "LOST", self.get_font(22), 
            (255, 255, 255), (0, 0, 0)
        )
        ## 保存图片
        background.convert("RGB").save(OUTPUT_PATH, quality=95)
        #background.save(OUTPUT_PATH)
        LOG.info(f"图片已生成至: {OUTPUT_PATH}")
        try:
            if hasattr(msg, "group_id"):
                await self.api.post_group_msg(msg.group_id, rtf=MessageChain(BotImage(OUTPUT_PATH)))
            else:
                await self.api.post_private_msg(msg.user_id, rtf=MessageChain(BotImage(OUTPUT_PATH)))
        except Exception as e:
            LOG.error(f"图片生成失败: {str(e)}")
            await msg.reply(text="成绩卡片生成失败，请稍后再试")