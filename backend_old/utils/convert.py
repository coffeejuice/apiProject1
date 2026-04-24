import yaml
import json

# Read the YAML file
with open('../config.yml', 'r') as yml_file:
    yml_data = yaml.safe_load(yml_file)

# Convert and write to a JSON file
with open('../configs/config.json', 'w') as json_file:
    json.dump(yml_data, json_file, indent=4)

print("Conversion completed: config.yml -> config.json")
