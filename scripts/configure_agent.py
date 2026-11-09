#!/usr/bin/env python3
"""Append the KB startup block to an explicitly selected local instructions file."""
import argparse
import json
from pathlib import Path
import sys

PACKAGE = Path(__file__).resolve().parents[1]
BEGIN = '<!-- industry-education-kb:start -->'
END = '<!-- industry-education-kb:end -->'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--instructions', required=True, help='Project instructions file selected by the user/Agent (AGENTS.md, CLAUDE.md, etc.)')
    p.add_argument('--profile', default='industry-education', help='Existing personal CLI profile; this does not create it')
    p.add_argument('--apply', action='store_true', help='Write the managed block; otherwise only preview')
    a = p.parse_args()
    dest = Path(a.instructions).expanduser().resolve()
    old = dest.read_text(encoding='utf-8') if dest.exists() else ''
    if (BEGIN in old) != (END in old) or old.count(BEGIN) > 1 or old.count(END) > 1:
        sys.exit('Existing managed block is malformed; preserve file and resolve manually.')
    block = '\n'.join([BEGIN, '## 产教融合飞书知识库',
        '只在处理产教融合知识库任务时加载以下约定，不影响其他项目。',
        '先读取本机启动说明：' + str(PACKAGE / '给Agent的启动指令.md'),
        '团队非凭据配置：' + str(PACKAGE / 'workspace.team.json'),
        '业务维护Skill：' + str(PACKAGE / 'skills/industry-education-feishu-kb/SKILL.md'),
        '每个新任务通过自己的飞书连接读取固定入口：https://lcngwcork9tw.feishu.cn/wiki/HRuKwDgTAiA0C7kbW1bcBW8KnGg',
        'CLI配置名：' + a.profile + '；API操作显式 --as user，不改全局默认身份，不回退bot。',
        '按线上规则查询或维护；任务授权、内容状态、来源及版本分别核对。无连接时按启动说明先完成接入。',
        '上传材料前读业务Skill的references/ingestion.md及线上入库规程：写为可读飞书在线文档，源文件作为文内附件；保存实际父节点清单，首件正文、附件SHA-256、位置及索引验收通过再批量。',
        '新建或整理项目时读业务Skill的references/projects.md及线上项目模板v1.0：逐一初始化七个栏目，材料归入栏目下，真实资料填写或列明缺口后运行project_workspace.py check；失败先修复，不报告项目整理完成。', END])
    if BEGIN in old:
        left, rest = old.split(BEGIN, 1)
        _, right = rest.split(END, 1)
        new = left + block + right
    else:
        new = old + ('\n\n' if old and not old.endswith('\n\n') else '') + block + '\n'
    result = {'instructions_file': str(dest), 'changed': new != old, 'applied': False,
              'credentials_written': False, 'cli_profile_created': False, 'remote_writes': 0}
    if a.apply and new != old:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(new, encoding='utf-8')
        result['applied'] = True
    if not a.apply:
        result['preview'] = block
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
