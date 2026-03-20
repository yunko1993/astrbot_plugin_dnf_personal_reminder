import logging
import json
import os
import asyncio
from datetime import datetime
from astrbot.api.all import *

@register("dnf_personal_reminder", "yunko1993", "DNF私人提醒秘书", "1.3.4")
class PersonalReminder(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        
        self.plugin_name = "dnf_personal_reminder"
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        self.data_dir = os.path.join(base_dir, "data", "plugin_data", self.plugin_name)
        
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            
        self.data_file = os.path.join(self.data_dir, "reminders.json")
        self.reminders = self._load_data()

        # 初始化定时任务
        self._refresh_scheduler()

    def _load_data(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []

    def _save_data(self):
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.reminders, f, ensure_ascii=False, indent=4)
            self._refresh_scheduler()
        except Exception as e:
            logging.error(f"DNF提醒保存失败: {e}")

    def _get_scheduler(self):
        """兼容性寻找调度器"""
        # 尝试几种不同版本 AstrBot 存放调度器的位置
        if hasattr(self.context, 'get_scheduler'):
            return self.context.get_scheduler()
        if hasattr(self.context, 'scheduler'):
            return self.context.scheduler
        # v4.16.x 常用路径
        if hasattr(self.context, 'runtime') and hasattr(self.context.runtime, 'scheduler'):
            return self.context.runtime.scheduler
        return None

    def _refresh_scheduler(self):
        """刷新定时任务列表"""
        scheduler = self._get_scheduler()
        if not scheduler:
            logging.error("DNF提醒: 无法在当前版本 AstrBot 中找到调度器，定时提醒将失效。")
            return

        # 移除旧任务
        for job in scheduler.get_jobs():
            if job.id.startswith(f"{self.plugin_name}_"):
                scheduler.remove_job(job.id)

        # 重新注册任务
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
            except:
                pass

    async def _send_private_notification(self, item):
        msg = f"🔔 【私人秘书提醒】\n--------------------\n内容：{item['content']}\n时间：{item['time']}\n--------------------\n别忘了去领取哦！"
        try:
            await self.context.send_private_message(str(item['user_id']), [Plain(msg)])
        except:
            pass

    # ================= 核心指令逻辑 =================
    
    @command("提醒添加")
    async def add(self, event: AstrMessageEvent):
        '''用法: /提醒添加 10:30 领心悦'''
        raw_msg = event.message_str.strip()
        parts = raw_msg.split()
        
        if len(parts) < 3:
            yield event.plain_result("❌ 格式错误！格式: /提醒添加 10:30 领东西")
            return
            
        time_str = parts[1]
        content = " ".join(parts[2:])
            
        try:
            datetime.strptime(time_str, "%H:%M")
        except:
            yield event.plain_result("❌ 时间格式不对，请使用 24小时制 HH:MM (如 09:30)")
            return

        user_id = str(event.get_sender_id())
        self.reminders.append({"user_id": user_id, "time": time_str, "content": content})
        self._save_data()
        
        yield event.plain_result(f"✅ 设置成功！每天 {time_str} 我会私聊提醒你：{content}")

    @command("提醒列表")
    async def list_reminders(self, event: AstrMessageEvent):
        '''用法: /提醒列表'''
        user_id = str(event.get_sender_id())
        my_items = [f"[{i}] {r['time']} - {r['content']}" for i, r in enumerate(self.reminders) if str(r['user_id']) == user_id]
        
        if not my_items:
            yield event.plain_result("你当前没有任何私人提醒。")
        else:
            yield event.plain_result("📅 你的提醒清单：\n" + "\n".join(my_items))

    @command("提醒删除")
    async def delete(self, event: AstrMessageEvent):
        '''用法: /提醒删除 [编号]'''
        raw_msg = event.message_str.strip()
        parts = raw_msg.split()
        if len(parts) < 2:
            yield event.plain_result("请输入编号，如: /提醒删除 0")
            return
            
        try:
            index = int(parts[1])
            user_id = str(event.get_sender_id())
        except:
            yield event.plain_result("❌ 无效的编号。")
            return
            
        if 0 <= index < len(self.reminders) and str(self.reminders[index]['user_id']) == user_id:
            removed = self.reminders.pop(index)
            self._save_data()
            yield event.plain_result(f"🗑 已删除 {removed['time']} 的提醒。")
        else:
            yield event.plain_result("❌ 找不到该编号，或者该任务不属于你。")

    @command("提醒测试")
    async def test(self, event: AstrMessageEvent):
        '''用法: /提醒测试'''
        user_id = str(event.get_sender_id())
        my_items = [r for r in self.reminders if str(r['user_id']) == user_id]
        
        if not my_items:
            yield event.plain_result("你还没有设置任何任务，无法测试。")
            return
            
        yield event.plain_result("正在测试，请观察私聊...")
        for item in my_items:
            await self._send_private_notification(item)
            await asyncio.sleep(0.5)
