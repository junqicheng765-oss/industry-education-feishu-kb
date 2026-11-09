#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Initialize all seven project pages, or check actual Wiki structure (user identity)."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

SCHEMA = json.loads((Path(__file__).resolve().parents[1] / 'assets/project-schema.json').read_text())


class Failure(Exception):
    pass


class Client:
    def __init__(self, cli, profile):
        self.cli, self.profile, self.writes = cli, profile, 0

    def call(self, args, write=False):
        try:
            proc = subprocess.run([self.cli, '--profile', self.profile] + args + ['--as', 'user'],
                                  capture_output=True, text=True, timeout=90)
            data = json.loads(proc.stdout)
        except (subprocess.TimeoutExpired, ValueError):
            raise Failure('response_unknown_query_current_state_before_retry') from None
        if proc.returncode or data.get('ok') is not True or data.get('identity') != 'user':
            raise Failure('cli_failed_check_personal_auth_access_and_current_state')
        if write:
            self.writes += 1
        return data['data']

    def node(self, token):
        n = self.call(['wiki', '+node-get', '--space-id', SCHEMA['space_id'], '--node-token', token])
        n = n.get('node', n)
        if n.get('space_id') != SCHEMA['space_id'] or n.get('node_token') != token:
            raise Failure('node_identity_or_space_mismatch')
        return n

    def children(self, token):
        data = self.call(['wiki', '+node-list', '--space-id', SCHEMA['space_id'],
                          '--parent-node-token', token, '--page-all', '--page-limit', '0'])
        return data.get('items', data.get('nodes', []))

    def fetch(self, token):
        return self.call(['docs', '+fetch', '--doc', token, '--doc-format', 'xml', '--detail', 'full'])['document']

    def copy(self, source, parent, title):
        # Wiki copy is NOT recursive. Read back by unique title even if a response is lost.
        self.call(['wiki', '+node-copy', '--space-id', SCHEMA['space_id'], '--node-token', source,
                   '--target-parent-node-token', parent, '--title', title, '--yes'], write=True)
        matches = [n for n in self.children(parent) if n['title'] == title]
        if len(matches) != 1:
            raise Failure('copy_result_not_unique_stop_and_reconcile')
        n = self.node(matches[0]['node_token'])
        if n.get('parent_node_token') != parent or n.get('obj_type') != 'docx':
            raise Failure('copied_node_placement_mismatch')
        return n


def root_xml(document):
    return ET.fromstring('<root>' + document['content'] + '</root>')


def values(document):
    return [''.join(x.itertext()).strip() for x in root_xml(document) if x.tag != 'title']


def check(client, token, recursive=True):
    errors, pending, sections, materials = [], [], [], []
    n = client.node(token)
    if n.get('parent_node_token') != SCHEMA['workspace'] or n.get('obj_type') != 'docx':
        errors.append('project_root_parent_or_type_mismatch')
    root_doc = client.fetch(token)
    text = values(root_doc)
    for field in SCHEMA['root_fields']:
        found = [v[len(field):].strip() for v in text if v.startswith(field)]
        if len(found) != 1 or not found[0]:
            errors.append('root_field_missing_or_duplicate:' + field)
        elif any(s in found[0] for s in ('待填', '待指派', '待确认', '未确认', '待核实')):
            pending.append(field + found[0])
    if '项目模板版本：v' + SCHEMA['version'] not in text:
        errors.append('template_version_mismatch')
    direct = client.children(token)
    expected = {s['title'] for s in SCHEMA['sections']}
    for item in direct:
        if item['title'] not in expected:
            errors.append('unclassified_direct_child:' + item['title'])
    seen = {token}

    def descendants(parent):
        for item in client.children(parent):
            actual = client.node(item['node_token'])
            if item['node_token'] in seen:
                raise Failure('cycle_or_duplicate_node')
            seen.add(item['node_token'])
            if actual.get('parent_node_token') != parent or actual.get('obj_type') != 'docx':
                errors.append('material_parent_or_type_mismatch:' + item['node_token'])
                continue
            if actual.get('has_child') or client.children(item['node_token']):
                descendants(item['node_token'])
            else:
                doc = root_xml(client.fetch(item['node_token']))
                sources = len(list(doc.iter('source')))
                if not sources:
                    errors.append('material_leaf_without_original_attachment:' + item['node_token'])
                materials.append({'node_token': item['node_token'], 'source_attachments': sources})

    for spec in SCHEMA['sections']:
        matches = [n for n in direct if n['title'] == spec['title']]
        if len(matches) != 1:
            errors.append('section_missing_or_duplicate:' + spec['title'])
            continue
        section = client.node(matches[0]['node_token'])
        if section.get('parent_node_token') != token or section.get('obj_type') != 'docx':
            errors.append('section_parent_or_type_mismatch:' + spec['title'])
            continue
        doc = client.fetch(section['node_token'])
        section_text = values(doc)
        for field in SCHEMA['section_fields']:
            fields = [v[len(field):].strip() for v in section_text if v.startswith(field)]
            if len(fields) != 1 or not fields[0]:
                errors.append('section_field_missing_or_duplicate:' + spec['title'] + ':' + field)
        if '模板，未填写' in doc['content'] or '待实际项目资料补充。不要在此模板' in doc['content']:
            errors.append('unfilled_template:' + spec['title'])
        for v in section_text:
            if v.startswith(('负责人：', '内容状态：')) and any(s in v for s in ('待指派', '待补', '待业务', '未确认')):
                pending.append(spec['title'] + '/' + v)
        sections.append({'title': spec['title'], 'node_token': section['node_token']})
        if recursive:
            descendants(section['node_token'])
    return {'structure_passed': not errors, 'errors': errors, 'business_pending': pending,
            'business_ready': False, 'business_approval_verified': False,
            'sections': sections, 'materials': materials,
            'original_binary_hashes_verified': False,
            'note': 'Mechanical structure check only; business approval and attachment hashes require separate evidence.',
            'remote_writes': client.writes}


