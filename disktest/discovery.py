"""Read-only Linux inventory; no authorization to write a device."""
from __future__ import annotations

import json
import subprocess
import sys


def discover():
    if sys.platform != "linux":
        raise RuntimeError("Disk keşfi Linux Live ortamı gerektirir. Windows'ta demo kullanın.")
    result = subprocess.run(["lsblk", "--json", "--tree", "--bytes", "--paths", "--output",
                             "PATH,TYPE,SIZE,MODEL,SERIAL,WWN,TRAN,MOUNTPOINTS,RO,RM"],
                            capture_output=True, text=True, check=True, timeout=15)
    return json.loads(result.stdout)
