#!/usr/bin/env python

import datetime
import eideticker
import json
import os
import sys
import time
import uuid
import videocapture

CAPTURE_DIR = os.path.join(os.path.dirname(__file__), "../captures")


def runtest(device_prefs, testname, options, apk=None, appname=None,
            appdate=None):
    if apk:
        appinfo = eideticker.get_fennec_appinfo(apk)
        appname = appinfo['appname']
        print "Installing %s (version: %s, revision %s)" % (
            appinfo['appname'], appinfo['version'], appinfo['revision'])
        device = eideticker.getDevice(**device_prefs)
        device.updateApp(apk)
    else:
        appinfo = None

    options.appname = appname

    testinfo = eideticker.get_testinfo(testname)
    stableframecapture = (testinfo['type'] in ('startup', 'webstartup') or
                          testinfo['defaultMeasure'] == 'timetostableframe')

    capture_results = []

    if options.prepare_test:
        eideticker.prepare_test(testname, options)

    for i in range(options.num_runs):
        # get a uuid for the run
        test_uuid = uuid.uuid1().hex

        # Now run the test
        curtime = int(time.time())
        capture_file = os.path.join(CAPTURE_DIR,
                                    "metric-test-%s-%s.zip" % (appname,
                                                               curtime))
        if options.enable_profiling and options.outputdir:
            profile_relpath = os.path.join('profiles', '%s.zip' % test_uuid)
            profile_filename = os.path.join(options.outputdir, profile_relpath)
        else:
            profile_filename = None

        current_date = time.strftime("%Y-%m-%d")
        capture_name = "%s - %s (taken on %s)" % (
            testname, appname, current_date)

        testlog = eideticker.run_test(testname, options,
                                      capture_filename=capture_file,
                                      profile_filename=profile_filename,
                                      capture_name=capture_name)

        datapoint = { 'uuid': test_uuid }
        metadata = {}
        metrics = {}

        if options.capture:
            capture = videocapture.Capture(capture_file)

            datapoint['captureFile'] = metadata['captureFile'] = capture_file
            metadata['captureFPS'] = capture.fps
            metadata['generatedVideoFPS'] = capture.generated_video_fps

            if stableframecapture:
                metrics['timetostableframe'] = \
                    eideticker.get_stable_frame_time(capture)
            else:
                metrics.update(
                    eideticker.get_standard_metrics(capture, testlog.actions))
            metadata['metrics'] = metrics

            metadata.update(eideticker.get_standard_metric_metadata(capture))

            if options.outputdir:
                video_path = os.path.join(options.outputdir, 'videos',
                                          '%s.webm' % test_uuid)
                open(video_path, 'w').write(capture.get_video().read())

        if options.log_checkerboard_stats:
            metrics['internalcheckerboard'] = \
                testlog.checkerboard_percent_totals

        # Want metrics data in data, so we can graph everything at once
        datapoint.update(metrics)

        if options.enable_profiling:
            metadata['hasProfile'] = True

        # dump metadata
        if options.outputdir:
            # metadata
            metadata_path = os.path.join(options.outputdir, 'metadata',
                                         '%s.json' % test_uuid)
            open(metadata_path, 'w').write(json.dumps(metadata))

        capture_results.append(datapoint)

    if options.devicetype == "b2g":
        # FIXME: get information from sources.xml and application.ini on
        # device, as we do in update-dashboard.py
        display_key = appkey = "FirefoxOS"
    else:
        appkey = appname
        if appdate:
            appkey = appdate.isoformat()
        else:
            appkey = appname

        if appinfo and appinfo.get('revision'):
            display_key = "%s (%s)" % (appkey, appinfo['revision'])
        else:
            display_key = appkey

    print "=== Results on %s for %s ===" % (testname, display_key)

    if options.capture:
        measures = [ ('timetostableframe',
                      'Times to first stable frame (seconds)'),
                     ('uniqueframes', 'Number of unique frames'),
                     ('fps', 'Average number of unique frames per second'),
                     ('overallentropy',
                      'Overall entropy over length of capture'),
                     ('checkerboard',
                      'Checkerboard area/duration (sum of percents NOT '
                      'percentage)'),
                     ('timetoresponse',
                      'Time to first input response (seconds)') ]
        for measure in measures:
            if measure[0] in capture_results[0]:
                print "  %s:" % measure[1]
                print "  %s" % map(lambda c: c[measure[0]], capture_results)
                print

        print "  Capture files:"
        print "  Capture files: %s" % map(lambda c: c['captureFile'], capture_results)
        print

    if options.log_checkerboard_stats:
        print "  Internal Checkerboard Stats (sum of percents, not "
        "percentage):"
        print "  %s" % map(
            lambda c: c['internalcheckerboard'], capture_results)
        print

    if options.outputdir:
        outputfile = os.path.join(options.outputdir, "metric.json")
        resultdict = {'title': testname, 'data': {}}
        if os.path.isfile(outputfile):
            resultdict.update(json.loads(open(outputfile).read()))

        if not resultdict['data'].get(appkey):
            resultdict['data'][appkey] = []
        resultdict['data'][appkey].extend(capture_results)

        with open(outputfile, 'w') as f:
            f.write(json.dumps(resultdict))


