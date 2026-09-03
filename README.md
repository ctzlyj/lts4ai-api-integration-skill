# LTS4AI API Integration Skill

让 Codex 自动把 LTS4AI 的模型接入网站、后端、CLI 或其他应用。

这个 Skill 适合不会编程的使用者。你只需要把下面提供的文字复制给 Codex，Codex 会识别项目使用的技术、选择合适的 API 调用方式、编写代码并补充测试。

## 它能做什么

- 通过 `https://api.lts4ai.com/v1` 接入 LTS4AI。
- 使用 OpenAI 兼容的 Responses、Chat Completions、图片、Embedding 和音频接口。
- 根据你选择的模型完成接入，不偷偷替换模型。
- 从 LTS4AI 动态读取可用模型，避免把未来模型写死在代码里。
- 把真实 API Token 保存在服务端，不暴露给网页浏览器或客户端用户。
- 在真正调用付费模型前，先完成模拟测试和只读检查。

## 第一步：让 Codex 安装 Skill

打开 Codex，新建一个任务，把下面整段文字复制发送：

```text
请使用 $skill-installer，从下面的 GitHub 地址安装 Skill：
https://github.com/ctzlyj/lts4ai-api-integration-skill/tree/main/skills/lts4ai-api-integration

安装完成后告诉我。现在不要修改我的项目，也不要发送任何付费 AI 请求。
```

Codex 回复安装完成后，再发送下一条消息。新安装的 Skill 通常会在下一轮消息中生效。

## 第二步：准备 API Token

1. 打开 [LTS4AI](https://api.lts4ai.com) 并登录。
2. 在控制台创建一个供当前应用使用的 Token。
3. **不要把 Token 发到聊天、群聊、截图、GitHub 或公开文档里。**

把下面这段话复制给 Codex：

```text
请使用 $lts4ai-api-integration，为当前项目准备 LTS4AI 的服务端环境变量配置：

LTS4AI_BASE_URL=https://api.lts4ai.com/v1
LTS4AI_API_KEY=

请确保密钥文件不会被 Git 提交，也不会进入浏览器代码。不要读取、打印或回显我的真实 Token。准备好以后，只告诉我应该在哪个文件或部署平台的哪个 Secret 输入框中手工粘贴 Token。
```

这是整套流程中唯一必须由你亲自完成的安全步骤：按照 Codex 的提示，把 Token 粘贴进本地密钥文件或网站托管平台的 Secret 输入框。粘贴后不要把 Token 再发给 Codex。

## 第三步：不知道选哪个模型时

完成 Token 配置后，把下面这段话复制给 Codex：

```text
请使用 $lts4ai-api-integration，只读获取当前 Token 可用的 LTS4AI 模型列表，并按文本、图片、Embedding、音频分类展示给我选择。不要调用任何模型，不要产生付费请求。
```

看到列表后，记下你想使用的完整模型 ID。模型 ID 中如果有 `/`，必须完整保留。

## 第四步：让 Codex 自动接入

把下面文字中的 `完整模型ID`、`功能说明` 替换成你的实际需求，然后复制给 Codex：

```text
请使用 $lts4ai-api-integration，把模型“完整模型ID”接入当前打开的项目，用来实现“功能说明”。

要求：
1. 先读取项目说明和现有代码，沿用当前技术栈，不要重写整个项目。
2. API Token 只能保存在服务端环境变量中，浏览器和客户端不能接触真实 Token。
3. 使用我指定的完整模型 ID，不要自动替换成其他模型。
4. 如果网页允许用户选择模型，请从 LTS4AI 动态读取，并在服务端校验允许的模型。
5. 添加与改动范围匹配的测试，先使用模拟响应测试。
6. 暂时不要部署，不要提交，不要推送，也不要发送付费 AI 请求。
7. 完成后用小白能看懂的话告诉我：改了什么、怎么验证、还需要我做什么。
```

示例：

```text
请使用 $lts4ai-api-integration，把模型“openai/gpt-5.6-terra”接入当前打开的网站，用来实现客服聊天。先完成代码和模拟测试，不要部署，也不要发送付费 AI 请求。
```

## 第五步：让 Codex 检查结果

复制发送：

```text
请检查刚才的 LTS4AI 接入：运行相关测试和构建，并执行只读健康检查与模型可用性检查。检查浏览器代码、日志、Git 暂存区和配置示例中是否意外包含真实 Token。不要发送付费 AI 请求，不要部署。
```

## 第六步：需要真实调用时

只有在代码、测试和只读检查都通过后，才发送明确授权。真实请求会消耗 LTS4AI 余额。

```text
我授权你只对模型“完整模型ID”执行 1 次最小真实请求，用于验证接入。限制输出长度，不要重试付费请求。完成后只报告状态、模型、Token 用量和扣费结果，不要输出任何密钥或完整敏感内容。
```

这条授权只适用于这一模型和这一次验证，不代表允许部署、提交或推送。

## 第七步：需要发布时

确认本地验证通过后，再单独发送：

```text
请先告诉我本次发布会修改什么、发布到哪里、需要哪些环境变量和回滚方式。等我确认后再部署，现在先不要执行部署。
```

确认 Codex 给出的范围没有问题后，再明确回复“部署”。

## 常见问题

### 我可以把 Token 直接发给 Codex 吗？

不建议。Token 应由你亲自粘贴到本地密钥文件或部署平台的 Secret 输入框。不要发在聊天消息中。

### 网页能直接调用 LTS4AI 吗？

网页可以调用你自己网站的后端接口，但不能携带真实 LTS4AI Token 直接调用上游。否则访问网页的人可能窃取 Token 并消耗你的余额。

### 为什么不能一开始就真实测试？

真实模型调用可能产生费用。Skill 会先做代码测试、模拟响应、健康检查和模型列表检查，最后才在你明确同意后执行一次最小真实请求。

### 模型会自动更新吗？

Skill 要求应用从 LTS4AI 动态读取可用模型，不把不断变化的模型目录写死。但应用仍应设置服务端允许列表，避免用户随意调用不希望开放的高成本模型。

## 仓库结构

```text
skills/lts4ai-api-integration/
├── SKILL.md
├── agents/openai.yaml
├── references/api-contract.md
├── references/integration-recipes.md
└── scripts/check_lts4ai.py
```

## 安全说明

- 本仓库不包含任何 API Token、密码或生产环境配置。
- Skill 默认不会为了测试而发送付费推理请求。
- Skill 不会把 LTS4AI Token 放进浏览器或桌面客户端渲染进程。
- 提交、推送和部署仍需要使用者单独明确授权。
