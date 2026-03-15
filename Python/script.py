import os
import getpass
import platform
from datetime import datetime
import socket
import subprocess
import psutil
import tkinter as tk
from tkinter import scrolledtext

# -----------------------------
# Helper functions
# -----------------------------
def log(msg):
    output_box.insert(tk.END, f"{msg}\n")
    output_box.see(tk.END)  # auto scroll
    with open("script_log.txt", "a") as f:
        f.write(f"{msg}\n")

def show_system_info():
    log("🔥 System Info")
    log(f"Time: {datetime.now()}")
    log(f"User: {getpass.getuser()}")
    log(f"Computer: {platform.node()}")
    log(f"OS: {platform.system()} {platform.release()}")

def list_files():
    log("📂 Current Folder Files:")
    for f in os.listdir('.'):
        log(f" - {f}")

def show_drives():
    log("💽 Drives:")
    if platform.system() == "Windows":
        for drive in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            if os.path.exists(f"{drive}:\\"):
                log(f" - {drive}:\\")
    else:
        log(" - Not Windows, skipping drives")

def show_processes():
    log("⚡ Top 10 Running Processes:")
    for i, proc in enumerate(psutil.process_iter(attrs=['pid', 'name']), 1):
        log(f"{proc.info['pid']} - {proc.info['name']}")
        if i >= 10:
            break

def network_info():
    hostname = socket.gethostname()
    ip = socket.gethostbyname(hostname)
    log(f"🌐 Hostname: {hostname}")
    log(f"🌐 IP Address: {ip}")
    log("📡 Ping google.com:")
    try:
        result = subprocess.run(["ping", "-n", "1", "google.com"], capture_output=True, text=True)
        log(result.stdout)
    except Exception as e:
        log(f"Ping failed: {e}")

def clear_output():
    output_box.delete('1.0', tk.END)

# -----------------------------
# GUI Setup
# -----------------------------
root = tk.Tk()
root.title("Python Control Panel")
root.geometry("600x500")

# Buttons
tk.Button(root, text="System Info", command=show_system_info).pack(fill=tk.X)
tk.Button(root, text="List Files", command=list_files).pack(fill=tk.X)
tk.Button(root, text="Show Drives", command=show_drives).pack(fill=tk.X)
tk.Button(root, text="Top 10 Processes", command=show_processes).pack(fill=tk.X)
tk.Button(root, text="Network Info", command=network_info).pack(fill=tk.X)
tk.Button(root, text="Clear Output", command=clear_output).pack(fill=tk.X)

# Output box
output_box = scrolledtext.ScrolledText(root, wrap=tk.WORD, height=20)
output_box.pack(fill=tk.BOTH, expand=True)

# Run the GUI
root.mainloop()
