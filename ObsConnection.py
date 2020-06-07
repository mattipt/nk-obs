from obswebsocket import obsws, requests, events

class ObsConnection:
    def __init__(self, host = 'localhost', port = 4444, password='', verbose = False):
        self.connection = obsws(host, port, password)
        self.connection.register(self.on_event)
        self.connection.connect()
        if verbose:
            sources = self.connection.call(requests.GetSourcesList()).getSources()
            print('Sources detected:')
            for source in sources:
                print(' - {}'.format(source['name']))

    def __del__(self):
        self.connection.disconnect()

    def link(self, controller):
        self.controller = controller

    def query_state(self):
        self.controller.set_state('stream', self.connection.call(requests.GetStreamingStatus()).getStreaming())
        self.controller.set_state('record', self.connection.call(requests.GetStreamingStatus()).getRecording())

    def on_event(self, event):
        # print('Received message {}'.format(event))
        actionable_events = {
            events.StreamStarted: ('stream', True),
            events.StreamStopped: ('stream', False),
            events.RecordingStarted: ('record', True),
            events.RecordingStopped: ('record', False)
        }
        for e, action in actionable_events.items():
            if isinstance(event, e):
                self.controller.set_state(*action)
                        
    def set_volume(self, name, val):
        self.connection.call(requests.SetVolume(name, val))

    def set_sync_offset(self, name, val):
        """
        Set the sync offset for a track.
        """
        # Select desired adjustment range in nanoseconds.
        # Range is [-sync_offset_range, sync_offset_range]
        sync_offset_range = 1000 * 1e6
        # The input value is between 0 and 1; scale appropriately
        offset_value = int((val - 0.5) * 2 * sync_offset_range)
        # print('set_sync_offset {} => {}'.format(name, offset_value))
        self.connection.call(requests.SetSyncOffset(name, offset_value))
        
    def set_stream(self, val = None):
        if val is None:
            val = not self.connection.call(requests.GetStreamingStatus()).getStreaming()

        if val == True:
            self.connection.call(requests.StartStreaming())
        else:
            self.connection.call(requests.StopStreaming())

    def set_record(self, val = None):
        if val is None:
            val = not self.connection.call(requests.GetStreamingStatus()).getRecording()

        if val == True:
            self.connection.call(requests.StartRecording())
        else:
            self.connection.call(requests.StopRecording())

    def change_scene(self, amount):
        """
        Jump to the next / previous scene.

        The web socket will only give us the current scene name and an orderd list of scenes;
        we therefore need to work out the index of the current scene and then the name of the
        desired scene to jump to.
        """
        if self.connection.call(requests.GetStudioModeStatus()).getStudioMode() == False:
            print('Studio mode must be on for scene switching')
            return

        scenes = self.connection.call(requests.GetSceneList()).getScenes()
        current_scene = self.connection.call(requests.GetPreviewScene()).getName()
        current_scene_index = [i for i, s in enumerate(scenes) if s['name'] == current_scene][0]
        new_scene_index = (current_scene_index + amount) % len(scenes)
        new_scene = scenes[new_scene_index]['name']
        self.connection.call(requests.SetPreviewScene(new_scene))

    def next_scene(self):
        self.change_scene(1)

    def prev_scene(self):
        self.change_scene(-1)

    def transition(self):
        current_transition = self.connection.call(requests.GetTransitionList()).getCurrentTransition()
        self.connection.call(requests.TransitionToProgram(with_transition_name = current_transition))

    def set_monitor(self, name, val):
        print('SetAudioMonitorType not yet supported')
        return
        # Toggle between 'monitor off' and 'monitor and output'
        monitor_type = 'monitorAndOutput' if val > 0 else 'none'
        print('Set monitor {} to {}'.format(name, monitor_type))
        #self.connection.call(requests.SetVolume(name, val))
        self.connection.call(requests.SetAudioMonitorType(name, monitor_type))
        