def main(args=sys.argv[1:]):
    usage = "usage: %prog <test> [appname1] [appname2] ..."
    parser = eideticker.TestOptionParser(usage=usage)
    parser.add_option("--num-runs", action="store",
                      type="int", dest="num_runs",
                      default=1,
                      help="number of runs (default: 1)")
    parser.add_option("--output-dir", action="store",
                      type="string", dest="outputdir",
                      help="output results to web site")
    parser.add_option("--enable-profiling", action="store_true",
                      dest="enable_profiling",
                      help="Collect performance profiles using the built in "
                      "profiler.")
    parser.add_option("--url-params", action="store",
                      dest="url_params", default="",
                      help="additional url parameters for test")
    parser.add_option("--use-apks", action="store_true", dest="use_apks",
                      help="use and install android APKs as part of test "
                      "(instead of specifying appnames)")
    parser.add_option("--date", action="store", dest="date",
                      metavar="YYYY-MM-DD",
                      help="get and test nightly build for date")
    parser.add_option("--start-date", action="store", dest="start_date",
                      metavar="YYYY-MM-DD",
                      help="start date for range of nightlies to test")
    parser.add_option("--end-date", action="store", dest="end_date",
                      metavar="YYYY-MM-DD",
                      help="end date for range of nightlies to test")

    options, args = parser.parse_args()

    if len(args) == 0:
        parser.error("Must specify at least one argument: the test")

    if options.enable_profiling and not options.outputdir:
        parser.error("Must specify output directory if profiling enabled")

    dates = []
    appnames = []
    apks = []
    if options.start_date and options.end_date and len(args) == 1:
        testname = args[0]
        start_date = eideticker.BuildRetriever.get_date(options.start_date)
        end_date = eideticker.BuildRetriever.get_date(options.end_date)
        days = (end_date - start_date).days
        for numdays in range(days + 1):
            dates.append(start_date + datetime.timedelta(days=numdays))
    elif options.date and len(args) == 1:
        testname = args[0]
        dates = [eideticker.BuildRetriever.get_date(options.date)]
    elif not options.date and len(args) >= 2:
        testname = args[0]
        if options.use_apks:
            apks = args[1:]
        else:
            appnames = args[1:]
    elif options.devicetype == "b2g":
        testname = args[0]
    elif not options.date or (not options.start_date and not options.end_date):
        parser.error("On Android, must specify date, date range, a set of "
                     "appnames (e.g. org.mozilla.fennec) or a set of apks (if "
                     "--use-apks is specified)")

    device_prefs = eideticker.getDevicePrefs(options)

    if options.outputdir:
        eideticker.copy_dashboard_files(options.outputdir,
                                        indexfile='metric.html')

    if options.devicetype == "b2g":
        runtest(device_prefs, testname, options)
    elif appnames:
        for appname in appnames:
            runtest(device_prefs, testname, options, appname=appname)
    elif apks:
        for apk in apks:
            runtest(device_prefs, testname, options, apk=apk)
    else:
        br = eideticker.BuildRetriever()
        productname = "nightly"
        product = eideticker.get_product(productname)
        for date in dates:
            apk = br.get_build(product, date)
            runtest(device_prefs, testname, options, apk=apk, appdate=date)

main()
