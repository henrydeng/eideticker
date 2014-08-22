# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import json
import marionette
import mozdevice
import moznetwork
import mozlog
import os
import posixpath
import re
import tempfile
import time

from gaia_compat import GaiaCompat
from gaiatest.gaia_test import GaiaDevice, GaiaData, GaiaApps
from b2gpopulate import B2GPopulate

# I know specifying resolution manually like this is ugly, but as far as I
# can tell there is no good, device-independant way of getting this
# information universally (we can get the resolution with SUT, but not the
# required HDMI mode)
DEVICE_PROPERTIES = {
    "android": {
        "galaxy nexus": {
            "hdmiResolution": "720p",
            "inputDevice": "/dev/input/event1",
            "defaultOrientation": "landscape",
            "dimensions": (1180, 720),
            "swipePadding": (240, 40, 100, 40)},
        "panda": {
            "hdmiResolution": "720p",
            "inputDevice": "/dev/input/event0",
            "dimensions": (1280, 672),
            "swipePadding": (240, 40, 100, 40)},
        "lg-p999": {
            "hdmiResolution": "1080p",
            "inputDevice": "/dev/input/event1",
            "dimensions": (480, 800),
            "swipePadding": (240, 40, 100, 40)},
        "mid": {
            "hdmiResolution": None,
            "inputDevice": "/dev/input/event2",
            "dimensions": (480, 800),
            "swipePadding": (240, 40, 100, 40)},
        "turkcell maxi plus 5": {
            "hdmiResolution": None,
            "inputDevice": "/dev/input/event0",
            "dimensions": (320, 480),
            "swipePadding": (40, 40, 40, 40)}
    },
    "b2g": {
        "panda": {
            "hdmiResolution": "720p",
            "inputDevice": "/dev/input/event2",
            "defaultOrientation": "landscape",
            "dimensions": (1280, 720),
            "swipePadding": (40, 40, 40, 40)},
        "unagi1": {
            "hdmiResolution": None,
            "inputDevice": "/dev/input/event0",
            "defaultOrientation": "portrait",
            "dimensions": (320, 480),
            "swipePadding": (40, 40, 40, 40)},
        "inari1": {
            "hdmiResolution": None,
            "inputDevice": "/dev/input/event0",
            "defaultOrientation": "portrait",
            "dimensions": (320, 480),
            "swipePadding": (40, 40, 40, 40)},
        "msm7627a": {
            "hdmiResolution": None,
            "inputDevice": "/dev/input/event4",
            "defaultOrientation": "portrait",
            "dimensions": (320, 480),
            "swipePadding": (40, 40, 40, 40)},
        "alcatel one touch fire": {
            "hdmiResolution": None,
            "inputDevice": "/dev/input/event4",
            "defaultOrientation": "portrait",
            "dimensions": (320, 480),
            "swipePadding": (40, 40, 40, 40)},
        "sp6821a": {
            "hdmiResolution": None,
            "inputDevice": "/dev/input/event1",
            "defaultOrientation": "portrait",
            "dimensions": (320, 480),
            "swipePadding": (40, 40, 40, 40)
        },
        "flame": {
            "hdmiResolution": None,
            "inputDevice": "/dev/input/event0",
            "defaultOrientation": "portrait",
            "dimensions": (480, 854),
            "swipePadding": (40, 40, 40, 40)
        }
    }
}

ORANGUTAN = "orangutan"
NTPCLIENT = "ntpclient"

