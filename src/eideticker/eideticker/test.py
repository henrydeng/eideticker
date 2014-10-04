# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import eideticker
import imp
import json
import manifestparser
import mozhttpd
import mozlog
import moznetwork
import os
import re
import time
import urllib
import urlparse

from gaiatest.gaia_test import GaiaApps

from marionette.by import By
from marionette.wait import Wait

SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
TEST_DIR = os.path.abspath(os.path.join(SRC_DIR, "tests"))
EIDETICKER_TEMP_DIR = "/tmp/eideticker"

class TestException(Exception):

    def __init__(self, msg, can_retry=False):
        Exception.__init__(self, msg)
        # can_retry means a failure that is possibly intermittent
        self.can_retry = can_retry


class TestLog(object):
    # initialize possible parameters to None
    actions = None
    http_request_log = None
    checkerboard_percent_totals = None

    def getdict(self, log_http_requests=True, log_actions=True):
        logdict = {}
        if log_http_requests and self.http_request_log:
            logdict['httpLog'] = self.http_request_log
        if log_actions and self.actions:
            logdict['actionLog'] = self.actions
        if self.checkerboard_percent_totals:
            logdict['checkerboardPercentTotals'] = self.checkerboard_percent_totals

        return logdict

class CaptureServer(object):

    start_capture_called = False
    end_capture_called = False
    input_called = False
    logger = mozlog.getLogger('CaptureServer')

    def __init__(self, test):
        self.test = test

    @mozhttpd.handlers.json_response
    def start_capture(self, request):
        self.logger.info("Received start capture callback from test")
        assert not self.start_capture_called
        self.start_capture_called = True
        self.test.start_capture()

        return (200, {'capturing': True})

    @mozhttpd.handlers.json_response
    def end_capture(self, request):
        self.logger.info("Received end capture callback from test")
        assert not self.end_capture_called
        self.end_capture_called = True
        self.test.end_capture()

        return (200, {'capturing': False})

    @mozhttpd.handlers.json_response
    def input(self, request):
        commandset = urlparse.parse_qs(request.body)['commands'][0]
        self.logger.info("Received input callback from test")
        assert not self.input_called
        self.input_called = True
        self.test.input_actions(commandset)

        return (200, {})


def get_test_manifest():
    return manifestparser.TestManifest(manifests=[os.path.join(
        TEST_DIR, 'manifest.ini')])


def get_testinfo(testkey):
    manifest = get_test_manifest()

    # sanity check... does the test match a known test key?
    testkeys = [test["key"] for test in manifest.active_tests()]
    if testkey not in testkeys:
        raise TestException("No tests matching '%s' (options: %s)" % (
            testkey, ", ".join(testkeys)))

    return [test for test in manifest.active_tests() if test['key'] == testkey][0]


def get_test(testinfo, options, device, capture_controller=None, profile_filename=None):
    testpath = testinfo['path']
    testtype = testinfo['type']

    if options.devicetype == 'b2g':
        if testtype == 'web':
            return B2GWebTest(testinfo, options, device, capture_controller)
        else:
            (basepath, testfile) = os.path.split(testpath)
            (file, pathname, description) = imp.find_module(testfile[0:-3],
                                                            [basepath])
            module = imp.load_module('test', file, pathname, description)
            test = module.Test(testinfo, options, device, capture_controller)
            return test
    else:
        if testtype == 'webstartup':
            return AndroidWebStartupTest(testinfo, options, device,
                                         capture_controller, profile_filename=profile_filename)
        elif testtype == 'appstartup':
            return AndroidAppStartupTest(testinfo, options, device,
                                         capture_controller)
        elif testtype == "web":
            return AndroidWebTest(testinfo, options, device,
                                  capture_controller, profile_filename=profile_filename)


