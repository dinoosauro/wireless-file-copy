import os 
import sys
import urllib.request
import urllib.parse
import json
from datetime import datetime
import time
import shlex


def get_files_recursively(directory: str) -> str:
    """
    Get the files that are available in the provided directory, and look also in all of the subdirectories.
    Attributes:
        directory (`str`): the directory to look
    Returns:
        the string with the **relative path** of the files in the directory
    """
    files = []
    start_path = len(sys.argv[1]) + 1
    for root, _, filenames in os.walk(directory):
        for filename in filenames:
            if not filename.startswith(".DS") and not filename.startswith("._"): 
                files.append(os.path.join(root, filename)[start_path:])
    return files

def format_value(str):
    """
    Convert the byte length to a readable string
    Attributes:
        str: actually, any value that can be converted to a float, that indicates the number of bytes
    """
    possible_types = ["byte(s)", "kilobyte(s)", "megabyte(s)", "gigabyte(s)", "terabyte(s)"]
    i = 0
    num = float(str)
    while (num / 1024 >= 1):
        num /= 1024
        i = i+1
        if i == 4: break
    return f"{num:.2f} {possible_types[i]}"

def get_epoch_str(val): 
    """
    Convert a Unix Epoch to a readable string
    Attributes:
        val: any value that can be converted to a float
    """
    return datetime.fromtimestamp(float(val)).strftime('%Y-%m-%d %H:%M:%S')

script_settings = dict(allowed_extensions=[""], overwrite=0, auth_token="") 

# We'll try getting the authentication key from the env file. Since I don't want to use any external library (and I want to deploy both the server and the client script in only a file), there'll be a few duplicated script

def update_property(lines: list[str], settings_key: str, look_for: str, type = 0):
    """
    Update a property reading from an env file
    """
    for line in lines:
        line = line.strip()
        if line.rfind("=") == -1 or line.startswith("#"): continue
        start = shlex.split(line[:line.index("=")])[0] # Let's get the key of this env line
        if (start == look_for):
            length = line.index("=") + 1
            key = line[length:]
            if key.startswith("\"") or key.startswith("'"): # We need to escape the string
                key = shlex.split(key)[0]
            elif key.rfind(" ") != -1: # Get only the valid part (so, before the space)
                key = key[:key.rfind(" ")]
            script_settings[settings_key] = int(key) if type == 1 else key.split(",") if type == 2 else key
            break

# We'll now try reading the properties from the env file
if (os.path.isfile(f"{os.getcwd()}{os.path.sep}wireless-file-copy.env")):
    with (open(f"{os.getcwd()}{os.path.sep}wireless-file-copy.env", "r")) as file:
        available_lines = file.readlines()
        for [key, look, number] in [["auth_token", "WIRELESS_FILE_COPY_KEY", 0], ["overwrite", "WIRELESS_FILE_COPY_OVERWRITE_SETTINGS", 1], ["allowed_extensions", "WIRELESS_FILE_COPY_ALLOWED_EXTENSIONS", 2]]: update_property(available_lines, key, look, number)

for i in range(2, len(sys.argv)): # Update the values reading the console arguments
    match(sys.argv[i]):
        case "--allowed-extensions":
            script_settings["allowed_extensions"] = sys.argv[i+1].split(",")
        case "--overwrite":
            j = int(sys.argv[i + 1])
            if (i > -1 and i < 4): script_settings["overwrite"] = j
        case "--authentication-key":
            script_settings["auth_token"] = sys.argv[i+1]

class ProgressFile:
    def __init__(self, f, size):
        """
        Create the ProgressFile class, that'll track the file upload progress
        Attributes:
            f: the File to copy
            size: the parsed string of the file size
        """
        self.f = f
        """
        The file that needs to be copied
        """
        self.size = size
        """
        A string that displays in an human-readable form the file size
        """
        self.uploaded = 0
        """
        The number of bytes uploaded
        """
        self.last_print = time.time()
        """
        The last time the console has been updated
        """
    def read(self, size):
        chunk = self.f.read(size) 
        if chunk:
            self.uploaded += len(chunk)
            now = time.time()
            if now - self.last_print >= 1: # Let's wait a second before updating the console
                print(f"{format_value(self.uploaded)} uploaded [Total: {self.size}]", end="\033[K\r")
                self.last_print = now
        return chunk


