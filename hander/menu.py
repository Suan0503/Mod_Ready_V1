from linebot.models import TextSendMessage
from extensions import line_bot_api, db
from models import Whitelist, Coupon
from utils.menu import get_menu_carousel
from utils.draw_utils import draw_coupon, get_today_coupon_flex, has_drawn_today, save_coupon_record
from utils.verify_guard import guard_verified
import pytz
from datetime import datetime
from sqlalchemy import cast, Integer  # ★ 券紀錄排序用

def handle_menu(event):
    # ▼ 新增驗證守門，只要不是驗證資訊或輸入手機號碼就攔住未驗證者 ▼
    user_id = event.source.user_id
    user_text = event.message.text.strip()
    if user_text not in ["驗證資訊"]:  # 你可依需求再加白名單
        if not guard_verified(event, line_bot_api):
            return
    # ▲

    tz = pytz.timezone("Asia/Taipei")
    try:
        profile = line_bot_api.get_profile(user_id)
        display_name = profile.display_name
    except Exception:
        display_name = "用戶"

    # 主選單
    if user_text in ["主選單", "功能選單", "選單", "menu", "Menu"]:
        line_bot_api.reply_message(event.reply_token, get_menu_carousel())
        return

    # 驗證資訊
    if user_text == "驗證資訊":
        existing = Whitelist.query.filter_by(line_user_id=user_id).first()
        if existing:
            reply = (
                f"📱 {existing.phone}\n"
                f"🌸 暱稱：{existing.name or display_name}\n"
                f"       個人編號：{existing.id}\n"
                f"🔗 LINE ID：{existing.line_id or '未登記'}\n"
                f"🕒 {existing.created_at.astimezone(tz).strftime('%Y/%m/%d %H:%M:%S')}\n"
                f"✅ 驗證成功，歡迎加入茗殿\n"
                f"🌟 加入密碼：ming666"
            )
            line_bot_api.reply_message(event.reply_token, [TextSendMessage(text=reply), get_menu_carousel()])
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ 你尚未完成驗證，請輸入手機號碼進行驗證。"))
        return

    # 每日抽獎
    if user_text == "每日抽獎":
        if not Whitelist.query.filter_by(line_user_id=user_id).first():
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ 你尚未完成驗證，請先完成驗證才能參加每日抽獎！"))
            return

        today_str = datetime.now(tz).strftime("%Y-%m-%d")
        coupon = Coupon.query.filter_by(line_user_id=user_id, date=today_str, type="draw").first()
        if coupon:
            flex = get_today_coupon_flex(user_id, display_name, coupon.amount)
            line_bot_api.reply_message(event.reply_token, flex)
            return

        amount = draw_coupon()  # 0/100/200/300
        save_coupon_record(user_id, amount, Coupon, db, type="draw")
        flex = get_today_coupon_flex(user_id, display_name, amount)
        line_bot_api.reply_message(event.reply_token, flex)
        return

    # 券紀錄
    if user_text in ["券紀錄", "我的券紀錄"]:
        now = datetime.now(tz)
        today_str = now.strftime("%Y-%m-%d")

        # 本月時間範圍
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if month_start.month == 12:
            next_month_start = month_start.replace(year=month_start.year + 1, month=1)
        else:
            next_month_start = month_start.replace(month=month_start.month + 1)

        # 今日抽獎券
        draw_today = (Coupon.query
            .filter(Coupon.line_user_id == user_id)
            .filter(Coupon.type == "draw")
            .filter(Coupon.date == today_str)
            .order_by(Coupon.id.desc())
            .all())

        # 本月回報文抽獎券
        report_month = (Coupon.query
            .filter(Coupon.line_user_id == user_id)
            .filter(Coupon.type == "report")
            .filter(Coupon.created_at >= month_start)
            .filter(Coupon.created_at < next_month_start)
            .order_by(cast(Coupon.report_no, Integer).asc(), Coupon.id.asc())
            .all())

        # 組訊息
        lines = []
        lines.append("🎁【今日抽獎券】")
        if draw_today:
            for c in draw_today:
                lines.append(f"　　• 日期：{c.date}｜金額：{int(c.amount)}元")
        else:
            lines.append("　　• 無")

        lines.append("\n📝【本月回報文抽獎券】")
        if report_month:
            for c in report_month:
                no = c.report_no.strip() if (c.report_no or "").strip() else "-"
                date_str = c.date or c.created_at.astimezone(tz).strftime("%Y-%m-%d")
                if c.amount and c.amount > 0:
                    lines.append(f"　　• 日期：{date_str}｜編號：{no}｜金額：{int(c.amount)}元")
                else:
                    lines.append(f"　　• 日期：{date_str}｜編號：{no}")
        else:
            lines.append("　　• 無")

        lines.append("\n※ 回報文抽獎券中獎名單與金額，將於每月抽獎公布")

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="\n".join(lines)))
        return
