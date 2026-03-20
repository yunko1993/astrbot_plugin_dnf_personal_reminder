import logging
import json
import os
import asyncio
import traceback
from datetime import datetime
from astrbot.api.all import *

@register("dnf_personal_reminder", "yunko1993", "DNF私人提醒秘书", "1.3.8")
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
        self._refresh_scheduler()

    def _load_data(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return[]
        return[]

    def _save_data(self):
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.reminders, f, ensure_ascii=False, indent=4)
            self._refresh_scheduler()
        except Exception as e:
            logging.error(f"DNF提醒保存失败: {e}")

    def _get_scheduler(self):
        if hasattr(self.context, 'get_scheduler'):
            return self.context.get_scheduler()
        if hasattr(self.context, 'runtime') and hasattr(self.context.runtime, 'scheduler'):
            return self.context.runtime.scheduler
        return None

    def _refresh_scheduler(self):
        scheduler = self._get_scheduler()
        if not scheduler: return

        for job in scheduler.get_jobs():
            if job.id.startswith(f"{self.plugin_name}_"):
                scheduler.remove_job(job.id)

        for idx, item in enumerate(self.reminders):
            try:
                h, m = item['time'].split(':')
                scheduler.add_job(
                    self._send_private_notification,
                    "cron", hour=h, minute=m,
                    args=[item],
                    id=f"{self.plugin_name}_{idx}",
                    replace_existing=True
                )
            except: pass

    # ================= 核心黑科技：全网搜捕发送器 =================
    def _get_active_platforms(self):
        """利用反射(Reflection)暴力扫描并获取底层适配器，无视 API 改名"""
        pm = self.context.platform_manager
        platforms =[]
        
        # 扫描 platform_manager 内部所有的列表和字典
        for attr in dir(pm):
            if attr.startswith('_'): continue
            val = getattr(pm, attr)
            
            if isinstance(val, dict):
                platforms.extend(val.values())
            elif isinstance(val, list):
                platforms.extend(val)
                
        # 筛选出真正具备“发送消息”能力的适配器对象
        valid_platforms =[]
        for p in platforms:
            if hasattr(p, 'send_msg') or hasattr(p, 'send_private_msg') or hasattr(p, 'handle_out_msg'):
                if p not in valid_platforms:
                    valid_platforms.append(p)
                    
        return valid_platforms

    async def _send_private_notification(self, item):
        user_id = str(item['user_id'])
        msg_text = f"🔔 【私人秘书提醒】\n--------------------\n内容：{item['content']}\n时间：{item['time']}\n--------------------\n👉 记得领取哦！"
        
        logging.info(f"DNF提醒: 开始向用户 {user_id} 发送私聊消息...")
        
        platforms = self._get_active_platforms()
        if not platforms:
            logging.error("DNF提醒: 致命错误 - 找不到任何网络通信适配器！")
            return

        success = False
        for platform in platforms:
            # 策略1：通用 OutMsg 协议
            if hasattr(platform, 'send_msg') or hasattr(platform, 'handle_out_msg'):
                try:
                    from astrbot.api.message_event import OutMsg, TargetType
                    out_msg = OutMsg(type=TargetType.PRIVATE, target_id=user_id, chain=[Plain(msg_text)])
                    
                    if hasattr(platform, 'send_msg'):
                        await platform.send_msg(out_msg)
                    else:
                        await platform.handle_out_msg(out_msg)
                        
                    logging.info(f"DNF提醒: 已通过 OutMsg 协议成功发送。")
                    success = True
                    break
                except Exception as e:
                    pass

            # 策略2：OneBot 原生协议底层强发 (专治 NapCat)
            if not success and hasattr(platform, 'send_private_msg'):
                try:
                    await platform.send_private_msg(user_id=int(user_id), message=[Plain(msg_text)])
                    logging.info(f"DNF提醒: 已通过 OneBot 原生协议成功发送。")
                    success = True
                    break
                except Exception as e:
                    pass
                    
        if not success:
            logging.error(f"DNF提醒: 所有适配器均发送失败。")

    # ================= 指令区 =================
    
    @command("提醒添加")
    async def add(self, event: AstrMessageEvent):
        raw_msg = event.message_str.strip()
        parts = raw_msg.split()
        if len(parts) < 3:
            yield event.plain_result("❌ 格式错误！格式: /提醒添加 10:30 内容")
            return
            
        time_str = parts[1]
        content = " ".join(parts[2:])
        try:
            datetime.strptime(time_str, "%H:%M")
        except:
            yield event.plain_result("❌ 时间格式不对，请使用 24小时制 HH:MM")
            return

        user_id = str(event.get_sender_id())
        self.reminders.append({"user_id": user_id, "time": time_str, "content": content})
        self._save_data()
        yield event.plain_result(f"✅ 设置成功！每天 {time_str} 我会私聊提醒你。")

    @command("提醒列表")
    async def list_reminders(self, event: AstrMessageEvent):
        user_id = str(event.get_sender_id())
        my_items = [f"[{i}] {r['time']} - {r['content']}" for i, r in enumerate(self.reminders) if str(r['user_id']) == user_id]
        if not my_items:
            yield event.plain_result("你还没有设置任何提醒。")
        else:
            yield event.plain_result("📅 你的提醒清单：\n" + "\n".join(my_items))

    @command("提醒删除")
    async def delete(self, event: AstrMessageEvent):
        raw_msg = event.message_str.strip()
        parts = raw_msg.split()
        if len(parts) < 2:
            yield event.plain_result("用法: /提醒删除 [编号]")
            return
        try:
            index = int(parts[1])
            user_id = str(event.get_sender_id())
            if 0 <= index < len(self.reminders) and str(self.reminders[index]['user_id']) == user_id:
                removed = self.reminders.pop(index)
                self._save_data()
                yield event.plain_result(f"🗑 已删除 {removed['time']} 的提醒。")
            else:
                yield event.plain_result("❌ 编号无效。")
        except:
            yield event.plain_result("❌ 删除失败。")

    @command("提醒测试")
    async def test(self, event: AstrMessageEvent):
        user_id = str(event.get_sender_id())
        my_items =[r for r in self.reminders if str(r['user_id']) == user_id]
        if not my_items:
            yield event.plain_result("你没有设置任务，无法测试。")
            return
            
        yield event.plain_result(f"🚀 正在发送测试消息...")
        for item in my_items:
            await self._send_private_notification(item)
            await asyncio.sleep(0.5)
