#!/usr/bin/env python3
"""Configure the approved existing Feishu app. Run --apply in the member's terminal."""
import argparse
import getpass
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import warnings

PACKAGE = Path(__file__).resolve().parents[1]


class SetupError(Exception):
    pass


def call(cli, args, secret=None):
    env = dict(os.environ, LARKSUITE_CLI_NO_UPDATE_NOTIFIER='1',
               LARKSUITE_CLI_NO_SKILLS_NOTIFIER='1')
    try:
        return subprocess.run([cli, *args], input=secret, capture_output=True,
                              text=True, encoding='utf-8', errors='replace',
                              timeout=60, env=env)
    except (OSError, subprocess.TimeoutExpired):
        raise SetupError('CLI执行失败或超时；检查安装与网络。原始输出已隐藏。')


def profiles(cli):
    p = call(cli, ['profile', 'list'])
    if p.returncode:
        raise SetupError('无法读取已有profile；保留现场，由Agent检查CLI帮助，不继续写入。')
    try:
        data = json.loads(p.stdout)
        if isinstance(data, dict):
            data = data.get('data', data)
            if isinstance(data, dict):
                data = data.get('profiles')
        if not isinstance(data, list) or any(not isinstance(x, dict) or
                not isinstance(x.get('name'), str) or not isinstance(x.get('appId'), str)
                for x in data):
            raise ValueError()
        return data
    except (ValueError, TypeError):
        raise SetupError('profile列表格式与已验证版本不同；不猜测、不覆盖，由Agent检查当前CLI。')


def setup(args):
    cfg = json.loads(Path(args.config).read_text(encoding='utf-8'))
    target = cfg['connector']['app_id']
    profile = args.profile or cfg['connector']['profile']
    cli = args.cli or shutil.which('lark-cli')
    if not cli or not Path(cli).is_file():
        raise SetupError('未找到lark-cli；先安装或用--cli指定可执行文件。')
    before = profiles(cli)
    existing = next((x for x in before if x['name'] == profile), None)
    if existing:
        if existing['appId'] != target:
            raise SetupError('同名profile属于其他应用，已保留；请Agent选择空闲profile并显式传--profile。')
        return {'ok': True, 'profile': profile, 'app_id': target,
                'status': 'existing_application_configuration', 'credentials_written': False,
                'next': '继续本人OAuth检查及只读验证；本结果仅核对App ID，不证明密钥有效或本人已授权。'}
    report = {'ok': True, 'profile': profile, 'app_id': target,
              'status': 'ready_for_hidden_secret_input' if args.apply else 'preview',
              'credentials_written': False,
              'next': '请成员在自己的交互终端运行本脚本并加--apply，隐藏输入管理员提供的App Secret。'}
    if not args.apply:
        return report
    if not sys.stdin.isatty():
        raise SetupError('需要成员自己的交互终端；禁止把密钥作为命令参数或通过Agent工具输入。')
    help_result = call(cli, ['config', 'init', '--help'])
    if help_result.returncode or not all(flag in help_result.stdout for flag in
                                         ['--app-secret-stdin', '--app-id', '--name']):
        raise SetupError('当前CLI不支持预期的安全配置参数；请Agent检查版本与帮助。')
    print('正在配置管理员指定的现有应用；不会新建飞书应用。')
    print('App ID：' + target + '；profile：' + profile)
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        try:
            secret = getpass.getpass('请粘贴管理员提供的App Secret（输入不可见），再按回车：')
        except (getpass.GetPassWarning, EOFError):
            raise SetupError('终端无法安全隐藏输入，已停止；请换用本机交互终端。')
    if not secret or any(ch.isspace() for ch in secret):
        raise SetupError('密钥为空或包含空白；未写入，请重新运行。')
    # Recheck after human input so an intervening config is not blindly replaced.
    if any(x['name'] == profile for x in profiles(cli)):
        raise SetupError('输入期间目标profile已出现；未写入，请重新检查。')
    old_mask = os.umask(0o077)
    try:
        p = call(cli, ['config', 'init', '--name', profile, '--app-id', target,
                       '--app-secret-stdin', '--brand', 'feishu'], secret + '\n')
    finally:
        os.umask(old_mask)
        del secret
    if p.returncode:
        raise SetupError('应用配置未成功；原始输出已隐藏。请Agent检查CLI/宿主绑定策略；不要自动重试或加--force-init。')
    after = profiles(cli)
    saved = next((x for x in after if x['name'] == profile), None)
    if not saved or saved['appId'] != target:
        raise SetupError('配置返回后App ID核对未通过；请Agent检查，不重复覆盖。')
    stable_keys = ('name', 'appId', 'active')
    for previous in before:
        current = next((x for x in after if x['name'] == previous['name']), None)
        if not current or any(previous.get(k) != current.get(k) for k in stable_keys):
            raise SetupError('发现其他profile或默认选择变化；请Agent检查并报告，勿继续授权。')
    return {'ok': True, 'profile': profile, 'app_id': target, 'status': 'configured',
            'credentials_written': True,
            'next': '返回Agent回复“应用已配置”，由Agent发起本人OAuth链接和二维码；尚未验证密钥/API权限。'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default=str(PACKAGE / 'workspace.team.json'))
    parser.add_argument('--cli')
    parser.add_argument('--profile')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    try:
        result = setup(args)
    except KeyboardInterrupt:
        result = {'ok': False, 'status': 'cancelled', 'next': '用户已取消，未继续授权。'}
    except (SetupError, OSError, ValueError, KeyError) as exc:
        message = str(exc) if isinstance(exc, SetupError) else '本地配置无法读取；请Agent检查路径与格式。'
        result = {'ok': False, 'status': 'configuration_incomplete', 'next': message}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