class Test(object):

    finished_capture = False
    start_frame = None
    end_frame = None
    testlog = TestLog()
    logger = mozlog.getLogger('Test')

    def __init__(self, testinfo, options, device, capture_controller,
                 track_start_frame=False,
                 track_end_frame=False):

        # note: url params for startup tests currently not supported
        if testinfo.get('urlOverride'):
            self.testpath_rel = testinfo['urlOverride']
        else:
            self.testpath_rel = testinfo['relpath']
        if testinfo.get('urlParams'):
            self.testpath_rel += "?%s" % urllib.quote_plus(testinfo.get('urlParams'))

        self.requires_wifi = bool(testinfo.get('requiresWifi'))

        self.device = device
        self.capture_controller = capture_controller
        self.capture_timeout = int(testinfo['captureTimeout'])
        self.track_start_frame = track_start_frame
        self.track_end_frame = track_end_frame

    def cleanup(self):
        pass

    def wait(self):
        # Keep on capturing until we finish or timeout
        if self.capture_timeout:
            timeout = int(self.capture_timeout)
        else:
            timeout = 100
        timer = 0
        interval = 0.1

        try:
            while not self.finished_capture and timer < timeout:
                time.sleep(interval)
                timer += interval
        except KeyboardInterrupt:
            self.end_capture()
            raise

        if self.capture_timeout and not self.finished_capture:
            # this test was meant to time out, ok
            self.test_finished()
            self.end_capture()
        elif not self.finished_capture:
            # Something weird happened -- we probably didn't get a capture
            # callback. However, we can still retry the test.
            self.logger.info("Did not finish test / capture. Error!")
            self.end_capture()
            raise TestException("Did not finish test / capture",
                                can_retry=True)

    def start_capture(self):
        # callback indicating we should start capturing (if we're not doing so
        # already)
        self.logger.info("Start capture")
        if self.capture_controller and not self.capture_controller.capturing:
            self.capture_start_time = time.time()
            self.capture_controller.start_capture()

    def end_capture(self):
        # callback indicating we should terminate the capture
        self.logger.info("Ending capture")
        self.finished_capture = True
        if self.capture_controller:
            self.capture_controller.terminate_capture()

    def test_started(self):
        # callback indicating test has started
        if self.capture_controller and self.track_start_frame:
            self.start_frame = self.capture_controller.capture_framenum()

        self.test_start_time = time.time()
        self.logger.info("Test started callback (framenum: %s)" %
                         self.start_frame)

    def test_finished(self):
        # callback indicating test has finished
        if self.capture_controller and self.track_end_frame:
            self.end_frame = self.capture_controller.capture_framenum()
            # we don't need to find the end frame if we're slated to get the
            # start one...
            if self.capture_controller.find_start_signal:
                self.capture_controller.find_end_signal = False

        self.logger.info("Test finished callback (framenum: %s)" %
                         self.end_frame)

    def execute_actions(self, actions, test_finished_after_actions=True):
        self.logger.info("Executing actions")

        def executeCallback():
            self.test_started()
        actions = self.device.executeCommands(actions,
                                              executeCallback=executeCallback)
        for action in actions:
            # adjust time to be relative to start of test
            action['start'] -= self.test_start_time
            action['end'] -= self.test_start_time

        self.testlog.actions = actions

        if test_finished_after_actions:
            self.test_finished()


class WebTest(Test):

    def __init__(self, testinfo, options, device, capture_controller, use_actions=True):
        Test.__init__(self, testinfo, options, device, capture_controller,
                      track_start_frame=True, track_end_frame=True)

        # get actions for web tests
        actions_path = os.path.join(testinfo['here'], "actions.json")
        if use_actions:
            if os.path.exists(actions_path):
                self.actions = json.loads(open(actions_path).read())
            else:
                raise TestException("Test needs actions but no actions file '%s'" %
                                    actions_path)
        else:
            self.actions = None

        self.capture_server = CaptureServer(self)
        self.host = moznetwork.get_ip()
        self.http = mozhttpd.MozHttpd(
            docroot=TEST_DIR, host=self.host, port=0, log_requests=True,
            urlhandlers=[
                {'method': 'GET',
                 'path': '/api/captures/start/?',
                 'function': self.capture_server.start_capture},
                {'method': 'GET',
                 'path': '/api/captures/end/?',
                 'function': self.capture_server.end_capture},
                {'method': 'POST',
                 'path': '/api/captures/input/?',
                 'function': self.capture_server.input}])
        self.http.start(block=False)

        connected = False
        tries = 0
        while not connected and tries < 20:
            tries += 1
            import socket
            s = socket.socket()
            try:
                s.connect((self.host, self.http.httpd.server_port))
                connected = True
            except Exception:
                self.logger.info("Can't connect to %s:%s, retrying..." %
                                 (self.host, self.http.httpd.server_port))

        self.logger.info("Test URL is: %s" % self.url)

        if not connected:
            raise "Could not open webserver. Error!"

    @property
    def url(self):
        return "http://%s:%s/start.html?testpath=%s" % (
            self.host, self.http.httpd.server_port, self.testpath_rel)

    def test_finished(self):
        super(WebTest, self).test_finished()

        self.testlog.http_request_log = []
        # let's make the request times relative to the start of the test
        for request in self.http.request_log:
            request['time'] -= self.test_start_time
            self.testlog.http_request_log.append(request)

    def input_actions(self, commandset):
        if self.actions:  # startup test indicated by no actions
            self.logger.info("Executing commands '%s' for device '%s' "
                             "(framenum: %s)" % (commandset,
                                                 self.device.model,
                                                 self.start_frame))
            if not self.actions.get(commandset):
                raise TestException("Could not get actions for commandset "
                                    "'%s'" % commandset)
            # try to get a device-specific set of actions, falling back to
            # "default" if none exist
            default_actions = self.actions[commandset].get('default')
            actions = self.actions[commandset].get(self.device.model,
                                                   default_actions)
            if not actions:
                raise TestException("Could not get actions for device %s (and "
                                    "no default fallback)" % self.device.model)

            self.execute_actions(actions)
        else:
            # startup test: if we get here, it means we're done
            self.test_finished()


