#!/usr/bin/env python

import eideticker
import os
import sys
import time
import videocapture
import uuid
import xml
import StringIO

DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), "../downloads")
CAPTURE_DIR = os.path.join(os.path.dirname(__file__), "../captures")

def get_revision_data(sources_xml):
    revision_data = {}
    sources = xml.dom.minidom.parseString(open(sources_xml).read())
    for element in sources.getElementsByTagName('project'):
        path = element.getAttribute('path')
        revision = element.getAttribute('revision')
        if path in ['gaia', 'build']:
            revision_data[path + 'Revision'] = revision
    return revision_data

def runtest(dm, device_prefs, options, product, appinfo, testinfo,
            capture_name):
    capture_filename = os.path.join(CAPTURE_DIR,
                                    "%s-%s-%s-%s.zip" % (testinfo['key'],
                                                         options.appname,
                                                         appinfo.get('appdate'),
                                                         int(time.time())))
    productname = product['name']
    test_uuid = uuid.uuid1().hex

    if options.enable_profiling:
        productname += "-profiling"
        profile_filename = os.path.join(options.dashboard_dir, 'profiles',
                                        '%s.zip' % test_uuid)
    else:
        profile_filename = None

    test_completed = False
    for i in range(3):
        print "Running test %s (try %s of 3)" % (testinfo['key'], (i + 1))

        try:
            testlog = eideticker.run_test(
                testinfo['key'], options, capture_filename=capture_filename,
                profile_filename=profile_filename, capture_name=capture_name)
            test_completed = True
            break
        except eideticker.TestException, e:
            if e.can_retry:
                print "Test failed, but not fatally. Retrying..."
                print e
            else:
                print "Test failed (fatally). Aborting"
                print e
                raise

    if not test_completed:
        raise eideticker.TestException("Failed to run test %s for %s (after 3 "
                                       "tries). Aborting." % (testinfo['key'],
                                                              productname))

    # app/product date
    appdate = appinfo['appdate']

    datapoint = { 'uuid': test_uuid }
    metadata =  { 'appdate': appdate, 'label': options.capture_name,
                  'hasProfile': bool(options.enable_profiling) }
    for key in ['appdate', 'buildid', 'revision', 'geckoRevision',
                'gaiaRevision', 'buildRevision', 'sourceRepo']:
        if appinfo.get(key):
            metadata.update({key: appinfo[key]})

    # only interested in version if we don't have revision
    if not appinfo.get('revision') and appinfo.get('version'):
        metadata.update({ 'version': appinfo['version'] })

    if options.baseline:
        datapoint.update({'baseline': True})

    metrics = {}
    if options.capture:
        capture = videocapture.Capture(capture_filename)

        # video file
        video_relpath = os.path.join('videos', '%s.webm' % test_uuid)
        video_path = os.path.join(options.dashboard_dir, video_relpath)
        open(video_path, 'w').write(capture.get_video().read())

        if testinfo['type'] == 'startup' or testinfo['type'] == 'webstartup' or \
                testinfo['defaultMeasure'] == 'timetostableframe':
            metrics['timetostableframe'] = eideticker.get_stable_frame_time(
                capture)
        else:
            # standard test metrics
            metrics = eideticker.get_standard_metrics(capture, testlog.actions)

        metadata.update(eideticker.get_standard_metric_metadata(capture))

    datapoint.update(metrics)
    metadata['metrics'] = metrics

    # add logs (if any) to test metadata. we log http requests for webstartup
    # tests only. likewise, we log actions only for web tests and b2g tests
    testtype = testinfo['type']
    metadata.update(testlog.getdict(
            log_http_requests=(testtype == 'webstartup'),
            log_actions=(testtype == 'web' or testtype == 'b2g')))

    # Write testdata
    eideticker.update_dashboard_testdata(options.dashboard_dir,
                                         options.dashboard_id,
                                         options.device_id,
                                         options.branch_id, testinfo,
                                         productname, appdate,
                                         datapoint, metadata)

