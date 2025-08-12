import asyncio
import os
from datetime import datetime
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import BaseMessage
from ncatbot.utils import get_log
from ncatbot.plugin.event import Event
import sqlite3

LOG = get_log("GroupMemberValidator")
bot = CompatibleEnrollment

# 数据库路径配置
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DATABASE_PATH = os.path.join(PARENT_DIR, "ArkanaServer\\database\\arcaea_database.db")
# 配置需要检查的群ID列表
CHECK_GROUP_IDS = [123456789, 987654321]

class GroupMemberValidator(BasePlugin):
    name = "GroupMemberValidator"
    version = "1.0.0"
    author = "Swiro"
    description = "自动检查并识别非本群玩家的游戏存档，执行封号处理，并输出已封号玩家名单"
    dependencies = {}

    async def is_group_admin(self, group_id, user_id):
        """检查用户是否为群管理员"""
        member_info = await self.api.get_group_member_info(group_id, user_id, no_cache=False)
        return member_info["data"]["role"] in ["admin", "owner"]

    async def load_group_members(self):
        """加载指定群的所有成员"""
        for group_id in CHECK_GROUP_IDS:
            try:
                members = await self.api.get_group_member_list(group_id)
                self.group_members[group_id] = {
                    member["user_id"] for member in members["data"]
                }
                LOG.info(f"已加载群 {group_id} 的成员，共 {len(self.group_members[group_id])} 人")
            except Exception as e:
                LOG.error(f"加载群 {group_id} 成员失败: {str(e)}")

    def get_db_users(self):
        """从数据库获取所有用户及其ID和密码状态"""
        users = []
        try:
            with sqlite3.connect(DATABASE_PATH) as conn:
                cursor = conn.cursor()
                # 获取用户ID、名称、邮箱和密码状态
                cursor.execute("SELECT user_id, name, email, password FROM user") 
                users = cursor.fetchall()
        except Exception as e:
            LOG.error(f"读取数据库失败: {str(e)}")
        return users

    def get_banned_users(self):
        """获取所有已封号用户的列表"""
        banned_users = []
        try:
            with sqlite3.connect(DATABASE_PATH) as conn:
                cursor = conn.cursor()
                # 查询所有密码为空的用户（已封号用户）
                cursor.execute("SELECT user_id, name, email FROM user WHERE password IS NULL OR password = ''")
                banned_users = cursor.fetchall()
        except Exception as e:
            LOG.error(f"获取已封号用户列表失败: {str(e)}")
        return banned_users

    def is_user_banned(self, password):
        """判断用户是否已被封号（密码为空视为已封号）"""
        return password is None or password.strip() == ""

    def ban_user(self, user_id):
        """执行封号操作：清空密码并删除登录记录"""
        try:
            with sqlite3.connect(DATABASE_PATH) as conn:
                cursor = conn.cursor()
                # 先检查用户是否已被封号
                cursor.execute("SELECT password FROM user WHERE user_id=:a", {'a': user_id})
                result = cursor.fetchone()
                if result and self.is_user_banned(result[0]):
                    LOG.info(f"用户 ID: {user_id} 已处于封号状态，无需重复操作")
                    return True, False  # (操作成功, 是否为新封号)
                # 清空用户密码
                cursor.execute('''update user set password = '' where user_id=:a''',
                              {'a': user_id})
                # 删除登录记录
                cursor.execute('''delete from login where user_id=:a''', {'a': user_id})
                conn.commit()
                LOG.info(f"已成功封禁用户 ID: {user_id}")
                return True, True  # (操作成功, 是否为新封号)
        except Exception as e:
            LOG.error(f"封禁用户 ID: {user_id} 失败: {str(e)}")
            return False, False

    async def check_non_group_users(self):
        """检查不在群中的用户并执行封号处理，输出已封号玩家名单"""
        await self.load_group_members()
        db_users = self.get_db_users()
        if not db_users:
            LOG.info("数据库中没有找到用户")
            return
        # 获取并输出已封号用户名单
        banned_users = self.get_banned_users()
        banned_count = len(banned_users)
        # 日志输出已封号用户名单
        LOG.info(f"当前已封号用户共 {banned_count} 人:")
        for user_id, name, email in banned_users:
            LOG.info(f"已封号用户: 用户名: {name}, 邮箱: {email}, 用户ID: {user_id}")
        # 群通知输出已封号用户名单摘要
        banned_summary = [f"{name} (ID: {user_id})" for user_id, name, email in banned_users]
        banned_notification = f"当前已封号用户共 {banned_count} 人:\n" + "\n".join(banned_summary)
        all_group_users = set()
        for members in self.group_members.values():
            all_group_users.update(members)
        non_group_users = []
        for user_id, name, email, password in db_users:
            # 跳过已封号的用户
            if self.is_user_banned(password):
                continue
            if email.endswith("@qq.com"):
                qq_str = email[:-7]
                if qq_str.isdigit():
                    qq = int(qq_str)
                    if qq not in all_group_users:
                        non_group_users.append((user_id, name, email))
        if non_group_users:
            LOG.info(f"发现 {len(non_group_users)} 个未封号的非本群用户，将执行封号处理:")
            banned_results = []
            new_ban_count = 0
            # 对每个非本群用户执行封号操作
            for user_id, name, email in non_group_users:
                LOG.info(f"处理非本群用户: 用户名: {name}, 用户ID: {user_id}")
                success, is_new_ban = self.ban_user(user_id)
                status = "成功" if success else "失败"
                if success and is_new_ban:
                    new_ban_count += 1
                banned_results.append(f"{name} (ID: {user_id}) - {status}")
            # 向监控群发送综合通知：已封号名单 + 新增封号结果
            notification = (
                f"=== 封号状态报告 ===\n"
                f"{banned_notification}\n\n"
                f"=== 本次新增封号 ===\n"
                f"发现 {len(non_group_users)} 个未封禁的非本群成员的游戏存档，"
                f"成功新增封号 {new_ban_count} 个：\n" +
                "\n".join(banned_results)
            )
            for group_id in CHECK_GROUP_IDS:
                await self.api.post_group_msg(
                    group_id,
                    text=notification
                )
        else:
            LOG.info("未发现未封号的非本群用户")
            return banned_notification

    async def refresh_database(self, msg: BaseMessage):
        """手动刷新群成员数据库指令处理"""
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
        
        try:
            await self.load_group_members()
            res = await self.check_non_group_users()
            return await self.api.post_group_msg(
                msg.group_id,
                text="已手动刷新封号名单并校验数据库~\n" +
                str(res)
            )
        except Exception as e:
            LOG.error(f"手动刷新失败: {str(e)}")
            return await self.api.post_group_msg(
                msg.group_id,
                text=f"刷新失败: {str(e)}"
            )

    async def handle_group_increase(self, data):
        """处理群成员进群事件"""
        group_id = data.get("group_id")
        user_id = data.get("user_id")
        sub_type = data.get("sub_type", "unknown")
        if group_id not in CHECK_GROUP_IDS:
            return
        LOG.info(f"群 {group_id} 有新成员加入: {user_id}（{sub_type}）")
        await self.load_group_members()
        LOG.info(f"因新成员加入，已自动刷新群 {group_id} 成员列表")

    async def handle_group_decrease(self, data):
        """处理群成员退群事件"""
        group_id = data.get("group_id")
        user_id = data.get("user_id")
        sub_type = data.get("sub_type", "unknown")
        if group_id not in CHECK_GROUP_IDS:
            return
        LOG.info(f"群 {group_id} 有成员退出: {user_id}（{sub_type}）")
        await self.load_group_members()
        LOG.info(f"因成员退出，已自动刷新群 {group_id} 成员列表")
        await self.check_non_group_users()

    async def handle_notice_event(self, event: Event):
        """统一处理所有通知事件，按子类型分发"""
        notice_data = event.data
        notice_type = notice_data.get("notice_type")
        if notice_type == "group_increase":
            await self.handle_group_increase(notice_data)
        elif notice_type == "group_decrease":
            await self.handle_group_decrease(notice_data)

    async def on_load(self):
        """插件加载时初始化"""
        self.group_members = {} 
        self.running = True
        LOG.info(f"将使用数据库文件: {DATABASE_PATH}")
        # 注册定时任务（使用框架推荐方式）
        self.add_scheduled_task(
            job_func=self.check_non_group_users,
            name="整点检查非本群用户并输出封号名单",
            interval="1h", 
        )
        # 初始加载时立即检查一次
        asyncio.get_event_loop().create_task(self.check_non_group_users())
        # 注册手动刷新指令
        self.register_user_func(
            "/validator refresh",
            self.refresh_database,
            prefix="/validator",
            description="手动刷新群成员数据库并检查非本群用户，输出封号状态报告",
            usage="/validator refresh",
            examples=["/validator refresh"],
            tags=["admin"]
        )
        # 注册通知事件处理器
        self.register_handler("ncatbot.notice_event", self.handle_notice_event)
        LOG.info(f"{self.name} 插件已加载，版本: {self.version}")
        LOG.info(f"将在每个整点检查群 {CHECK_GROUP_IDS} 并输出已封号玩家名单")