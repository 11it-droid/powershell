import os
import getpass
from datetime import datetime

print("🔥 Python script is running!")

username = getpass.getuser()
computer = os.environ.get("COMPUTERNAME", "Unknown")
time_now = datetime.now()

print(f"User: {username}")
print(f"Computer: {computer}")
print(f"Time: {time_now}")
