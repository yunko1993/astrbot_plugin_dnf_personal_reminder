import logging
import json
import os
import asyncio
from datetime import datetime
from astrbot.api.all import *

@register("dnf_personal_reminder", "yunko1993", "DNF私人提醒秘书", "1.3.3")
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

        try:
            self._refresh_scheduler()
            logging.info("DNF私人提醒插件初始化完成，定时任务已同步。")
        except Exception as e:
            logging.error(f"插件任务初始化失败: {e}")

    def _load_data(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save_data(self):
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.reminders, f, ensure_ascii=False, indent=4)
            self._refresh_scheduler()
        except Exception as e:
            logging.error(f"保存数据失败: {e}")

    def _refresh_scheduler(self):
        scheduler = self.context.get_scheduler()
        for job in scheduler.get_jobs():
            if job.id.startswith(f"{self.plugin_name}_"):
                scheduler.remove_job(job.id)

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
            except: pass

    async def _send_private_notification(self, item):
        msg = f"🔔 【私人秘书提醒】\n--------------------\n内容：{item['content']}\n时间：{item['time']}\n--------------------\n别忘了去领取哦！"
        try:
            await self.context.send_private_message(str(item['user_id']), [Plain(msg)])
        except: pass

    # ================= 终极解决方案：手动解析消息文本 =================
    
    @command("提醒添加")
    async def add(self, event: AstrMessageEvent):
        '''用法: /提醒添加 10:30 领心悦增幅器'''
        # 手动解析文本
        raw_msg = event.message_str.strip() # "/提醒添加 10:30 内容"
        parts = raw_msg.split()
        
        if len(parts) < 3:
            yield CommandResult().error("格式错误！格式: /提醒添加 10:30 领东西")
            return
            
        time_str = parts[1]
        content = " ".join(parts[2:])
            
        try:
            datetime.strptime(time_str, "%H:%M")
        except:
            yield CommandResult().error("时间错误！请使用 HH:MM (如 09:30)")
            return

        try:
            user_id = str(event.get_sender_id())
        except:
            user_id = str(event.message_obj.sender.user_id)
        
        self.reminders.append({"user_id": user_id, "time": time_str, "content": content})
        self._save_data()
        yield CommandResult().success(f"✅ 设置成功！每天 {time_str} 我会私聊提醒你。")

    @command("提醒列表")
    async def list_reminders(self, event: AstrMessageEvent):
        '''用法: /提醒列表'''
        try:
            user_id = str(event.get_sender_id())
        except:
            user_id = str(event.message_obj.sender.user_id)
            
        my_items =[f"[{i}] {r['time']} - {r['content']}" for i, r in enumerate(self.reminders) if str(r['user_id']) == user_id]
        
        if not my_items:
            yield CommandResult().success("你当前没有任何私人提醒。")
        else:
            yield CommandResult().success("📅 你的提醒清单：\n" + "\n".join(my_items))

    @command("提醒删除")
    async def delete(self, event: AstrMessageEvent):
        '''用法: /提醒删除 [编号]'''
        raw_msg = event.message_str.strip()
        parts = raw_msg.split()
        if len(parts) < 2:
            yield CommandResult().error("请提供编号，如: /提醒删除 0")
            return
            
        try:
            index = int(parts[1])
            user_id = str(event.get_sender_id())
        except:
            yield CommandResult().error("编号无效。")
            return
            
        if 0 <= index < len(self.reminders) and str(self.reminders[index]['user_id']) == user_id:
            removed = self.reminders.pop(index)
            self._save_data()
            yield CommandResult().success(f"🗑 已删除：{removed['time']} {removed['content']}")
        else:
            yield CommandResult().error("找不到该编号或无权限。")

    @command("提醒测试")
    async def test(self, event: AstrMessageEvent):
        '''用法: /提醒测试'''
        try:
            user_id = str(event.get_sender_id())
        except:
            user_id = str(event.message_obj.sender.user_id)
            
        my_items = [r for r in self.reminders if str(r['user_id']) == user_id]
        if not my_items:
            yield CommandResult().error("你还没有设置任何任务。")
            return
            
        yield CommandResult().success("测试消息已发出，请查看私聊。")
        for item in my_items:
            await self._send_private_notification(item)
            await asyncio.sleep(0.5)
