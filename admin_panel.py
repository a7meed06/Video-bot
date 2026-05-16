from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import Config

class AdminPanel:
    def __init__(self, database):
        self.db = database

    def is_admin(self, user_id):
        return user_id in Config.ADMIN_IDS

    async def show_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not self.is_admin(user_id):
            await update.message.reply_text("⛔ ممنوع!")
            return

        stats = self.db.get_stats()

        keyboard = [
            [InlineKeyboardButton("📊 إحصائيات", callback_data='admin_stats')],
            [InlineKeyboardButton("🔍 بحث مستخدم", callback_data='admin_search')],
            [InlineKeyboardButton("🚷 حظر/فك حظر", callback_data='admin_ban')],
        ]

        text = f'''
🔧 **لوحة تحكم الأدمن**

📊 الإحصائيات:
• المستخدمين: {stats['total_users']:,}
• إجمالي التحميلات: {stats['total_downloads']:,}
• تحميلات اليوم: {stats['today_downloads']:,}
• نشطين اليوم: {stats['active_today']:,}
'''

        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        if not self.is_admin(user_id):
            return

        data = query.data

        if data == 'admin_stats':
            await self.show_stats(query)
        elif data == 'admin_search':
            await query.edit_message_text("🔍 أرسل ID المستخدم:")
            context.user_data['admin_action'] = 'search'
        elif data == 'admin_ban':
            await query.edit_message_text("🚷 أرسل ID المستخدم للحظر/فك الحظر:")
            context.user_data['admin_action'] = 'ban'

    async def show_stats(self, query):
        stats = self.db.get_stats()
        text = f'''
📊 **إحصائيات كاملة**

👥 المستخدمين: {stats['total_users']:,}
📥 إجمالي التحميلات: {stats['total_downloads']:,}
📅 تحميلات اليوم: {stats['today_downloads']:,}
🔥 نشطين اليوم: {stats['active_today']:,}
'''
        await query.edit_message_text(text, parse_mode='Markdown')

    async def handle_admin_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not self.is_admin(user_id):
            return

        action = context.user_data.get('admin_action')
        text = update.message.text

        if action == 'search':
            try:
                target_id = int(text)
                user, downloads = self.db.get_user_stats(target_id)

                if user:
                    dl_text = "\n".join([
                        f"• {d.title[:30]}... ({d.status})" 
                        for d in downloads
                    ]) if downloads else "لا يوجد"

                    msg = f'''
👤 **مستخدم:** {user.id}
📛 الاسم: {user.first_name or 'N/A'}
📊 التحميلات: {user.total_downloads}
📅 اليوم: {user.daily_downloads}/{Config.DAILY_LIMIT}
🚷 محظور: {'نعم' if user.is_banned else 'لا'}

**آخر التحميلات:**
{dl_text}
'''
                    await update.message.reply_text(msg, parse_mode='Markdown')
                else:
                    await update.message.reply_text("❌ المستخدم غير موجود")
            except ValueError:
                await update.message.reply_text("❌ ID غير صالح")

            context.user_data.pop('admin_action', None)

        elif action == 'ban':
            try:
                target_id = int(text)
                self.db.ban_user(target_id)
                await update.message.reply_text(f"✅ تم حظر/فك حظر المستخدم {target_id}")
            except ValueError:
                await update.message.reply_text("❌ ID غير صالح")

            context.user_data.pop('admin_action', None)
