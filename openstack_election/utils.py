# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import datetime
import json
import os
import pickle
import pytz
import re
import requests
import subprocess
import time
import urllib
import yaml

# Per election constants

SERIES_NAME = 'ocata'
# 2015-09-05 00:00:00 +0000
PERIOD_START = datetime.datetime(2015, 9, 5, 0, 0, 0, tzinfo=pytz.utc)
# 2016-09-04 23:59:59 +0000
PERIOD_END = datetime.datetime(2016, 9, 4, 23, 59, 59, tzinfo=pytz.utc)
PROJECTS_TAG = 'sept-2016-elections'

# Library constants
CANDIDATE_PATH = 'candidates'
GERRIT_BASE = 'https://review.openstack.org'
ELECTION_REPO = 'openstack/election'
CGIT_URL = 'https://git.openstack.org/cgit'
PROJECTS_URL = ('%s/openstack/governance/plain/reference/projects.yaml' %
                (CGIT_URL))

PAST_ELECTIONS = ['ocata']

conf = yaml.load(open('configuration.yaml'))
exceptions = None


# Generic functions
def load_exceptions():
    global exceptions
    exceptions = {}
    for e in open("exceptions.txt").readlines():
        if e[0] == "#" or ":" not in e:
            continue
        exceptions[e.split(':')[0]] = " ".join(e.split(':')[1:])[:-1].strip()


def get_event(event_name):
    for e in conf['timelines']:
        if e['name'] == event_name:
            d = datetime.datetime.strptime(e['date'], "%Y-%m-%dT%H:%M")
            return d.replace(tzinfo=pytz.utc)
    raise ValueError("Couldn't find event_name %s" % event_name)


# Gerrit functions
def gerrit_datetime(dt):
    return dt.strftime('%Y-%m-%d %H:%M:%S %z')


def gerrit_query(url):
    r = requests.get(url)
    if r.status_code == 200:
        data = json.loads(r.text[4:])
    else:
        data = []
    return data


def get_email(filepath):
    cmd = ["git", "log", "--follow", "--format=%aE", filepath]
    git = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    return git.stdout.readlines()[-1][:-1]


def get_fullname(filepath):
    # Check if filepath is an exception
    if exceptions is None:
        load_exceptions()
    if filepath in exceptions:
        return exceptions[filepath]

    # Otherwise query gerrit using git log email
    email = get_email(filepath)
    url = '%s/accounts/%s' % (GERRIT_BASE, email)
    fullname = gerrit_query(url)['name']

    # Remove parenthesis content
    fullname = re.sub(r"\([^)]*\)", "", fullname)
    # Strip double space and trailing spaces
    fullname = re.sub(r"  ", " ", fullname).strip()

    # Make sure first letter of first and last component are upper-case
    s = fullname.split()
    fullname = (
        [s[0][0].upper() + s[0][1:]] +
        s[1:-1] +
        [s[-1][0].upper() + s[-1][1:]]
    )
    return u" ".join(fullname)


def get_reviews(query):
    opts = ['CURRENT_REVISION', 'CURRENT_FILES', 'DETAILED_ACCOUNTS']
    opts_str = '&o=%s' % ('&o='.join(opts))
    url = ('%s/changes/?q=%s%s' %
           (GERRIT_BASE, urllib.quote_plus(query, safe='/:=><^.*'), opts_str))
    return gerrit_query(url)


def candidate_files(review):
    return list(filter(lambda x: x.startswith(CANDIDATE_PATH),
                       list(review['revisions'].values())[0]['files'].keys()))


# Governance functions
def check_atc_date(atc):
    if 'expires-in' not in atc:
        return False
    expires_in = datetime.datetime.strptime(atc['expires-in'], '%B %Y')
    expires_in = expires_in.replace(tzinfo=pytz.utc)
    return PERIOD_END < expires_in


def get_projects(tag=None):
    url = PROJECTS_URL
    cache_file = '.projects.pkl'

    if tag:
        url += '?%s' % tag
        cache_file = '.projects.%s.pkl' % tag

    # Refresh the cache if it's not there or if it's older than a week
    if (not os.path.isfile(cache_file) or
            os.stat(cache_file).st_size < 100 or
            os.stat(cache_file).st_mtime + (7*24*3600) < time.time()):
        print("[+] Updating %s" % (cache_file))
        data = yaml.safe_load(urllib.urlopen(url).read())
        pickle.dump(data, open(cache_file, "w"))

    return pickle.load(open(cache_file))


# Election functions
def name2dir(name):
    """Convert project name to directory name: only [a-zA-Z_] in camelcase"""
    name = name.replace(' ', '_').replace('-', '_')
    return "_".join(map(lambda x: x[0].upper()+x[1:], name.split('_')))


def dir2name(name, projects):
    """Convert directory name to original project name"""
    name = name.replace('_', '').lower()
    for project_name in projects:
        pname = project_name.lower().replace(' ', '').replace('-', '').lower()
        if name == pname:
            return project_name
    raise ValueError(('%s does not match any project' % (name)))


def build_candidates_list(election=SERIES_NAME):
    project_list = os.listdir(os.path.join(CANDIDATE_PATH, election))
    project_list.sort()
    candidates_lists = {}
    for project in project_list:
        project_prefix = os.path.join(CANDIDATE_PATH, election, project)
        file_list = filter(
            lambda x: x.endswith(".txt"),
            os.listdir(unicode(project_prefix)),
        )
        candidates_list = []
        for candidate_file in file_list:
            filepath = os.path.join(project_prefix, candidate_file)
            candidates_list.append(
                {
                    'url': ('%s/%s/plain/%s' %
                            (CGIT_URL, ELECTION_REPO,
                             urllib.quote_plus(filepath, safe='/'))),
                    'ircname': candidate_file[:-4].replace('`', r'\`'),
                    'email': get_email(filepath),
                    'fullname': get_fullname(filepath)
                })

        candidates_list.sort(key=lambda x: x['fullname'])
        candidates_lists[project] = candidates_list

    return {'election': election,
            'projects': project_list,
            'candidates': candidates_lists}