class EidetickerMixin(object):
    """Mixin to extend DeviceManager with functionality to allow it to be
       remotely controlled and other related things"""

    @property
    def devicePixelRatio(self):
        return 1

    @property
    def hdmiResolution(self):
        return self.deviceProperties['hdmiResolution']

    @property
    def inputDevice(self):
        return self.deviceProperties['inputDevice']

    def _init(self):
        self.model = self.getprop("ro.product.model").lower()
        self.exec_locations = {}

        if not DEVICE_PROPERTIES.get(self.type) or \
                not DEVICE_PROPERTIES[self.type].get(self.model):
            raise mozdevice.DMError("Unsupported device '%s' for type '%s'" % (
                self.model, self.type))
        self.deviceProperties = DEVICE_PROPERTIES[self.type][self.model]

        for (name, execname) in [(ORANGUTAN, "orng"),
                                 (NTPCLIENT, "ntpclient")]:
            for path in ['/data/local/', '/data/local/tmp/' ]:
                fullpath = posixpath.join(path, execname)
                if self.fileExists(fullpath):
                    self.exec_locations[name] = fullpath

            if not self.exec_locations.get(name):
                raise mozdevice.DMError("%s not on device! Please "
                                        "install it according to the "
                                        "documentation" % name)

        # Hack: this gets rid of the "finished charging" modal dialog that the
        # LG G2X sometimes brings up
        if self.model == 'lg-p999':
            self.executeCommand("tap", [240, 617])

    # FIXME: make this part of devicemanager
    def _executeScript(self, events, executeCallback=None):
        '''Executes a set of monkey commands on the device'''
        command_output = None
        with tempfile.NamedTemporaryFile() as f:
            f.write("\n".join(events) + "\n")
            f.flush()
            remotefilename = os.path.join(self.getDeviceRoot(),
                                          os.path.basename(f.name))
            self.pushFile(f.name, remotefilename)
            if executeCallback:
                executeCallback()
            command_output = self.shellCheckOutput([
                self.exec_locations[ORANGUTAN], '-t',
                self.inputDevice,
                remotefilename],
                root=self._logcatNeedsRoot)
            self.removeFile(remotefilename)

        return command_output

    def getPIDs(self, appname):
        '''FIXME: Total hack, put this in devicemanagerADB instead'''
        procs = self.getProcessList()
        pids = []
        for (pid, name, user) in procs:
            if name == appname:
                pids.append(pid)
        return pids

    def synchronizeTime(self):
        self._logger.info("Synchronizing time...")
        ntpdate_wait_time = 5
        ntpdate_retries = 10
        num_retries = 0
        synced_time = False
        while not synced_time:
            try:
                self.shellCheckOutput([self.exec_locations[NTPCLIENT], "-c", "1", "-d",
                                       "-h", moznetwork.get_ip(), "-s"], root=True,
                                      timeout=ntpdate_wait_time)
                synced_time = True
            except mozdevice.DMError:
                # HACK: we need to force a reconnection here on SUT (until bug
                # 1009862 is fixed and lands in a released version of
                # mozdevice)
                self._sock = None
                if num_retries == ntpdate_retries:
                    raise Exception("Exceeded maximum number of retries "
                                    "synchronizing time!")

                # FIXME: as of this writing mozdevice doesn't distinguishing
                # between timeouts and other errors (bug 1010328), so we're
                # just gonna assume timeout
                num_retries+=1
                self._logger.info("Attempt to synchronize time failed, "
                                  "retrying (try %s/%s)..." % (num_retries,
                                                               ntpdate_retries))
        self._logger.info("Time synchronized!")

    def sendSaveProfileSignal(self, appName):
        pids = self.getPIDs(appName)
        if pids:
            self.shellCheckOutput(
                ['kill', '-s', '12', str(pids[0])], root=True)

    def fileExists(self, filepath):
        ret = self.shellCheckOutput(
            ['sh', '-c', 'ls -a %s || true' % filepath])
        return ret.strip() == filepath

    def getAPK(self, appname, localfile):
        remote_tempfile = posixpath.join(self.getDeviceRoot(),
                                         'apk-tmp-%s' % time.time())
        for remote_apk_path in ['/data/app/%s-1.apk' % appname,
                                '/data/app/%s-2.apk' % appname]:
            if self.fileExists(remote_apk_path):
                self.shellCheckOutput(['dd', 'if=%s' % remote_apk_path,
                                       'of=%s' % remote_tempfile], root=True)
                self.shellCheckOutput(['chmod', '0666', remote_tempfile],
                                      root=True)
                self.getFile(remote_tempfile, localfile)
                self.removeFile(remote_tempfile)
                return

        raise mozdevice.DMError("Unable to get APK for %s" % appname)

    def getprop(self, prop):
        return self.shellCheckOutput(["getprop", str(prop)])

    def setprop(self, prop, value):
        if not value:
            value = "\"\""
        self.shellCheckOutput(["setprop", str(prop), str(value)])

    def _transformXY(self, coords, prescaled):
        # FIXME: Only handling 90 degrees for now, everything else falls back
        # to default
        if hasattr(self, "rotation") and self.rotation == 90:
            coords = (self.dimensions[1] - int(coords[1]),
                      int(coords[0]))

        if not prescaled:
            coords = (int(float(coords[0]) * self.devicePixelRatio),
                      int(float(coords[1]) * self.devicePixelRatio))

        return coords

    def _getDragEvent(self, touchstart_x1, touchstart_y1, touchend_x1,
                      touchend_y1, duration=1000, num_steps=5, prescaled=False):
        touchstart = self._transformXY((touchstart_x1, touchstart_y1), prescaled)
        touchend = self._transformXY((touchend_x1, touchend_y1), prescaled)

        return "drag %s %s %s %s %s %s" % (
            touchstart[0], touchstart[1],
            touchend[0], touchend[1],
            num_steps, duration)

    def _getSleepEvent(self, duration=1.0):
        return "sleep %s" % int(float(duration) * 1000.0)

    def _getTapEvent(self, x, y, times=1, prescaled=False):
        coords = self._transformXY((x, y), prescaled)
        return "tap %s %s %s 100" % (coords[0], coords[1], times)

    def _getScrollEvents(self, direction, numtimes=1, numsteps=10,
                         duration=100):
        events = []
        x = int(self.dimensions[0] / 2)
        ybottom = self.dimensions[1] - self.deviceProperties['swipePadding'][2]
        ytop = self.deviceProperties['swipePadding'][0]
        (p1, p2) = ((x, ybottom), (x, ytop))
        if direction == "up":
            (p1, p2) = (p2, p1)
        for i in range(int(numtimes)):
            events.append(self._getDragEvent(
                p1[0], p1[1], p2[0], p2[1], duration, int(numsteps), prescaled=True))
        return events

    def _getSwipeEvents(self, direction, numtimes=1, numsteps=10,
                        duration=100):
        events = []
        y = (self.dimensions[1] / 2)
        (x1, x2) = (
            self.deviceProperties['swipePadding'][3],
            self.dimensions[0] - self.deviceProperties['swipePadding'][2])
        if direction == "left":
            (x1, x2) = (x2, x1)
        for i in range(int(numtimes)):
            events.append(self._getDragEvent(x1, y, x2, y, duration,
                                             int(numsteps), prescaled=True))
        return events

    def _getPinchEvent(self, touch1_x1, touch1_y1, touch1_x2, touch1_y2,
                       touch2_x1, touch2_y1, touch2_x2, touch2_y2,
                       numsteps=10, duration=1000, prescaled=False):
        cmd = "pinch "
        for coords in [ (touch1_x1, touch1_y1), (touch1_x2, touch1_y2),
                        (touch2_x1, touch2_y1), (touch2_x2, touch2_y2) ]:
            transformedCoords = self._transformXY(coords, prescaled)
            cmd += "%s %s " % transformedCoords
        cmd += "%s %s" % (numsteps, duration)

        return cmd

    def _getCmdEvents(self, cmd, args):
        if cmd == "scroll_down":
            cmdevents = self._getScrollEvents("down", *args)
        elif cmd == "scroll_up":
            cmdevents = self._getScrollEvents("up", *args)
        elif cmd == "swipe_left":
            cmdevents = self._getSwipeEvents("left", *args)
        elif cmd == "swipe_right":
            cmdevents = self._getSwipeEvents("right", *args)
        elif cmd == "drag":
            cmdevents = [self._getDragEvent(*args)]
        elif cmd == "tap":
            cmdevents = [self._getTapEvent(*args)]
        elif cmd == "double_tap":
            cmdevents = [self._getTapEvent(*args, times=2)]
        elif cmd == "pinch":
            cmdevents = [self._getPinchEvent(*args)]
        elif cmd == "sleep":
            if len(args):
                cmdevents = [self._getSleepEvent(duration=args[0])]
            else:
                cmdevents = [self._getSleepEvent()]
        else:
            raise Exception("Unknown command")

        return cmdevents

    def executeCommand(self, cmd, args, executeCallback=None):
        cmdevents = self._getCmdEvents(cmd, args)
        if cmdevents:
            self._executeScript(cmdevents, executeCallback=executeCallback)

    @staticmethod
    def _parseTimings(timings_str):
        actions = []
        current_action = None
        for line in timings_str.splitlines():
            if line:
                action = json.loads(line)
                if action['level'] == 0:
                    if action['event'] == 'START':
                        current_action = {'start': action['time'],
                                          'type': action['type'],
                                          'params': action.get('params')}
                    else:
                        assert current_action
                        current_action['end'] = action['time']
                        actions.append(current_action)
                        current_action = None

        return actions

    def executeCommands(self, cmds, executeCallback=None):
        cmdevents = []
        for cmd in cmds:
            (cmd, args) = (cmd[0], cmd[1:])
            cmdevents.extend(self._getCmdEvents(cmd, args))
        timings_str = self._executeScript(cmdevents,
                                          executeCallback=executeCallback)
        return self._parseTimings(timings_str)


