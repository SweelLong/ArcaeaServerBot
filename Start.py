# ========= 导入模块 ==========
import json
import os
import time
import random
import sqlite3
import datetime
from ncatbot.utils import get_log
from ncatbot.core import BotClient, GroupMessage, PrivateMessage
import requests
#from ncatbot.core import BotClient, MessageChain, Text, At, Image, Face, Reply

# ========== 全局配置 ==========
BASE_PATH = os.path.abspath(os.path.dirname(__file__))
PARENT_PATH = os.path.dirname(BASE_PATH)
USER_DB_PATH = os.path.join(PARENT_PATH, "ArkanaServer\\web\\user.db")
GAME_DB_PATH = os.path.join(PARENT_PATH, "ArkanaServer\\database\\arcaea_database.db")
CURRENCY_RANGE = [100, 200]
VOTE_RANGE = [1, 5]
# 百度API配置
APP_ID = "百度API智能体每天500次免费调用额外"
SECRET_KEY = "如果感觉不够可以多个账号然后改写成API池轮流调用"
BAIDU_API_URL = f"https://agentapi.baidu.com/assistant/getAnswer?appId={APP_ID}&secretKey={SECRET_KEY}"

# ========== 创建对象 ==========
bot = BotClient()
_log = get_log()

# ========= 工具函数 ==========
def call_baidu_api(text):
    """调用百度API获取回复"""
    try:
        headers = {"Content-Type": "application/json"}
        response = requests.post(
            BAIDU_API_URL, 
            headers=headers, 
            data=json.dumps({
                "message": {
                    "content": {
                        "type": "text",
                        "value": {
                            "showText": text
                        }
                    }
                },
                "source": APP_ID,
                "from": "openapi",
                "openId": "SweelLong"
            })
        )
        response_data = response.json()
        if 'data' in response_data and 'content' in response_data['data'] and len(response_data['data']['content']) > 0:
            return str(response_data['data']['content'][0]['data'])
        else:
            _log.error(f"百度API返回格式异常: {response_data}")
            return "唔，告诉你太多秘密了，再多说的话，我就要被大魔王抓走了，呜呜呜~"
    except Exception as e:
        _log.error(f"调用百度API时发生错误: {str(e)}")
        return "唔，告诉你太多秘密了，再多说的话，我就要被大魔王抓走了，呜呜呜~"

# ========= 回调函数 ==========
@bot.group_event()
async def on_group_message(msg: GroupMessage):
    _log.info(msg)
    if msg.raw_message.startswith("[CQ:at,qq=2316740514]"):
        if "签到" in msg.raw_message:
            today = str(datetime.date.today())
            today_currency = random.randint(*CURRENCY_RANGE)
            with sqlite3.connect(USER_DB_PATH, timeout=30) as conn:
                cursor = conn.cursor()
                # 清理3天之前的记录
                time_delta = str(datetime.date.today() - datetime.timedelta(1))
                cursor.execute("DELETE FROM punch_in WHERE today<=?", (time_delta, ))
                conn.commit()
                # 检查今日签到记录是否存在
                cursor.execute("SELECT 1 FROM punch_in WHERE qq_id=? AND today=?", (msg.user_id, today))
                result = cursor.fetchone()
                if result is None:
                    with sqlite3.connect(GAME_DB_PATH, timeout=30) as conn2:
                        cursor2 = conn2.cursor()
                        present_id = "每日签到" + str(msg.user_id)
                        description = f"QQ号码{msg.user_id}的每日签到"
                        # 检查present表记录是否存在
                        cursor2.execute("SELECT 1 FROM present WHERE present_id=? AND description=?", (present_id, description))
                        if cursor2.fetchone():
                            # 存在则更新
                            cursor2.execute("UPDATE present SET expire_ts=? WHERE present_id=? AND description=?", 
                                          (int((time.time() + 86400) * 1000), present_id, description))
                        else:
                            # 不存在则插入
                            cursor2.execute("INSERT INTO present (present_id, description, expire_ts) VALUES (?,?,?)", 
                                          (present_id, description, int((time.time() + 86400) * 1000)))
                        conn2.commit()
                        # 检查present_item表记录是否存在
                        cursor2.execute("SELECT 1 FROM present_item WHERE present_id=? AND item_id=? AND type=?", 
                                      (present_id, "memory", "memory"))
                        if cursor2.fetchone():
                            # 存在则更新
                            cursor2.execute("UPDATE present_item SET amount=? WHERE present_id=? AND item_id=? AND type=?", 
                                          (today_currency, present_id, "memory", "memory"))
                        else:
                            # 不存在则插入（这里假设表结构，你可能需要根据实际情况调整字段）
                            cursor2.execute("INSERT INTO present_item (present_id, item_id, type, amount) VALUES (?,?,?,?)", 
                                          (present_id, "memory", "memory", today_currency))
                        conn2.commit()
                        # 获取用户ID
                        cursor2.execute("SELECT user_id FROM user WHERE email=?", (str(msg.user_id) + "@qq.com",))
                        user_id = cursor2.fetchone()
                        if user_id is None:
                            return await msg.reply("你现在还不是讲述者哦！请先注册账号再进行签到~")
                        user_id = user_id[0]
                        # 检查user_present表记录是否存在
                        cursor2.execute("SELECT 1 FROM user_present WHERE user_id=? AND present_id=?", (user_id, present_id))
                        if cursor2.fetchone():
                            cursor2.execute("DELETE FROM user_present WHERE user_id=? AND present_id=?", (user_id, present_id))
                            conn2.commit()
                        cursor2.execute("INSERT INTO user_present (user_id, present_id) VALUES (?,?)", (user_id, present_id))
                        conn2.commit()
                    # 插入打卡记录
                    cursor.execute("INSERT INTO punch_in (qq_id, today) VALUES (?,?)", (msg.user_id, today))
                    conn.commit()
                    cursor.execute("SELECT vote_ticket FROM user_item WHERE qq_id=?", (msg.user_id,))
                    vote_ticket = cursor.fetchone()
                    today_vote = random.randint(*VOTE_RANGE)
                    if vote_ticket is None:
                        cursor.execute("INSERT INTO user_item (qq_id, vote_ticket) VALUES (?,?)", (msg.user_id, today_vote))
                        conn.commit()
                    else:
                        cursor.execute("UPDATE user_item SET vote_ticket=? WHERE qq_id=?", (vote_ticket[0] + today_vote, msg.user_id))
                        conn.commit()
                    return await msg.reply(f"今日签到成功!\n奖励如下：\n- 获得{today_currency}枚虚实构想\n- 获得{today_vote}张歌曲投票券")
                else:
                    content = f"现在{msg.sender.nickname}这个人找你签到，但是他已经签过到了，请你告诉他！"
                    api_response = call_baidu_api(content)
                    return await msg.reply(api_response)
        else:
            content = msg.raw_message.replace("[CQ:at,qq=2316740514]", "").strip()
            if content:
                content = f"现在我将以{msg.sender.nickname}的身份和你聊天：{msg.raw_message.replace("[CQ:at,qq=2316740514]", "").strip()}"
                api_response = call_baidu_api(content)
                return await msg.reply(api_response)
            else:
                return await msg.reply("你好呀，欢迎来到Arkana！有什么可以帮助你的吗？可以使用/help命令查看帮助信息哦~")

@bot.private_event()
async def on_private_message(msg: PrivateMessage):
    _log.info(msg)

# ========== 启动实例 ==========
if __name__ == "__main__":
    # 正常关闭实例：CTRL + C
    bot.plugins_path = "Plugins"
    bot.run(bt_uin="你的QQ号码")