class AndroidWebTest(WebTest):

    def __init__(self, testinfo, options, device, capture_controller,
                 profile_filename=None, use_actions=True):
        WebTest.__init__(self, testinfo, options, device, capture_controller,
                         use_actions=use_actions)

        self.appname = options.appname
        self.extra_prefs = options.extra_prefs
        self.log_checkerboard_stats = options.log_checkerboard_stats
        self.profile_filename = profile_filename
        self.gecko_profiler_addon_dir = options.gecko_profiler_addon_dir
        self.preinitialize_user_profile = bool(
            int(testinfo.get('preInitializeProfile')))
        self.open_url_after_launch = bool(testinfo.get('openURLAfterLaunch'))

        # If we're logging checkerboard stats, set that up here (seems like it
        # takes a second or so to accept the new setting, so let's do that
        # here -- ideally we would detect when that's working, but I'm not sure
        # how to do so trivially)
        if self.log_checkerboard_stats:
            self.old_log_val = self.device.getprop(
                "log.tag.GeckoLayerRendererProf")
            self.device.setprop("log.tag.GeckoLayerRendererProf", "DEBUG")

        self.runner = eideticker.AndroidBrowserRunner(
            self.device, self.appname,
            self.url,
            preinitialize_user_profile=self.preinitialize_user_profile,
            open_url_after_launch=self.open_url_after_launch,
            enable_profiling=bool(self.profile_filename),
            gecko_profiler_addon_dir=options.gecko_profiler_addon_dir,
            extra_prefs=self.extra_prefs,
            extra_env_vars=options.extra_env_vars)

    def cleanup(self):
        # Clean up checkerboard logging preferences
        if self.log_checkerboard_stats:
            self.device.setprop(
                "log.tag.GeckoLayerRendererProf", self.old_log_val)

        # kill fennec, clean up temporary user profile
        self.runner.cleanup()

    def test_started(self):
        super(AndroidWebTest, self).test_started()

        if self.log_checkerboard_stats:
            self.device.recordLogcat()

    def test_finished(self):
        super(AndroidWebTest, self).test_finished()

        if self.log_checkerboard_stats:
            # sleep a bit to make sure we get all the checkerboard stats from
            # test
            time.sleep(1)
            self.testlog.checkerboard_percent_totals = 0.0
            CHECKERBOARD_REGEX = re.compile(
                '.*GeckoLayerRendererProf.*1000ms:.*\ '
                '([0-9]+\.[0-9]+)\/([0-9]+).*')
            for line in self.device.getLogcat(
                    filterSpecs=["GeckoLayerRendererProf:D", "*:S"],
                    format="brief"):
                match = CHECKERBOARD_REGEX.search(line.rstrip())
                if match:
                    (amount, total) = (float(match.group(1)),
                                       float(match.group(2)))
                    self.testlog.checkerboard_percent_totals += (
                        total - amount)

        if self.profile_filename:
            self.runner.save_profile()

    def run(self):
        self.runner.start()

        self.wait()

        if self.profile_filename:
            self.runner.process_profile(self.profile_filename)

        self.runner.cleanup()


