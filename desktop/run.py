import os
import sys
import threading
import time
import webview
from django.core.management import execute_from_command_line

# Set environment for Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

def run_django():
    # Run Django server (not suitable for high concurrency prod, but fine for single-user desktop)
    # Using execute_from_command_line directly
    sys.argv = ["manage.py", "runserver", "127.0.0.1:8000", "--noreload"]
    execute_from_command_line(sys.argv)

def start_desktop_app():
    # Start Django in a separate thread
    t = threading.Thread(target=run_django)
    t.daemon = True
    t.start()
    
    # Wait a bit for server to start
    time.sleep(2)
    
    # Create window
    webview.create_window(
        "Delta Sharm Resort Management", 
        "http://127.0.0.1:8000/admin/",
        width=1200,
        height=800,
        resizable=True
    )
    
    # Start webview (this blocks until window is closed)
    webview.start()

if __name__ == "__main__":
    start_desktop_app()
