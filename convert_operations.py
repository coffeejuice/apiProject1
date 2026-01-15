import json
import yaml
from pathlib import Path

def convert_json_to_yaml(json_path: str, yaml_path: str):
    print(f"Reading {json_path}...")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"Writing {yaml_path}...")
    with open(yaml_path, 'w', encoding='utf-8') as f:
        # Use sort_keys=False to preserve order if possible (though JSON dicts aren't strictly ordered)
        # However, these are numbered keys, so they might have a specific logical order
        yaml.dump(data, f, sort_keys=False, allow_unicode=True)
    
    print("Conversion complete.")

if __name__ == "__main__":
    json_file = "operations.json"
    yaml_file = "operations.yaml"
    
    if Path(json_file).exists():
        convert_json_to_yaml(json_file, yaml_file)
    else:
        print(f"Error: {json_file} not found.")
