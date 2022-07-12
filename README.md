# Plex Missing Media

Simple script that compares content on disk versus what's in a Plex library, printing out the differences.

## Requirements

[Python 3](https://www.python.org/downloads/). Additional dependencies can be installed with the `requirements.txt` file in this repository: `pip install -r requirements.txt`.

## Usage

`python MissingMedia.py [args]`

### Arguments

There are three ways to specify arguments:

1. As command line arguments, outlined in the table below.
2. From config.yml, outlined in the table below.
3. Interactively when running the script.

If the arguments are not found in the command line, it will look in config.yml. If it's still not found, a default value will be used. If there's no valid default, the script will ask you to provide values.

Value | Command line | config.yaml | Default | Description
---|---|---|---|---
use_db | `--use_database` | `use_database` | Whether to read from the database directly instead of making web API calls. This will be faster, but it's recommended to shut down PMS before you do any external access on your database.
db_path | `d`, `--db_path` | `db_path` | The full path to the Plex database. Only needed if `use_db` is True
host | `--host` | `host` | `http://localhost:32400` | The host of the Plex server. Only needed if `use_db` if False.
token | `-t`, `--token` | `token` | None | Your Plex token (see [finding an authentication token](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/)). Only needed if `use_db` is False.
section | `-s`, `--section` | `section` | None | The id of the library section to parse. If none is provided, the script will print available values.
find_extras | `-e`, `--find_extras` | `find_extras` | `False` | If enabled, searches for extras (trailers/behind the scenes/featurettes/etc) in addition to main library items. Note that this _significantly_ increases the script's execution time, as it makes an additional synchronous web request for every item in the library. Only needed if `use_db` is False. If `use_db` is true, all extras are found regardless of this setting.

#### Examples

Specify a custom host and search for extras:

    python MissingMedia.py --host https://plex.mydomain.com --token 0123456789abcdef -s 2 --find_extras

Use the default host, don't look for extras, and have the script print out available libraries to parse:

    python MissingMedia.py --token 0123456789abcdef

## Known issues

* `.plexignore` files are not parsed, leading to intentionally ignored files appearing in the "not found" list.
* Show and season-level TV extras won't be captured when using the web API, even with `find_extras` enabled.
* This was whipped up in about an hour. Its output is ugly, and it's bound to be missing some edge cases.