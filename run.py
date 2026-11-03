"""
AniFilter AI - Entry Point & Server Runner
Starts the FastAPI application and serves the web interface.
"""

import uvicorn
import webbrowser
import threading
import time

PORT = 8080

def open_browser():
    time.sleep(1.2)
    url = f"http://localhost:{PORT}"
    print(f"\n🚀 เปิดเว็บแอปพลิเคชันที่: {url}\n")
    try:
        webbrowser.open(url)
    except Exception:
        pass

if __name__ == "__main__":
    print("=" * 60)
    print("   AniFilter AI — Universal Canon & Episode Intelligence")
    print("=" * 60)
    print(f"กำลังเริ่มระบบเซิร์ฟเวอร์ที่ http://localhost:{PORT} ...")

    threading.Thread(target=open_browser, daemon=True).start()

    uvicorn.run("backend.main:app", host="0.0.0.0", port=PORT, reload=False)
