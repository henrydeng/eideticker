from setuptools import setup, find_packages
setup(
    name="eideticker",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        'mozdevice==0.45', 'mozlog==2.11', 'mozprofile==0.24',
        'moznetwork==0.26', 'mozhttpd==0.7', 'mozrunner==6.7',
        'gaiatest==0.32', 'b2gpopulate==0.27', 'marionette_client==0.8.5',
        'httplib2', 'BeautifulSoup',
        'requests>=2.2.1', 'futures >= 2.1.6', 'treeherder-client == 1.1'])

# (FIXME: templeton needs to be installed manually now, it constantly causes
# problems)
# FIXME: Compile decklink-capture script automatically
