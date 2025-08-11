# wireless-file-copy

A really simple Python script that permits to copy a file from a device to another one. No external dependencies required.

## Server script

First, you need to start the [server script](./server.py). You'll need to pass the folder where the files should be saved (note that the script will automatically create subdirectories if necessary). So, the script will be something like this:

```
python3 script.py *Path where the files will be saved* *...options*
```

After you've started the server, you don't need to do anything else. The server will continue to work until it's manually closed. You can either close the terminal window, or you can press `CTRL` + `C` to force exit the process.

### Server options

You can specify at the end some custom, optional options for the server. You can also set up an `.env` file, called `wireless-file-copy.env` that'll be automatically read by the application. Commands passed by the console will override the preferences in the env file.

| Argument (command-line) | Argument (.env file) | Description | Followed by |
| -- | -- | -- | -- |
| `--authentication-key` | `WIRELESS_FILE_COPY_KEY` | A custom value that must be passed from the client to connect to the server. If the value is not the same, the server will decline the connection. | A string of that value |
| `--port` | `WIRELESS_FILE_COPY_PORT` | The port where the server should be opened. | a valid port number |
| `--address` | `WIRELESS_FILE_COPY_ADDRESS` | The address of the server | a string |


## Client script

The client script is the script that fetches the files from your device and uploads them to the server script. Even here, you just need to run a command, that follows this order:

```
python3 client.py *Path where the files should be fetched* *The URL of the server* *...options*
```

A few notes:
- The script will automatically copy the subfolders of that folder, and it'll keep the folder structure
- The script will keep the "Last modified" date of the source file
- The script will ask you if you want to overwrite the files or not. This behavior can be changed by pasing extra arguments (I'll explain this in a bit)
- The server URL can be both localhost, a local URL or a "public" URL. However, it must be a valid URL, so please use the full syntax (ex: `http://localhost:15000`)


### Other arguments

You can customize the behavior of the client script by passing these extra arguments. Just like in the server script, if a `wireless-file-copy.env` file is added, the script will fetch the preferences from there (but you can still override them by passing the following arguments).

| Argument (command-line) | Argument (.env file) | Description | Followed by |
| -- | -- | -- | -- |
| `--authentication-key` | `WIRELESS_FILE_COPY_KEY` | A custom value that must be passed from the client to connect to the server. If the value is not the same, the server will decline the connection. | A string of that value |
| `--allowed-extensions` | `WIRELESS_FILE_COPY_ALLOWED_EXTENSIONS` | The script will only upload files that end with these extensions | A comma-separated list of extensions |
| `--overwrite` | `WIRELESS_FILE_COPY_OVERWRITE_SETTINGS` | Customize the behavior of the script when a file with the same name is found | * `0`: default value: the script will ask you what to do if a duplicate file is found<br>* `1`: the script will always skip overwriting files<br>* `2`: the script will always overwrite files<br>* `3`: the script will overwrite files if they have a different file size or a different last modified date |
