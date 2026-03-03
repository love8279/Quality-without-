import os
import re
import asyncio
import requests
import logging
from pyrogram import Client, filters
from pyromod import listen
from pyrogram.types import Message
import config

# Logging setup
logging.basicConfig(level=logging.INFO)

# Bot Client Setup 
# (Note: Pyromod automatically patches the Client)
bot = Client(
    "QualityBot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN
)

def clean_filename(text):
    """अवैध अक्षरों को फ़ाइल नाम से हटाता है"""
    return re.sub(r'[\\/*?:"<>|]', "", text).strip()

def count_urls(file_path):
    """फ़ाइल में लिंक्स की गिनती करता है"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        total_links = len(lines)
        video_links = sum(1 for line in lines if any(ext in line.lower() for ext in [".m3u8", ".mp4"]))
        pdf_links = sum(1 for line in lines if ".pdf" in line.lower())
        return total_links, pdf_links, video_links
    except Exception:
        return 0, 0, 0

@bot.on_message(filters.command(["start"]))
async def start_handler(bot, m: Message):
    await m.reply_text("नमस्ते! Quality Education बैच निकालने के लिए /qe कमांड का उपयोग करें।")

@bot.on_message(filters.command(["qe"]))
async def quality_command_handler(bot, m: Message):
    user_id = m.from_user.id
    temp_msg = await m.reply_text("🔍 Fetching available batches...", disable_web_page_preview=True)

    headers = {
        "Host": "test.qualityeducation.in",
        "accept-encoding": "gzip",
        "user-agent": "okhttp/3.14.7"
    }

    try:
        # Step 1: Get Categories
        r = requests.get("https://test.qualityeducation.in/api/video-category-get", headers=headers)
        j = r.json()
        listing = "🎓 **Available Course Batches:**\n\n"
        
        for i in j["data"]:
            batch_id = i.get("id")
            category_name = i.get("category_name", "No Name")
            listing += f"🔹 `{batch_id}` → **{category_name}**\n"

        await temp_msg.edit_text(listing)

        # Step 2: Ask for Course ID
        bi_msg = await bot.ask(m.chat.id, "🆔 Please enter the **Course ID** to proceed:")
        bi = bi_msg.text.strip()

        update = await m.reply_text(f"⏳ Extracting data for ID `{bi}`...", disable_web_page_preview=True)

        # Step 3: Fetch Batch Details
        r2 = requests.get(f"https://test.qualityeducation.in/api/combo-get/318096/{bi}", headers=headers)
        j2 = r2.json()

        # Check if data exists
        if not j2.get("data") or not j2["data"].get("video"):
            await update.edit_text("❌ इस ID के लिए कोई डाटा नहीं मिला।")
            return

        dn = j2["data"]["video"][0].get("title", "Batch")
        file_name = f"{clean_filename(bi)}_{clean_filename(dn)}.txt"

        # Step 4: Scraping Links WITHOUT Encryption
        with open(file_name, "w", encoding='utf-8') as f:
            for video_data in j2["data"]["video"]:
                di = video_data.get("id")
                r3 = requests.get(f"https://test.qualityeducation.in/api/subject-get/{di}", headers=headers)
                j3 = r3.json()
                for subject in j3.get("data", []):
                    ti = subject.get("id")
                    r4 = requests.get(f"https://test.qualityeducation.in/api/subject-get/{di}/{ti}", headers=headers)
                    j4 = r4.json()
                    for content in j4.get("data", []):
                        topic = content.get("topic_name", "Untitled")
                        pdf = content.get("pdf_link")
                        v_links = [
                            content.get("quality_1080"), content.get("quality_720"),
                            content.get("quality_480"), content.get("quality_360"),
                            content.get("video_link")
                        ]
                        v = next((vl for vl in v_links if vl), None)
                        
                        if pdf:
                            f.write(f"{topic}: {pdf}\n")
                        if v:
                            f.write(f"{topic}: {v}\n")

        # Step 5: Send File
        total, pdfs, videos = count_urls(file_name)
        caption = (
            f"<b>📦 Batch Extracted!</b>\n"
            f"<b>📛 Batch:</b> <code>{dn}</code>\n"
            f"<b>📊 Content:</b>\n"
            f"    🔗 Total: <code>{total}</code>\n"
            f"    🎥 Videos: <code>{videos}</code>\n"
            f"    📄 PDFs: <code>{pdfs}</code>\n\n"
            f"<b>🏆 Extracted By:</b> {m.from_user.mention}"
        )

        await m.reply_document(file_name, caption=caption)
        
        # Cleanup
        if os.path.exists(file_name):
            os.remove(file_name)
        await update.delete()

    except Exception as e:
        logging.error(f"Error: {e}")
        await m.reply_text(f"❌ Error: `{str(e)}`")

# --- सुधारित स्टार्टअप सेक्शन ---
async def start_bot():
    await bot.start()
    logging.info("--- BOT STARTED SUCCESSFULLY ---")
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(start_bot())
    except KeyboardInterrupt:
        logging.info("--- BOT STOPPED ---")
    
