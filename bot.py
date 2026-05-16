import logging
import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

from config import Config
from database import Database
from downloader import VideoDownloader
from watermark_remover import WatermarkRemover
from queue_manager import DownloadQueue
from admin_panel import AdminPanel
from utils import format_size, format_duration, create_progress_bar, escape_markdown, is_valid_url

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

db = Database(Config.DATABASE_URL)
downloader = VideoDownloader()
queue = DownloadQueue(max_concurrent=3)
admin_panel = AdminPanel(db)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.get_user(user.id)

    keyboard = [
        [InlineKeyboardButton("📥 تحميل فيديو", callback_data='download_video')],
        [InlineKeyboardButton("🎵 تحميل صوت", callback_data='download_audio')],
        [InlineKeyboardButton("ℹ️ معلوماتي", callback_data='my_info')],
    ]

    if user.id in Config.ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("🔧 لوحة التحكم", callback_data='admin_panel')])

    await update.message.reply_text(
        f"""👋 مرحباً {user.first_name}!

🤖 **بوت تحميل الفيديوهات العالمي**

✅ يدعم 1000+ منصة
✅ أعلى جودة ممكنة
✅ بدون علامة مائية
✅ مجاني بالكامل
✅ تحميل 24/7

📤 **أرسل رابط الفيديو مباشرة**
""",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    url = update.message.text.strip()

    user = db.get_user(user_id)
    if user.is_banned:
        await update.message.reply_text("🚷 حسابك محظور!")
        return

    if not is_valid_url(url):
        await update.message.reply_text("❌ الرابط غير صالح!")
        return

    platform = downloader.get_platform(url)
    if platform == 'unknown':
        await update.message.reply_text("❌ المنصة غير مدعومة!")
        return

    can_dl, msg = db.can_download(user_id)
    if not can_dl:
        await update.message.reply_text(msg)
        return

    context.user_data['url'] = url
    context.user_data['platform'] = platform

    keyboard = [
        [InlineKeyboardButton("🎯 أفضل جودة تلقائية", callback_data='quality_best')],
        [InlineKeyboardButton("📱 1080p", callback_data='quality_1080')],
        [InlineKeyboardButton("💻 720p", callback_data='quality_720')],
        [InlineKeyboardButton("🎵 صوت فقط (MP3)", callback_data='format_audio')],
    ]

    try:
        info = await downloader.get_info(url)
        preview = f"""
🎬 **{escape_markdown(info['title'][:50])}**

👤 القناة: {escape_markdown(info['uploader'] or 'Unknown')}
⏱️ المدة: {format_duration(info['duration'] or 0)}
📺 المنصة: {platform.upper()}

اختر الجودة:
"""
    except:
        preview = f"""
📎 الرابط: {url[:50]}...
📺 المنصة: {platform.upper()}

اختر الجودة:
"""

    await update.message.reply_text(
        preview,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    if data == 'admin_panel':
        await admin_panel.show_panel(update, context)
        return
    elif data.startswith('admin_'):
        await admin_panel.handle_callback(update, context)
        return

    if data == 'download_video':
        await query.edit_message_text("📤 أرسل رابط الفيديو:")
        return
    elif data == 'download_audio':
        await query.edit_message_text("🎵 أرسل رابط الصوت:")
        context.user_data['audio_only'] = True
        return
    elif data == 'my_info':
        await show_user_info(query, user_id)
        return
    elif data == 'back_start':
    # ارسل رسالة جديدة بدل edit
    await query.delete_message()
    await start(update, context)
    return


    if data.startswith('quality_'):
        quality = data.replace('quality_', '')
        context.user_data['quality'] = quality
        context.user_data['audio_only'] = False
        await start_download(update, context)
        return
    elif data == 'format_audio':
        context.user_data['quality'] = 'best'
        context.user_data['audio_only'] = True
        await start_download(update, context)
        return

async def show_user_info(query, user_id):
    user, downloads = db.get_user_stats(user_id)

    remaining = Config.DAILY_LIMIT - user.daily_downloads

    dl_text = "\n".join([
        f"• {d.title[:25]}... ({d.quality or 'N/A'})"
        for d in downloads[:5]
    ]) if downloads else "لا يوجد تحميلات"

    text = f"""
ℹ️ **معلومات حسابك**

📊 التحميلات الكلية: {user.total_downloads}
📅 اليوم: {user.daily_downloads}/{Config.DAILY_LIMIT}
✅ المتبقي اليوم: {remaining}

**آخر التحميلات:**
{dl_text}

🆓 البوت مجاني بالكامل!
"""

    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data='back_start')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def start_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    url = context.user_data.get('url')
    quality = context.user_data.get('quality', 'best')
    audio_only = context.user_data.get('audio_only', False)
    platform = context.user_data.get('platform', 'unknown')

    if not url:
        await query.edit_message_text("❌ خطأ: الرابط غير موجود!")
        return

    dl_id = db.add_download(user_id, url, platform, "Processing...")

    item, position = await queue.add(
        user_id, url, quality, audio_only,
        lambda item: process_download(update, context, item, dl_id, url, quality, audio_only, platform)
    )

    if position > 0:
        await query.edit_message_text(
            f"""
⏳ **أنت في الانتظار**
📊 موقعك: {position}
⏱️ الوقت المقدر: ~{position * 2} دقيقة
""",
            parse_mode='Markdown'
        )
    else:
        await query.edit_message_text("🔄 جاري التحميل...")

async def process_download(update, context, item, dl_id, url, quality, audio_only, platform):
    query = update.callback_query
    user_id = update.effective_user.id

    try:
        await query.edit_message_text("📥 جاري تحليل الفيديو...")

        last_update = [0]
        async def progress_hook(d):
            if d['status'] == 'downloading':
                percent = d.get('downloaded_bytes', 0) / max(d.get('total_bytes', 1), 1) * 100
                if percent - last_update[0] > 10:
                    last_update[0] = percent
                    bar = create_progress_bar(percent)
                    try:
                        await query.edit_message_text(
                            f"📥 جاري التحميل...\n{bar}\n⚡ السرعة: {d.get('speed', 0):.1f} KB/s",
                            parse_mode='Markdown'
                        )
                    except:
                        pass

        result = await downloader.download(url, quality, audio_only, progress_hook)

        # إزالة العلامة المائية للجميع
        if platform in ['tiktok', 'instagram']:
            await query.edit_message_text("🧹 جاري إزالة العلامة المائية...")
            clean_path = result['filename'].replace('.mp4', '_clean.mp4')
            WatermarkRemover.process_video(result['filename'], platform)
            if os.path.exists(clean_path):
                result['filename'] = clean_path

        file_size = result['filesize']

        await query.edit_message_text("📤 جاري الإرسال...")

        caption = f"""
🎬 {escape_markdown(result['title'][:50])}

📊 الجودة: {result.get('height', 'N/A')}p
📦 الحجم: {format_size(file_size)}
⏱️ المدة: {format_duration(result.get('duration', 0))}
✅ @YourBot | مجاني بالكامل
"""

        with open(result['filename'], 'rb') as f:
            if audio_only:
                await context.bot.send_audio(
                    chat_id=user_id,
                    audio=f,
                    caption=caption,
                    title=result['title'][:50],
                    performer=result.get('uploader', 'Unknown'),
                    parse_mode='Markdown'
                )
            else:
                await context.bot.send_video(
                    chat_id=user_id,
                    video=f,
                    caption=caption,
                    supports_streaming=True,
                    parse_mode='Markdown'
                )

        db.complete_download(dl_id, f"{result.get('height', 'N/A')}p", file_size)
        downloader.cleanup(result['filename'])

        keyboard = [[InlineKeyboardButton("📥 تحميل آخر", callback_data='download_video')]]
        await query.edit_message_text(
            "✅ **تم التحميل بنجاح!**\n\nأرسل رابط جديد:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Download error: {e}")
        db.complete_download(dl_id, 'error', 0, 'failed')
        await query.edit_message_text(f"❌ حدث خطأ: {str(e)[:100]}")

async def handle_admin_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in Config.ADMIN_IDS and context.user_data.get('admin_action'):
        await admin_panel.handle_admin_message(update, context)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text("❌ حدث خطأ غير متوقع!")
    except:
        pass

async def main():
    os.makedirs(Config.TEMP_DIR, exist_ok=True)
    application = Application.builder().token(Config.BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel.show_panel))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_messages))
    application.add_error_handler(error_handler)
    
    # شغل queue في background
    asyncio.create_task(queue.process_queue())
    
    await application.initialize()
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    
    # خليه يشتغل للأبد
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())


    
