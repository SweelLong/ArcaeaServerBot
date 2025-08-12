from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import BaseMessage
from ncatbot.utils import get_log
LOG = get_log("Say")
bot = CompatibleEnrollment

class Say(BasePlugin):
    name = "Say"
    version = "1.0.0"
    author = "Swiro"
    description = "使用机器人发布权威性话语"
    dependencies = {}

    async def is_group_admin(self, group_id, user_id):
        member_info = await self.api.get_group_member_info(group_id, user_id, no_cache=False)
        return member_info["data"]["role"] in ["admin", "owner"]

    async def say(self, msg: BaseMessage):
        parts = msg.raw_message.split(maxsplit=2)
        target_group_id = parts[1]
        text = parts[2]
        is_admin = await self.is_group_admin(target_group_id, msg.sender.user_id)
        if not is_admin:
            return self.api.post_group_msg_sync(
                target_group_id,
                at=msg.sender.user_id,
                text=f"不要试图使用/say命令，只有本群管理员才可以使用哦~"
            )
        
        if len(parts) < 3:
            return self.api.post_group_msg_sync(
                target_group_id,
                text="参数错误，请使用: /say QQGroupID Text"
            )
        
        try:
            return self.api.post_group_msg_sync(target_group_id, text=text)
        except Exception as e:
            LOG.error(f"发送消息失败: {str(e)}")
            return self.api.post_group_msg_sync(
                target_group_id,
                text=f"发送失败: {str(e)}"
            )

    async def on_load(self):
        self.register_user_func(
            "/say",
            self.say,
            prefix="/say",
            description="使用机器人发布权威性话语",
            usage="/say QQGroupID Text",
            examples=["/say 123456 这是一条测试消息"],
            tags=["user"]
        )
        self.images = []
        LOG.info(f"{self.name} 插件已加载，版本: {self.version}")