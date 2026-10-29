# 闲鱼商品重写与商品包导入工作流

## 目标

把候选商品的原始标题和文案加工为可审核的闲鱼商品内容，生成商品首图，并将结果导入 xianyu-control 的商品包新版本。

本工作流只负责内容加工和结果交接，不负责直接发布闲鱼商品、修改原商品资料或处理订单履约。

## 输入

至少需要：

- 原商品标题；
- 原商品文案。

建议同时提供：

- 来源商品 ID；
- 候选 ID；
- 原商品图片；
- 已核实的商品事实；
- 来源观测 ID；
- 原商品包的当前版本信息。

## 流程

### 1. 文案改写

先读取 `business/rules/xianyu-shop-operations.md`，再调用 skills/xianyu-copy-rewriter。提取商品身份、实际交付物、内容或功能、服务范围、使用门槛及重要限制，结合本店适用的经营规则生成：

- 重写后的商品标题；
- 重写后的商品描述；
- 必要的事实说明和人工复核项。

商品事实来自输入，本店交付与资料来源等说明来自经营规则或本次明确安排；不自动继承原卖家的安装、售后、更新或授权承诺。不得虚构品牌、销量、评价、资质、收益或效果承诺。价格、库存、运费和发布参数不由文案模型决定。

完整描述包含适用的“商品说明”。卖家审核事项独立保存，结构化结果中使用 `metadata.review_notes`（字符串数组），不写进买家可见的 `description`。关键事实或权利问题尚未解决时，保留草稿等待审核，不以附上声明视作已确认，也不继续生成首图或导入商品包。

### 2. 首图设计与生成

先调用 skills/xianyu-cover-designer，把重写结果转换为首图设计方案和完整生图提示词，再调用 skills/xianyu-image-generator 生成图片。

默认生成一张商品首图。首图应能让用户快速识别商品类型，避免伪造商品截图、平台认证、客户案例和无法证明的文字。生成后检查主体、裁切、清晰度、文字和水印。

### 3. 导入商品包

将重写结果和首图整理为 UTF-8 的 result JSON，使用 scripts/import_rewrite_to_control.py 提交到 control：

    python scripts/import_rewrite_to_control.py --result rewrite-result.json

脚本默认从项目根目录 .env 读取 CONTROL_BASE_URL 和 CONTROL_TOKEN，也可以用 --control-url 或 --token 临时覆盖。

脚本调用：

    POST /api/selection/candidates/{candidate_id}/package/import-rewrite

接口会创建商品包或新增商品包版本，更新标题、文案和图片，并继承当前商品包或来源商品的价格及发布参数。相同 rewrite_run_id 重复提交时返回已有版本，不重复创建。

## 结果格式

result JSON 至少包含：

    {
      "candidate_id": 123,
      "source_item_id": "来源商品ID",
      "title": "重写后的标题",
      "description": "重写后的文案",
      "rewrite_run_id": "本次处理唯一 ID",
      "images": [
        {
          "path": "首图文件路径",
          "kind": "generated_poster",
          "selected": true
        }
      ],
      "metadata": {
        "rewrite_model": "使用的文案模型",
        "image_model": "使用的图片模型"
      }
    }

图片使用 path 或 local_path 指定本地文件。脚本会上传图片并把返回的受保护素材地址写入商品包版本。

## 校验与人工确认

导入前确认：

1. 商品表述对应原始或已核实事实，交付等经营说明符合本店规则，未误继承原卖家承诺；
2. 首图与商品内容一致，没有无依据的宣传；
3. 图片文件存在且格式受支持；
4. candidate_id 与来源商品对应；
5. 价格和发布参数由 control 当前版本继承，必要时在商品包中人工修改；
6. 导入结果返回的 version_no、标题、文案和图片数量正确；
7. 使用门槛、服务边界和适用商品说明未遗漏，卖家审核备注未混入买家描述，影响商品真实性或权利的关键待确认事项已处理。

## 失败处理

- 文案改写失败：不生成首图，不导入商品包。
- 首图生成失败：保留文案结果，等待重新生成图片。
- 图片文件不存在或格式不支持：修复文件后重新执行导入。
- control 返回 4xx/5xx：不认为导入成功，保留 result JSON，核对接口错误后重试。
- 重试必须复用 rewrite_run_id，避免同一结果重复创建商品包版本。

## Control 触发

原商品图片由 control 的导入接口自动合并保留；rewrite 只需回传新生成的首图，不需要接收或再次回传原图。

xianyu-control 在“选品台 → 模板设置 → rewrite 提示词模板”中拼接完整首次输入和会话标题，codex-task-managers 使用 external 输入模式原样转交。输入包含 candidate_id、source_item_id、source_observation_id、原标题、原始描述及本次 rewrite_run_id，不传原商品图片。仅依据文字设计首图。执行时保留来源标识，实际运行生成和导入脚本。

任务管理服务负责启动 Codex，本项目负责执行内容加工和导入。启动地址、任务管理 token 和 control 回写 token 均从各自项目的 .env 提供。

Docker 任务在 /workspace 中执行，使用容器内的 python3，不使用 Windows .venv。导入脚本会将 .env 中的本机回环地址转换为 host.docker.internal；本机执行保持原地址。密钥由脚本读取，勿打印 .env 或 auth.json。每次任务的产物放在独立的 outputs/<source_item_id>/<rewrite_run_id>/ 目录。
