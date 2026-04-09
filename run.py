"""
run.py  –  SkillMatch one-command launcher
Usage:  python run.py
"""

import os, sys, subprocess, time, sqlite3, threading

_APP_ROOT = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.abspath(os.getenv("SKILLMATCH_DATA_DIR", _APP_ROOT))
DB_PATH = os.path.join(_DATA, "jobs.db")
RUN_ALERT_WORKER = os.getenv("RUN_ALERT_WORKER", "0") == "1"

def db_exists_and_populated():
    if not os.path.exists(DB_PATH):
        return False
    try:
        conn = sqlite3.connect(DB_PATH)
        count = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        conn.close()
        return count > 0
    except Exception:
        return False

def main():

    if db_exists_and_populated():
        print("✅  jobs.db already exists – skipping seed step.")
    else:
        print("🗄️  Creating and seeding jobs.db …")
        result = subprocess.run([sys.executable, "create_db.py"], check=False)
        if result.returncode != 0:
            print("❌  create_db.py failed. Aborting.")
            sys.exit(1)
        print("✅  Database ready.")

    alert_thread = None
    alert_stop = threading.Event()
    if RUN_ALERT_WORKER:
        def _alert_loop():
            from src.alerts import run_alert_cycle
            while not alert_stop.is_set():
                try:
                    run_alert_cycle()
                except Exception as e:
                    print(f"[alerts] cycle failed: {e}")
                alert_stop.wait(60 * 60)
        alert_thread = threading.Thread(target=_alert_loop, daemon=True)
        alert_thread.start()
        print("🔔  Alert worker enabled (hourly cycle).")

    print("\n🚀  Starting FastAPI backend on http://127.0.0.1:8000 …")
    api_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main12:app",
         "--host", "127.0.0.1", "--port", "8000", "--reload"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )

  
    import urllib.request, urllib.error
    for attempt in range(30):
        time.sleep(0.5)
        try:
            urllib.request.urlopen("http://127.0.0.1:8000/jobs/filters", timeout=2)
            print("✅  FastAPI is up.")
            break
        except Exception:
            pass
    else:
        print("⚠️  FastAPI did not start in time – check errors below.")
     
        for line in api_proc.stdout:
            print("   [api]", line, end="")
        api_proc.terminate()
        sys.exit(1)

 
    print("\n🎨  Starting Streamlit frontend on http://localhost:8501 …")
    st_proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py",
         "--server.port", "8501", "--server.headless", "false"],
    )

    print("\n" + "─" * 52)
    print("  SkillMatch is running!")
    print("  Frontend : http://localhost:8501")
    print("  API docs : http://127.0.0.1:8000/docs")
    print("  Press Ctrl+C to stop both servers.")
    print("─" * 52 + "\n")

    try:
       
        for line in api_proc.stdout:
            print("[api]", line, end="")
    except KeyboardInterrupt:
        pass
    finally:
        print("\n🛑  Shutting down…")
        alert_stop.set()
        api_proc.terminate()
        st_proc.terminate()

if __name__ == "__main__":
    main()
