import json
import os
import shutil
import subprocess
import time

DASHBOARD_DIR = os.path.join(os.path.dirname(__file__), "../../dashboard/")

def add_dashboard_options(option_parser):
    # A set of dashboard-specific options you can add to your option parser
    option_parser.add_option("--dashboard-user", action="store",
                             dest="dashboard_user", default=os.getenv("DASHBOARD_USER",
                                                                      "eideticker"),
                             help="username to login to dashboard if "
                             "using rsync (default: %default)")
    option_parser.add_option("--dashboard-server", action="store",
                             dest="dashboard_server",
                             default=os.getenv('DASHBOARD_SERVER'),
                             help="server to upload dashboard data to")
    option_parser.add_option("--dashboard-remote-path", action="store",
                             dest="dashboard_remote_path", default="~/www/",
                             help="remote path on dashboard server to upload "
                             "to (default: %default)")
    option_parser.add_option("--output-dir", action="store",
                             type="string", dest="dashboard_dir",
                             default=DASHBOARD_DIR,
                             help="directory where dashboard results are or "
                             "will be stored (default: %default)")

class NestedDict(dict):
    def __getitem__(self, key):
        if key in self:
            return self.get(key)
        return self.setdefault(key, NestedDict())

def copy_dashboard_files(dashboard_dir, indexfile='index.html'):
    # nothing to do if output dir is actually dashboard dir (well, except
    # if indexfile=='metric.html', but in that case you probably shouldn't
    # be dumping results there...)
    if os.path.abspath(dashboard_dir) == os.path.abspath(DASHBOARD_DIR):
        return

    dashboard_filenames = subprocess.check_output(
        ['git', 'ls-files', DASHBOARD_DIR]).splitlines()
    relative_dashboard_filenames = map(lambda f:
                                           os.path.relpath(f, DASHBOARD_DIR),
                                       dashboard_filenames)
    dirnames = [dashboard_dir] + \
        sorted(set(map(lambda x: os.path.join(dashboard_dir,
                                              os.path.dirname(x)),
                       relative_dashboard_filenames)))
    for dirname in dirnames:
        if not os.path.exists(dirname):
            os.makedirs(dirname)
    for filename in relative_dashboard_filenames:
        source = os.path.join(DASHBOARD_DIR, filename)
        outfilename = filename
        if indexfile is not 'index.html':
            if filename == indexfile:
                outfilename = 'index.html'
            elif filename == 'index.html':
                outfilename = None
        if outfilename:
            dest = os.path.join(dashboard_dir, outfilename)

        if os.path.isfile(dest):
            # remove any existing files to ensure we use the latest
            os.remove(dest)
        shutil.copyfile(source, dest)

def update_dashboard_list(dashboard_dir, dashboard_id, dashboard_name):
    dashboards = []
    dashboard_filename = os.path.join(dashboard_dir, 'dashboard.json')
    if os.path.isfile(dashboard_filename):
        dashboards = json.loads(open(dashboard_filename).read())['dashboards']

    found_dashboard = False
    for dashboard in dashboards:
        if dashboard['id'] == dashboard_id:
            dashboard['name'] = dashboard_name
            found_dashboard = True

    if not found_dashboard:
        dashboards.append({'id': dashboard_id, 'name': dashboard_name})

    with open(dashboard_filename, 'w') as f:
        f.write(json.dumps({'dashboards': dashboards}))

def update_dashboard_device_list(dashboard_dir, dashboard_id, device_id, branch_id,
                                 device_info):
    devices = {}

    device_dirname = os.path.join(dashboard_dir, dashboard_id)
    if not os.path.exists(device_dirname):
        os.makedirs(device_dirname)

    device_filename = os.path.join(device_dirname, 'devices.json')
    if os.path.isfile(device_filename):
        devices = json.loads(open(device_filename).read())['devices']

    branches = []
    if devices.get(device_id):
        branches = devices[device_id].get('branches', [])
    if branch_id not in branches:
        branches.append(branch_id)

    devices[device_id] = device_info
    devices[device_id]['branches'] = branches
    with open(device_filename, 'w') as f:
        f.write(json.dumps({'devices': devices}))

def update_dashboard_test_list(dashboard_dir, dashboard_id, device_id, branch_id, testinfo):
    testsdirname = os.path.join(dashboard_dir, dashboard_id, device_id, branch_id)
    if not os.path.exists(testsdirname):
        os.makedirs(testsdirname)

    tests = {}
    testsfilename = os.path.join(testsdirname, 'tests.json')
    if os.path.isfile(testsfilename):
        tests = json.loads(open(testsfilename).read())['tests']
    update_timestamp = time.time()
    tests[testinfo['key']] = {'shortDesc': testinfo['shortDesc'],
                              'defaultMeasureId': testinfo['defaultMeasure'],
                              'lastUpdated': update_timestamp}

    # update the test list for the dashboard
    with open(testsfilename, 'w') as f:
        f.write(json.dumps({
            'lastUpdated': update_timestamp,
            'tests': tests}))

def update_dashboard_testdata(dashboard_dir, dashboard_id, device_id,
                              branch_id, testinfo, productname, productdate,
                              datapoint, metadata):
    # get existing data
    fname = os.path.join(dashboard_dir, dashboard_id, device_id, branch_id,
                         '%s.json' % testinfo['key'])
    testdata = NestedDict()
    if os.path.isfile(fname):
        testdata.update(json.loads(open(fname).read()))

    # need to initialize dict for product if not there already
    if not testdata['testdata'].get(productname):
        testdata['testdata'][productname] = {}

    if not testdata['testdata'][productname].get(productdate):
        testdata['testdata'][productname][productdate] = []

    # Add datapoint
    testdata['testdata'][productname][productdate].append(datapoint)

    # write new testdata to disk
    open(fname, 'w').write(json.dumps(testdata))

    # Write metadata
    open(os.path.join(dashboard_dir, 'metadata',
                      '%s.json' % datapoint['uuid']),
         'w').write(json.dumps(metadata))

def upload_dashboard(options):
    print 'Uploading dashboard to %s' % options.dashboard_server
    subprocess.check_call([
        'rsync', '-avz', '--bwlimit=1280', '--copy-links', '-e', 'ssh', options.dashboard_dir,
            '%s@%s:%s' % (options.dashboard_user, options.dashboard_server,
                          options.dashboard_remote_path)])
