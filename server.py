import sys
import os
import json
import urllib.parse
import secrets
import shlex

from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler


server_settings = dict(authentication_key="", port=14937, server_address="")

# We'll try getting the authentication key from the env file. Since I don't want to use any external library (and I want to deploy both the server and the client script in only a file), there'll be a few duplicated script

def update_property(lines: list[str], settings_key: str, look_for: str, is_number = False):
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
            server_settings[settings_key] = int(key) if is_number else key
            break

if (os.path.isfile(f"{os.getcwd()}{os.path.sep}wireless-file-copy.env")):
    with (open(f"{os.getcwd()}{os.path.sep}wireless-file-copy.env", "r")) as file:
        available_lines = file.readlines()
        for [key, look, number] in [["authentication_key", "WIRELESS_FILE_COPY_KEY", False], ["server_address", "WIRELESS_FILE_COPY_ADDRESS", False], ["port", "WIRELESS_FILE_COPY_PORT", True]]: update_property(available_lines, key, look, number)

print(server_settings)

for i in range(2, len(sys.argv)):
    match(sys.argv[i]):
        case "--authentication-key":
            server_settings["authentication_key"] = sys.argv[i+1]
        case "--port":
            server_settings["port"] = int(sys.argv[i+1])
        case "--address":
            server_settings["server_address"] = sys.argv[i+1]


def send_error(self, error = "missing_params", error_code = 400):
    """
    Send a standard error response
    """
    self.send_response(error_code)
    self.send_header("Content-Type", "application/json")
    self.send_header("Connection", "close")
    self.end_headers()
    self.wfile.write(bytes(json.dumps({
        "error": error,
    }), "utf-8"))
    self.close_connection = True

stored_tokens = []

class ServerRequestHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args): # Disable any kind of logging of server requests
        pass
    def do_GET(self): 
        url_type = urllib.parse.urlparse(f"http://localhost{self.path}")
        if url_type.path == "/info/": # Check if a file exists in that path. If so, return the file size and last edited date
            query = urllib.parse.parse_qs(url_type.query)
            if self.headers.get("Authentication", "Bearer ")[7:] in stored_tokens:
                if "url" in query:
                    suggested_path = f"{sys.argv[1]}{os.path.sep}{query["url"][0]}"
                    if os.path.isfile(suggested_path):
                        file_stat = os.stat(suggested_path)
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(bytes(json.dumps({
                            "error": "already_exists",
                            "file_size": file_stat.st_size,
                            "last_edited": file_stat.st_mtime
                        }), "utf-8"))
                    else: # No file found. Return an empty response
                        self.send_response(204)
                        self.end_headers()       
                else: send_error(self)
            else: send_error(self, "unauthorized", 403)
        elif url_type.path == "/logout/": # Remove the provided token from the list
            try:
                stored_tokens.remove(self.headers.get("Authentication", "Bearer ")[7:])
            except:
                pass
            self.send_response(204)
            self.end_headers()
        else: send_error(self, "endpoint_not_found")

    def do_POST(self):
        url_type = urllib.parse.urlparse(f"http://localhost{self.path}")
        if url_type.path == "/auth/": # Obtain a token for all the other endpoints
            auth_key = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8")
            if auth_key.strip() == server_settings["authentication_key"].strip():
                token = secrets.token_hex(32)
                stored_tokens.append(token)
                response_data = json.dumps({
                    "token": token,
                    "auth_type": "Bearer"
                })
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response_data)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(response_data.encode("utf-8"))
                self.close_connection = True
            else: send_error(self, "unauthorized", 403)
        else: send_error(self, "endpoint_not_found")

    def do_PUT(self):
        self.protocol_version = "HTTP/1.1"
        url_type = urllib.parse.urlparse(f"http://localhost{self.path}")
        if url_type.path == "/upload/":  # The user is uploading the new file
            query = urllib.parse.parse_qs(url_type.query)
            if self.headers.get("Authentication", "Bearer ")[7:] in stored_tokens:
                if "path" in query and "last_edit" in query and "overwrite" in query: # Three required URL parameters
                    suggested_path = f"{sys.argv[1]}{os.path.sep}{query["path"][0]}"
                    os.makedirs(os.path.dirname(suggested_path), exist_ok=True)
                    if (os.path.isfile(suggested_path) and query["overwrite"][0] != "1"): # The file exists, but the user doesn't want to overwrite it, let's return an error response
                        self.send_response(409)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Connection", "close")
                        self.end_headers()
                        response_data = json.dumps({"error": "already_exists"})
                        self.wfile.write(response_data.encode('utf-8'))
                        self.close_connection = True
                    else: # Write the file
                        print("Opening:", suggested_path)
                        with open(suggested_path, "wb", buffering=8192) as file:
                            bytes_remaining = int(self.headers.get("Content-Length", 0)) # We'll enforce the Content-Length sent by the client
                            while bytes_remaining > 0:
                                chunk_size_to_read = min(8192, bytes_remaining)
                                chunk = self.rfile.read(chunk_size_to_read)
                                if not chunk: break
                                file.write(chunk)
                                bytes_remaining -= len(chunk)
                            os.utime(suggested_path, (os.stat(suggested_path).st_atime, int(query["last_edit"][0].split(".")[0]))) # Update the last modified time to the source file's one
                            self.send_response(204)
                            self.end_headers()
                            print("Done!")
                else: send_error(self)
            else: send_error(self, "unauthorized", 403)
        else: send_error(self, "endpoint_not_found")


server = ThreadingHTTPServer((server_settings["server_address"], server_settings["port"]), ServerRequestHandler)
print(f"Starting server. {"You can access this server both from localhost and from your local IP address, connecting to port " if server_settings["server_address"] == "" else "Server address: {0}:".format(server_settings["server_address"])}{server_settings["port"]}")
server.serve_forever()