class EidetickerDroidMixin(object):
    """Common functionality between adb and sut android implementations"""

    def cleanup(self):
        # clean up any test stuff (profiles, etc.)
        self.removeDir(self.getDeviceRoot())

        # cleanup any stale profiles
        files = self.listFiles('/mnt/sdcard/')
        for file in files:
            if re.match('profile_.*txt', file):
                self.removeFile('/mnt/sdcard/%s' % file)

class DroidADB(EidetickerMixin, EidetickerDroidMixin, mozdevice.DroidADB):

    def __init__(self, **kwargs):
        mozdevice.DroidADB.__init__(self, **kwargs)
        self._init()  # custom eideticker init steps

    @property
    def type(self):
        return "android"

    def killProcess(self, appname, forceKill=False):
        '''FIXME: Total hack, put this in devicemanagerADB instead'''
        procs = self.getProcessList()
        didKillProcess = False
        for (pid, name, user) in procs:
            if name == appname:
                self._runCmd(["shell", "echo kill %s | su" % pid])
                didKillProcess = True
        return didKillProcess

    @property
    def dimensions(self):
        return self.deviceProperties['dimensions']

    @property
    def rotation(self):
        if self.deviceProperties.get('defaultOrientation') == 'landscape':
            return 90
        return 0

class DroidSUT(EidetickerMixin, EidetickerDroidMixin, mozdevice.DroidSUT):

    cached_dimensions = None
    cached_rotation = None

    def __init__(self, **kwargs):
        mozdevice.DroidSUT.__init__(self, **kwargs)
        self._init()  # custom eideticker init steps

    @property
    def type(self):
        return "android"

    @property
    def dimensions(self):
        if self.cached_dimensions:
            return self.cached_dimensions

        res_string = self.getInfo('screen')['screen'][0]
        m = re.match('X:([0-9]+) Y:([0-9]+)', res_string)
        self.cached_dimensions = (int(m.group(1)), int(m.group(2)))
        return self.cached_dimensions

    @property
    def rotation(self):
        # for now we assume rotation never changes
        if self.cached_rotation is not None:
            return self.cached_rotation

        rot_string = self.getInfo('rotation')['rotation'][0]
        m = re.match('ROTATION:([0-9]+)', rot_string)
        self.cached_rotation = int(m.group(1))
        return self.cached_rotation

    def updateApp(self, appBundlePath, processName=None, destPath=None,
                  ipAddr=None, port=30000):
        '''Replacement for SUT version of updateApp'''
        '''which operates more like the ADB version'''
        '''(FIXME: TOTAL HACK ETC ETC)'''
        basename = os.path.basename(appBundlePath)
        pathOnDevice = os.path.join(self.getDeviceRoot(), basename)
        self.pushFile(appBundlePath, pathOnDevice)
        self.installApp(pathOnDevice)
        self.removeFile(pathOnDevice)