def main(args=sys.argv[1:]):
    usage = "usage: %prog [options] TEST..."

    parser = eideticker.TestOptionParser(usage=usage)
    eideticker.add_dashboard_options(parser)
    parser.add_option("--enable-profiling",
                      action="store_true", dest="enable_profiling",
                      help="Create SPS profile to go along with capture")
    parser.add_option("--dashboard-id", action="store", dest="dashboard_id",
                      help="id of dashboard (used in output json)",
                      default=os.environ.get('DASHBOARD_ID'))
    parser.add_option("--dashboard-name", action="store", dest="dashboard_name",
                      help="name of dashboard to display",
                      default=os.environ.get('DASHBOARD_NAME'))
    parser.add_option("--device-id", action="store", dest="device_id",
                      help="id of device (used in output json)",
                      default=os.environ.get('DEVICE_ID'))
    parser.add_option("--branch", action="store", dest="branch_id",
                      help="branch under test (used in output json)",
                      default=os.environ.get('BRANCH'))
    parser.add_option("--device-name", action="store", dest="device_name",
                      help="name of device to display in dashboard (if not "
                      "specified, display model name)",
                      default=os.environ.get('DEVICE_NAME'))
    parser.add_option("--apk", action="store", dest="apk",
                      help="Product apk to get metadata from "
                      "(Android-specific)")
    parser.add_option("--baseline", action="store_true", dest="baseline",
                      help="Create baseline results for dashboard")
    parser.add_option("--num-runs", action="store",
                      type="int", dest="num_runs",
                      help="number of runs (default: %default)", default=1)
    parser.add_option("--app-version", action="store", dest="app_version",
                      help="Specify app version (if not automatically "
                      "available; Android-specific)")
    parser.add_option("--sources-xml", action="store", dest="sources_xml",
                      help="Path to sources XML file for getting revision "
                      "information (B2G-specific)")
    parser.add_option("--product", action="store",
                      type="string", dest="product_name",
                      default="nightly",
                      help="product name (android-specific, default: "
                      "%default)")
    options, args = parser.parse_args()

    if not args: # need to specify at least one test to run!
        parser.print_usage()
        sys.exit(1)

    if not options.dashboard_id:
        parser.error("Must specify dashboard id (either with --dashboard-id "
                     "or with DASHBOARD_ID environment variable)")
    if not options.dashboard_name:
        parser.error("Must specify dashboard name (either with "
                     "--dashboard-name or with DASHBOARD_NAME environment "
                     "varaiable)")
    if not options.device_id:
        parser.error("Must specify device id (either with --device-id or with "
                     "DEVICE_ID environment variable)")
    if not options.branch_id:
        parser.error("Must specify branch (either with --branch or with "
                     "BRANCH environment variable)")

    # get device info
    device_prefs = eideticker.getDevicePrefs(options)
    device = eideticker.getDevice(**device_prefs)
    device_name = options.device_name
    if not device_name:
        device_name = device.model

    # copy dashboard files to output directory (if applicable)
    eideticker.copy_dashboard_files(options.dashboard_dir)

    if options.devicetype == 'android':
        product = eideticker.get_product(options.product_name)
        device_info = { 'name': device_name,
                        'version': device.getprop('ro.build.version.release')}
    elif options.devicetype == 'b2g':
        product = eideticker.get_product('b2g-nightly')
        device_info = { 'name': device_name }
    else:
        print "ERROR: Unknown device type '%s'" % options.devicetype

    # update dashboard / device index
    eideticker.update_dashboard_list(options.dashboard_dir, options.dashboard_id,
                                     options.dashboard_name)
    eideticker.update_dashboard_device_list(options.dashboard_dir, options.dashboard_id,
                                            options.device_id, options.branch_id, device_info)

    # get application/build info
    if options.devicetype == "android":
        if options.apk:
            if options.app_version:
                raise Exception("Should specify either --app-version or "
                                "--apk, not both!")
            appinfo = eideticker.get_fennec_appinfo(options.apk)
            options.appname = appinfo['appname']
            print "Using application name '%s' from apk '%s'" % (
                options.appname, options.apk)
            options.capture_name = "%s %s" % (product['name'], appinfo['appdate'])
        else:
            if not options.app_version:
                raise Exception("Should specify --app-version if not --apk!")

            # no apk, assume it's something static on the device
            appinfo = {
                'appdate': time.strftime("%Y-%m-%d"),
                'version': options.app_version}

    elif options.devicetype == "b2g":
        if not options.sources_xml:
            raise Exception("Must specify --sources-xml on b2g!")

        appinicontents = device.pullFile('/system/b2g/application.ini')
        sfh = StringIO.StringIO(appinicontents)
        appinfo = eideticker.get_appinfo(sfh)
        appinfo.update(get_revision_data(options.sources_xml))
        options.appname = None
    else:
        print "Unknown device type '%s'!" % options.devicetype

    # run through the tests...
    failed_tests = []
    for testkey in args:
        testinfo = eideticker.get_testinfo(testkey)

        eideticker.update_dashboard_test_list(options.dashboard_dir, options.dashboard_id,
                                              options.device_id, options.branch_id,
                                              testinfo)

        current_date = time.strftime("%Y-%m-%d")
        options.capture_name = "%s - %s (taken on %s)" % (testkey, product['name'],
                                                  current_date)

        if options.prepare_test:
            eideticker.prepare_test(testkey, options)

        # Run the test the specified number of times
        for i in range(options.num_runs):
            try:
                runtest(device, device_prefs, options,
                        product, appinfo, testinfo,
                        options.capture_name + " #%s" % i)
            except eideticker.TestException:
                print "Unable to run test '%s'. Skipping and continuing." % testkey
                failed_tests.append(testkey)
                break

        # synchronize with dashboard (if we have a server to upload to)
        if options.dashboard_server:
            eideticker.upload_dashboard(options)
        else:
            print "No dashboard server specified. Skipping upload."

    if failed_tests:
        print "The following tests failed: %s" % ", ".join(failed_tests)
        sys.exit(1)

main()
