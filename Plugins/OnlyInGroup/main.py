from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import BaseMessage
from ncatbot.utils import get_log
from ncatbot.plugin.event import Event  # 导入事件类
import sqlite3
import os

LOG = get_log("OnlyInGroup")
bot = CompatibleEnrollment

class OnlyInGroup(BasePlugin):
    name = "OnlyInGroup"
    version = "1.0.0"
    author = "Swiro"
    description = "群成员数据库管理插件，自动维护群成员状态"
    dependencies = {}
    
    def _init_db(self):
        """初始化数据库表结构"""
        db_dir = os.path.dirname(self.db_path)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            LOG.info(f"创建数据库目录: {db_dir}")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user (
            qq_group_id INTEGER,
            qq_number INTEGER,
            user_name TEXT,
            is_banned INTEGER DEFAULT 0,
            ban_reason TEXT DEFAULT "",
            PRIMARY KEY (qq_group_id, qq_number)
        )
        ''')
        conn.commit()
        conn.close()
        LOG.info(f"数据库初始化完成，路径: {self.db_path}")

    async def is_group_admin(self, group_id, user_id):
        member_info = await self.api.get_group_member_info(group_id, user_id, no_cache=False)
        return member_info["data"]["role"] in ["admin", "owner"]
    
    async def refresh_userdb(self, msg: BaseMessage):
        """刷新群成员数据库指令处理"""
        if not hasattr(msg, "group_id"):
            return await self.api.post_private_msg(
                msg.sender.user_id,
                text="此指令只能在群聊中使用"
            )
        
        is_admin = await self.is_group_admin(msg.group_id, msg.sender.user_id)
        if not is_admin:
            return await self.api.post_group_msg(
                msg.group_id,
                at=msg.sender.user_id,
                text="权限不足，只有管理员可以使用此指令"
            )
        
        group_id = msg.group_id
        try:
            members = await self.api.get_group_member_list(group_id)
            if not members or "data" not in members:
                return await self.api.post_group_msg(
                    group_id,
                    text="获取群成员列表失败"
                )
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # 先将数据库表中该群所有成员标记为退群状态
            cursor.execute('''
            UPDATE user SET is_banned = 1, ban_reason = "退群" 
            WHERE qq_group_id = ?
            ''', (group_id,))
            
            current_members = []
            for member in members["data"]:
                qq_number = int(member["user_id"])
                user_name = member["nickname"]
                current_members.append(qq_number)
                
                # 检查成员是否已在数据库中
                cursor.execute('''
                SELECT 1 FROM user 
                WHERE qq_group_id = ? AND qq_number = ?
                ''', (group_id, qq_number))
                
                if cursor.fetchone():
                    # 已存在则更新信息并解封
                    cursor.execute('''
                    UPDATE user SET user_name = ?, is_banned = 0, ban_reason = "" 
                    WHERE qq_group_id = ? AND qq_number = ?
                    ''', (user_name, group_id, qq_number))
                else:
                    # 新成员则插入数据库
                    cursor.execute('''
                    INSERT INTO user (qq_group_id, qq_number, user_name, is_banned, ban_reason)
                    VALUES (?, ?, ?, 0, "")
                    ''', (group_id, qq_number, user_name))
            
            conn.commit()
            conn.close()
            LOG.info(f"群 {group_id} 成员数据库已更新，共处理 {len(current_members)} 名成员")
            return await self.api.post_group_msg(
                group_id,
                text=f"用户数据库刷新完成，共处理 {len(current_members)} 名成员"
            )
        except Exception as e:
            LOG.error(f"刷新用户数据库失败: {str(e)}")
            return await self.api.post_group_msg(
                group_id,
                text=f"操作失败: {str(e)}"
            )
    
    async def handle_group_increase(self, data):
        """处理群成员增加事件（进群）"""
        group_id = data.get("group_id")
        user_id = data.get("user_id")
        sub_type = data.get("sub_type", "unknown")  # 入群方式：approve/invite
        
        if not group_id or not user_id:
            LOG.warning("进群事件缺少群号或用户ID")
            return
        
        # 获取用户昵称
        try:
            member_info = await self.api.get_group_member_info(group_id, user_id, no_cache=False)
            user_name = member_info["data"]["nickname"]
            print(member_info)
        except Exception as e:
            LOG.error(f"获取进群用户信息失败: {e}")
            user_name = f"用户{user_id}"
     
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT 1, ban_reason FROM user WHERE qq_group_id = ? AND qq_number = ?
                           ''', (group_id, user_id))
            result = cursor.fetchone()
            if result:
                ban_reason = result[1]
                cursor.execute('''
                UPDATE user SET user_name = ?, is_banned = 0, ban_reason = "" 
                WHERE qq_group_id = ? AND qq_number = ?
                ''', (user_name, group_id, user_id))
                if ban_reason and ban_reason.strip():
                    welcome_text = f"欢迎重新加入本群！你之前因 '{ban_reason}' 被移出，现在已恢复权限~\n查看指令请输入/help哦"
                else:
                    welcome_text = f"欢迎重新加入本群！成员 {user_name}({user_id}) 已恢复到数据库~\n查看指令请输入/help哦"
                LOG.info(f"群 {group_id} 成员 {user_name}({user_id}) 重新入群（{sub_type}）")
                await self.api.post_group_msg(
                    group_id=group_id,
                    at=user_id,
                    text=welcome_text
                )
            else:
                cursor.execute('''
                INSERT INTO user (qq_group_id, qq_number, user_name, is_banned, ban_reason)
                VALUES (?, ?, ?, 0, "")
                ''', (group_id, user_id, user_name))
                LOG.info(f"群 {group_id} 新成员 {user_name}({user_id}) 入群（{sub_type}）")
                await self.api.post_group_msg(
                    group_id=group_id,
                    at=user_id,
                    text=f"欢迎加入本群！新成员 {user_name}({user_id}) 已添加到数据库~\n查看指令请输入/help哦~"
                )
            conn.commit()
        except Exception as e:
            LOG.error(f"处理进群事件失败: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    async def handle_group_decrease(self, data):
        """处理群成员减少事件（退群）"""
        group_id = data.get("group_id")
        user_id = data.get("user_id")
        sub_type = data.get("sub_type", "unknown")  # 退群方式：leave/kick/kick_me
        
        if not group_id or not user_id:
            LOG.warning("退群事件缺少群号或用户ID")
            return
        
        # 数据库操作
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # 更新成员状态为封禁，记录退群原因
            cursor.execute('''
            UPDATE user SET is_banned = 1, ban_reason = ? 
            WHERE qq_group_id = ? AND qq_number = ?
            ''', (f"退群（{sub_type}）", group_id, user_id))
            
            if cursor.rowcount > 0:
                LOG.info(f"群 {group_id} 成员 {user_id} 退群（{sub_type}），已更新状态")
                await self.api.post_group_msg(
                    group_id=group_id,
                    text=f"成员 {user_id} 已退群（{sub_type}），数据库中已标记为封禁状态~"
                )
            conn.commit()
        except Exception as e:
            LOG.error(f"处理退群事件失败: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    async def handle_notice_event(self, event: Event):
        """统一处理所有通知事件，按子类型分发"""
        notice_data = event.data
        notice_type = notice_data.get("notice_type")
        
        # 根据通知类型分发到对应处理方法
        if notice_type == "group_increase":
            await self.handle_group_increase(notice_data)
        elif notice_type == "group_decrease":
            await self.handle_group_decrease(notice_data)
        # 可在此扩展其他通知事件（如禁言、管理员变动等）
    
    async def on_load(self):
        """插件加载时初始化"""
        # 数据库路径设置
        self.BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        self.PARENT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(self.BASE_DIR)))
        self.db_path = os.path.join(self.PARENT_DIR, "ArkanaServer", "web", "user.db")
        self._init_db()
        
        # 注册用户指令
        self.register_user_func(
            "/userdb refresh",
            self.refresh_userdb,
            prefix="/userdb",
            description="刷新群成员数据库",
            usage="/userdb refresh",
            examples=["/userdb refresh"],
            tags=["admin"]
        )
        
        # 注册官方通知事件处理器（关键修复）
        self.register_handler("ncatbot.notice_event", self.handle_notice_event)
        
        LOG.info(f"{self.name} 插件已加载，版本: {self.version}，数据库路径: {self.db_path}")