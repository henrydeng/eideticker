# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import time

from marionette import By
from marionette import Wait
from marionette import expected


class GaiaCompat():

    def __init__(self):
        version_file = os.path.join(os.path.dirname(__file__),
                                    'gaia_compat_version.txt')
        self.version = 'master'
        if os.path.isfile(version_file):
            with open(version_file) as f:
                self.version = f.readline().strip() or 'master'
        print 'Gaia compatibility version: %s' % self.version

    def supress_update_check(self, marionette):
        if not self.version == '1.3':
            # gaiatest v1.3 does not currently have the FakeUpdateChecker
            from gaiatest import FakeUpdateChecker
            FakeUpdateChecker(marionette).check_updates()

    def wait_for_b2g(self, marionette, timeout=60):
        if self.version == '1.3':
            marionette.execute_script("""
window.addEventListener('mozbrowserloadend', function loaded(aEvent) {
  if (/ftu|homescreen/.test(aEvent.target.src)) {
    window.removeEventListener('mozbrowserloadend', loaded);
    window.wrappedJSObject.b2g_ready = true;
  }
});""", new_sandbox=False)
            Wait(marionette, timeout).until(lambda m: m.execute_script(
                'return window.wrappedJSObject.b2g_ready;', new_sandbox=False))
            time.sleep(5)
        else:
            Wait(marionette, timeout).until(expected.element_present(
                By.CSS_SELECTOR, '#homescreen[loading-state=false]'))
