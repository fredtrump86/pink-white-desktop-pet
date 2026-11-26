# 粉白桌宠

我的第一个 Vibe Coding 作品：一款以 AI 辅助编码完成的 Windows Q 版桌宠，让角色通过鼠标互动、随机动作和对话气泡，提供轻量的桌面陪伴。

应用在本地运行，无需部署服务器；打包版无需安装 Python。

[项目源码](https://github.com/fredtrump86/pink-white-desktop-pet) · [版本与下载](https://github.com/fredtrump86/pink-white-desktop-pet/releases) · [自动构建进度](https://github.com/fredtrump86/pink-white-desktop-pet/actions)

## 运行效果

以下为应用实际运行时的演示截图。

| 眨眼互动 | 挥手问候 | 休息陪伴 |
| :---: | :---: | :---: |
| <img src="assets/screenshots/wink.jpg" width="220" alt="桌宠眨眼并显示今天也要开心呀的气泡"> | <img src="assets/screenshots/wave.jpg" width="220" alt="桌宠挥手并显示问候气泡"> | <img src="assets/screenshots/rest.jpg" width="220" alt="桌宠休息并提醒不要熬夜"> |

| 右键设置菜单 | 安静看书 |
| :---: | :---: |
| <img src="assets/screenshots/menu.jpg" width="280" alt="桌宠右键菜单，可设置尺寸、置顶、自动动作和开机启动"> | <img src="assets/screenshots/reading.jpg" width="220" alt="桌宠看书并显示安静陪伴模式开启"> |

## 下载使用

面向 Windows 用户，现有安装包按 x64 兼容环境配置；macOS 和 Linux 不在当前支持范围内。

请从仓库的 [Releases 页面](https://github.com/fredtrump86/pink-white-desktop-pet/releases)下载以下任一文件。首次自动构建完成后会生成下载附件；构建进度可在 Actions 页面查看。

| 文件 | 使用方式 |
| --- | --- |
| `pink-white-desktop-pet.exe` | 便携版，下载后双击运行 |
| `pink-white-desktop-pet-setup.exe` | 安装版，提供开始菜单、可选桌面快捷方式和卸载程序 |

两种版本均已打包运行所需的 Python 环境、依赖和角色素材，不需要另行下载图片。安装版默认安装到当前用户的本地应用目录，不要求管理员权限。

**Code → Download ZIP 下载的是源码。** 如果只想使用桌宠，请下载 Release 附件中的 EXE。

## 已实现功能

- 透明无边框窗口与始终置顶
- 鼠标拖拽并记忆上次位置
- 单击眨眼互动，双击开心挥手
- 鼠标悬停约 350ms 后，随机挥手、眨眼或害羞；可打断看书和休息，快速划过不触发
- 待机、挥手、眨眼、睡觉、伸懒腰、打哈欠、思考、加油、害羞、看书、喝水共 11 种独立角色状态
- 角色固定显示，保持稳定的桌面位置
- 启动后随机等待 15～25 秒执行首次主动动作；之后每个动作结束再待机 20～40 秒
- 未互动不足 10 分钟时，从除看书、休息外的 8 个动作中均匀选择（每个 12.5%）
- 未互动达到 10 分钟后，只在看书、休息中均匀选择（各 50%），两个动作均持续 30 分钟
- 自动调度使用 500ms 心跳检查，右键可查看已主动活动次数与下次触发倒计时
- 点击、悬停和手动动作会重置调度，当前动作结束后再等待 20～40 秒；拖动结束或重新显示角色后也会重新等待
- 粉白圆角对话气泡与主动台词
- 右键菜单与系统托盘菜单
- 小、中、大三档尺寸，默认高度 280 像素并保持角色原始比例
- 可选开机启动
- 单实例保护

## 操作方式

| 操作 | 效果 |
| --- | --- |
| 左键单击 | 眨眼互动 |
| 左键双击 | 开心挥手 |
| 左键拖拽 | 移动桌宠，结束后保存位置 |
| 鼠标悬停 | 随机挥手、眨眼或害羞，可打断看书和休息 |
| 鼠标滚轮 | 调整大小 |
| 右键 → 更多动作 | 手动选择动作 |
| 右键 → 自动动作 | 启用或关闭、立即测试、查看触发状态 |
| 系统托盘菜单 | 显示或隐藏、切换动作、设置或退出 |

隐藏桌宠后，气泡也会隐藏；可以通过系统托盘重新显示。

## 从想法到实现

最初的目标是让喜欢的角色出现在桌面上，可以拖动，并在学习或工作时提供一点陪伴。围绕这个目标，项目逐步完善了以下几个方面。以下按实现层次介绍，不作为逐次提交的版本记录。

### 1. 建立可以操作的原型

使用 Tkinter 实现透明无边框、始终置顶的窗口，结合 Pillow 加载角色素材，并加入鼠标拖动与位置记忆。先让角色能显示、能移动，再继续丰富行为。

### 2. 让角色理解不同的操作

加入点击、双击和悬停互动后，需要区分用户的操作意图。通过单击延迟判定、双击取消单击、拖动位移阈值，以及悬停等待和冷却机制，处理操作之间的触发冲突。鼠标快速划过不会立即触发互动，已有动作也不会被悬停随意打断。

### 3. 为主动陪伴设计节奏

将角色扩展为 11 种状态，集中管理动作时长和台词。自动动作采用随机等待，并在当前动作结束后安排下一次触发；未互动达到 10 分钟时转为看书或休息，在存在感与专注空间之间作出取舍。

行为逻辑区分用户操作与自动动作：只有用户操作才更新最后互动时间，避免桌宠自己的活动干扰休息判断。

### 4. 为异常提供恢复路径

自动调度使用心跳检查，并加入看门狗、拖动状态超时恢复、动作截止时间和异常日志。托盘线程通过队列提交操作，由 GUI 主线程更新界面。相关机制用于处理回调异常和过期状态，不代替对 GUI 主线程阻塞问题的排查。

### 5. 让修改可以验证，让作品可以交付

将界面、行为、配置和素材处理拆分到不同模块。行为模块可传入时钟和随机源，测试可以直接模拟长时间未互动，无需真实等待。项目提供单元测试、资源自检和窗口冒烟验证入口，并通过 PyInstaller 与 Inno Setup 生成便携版及安装包。

## 技术与目录

| 技术 | 用途 |
| --- | --- |
| Python / Tkinter | 窗口、鼠标事件和定时回调 |
| Pillow | 角色裁剪、缩放、透明通道与图标处理 |
| pystray | Windows 系统托盘 |
| unittest | 行为、配置和素材测试 |
| PyInstaller / Inno Setup | EXE 打包与安装包制作 |

```text
app.py                         命令行入口与诊断选项
desktop_pet/
  application.py               窗口、交互、调度与托盘
  behavior.py                  行为选择、动作时长与互动计时
  config.py                    配置校验与 UTF-8 持久化
  resources.py                 素材加载、渲染与图标生成
  diagnostics.py               无窗口资源与配置自检
  single_instance.py           Windows 单实例保护
  startup.py                   当前用户的开机启动设置
assets/
  characters/                  11 张透明角色状态图
  source/                      保留的原始色底素材
  screenshots/                 实际运行演示截图
  app.ico                      应用图标
tests/                         自动测试
installer/                     安装器中文语言文件与对应许可说明
desktop_pet.spec               PyInstaller 打包配置
installer.iss                  Inno Setup 安装配置
build.ps1                      构建脚本
requirements.txt               Python 依赖
.github/workflows/release.yml   Windows 自动测试、打包与发布
```

`.venv/`、`build/` 和 `dist/` 是本地产物，不提交到源码仓库。运行配置默认存储在 `%LOCALAPPDATA%/粉白桌宠/settings.json`，运行异常日志位于同目录下的 `runtime.log`。

## 从源码运行

当前开发环境使用 Python 3.11。以下 PowerShell 命令均在项目根目录执行，无需激活虚拟环境。

首次运行，先创建环境并安装依赖：

```powershell
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
python -m venv .venv
& ".venv/Scripts/python.exe" -m pip install -r "requirements.txt"
```

启动桌宠：

```powershell
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
& ".venv/Scripts/python.exe" "app.py"
```

## 验证与检查

单元测试覆盖行为选择、互动计时、调度恢复、悬停规则、配置读写及素材渲染。无窗口自检额外检查角色素材、透明通道、中文配置往返与动作映射。

```powershell
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
& ".venv/Scripts/python.exe" -B -m unittest discover -s tests -v
& ".venv/Scripts/python.exe" -B "app.py" --check
```

需要验证实际窗口时，可依次执行以下命令。每项会短暂启动桌宠并自动退出，请先退出已经运行的桌宠。

```powershell
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
& ".venv/Scripts/python.exe" -B "app.py" --smoke-window
& ".venv/Scripts/python.exe" -B "app.py" --smoke-interactions
& ".venv/Scripts/python.exe" -B "app.py" --smoke-auto
& ".venv/Scripts/python.exe" -B "app.py" --smoke-hover
```

其中自动动作检查模拟拖动释放后的调度恢复；悬停检查直接调用动作逻辑，不代替真实鼠标操作验收。

## 打包 EXE

先完成依赖安装和自动检查，再在项目根目录运行构建脚本。生成安装包还需要安装 Inno Setup 6；脚本会检查当前用户及系统的常见安装位置，未找到时仅生成便携版。

```powershell
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
& "./build.ps1"
```

构建产物：

- `dist/粉白桌宠.exe`：无需安装的便携版
- `dist/粉白桌宠安装包.exe`：可直接发送给朋友的标准 Windows 安装包

构建脚本会先执行资源自检并重新生成图标，再构建 EXE。完整单元测试需按上节单独执行。

### GitHub 自动发布

仓库提供 `.github/workflows/release.yml`，在 Windows 运行器上完成依赖安装、单元测试、EXE 与安装包构建，以及打包后的资源自检。

- 在 `main` 分支修改发布工作流或 `installer.iss` 时自动触发；也可以在 Actions 页面选择工作流并点击 **Run workflow** 手动执行。
- 版本号读取自 `installer.iss` 的 `MyAppVersion`，对应标签为 `v版本号`。发布新版时先更新该版本号。
- 同版本已公开发布时跳过构建，保留已有附件；本工作流创建的同版本草稿可在失败后重新构建并恢复，其他草稿会停止并提示检查。
- 两个 EXE 和 `SHA256SUMS.txt` 先上传到发布草稿，确认附件名称、状态与大小均正确后再公开发布。
- Release 使用英文附件名避免中文名称在上传时冲突；本地构建仍保留中文 EXE 名称。
- 自动检查不代替真实桌面交互及安装、卸载验收。

## 替换人物形象

将 `assets/characters/` 中对应文件替换为同名的透明背景 PNG：

| 状态 | 文件名 |
| --- | --- |
| 待机 / 挥手 / 眨眼 | `idle.png` / `wave.png` / `wink.png` |
| 睡觉 / 伸懒腰 / 打哈欠 | `sleep.png` / `stretch.png` / `yawn.png` |
| 思考 / 加油 / 害羞 | `think.png` / `cheer.png` / `shy.png` |
| 看书 / 喝水 | `read.png` / `drink.png` |

程序会按透明区域裁剪并等比缩放。各状态的人物比例和位置应尽量一致，以减小切换时的视觉跳变。只替换待机图时，其他动作仍会显示旧人物。

源码运行需重启才能加载新素材；EXE 将素材打包在内部，更换形象后需要重新构建。当前使用独立状态图片切换，尚未实现逐帧动画或运行时换肤。

## GitHub 发布清单

1. 将源码、`assets/`、`tests/`、依赖与构建配置、安装器语言文件及本 README 提交到仓库；保留 `installer/ChineseSimplified.LICENSE.txt`。
2. 使用 `.gitignore` 排除虚拟环境、构建产物、本地工具配置、环境变量文件和日志。不要直接把整个工作目录作为 ZIP 上传。
3. 在发布说明中写明支持的 Windows 环境、已验证的功能和已知限制。当前安装脚本版本号为 `0.2.0`，发布标签应与实际构建版本一致。
4. 创建 Release，把 `dist/粉白桌宠.exe` 和 `dist/粉白桌宠安装包.exe` 作为附件上传。源码仓库不跟踪 `dist/`。
5. 发布后更新本文顶部的发布状态，并补上实际 Release 下载链接。
6. 在没有 Python 开发环境的 Windows 电脑上验证下载、运行、安装与卸载，记录验证结果。

当前尚未附项目级开源许可证；发布前需由项目作者选定，并补充角色参考图和素材的来源与授权说明。安装器语言文件自带的许可说明单独保留。