def initialize(client, args):
    # Required online reads, including all source pages, happen before any mutation.
    client.fetch(SCHEMA['entry'])
    template = client.node(SCHEMA['template'])
    if template.get('parent_node_token') != SCHEMA['workspace']:
        raise Failure('template_moved_review_schema_before_writing')
    template_doc = client.fetch(SCHEMA['template'])
    if '项目模板版本：v' + SCHEMA['version'] not in values(template_doc):
        raise Failure('online_template_version_mismatch_review_before_writing')
    template_children = client.children(SCHEMA['template'])
    for spec in SCHEMA['sections']:
        if not any(n['node_token'] == spec['template'] and n['title'] == spec['title'] for n in template_children):
            raise Failure('online_template_changed_review_schema_before_writing')
        client.fetch(spec['template'])
    token = args.project
    if not token:
        if not args.name:
            raise Failure('new_project_requires_name')
        matches = [n for n in client.children(SCHEMA['workspace']) if n['title'] == args.name]
        if len(matches) > 1:
            raise Failure('duplicate_project_names_reconcile_first')
        if matches:
            token = matches[0]['node_token']
        elif args.apply:
            token = client.copy(SCHEMA['template'], SCHEMA['workspace'], args.name)['node_token']
    if token:
        actual = client.node(token)
        if token == SCHEMA['template'] or actual.get('parent_node_token') != SCHEMA['workspace']:
            raise Failure('project_must_be_direct_child_of_project_workspace')
    existing = client.children(token) if token else []
    plan = []
    for spec in SCHEMA['sections']:
        matches = [n for n in existing if n['title'] == spec['title']]
        if len(matches) > 1:
            raise Failure('duplicate_section_reconcile_first')
        if not matches:
            plan.append(spec)
    for spec in plan:
        if args.apply:
            client.copy(spec['template'], token, spec['title'])
    return {'project': token, 'pages_to_create': [s['title'] for s in plan],
            'applied': args.apply, 'remote_writes': client.writes,
            'next': 'Fill the project and seven pages using references/projects.md, then run check. Copied placeholders cannot pass.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['init', 'check'])
    parser.add_argument('--project', help='Raw Wiki node token of an existing project')
    parser.add_argument('--name', help='Unique name when initializing a new project')
    parser.add_argument('--apply', action='store_true', help='Execute the authorized initialization plan')
    parser.add_argument('--profile', default='industry-education')
    parser.add_argument('--cli', default='lark-cli')
    parser.add_argument('--structure-only', action='store_true', help='Skip descendant attachment checks')
    args = parser.parse_args()
    result = None
    try:
        cli = shutil.which(args.cli)
        if not cli:
            raise Failure('cli_not_found')
        if args.project and not args.project.isalnum():
            raise Failure('use_raw_wiki_node_token')
        client = Client(cli, args.profile)
        if args.action == 'init':
            result = initialize(client, args)
        else:
            if not args.project:
                raise Failure('check_requires_project')
            client.fetch(SCHEMA['entry'])
            result = check(client, args.project, not args.structure_only)
    except (Failure, OSError, KeyError, ET.ParseError) as exc:
        result = {'structure_passed': False, 'error': str(exc) if isinstance(exc, Failure) else type(exc).__name__,
                  'remote_writes': client.writes if 'client' in locals() else 0}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result.get('error') or result.get('structure_passed') is False else 0


if __name__ == '__main__':
    raise SystemExit(main())
