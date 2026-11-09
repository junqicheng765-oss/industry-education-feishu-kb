#!/usr/bin/env python3
"""Read-only Wiki placement verification; never proves content/index completion."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess


class CheckError(Exception):
    pass


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def verify(manifest, config, get_node):
    space = config.get('space_id')
    root = manifest.get('catalog_root_node_token')
    if not nonempty(space) or manifest.get('space_id') != space:
        raise CheckError('manifest_space_mismatch')
    if root not in config.get('catalog_roots', {}).values():
        raise CheckError('unknown_catalog_root')
    items = manifest.get('items')
    if not isinstance(items, list) or not items:
        raise CheckError('empty_items')
    required = ('node_token', 'expected_parent_node_token', 'expected_title', 'expected_obj_type')
    if any(not isinstance(i, dict) or any(not nonempty(i.get(k)) for k in required) for i in items):
        raise CheckError('incomplete_expected_placement')
    if len({i['node_token'] for i in items}) != len(items):
        raise CheckError('duplicate_items')
    cache = {}

    def node(token):
        if token not in cache:
            n = get_node(token)
            if not isinstance(n, dict) or n.get('node_token') != token or n.get('space_id') != space:
                raise CheckError('node_identity_or_space_mismatch')
            if 'parent_node_token' not in n or not isinstance(n['parent_node_token'], str):
                raise CheckError('unknown_parent')
            cache[token] = n
        return cache[token]

    if node(root)['parent_node_token']:
        raise CheckError('catalog_root_is_not_top_level')
    results = []
    for item in items:
        token = item['node_token']
        try:
            n = node(token)
            reasons = []
            parent = n['parent_node_token']
            if not parent:
                reasons.append('material_at_space_root')
            if parent != item['expected_parent_node_token']:
                reasons.append('parent_mismatch')
            if n.get('title') != item['expected_title']:
                reasons.append('title_mismatch')
            if n.get('obj_type') != item['expected_obj_type']:
                reasons.append('object_type_mismatch')
            # Walk actual ancestry, including invisible/missing parents as failures.
            ancestor, seen = parent, {token}
            while ancestor and ancestor != root:
                if ancestor in seen or len(seen) >= 64:
                    raise CheckError('invalid_ancestor_chain')
                seen.add(ancestor)
                ancestor = node(ancestor)['parent_node_token']
            if ancestor != root:
                reasons.append('outside_expected_catalog')
            results.append({'node_token': token, 'passed': not reasons,
                            'actual_parent_node_token': parent, 'reasons': reasons})
        except CheckError as exc:
            results.append({'node_token': token, 'passed': False, 'reasons': [str(exc)]})
    return {'placement_verified': all(r['passed'] for r in results), 'items': results,
            'content_verified': False, 'index_verified': False, 'remote_writes': 0}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', required=True)
    p.add_argument('--team-config', required=True)
    p.add_argument('--profile', default='industry-education')
    p.add_argument('--cli', default='lark-cli')
    args = p.parse_args()
    try:
        config = json.loads(Path(args.team_config).read_text(encoding='utf-8'))
        manifest = json.loads(Path(args.manifest).read_text(encoding='utf-8'))
        if not isinstance(config, dict) or not isinstance(manifest, dict):
            raise CheckError('invalid_json_object')
        if not nonempty(args.profile) or not args.profile[0].isalnum():
            raise CheckError('invalid_profile')
        cli = shutil.which(args.cli)
        if not cli:
            raise CheckError('cli_not_found')

        def get_node(token):
            if not token.isalnum():
                raise CheckError('expected_raw_node_token')
            try:
                proc = subprocess.run([cli, '--profile', args.profile, 'wiki', '+node-get',
                                       '--node-token', token, '--space-id', config['space_id'],
                                       '--as', 'user'], capture_output=True, text=True, timeout=45)
            except subprocess.TimeoutExpired:
                raise CheckError('read_timeout') from None
            try:
                data = json.loads(proc.stdout)
            except ValueError:
                raise CheckError('unrecognized_cli_response') from None
            if proc.returncode or not isinstance(data, dict) or data.get('ok') is not True:
                raise CheckError('node_read_failed_check_access_or_cli')
            if data.get('identity') != 'user':
                raise CheckError('unexpected_identity')
            return data.get('data')

        result = verify(manifest, config, get_node)
    except (OSError, ValueError, KeyError, CheckError) as exc:
        # Do not echo raw CLI output, account details, file contents or credentials.
        result = {'placement_verified': False,
                  'error': str(exc) if isinstance(exc, CheckError) else type(exc).__name__,
                  'content_verified': False, 'index_verified': False, 'remote_writes': 0}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['placement_verified'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
