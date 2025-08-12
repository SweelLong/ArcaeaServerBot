import datetime
import json
import os
import glob
import sqlite3
import ncatbot
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import BaseMessage
from ncatbot.utils import get_log

LOG = get_log("Vote")
bot = CompatibleEnrollment

# 路径设置
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) 
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(BASE_DIR)))  
DATABASE_PATH = os.path.join(PARENT_DIR, "ArkanaServer\\web\\user.db")
GAMEDB_PATH = os.path.join(PARENT_DIR, "ArkanaServer\\database\\arcaea_database.db")
SLST_PATH = os.path.join(PARENT_DIR, "ArkanaServer\\database\\songs\\songlist")
ILLUSTRATION_PATH = [
    # 第一个位置的songlist优先级最高，请确保该songlist的内容最新最完整
    os.path.join(PARENT_DIR, "ArkanaServer\\database\\songs\\"),  # 曲绘来源路径1
    os.path.join(PARENT_DIR, "ArkanaBundler\\assets\\songs\\")  # 曲绘来源路径2
]

class Vote(BasePlugin):
    name = "Vote"
    version = "1.0.0"
    author = "Swiro"
    description = "为歌曲投票插件"
    dependencies = {}

    def _load_songlist(self):
        """加载歌曲列表并将歌曲ID添加到投票表"""
        try:
            if not os.path.exists(SLST_PATH):
                LOG.error(f"歌曲列表文件不存在: {SLST_PATH}")
                return
            with open(SLST_PATH, 'r', encoding='utf-8') as f:
                songlist_data = json.load(f)
            # 获取所有歌曲信息
            songs = songlist_data.get('songs', [])
            if not songs:
                LOG.warning("歌曲列表中没有找到歌曲数据")
                return
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            # 加载歌曲ID到投票表
            for song in songs:
                song_id = str(song.get('id', ''))
                if not song_id:
                    continue
                # 检查歌曲是否已存在于投票表中
                cursor.execute("SELECT song_id FROM song_vote WHERE song_id = ?", (song_id,))
                if not cursor.fetchone():
                    # 不存在则添加
                    cursor.execute("INSERT INTO song_vote (song_id, vote_number) VALUES (?, 0)", (song_id,))
                    LOG.info(f"添加新歌曲到投票表: {song_id}")
            conn.commit()
            conn.close()
            LOG.info(f"成功加载 {len(songs)} 首歌曲到投票系统")
            # 加载曲绘路径
            self._load_jacket_paths(songs)
        except Exception as e:
            LOG.error(f"加载歌曲列表失败: {str(e)}")

    def _load_jacket_paths(self, songs):
        """加载所有歌曲的曲绘路径"""
        for song in songs:
            song_id = str(song.get('id', ''))
            if not song_id:
                continue
            for path in ILLUSTRATION_PATH:
                # 检查可能的曲绘路径
                if os.path.exists(os.path.join(path, f"dl_{song_id}")):
                    jacket_path = glob.glob(os.path.join(path, f"dl_{song_id}", "*.[jJ][pP][gG]"))
                    if jacket_path:
                        self.song_jacket_path[song_id] = jacket_path[0]
                        break
                elif os.path.exists(os.path.join(path, song_id)):
                    jacket_path = glob.glob(os.path.join(path, song_id, "*.[jJ][pP][gG]"))
                    if jacket_path:
                        self.song_jacket_path[song_id] = jacket_path[0]
                        break
    
    def get_song_id_by_alias(self, identifier: str) -> str:
        """通过歌曲ID或别名获取对应的song_id"""
        if not identifier:
            return None
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            # 先尝试通过song_id查找
            cursor.execute('''
            SELECT DISTINCT song_id FROM song_alias WHERE song_id = ?
            ''', (identifier,))
            result = cursor.fetchone()
            if result:
                conn.close()
                return result[0]
            # 再尝试通过别名查找
            cursor.execute('''
            SELECT DISTINCT song_id FROM song_alias WHERE song_name = ?
            ''', (identifier,))
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else None
        except Exception as e:
            LOG.error(f"通过别名获取song_id失败: {str(e)}")
            return None
        
    async def _vote_for_song(self, qq_id, song_id, count=1):
        """为歌曲投票，返回投票结果"""
        if count <= 0:
            return False, "投票数量必须大于0"
            
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            
            # 检查歌曲是否存在
            cursor.execute("SELECT song_id FROM song_vote WHERE song_id = ?", (song_id,))
            if not cursor.fetchone():
                conn.close()
                return False, f"歌曲ID不存在，请使用/aa info 别名查找正确的歌曲ID"
            
            # 检查用户是否有足够的投票券
            cursor.execute("SELECT vote_ticket FROM user_item WHERE qq_id = ?", (qq_id,))
            result = cursor.fetchone()
            if not result or result[0] < count:
                conn.close()
                return False, "您的投票券不足"
            
            # 扣除投票券
            cursor.execute("""
            UPDATE user_item 
            SET vote_ticket = vote_ticket - ? 
            WHERE qq_id = ?
            """, (count, qq_id))
            
            # 增加歌曲票数
            cursor.execute("""
            UPDATE song_vote 
            SET vote_number = vote_number + ? 
            WHERE song_id = ?
            """, (count, song_id))
            
            conn.commit()
            conn.close()
            return True, f"成功为歌曲 {song_id} 投票 {count} 次\n还剩 {result[0] - count} 张投票券"
            
        except Exception as e:
            LOG.error(f"投票失败: {str(e)}")
            return False, f"投票失败: {str(e)}"

    async def _get_vote_info(self, song_id):
        """获取歌曲的投票信息"""
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            
            cursor.execute("SELECT vote_number FROM song_vote WHERE song_id = ?", (song_id,))
            result = cursor.fetchone()
            
            conn.close()
            
            if not result:
                return None, f"歌曲ID不存在，请使用/aa info 别名查找正确的歌曲ID"
                
            jacket_path = self.song_jacket_path.get(song_id, None)
            return {
                "song_id": song_id,
                "vote_count": result[0],
                "jacket_path": jacket_path
            }, "success"
            
        except Exception as e:
            LOG.error(f"获取投票信息失败: {str(e)}")
            return None, f"获取投票信息失败: {str(e)}"

    async def _get_vote_rank(self, limit=10):
        """获取歌曲投票排名"""
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            
            cursor.execute("""
            SELECT song_id, vote_number 
            FROM song_vote 
            ORDER BY vote_number DESC 
            LIMIT ?
            """, (limit,))
            
            results = cursor.fetchall()
            conn.close()
            
            return results, "success"
            
        except Exception as e:
            LOG.error(f"获取投票排名失败: {str(e)}")
            return None, f"获取投票排名失败: {str(e)}"

    async def handle_vote_command(self, msg: BaseMessage):
        """处理投票相关命令"""
        content = msg.raw_message.split(maxsplit=2)
        parts = list(content)
        LOG.info(f"收到投票命令: {content}, {len(parts)}")
        if len(parts) <= 1:
            return await msg.reply("投票命令格式错误，请使用:\n"
                                 "/vote for [歌曲id/别名] [数量(默认1)] - 为歌曲投票，数量默认为1\n"
                                 "/vote info [歌曲id/别名] - 查询歌曲的投票数量\n"
                                 "/vote rank [数量(默认10)] - 获取歌曲投票排名")
        sub_command = parts[1]
        qq_id = msg.user_id
        if sub_command == "for":
            if len(parts) < 2:
                return await msg.reply("请指定歌曲ID或别名，格式: /vote for [歌曲id/别名] [数量(默认1)]")
            pp = parts[2].rsplit(maxsplit=1)
            identifier = pp[0]
            count = int(pp[1]) if len(pp) == 2 and pp[1].isdigit() else 1
            # 通过别名获取真实song_id
            song_id = self.get_song_id_by_alias(identifier)
            if not song_id:
                return await msg.reply(f"未找到ID或别名为 {identifier} 的歌曲")
            success, message = await self._vote_for_song(qq_id, song_id, count)
            if success:
                prize = count * 10
                with sqlite3.connect(GAMEDB_PATH, timeout=30) as c:
                    c.execute("UPDATE user SET ticket=ticket+? WHERE email=?", (prize, str(qq_id) + "@qq.com"))
                    c.commit()
            return await msg.reply(message + f"\n奖励：{prize}枚虚实构想")
            
        elif sub_command == "info":
            if len(parts) < 2:
                return await msg.reply("请指定歌曲ID或别名，格式: /vote info [歌曲id/别名]")
                
            identifier = parts[2]
            # 通过别名获取真实song_id
            song_id = self.get_song_id_by_alias(identifier)
            if not song_id:
                return await msg.reply(f"未找到ID或别名为 {identifier} 的歌曲")
                
            info, message = await self._get_vote_info(song_id)
            
            if info:
                reply_msg = ncatbot.core.MessageChain([ncatbot.core.At(msg.user_id)])
                if info['jacket_path']:
                    reply_msg += ncatbot.core.Image(info['jacket_path'])
                reply_msg += f"歌曲 {song_id} 的投票信息如下：\n",
                reply_msg += f"当前票数: {info['vote_count']}\n",
                reply_msg += f"查询时间: {str(datetime.datetime.now())}"

                return await msg.api.post_group_msg(group_id=msg.group_id, rtf=reply_msg)
            else:
                return await msg.reply(message)
                
        elif sub_command == "rank":
            limit = 10
            try:
                limit = int(parts[2])
            finally:
                rank_list, message = await self._get_vote_rank(limit)
                if rank_list:
                    reply_msg = f"歌曲投票排名 (前{limit}名):\n"
                    for i, (song_id, vote_count) in enumerate(rank_list, 1):
                        reply_msg += f"{i}. {song_id} : {vote_count}票\n"
                    reply_msg += f"查询时间: {str(datetime.datetime.now())}\n(时间有限暂无图片展示)"
                    return await msg.reply(reply_msg)
                else:
                    return await msg.reply(message)
                
        else:
            return await msg.reply("未知的投票命令，请使用:\n"
                                 "/vote for [歌曲id] [数量(默认1)] - 为歌曲投票\n"
                                 "/vote info [歌曲id] - 查询歌曲的投票数量\n"
                                 "/vote rank - 获取歌曲投票排名")

    async def on_load(self):
        """插件加载时执行的操作"""
        self.song_jacket_path = {}  # 存储歌曲id到曲绘路径的映射
        # 注册投票命令
        self.register_user_func(
            "/vote",
            self.handle_vote_command,
            description="为歌曲投票插件",
            prefix="/vote",
            usage="""
            /vote for [歌曲id] [数量(默认1)] - 为歌曲投票，数量默认为1
            /vote info [歌曲id] - 查询歌曲的投票数量
            /vote rank [数量(默认10)] - 获取歌曲投票排名，数量默认为10
            """,
            examples=[
                "/vote for 123456",
                "/vote for 123456 5",
                "/vote info 123456",
                "/vote rank 20"
            ],
            tags=["user"]
        )
        
        # 加载歌曲列表和曲绘
        self._load_songlist()
        
        LOG.info(f"{self.name} 插件已加载，版本: {self.version}")