class EidetickerB2GMixin(EidetickerMixin):
    """B2G-specific extensions to the eideticker mixin"""

    marionette = None
    _devicePixelRatio = None

    def setupMarionette(self):
        self.marionette = marionette.Marionette()
        self._logger.info("Waiting for Marionette...")
        self.marionette.wait_for_port()
        self._logger.info("Marionette ready, starting session")
        self.marionette.start_session()
        if 'b2g' not in self.marionette.session:
            raise mozdevice.DMError(
                "bad session value %s returned by start_session" %
                self.marionette.session)
        self.marionette.set_script_timeout(60000)
        self.marionette.timeouts(self.marionette.TIMEOUT_SEARCH, 10000)
        self._logger.info("Marionette ready!")

        self.b2gpopulate = B2GPopulate(self.marionette)
        self.gaiaApps = GaiaApps(self.marionette)
        self.gaiaData = GaiaData(self.marionette)
        self.gaiaDevice = GaiaDevice(self.marionette)
        self.gaiaCompat = GaiaCompat()

    def connectWIFI(self, wifiSettings):
        """
        Tries to connect to the wifi network
        """
        self._logger.info("Setting up wifi...")
        self.gaiaData.connect_to_wifi(wifiSettings)
        self._logger.info("WIFI ready!")

    def cleanup(self):
        self.removeDir('/data/local/storage/persistent')
        self.removeDir('/data/b2g/mozilla')
        for item in self.listFiles('/sdcard/'):
            self.removeDir('/'.join(['/sdcard', item]))

    def stopB2G(self):
        self._logger.info("Stopping B2G")

        if self.marionette and self.marionette.session:
            self.marionette.delete_session()
            self.marionette = None

        self.shellCheckOutput(['stop', 'b2g'])
        # Wait for a bit to make sure B2G has completely shut down.
        tries = 100
        while "b2g" in self.shellCheckOutput(['ps', 'b2g']) and tries > 0:
            tries -= 1
            time.sleep(0.1)
        if tries == 0:
            raise mozdevice.DMError("Could not kill b2g process")

    def startB2G(self):
        self._logger.info("Starting B2G")
        self.shellCheckOutput(['start', 'b2g'])
        self.setupMarionette()
        self.gaiaCompat.wait_for_b2g(self.marionette)

        # run the fake update checker
        self.gaiaCompat.supress_update_check(self.marionette)

        # unlock device, so it doesn't go to sleep
        self._logger.info("Unlocking screen...")
        self.gaiaDevice.unlock()

        # turn off automatic brightness adjustments and set to 100%
        self.gaiaData.set_setting('screen.automatic-brightness', '')
        self.gaiaData.set_setting('screen.brightness', 1)

        # kill running apps so they don't interfere with the test
        self._logger.info("Killing all running apps...")
        self.gaiaApps.kill_all()

        # set correct orientation
        self._logger.info("Setting orientation")
        self.marionette.execute_script("screen.mozLockOrientation('%s');" %
                                       self.deviceProperties['defaultOrientation'])

    def restartB2G(self):
        """
        Restarts the b2g process on the device.
        """
        self.stopB2G()
        self.startB2G()

    @property
    def devicePixelRatio(self):
        if not self._devicePixelRatio:
            if self.marionette and self.marionette.session:
                self._devicePixelRatio = self.marionette.execute_script(
                    'return window.wrappedJSObject.devicePixelRatio;')
        return self._devicePixelRatio or 1


