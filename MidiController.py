import mido
import sys
import time
from collections import OrderedDict


class Controller:
    def __init__(self, name='', channel=0):
        """
        Initialise a connection to a MIDI device.

        Makes a connection to the first MIDI device matching the substring.
        Args:
            name (str): Substring of the device name, to match.
            channel (int): MIDI channel this controller uses. 

        Note that this requires all controls on this device to use the same channel.
        """
        devices = [i for i in mido.get_ioport_names() if name in i]
        if len(devices) == 0:
            sys.exit('No controller devices found!')
        if len(devices) > 1:
            sys.stderr.write(
                'Warning: multiple possible controller devices found: {}. Selecting first one.\n'.format(devices))
        device = devices[0]
        self.midi_port = mido.open_ioport(device, autoreset=True)
        self.channel = channel
        self.controls = dict()
        self.leds = dict()
        self.event_queue = OrderedDict()

    def link(self, obs_connection):
        self.obs_connection = obs_connection
        self.obs_connection.link(self)

    def add_fader(self, fader):
        control = self.controls[fader['control']] = {'type': 'fader',
                                                     'min_value': fader.get('min_value', 0),
                                                     'max_value': fader.get('max_value', 127)}
        if 'action' in fader.keys():
            if fader['action'] == 'volume':
                control['action'] = self.obs_connection.set_volume
                control['target'] = self.sources[fader['source']]

    # Buttons are momentary and send an 'on' value when pressed and 'off' value when released
    def add_button(self, button):
        control = self.controls[button['control']] = {'type': 'button',
                                                      'min_value': button.get('off_value', 0),
                                                      'max_value': button.get('on_value', 127)}

        if 'action' in button.keys():
            action_map = {
                'prev_scene': self.obs_connection.prev_scene,
                'next_scene': self.obs_connection.next_scene,
                'transition': self.obs_connection.transition,
                'stream': self.obs_connection.set_stream,
                'record': self.obs_connection.set_record,
                'monitor': self.obs_connection.set_monitor
            }
            if button['action'] in action_map.keys():
                control['action'] = action_map[button['action']]
            if 'source' in button.keys():
                control['target'] = self.sources[button['source']]

        if 'led' in button.keys():
            self.leds[button['led']] = button['control']

    # Toggles are buttons with an internal on/off state. They send the on value and off value alternately
    def add_toggle(self, toggle):
        control = self.controls[toggle['control']] = {'type': 'toggle',
                                                      'min_value': toggle.get('off_value', 0),
                                                      'max_value': toggle.get('on_value', 127)}
        if 'action' in toggle.keys():
            action_map = {
                'stream': self.obs_connection.set_stream,
                'record': self.obs_connection.set_record,
                'monitor': self.obs_connection.set_monitor
            }
            if toggle['action'] in action_map.keys():
                control['action'] = action_map[toggle['action']]
            if 'source' in toggle.keys():
                control['target'] = self.sources[toggle['source']]

        if 'led' in toggle.keys():
            self.leds[toggle['led']] = toggle['control']

    def configure(self, controller_config):
        # print(controller_config)
        self.sources = controller_config['sources']
        print('Channel assignment:')
        for num, name in self.sources.items():
            print(' - {}: {}'.format(num, name))
        for fader in controller_config['faders']:
            self.add_fader(fader)
        for button in controller_config['buttons']:
            self.add_button(button)
        for toggle in controller_config['toggles']:
            self.add_toggle(toggle)

        self.obs_connection.query_state()

    def process_message(self, msg):
        #print('Received message {}'.format(msg))
        # Ignore message if the control has not been added:
        if msg.control not in self.controls.keys():
            return

        # Buttons store the highest value and ignore release event; faders and toggles store the latest value
        if self.controls[msg.control]['type'] == 'button':
            if msg.value != self.controls[msg.control]['min_value']:
                self.event_queue[msg.control] = max(
                    self.event_queue.get(msg.control, 0), msg.value)
        else:
            self.event_queue[msg.control] = msg.value

    def set_state(self, control, state):
        value = 127 if state == True else 0
        msg = mido.Message(
            'control_change', channel=self.channel, control=self.leds[control], value=value)
        self.midi_port.send(msg)

    def process_events(self):
        # Wait until a message arrives
        self.process_message(self.midi_port.receive())
        # Process all remaining messages
        for msg in self.midi_port.iter_pending():
            self.process_message(msg)

    def dispatch_commands(self):
        for control, value in self.event_queue.items():
            #print('{} => {}'.format(control, value))
            ctl = self.controls[control]
            if 'action' in ctl.keys():
                if ctl['type'] == 'fader':
                    scaled_value = float(
                        value - ctl['min_value']) / (ctl['max_value'] - ctl['min_value'])
                    ctl['action'](ctl['target'], scaled_value)
                elif ctl['type'] == 'toggle':
                    ctl_value = True if value == ctl['max_value'] else False
                    if 'target' in ctl.keys():
                        ctl['action'](ctl['target'], ctl_value)
                    else:
                        ctl['action'](ctl_value)
                else:  # Button
                    if 'target' in ctl.keys():
                        ctl['action'](ctl['target'])
                    ctl['action']()

        self.event_queue.clear()

    def event_loop(self):
        try:
            while True:
                self.process_events()
                self.dispatch_commands()
        except KeyboardInterrupt:
            pass

    def __del__(self):
        self.midi_port.close()
