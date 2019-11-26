import argparse
from old import api2

# args
parser = argparse.ArgumentParser(description='mray_gesture_control')
parser.add_argument('config_file', type=str, help='config_file')
args = parser.parse_args()

config = api2.ProjectConfig()
config.from_json_file(args.config_file)
api2.setup_logging(config.log_level, config.log_file)
func_ = api2.get_function("shell", config.action)
func_(config)
