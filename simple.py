import datetime
import ok
import pyglet
import wx

def print_msg(msg):
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print "{}: {}".format(timestamp, msg)

def check_bit(val, offset):
    mask = 1 << offset
    return (val & mask)

class SimpleBehaviorController(wx.Frame):
    '''
    Demonstration of a go/no-go trial
    '''

    def __init__(self, parent, title):
        wx.Frame.__init__(self, parent, title=title, size=(200, 60),
                          style=wx.DEFAULT_FRAME_STYLE ^ wx.RESIZE_BORDER)

        # Initialize FPGA
        self.xem = ok.FrontPanel()
        serial = self.xem.GetDeviceListSerial(0)
        self.xem.OpenBySerial(serial)
        self.xem.LoadDefaultPLLConfiguration()
        self.xem.ConfigureFPGA('first.bit')

        # Load the sounds
        self.go_sound = pyglet.resource.media('go.wav', streaming=False)
        self.nogo_sound = pyglet.resource.media('no-go.wav', streaming=False)

        # Set up the GUI
        box = wx.BoxSizer(wx.HORIZONTAL)
        self.trial_type_cb = wx.ComboBox(self, size=(60,-1), style=wx.CB_READONLY,
                                    choices=['go', 'no-go'], value='go')
        self.run_btn = wx.Button(self, label='Run trial')
        self.run_btn.Bind(wx.EVT_BUTTON, self._start_trial)
        box.Add(self.trial_type_cb, 1, wx.ALL | wx.EXPAND, 0)
        box.Add(self.run_btn, 1, wx.ALL | wx.EXPAND, 0)
        self.SetSizer(box)

        # Set up for polling of the FPGA
        self.poll_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._trial_polling, self.poll_timer)

        self.Show(True)

    def _start_trial(self, e):
        self.run_btn.Disable()

        trial_type = self.trial_type_cb.GetValue()
        print_msg('Starting {} trial...'.format(trial_type.upper()))
        
        # Play tone (non-blocking)
        print_msg('Playing sound...')
        if (trial_type == 'go'):
            self.go_sound.play()
        else:
            self.nogo_sound.play()

        # Begin polling the FPGA and trigger the "timed_response" module
        self.poll_timer.Start(250) # Approximate delay in ms
        self.xem.ActivateTriggerIn(0x40, 0) # Bit0: Start

    def _trial_polling(self, e):
        print_msg('Polling FPGA...')
        self.xem.UpdateWireOuts()
        trial_status = self.xem.GetWireOutValue(0x20)

        if (check_bit(trial_status, 1)): # Bit 1 indicates that "timed_response" is done
            self.poll_timer.Stop() # Can stop the polling now
            self._finish_trial()

    def _finish_trial(self):
        trial_type = self.trial_type_cb.GetValue()
        trial_status = self.xem.GetWireOutValue(0x20)
        if (check_bit(trial_status, 0)): # There was a response (e.g. lick)
            if (trial_type == 'go'):
                self.xem.SetWireInValue(0x00, 1<<0)
                self.xem.UpdateWireIns()
                wx.MessageBox('Correct response on a GO trial. Reward (LED8) is activated.', 'Hit', wx.OK)
            else:
                self.xem.SetWireInValue(0x00, 1<<1)
                self.xem.UpdateWireIns()
                wx.MessageBox('Incorrect response on a NO-GO trial. Punishment (LED7) is activated.', 'False start', wx.OK | wx.ICON_ERROR)
        else: # No response
            if (trial_type == 'go'):
                self.xem.SetWireInValue(0x00, 1<<1)
                self.xem.UpdateWireIns()
                wx.MessageBox('Incorrect response on a GO trial. Punishment (LED7) is activated', 'Miss', wx.OK | wx.ICON_ERROR)
            else:
                wx.MessageBox('Correct response on a NO-GO trial', 'Correct rejection', wx.OK)
        # Clear the reward bits
        self.xem.SetWireInValue(0x00, 0)
        self.xem.UpdateWireIns()

        # Reset the "timed_response" module in the FPGA
        self.xem.ActivateTriggerIn(0x40, 1)

        # Let the user run more trials...
        print_msg('Finished trial...')
        self.run_btn.Enable()

if (__name__ == '__main__'):
    app = wx.App(False);
    sbc = SimpleBehaviorController(None, 'Simple Behavior Controller')
    app.MainLoop()
