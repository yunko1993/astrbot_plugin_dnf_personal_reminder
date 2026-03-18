import logging
import json
import os
import asyncio
from datetime import datetime
from astrbot.api.all import *

@register("dnf_personal_reminder", "yunko1993", "私人定时提醒秘书", "1.2.0")
class PersonalReminder(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        
        # 1. 确定数据存放路径 (data/plugin_data/dnf_personal_reminder/)
        self.plugin_name = "dnf_personal_reminder"
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        self.data_dir = os.path.join(base_dir, "data", "plugin_data", self.plugin_name)
        
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            
        self.data_file = os.path.join(self.data_dir, "reminders.json")
        self.reminders = self._load_data()

    def _load_data(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"加载提醒数据失败: {e}")
                return []
        return []

    def _save_data(self):
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.reminders, f, ensure_ascii=False, indent=4)
            self._refresh_scheduler()
        except Exception as e:
            logging.error(f"保存提醒数据失败: {e}")

    def _refresh_scheduler(self):
        """刷新定时任务，所有任务现在都指向私聊发送"""
        scheduler = self.context.get_scheduler()
        # 清除旧任务
        for job in scheduler.get_jobs():
            if job.id.startswith(f"{self.plugin_name}_"):
                scheduler.remove_job(job.id)

        # 重新注册
        for idx, item in enumerate(self.reminders):
            try:
                h, m = item['time'].split(':')
                scheduler.add_job(
                    self._send_private_notification,
                    "cron",
                    hour=h,
                    minute=m,
                    args=[item],
                    id=f"{self.plugin_name}_{idx}",
                    replace_existing=True
                )
            except Exception as e:
                logging.error(f"注册任务失败: {e}")

    async def _send_private_notification(self, item):
        """核心逻辑：始终通过私聊发送"""
        msg = f"🔔 【私人秘书提醒】\n--------------------\n内容：{item['content']}\n时间：{item['time']}\n--------------------\n别忘了去领取哦！"
        try:
            # 始终发送私聊消息给设置该任务的用户
            await self.context.send_private_message(item['user_id'], [Plain(msg)])
            logging.info(f"已向用户 {item['user_id']} 发送私人提醒。")
        except Exception as e:
            logging.error(f"私人提醒发送失败: {e}")

    @on_startup
    async def startup(self, event: AstrBotMessageEvent):
        self._refresh_scheduler()
        logging.info("DNF私人秘书插件已就绪，所有提醒将通过私聊发放。")

    @command("提醒")
    async def reminder_manager(self, event: AstrBotMessageEvent):
        '''私人提醒管理助手'''
        pass

    @reminder_manager.group("添加")
    async def add(self, event: AstrBotMessageEvent, time_str: str, *, content: str):
        '''添加私人提醒。格式: /提醒 添加 10:30 领心悦增幅器'''
        try:
            datetime.strptime(time_str, "%H:%M")
        except:
            yield CommandResult().error("时间格式错误！请使用 HH:MM (如 09:30)")
            return

        user_id = event.message_obj.user_id
        
        new_item = {
            "user_id": user_id,
            "time": time_str,
            "content": content,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        self.reminders.append(new_item)
        self._save_data()
        
        # 提示语根据发送环境不同稍作调整
        if event.message_obj.group_id:
            yield CommandResult().success(f"✅ 设置成功！我会每天 {time_str} 【私聊】提醒你：{content}")
        else:
            yield CommandResult().success(f"✅ 没问题，我会每天 {time_str} 准时提醒你。")

    @reminder_manager.group("列表")
    async def list_reminders(self, event: AstrBotMessageEvent):
        '''查看【我】设置的所有私人提醒'''
        user_id = event.message_obj.user_id
        # 只筛选当前用户的提醒
        my_items = [f"[{i}] {r['time']} - {r['content']}" for i, r in enumerate(self.reminders) if r['user_id'] == user_id]
        
        if not my_items:
            yield CommandResult().success("你当前没有任何私人提醒。")
        else:
            yield CommandResult().success("📅 你的私人提醒清单：\n" + "\n".join(my_items))

    @reminder_manager.group("删除")
    async def delete(self, event: AstrBotMessageEvent, index: int):
        '''根据编号删除【我】的提醒'''
        user_id = event.message_obj.user_id
        try:
            # 权限检查：确保删除的是自己的
            if 0 <= index < len(self.reminders) and self.reminders[index]['user_id'] == user_id:
                removed = self.reminders.pop(index)
                self._save_data()
                yield CommandResult().success(f"🗑 已删除：{removed['time']} {removed['content']}")
            else:
                yield CommandResult().error("找不到该编号的提醒，或你无权删除。")
        except:
            yield CommandResult().error("删除失败。")

    @reminder_manager.group("立即测试")
    async def test(self, event: AstrBotMessageEvent):
        '''立即触发一次【我】的提醒（测试用）'''
        user_id = event.message_obj.user_id
        my_items = [r for r in self.reminders if r['user_id'] == user_id]
        
        if not my_items:
            yield CommandResult().success("你还没有设置任何任务，无法测试。")
            return
            
        yield CommandResult().success(f"正在测试向你私聊发送 {len(my_items)} 条任务...")
        for item in my_items:
            await self._send_private_notification(item)
            await asyncio.sleep(0.5)