session_token = ""
"""
The token that needs to be passed for authentication. It already includes "Bearer" at the start
"""

try: # Fetch token
    byte = bytes(script_settings["auth_token"], "utf-8")
    req = urllib.request.Request(f"{sys.argv[2]}/auth/", method="POST", data=(byte), headers={
        "Content-Length": len(byte)
    })
    with(urllib.request.urlopen(req)) as token_req:
        res_json = json.loads(token_req.read().decode("utf-8"))
        session_token = f"{res_json['auth_type']} {res_json['token']}"
except:
    raise Exception("Failed to obtain server token. No operation can be done.")
        

for file in get_files_recursively(sys.argv[1]):
    for extension in script_settings["allowed_extensions"]: # Check that the user wants to upload that file
        if file.lower().endswith(extension.lower()):
            full_file_path = f"{sys.argv[1]}{os.path.sep}{file}"
            stat = os.stat(full_file_path)
            file_size = stat.st_size
            upload_this = True # If the current file should be uploaded or not
            with open(full_file_path, "rb", buffering=8192) as file_read:
                print(f"\033[34mUploading {full_file_path}\033[0m")
                # We'll now check if the file already exists, by doing a GET request to the server. 
                allow_overwrite = "1" if script_settings["overwrite"] == 2 else "0"
                file_info = urllib.request.Request(f"{sys.argv[2]}/info/?url={urllib.parse.quote(file)}&systype={urllib.parse.quote(os.name)}", method="GET", headers={
                    "Authentication": session_token
                })
                file_info_res = urllib.request.urlopen(file_info)
                if file_info_res.getcode() == 200: # There's already a file with the same name. Let's decode the JSON file so that we can compare it, and we'll ask the user if they want to replace it.
                    object = json.loads(file_info_res.read().decode("utf-8"))
                    if object["error"] == "already_exists":
                        if script_settings["overwrite"] == 3: # In this case, we'll skip overwriting it only if if the file has the same last modified date and the same size
                            if (str(file_size) != str(object["file_size"]) or str(object["last_edited"]) != str(stat.st_mtime)):
                                allow_overwrite = "1"
                            else: upload_this = False # Skip upload
                        elif script_settings["overwrite"] == 1: # Skip overwrite
                            upload_this = False
                        elif script_settings["overwrite"] == 2: # Always enable overwrite
                            upload_this = True
                        elif (input(f'\033[35mA file with the same name already exists.\033[0m\n\033[{"90" if str(object["last_edited"]) == str(stat.st_mtime) else "33"}mLast edited date: {get_epoch_str(object["last_edited"])} [Already there] —> {get_epoch_str(stat.st_mtime)} [New file]\033[0m\n\033[{"90" if str(object["file_size"]) == str(stat.st_size) else "33"}mFile size: {format_value(object["file_size"])} [Already there] —> {format_value(stat.st_size)} [New file]\033[0m\n\033[36mOverwrite? (y/N)\033[0m').strip().lower() == "y"): # Ask the user
                            allow_overwrite = "1"
                        else: upload_this = False
                # Let's now upload the file
                req = urllib.request.Request(f"{sys.argv[2]}/upload/?path={urllib.parse.quote(file)}&last_edit={stat.st_mtime}&overwrite={allow_overwrite}&systype={urllib.parse.quote(os.name)}", data=ProgressFile(file_read, format_value(file_size)), method="PUT", headers={
                    "Content-Length": str(stat.st_size),
                    "Authentication": session_token
                })
                try:
                    if upload_this:
                        with urllib.request.urlopen(req):
                            print(f"\n\r\033[32;1mSuccessful file copy: {file}\033[0m")
                    else: print(f"\033[90;1mSkipped file copy: {file}\033[0m")
                except urllib.error.URLError as e:
                    print(f"\n\r\033[31;1mFailed file copy: {file}\033[0m")
            break # Stop looking to the files

# Delete the session token from the valid ones
urllib.request.urlopen(urllib.request.Request(f"{sys.argv[1]}/logout/", method="GET", headers={
    "Authorization": session_token
}))