class B2GADB(EidetickerB2GMixin, mozdevice.DeviceManagerADB):

    def __init__(self, **kwargs):
        mozdevice.DeviceManagerADB.__init__(self, **kwargs)
        self._init()  # custom eideticker init steps

    @property
    def type(self):
        return "b2g"

    @property
    def dimensions(self):
        return self.deviceProperties['dimensions']

    def rotation(self):
        return 90  # Assume portrait orientation for now


def getDevicePrefs(options):
    '''Gets a dictionary of eideticker device parameters'''
    optionDict = {}
    optionDict['dmtype'] = options.dmtype
    optionDict['devicetype'] = options.devicetype
    if options.debug:
        optionDict['logLevel'] = mozlog.DEBUG
    else:
        optionDict['logLevel'] = mozlog.INFO

    host = options.host
    if not host and optionDict['dmtype'] == "sut":
        host = os.environ.get('TEST_DEVICE')

    optionDict['host'] = host
    optionDict['port'] = options.port

    return optionDict


def getDevice(dmtype="adb", devicetype="android", host=None, port=None,
              logLevel=mozlog.INFO):
    '''Gets an eideticker device according to parameters'''

    if dmtype == "adb":
        if host and not port:
            port = 5555
        if devicetype == 'b2g':
            # HACK: Assume adb-over-usb for now, with marionette forwarded
            # to localhost via "adb forward tcp:2828 tcp:2828"
            return B2GADB(logLevel=logLevel)
        else:
            return DroidADB(packageName=None, host=host, port=port,
                            logLevel=logLevel)
    elif dmtype == "sut":
        if not host:
            raise Exception("Must specify host with SUT!")
        if not port:
            port = 20701
        if devicetype == 'b2g':
            return B2GSUT(host=host, port=port, logLevel=logLevel)
        else:
            return DroidSUT(host=host, port=port, logLevel=logLevel)
    else:
        raise Exception("Unknown device manager type: %s" % type)
