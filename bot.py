import os
import math
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from moviepy.editor import VideoFileClip
import logging
import aiohttp
import asyncio
from telegram.error import BadRequest
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "8083480600:AAGiwI__cQ9MpwXE7Uy50WIZPXWRwufuiqI"
MAX_WORKERS = 3  # Maximum concurrent video processes

class VideoProcessor:
    def __init__(self):
        self.processing_queue = asyncio.Queue()
        self.executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
    
    async def process_queue(self):
        while True:
            task = await self.processing_queue.get()
            asyncio.create_task(self.process_single_video(*task))
            self.processing_queue.task_done()

    async def add_to_queue(self, update, context, video_message):
        await self.processing_queue.put((update, context, video_message))

    async def update_progress(self, message, text, last_text=None):
        if text != last_text:
            try:
                await message.edit_text(text)
                return text
            except BadRequest:
                pass
        return last_text

    async def download_file(self, file_url, dest_path, status_message):
        async with aiohttp.ClientSession() as session:
            async with session.get(file_url) as response:
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                last_text = None
                
                with open(dest_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(1024 * 1024 * 5):  # 5MB chunks
                        f.write(chunk)
                        downloaded += len(chunk)
                        progress = min(25, int((downloaded / total_size) * 25))
                        text = f"⏳ Downloading: {progress}%\n{'⬛' * progress}{'⬜' * (25 - progress)}"
                        last_text = await self.update_progress(status_message, text, last_text)

    async def process_single_video(self, update, context, video_message):
        status_message = await video_message.reply_text("🎬 Queued for processing...")
        try:
            video = await video_message.video.get_file()
            video_path = f"downloads/{video_message.video.file_id}.mp4"
            output_path = f"outputs/{video_message.video.file_id}_clip.mp4"
            
            os.makedirs("downloads", exist_ok=True)
            os.makedirs("outputs", exist_ok=True)

            # Download phase (0-25%)
            await self.download_file(video.file_path, video_path, status_message)

            # Processing phase (25-75%)
            await self.update_progress(status_message, "🔄 Processing: 50%\n⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜")

            def process_video_sync():
                with VideoFileClip(video_path) as clip:
                    duration = clip.duration
                    clip_duration = 3 if duration <= 30 else 7
                    mid_point = duration / 2
                    start_time = mid_point - (clip_duration / 2)
                    subclip = clip.subclip(start_time, start_time + clip_duration)
                    subclip.write_videofile(output_path, codec='libx264', audio_codec='aac', verbose=False)

            await asyncio.get_event_loop().run_in_executor(self.executor, process_video_sync)

            # Uploading phase (75-100%)
            await self.update_progress(status_message, "📤 Uploading: 90%\n⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬜⬜⬜")

            with open(output_path, 'rb') as f:
                await video_message.reply_video(
                    video=f,
                    caption="✂️ Shortened clip from your video",
                    reply_to_message_id=video_message.message_id
                )

            await self.update_progress(status_message, "✅ Complete: 100%\n⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛⬜")

        except Exception as e:
            logger.error(f"Error processing video: {e}")
            await self.update_progress(status_message, "❌ Error processing video. Please try again!")
        finally:
            if os.path.exists(video_path):
                os.remove(video_path)
            if 'output_path' in locals() and os.path.exists(output_path):
                os.remove(output_path)

video_processor = VideoProcessor()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Send videos to create clips! I can handle multiple videos at once.")

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await video_processor.add_to_queue(update, context, update.message)

def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.VIDEO, handle_video))
    
    # Start video processing queue
    loop = asyncio.get_event_loop()
    loop.create_task(video_processor.process_queue())
    
    print("🤖 Bot started with multi-video processing!")
    application.run_polling()

if __name__ == '__main__':
    main()
