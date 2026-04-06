(function attachNotesSnapshotI18n(globalScope) {
  "use strict";

  const DEFAULT_LOCALE = "en";
  const ZH_CN_LOCALE = "zh-CN";
  const LOCALE_STORAGE_KEY = "notes_snapshot_web_locale";
  const SUPPORTED_LOCALES = Object.freeze([DEFAULT_LOCALE, ZH_CN_LOCALE]);
  const DISALLOWED_MERGE_KEYS = Object.freeze(["__proto__", "constructor", "prototype"]);

  const TRANSLATIONS = {
    en: {
      locale: {
        code: "en",
        label: "English",
        labelText: "Language",
        option: {
          en: "English",
          zhCN: "Simplified Chinese",
        },
      },
      meta: {
        productName: "Apple Notes Snapshot",
        controlRoomName: "Notes Snapshot Console",
        productSummary: "Local-first backup control room for Apple Notes on macOS.",
      },
      options: {
        logType: {
          stdout: "stdout",
          stderr: "stderr",
          launchd: "launchd",
          webui: "webui",
        },
        rotateScope: {
          all: "all",
          stdout: "stdout",
          stderr: "stderr",
          launchd: "launchd",
          webui: "webui",
          metrics: "metrics",
          structured: "structured",
        },
      },
      common: {
        unknown: "unknown",
        none: "none",
        yes: "yes",
        no: "no",
        ok: "ok",
        missing: "missing",
        manual: "manual",
        online: "online",
        offline: "offline",
        valueTail: "tail {count}",
        durationSeconds: "{count}s",
        durationMinuteSecond: "{minutes}m {seconds}s",
        durationHourMinute: "{hours}h {minutes}m",
        durationMinutes: "{count}m",
        rateLimitFormat: "{count} / {window}s",
        phaseDuration: "{name} ({duration})",
        phaseFallback: "phase",
        metricEventFallback: "event",
        streakFormat: "{status} x{count}",
        recoverabilityFormat: "Recoverability: {state}",
        statusWindowFormat: "Status window: {window}",
        loading: "Loading...",
        empty: "--",
        noOutputYet: "No output.",
      },
      pill: {
        ok: "OK",
        warn: "WARN",
        fail: "FAIL",
        degraded: "DEGRADED",
        onboarding: "ONBOARDING",
        readonly: "READONLY",
        active: "ACTIVE",
        locked: "LOCKED",
        ready: "ready",
        running: "running",
        idle: "idle",
        safe: "safe",
        tail: "tail",
        launchd: "launchd",
      },
      ui: {
        title: "Notes Snapshot Console",
        badgeLocal: "LOCAL",
        heroSummary: "Deterministic local Web console for Apple Notes exports, without requiring a bundled desktop app.",
        refresh: "Refresh",
        lastUpdate: "Last update",
        firstRunGuidance: "First-Run Guidance",
        snapshotStatus: "Snapshot Status",
        logHealth: "Log Health",
        doctor: "Doctor",
        recentMetrics: "Recent Metrics",
        recentRuns: "Recent Runs",
        accessPolicy: "Access Policy",
        quickActions: "Quick Actions",
        scheduler: "Scheduler",
        vendorSync: "Vendor Sync",
        logViewer: "Log Viewer",
        actionOutput: "Action Output",
        healthSummary: "Health Summary",
        stateLayers: "State Layers",
        healthReasonCodes: "Health Reason Codes",
        triggerSources: "Trigger Sources",
        effectiveActions: "Effective Actions",
        status: "Status",
        exitCode: "Exit Code",
        lastSuccess: "Last Success",
        lastRun: "Last Run",
        age: "Age",
        launchd: "Launchd",
        triggerSource: "Trigger Source",
        failureReason: "Failure Reason",
        healthScore: "Health Score",
        schema: "Schema",
        runId: "Run ID",
        interval: "Interval",
        totalErrors: "Total Errors",
        stdout: "Stdout",
        stderr: "Stderr",
        launchdErr: "Launchd Err",
        pattern: "Pattern",
        tailLines: "Tail Lines",
        tailConfig: "Tail Config",
        dependencies: "Dependencies",
        warnings: "Warnings",
        repoRoot: "Repo Root",
        vendorDir: "Vendor Dir",
        stateDir: "State Dir",
        pythonBin: "Python Binary",
        osascript: "AppleScript",
        launchctl: "launchctl",
        plutil: "plutil",
        timeoutBin: "Timeout Binary",
        runIdFilter: "Run ID Filter",
        recentRunsCount: "Recent Runs",
        successes: "Successes",
        failures: "Failures",
        latestStatus: "Latest Status",
        topFailure: "Top Failure",
        recentTrend: "Recent Trend",
        currentStreak: "Current Streak",
        runChangeSummary: "Run / Change Summary",
        failureClusters: "Failure Clusters",
        requireToken: "Require Token",
        staticToken: "Static Token",
        readonly: "Readonly",
        tokenScopes: "Token Scopes",
        actionsAllowlist: "Actions Allowlist",
        rateLimit: "Rate Limit",
        cooldowns: "Cooldowns",
        minutes: "Minutes",
        intervalSec: "Interval (sec)",
        loadAfterInstall: "Load after install",
        keepWebAlive: "Keep Web UI alive",
        install: "Install",
        ensure: "Ensure",
        unload: "Unload",
        vendorRef: "Ref (tag/branch/sha)",
        patchDryRun: "Patch dry-run",
        autoCommit: "Auto commit",
        updateVendor: "Update Vendor",
        logType: "Log Type",
        sinceMinutes: "Since Minutes",
        rotateScope: "Rotate Scope",
        fetchLogs: "Fetch Logs",
        rotateLogs: "Rotate Logs",
        perfectSetup: "Perfect Setup",
        runSnapshot: "Run Snapshot",
        verify: "Verify",
        fastFix: "Fast Fix",
        selfHeal: "Self Heal",
        permissions: "Permissions",
        placeholderOptional: "optional",
        placeholderVendorRef: "v1.3.0",
        placeholderRunIdContains: "run_id contains...",
      },
      emptyState: {
        metrics: "No metrics yet.",
        healthSummary: "Health summary not available yet.",
        doctorSummary: "Doctor summary not available yet.",
        noWarnings: "No warnings",
        noRecordedRuns: "No recorded runs yet.",
        noChangeSummary: "No run/change summary yet.",
        noFailureClusters: "No failure clusters in the recent window.",
        noActions: "No actions available",
        noIssues: "No issues detected",
        noActionsYet: "No actions yet.",
      },
      message: {
        apiUnavailable: "Unable to reach local API. If this persists, ensure Web UI server is running.",
        runningAction: "Running {action}...",
        actionFailed: "Action failed: {detail}",
        firstRunSummary: "Build one successful snapshot first, then treat the rest of the control room as ongoing operations.",
        firstRunHint: "Need the full checklist? Open the quickstart or the troubleshooting guide.",
        firstRunHintHtml:
          'Need the full checklist? Open the <a href="https://xiaojiou176-open.github.io/apple-notes-snapshot/quickstart/">quickstart</a> or the <a href="https://xiaojiou176-open.github.io/apple-notes-snapshot/troubleshooting/">troubleshooting guide</a>.',
        firstRunExplanation: "This is a normal first-run or cleaned-checkout state. Build one successful snapshot baseline before you read this as an active failure.",
        logHealthLastStatus: "last_status: {status}",
        outputOk: "OK",
        actionFileLabel: "file: {path}",
        unknownError: "unknown error",
        webActionSource: "web:{action}",
        accessTip: "Tip: use minimal scopes + allowlist (ex: scopes=read,run and actions=run) to shrink exposure.",
        bannerReadonly: "Readonly mode is active. Review access policy before you expect action buttons to change state.",
        bannerFailureCluster: "Recent runs still point to an active failure cluster: {reason}",
        bannerRecoveryWatch: "The latest run recovered, but keep watching the next run before you call the loop stable.",
        bannerStale: "The snapshot loop looks stale. Refresh it before you treat this as a deeper runtime incident.",
      },
      onboarding: {
        stepRun: "Run ./notesctl run --no-status so macOS can surface the first permission prompts.",
        stepVerify: "Run ./notesctl verify to confirm the local state ledger now has a successful baseline.",
        stepDoctor: "Run ./notesctl doctor if the state still looks empty or warnings remain.",
      },
      backend: {
        status: {
          success: "success",
          failed: "failed",
          aborted: "aborted",
          running: "running",
          unknown: "unknown",
        },
        healthLevel: {
          OK: "OK",
          WARN: "WARN",
          DEGRADED: "DEGRADED",
          FAIL: "FAIL",
          ONBOARDING: "ONBOARDING",
        },
        stateLayerStatus: {
          configured: "configured",
          loaded: "loaded",
          notLoaded: "not_loaded",
          unknown: "unknown",
          fresh: "fresh",
          stale: "stale",
          failed: "failed",
          runningWithoutSuccess: "running_without_success",
          needsFirstRun: "needs_first_run",
        },
        healthReason: {
          launchdNotLoaded: "launchd_not_loaded",
          lastRunFailed: "last_run_failed",
          running: "running",
          exitNonzero: "exit_nonzero",
          statusExitMismatch: "status_exit_mismatch",
          stale: "stale",
          unknownLastSuccess: "unknown_last_success",
          checksumMismatch: "checksum_mismatch",
          checksumMissing: "checksum_missing",
          logHealthErrors: "log_health_errors",
        },
        stateLayerLabel: {
          config: "Config Layer",
          launchd: "Launchd Live Layer",
          ledger: "Ledger Layer",
        },
        metricEvent: {
          runStart: "run start",
          runEnd: "run end",
        },
        healthSummary: {
          needsFirstRun: "Config and launchd look readable, but the ledger still needs the first successful snapshot baseline.",
          runningWithoutSuccess: "A snapshot run is active, but the ledger has not recorded a successful baseline yet.",
          stale: "A successful snapshot exists, but it is older than the freshness target.",
          failed: "The local ledger points to a failed run and still needs a successful recovery baseline.",
          launchdNotLoaded: "The local scheduler is not loaded right now, so the backup loop is not running on its own.",
          logHealthErrors: "Recent log health signals show runtime errors even though the control-room state surface is present.",
          healthy: "The current local backup surface looks healthy enough to keep using the deterministic tooling as the source of truth.",
        },
        stateLayerSummary: {
          configured: "Config surface resolved for root, state, logs, and interval.",
          launchdLoaded: "launchctl reports {label} is loaded.",
          launchdNotLoaded: "launchctl does not currently report {label} as loaded.",
          launchdUnknown: "launchctl state could not be determined.",
          ledgerFresh: "A successful snapshot is recorded in the local state ledger.",
          ledgerStale: "A successful snapshot exists, but it is older than the freshness threshold.",
          ledgerRunningWithoutSuccess: "A run is active, but the ledger has not recorded a successful snapshot yet.",
          ledgerFailed: "The ledger recorded a failed run and still has no successful snapshot.",
          ledgerNeedsFirstRun: "No successful snapshot is recorded yet. Run one manual snapshot to initialize the ledger.",
        },
        operatorSummary: {
          firstRun: "This looks like a first-run or cleaned-checkout baseline. Finish one successful manual snapshot before treating it as an active runtime failure.",
          launchdNotLoaded: "The scheduler is not currently loaded, so the backup loop is not running on its own.",
          stale: "A successful snapshot exists, but it is outside the freshness target.",
          failed: "The local state ledger points to a failed run and still needs a successful recovery baseline.",
          healthy: "The deterministic control-room surfaces are present; use warnings below to inspect any remaining gaps.",
        },
        warning: {
          noSuccessfulSnapshot: "no successful snapshot recorded yet; run ./notesctl run --no-status once to initialize the ledger",
          lastSuccessStale: "last success is stale ({ageSec}s > {thresholdSec}s)",
          launchdJobNotLoaded: "launchd job not loaded",
          webTokenRequired: "web token required but NOTES_SNAPSHOT_WEB_TOKEN is empty",
          webStaticTokenRequired: "web static token required but NOTES_SNAPSHOT_WEB_TOKEN is empty",
          remoteWithoutToken: "web allow remote without token requirement",
          remoteEmptyAllowlist: "web allow remote with empty allowlist",
        },
        changeTrend: {
          unknown: "unknown",
          noRuns: "no recent runs",
          singleSuccess: "single success",
          singleFailed: "single failure",
          recovered: "recovered",
          regressed: "regressed",
          steadySuccess: "steady success",
          steadyFailure: "steady failure",
          mixed: "mixed",
        },
        changeSummary: {
          noRuns: "No recent runs were available in the current window.",
          singleSuccess: "Only one recent run is available, and it ended with success.",
          singleFailed: "Only one recent run is available, and it ended with failed.",
          recovered: "The most recent run succeeded after earlier failures in the recent window.",
          regressed: "The most recent run failed after earlier successes in the recent window.",
          steadySuccess: "The recent window is steady: the last {count} run(s) all succeeded.",
          steadyFailure: "The recent window is unstable: the last {count} run(s) all failed.",
          mixed: "Recent runs show mixed or incomplete status signals.",
        },
        recoverability: {
          bootstrap: "bootstrap",
          recoverable: "recoverable",
          watchWindow: "watch window",
          stableMonitoring: "stable monitoring",
          manualReview: "manual review",
        },
        workflowHint: {
          bootstrap: "Initialize the first successful snapshot baseline before treating the control room as a live incident board.",
          failureCluster: "Treat the latest failure cluster as the first stop, then inspect status, log-health, and doctor in that order.",
          recoveryWatch: "The latest run recovered; verify freshness and watch the next run before declaring the loop stable.",
          stable: "Stay in watch mode; no immediate recovery action is required unless freshness or warnings change.",
          mixed: "Use recent-run trend and state layers together before choosing the next operator action.",
        },
      },
    },
    "zh-CN": {
      locale: {
        code: "zh-CN",
        label: "简体中文",
        labelText: "语言",
        option: {
          en: "English",
          zhCN: "简体中文",
        },
      },
      meta: {
        productName: "Apple Notes Snapshot",
        controlRoomName: "Notes Snapshot 控制台",
        productSummary: "面向 macOS Apple Notes 的本地优先备份控制室。",
      },
      options: {
        logType: {
          stdout: "标准输出",
          stderr: "标准错误",
          launchd: "launchd",
          webui: "webui",
        },
        rotateScope: {
          all: "全部",
          stdout: "标准输出",
          stderr: "标准错误",
          launchd: "launchd",
          webui: "webui",
          metrics: "metrics",
          structured: "structured",
        },
      },
      common: {
        unknown: "未知",
        none: "无",
        yes: "是",
        no: "否",
        ok: "正常",
        missing: "缺失",
        manual: "手动",
        online: "在线",
        offline: "离线",
        valueTail: "尾部 {count}",
        durationSeconds: "{count}秒",
        durationMinuteSecond: "{minutes}分 {seconds}秒",
        durationHourMinute: "{hours}小时 {minutes}分",
        durationMinutes: "{count} 分钟",
        rateLimitFormat: "{count} 次 / {window} 秒",
        phaseDuration: "{name}（{duration}）",
        phaseFallback: "阶段",
        metricEventFallback: "事件",
        streakFormat: "{status} × {count}",
        recoverabilityFormat: "可恢复性：{state}",
        statusWindowFormat: "状态窗口：{window}",
        loading: "加载中...",
        empty: "--",
        noOutputYet: "暂无输出。",
      },
      pill: {
        ok: "正常",
        warn: "警告",
        fail: "失败",
        degraded: "降级",
        onboarding: "初始引导",
        readonly: "只读",
        active: "已启用",
        locked: "锁定",
        ready: "就绪",
        running: "运行中",
        idle: "空闲",
        safe: "安全",
        tail: "尾部",
        launchd: "launchd",
      },
      ui: {
        title: "Notes Snapshot 控制台",
        badgeLocal: "本地",
        heroSummary: "用于 Apple Notes 导出的确定性本地 Web 控制台，无需打包桌面应用。",
        refresh: "刷新",
        lastUpdate: "最后更新",
        firstRunGuidance: "首次运行指引",
        snapshotStatus: "快照状态",
        logHealth: "日志健康度",
        doctor: "诊断",
        recentMetrics: "最近指标",
        recentRuns: "最近运行",
        accessPolicy: "访问策略",
        quickActions: "快捷操作",
        scheduler: "调度器",
        vendorSync: "Vendor 同步",
        logViewer: "日志查看器",
        actionOutput: "操作输出",
        healthSummary: "健康摘要",
        stateLayers: "状态分层",
        healthReasonCodes: "健康原因代码",
        triggerSources: "触发来源",
        effectiveActions: "实际可用操作",
        status: "状态",
        exitCode: "退出码",
        lastSuccess: "最近成功",
        lastRun: "最近运行",
        age: "距离现在",
        launchd: "Launchd",
        triggerSource: "触发来源",
        failureReason: "失败原因",
        healthScore: "健康分数",
        schema: "Schema",
        runId: "运行 ID",
        interval: "间隔",
        totalErrors: "错误总数",
        stdout: "Stdout",
        stderr: "Stderr",
        launchdErr: "Launchd 错误",
        pattern: "模式",
        tailLines: "尾部行数",
        tailConfig: "Tail 配置",
        dependencies: "依赖",
        warnings: "警告",
        repoRoot: "仓库根目录",
        vendorDir: "Vendor 目录",
        stateDir: "状态目录",
        pythonBin: "Python 可执行文件",
        osascript: "AppleScript",
        launchctl: "launchctl",
        plutil: "plutil",
        timeoutBin: "超时命令",
        runIdFilter: "运行 ID 过滤",
        recentRunsCount: "最近运行数",
        successes: "成功次数",
        failures: "失败次数",
        latestStatus: "最新状态",
        topFailure: "最高频失败",
        recentTrend: "近期趋势",
        currentStreak: "当前连续状态",
        runChangeSummary: "运行 / 变化摘要",
        failureClusters: "失败簇",
        requireToken: "需要 Token",
        staticToken: "静态资源 Token",
        readonly: "只读",
        tokenScopes: "Token 作用域",
        actionsAllowlist: "操作白名单",
        rateLimit: "速率限制",
        cooldowns: "冷却时间",
        minutes: "分钟",
        intervalSec: "间隔（秒）",
        loadAfterInstall: "安装后加载",
        keepWebAlive: "保持 Web UI 常驻",
        install: "安装",
        ensure: "修复确保",
        unload: "卸载",
        vendorRef: "Ref（tag/branch/sha）",
        patchDryRun: "补丁演练",
        autoCommit: "自动提交",
        updateVendor: "更新 Vendor",
        logType: "日志类型",
        sinceMinutes: "追溯分钟数",
        rotateScope: "轮转范围",
        fetchLogs: "获取日志",
        rotateLogs: "轮转日志",
        perfectSetup: "完整设置",
        runSnapshot: "运行快照",
        verify: "校验",
        fastFix: "快速修复",
        selfHeal: "自愈",
        permissions: "权限",
        placeholderOptional: "可选",
        placeholderVendorRef: "v1.3.0",
        placeholderRunIdContains: "run_id 包含...",
      },
      emptyState: {
        metrics: "暂时还没有指标。",
        healthSummary: "健康摘要暂未提供。",
        doctorSummary: "诊断摘要暂未提供。",
        noWarnings: "没有警告",
        noRecordedRuns: "还没有记录到运行。",
        noChangeSummary: "还没有运行变化摘要。",
        noFailureClusters: "最近窗口里没有失败簇。",
        noActions: "没有可用操作",
        noIssues: "未检测到问题",
        noActionsYet: "还没有操作记录。",
      },
      message: {
        apiUnavailable: "无法连接本地 API。若一直如此，请确认 Web UI 服务器正在运行。",
        runningAction: "正在执行 {action}...",
        actionFailed: "操作失败：{detail}",
        firstRunSummary: "先完成一次成功快照，再把控制室里的其他信息当成持续运维状态来看。",
        firstRunHint: "需要完整清单？打开 quickstart 或 troubleshooting 指南。",
        firstRunHintHtml:
          '想看完整清单？打开 <a href="https://xiaojiou176-open.github.io/apple-notes-snapshot/quickstart/">quickstart</a> 或 <a href="https://xiaojiou176-open.github.io/apple-notes-snapshot/troubleshooting/">troubleshooting guide</a>。',
        firstRunExplanation: "这通常是首次运行或刚清理后的正常状态。先建立一次成功快照基线，再判断它是否属于主动故障。",
        logHealthLastStatus: "last_status：{status}",
        outputOk: "完成",
        actionFileLabel: "文件：{path}",
        unknownError: "未知错误",
        webActionSource: "Web：{action}",
        accessTip: "提示：尽量只使用最小 scope 和 allowlist（例如 scopes=read,run 且 actions=run），把暴露面压到最小。",
        bannerReadonly: "当前处于只读模式。若你希望按钮真正执行动作，请先检查访问策略。",
        bannerFailureCluster: "最近运行仍指向一个活跃失败簇：{reason}",
        bannerRecoveryWatch: "最新一次运行已经恢复，但还需要再观察下一次运行，才能判断循环是否真的稳定。",
        bannerStale: "当前更像是快照循环变旧了。先刷新快照，再判断是不是更深层的运行事故。",
      },
      onboarding: {
        stepRun: "运行 ./notesctl run --no-status，让 macOS 先弹出首次权限提示。",
        stepVerify: "运行 ./notesctl verify，确认本地状态账本已经记录到成功基线。",
        stepDoctor: "如果状态仍然空白或还有警告，再运行 ./notesctl doctor。",
      },
      backend: {
        status: {
          success: "成功",
          failed: "失败",
          aborted: "中止",
          running: "运行中",
          unknown: "未知",
        },
        healthLevel: {
          OK: "正常",
          WARN: "警告",
          DEGRADED: "降级",
          FAIL: "失败",
          ONBOARDING: "初始引导",
        },
        stateLayerStatus: {
          configured: "已配置",
          loaded: "已加载",
          notLoaded: "未加载",
          unknown: "未知",
          fresh: "新鲜",
          stale: "过期",
          failed: "失败",
          runningWithoutSuccess: "运行中但尚无成功",
          needsFirstRun: "需要首次运行",
        },
        healthReason: {
          launchdNotLoaded: "launchd 未加载",
          lastRunFailed: "最近一次运行失败",
          running: "正在运行",
          exitNonzero: "退出码非 0",
          statusExitMismatch: "状态与退出码不一致",
          stale: "成功记录已过期",
          unknownLastSuccess: "最近成功时间未知",
          checksumMismatch: "校验和不一致",
          checksumMissing: "缺少校验和",
          logHealthErrors: "日志健康度检测到错误",
        },
        stateLayerLabel: {
          config: "配置层",
          launchd: "Launchd 实时层",
          ledger: "账本层",
        },
        metricEvent: {
          runStart: "运行开始",
          runEnd: "运行结束",
        },
        healthSummary: {
          needsFirstRun: "配置和 launchd 都能正常读取，但账本还缺少第一次成功快照基线。",
          runningWithoutSuccess: "当前有快照任务在运行，但账本还没有记录到成功基线。",
          stale: "已经有成功快照，但它早于当前的新鲜度目标。",
          failed: "本地账本指向一次失败运行，仍然需要一次成功恢复基线。",
          launchdNotLoaded: "本地调度器当前没有加载，所以备份循环不会自动运行。",
          logHealthErrors: "控制室状态面已经存在，但最近日志健康信号里仍然出现运行时错误。",
          healthy: "当前本地备份表面状态足够健康，可以继续把这套确定性工具链当作真理源。",
        },
        stateLayerSummary: {
          configured: "配置层已经解析出根目录、状态目录、日志目录和时间间隔。",
          launchdLoaded: "launchctl 报告 {label} 已加载。",
          launchdNotLoaded: "launchctl 当前没有报告 {label} 已加载。",
          launchdUnknown: "无法确定 launchctl 当前状态。",
          ledgerFresh: "本地状态账本里已经记录到一次成功快照。",
          ledgerStale: "已经存在成功快照，但它早于当前的新鲜度阈值。",
          ledgerRunningWithoutSuccess: "当前有运行进行中，但账本还没有记录到成功快照。",
          ledgerFailed: "账本记录到一次失败运行，而且仍然没有成功快照。",
          ledgerNeedsFirstRun: "还没有记录到成功快照。先手动运行一次快照来初始化账本。",
        },
        operatorSummary: {
          firstRun: "这更像是首次运行或刚清理后的基线状态。先完成一次成功的手动快照，再把它当成主动运行故障处理。",
          launchdNotLoaded: "调度器当前没有加载，所以备份循环不会自己跑起来。",
          stale: "已经存在成功快照，但它超出了新鲜度目标。",
          failed: "本地状态账本指向一次失败运行，仍然需要一次成功恢复基线。",
          healthy: "确定性控制室表面都已就位；剩余缺口请继续看下面的警告。",
        },
        warning: {
          noSuccessfulSnapshot: "还没有记录到成功快照；先运行 ./notesctl run --no-status 初始化账本。",
          lastSuccessStale: "最近一次成功已过期（{ageSec} 秒 > {thresholdSec} 秒）",
          launchdJobNotLoaded: "launchd 任务尚未加载",
          webTokenRequired: "Web 要求 Token，但 NOTES_SNAPSHOT_WEB_TOKEN 为空",
          webStaticTokenRequired: "静态资源要求 Token，但 NOTES_SNAPSHOT_WEB_TOKEN 为空",
          remoteWithoutToken: "允许远程访问，但没有要求 Token",
          remoteEmptyAllowlist: "允许远程访问，但 IP 白名单为空",
        },
        changeTrend: {
          unknown: "未知",
          noRuns: "近期无运行",
          singleSuccess: "单次成功",
          singleFailed: "单次失败",
          recovered: "已恢复",
          regressed: "发生回退",
          steadySuccess: "持续成功",
          steadyFailure: "持续失败",
          mixed: "混合",
        },
        changeSummary: {
          noRuns: "当前窗口里还没有 recent runs。",
          singleSuccess: "当前窗口里只有一次 recent run，而且它以成功结束。",
          singleFailed: "当前窗口里只有一次 recent run，而且它以失败结束。",
          recovered: "最近一次运行已经成功，说明它是在当前窗口内从更早的失败里恢复出来的。",
          regressed: "最近一次运行已经失败，说明它是在当前窗口内从更早的成功状态回退下来的。",
          steadySuccess: "当前窗口相对稳定：最近连续 {count} 次运行都成功了。",
          steadyFailure: "当前窗口仍不稳定：最近连续 {count} 次运行都失败了。",
          mixed: "最近运行呈现混合或不完整的状态信号。",
        },
        recoverability: {
          bootstrap: "初始化阶段",
          recoverable: "可恢复",
          watchWindow: "观察窗口",
          stableMonitoring: "稳定监控",
          manualReview: "需要人工复核",
        },
        workflowHint: {
          bootstrap: "先建立第一次成功快照基线，再把控制室当成正在发生的事故面板来读。",
          failureCluster: "先把最近的失败簇当成第一站，再按顺序检查 status、log-health、doctor。",
          recoveryWatch: "最新一次运行已经恢复；先验证新鲜度，再观察下一次运行，别太早宣布稳定。",
          stable: "当前保持观察模式即可，除非新鲜度或警告变化，否则不需要立即恢复动作。",
          mixed: "先把 recent-run 趋势和 state layers 一起看，再决定下一步操作顺序。",
        },
      },
    },
  };

  const DISPLAY_KEY_MAPS = {
    status: {
      success: "backend.status.success",
      failed: "backend.status.failed",
      aborted: "backend.status.aborted",
      running: "backend.status.running",
      unknown: "backend.status.unknown",
    },
    healthLevel: {
      OK: "backend.healthLevel.OK",
      WARN: "backend.healthLevel.WARN",
      DEGRADED: "backend.healthLevel.DEGRADED",
      FAIL: "backend.healthLevel.FAIL",
      ONBOARDING: "backend.healthLevel.ONBOARDING",
      READONLY: "pill.readonly",
      ACTIVE: "pill.active",
      LOCKED: "pill.locked",
      ready: "pill.ready",
      running: "pill.running",
      idle: "pill.idle",
      safe: "pill.safe",
      tail: "pill.tail",
      launchd: "pill.launchd",
    },
    stateLayerStatus: {
      configured: "backend.stateLayerStatus.configured",
      loaded: "backend.stateLayerStatus.loaded",
      not_loaded: "backend.stateLayerStatus.notLoaded",
      unknown: "backend.stateLayerStatus.unknown",
      fresh: "backend.stateLayerStatus.fresh",
      stale: "backend.stateLayerStatus.stale",
      failed: "backend.stateLayerStatus.failed",
      running_without_success: "backend.stateLayerStatus.runningWithoutSuccess",
      needs_first_run: "backend.stateLayerStatus.needsFirstRun",
    },
    healthReason: {
      launchd_not_loaded: "backend.healthReason.launchdNotLoaded",
      last_run_failed: "backend.healthReason.lastRunFailed",
      running: "backend.healthReason.running",
      exit_nonzero: "backend.healthReason.exitNonzero",
      status_exit_mismatch: "backend.healthReason.statusExitMismatch",
      stale: "backend.healthReason.stale",
      unknown_last_success: "backend.healthReason.unknownLastSuccess",
      checksum_mismatch: "backend.healthReason.checksumMismatch",
      checksum_missing: "backend.healthReason.checksumMissing",
      log_health_errors: "backend.healthReason.logHealthErrors",
    },
    stateLayerLabel: {
      config: "backend.stateLayerLabel.config",
      launchd: "backend.stateLayerLabel.launchd",
      ledger: "backend.stateLayerLabel.ledger",
    },
    metricEvent: {
      run_start: "backend.metricEvent.runStart",
      run_end: "backend.metricEvent.runEnd",
    },
    boolean: {
      yes: "common.yes",
      no: "common.no",
      online: "common.online",
      offline: "common.offline",
      unknown: "common.unknown",
      none: "common.none",
    },
    changeTrend: {
      unknown: "backend.changeTrend.unknown",
      no_runs: "backend.changeTrend.noRuns",
      single_success: "backend.changeTrend.singleSuccess",
      single_failed: "backend.changeTrend.singleFailed",
      recovered: "backend.changeTrend.recovered",
      regressed: "backend.changeTrend.regressed",
      steady_success: "backend.changeTrend.steadySuccess",
      steady_failure: "backend.changeTrend.steadyFailure",
      mixed: "backend.changeTrend.mixed",
    },
    recoverability: {
      bootstrap: "backend.recoverability.bootstrap",
      recoverable: "backend.recoverability.recoverable",
      watch_window: "backend.recoverability.watchWindow",
      stable_monitoring: "backend.recoverability.stableMonitoring",
      manual_review: "backend.recoverability.manualReview",
    },
  };

  const DISPLAY_PATTERNS = {
    healthSummary: [
      {
        match: "Config and launchd look readable, but the ledger still needs the first successful snapshot baseline.",
        key: "backend.healthSummary.needsFirstRun",
      },
      {
        match: "A snapshot run is active, but the ledger has not recorded a successful baseline yet.",
        key: "backend.healthSummary.runningWithoutSuccess",
      },
      {
        match: "A successful snapshot exists, but it is older than the freshness target.",
        key: "backend.healthSummary.stale",
      },
      {
        match: "The local ledger points to a failed run and still needs a successful recovery baseline.",
        key: "backend.healthSummary.failed",
      },
      {
        match: "The local scheduler is not loaded right now, so the backup loop is not running on its own.",
        key: "backend.healthSummary.launchdNotLoaded",
      },
      {
        match: "Recent log health signals show runtime errors even though the control-room state surface is present.",
        key: "backend.healthSummary.logHealthErrors",
      },
      {
        match: "The current local backup surface looks healthy enough to keep using the deterministic tooling as the source of truth.",
        key: "backend.healthSummary.healthy",
      },
    ],
    stateLayerSummary: [
      {
        match: "Config surface resolved for root, state, logs, and interval.",
        key: "backend.stateLayerSummary.configured",
      },
      {
        match: /^launchctl reports (.+) is loaded\.$/,
        key: "backend.stateLayerSummary.launchdLoaded",
        toParams: function toParams(matches) {
          return { label: matches[1] };
        },
      },
      {
        match: /^launchctl does not currently report (.+) as loaded\.$/,
        key: "backend.stateLayerSummary.launchdNotLoaded",
        toParams: function toParams(matches) {
          return { label: matches[1] };
        },
      },
      {
        match: "launchctl state could not be determined.",
        key: "backend.stateLayerSummary.launchdUnknown",
      },
      {
        match: "A successful snapshot is recorded in the local state ledger.",
        key: "backend.stateLayerSummary.ledgerFresh",
      },
      {
        match: "A successful snapshot exists, but it is older than the freshness threshold.",
        key: "backend.stateLayerSummary.ledgerStale",
      },
      {
        match: "A run is active, but the ledger has not recorded a successful snapshot yet.",
        key: "backend.stateLayerSummary.ledgerRunningWithoutSuccess",
      },
      {
        match: "The ledger recorded a failed run and still has no successful snapshot.",
        key: "backend.stateLayerSummary.ledgerFailed",
      },
      {
        match: "No successful snapshot is recorded yet. Run one manual snapshot to initialize the ledger.",
        key: "backend.stateLayerSummary.ledgerNeedsFirstRun",
      },
    ],
    operatorSummary: [
      {
        match: "This looks like a first-run or cleaned-checkout baseline. Finish one successful manual snapshot before treating it as an active runtime failure.",
        key: "backend.operatorSummary.firstRun",
      },
      {
        match: "The scheduler is not currently loaded, so the backup loop is not running on its own.",
        key: "backend.operatorSummary.launchdNotLoaded",
      },
      {
        match: "A successful snapshot exists, but it is outside the freshness target.",
        key: "backend.operatorSummary.stale",
      },
      {
        match: "The local state ledger points to a failed run and still needs a successful recovery baseline.",
        key: "backend.operatorSummary.failed",
      },
      {
        match: "The deterministic control-room surfaces are present; use warnings below to inspect any remaining gaps.",
        key: "backend.operatorSummary.healthy",
      },
    ],
    changeSummary: [
      {
        match: "No recent runs were available in the current window.",
        key: "backend.changeSummary.noRuns",
      },
      {
        match: "Only one recent run is available, and it ended with success.",
        key: "backend.changeSummary.singleSuccess",
      },
      {
        match: "Only one recent run is available, and it ended with failed.",
        key: "backend.changeSummary.singleFailed",
      },
      {
        match: "The most recent run succeeded after earlier failures in the recent window.",
        key: "backend.changeSummary.recovered",
      },
      {
        match: "The most recent run failed after earlier successes in the recent window.",
        key: "backend.changeSummary.regressed",
      },
      {
        match: /^The recent window is steady: the last (\d+) run\(s\) all succeeded\.$/,
        key: "backend.changeSummary.steadySuccess",
        toParams: function toParams(matches) {
          return { count: matches[1] };
        },
      },
      {
        match: /^The recent window is unstable: the last (\d+) run\(s\) all failed\.$/,
        key: "backend.changeSummary.steadyFailure",
        toParams: function toParams(matches) {
          return { count: matches[1] };
        },
      },
      {
        match: "Recent runs show mixed or incomplete status signals.",
        key: "backend.changeSummary.mixed",
      },
    ],
    workflowHint: [
      {
        match: "Initialize the first successful snapshot baseline before treating the control room as a live incident board.",
        key: "backend.workflowHint.bootstrap",
      },
      {
        match: "Treat the latest failure cluster as the first stop, then inspect status, log-health, and doctor in that order.",
        key: "backend.workflowHint.failureCluster",
      },
      {
        match: "The latest run recovered; verify freshness and watch the next run before declaring the loop stable.",
        key: "backend.workflowHint.recoveryWatch",
      },
      {
        match: "Stay in watch mode; no immediate recovery action is required unless freshness or warnings change.",
        key: "backend.workflowHint.stable",
      },
      {
        match: "Use recent-run trend and state layers together before choosing the next operator action.",
        key: "backend.workflowHint.mixed",
      },
    ],
    warning: [
      {
        match: "no successful snapshot recorded yet; run ./notesctl run --no-status once to initialize the ledger",
        key: "backend.warning.noSuccessfulSnapshot",
      },
      {
        match: /^last success is stale \((\d+)s > (\d+)s\)$/,
        key: "backend.warning.lastSuccessStale",
        toParams: function toParams(matches) {
          return { ageSec: matches[1], thresholdSec: matches[2] };
        },
      },
      {
        match: "launchd job not loaded",
        key: "backend.warning.launchdJobNotLoaded",
      },
      {
        match: "web token required but NOTES_SNAPSHOT_WEB_TOKEN is empty",
        key: "backend.warning.webTokenRequired",
      },
      {
        match: "web static token required but NOTES_SNAPSHOT_WEB_TOKEN is empty",
        key: "backend.warning.webStaticTokenRequired",
      },
      {
        match: "web allow remote without token requirement",
        key: "backend.warning.remoteWithoutToken",
      },
      {
        match: "web allow remote with empty allowlist",
        key: "backend.warning.remoteEmptyAllowlist",
      },
    ],
  };

  function getGlobalStorage() {
    if (!globalScope || !globalScope.localStorage) {
      return null;
    }
    return globalScope.localStorage;
  }

  function normalizeLocale(locale) {
    if (typeof locale !== "string" || locale.trim() === "") {
      return DEFAULT_LOCALE;
    }

    const raw = locale.trim();
    if (SUPPORTED_LOCALES.indexOf(raw) >= 0) {
      return raw;
    }

    const lowered = raw.toLowerCase();
    if (lowered === "zh" || lowered === "zh-cn" || lowered === "zh_cn") {
      return ZH_CN_LOCALE;
    }

    if (lowered === "en" || lowered === "en-us" || lowered === "en_us") {
      return DEFAULT_LOCALE;
    }

    return DEFAULT_LOCALE;
  }

  function getByPath(source, path) {
    if (!source || typeof path !== "string" || path === "") {
      return undefined;
    }
    return path.split(".").reduce(function walk(current, segment) {
      if (!current || typeof current !== "object") {
        return undefined;
      }
      return current[segment];
    }, source);
  }

  function deepMerge(target, source) {
    const base = target && typeof target === "object" ? target : Object.create(null);
    if (!source || typeof source !== "object") {
      return base;
    }

    Object.keys(source).forEach(function mergeKey(key) {
      if (key === "__proto__" || key === "constructor" || key === "prototype") {
        return;
      }
      const incoming = source[key];
      const current = Object.prototype.hasOwnProperty.call(base, key) ? base[key] : undefined;
      const canMergeRecursively =
        incoming &&
        typeof incoming === "object" &&
        !Array.isArray(incoming) &&
        current &&
        typeof current === "object" &&
        !Array.isArray(current);
      if (canMergeRecursively) {
        base[key] = deepMerge(current, incoming);
        return;
      }
      base[key] = incoming;
    });

    return base;
  }

  function interpolate(template, params) {
    if (typeof template !== "string" || !params || typeof params !== "object") {
      return template;
    }
    return template.replace(/\{([^}]+)\}/g, function replaceToken(match, tokenName) {
      if (!Object.prototype.hasOwnProperty.call(params, tokenName)) {
        return match;
      }
      const value = params[tokenName];
      return value === undefined || value === null ? "" : String(value);
    });
  }

  function readStoredLocale(storage) {
    const activeStorage = storage || getGlobalStorage();
    if (!activeStorage || typeof activeStorage.getItem !== "function") {
      return null;
    }

    try {
      const stored = activeStorage.getItem(LOCALE_STORAGE_KEY);
      return stored ? normalizeLocale(stored) : null;
    } catch (error) {
      return null;
    }
  }

  function persistLocale(locale, storage) {
    const nextLocale = normalizeLocale(locale);
    const activeStorage = storage || getGlobalStorage();
    if (!activeStorage || typeof activeStorage.setItem !== "function") {
      return nextLocale;
    }

    try {
      activeStorage.setItem(LOCALE_STORAGE_KEY, nextLocale);
    } catch (error) {
      return nextLocale;
    }

    return nextLocale;
  }

  function resolveInitialLocale(options) {
    const opts = options || {};
    const fromExplicit = opts.locale ? normalizeLocale(opts.locale) : null;
    if (fromExplicit) {
      return fromExplicit;
    }

    const stored = readStoredLocale(opts.storage);
    if (stored) {
      return stored;
    }

    return DEFAULT_LOCALE;
  }

  function resolveRegistrationLocale(locale) {
    if (typeof locale !== "string") {
      throw new Error(`Unsupported locale: ${locale}`);
    }
    const requested = locale.trim();
    if (!requested) {
      throw new Error(`Unsupported locale: ${locale}`);
    }
    const lowered = requested.toLowerCase();
    for (let index = 0; index < SUPPORTED_LOCALES.length; index += 1) {
      const supportedLocale = SUPPORTED_LOCALES[index];
      if (supportedLocale.toLowerCase() === lowered) {
        return supportedLocale;
      }
    }
    throw new Error(`Unsupported locale: ${locale}`);
  }

  function registerTranslations(locale, entries) {
    const normalizedLocale = resolveRegistrationLocale(locale);
    if (!TRANSLATIONS[normalizedLocale]) {
      TRANSLATIONS[normalizedLocale] = {};
    }
    deepMerge(TRANSLATIONS[normalizedLocale], entries || {});
    return TRANSLATIONS[normalizedLocale];
  }

  function listLocales() {
    return SUPPORTED_LOCALES.slice();
  }

  function getMessages(locale) {
    return TRANSLATIONS[normalizeLocale(locale)];
  }

  function hasTranslation(key, locale) {
    return getByPath(getMessages(locale), key) !== undefined || getByPath(getMessages(DEFAULT_LOCALE), key) !== undefined;
  }

  function translateKey(key, params, locale) {
    const normalizedLocale = normalizeLocale(locale);
    const rawValue = getByPath(getMessages(normalizedLocale), key);
    const fallbackValue = rawValue === undefined ? getByPath(getMessages(DEFAULT_LOCALE), key) : rawValue;
    if (typeof fallbackValue !== "string") {
      return key;
    }
    return interpolate(fallbackValue, params);
  }

  function matchDisplayPattern(kind, canonicalValue, locale, params) {
    const candidates = DISPLAY_PATTERNS[kind] || [];
    for (let index = 0; index < candidates.length; index += 1) {
      const rule = candidates[index];
      if (typeof rule.match === "string" && canonicalValue === rule.match) {
        return translateKey(rule.key, params, locale);
      }
      if (rule.match instanceof RegExp) {
        const matches = canonicalValue.match(rule.match);
        if (matches) {
          const derivedParams = typeof rule.toParams === "function" ? rule.toParams(matches) : {};
          return translateKey(rule.key, Object.assign({}, derivedParams, params || {}), locale);
        }
      }
    }
    return null;
  }

  function translateDisplay(kind, canonicalValue, options) {
    if (canonicalValue === undefined || canonicalValue === null) {
      return "";
    }

    const opts = options || {};
    const locale = opts.locale || DEFAULT_LOCALE;
    const text = String(canonicalValue);
    const keyMap = DISPLAY_KEY_MAPS[kind];
    if (keyMap && Object.prototype.hasOwnProperty.call(keyMap, text)) {
      return translateKey(keyMap[text], opts.params, locale);
    }

    const patternMatch = matchDisplayPattern(kind, text, locale, opts.params);
    if (patternMatch !== null) {
      return patternMatch;
    }

    return text;
  }

  function translateStatus(value, locale) {
    return translateDisplay("status", value, { locale: locale });
  }

  function translateHealthLevel(value, locale) {
    return translateDisplay("healthLevel", value, { locale: locale });
  }

  function translateStateLayerStatus(value, locale) {
    return translateDisplay("stateLayerStatus", value, { locale: locale });
  }

  function translateHealthReason(value, locale) {
    return translateDisplay("healthReason", value, { locale: locale });
  }

  function translateHealthSummary(value, locale) {
    return translateDisplay("healthSummary", value, { locale: locale });
  }

  function translateStateLayerSummary(value, locale) {
    return translateDisplay("stateLayerSummary", value, { locale: locale });
  }

  function translateOperatorSummary(value, locale) {
    return translateDisplay("operatorSummary", value, { locale: locale });
  }

  function translateWarning(value, locale) {
    return translateDisplay("warning", value, { locale: locale });
  }

  function translateBoolean(value, locale) {
    return translateDisplay("boolean", value, { locale: locale });
  }

  function translateChangeTrend(value, locale) {
    return translateDisplay("changeTrend", value, { locale: locale });
  }

  function translateRecoverability(value, locale) {
    return translateDisplay("recoverability", value, { locale: locale });
  }

  function translateChangeSummary(value, locale) {
    return translateDisplay("changeSummary", value, { locale: locale });
  }

  function translateWorkflowHint(value, locale) {
    return translateDisplay("workflowHint", value, { locale: locale });
  }

  function parseElementParams(element, extraParams) {
    const params = Object.assign({}, extraParams || {});
    const raw = element ? element.getAttribute("data-i18n-params") : "";
    if (!raw) {
      return params;
    }

    try {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === "object") {
        return Object.assign(params, parsed);
      }
    } catch (error) {
      return params;
    }

    return params;
  }

  function applyElementTranslation(element, locale, params) {
    if (!element || typeof element.getAttribute !== "function") {
      return null;
    }

    const nextLocale = locale || DEFAULT_LOCALE;
    const mergedParams = parseElementParams(element, params);

    if (element.hasAttribute("data-i18n")) {
      const key = element.getAttribute("data-i18n");
      element.textContent = translateKey(key, mergedParams, nextLocale);
    }

    const attributeKeys = [
      ["data-i18n-html", "innerHTML"],
      ["data-i18n-placeholder", "placeholder"],
      ["data-i18n-title", "title"],
      ["data-i18n-aria-label", "aria-label"],
      ["data-i18n-value", "value"],
    ];

    attributeKeys.forEach(function eachAttribute(pair) {
      const dataKey = pair[0];
      const attributeName = pair[1];
      if (!element.hasAttribute(dataKey)) {
        return;
      }
      const key = element.getAttribute(dataKey);
      const translated = translateKey(key, mergedParams, nextLocale);
      if (attributeName === "innerHTML") {
        element.innerHTML = translated;
        return;
      }
      element.setAttribute(attributeName, translated);
    });

    return element;
  }

  function createI18n(options) {
    const opts = options || {};
    const storage = opts.storage || null;
    const listeners = new Set();
    const state = {
      locale: resolveInitialLocale({
        locale: opts.locale,
        storage: storage,
      }),
    };

    function notify() {
      listeners.forEach(function eachListener(listener) {
        listener(state.locale);
      });
    }

    function getLocale() {
      return state.locale;
    }

    function setLocale(locale, setOptions) {
      const innerOptions = setOptions || {};
      const nextLocale = normalizeLocale(locale);
      state.locale = nextLocale;
      if (innerOptions.persist !== false) {
        persistLocale(nextLocale, innerOptions.storage || storage);
      }
      notify();
      return state.locale;
    }

    function t(key, params, locale) {
      return translateKey(key, params, locale || state.locale);
    }

    function translateElement(element, translateOptions) {
      const innerOptions = translateOptions || {};
      return applyElementTranslation(element, innerOptions.locale || state.locale, innerOptions.params);
    }

    function applyTranslations(root, translateOptions) {
      const innerOptions = translateOptions || {};
      const base = root || (globalScope && globalScope.document ? globalScope.document : null);
      if (!base || typeof base.querySelectorAll !== "function") {
        return 0;
      }

      const selector = [
        "[data-i18n]",
        "[data-i18n-html]",
        "[data-i18n-placeholder]",
        "[data-i18n-title]",
        "[data-i18n-aria-label]",
        "[data-i18n-value]",
      ].join(", ");

      const nodes = base.querySelectorAll(selector);
      nodes.forEach(function eachNode(node) {
        applyElementTranslation(node, innerOptions.locale || state.locale, innerOptions.params);
      });

      if (
        typeof base.matches === "function" &&
        base.matches(selector)
      ) {
        applyElementTranslation(base, innerOptions.locale || state.locale, innerOptions.params);
      }

      return nodes.length;
    }

    function subscribe(listener) {
      if (typeof listener !== "function") {
        return function noop() {};
      }
      listeners.add(listener);
      return function unsubscribe() {
        listeners.delete(listener);
      };
    }

    function getState() {
      return {
        locale: state.locale,
        defaultLocale: DEFAULT_LOCALE,
        supportedLocales: listLocales(),
        storageKey: LOCALE_STORAGE_KEY,
      };
    }

    return {
      getLocale: getLocale,
      setLocale: setLocale,
      getState: getState,
      subscribe: subscribe,
      t: t,
      translateDisplay: function translateDisplayWithState(kind, canonicalValue, translateOptions) {
        const innerOptions = translateOptions || {};
        return translateDisplay(kind, canonicalValue, {
          locale: innerOptions.locale || state.locale,
          params: innerOptions.params,
        });
      },
      translateStatus: function translateStatusWithState(value, locale) {
        return translateStatus(value, locale || state.locale);
      },
      translateHealthLevel: function translateHealthLevelWithState(value, locale) {
        return translateHealthLevel(value, locale || state.locale);
      },
      translateStateLayerStatus: function translateStateLayerStatusWithState(value, locale) {
        return translateStateLayerStatus(value, locale || state.locale);
      },
      translateHealthReason: function translateHealthReasonWithState(value, locale) {
        return translateHealthReason(value, locale || state.locale);
      },
      translateHealthSummary: function translateHealthSummaryWithState(value, locale) {
        return translateHealthSummary(value, locale || state.locale);
      },
      translateStateLayerSummary: function translateStateLayerSummaryWithState(value, locale) {
        return translateStateLayerSummary(value, locale || state.locale);
      },
      translateOperatorSummary: function translateOperatorSummaryWithState(value, locale) {
        return translateOperatorSummary(value, locale || state.locale);
      },
      translateWarning: function translateWarningWithState(value, locale) {
        return translateWarning(value, locale || state.locale);
      },
      translateBoolean: function translateBooleanWithState(value, locale) {
        return translateBoolean(value, locale || state.locale);
      },
      translateChangeTrend: function translateChangeTrendWithState(value, locale) {
        return translateChangeTrend(value, locale || state.locale);
      },
      translateRecoverability: function translateRecoverabilityWithState(value, locale) {
        return translateRecoverability(value, locale || state.locale);
      },
      translateChangeSummary: function translateChangeSummaryWithState(value, locale) {
        return translateChangeSummary(value, locale || state.locale);
      },
      translateWorkflowHint: function translateWorkflowHintWithState(value, locale) {
        return translateWorkflowHint(value, locale || state.locale);
      },
      translateElement: translateElement,
      applyTranslations: applyTranslations,
    };
  }

  const defaultI18n = createI18n();

  const api = Object.assign({}, defaultI18n, {
    DEFAULT_LOCALE: DEFAULT_LOCALE,
    LOCALE_STORAGE_KEY: LOCALE_STORAGE_KEY,
    SUPPORTED_LOCALES: listLocales(),
    TRANSLATIONS: TRANSLATIONS,
    normalizeLocale: normalizeLocale,
    readStoredLocale: readStoredLocale,
    persistLocale: persistLocale,
    resolveInitialLocale: resolveInitialLocale,
    registerTranslations: registerTranslations,
    getMessages: getMessages,
    hasTranslation: hasTranslation,
    translateDisplayValue: translateDisplay,
    translateStatusValue: translateStatus,
    translateHealthLevelValue: translateHealthLevel,
    translateStateLayerStatusValue: translateStateLayerStatus,
    translateHealthReasonValue: translateHealthReason,
    translateHealthSummaryValue: translateHealthSummary,
    translateStateLayerSummaryValue: translateStateLayerSummary,
    translateOperatorSummaryValue: translateOperatorSummary,
    translateWarningValue: translateWarning,
    translateBooleanValue: translateBoolean,
    translateChangeTrendValue: translateChangeTrend,
    translateRecoverabilityValue: translateRecoverability,
    translateChangeSummaryValue: translateChangeSummary,
    translateWorkflowHintValue: translateWorkflowHint,
    createI18n: createI18n,
  });

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }

  globalScope.NotesSnapshotI18n = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
