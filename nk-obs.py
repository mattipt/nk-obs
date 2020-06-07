#!/usr/bin/env python3

from MidiController import Controller
from ObsConnection import ObsConnection

import yaml

def main():
    with open('config.yaml') as config_file:
        controller_config = yaml.load(config_file, Loader=yaml.SafeLoader)

    controller = Controller(controller_config['name'])
    obs = ObsConnection(verbose = True)
    controller.link(obs)
    controller.configure(controller_config)

    print("Listening to events...")
    controller.event_loop()

if __name__ == '__main__':
    main()
