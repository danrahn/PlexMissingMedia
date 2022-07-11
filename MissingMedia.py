import argparse
import json
import os
import requests
import sys
from urllib import parse
import yaml


class PlexMissingMedia:
    def __init__(self):
        self.get_config()
    
    def get_config(self):
        """Reads the config file from disk"""

        self.valid = False
        config_file = self.adjacent_file('config.yml')
        config = None
        if not os.path.exists(config_file):
            print('WARN: Could not find config.yml! Make sure it\'s in the same directory as this script')
        else:
            with open(config_file) as f:
                config = yaml.load(f, Loader=yaml.SafeLoader)
        
        if not config:
            config = {}

        parser = argparse.ArgumentParser()
        parser.add_argument('--host', help='Your Plex host. Defaults to http://localhost:32400')
        parser.add_argument('-t', '--token', help='Your Plex authentication token')
        parser.add_argument('-s', '--section', help='The id of the library to parse')
        parser.add_argument('-e', '--find_extras', action='store_true', help='Match extras in addition to regular library items. WARNING: Takes significantly more time to parse.')
        self.cmd_args = parser.parse_args()
        self.token = self.get_config_value(config, 'token', prompt='Enter your Plex token')
        self.host = self.get_config_value(config, 'host', 'http://localhost:32400')
        self.section_id = self.get_config_value(config, 'section', default=None)
        if type(self.section_id) != int and self.section_id.isnumeric():
            self.section_id = int(self.section_id)
        self.find_extras = self.get_config_value(config, 'find_extras', False, prompt='Find extras (Note: This is _significantly_ slower)')
        self.valid = True


    def get_config_value(self, config, key, default='', prompt=''):
        cmd_arg = None
        if key in self.cmd_args:
            cmd_arg = self.cmd_args.__dict__[key]

        if key in config and config[key] != None:
            if cmd_arg != None:
                # Command-line args shadow config file
                print(f'WARN: Duplicate argument "{key}" found in both command-line arguments and config file. Using command-line value ("{self.cmd_args.__dict__[key]}")')
                return cmd_arg
            return config[key]

        if cmd_arg != None:
            return cmd_arg

        if default == None:
            return ''

        if len(default) != 0:
            return default

        if len(prompt) == 0:
            return input(f'\nCould not find "{key}" and no default is available.\n\nPlease enter a value for "{key}": ')
        return input(f'\n{prompt}: ')


    def run(self):
        """Kick off the processing"""

        if not self.valid:
            return

        print()
        if not self.test_plex_connection():
            return

        section = self.get_section()
        if not section:
            print('Unable to find the right library section, exiting...')
            return

        # Whitelist from https://en.wikipedia.org/wiki/Video_file_format and https://en.wikipedia.org/wiki/Audio_file_format
        video_whitelist = ('.webm', '.mkv', '.flv', '.flv', '.vob', '.ogv', '.ogg', '.drc', '.gif', '.gifv', '.mng', '.avi', '.mts', '.m2ts', '.ts', '.mov', '.qt', '.wmv', '.yuv', '.rm', '.rmvb', '.viv', '.asf', '.amv', '.mp4', '.m4p', '.m4v', '.mpg', '.mp2', '.mpeg', '.mpe', '.mpv', '.mpg', '.mpeg', '.m2v', '.m4v', '.svi', '.3gp', '.3g2', '.mxf', '.roq', '.nsv', '.flv', '.f4v', '.f4p', '.f4a', '.f4b')
        audio_whitelist = ('.3gp', '.aa', '.aac', '.aax', '.act', '.aiff', '.alac', '.amr', '.ape', '.au', '.awb', '.dss', '.dvf', '.flac', '.gsm', '.iklax', '.ivs', '.m4a', '.m4b', '.m4p', '.mmf', '.mp3', '.mpc', '.msv', '.nmf', '.ogg', '.oga', '.mogg', '.opus', '.ra', '.rm', '.raw', '.rf64', '.sln', '.tta', '.voc', '.vox', '.wav', '.wma', '.wv', '.webm', '.8svx', '.cda')

        on_disk = set()
        whitelist = audio_whitelist if section['type'] == 'artist' else video_whitelist
        paths = section['Location']
        file_count = 0
        for location in paths:
            plex_path = location['path']
            print(f'Reading "{plex_path}"')
            for root, _, files in os.walk(plex_path):
                for file in files:
                    file_count += 1
                    if (file_count % 1000 == 0):
                        print(f'Processed {file_count} files')
                    if os.path.splitext(file)[1].lower() in whitelist:
                        on_disk.add(os.path.join(root, file).lower())

        print(f'Found {len(on_disk)} files for library section {section["key"]}\'s root path(s).')

        # 1 == movies, 4 == episodes, 10 == track
        media_type = 1
        if section['type'] == 'artist':
            media_type = 10
        elif section['type'] == 'show':
            media_type = 4

        plex_items = self.get_json_response(f'/library/sections/{section["key"]}/all', { 'type' : media_type })
        
        if 'Metadata' not in plex_items:
            print('Unable to parse library items, oops.')
            return
        
        in_library = set()
        extras_count = 0
        print(f'Reading {len(plex_items["Metadata"])} library items')
        for media_item in plex_items['Metadata']:
            for version in media_item['Media']:
                for part in version['Part']:
                    in_library.add(part['file'].lower())
            if self.find_extras:
                extras_resp = self.get_json_response(f'/library/metadata/{media_item["ratingKey"]}', { 'includeExtras' : 1 })
                extras_count += 1
                if (extras_count % 100 == 0):
                    print(f'Processed {extras_count} items')
                
                for extra_item in extras_resp['Metadata']:
                    if 'Extras' not in extra_item or 'Metadata' not in extra_item['Extras']:
                        continue
                    for extra in extra_item['Extras']['Metadata']:
                        if not extra['guid'].startswith('file://'):
                            continue
                        for extra_media in extra['Media']:
                            for extra_part in extra_media['Part']:
                                in_library.add(extra_part['file'].lower())

        print(f'Found {len(in_library)} items in library')

        intersection = on_disk - in_library

        print(f'Found {len(intersection)} items not in Plex library:')
        for missing in sorted(intersection):
            print(f'\t{missing}')

        intersection = in_library - on_disk
        if (len(intersection) > 0):
            print(f'Found {len(intersection)} items in library but not on disk:')
            for missing in sorted(intersection):
                print(f'\t{missing}')


    def test_plex_connection(self):
        """
        Does some basic validation to ensure we get a valid response from Plex with the given
        host and token.
        """

        status = None
        try:
            status = requests.get(self.url('/')).status_code
        except requests.exceptions.ConnectionError:
            print(f'Unable to connect to {self.host} ({sys.exc_info()[0].__name__}), exiting...')
            return False
        except:
            print(f'Something went wrong when connecting to Plex ({sys.exc_info()[0].__name__}), exiting...')
            return False

        if status == 200:
            return True

        if status == 401 or status == 403:
            print('Could not connect to Plex with the provided token, exiting...')
        else:
            print(f'Bad response from Plex ({status}), exiting...')
        return False


    def get_section(self):
        """Returns the section object that the collection will be added to"""
        sections = self.get_json_response('/library/sections')
        if not sections or 'Directory' not in sections:
            return None

        valid_types = { 'movie', 'artist', 'show' }
        sections = sections['Directory']
        find = self.section_id
        if type(find) == int:
            for section in sections:
                if int(section['key']) == int(find):
                    if section['type'] not in valid_types:
                        print(f'Found section {find}, but it\'s not a Movie, TV, or Music library')
                    else:
                        print(f'Found section {find}: "{section["title"]}"')
                        return section

            print(f'Provided library section {find} could not be found...\n')

        print('\nChoose a library to search.\n\nAvailable Libraries:\n')
        choices = {}
        sections.sort(key=lambda x: int(x['key']))
        for section in sections:
            if section['type'] not in valid_types:
                continue
            print(f'[{section["key"]}] {section["title"]}')
            choices[int(section['key'])] = section
        print()

        choice = input('Enter the library number (-1 to cancel): ')
        while not choice.isnumeric() or int(choice) not in choices:
            if choice == '-1':
                return None
            choice = input('Invalid section, please try again (-1 to cancel): ')

        self.section_id = int(choice)
        print(f'\nSelected "{choices[int(choice)]["title"]}"\n')
        return choices[int(choice)]


    def get_json_response(self, url, params={}):
        """Returns the JSON response from the given URL"""
        response = requests.get(self.url(url, params), headers={ 'Accept' : 'application/json' })
        if response.status_code != 200:
            data = None
        else:
            try:
                data = json.loads(response.content)['MediaContainer']
            except:
                print('ERROR: Unexpected JSON response:\n')
                print(response.content)
                print()
                data = None

        response.close()
        return data


    def url(self, base, params={}):
        """Builds and returns a url given a base and optional parameters. Parameter values are URL encoded"""

        real_url = f'{self.host}{base}?{parse.urlencode(params, doseq=True)}'
        return f'{real_url}{"&" if len(params.keys()) > 0 else ""}X-Plex-Token={self.token}'


    def adjacent_file(self, filename):
        """Returns the file path for a file that is in the same directory as this script"""

        return os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__))) + os.sep + filename


if __name__ == '__main__':
    runner = PlexMissingMedia()
    runner.run()
