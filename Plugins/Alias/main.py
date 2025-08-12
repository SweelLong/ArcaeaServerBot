from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import BaseMessage
from ncatbot.core import MessageChain, Image
from ncatbot.utils import get_log
import os
import sqlite3
import json
from typing import List, Tuple, Optional

LOG = get_log("Alias")
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) 
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(BASE_DIR)))  
DATABASE_PATH = os.path.join(PARENT_DIR, "ArkanaServer\\web\\user.db")
SLST_PATH = os.path.join(PARENT_DIR, "ArkanaServer\\database\\songs\\songlist")

class Alias(BasePlugin):
    name = "Alias"
    version = "1.0.0"
    author = "Swiro"
    description = "单曲别名管理插件，支持添加、删除和查询歌曲别名"
    dependencies = {}

    async def load_songlist(self):
        """从songlist文件加载歌曲信息到数据库"""
        if not self.db_conn:
            LOG.error("数据库连接未初始化，无法加载歌曲列表")
            return
        try:
            # 读取songlist文件
            with open(SLST_PATH, 'r', encoding='utf-8') as f:
                songlist_data = json.load(f)
            # 获取songs键下的所有内容
            songs = songlist_data.get('songs', [])
            if not songs:
                LOG.warning("songlist中未找到歌曲数据")
                return
            cursor = self.db_conn.cursor()
            count = 0
            # 遍历所有歌曲
            for song in songs:
                song_id = song.get('id')
                title_localized = song.get('title_localized', {})
                if not song_id or not title_localized:
                    continue
                # 处理所有本地化标题
                for lang, name in title_localized.items():
                    if not name:
                        continue
                    try:
                        # 插入数据，如果已存在则跳过
                        cursor.execute('''
                        INSERT OR IGNORE INTO song_alias (song_id, song_name)
                        VALUES (?, ?)
                        ''', (song_id, name))
                        count += 1
                    except Exception as e:
                        LOG.error(f"插入歌曲数据失败 (ID: {song_id}, Name: {name}): {str(e)}")
            self.db_conn.commit()
            LOG.info(f"成功加载 {count} 条歌曲信息到数据库")
        except Exception as e:
            LOG.error(f"加载songlist失败: {str(e)}")

    async def on_load(self):
        """插件加载时初始化配置和注册命令"""
        self.db_conn = sqlite3.connect(DATABASE_PATH)
        # 注册指令
        self.register_user_func(
            "/aa add", 
            self.alias_add, 
            prefix="/aa add", 
            description="为歌曲添加别名",
            usage="/aa add [歌曲ID/歌曲名] [歌曲别名]",
            examples=["/aa add 12345 我的别名", "/aa add 歌曲名称 新别名"],
            tags=["user"]
        )
        
        self.register_user_func(
            "/aa del", 
            self.alias_del, 
            prefix="/aa del", 
            description="删除歌曲别名",
            usage="/aa del [歌曲ID/歌曲名] [歌曲别名]",
            examples=["/aa del 12345 我的别名", "/aa del 歌曲名称 要删除的别名"],
            tags=["user"]
        )
        
        self.register_user_func(
            "/aa info", 
            self.alias_info, 
            prefix="/aa info", 
            description="查询歌曲的所有别名",
            usage="/aa info [歌曲ID/别名]",
            examples=["/aa info 12345", "/aa info 歌曲别名"],
            tags=["user"]
        )
        await self.load_songlist()
        self.images = []
        LOG.info(f"{self.name} 插件已加载，版本: {self.version}")

    def get_song_id(self, identifier: str) -> Optional[str]:
        """通过歌曲ID或名称获取对应的song_id"""
        if not self.db_conn or not identifier:
            return None
        try:
            cursor = self.db_conn.cursor()
            # 先尝试通过song_id查找
            cursor.execute('''
            SELECT DISTINCT song_id FROM song_alias WHERE song_id = ?
            ''', (identifier,))
            result = cursor.fetchone()
            if result:
                return result[0]
            # 再尝试通过song_name查找
            cursor.execute('''
            SELECT DISTINCT song_id FROM song_alias WHERE song_name = ?
            ''', (identifier,))
            result = cursor.fetchone()
            return result[0] if result else None
            
        except Exception as e:
            LOG.error(f"获取song_id失败: {str(e)}")
            return None

    async def alias_add(self, message: BaseMessage):
        """添加歌曲别名"""
        args = message.raw_message.split(maxsplit=3)[2:]
        if len(args) < 2:
            return await message.reply("参数不足！使用方法: /aa add [歌曲ID/歌曲名] [歌曲别名]")
        identifier = args[0]
        new_alias = args[1]
        # 获取对应的song_id
        song_id = self.get_song_id(identifier)
        if not song_id:
            return await message.reply(f"未找到ID或名称为 {identifier} 的歌曲")
        try:
            cursor = self.db_conn.cursor()
            # 检查是否已存在该别名
            cursor.execute('''
            SELECT 1 FROM song_alias WHERE song_id = ? AND song_name = ?
            ''', (song_id, new_alias))
            if cursor.fetchone():
                return await message.reply("已经添加过了哦~")
            # 添加新别名
            cursor.execute('''
            INSERT INTO song_alias (song_id, song_name)
            VALUES (?, ?)
            ''', (song_id, new_alias))
            self.db_conn.commit()
            return await message.reply(f"成功为歌曲 {song_id} 添加别名: {new_alias}")
        except Exception as e:
            LOG.error(f"添加别名失败: {str(e)}")
            return await message.reply("添加别名失败，请稍后再试")

    async def alias_del(self, message: BaseMessage):
        """删除歌曲别名"""
        args = message.raw_message.split(maxsplit=3)[2:]
        if len(args) < 2:
            return await message.reply("参数不足！使用方法: /aa del [歌曲ID/歌曲名] [歌曲别名]")
        identifier = args[0]
        alias_to_del = args[1]
        # 获取对应的song_id
        song_id = self.get_song_id(identifier)
        if not song_id:
            return await message.reply(f"未找到ID或名称为 {identifier} 的歌曲")
        try:
            cursor = self.db_conn.cursor()
            # 检查是否存在该别名
            cursor.execute('''
            SELECT 1 FROM song_alias WHERE song_id = ? AND song_name = ?
            ''', (song_id, alias_to_del))
            if not cursor.fetchone():
                return await message.reply("该别名不存在哦~") 
            # 删除别名
            cursor.execute('''
            DELETE FROM song_alias WHERE song_id = ? AND song_name = ?
            ''', (song_id, alias_to_del))
            self.db_conn.commit()
            return await message.reply(f"成功删除歌曲 {song_id} 的别名: {alias_to_del}")
        except Exception as e:
            LOG.error(f"删除别名失败: {str(e)}")
            return await message.reply("删除别名失败，请稍后再试")

    async def alias_info(self, message: BaseMessage):
        """查询歌曲的所有别名"""
        args = message.raw_message.split(maxsplit=2)[2:]
        if len(args) < 1:
            return await message.reply("参数不足！使用方法: /aa info [歌曲ID/歌曲名]")
        identifier = args[0]
        # 获取对应的song_id
        song_id = self.get_song_id(identifier)
        if not song_id:
            return await message.reply(f"未找到ID或名称为 {identifier} 的歌曲") 
        try:
            cursor = self.db_conn.cursor()
            # 查询所有别名
            cursor.execute('''
            SELECT song_name FROM song_alias WHERE song_id = ?
            ''', (song_id,))
            results = cursor.fetchall()
            if not results:
                return await message.reply(f"歌曲 {song_id} 没有任何别名")
            # 组合所有别名
            aliases = [r[0] for r in results]
            alias_text = "\n".join([f"- {alias}" for alias in aliases])
            return await message.reply(f"歌曲 {song_id} 的所有别名:\n{alias_text}")
        except Exception as e:
            LOG.error(f"查询别名失败: {str(e)}")
            return await message.reply("查询别名失败，请稍后再试")