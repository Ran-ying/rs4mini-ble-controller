# 原生面板和网页共用格式

`neutral-velocity.json` 是全中位速度轨迹。载入不自动执行，需在现场点击执行；执行前会停止已有运动，结束也发送停止。
`research-observe.json` 只选择 RS 3 研究配置并观察已有通知；`research-version.json` 为实验版本查询。
实验配置不代表 RS 4 Mini 已支持，不要批量重放其他设备的抓包或校准命令。

速度轨迹是至少两个关键帧的数组，timeMs 从零开始、严格递增，各轴为 -1..1；省略轴归零。
网页可选 linear/smoothstep/step，原生界面载入使用 smoothstep。

关节路点数组格式：`[{"pan":实际起点,"holdMs":500},{"pan":实际小幅目标}]`。
用界面的“当前角度”功能生成真实起点后再修改；不要把示意角度当作当前姿态。
路点是逐点低速到位、停止、停留，不是定时连续角度轨迹。

实验 JSON 对象必须有 profile（rs3 或 rs3mini）及 command。
command 为 observe、query、sleep，或 rs3 配置下的 absolute、rate；完整参数见 `../../node/API.md`。
原生面板的实验查询独占操作槽；Node/Python/Web SDK 的限定查询可与运动并行。
