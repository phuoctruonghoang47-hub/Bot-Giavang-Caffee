"""Tìm Chat ID của kênh/nhóm mà bot đã được thêm vào.
Cách dùng: thêm bot làm admin kênh, đăng 1 tin bất kỳ trong kênh, rồi chạy: python find_chat_id.py
"""
import json
import os
import sys
import urllib.request

import bot

bot.load_env()
token = os.environ["TELEGRAM_BOT_TOKEN"]
data = json.loads(urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getUpdates", timeout=20).read())
chats = {}
for u in data["result"]:
    for k in ("channel_post", "my_chat_member", "message", "edited_channel_post"):
        if k in u:
            c = u[k]["chat"]
            chats[c["id"]] = (c.get("type"), c.get("title") or c.get("first_name"), c.get("username"))
if not chats:
    sys.exit("Chưa thấy kênh nào. Hãy thêm bot làm admin kênh, đăng 1 tin trong kênh, rồi chạy lại.")
for cid, (typ, title, username) in chats.items():
    print(f"{typ:10} | {title} | chat_id = {cid}" + (f"  (hoặc @{username})" if username else ""))
