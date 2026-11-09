# 产教融合飞书知识库 Agent Skill

为团队内部出方案、产品资料查询、材料入库和项目协作提供统一规则。当前 **Skill v0.1.4 / 接入工具 v1.4 / 项目模板 v1.0**。

这是团队的 GitHub 分发和更新入口。飞书固定 README 及其指定的现行规则仍是执行时必须读取的线上依据；本地文件不替代业务确认或访问授权。本仓库按所有者明确要求公开，可直接浏览、克隆和下载，无需先申请 GitHub 仓库访问权限。

仓库包含经所有者授权公开的团队知识库入口、空间/节点ID和应用App ID等非凭据配置；实际飞书资料仍受本人OAuth、应用范围和知识库权限约束。这里没有App Secret、个人Token或业务原件。维护Skill默认建议不公开实际团队配置，本仓库的公开授权只适用于这一套非凭据配置，不推广到其他空间或敏感资料。

## 直接交给同事的 Agent

同事无需登录 GitHub 即可读取本仓库或使用 HTTPS 克隆。将下面这段话发给 Agent 即可：

```text
请从 https://github.com/junqicheng765-oss/industry-education-feishu-kb 获取或更新产教融合知识库 Skill，并配置到当前项目。

如果本机已有该仓库，先检查未提交修改，再 git pull --ff-only；不要覆盖本机修改。如果尚未获取，把仓库克隆到一个长期保留的目录。

先读仓库 README.md、给Agent的启动指令.md、workspace.team.json，再按接入与使用指南.md执行。已有可用的飞书CLI应用配置和本人OAuth直接复用；缺失才分步配置。复用指定应用，每个人使用自己的飞书账号授权；需要我操作时一次只给一个动作。

通过只读检查后，使用 scripts/configure_agent.py --instructions 当前项目实际指令文件 --apply 更新项目启动约定，保留其他内容。已有接入包只替换知识库标记区中的路径，指向本仓库，避免继续加载旧包。

项目创建和材料整理必须读取 skills/industry-education-feishu-kb/references/projects.md，按七个栏目归位并运行结构检查。完成后报告本次Git提交、Skill版本、个人连接、项目指令及未完成项。不要输出或提交App Secret、个人Token和认证日志。
```

获取公开仓库不需要管理员邀请。提交仓库修改仍需要GitHub写权限；读取或写入飞书知识库仍须分别完成本人授权及内容权限核验。

## 获取与更新

首次获取（在自己选择的长期目录中运行）：

```bash
git clone https://github.com/junqicheng765-oss/industry-education-feishu-kb.git
cd industry-education-feishu-kb
```

已有GitHub CLI的成员也可以使用 `gh repo clone junqicheng765-oss/industry-education-feishu-kb`。

后续在仓库目录更新：

```bash
git status --short
git pull --ff-only
git rev-parse HEAD
```

若有本地修改，先比较、保存和处理，不能用 `reset --hard`、强制覆盖或删除工作目录来更新。更新仓库不等于所有运行中的 Agent 已加载新内容；下一次任务重新读取启动说明和 Skill。若原来指向 ZIP 解压目录，需运行下方安装命令把当前项目指向仓库。

需要固定版本时，使用 [Releases](https://github.com/junqicheng765-oss/industry-education-feishu-kb/releases) 中的版本标签或 ZIP；固定版本不会自动获得新版本。跟踪 `main` 的成员仍须执行更新，没有配置后台自动更新任务。

## 安装到当前项目

在本仓库根目录，由 Agent 将路径替换为当前项目真实指令文件：

```bash
# 预览，仅本地读取
python3 scripts/configure_agent.py --instructions /实际项目路径/AGENTS.md

# 已获当前项目接入授权后应用，只更新知识库标记区
python3 scripts/configure_agent.py --instructions /实际项目路径/AGENTS.md --apply

# 已有个人飞书连接时做只读自检
python3 scripts/check_connection.py --profile industry-education
```

Claude Code 可以使用实际项目的 `CLAUDE.md`；其他 Agent 按其指令机制加载。包内 Skill 的位置是 `skills/industry-education-feishu-kb/SKILL.md`。不假定所有工具都能自动发现同一目录，也不强制改动全局配置。仓库移动后重新安装项目启动约定。

尚无飞书连接时，先按 [给 Agent 的启动指令](给Agent的启动指令.md) 引导应用配置和本人 OAuth；不要把只安装 Skill、只写项目指令当作已接入。App Secret 由管理员单独交付并在本机交互终端隐藏输入，不存入仓库。

## 包含的能力

- 六类业务知识库的归属、来源、版本、状态、查重和冲突处理。
- 飞书在线正文与文内原件的入库、首件验收及位置检查。
- 项目七栏目初始化与结构检查；业务缺口明确列出，不能把模板空页当已完成。
- 共享现有应用、每人独立 OAuth、个人身份显式读写和项目指令安装。

结构检查、连接检查和业务审批分别验收。直接 CLI/API 仍可能绕过 Agent 流程；本仓库没有部署统一写入服务、并发写锁或自动调度，也不会自动升级其他成员电脑。

## 目录与维护

| 路径 | 用途 |
|---|---|
| `skills/industry-education-feishu-kb/` | 当前维护 Skill、模板、引用规则和检查脚本 |
| `给Agent的启动指令.md` | Agent 首次接入及日常任务入口 |
| `接入与使用指南.md` | 安装、应用配置、本人授权、排障和使用说明 |
| `workspace.team.json` | 团队非凭据配置；不授予权限 |
| `scripts/` | 应用配置、只读自检和项目指令安装工具 |
| `SKILL-SOURCE.json` | 本版本 Skill 文件哈希，供分发核验 |
| `VERIFICATION.json` | 发布时的验证范围和限制 |

维护者在唯一维护源中修改后同步到本仓库，更新版本及 `SKILL-SOURCE.json`，验证后提交并发布版本。成员使用仓库更新，业务材料写入飞书，不在个人副本中维护另一套团队规则。历史 Release 保留用于复核和回退；不要在普通 Git 文件或提交历史中保存凭据、认证日志、原始合同或客户材料。
