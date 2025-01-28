import json


class Theme:
    _instance = None

    def __new__(cls, file_name="themes/alteryx.json"):
        if cls._instance is None:
            cls._instance = super(Theme, cls).__new__(cls)
            cls._instance.theme_data = cls.read_file(file_name)
        return cls._instance

    def brush_color(self, node_type):
        return self.theme_data[node_type]['_brush_color']

    def read_file(file_name):
        print("%%%%%%%%%%%%%%%%%%%%%%%%")
        print("Reading Theme file!")
        print("%%%%%%%%%%%%%%%%%%%%%%%%")
        with open(file_name, 'r') as f:
            theme_data = json.load(f)
            return theme_data

        return {}
