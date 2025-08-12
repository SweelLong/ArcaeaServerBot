from ncatbot.plugin import BasePlugin
from ncatbot.core.message import BaseMessage
from ncatbot.core import MessageChain
from ncatbot.core import Image as BotImage
from ncatbot.utils import get_log
import os
import sqlite3
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
from Plugins.Chart.ArcaeaChartRender.render import Render
from Plugins.Chart.ArcaeaChartRender.utils import fetch_song_info

# ======================== 全局配置 ========================
LOG = get_log("Chart")  # 日志对象
SAVES_DIR = os.path.join(BASE_DIR, "saves")  # 图片保存目录
os.makedirs(SAVES_DIR, exist_ok=True)  # 确保保存目录存在

# 数据库路径
USER_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(BASE_DIR))), 
                             "ArkanaServer\\web\\user.db")

# 歌曲资源路径（优先查找第一个）
SONGS_PATH = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(BASE_DIR))), "ArkanaServer\\database\\songs\\"),
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(BASE_DIR))), "ArkanaBundler\\assets\\songs\\")
]

# 第一个songlist路径（用于验证歌曲ID）
SONGLIST_PATH = os.path.join(SONGS_PATH[0], "songlist") if os.path.exists(SONGS_PATH[0]) else None

class Chart(BasePlugin):
    name = "Chart"
    version = "1.0.1"  # 版本更新
    author = "Swiro"
    description = """
    Arcaea谱面渲染插件
    指令格式: /chart [歌曲ID/别名(可含空格)] [难度(0-4)]
    示例: /chart xenolith 2 或 /chart "我的 歌曲" 2
    难度对应: 0=PAST, 1=PRESENT, 2=FUTURE, 3=BEYOND, 4=ETERNAL
    """
    dependencies = {}

    # ======================== 辅助函数 ========================
    @staticmethod
    def parse_command(args: list) -> tuple:
        """解析指令参数，返回(song_identifier, difficulty)"""
        if len(args) != 2:
            return None, None
        
        song_identifier = args[0].strip()
        try:
            difficulty = int(args[1].strip())
            if difficulty < 0 or difficulty > 4:
                return None, None
            return song_identifier, difficulty
        except ValueError:
            return None, None

    @staticmethod
    def is_valid_song_id(song_id: str) -> bool:
        """检查歌曲ID是否在songlist中存在"""
        if not SONGLIST_PATH or not os.path.exists(SONGLIST_PATH):
            LOG.error("songlist文件不存在，无法验证歌曲ID")
            return False
        
        try:
            with open(SONGLIST_PATH, "r", encoding="utf-8") as f:
                songlist = json.load(f)["songs"]
                return any(song["id"] == song_id for song in songlist)
        except Exception as e:
            LOG.error(f"验证歌曲ID失败: {e}")
            return False

    @staticmethod
    def get_song_id_from_alias(alias: str) -> str:
        """从别名查询歌曲ID（查询song_alias表）"""
        if not os.path.exists(USER_DB_PATH):
            LOG.error(f"数据库不存在: {USER_DB_PATH}")
            return None
        
        try:
            with sqlite3.connect(USER_DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                # 精确匹配别名（支持含空格的别名）
                cursor.execute("""
                    SELECT song_id FROM song_alias 
                    WHERE song_name = ?
                """, (alias,))  # 去掉LIKE模糊匹配，避免误匹配
                result = cursor.fetchone()
                return result["song_id"] if result else None
        except Exception as e:
            LOG.error(f"查询别名失败: {e}")
            return None

    @staticmethod
    def find_song_folder(song_id: str) -> str:
        """查找歌曲文件夹（优先第一个SONGS_PATH）"""
        for base_path in SONGS_PATH:
            if not os.path.exists(base_path):
                continue
            possible_folders = [
                os.path.join(base_path, song_id)
            ]
            for folder in possible_folders:
                if os.path.isdir(folder):
                    return folder
        return None

    @staticmethod
    def get_aff_path(song_folder: str, difficulty: int) -> str:
        """获取对应难度的.aff文件路径"""
        aff_path = os.path.join(song_folder, f"{difficulty}.aff")
        return aff_path if os.path.exists(aff_path) else None

    @staticmethod
    def get_cover_path(song_folder: str) -> str:
        """获取文件夹中第一个jpg封面图片"""
        for file in os.listdir(song_folder):
            if file.lower().endswith(".jpg") and not file.startswith("."):
                cover_path = os.path.join(song_folder, file)
                return cover_path if os.path.isfile(cover_path) else None
        return None

    # ======================== 核心逻辑 ========================
    def generate_chart_image(self, song_id: str, difficulty: int) -> str:
        """生成或获取已存在的谱面图片"""
        save_path = os.path.join(SAVES_DIR, f"{song_id}_{difficulty}.png")
        if os.path.exists(save_path):
            LOG.info(f"图片已存在: {save_path}")
            return save_path, None

        song_folder = self.find_song_folder(song_id)
        if not song_folder:
            LOG.error(f"未找到歌曲文件夹: {song_id}")
            return None, "歌曲文件夹不存在"

        aff_path = self.get_aff_path(song_folder, difficulty)
        cover_path = self.get_cover_path(song_folder)
        if not aff_path:
            LOG.error(f"未找到aff文件: {song_id}_{difficulty}.aff")
            return None, "aff文件不存在"
        if not cover_path:
            LOG.error(f"未找到封面图片: {song_folder}")
            return None, "封面图片不存在"

        try:
            song_info = fetch_song_info(SONGLIST_PATH, song_id) if SONGLIST_PATH else None
        except Exception as e:
            LOG.warning(f"获取歌曲信息失败，使用默认值: {e}")
            song_info = None

        try:
            render = Render(
                aff_path=aff_path,
                cover_path=cover_path,
                song=song_info,
                difficulty=difficulty,
                constant=0.0
            )
            render.save(save_path)
            LOG.info(f"图片生成成功: {save_path}")
            return save_path, None
        except Exception as e:
            LOG.error(f"渲染图片失败: {e}")
            if os.path.exists(save_path):
                os.remove(save_path)
            return None, "渲染失败"

    # ======================== 插件入口 ========================
    async def on_load(self):
        """插件初始化，注册指令"""
        self.register_user_func(
            "/chart",
            self.handle_chart,
            prefix="/chart",
            description="生成Arcaea谱面渲染图",
            usage="/chart [歌曲ID/别名(可含空格)] [难度(0-4)]，难度对应：0=PAST,1=PRESENT,2=FUTURE,3=BEYOND,4=ETERNAL",
            examples=["/chart xenolith 2", "/chart 我的 歌曲 2"],  # 支持含空格的别名示例
            tags=["user"]
        )
        LOG.info(f"{self.name} 插件已加载，版本: {self.version}")

    async def handle_chart(self, msg: BaseMessage):
        """处理/chart指令（修复含空格的参数解析）"""
        # 关键修复：使用maxsplit=2限制分割次数，确保歌曲标识（可能含空格）被正确提取
        # 格式：["/chart", "歌曲标识(可含空格)", "难度"] → [1:] → ["歌曲标识", "难度"]
        args = msg.raw_message.strip().split(maxsplit=2)[1:]  
        song_identifier, difficulty = self.parse_command(args)
        if not song_identifier or difficulty is None:
            return await msg.reply("指令格式错误！请使用: /chart [歌曲ID/别名(可含空格)] [难度(0-4)]")

        # 确定歌曲ID
        song_id = song_identifier
        if not self.is_valid_song_id(song_id):
            LOG.info(f"尝试从别名查询: {song_identifier}")
            song_id = self.get_song_id_from_alias(song_identifier)
            if not song_id:
                return await msg.reply(f"未找到歌曲: {song_identifier}（请检查ID或别名是否正确）")

        returnimginfo = self.generate_chart_image(song_id, difficulty)
        image_path, error_msg = returnimginfo
        if not image_path:
            return await msg.reply(f"谱面图片生成失败：{error_msg}")

        try:
            if hasattr(msg, "group_id"):
                return await self.api.post_group_msg(msg.group_id, rtf=MessageChain(BotImage(image_path)))
            else:
                return await msg.reply(BotImage(image_path))
        except Exception as e:
            LOG.error(f"发送图片失败: {e}")
            return await msg.reply("图片发送失败，请稍后再试")