CREATE TABLE IF NOT EXISTS help_documents (
    id TEXT PRIMARY KEY,
    published JSONB,
    draft JSONB,
    revision INTEGER NOT NULL DEFAULT 0,
    archived BOOLEAN NOT NULL DEFAULT FALSE,
    updated_by_name TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    published_by_name TEXT NOT NULL DEFAULT '',
    published_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS help_document_events (
    id BIGSERIAL PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES help_documents(id),
    action TEXT NOT NULL,
    revision INTEGER NOT NULL,
    actor JSONB NOT NULL,
    content JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_help_document_events_document ON help_document_events(document_id, id DESC);

INSERT INTO help_documents(id,published,published_by_name,published_at) VALUES
('getting-started', $json${"title":"第一次使用，从这里开始","category":"新手上手","summary":"先了解账号能做什么，再按自己的任务找到操作入口。","tags":["新手","账号","菜单","权限"],"attachments":[],"body":"## 1. 登录并确认当前账号\n登录后先确认右上角的账号身份。如果系统要求修改初始密码，请先完成修改。页面和可见数据由角色、个人授权及站点或片区绑定共同决定。\n## 2. 按当前任务找到入口\n- 录入检查发现：进入巡检系统的巡检登记。\n- 查找已录入的问题：进入巡检问题列表，设置条件后点击开始筛选。\n- 确认检查完成或签名验收：进入巡检记录。\n- 站点办理整改：进入我的待整改问题。\n- 督导组办理复核：进入我的待复核问题。\n- 查看申诉进度：进入申诉空间。\n## 3. 不确定下一步怎么办\n查看问题的流转记录，确认当前状态、上一环节意见和待处理事项，再选择相应操作。\n> 菜单或按钮不可用不一定是故障，可能与账号权限、数据范围或当前流程状态有关。请联系管理员核实，不要借用他人账号。\n## 4. 需要帮助或反馈\n先在帮助文档中搜索任务关键词；仍无法解决时，可在公共功能的系统反馈中说明操作位置、步骤和现象，并附上截图。"}$json$::jsonb,'系统预置',CURRENT_TIMESTAMP),
('inspection-workflow', $json${"title":"巡检登记与问题流转","category":"巡检登记","summary":"了解登记问题、选择规范、检查确认与签名验收的衔接方式。","tags":["巡检登记","规范ID","巡检记录","审核","验收"],"attachments":["inspection-workflow"],"body":"## 登记检查发现\n1. 在巡检登记中核实站点、检查日期等信息。\n2. 填写实际问题描述，上传问题照片，并人工选择或使用AI辅助引用规范。\n3. 需要引用多条规范时可多选；系统会按各条规范分别生成独立的问题记录。提交前检查规范与描述是否对应。\n4. 如果本次为亮点登记，请切换亮点登记选项，填写亮点信息。亮点进入独立的亮点列表，不进入问题整改流程。\n## 完成确认与审核\n在巡检记录中按实际进度完成检查确认，之后由有权账号审核问题。审核被否决的问题不再要求站点整改。记录是否可继续新增、是否已封存，应以页面显示的状态和提示为准。\n## 站点签名验收\n相关检查表的问题审核完成后，站点在巡检记录中查看并签名验收；通过审核并完成验收的问题进入站点待整改。\n## 查看下一步和处理依据\n进入问题的流转记录，可以查看审核、验收、整改、复核与申诉等事件；处理被退回的问题前，先查看退回原因。\n> 下方流程图按上传原件保留。照片要求、自动验收与时限规则可能调整，请以当前系统配置和实际页面为准。"}$json$::jsonb,'系统预置',CURRENT_TIMESTAMP),
('rectification-review', $json${"title":"站点如何整改，督导组如何复核","category":"整改复核","summary":"区分已整改、站级无法整改，以及被退回后的下一轮处理。","tags":["待整改","待复核","退回","照片","已闭环"],"attachments":[],"body":"## 站点提交整改\n1. 在我的待整改问题中找到对应问题，点击提交整改。\n2. 根据实际情况选择已整改或站级无法整改，并按页面要求填写说明及上传照片。\n3. 提交后问题进入待复核，等待督导组处理。\n## 督导组提交复核\n站点选择已整改时，督导组可选择整改通过或整改不通过。整改通过后为已闭环；整改不通过会退回站点继续整改，复核照片可选。\n站点选择站级无法整改时，复核选项为通过站级无法整改或驳回站级无法整改。通过后问题状态为站级无法整改；驳回后回到待整改。该分支不需要复核照片。\n## 被退回后重新处理\n先在退回提醒或流转记录中查看原因。重新提交整改时，本轮结果、说明及照片需要重新填写，历史轮次仍可追溯。\n> 申诉驳回和督导组复核退回不是同一个事件，请按提醒中的实际原因处理。"}$json$::jsonb,'系统预置',CURRENT_TIMESTAMP),
('issue-appeal-workflow', $json${"title":"对问题有异议时如何申诉","category":"问题申诉","summary":"从站点发起申诉到片区初审、质安部终审，了解适用条件与结果处理。","tags":["申诉空间","申诉时限","片区初审","质安部终审","站点角色"],"attachments":["issue-appeal-workflow"],"body":"## 先确认能否申诉\n申诉仅适用于计量稽查检查表（视频、现场）、环境无异味管理检查表（现场）、质量安全环保检查表（视频、现场）这五张检查表的问题。站点只能对自己站点已验收、审核通过且待整改的问题发起申诉。同一问题只能参加一次申诉流程。\n## 站点发起申诉\n1. 在我的待整改问题中找到问题，点击发起申诉。\n2. 填写必填的申诉理由，核对后提交。\n3. 提交后问题转入申诉空间，暂时离开待整改列表。\n## 片区与质安部审核\n所属片区先进行初审。初审通过后，交由获得终审权限的质安部账号处理；任一环节驳回，问题回到站点继续整改。终审通过后，问题已销毁，无需继续整改。\n## 查看进度和时限\n进入申诉空间查看当前处理环节、审核意见及结果；完整过程也会进入问题流转记录。\n> 验收、申诉申请、片区审核和质安部审核的开关、时限及超时处理由Root配置。下方原图中的时间用于说明，实际应以当前页面的倒计时和系统配置为准。"}$json$::jsonb,'系统预置',CURRENT_TIMESTAMP)
ON CONFLICT(id) DO NOTHING;
