#!/usr/bin/env python

import concurrent.futures
import eideticker
import json
import optparse
import os
import requests
import sys
import urlparse

exit_status = 0
MAX_WORKERS = 4

def save_file(filename, content):
    open(filename, 'wo').write(content)

def create_dir(dirname):
    if not os.path.exists(dirname):
        os.makedirs(dirname)

def validate_response(r):
    global exit_status

    if r.status_code != requests.codes.ok:
        print "WARNING: Problem downloading data at URL %s (HTTP " \
            "response code: %s)!" % (r.url, r.status_code)
        exit_status = 1
        return False

    return True

def validate_json_response(r):
    global exit_status

    if not validate_response(r):
        return False
    try:
        json.loads(r.text)
    except ValueError:
        exit_status = 1
        print "WARNING: Response from URL %s not valid json" % r.url
        return False

    return True

def urljoin(*args):
    baseurl = args[0]
    path = "/".join(args[1:])
    return urlparse.urljoin(baseurl, path)

def download_file(url, filename):
    r = requests.get(url)
    if not validate_response(r):
        return
    open(filename, 'w').write(r.content)

def download_metadata(baseurl, uuid, options, metadatadir, videodir, profiledir):
    metadata_url = urljoin(baseurl, 'metadata', "%s.json" % uuid)
    metadata_filename = os.path.join(metadatadir, "%s.json" % uuid)

    r = requests.get(metadata_url)
    if not validate_json_response(r):
        return

    metadata = r.json()
    videourl = urljoin(baseurl, 'videos', '%s.webm' % uuid)
    profileurl = None
    if metadata.get('hasProfile'):
        profileurl = urljoin(baseurl, 'profiles', '%s.zip' % uuid)
    if options.full_mirror:
        download_file(videourl,
                      os.path.join(videodir, os.path.basename(metadata['video'])))
        if profileurl:
            download_file(profileurl,
                          os.path.join(profiledir,
                                       os.path.basename(metadata['profile'])))
    save_file(metadata_filename, json.dumps(metadata))

def download_testdata(url, baseurl, filename, options, metadatadir,
                      videodir, profiledir):
    r = requests.get(url)
    if not validate_json_response(r):
        print "WARNING: %s json data invalid" % url
        return

    open(filename, 'w').write(r.content)

    testdata = r.json()['testdata']
    with concurrent.futures.ThreadPoolExecutor(MAX_WORKERS) as executor:
        for appname in testdata.keys():
            for date in testdata[appname].keys():
                for datapoint in testdata[appname][date]:
                    uuid = datapoint['uuid']
                    if options.download_metadata:
                        executor.submit(download_metadata, baseurl,
                                        uuid, options, metadatadir, videodir,
                                        profiledir)

usage = "usage: %prog [options] <url> <output directory>"
parser = optparse.OptionParser(usage)
parser.add_option("--full-mirror", action="store_true",
                  default=False, dest="full_mirror",
                  help="Download videos, profiles to disk")
parser.add_option("--skip-metadata", action="store_false",
                  dest="download_metadata", default=True,
                  help="Skip downloading metadata JSON files")
parser.add_option("--dashboard-id", action="store",
                  dest="dashboard_id",
                  help="Only download information for dashboard id")
parser.add_option("--device-id", action="store",
                  dest="device_id",
                  help="Only download information for device id (must be used "
                  "in conjunction with --dashboard-id)")
options, args = parser.parse_args()

if len(args) != 2:
    parser.print_usage()
    sys.exit(1)

if options.full_mirror and not options.download_metadata:
    parser.error("Need to download metadata for full mirror")
    sys.exit(1)

if options.device_id and not options.dashboard_id:
    parser.error("--device-id must be used in conjunction with --dashboard-id")
    sys.exit(1)

(baseurl, outputdir) = args
if baseurl[-1] != '/':
    baseurl += '/'

eideticker.copy_dashboard_files(outputdir)

metadatadir = os.path.join(outputdir, 'metadata')
videodir = os.path.join(outputdir, 'videos')
profiledir = os.path.join(outputdir, 'profiles')

r = requests.get(urljoin(baseurl, 'dashboard.json'))
if not validate_json_response(r):
    print "Can't download dashboard list, exiting"
    sys.exit(1)
save_file(os.path.join(outputdir, 'dashboard.json'), r.content)

dashboard_ids = map(lambda d: d['id'], r.json()['dashboards'])
if options.dashboard_id:
    if options.dashboard_id in dashboard_ids:
        dashboard_ids = [ options.dashboard_id ]
    else:
        print "ERROR: dashboard id '%s' specified but unavailable." % \
            options.dashboard_id

with concurrent.futures.ThreadPoolExecutor(MAX_WORKERS) as executor:
    for dashboard_id in dashboard_ids:
        dashboard_dir  = os.path.join(outputdir, dashboard_id)
        create_dir(dashboard_dir)

        r = requests.get(urljoin(baseurl, dashboard_id, 'devices.json'))
        if not validate_json_response(r):
            print "ERROR: Can't download device list for dashboard '%s', " \
                "exiting" % dashboard_id
            sys.exit(1)

        save_file(os.path.join(dashboard_dir, 'devices.json'), r.content)
        devices = r.json()['devices']

        if options.device_id:
            if options.device_id in devices.keys():
                deviceids = [ options.device_id ]
            else:
                print "WARNING: Device id '%s' specified but unavailable. " \
                    "Skipping." % options.device_id
                deviceids = []
        else:
            deviceids = devices.keys()

        for deviceid in deviceids:
            for branchid in devices[deviceid]['branches']:
                r = requests.get(urljoin(baseurl, dashboard_id, deviceid,
                                         branchid, 'tests.json'))
                if not validate_json_response(r):
                    print "WARNING: Skipping tests for dashboard %s, " \
                        "device: %s, branch: %s" % (dashboard_id, deviceid,
                                                    branchid)
                    continue

                testdir = os.path.join(dashboard_dir, deviceid, branchid)
                create_dir(testdir)
                save_file(os.path.join(testdir, 'tests.json'), r.content)

                tests = r.json()['tests']
                for testname in tests.keys():
                    testfilename = '%s.json' % testname
                    executor.submit(download_testdata,
                                    urljoin(baseurl, dashboard_id, deviceid,
                                            branchid, testfilename),
                                    baseurl,
                                    os.path.join(outputdir, dashboard_id,
                                                 deviceid, branchid,
                                                 testfilename),
                                    options,
                                    metadatadir, videodir, profiledir)

sys.exit(exit_status)
