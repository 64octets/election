#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""Build candidates list
"""

import jinja2
import jinja2.environment
import os
import yaml

from openstack_election import utils


def render_template(template, data, **kwargs):
    template_dir = kwargs.get('template_dir', os.getcwd())
    loader = jinja2.FileSystemLoader(template_dir)
    env = jinja2.environment.Environment(trim_blocks=True, loader=loader)
    template = env.get_template(template)
    return template.render(data)


def render_list(list_type, candidates_list):
    output_file = os.path.join(utils.CANDIDATE_PATH, "%s.rst" % list_type)
    template_name = "%s.jinja" % list_type
    template_dir = os.path.join(".", "doc", "source", "_exts")
    with open(output_file, "w") as out:
        out.write(
            render_template(
                template_name,
                candidates_list,
                template_dir=template_dir
            ).encode('utf-8')
        )


def build_archive(serie, list_type):
    db_file = os.path.join(".", "doc", "source", serie, "%s.yaml" % list_type)
    if not os.path.isfile(db_file):
        return
    db = yaml.safe_load(open(db_file))
    # Check for appointed or incumbent footnote
    db['tags'] = {}
    for project in db['projects']:
        for candidate in db['candidates'][project]:
            if candidate['elected'] == 'TC-APPOINTED':
                db['tags']['TC-APPOINTED'] = True
            elif candidate['elected'] == 'INCUMBENT-PTL':
                db['tags']['INCUMBENT-PTL'] = True
    output = os.path.join(".", "doc", "source", serie, "%s.rst" % list_type)
    template_name = "%s_archive.jinja" % list_type
    template_dir = os.path.join(".", "doc", "source", "_exts")
    with open(output, "w") as out:
        out.write(
            render_template(
                template_name,
                db,
                template_dir=template_dir
            ).encode('utf-8')
        )
    return True


def build_lists(app):
    # Current candidates
    candidates_list = utils.build_candidates_list()
    render_list("ptl", candidates_list)
    render_list("tc", candidates_list)

    # Archived elections
    previous_toc = [
        ".. toctree::",
        "    :maxdepth: 1",
        "    :titlesonly:",
        ""
    ]
    for previous in utils.PAST_ELECTIONS:
        if build_archive(previous, "ptl"):
            previous_toc.append("    %s/ptl.rst" % previous)
        if build_archive(previous, "tc"):
            previous_toc.append("    %s/tc.rst" % previous)
    toc = os.path.join(".", "doc", "source", "archive_toc.rst")
    open(toc, "w").write("\n".join(previous_toc))


def setup(app):
    app.info('loading candidates extension')
    app.connect('builder-inited', build_lists)
