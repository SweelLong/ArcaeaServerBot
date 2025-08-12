import glob
from ncatbot.plugin import BasePlugin
from ncatbot.core.message import BaseMessage
from ncatbot.core import MessageChain, At
from ncatbot.core import Image as BotImage
from ncatbot.utils import get_log
import os
import sqlite3
import json
import random
from PIL import Image
LOG = get_log("AiChan")
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) 
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(BASE_DIR)))  
AI_CHAN_IMG_PATH = os.path.join(BASE_DIR, "src\\ai-chan.png")
AI_CHAN_TEXT_PATH = os.path.join(BASE_DIR, "src\\AiChan.json")
OUTPUT_PATH = os.path.join(BASE_DIR, "output.png")
DATABASE_PATH = os.path.join(PARENT_DIR, "ArkanaServer\\database\\arcaea_database.db")
ILLUSTRATION_PATH = [
    # 第一个位置的songlist优先级最高，请确保该songlist的内容最新最完整
    os.path.join(PARENT_DIR, "ArkanaServer\\database\\songs\\"),  # 曲绘来源路径1
    os.path.join(PARENT_DIR, "ArkanaBundler\\assets\\songs\\")  # 曲绘来源路径2
]
class AiChan(BasePlugin):
    name = "AiChan"
    version = "1.0.0"
    author = "Swiro"
    description = "Ai酱推荐歌曲"
    dependencies = {}

    def get_diff_str(self, difficulty: int) -> str:
        """获取难度对应的字符串"""
        if difficulty == 0:
            return "PAST"
        elif difficulty == 1:
            return "PRESENT"
        elif difficulty == 2:
            return "FUTURE"
        elif difficulty == 3:
            return "BEYOND"
        elif difficulty == 4:
            return "ETERNAL"

    def get_diff_constant(self, difficulty: int) -> str:
        """获取难度对应的定数"""
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

    async def AiChan(self, msg: BaseMessage):
        """Ai酱推荐歌曲"""
        random_text = random.choice(self.aichan_text['ai_chan'])
        self.db_conn.row_factory = sqlite3.Row
        cursor = self.db_conn.cursor()
        cursor.execute("""SELECT * 
                       FROM best_score 
                       NATURAL JOIN (SELECT user_id, email FROM user)
                       NATURAL JOIN (SELECT song_id, name AS song_name, rating_pst, rating_prs, rating_ftr, rating_byn, rating_etr FROM chart)
                       WHERE email=?
                       ORDER BY random() LIMIT 1""", (str(msg.user_id) + '@qq.com', ))
        info = cursor.fetchone()
        if info is None:
            return await msg.reply("Ai酱找不到你的分数信息，无法为你推荐呢~")
        random_text = random_text.replace("“songName”", info['song_name'])
        random_text = random_text.replace("difficulty", self.get_diff_str(info['difficulty']))
        random_text = random_text.replace("constant，", str(round(info[self.get_diff_constant(info['difficulty'])] / 10, 1)))
        random_text = random_text.replace("score", str(info['score']))
        song_id = info['song_id']
        song_jacket_path = ""
        for path in ILLUSTRATION_PATH:
            if os.path.exists(os.path.join(path, f"dl_{song_id}")):
                jacket_path = glob.glob(os.path.join(path, f"dl_{song_id}", "*.[jJ][pP][gG]"))
                if jacket_path:
                    song_jacket_path = jacket_path[0]
                    break
            elif os.path.exists(os.path.join(path, song_id)):
                jacket_path = glob.glob(os.path.join(path, song_id, "*.[jJ][pP][gG]"))
                if jacket_path:
                    song_jacket_path = jacket_path[0]
                    break
        try:
            with Image.open(song_jacket_path) as jacket_img, Image.open(AI_CHAN_IMG_PATH) as ai_chan_img:
                # 强制将Ai酱图片转换为RGBA模式，解决透明通道问题
                ai_chan_img = ai_chan_img.convert("RGBA")
                
                # 获取主图片的尺寸
                jacket_width, jacket_height = jacket_img.size
                # 计算要添加的图片的合适尺寸
                max_width = int(jacket_width * 0.25)
                max_height = int(jacket_height * 0.25)
                # 保持比例缩放要添加的图片
                ai_width, ai_height = ai_chan_img.size
                scale = min(max_width / ai_width, max_height / ai_height)
                new_ai_width = int(ai_width * scale)
                new_ai_height = int(ai_height * scale)
                ai_chan_img = ai_chan_img.resize((new_ai_width, new_ai_height))
                # 计算放置位置
                margin = 10
                x = jacket_width - new_ai_width - margin
                y = jacket_height - new_ai_height - margin
                # 创建一个副本，避免修改原图
                # 如果主图不是RGBA模式，转换为RGBA以支持透明叠加
                if jacket_img.mode != "RGBA":
                    jacket_img = jacket_img.convert("RGBA")
                result_img = jacket_img.copy()
                # 将小图片粘贴到主图片上，使用RGBA的alpha通道作为掩码
                result_img.paste(ai_chan_img, (x, y), ai_chan_img)
                # 转换回RGB模式保存，避免透明通道导致的兼容问题
                result_img.convert("RGB").save(OUTPUT_PATH, quality=95)
                LOG.info(f"图片已成功保存到: {OUTPUT_PATH}")
                message = MessageChain([
                    At(msg.user_id),
                    BotImage(OUTPUT_PATH),
                    random_text
                ])
                if hasattr(msg, "group_id"):
                    return await self.api.post_group_msg(msg.group_id, rtf=message)
                else:
                    return await self.api.post_private_msg(msg.user_id, rtf=message)
                
        except Exception as e:
            LOG.error(f"处理图片时出错: {str(e)}")
            return await msg.reply("出错了，请稍后再试~")
    async def on_load(self):
        """插件加载时初始化配置和注册命令"""
        self.db_conn = sqlite3.connect(DATABASE_PATH)
        self.aichan_text = json.load(open(AI_CHAN_TEXT_PATH, "r", encoding="utf-8"))
        self.register_user_func(
            "/aichan", 
            self.AiChan, 
            prefix="/aichan", 
            description="Ai酱推荐歌曲",
            usage="/aichan",
            examples=["/aichan"],
            tags=["user"]
        )
        self.images = []
        LOG.info(f"{self.name} 插件已加载，版本: {self.version}")