class AndroidWebStartupTest(AndroidWebTest):

    def __init__(self, testinfo, options, device, capture_controller,
                 profile_filename=None, use_actions=False):
        AndroidWebTest.__init__(self, testinfo, options, device,
                                capture_controller,
                                profile_filename=profile_filename,
                                use_actions=use_actions)
        # don't want to track start frames for startup tests
        self.track_start_frame = False

        if self.capture_controller:
            # we never have the green screen tracking frames on startup tests,
            # but for most page load tests we have an end frame which helps
            # us get capture dimensions (the exception being about:home)
            self.capture_controller.find_start_signal = False
            self.capture_controller.find_end_signal = True
            if self.testpath_rel == "about:home":
                self.capture_controller.find_end_signal = False

    def run(self):
        self.runner.initialize_user_profile()

        if not self.open_url_after_launch:
            # FIXME: currently start capture before launching app because we
            # wait until app is launched -- would be better to make waiting
            # optional and then start capture after triggering app launch to
            # reduce latency?
            self.start_capture()
            self.test_started()
            self.runner.start()
        else:
            self.runner.start()
            # make sure fennec has actually started by sleeping for a bit.
            # this is a fairly arbitrary value but not sure of a better way
            time.sleep(5)
            self.start_capture()
            self.test_started()
            self.runner.open_url()

        self.wait()

        if self.profile_filename:
            self.runner.process_profile(self.profile_filename)

        self.runner.cleanup()

    @property
    def url(self):
        if self.testpath_rel == "about:home":
            return self.testpath_rel
        else:
            return "http://%s:%s/%s?startup_test=1" % (
                self.host, self.http.httpd.server_port, self.testpath_rel)


class AndroidAppStartupTest(Test):

    def __init__(self, testinfo, options, device, capture_controller):
        Test.__init__(self, testinfo, options, device, capture_controller)
        self.appname = testinfo.get('appname')
        self.activity = testinfo.get('activity')
        self.intent = testinfo.get('intent')

    def run(self):
        # FIXME: currently start capture before launching app because we wait
        # until app is launched -- would be better to make waiting optional and
        # then start capture after triggering app launch to reduce latency?
        self.start_capture()
        self.device.launchApplication(self.appname, self.activity, self.intent)
        self.wait()


class B2GWebTest(WebTest):

    def run(self):
        # start the tests by navigating to the url
        self.logger.info("Navigating to %s" % self.url)
        self.device.marionette.execute_script(
            "window.location.href='%s';" % self.url)
        self.wait()


class B2GAppTest(Test):

    def __init__(self, testinfo, options, device, capture_controller):
        Test.__init__(self, testinfo, options, device, capture_controller,
                      track_start_frame=True, track_end_frame=True)
        self.appname = testinfo.get('appname')

    def cleanup(self):
        if self.device.marionette and self.device.marionette.session:
            self.device.marionette.delete_session()
            self.device.marionette = None


class B2GAppActionTest(B2GAppTest):

    def launch_app(self):
        # launch app and wait for it to "settle" so that it's ready for use
        # (this is a naive implementation that just assumes that we're done
        # "loading" after 5 seconds -- feel free to override this method in
        # your test)
        apps = GaiaApps(self.device.marionette)
        app = apps.launch(self.appname)
        assert app.frame_id is not None
        time.sleep(5)

    def run(self):
        self.launch_app()
        self.start_capture()
        self.execute_actions(self.cmds)
        self.end_capture()

        # cleanup: switch back to main frame
        self.device.marionette.switch_to_frame()


class B2GAppStartupTest(B2GAppTest):

    def wait_for_content_ready(self):
        self.logger.info("No explicit logic for detecting content ready "
                         "specified. Waiting %s seconds for app to finish "
                         "starting (or settle)" % self.capture_timeout)
        time.sleep(self.capture_timeout)

    def run(self):
        self.device.gaiaApps.switch_to_displayed_app()  # switch to homescreen
        appicon = None

        # HACK: Bug 1026527 - perform a no-op swipe before running test to
        # workaround flame not processing input events properly
        self.device.executeCommands([['swipe_right']])

        icons = self.device.marionette.find_elements(
            By.CSS_SELECTOR, 'gaia-grid .icon:not(.placeholder)')
        for icon in icons:
            if icon.text == self.appname:
                self.device.marionette.execute_script(
                    'arguments[0].scrollIntoView(false);', [icon])
                appicon = icon
        if appicon is None:
            raise TestException("Cannot find icon for app with name "
                                "'%s'" % self.appname)

        tap_x = appicon.location['x'] + (appicon.size['width'] / 2)
        tap_y = appicon.location['y'] + (appicon.size['height'] / 2)

        self.start_capture()
        self.execute_actions([['tap', tap_x, tap_y]],
                             test_finished_after_actions=False)

        # wait for the app to be displayed
        apps = GaiaApps(self.device.marionette)
        Wait(self.device.marionette).until(
            lambda m: apps.displayed_app.name.lower() == self.appname.lower())
        apps.switch_to_displayed_app()

        self.wait_for_content_ready()

        self.logger.info("Content ready. Waiting an additional second to make "
                         "sure it has settled")
        time.sleep(1)

        self.test_finished()
        self.end_capture()
