import configparser
import os

class ConfigManager:
    def __init__(self, conf_file):
        self.conf_file = conf_file
        self.config = configparser.ConfigParser()
        self.load_defaults()
        if os.path.exists(self.conf_file):
            self.config.read(self.conf_file)
        else:
            self.save()

    def load_defaults(self):
        if 'General' not in self.config:
            self.config['General'] = {}
        self.config['General'].setdefault('show_shorts', 'True')
        self.config['General'].setdefault('seasonal_themes', 'True')
        self.config['General'].setdefault('multi_playlists', 'False')

    def save(self):
        os.makedirs(os.path.dirname(self.conf_file), exist_ok=True)
        with open(self.conf_file, 'w') as f:
            self.config.write(f)

    def get_bool(self, section, key):
        return self.config.getboolean(section, key)

    def set_val(self, section, key, value):
        self.config[section][key] = str(value)
        self.save()
