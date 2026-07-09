# Phase A.1 受控真实页面模型评测

`evaluate-pages` 只处理 `--pages` 明确列出的 PDF 实际页码。每页单独渲染为 PNG，
并将该页 PNG、PyMuPDF 提取后的脱敏文本和任务级 Prompt 一并发送给外部 Qwen 服务。
命令必须由已获授权的用户手动执行，并显式传入 `--confirm-external-processing`。

样例材料的建议人工评测范围如下；这些页码仅用于本评测示例，不属于通用业务规则：

| PDF 实际页码 | 任务类型 | 材料 |
| ---: | --- | --- |
| 5 | `bid_letter` | 投标函 |
| 6 | `bid_appendix` | 投标函附录 |
| 8 | `authorization` | 授权委托书 |
| 19 | `guarantee` | 保证金缴款证明 |
| 25 | `personnel_table` | 项目负责人及项目组成员表 |
| 36 | `social_security` | 养老保险缴纳证明 |

页面任务默认根据当前页本地文本判断，无法可靠判断时不会调用模型。此时可使用
`--task-map "5:bid_letter,6:bid_appendix"` 显式指定，支持的任务类型即上表六类。

人员表可使用专用轻量策略。它采用独立读取超时、受最长边和字节数约束的 JPEG，
只提取姓名、角色、职称、证书级别、证书编号和专业。超时重试必须显式传入
`--retry-timeout-failures`，最多一次；重试图像更小且 Prompt 更精简。
`--personnel-table-strategy auto` 仅在整页结果成功但证书列明显不完整时读取上下两个
裁剪块。裁剪区域和每次尝试的尺寸、体积、耗时均写入 `llm_calls.jsonl`。

发送给模型的原始页面 PNG 仅在调用期间暂存，调用结束即删除。`pages/` 中保留的是脱敏
审计预览：文本层敏感号码会被遮盖；在不安装 OCR 的约束下，无法证明安全的嵌入图片区域
会被保守遮盖。需要视觉核验这些区域时，应回到受控环境中的原始 PDF。

```bash
cd "/home/dzr/桌面/研一下/实习/软件所数分实习/工作/项目15:港区审计需求/backend"

/home/dzr/miniconda3/bin/python -m app.cli.main evaluate-pages \
  --input "../samples/中和刚大工程顾问有限公司(1)(1).pdf" \
  --pages "5,6,8,19,25,36" \
  --output "../outputs/zhgd_page_eval" \
  --provider qwen \
  --confirm-external-processing

/home/dzr/miniconda3/bin/python -m app.cli.main inspect-page-evaluation \
  --input "../outputs/zhgd_page_eval"
```

第 25 页人员表的单页重试示例：

```bash
/home/dzr/miniconda3/bin/python -m app.cli.main evaluate-pages \
  --input "../samples/中和刚大工程顾问有限公司(1)(1).pdf" \
  --pages "25" \
  --task-type personnel_table \
  --retry-timeout-failures \
  --personnel-table-strategy auto \
  --output "../outputs/zhgd_page_eval_personnel_retry" \
  --provider qwen \
  --confirm-external-processing
```

缺少确认参数时命令会显示外部处理提醒，以非零状态退出，不加载模型配置、不渲染页面，
也不创建输出目录。普通测试只注入 Mock Provider，不会产生外部请求。
