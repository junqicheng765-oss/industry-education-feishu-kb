#!/usr/bin/env python3
"""Read-only Feishu KB checks. Never copies credentials or prints raw CLI errors."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

PACKAGE = Path(__file__).resolve().parents[1]


class CheckError(Exception):
    def __init__(self, stage, detail):
        self.stage, self.detail = stage, detail


def run(cli, profile, args, stage):
    env = dict(os.environ, LARKSUITE_CLI_NO_UPDATE_NOTIFIER='1', LARKSUITE_CLI_NO_SKILLS_NOTIFIER='1')
    try:
        p = subprocess.run([cli, '--profile', profile, *args], capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=90, env=env)
    except subprocess.TimeoutExpired:
        raise CheckError(stage, {'kind': 'timeout', 'action': '检查网络及代理；本脚本未写入飞书。'})
    try:
        obj = json.loads(p.stdout if p.returncode == 0 else p.stderr)
    except (ValueError, TypeError):
        raise CheckError(stage, {'kind': 'unrecognized_cli_output', 'exit_code': p.returncode,
                                'action': '由Agent在本机检查CLI版本及帮助；不要转发原始认证输出。'})
    if p.returncode != 0 or obj.get('ok') is False:
        err = obj.get('error', {})
        scopes = err.get('missing_scopes', [])
        kind, subtype = str(err.get('type', 'cli_error'))[:80], str(err.get('subtype', ''))[:80]
        actions = {
            'not_configured': '应用未配置，不等同于本人未登录。运行configure_application.py预检，再由成员在终端隐藏输入共享应用密钥；不新建应用。',
            'missing_scope': '区分应用侧API权限未生效与本人OAuth缺scope；让Agent读取具体missing_scopes，应用侧由管理员处理，个人侧增量授权。',
            'unauthenticated': '应用配置后由本人完成OAuth；Agent展示链接及二维码，等待回复再继续。',
        }
        action = next((v for k, v in actions.items() if k in (kind, subtype)),
                      '按指南区分应用配置、个人授权、API scope和知识库内容权限；不回退bot。')
        raise CheckError(stage, {'kind': kind, 'subtype': subtype,
                                'exit_code': p.returncode,
                                'missing_scopes': scopes if isinstance(scopes, list) else [],
                                'action': action})
    return obj


def check(args):
    cfg = json.loads(Path(args.config).read_text(encoding='utf-8'))
    cli = args.cli or shutil.which('lark-cli')
    if not cli or not Path(cli).is_file():
        raise CheckError('cli', {'kind': 'cli_not_found', 'action': '先按指南安装官方lark-cli，或用--cli指定其实际路径。'})
    profile = args.profile or cfg['connector']['profile']
    report = {'package_version': cfg['package_version'], 'profile': profile,
              'identity_required': 'user', 'read_only': True, 'remote_writes': 0, 'checks': []}
    who = run(cli, profile, ['whoami', '--as', 'user'], 'application_and_identity')
    if cfg['connector'].get('app_id') and who.get('appId') != cfg['connector']['app_id']:
        raise CheckError('application', {'kind': 'app_id_mismatch', 'action': '核对团队指定App ID与当前profile；保留现有配置，不继续。'})
    if who.get('identity') != 'user' or who.get('available') is not True:
        raise CheckError('identity', {'kind': 'user_identity_unavailable', 'action': '应用配置与个人OAuth分开；完成本人授权后重新只读验证。'})
    # Fetch first: CLI can refresh an expired access token during a real API call.
    targets = {'entry': cfg['entry_url'], **cfg['rules'], 'products': cfg['product_overview_url']}
    if cfg.get('guide_url'):
        targets['guide'] = cfg['guide_url']
    for name, url in targets.items():
        result = run(cli, profile, ['docs', '+fetch', '--doc', url, '--doc-format', 'xml', '--detail', 'full', '--as', 'user'], name)
        doc = result.get('data', {}).get('document', {})
        if result.get('ok') is not True or result.get('identity') != 'user' or not doc.get('content'):
            raise CheckError(name, {'kind': 'unexpected_identity_or_empty_content'})
        report['checks'].append({'target': name, 'ok': True, 'revision_id': doc.get('revision_id')})
    who = run(cli, profile, ['whoami', '--as', 'user'], 'identity')
    if who.get('identity') != 'user' or who.get('available') is not True:
        raise CheckError('identity', {'kind': 'user_identity_unavailable'})
    # whoami is a management command; unlike API envelopes it has no top-level ok/data.
    report['identity_verified'] = True
    node = run(cli, profile, ['wiki', '+node-get', '--node-token', cfg['home_url'], '--space-id', cfg['space_id'], '--as', 'user'], 'space')
    if node.get('ok') is not True or node.get('identity') != 'user' or node.get('data', {}).get('space_id') != cfg['space_id']:
        raise CheckError('space', {'kind': 'space_mismatch'})
    roots = run(cli, profile, ['wiki', '+node-list', '--space-id', cfg['space_id'], '--page-all', '--as', 'user'], 'root_nodes')
    data = roots.get('data', {})
    if roots.get('ok') is not True or roots.get('identity') != 'user' or data.get('has_more') is not False:
        raise CheckError('root_nodes', {'kind': 'incomplete_root_listing'})
    known = {n['node_token'] for n in data.get('nodes', [])}
    report['root_nodes_visible'] = len(known)
    report['missing_configured_roots'] = [name for name, token in cfg['catalog_roots'].items() if token not in known]
    report['ok'] = not report['missing_configured_roots']
    report['limitations'] = ['只验证当前身份读取所列入口及根目录；未验证全库或受限内容覆盖。',
                             '未验证写权限、普通成员隔离、其他成员身份或并发保护；未执行写入。',
                             '连接成功不代表Agent已理解规则；须继续做指南中的产品查询练习。']
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default=str(PACKAGE / 'workspace.team.json'))
    parser.add_argument('--cli', help='Actual lark-cli executable path')
    parser.add_argument('--profile', help='Explicit personal profile override; never switches global default')
    args = parser.parse_args()
    try:
        report = check(args)
    except CheckError as e:
        print(json.dumps({'ok': False, 'stage': e.stage, 'detail': e.detail, 'remote_writes': 0}, ensure_ascii=False, indent=2))
        return 1
    except (OSError, ValueError, KeyError) as e:
        print(json.dumps({'ok': False, 'stage': 'local_config', 'kind': type(e).__name__, 'remote_writes': 0}, ensure_ascii=False))
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
