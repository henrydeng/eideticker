# Eideticker

Eideticker is an automated test harness for web browsers that captures and
analyzes browser output via HDMI or an external camera.

## Requirements

* Ubuntu Linux system with python and various other third-party dependencies
  installed. You can make sure that you have everything installed by running
  `install-ubuntu-deps.sh` from the root directory of your eideticker
  checkout (root is required).

  The recommended Linux distribution to use is Ubuntu 14.04 64-bit (32-bit is
  known not to work with the PointGrey cameras). Later versions
  of Ubuntu are probably also fine.

  If you wish to enable gecko profiler support, you will also need to download
  and install szip and addr2lines into your path. You can get szip from
  http://people.mozilla.com/~bgirard/szip/linux/szip and add2rline from
  https://people.mozilla.com/~nchen/arm-eabi-addr2line.tar.bz2

* A supported mobile phone running Firefox OS or Android. Your phone must be
  connected to the same network as the machine running the tests. In the case
  of Android, it is currently required that your device be rooted and must be
  configured to communicate with the host using either the
  [Android Debug Bridge](https://developer.android.com/tools/help/adb.html) (adb)
  or [SUTAgent](https://wiki.mozilla.org/Auto-tools/Projects/SUTAgent). If
  the latter on Android, you must configure the su binary to automatically
  allow SUTAgent to run commands as root in silent mode (so that
  notifications don't pop up while running tests.

The remaining requirements depend on whether you are capturing with the phone's
HDMI out or with a PointGrey camera. It is also possible to use the Eideticker
harness without video capture, which can be useful for certain cases: see below.

### HDMI

For HDMI capture, the Linux system you are using must be a desktop class
machine with a spare PCI express slot (we used the Dell Precision T1600
workstation, but that seems to be no longer sold) with a Blackmagic Design
DeckLink HD Extreme 3D card installed. The mobile phone you are using must
also support HDMI out with a clean 720p or 1080p signal: the Samsung Galaxy
Nexus (with an MHL adaptor) and the LG G2X are known to work. Note that the
Samsung Nexus 4 is known NOT to work, even with a MHL HDMI adapter as it does
not output an exact 720p signal (and thus the Decklink card can not understand
what it is outputting).

For more information on the Decklink cards, see the
[Decklink Primer](https://wiki.mozilla.org/Project_Eideticker/DeckLink_Primer)

### Camera

* The Linux system you are using must have USB3 ports (USB3 ports are usually
  blue). If you have a desktop machine without a USB3 port, there are
  [PCI cards](http://www.ptgrey.com/products/usb3-components/usb3-components.asp)
  to add this capability.

* [USB3 micro-b cable](http://www.ptgrey.com/products/usb3-components/usb3-components.asp)
  (possibly add a hub depending on machine)

* [PointGrey Flea3 FL3-U3-13E4C-C](http://www.ptgreystore.com/products/229-flea3-13mp-color-usb-30-e2v-ev76c560.aspx)
  camera. Note that the iris on the camera should be fully open for the distributed settings file to be most effective.

* [Fujinon HF12.5HA-1B](http://www.ptgreystore.com/products/98-fujinon-hf125ha-1b-lens.aspx)
  camera lens.

* [Joby GorillaPod](http://joby.com/gorillapod/original/) flexible tripod for
  the camera.

* FlyCapture camera software available from
  [PointGrey](http://www.ptgrey.com/support/downloads) (you will need to
  register an account to access the downloads). Note that you may also need to
  run this using `sudo` in order to get it to detect the camera.

## Installation

### Host Machine

Run `bootstrap.sh` in the root directory to set everything up.

There are two additional steps required if you wish to capture video with
HDMI or the PointGrey Camera

#### HDMI

From the root directory, type:

    cd src/videocapture/videocapture/decklink && make

#### Camera

    cd src/videocapture/videocapture/pointgrey && make

### Phones

You will need to install copies of [Orangutan](http://github.com/mozilla-b2g/orangutan)
and [ntpdate-android](http://github.com/wlach/ntpclient-android) on each of the phones
in either `/data/local` or `/data/local/tmp`.

## Usage

Eideticker is meant to be run in a virtualenv, so the first step is to set
that up in your shell by running this command within the root directory:

    source ./bin/activate

The next step depends on whether you're using adb or SUTAgent to interface
with the device (on Firefox OS, we assume adb). If the former, just connect
your device to your computer's USB port. That's it, you should now be set to
run tests!

If you're using SUTAgent, you'll want to start the SUTAgent app, note the
ip address of your phone, then set the following environment variables:

    export DM_TRANS=sut
    export TEST_DEVICE=<device ip of phone>

If you are using a FirefoxOS device with adb, then you might need sudo
privileges for adb if you haven't set up udev rules that allow a normal
user to access the device:

    adb kill-server
    sudo adb start-server

If you are using a FirefoxOS device, then you also might need to set
the property of the following environment variable as it presently is
set to default to 'android'

    export DEVICE_TYPE=b2g

On FirefoxOS, you will also need to set up a WIFI settings file for the
device, so it knows which network to connect to when running tests (this
should be the same one that the host computer is connected to). You can
generate one by running the `create-wifi-settings.py` script with the
appropriate arguments. For example, to create WIFI settings for a network
called "Mozilla" with WPA-PSK key management and the password "letmein", run:

    create-wifi-settings.py Mozilla WPA-PSK letmein > wifi-settings-mozilla

If you are using a PointGrey camera to capture footage of the device, you
will need to first calibrate the camera and determine the area to capture.

First, set the following environment variables:

    export CAPTURE_DEVICE=pointgrey

Next, change to the /src/videocapture/videocapture/pointgrey directory and
run `make` to build the capture tool for the PointGrey hardware.

Make sure that you have the appropriate udev rules in place. These are set
in `/etc/udev/rules.d/40-pgr.rules`. You can find your exact vendor and product
details by running `lsusb` with the camera attached. For example if you see
something like:

    Bus 004 Device 003: ID 1e10:300a Point Grey Research, Inc.

You will need the following like in your rules file:

    ATTRS{idVendor}=="1e10", ATTRS{idProduct}=="300a", MODE="0664", GROUP="pgrimaging"

This should be done for you during the installation of the FlyCap software,
however it's best to double check as the values are case sensitive. If the
camera cannot be detected it's a good chance this is wrong. You should
restart the udev service after updating this file, and may been to disconnect
and reconnect the camera:

    sudo service udev restart

Now position the camera setup and mounted device so that the device appears
to be in the visual field. Next, run the `flycap` utility on the command line.
Select camera. Select "Configure Selected". In new dialog, select "Standard
Video Modes". Select Y8. Now, go back to main dialog and select "OK". You
should see a camera preview. Adjust the camera/device as needed until there is
a very clear and sharp picture of the device in view. Once this is done, you
will need to run the getdimensions.py to get the dimensions to capture:

    ./bin/getdimensions.py -w <wifi settings file>

Set the CAPTURE_AREA environment variable to the output of that utility, for
example:

    export CAPTURE_AREA="[355, 83, 1043, 933]"

### Running a simple test

To get a list of tests to run, use the list tests script:

    ./bin/list-tests.py

Once you've selected a test to run, you can launch it with the following
command line:

    ./bin/runtest.py [options] <test>

On Android, you need to specify the name of the application you want to run
the test. For fennec nightly, you'd use:

    ./bin/runtest.py --app-name org.mozilla.fennec <test>

On Firefox OS, you can just specify the test and a wifi settings file, like
this:

    ./bin/runtest.py -w <wifi settings file> <test>

If you have a proper camera set up, you should get a recorded capture in the
captures/ subdirectory. You can view some details of this capture with the
Eideticker web application. Load it by running `./bin/webapp.sh` and then
navigating to http://localhost:8080 with your browser.

If you just want to run through a test *without* capturing any output (e.g. if
you are just working on a test and/or don't have a capture rig), pass the
--no-capture option. For example on Android:

    ./bin/runtest.py --app-name org.mozilla.fennec --no-capture taskjs

#### Tests that need Marionette

If you need to run a test that needs Marionette you will need to forward port 2828
    adb forward tcp:2828 tcp:2828

### Console profiling

Console mode allows you to get one-off results of running Eideticker for a
single test. You run a program called get-metric-for-build.py and it will
print some numbers to standard output (or optionally output a web
visualization of the results: see below).

#### get-metric-for-build on Android

To run get-metric-for-build against an already-installed version of
Fennec, specify the name of the test followed by the names of the
applications you want to test:

    ./bin/get-metric-for-build.py <test> [app name 1] [app name 2] ...

If you want to test a set of apks, use the `--use-apks` option and specify
the set of apks you want to test after the test name.

    ./bin/get-metric-for-build.py --use-apks <test> <apk of build 1> [apk of build 2] ...

For example, to run the canvas clock test against the copy of Fennec nightly
currently installed on the device, do:

    ./bin/get-metric-for-build.py --use-apks clock org.mozilla.fennec

To run the same test against an uninstalled copy of Fennec nightly, try:

    ./bin/get-metric-for-build.py --use-apks clock nightly.apk

Occasionally you may want to run Fennec with a custom preference or two set,
you can do this with the "extra prefs" option. Just pass a json dictionary
of preferences, and they will be merged into the profile used by fennec:

    ./bin/get-metric-for-build.py --use-apks \
        --extra-prefs "{gfx.color_management.enablev4: true}" clock \
        nightly.apk

In addition to supporting HDMI capture and analysis on Fennec, it is also
possible to run the Eideticker harness in a mode that simply "captures" a
performance log of the amnount of checkerboarding in Fennec and outputs
results. This has two advantages: first, you don't need any kind of
specialized hardware. Second, it's much faster (since there's no
video encoding/decoding/analysis step). For this you want to pass in
"--no-capture" and "--get-internal-checkerboard-stats", like so:

    ./bin/get-metric-for-build.py --use-apks --no-capture --get-internal-checkerboard-stats taskjs nightly.apk

#### get-metric-for-build on FirefoxOS

Running get-metric-for-build on FirefoxOS is almost exactly the same, except
you do not have to specify apk or application information. Just specify the
name of the test you'd like to run. For example:

    ./bin/get-metric-for-build.py -w <wifi settings file> b2g-contacts-scrolling

A WIFI settings file is required on FirefoxOS because we automatically wipe
the saved settings before every test and we always need a network connection
in order to synchronize the time between the device and the host machine
running it, even if there is no other network activity involved in the test.

#### Getting more results

Typically, you want to run Eideticker more than once on a particular test to
get a range of results as tests are not 100% deterministic (both due to the
nature of the tests and the device we are running the test on). You can do
this with the `--num-runs` option. For example on Android:

    ./bin/get-metric-for-build.py --use-apks --num-runs 5 clock nightly.apk

Or on FirefoxOS:

    ./bin/get-metric-for-build.py -w <wifi settings file> --num-runs 5 clock

#### Visualizing results

You can optionally output the results of get-metric-for-build to a web site
through the `--output-dir` option. For example:

    ./bin/get-metric-for-build.py -w <wifi settings file> --num-runs 5 \
        --output-dir $HOME/contacts-test b2g-contacts-scrolling

You can then open up the resulting directory in a web browser and view the
results. Or upload them to a static web server and share them with others!

#### Interpreting results

If you want to know more about the results (where the numbers are coming from)
you can open them up inside the Eideticker web interface. To open it, execute:

    ./bin/webapp.sh

Then connect to http://localhost:8080. You should see a list of captures, select
the one you're interested in to dive into fine grained detail.

## Eideticker "dashboard"

Dashboard mode is used to generate a dashboard of Eideticker results, like
what you see at http://eideticker.mozilla.org. From a toplevel, it
is run from a script called `bin/run-update-dashboard.sh`, which can be called
standalone. This script then in turn calls another script called
`bin/update-dashboard.py` with various arguments corresponding to Firefox
version, test to run, etc. This is not yet supported for FirefoxOS.

Setting up a new instance of the dashboard has two components: setting up one
or more "clients" (machines that run the tests) and setting up the server
(machines that will serve up the results).

### Dashboard Server Setup

* Install nginx, ssh, and rsync if not installed already.
* Create an "eideticker" user on the machine (with home directory).
* As the newly-created user, create a "www" subdirectory.
* Create an nginx configuration (on Redhat-based systems,
`/etc/nginx/conf.d`).
* Restart nginx. You will need to configure the clients before you
will see anything on the dashboard.

Here's the nginx configuration we currently use in production:

    server {
            listen 80; #or change this to your public IP address eg 1.1.1.1:80
            server_name eideticker;
            server_name eideticker.wrla.ch;
            access_log /var/log/nginx/eideticker.access_log;
            error_log /var/log/nginx/eideticker.error_log;

            location / {
                    root   /home/eideticker/www;
                    index  index.html index.htm;
                    add_header 'Access-Control-Allow-Origin' '*';
            }
    }

Note the Access-Control-Origin header, which allows us to integrate the SPS
profiler to request Eideticker resources directly (useful for direct linking
to capture analysis).

### Dashboard Client Setup

Each Eideticker client works by creating its own static copy of the dashboard,
then copying the relevant files to the server setup above.

To setup to capture and store results

FIXME: TODO

To setup to synchronize to the Eideticker server:

* Generate an ssh key for the client machine, if it doesn't have one already.
* On the server, copy/paste the generated public key into
  `/home/eideticker/.ssh/authorized_keys` (if you're creating this file /
  directory for the first time, be sure that the directory has 700 (rwx only
  for its owner) permissions and the file has 600 (rw only for its owner)
  permissions.
* Set up the sync-dashboard script to synchronize the dashboard data to the
  server on a fixed schedule using cron. Use `crontab -e` to add an entry like
  this:

    0 0 * * * /home/mozauto/src/eideticker/bin/sync-dashboard.sh eideticker.wrla.ch

## Creating New Eideticker Tests

There are several types of Eideticker tests: startup tests, web tests, and
b2g (FirefoxOS) tests. Startup tests measure the amount of time it takes to
load a particular web site. Web tests load a website and then perform a set of
actions on them (e.g. panning). B2G tests record the performance of some set
of actions inside a FirefoxOS application (e.g. scrolling through a list of
contacts).

The first step in adding a new test is to create a subdirectory in `src/tests`
to store the test, then add an ini file with the test manifest. A manifest
allows the command line tools to get the testname and we provides the necessary
metadata (test descriptions, etc.) for the dashboard and other reporting tools.
It is just a simple ini file like this:

    [index.html]
    key = clock
    shortDesc = Canvas Clock Test
    defaultMeasure = fps

The filename in square brackets is the test file name (usually an html file in
the case of a web test, probably a python file in the case of a b2g test). The
"key" is a short alphanumeric key used to identify the test. The shortDesc and
defaultMeasure are for the dashboard: the description is the graph title, the
defaultMeasure indicates what metric we should display by default when the user
clicks on the entry in the dashboard web UI.

After creating the ini file, you'll want to link to it from the parent directory
so it gets picked up by the harness. See "manifest.ini" in the ep1 testset for
an example.

### B2G Tests

A B2G test is generally a mix of calls to Marionette (to launch an application
and set it into an initial state) followed by another set of calls to Marionette
and/or a set of direct input actions which are recorded.

Perhaps the best way to illustrate what you need in such a test is to take an
example. Let's take a look at the current b2g startup test:

    from eideticker.test import B2GTest
    import time
    from gaiatest.gaia_test import GaiaApps
    
    class Test(B2GTest):
        def __init__(self, testinfo, **kwargs):
            super(Test, self).__init__(testinfo, **kwargs)
    
            self.appname = testinfo['appname']
    
        def run(self):
            apps = GaiaApps(self.device.marionette)
    
            # theoretically it would be cleaner to set this specifically for the
            # camera test, but that seemed additional complication for no real
            # gain
            apps.set_permission('Camera', 'geolocation', 'deny')
    
            self.start_capture()
            self.test_started()
            app = apps.launch(self.appname)
            assert app.frame_id is not None
            self.log("Waiting %s seconds for app to finish starting" %
                     self.capture_timeout)
            time.sleep(self.capture_timeout)
            self.test_finished()
            self.end_capture()
    
            # cleanup: switch back to main frame
            self.device.marionette.switch_to_frame()

The __init__ method contains a constructor which grabs a bit of metadata from
the testinfo dictionary (passed in from the manifest) to determine which
application to launch.

The run method is where we actually interact with the harness. The key points
of interaction with the Eideticker harness are start_capture, test_started,
test_finished, and end_capture methods. start_capture and end_capture
correspond to starting and shutting down the video capture. test_started and
test_finished correspond to the test starting and ending. Generally you
would pair each start and end pair together unless you were doing something
exotic. It is between the test_started and test_finished callbacks that you
would perform whatever action you wanted to perform.

### Web Tests

Web tests are just static HTML with a bit of JavaScript glue to
interface with the harness and some JSON metadata to describe actions that
Eideticker should perform while a capture is ongoing. The simplest example
of a test would probably be the clock demo, which you can find in
`src/tests/ep1/clock/index.html` (you have to run `./bootstrap.sh first to
checkout the ep1 submodule before you can find this file).

Writing your own tests is a matter of adding a subdirectory to Eideticker as
per the generic instructions, then creating/copying an HTML page of your choice,
adding the relevant JavaScript code to start/stop the test as appropriate, and
then making an actions.json file with whatever actions you want to simulate during
the test.

The JavaScript code is encapsulated in the file: `src/tests/js/eideticker.js`.
Much of the code in there is just used by the harness. From the point of view
of an Eideticker test, you really just need to call the "finish" method, which
we use to trigger the end of a capture.

Creating actions for use during a test (and making sure they get called) is
somewhat more involved, but not much. Alongside the various HTML/JS/Image
files that correspond to your page, you also want to create an `actions.json`
file that indicates what you want to happen during the test. Here's an example:

    {
      "default": {
        "LG-P999": [
          ["scroll_down", 4],
          ["sleep", 5]
        ],
        "Galaxy Nexus": [
          ["scroll_down", 7, 3],
          ["sleep", "4"]
        ]
      }
    }

As you can see, this is basically a dictionary of dictionaries. The top-level
is a dictionary of action sets. Normally you just have one, default, but you
can add more in case you want to have multiple tests with different types
of actions (the New York Times test, in `src/tests/ep1/nytimes` would be
an exmaple of this).

The next level down is a dictionary of actions corresponding to different
models of phone (as determined by the `ro.product.model` property of
Android). This is because different types of phones have different input
properties (screen sizes, operating system versions, etc.). The set of
actions is an array of arrays. Each action array corresponds to a single
action performed during a test. As of this writing, there are four possible
actions:

*sleep* [secs]

This action simply sleeps for the corresponding number of seconds (typically
used to allow something to complete in the capture before possibly performing
other actions)

*scroll_down* [number of times] [number of steps]

Triggers a scroll down the specified number of times. Optionally pass the
number of steps parameter to make the action go slower is faster
(lower=faster, default is 10).

*scroll_up* [number of times] [number of steps]

Triggers a scroll up the specified number of times. Optionally pass the
number of steps parameter to make the action go slower is faster
(lower=faster, default is 10).

*double_tap* [x coordinate] [y coordinate]

Triggers two tap events in succession, at the specified x and y coordinates
(this is designed to allow zooming into a web page).

Triggering these actions requires posting to the JSON API endpoint on the
Eideticker desktop machine running the test. This is typically done as
follows (using jQuery):

    $.post('/api/captures/input', { 'commands': 'default' },
           function() {
               Eideticker.finish();
           });

Obviously you should replace "default" in the above example with the set of
commands that you actually want to run.

