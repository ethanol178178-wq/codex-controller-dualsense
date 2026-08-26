(() => {
  const API_BASE = "http://127.0.0.1:37845";
  const EFFECT_NAMES = { static: "靜態常亮", blink: "閃爍", breathe: "呼吸" };
  const SPEED_NAMES = ["極慢", "慢速", "中速", "快速", "極快"];
  const TRIGGER_MODE_NAMES = {
    off: "關閉",
    feedback: "連續阻力",
    weapon: "槍械斷點",
  };
  const MAPPING_SCHEMA_VERSION = 23;
  const CODEX_DICTATION_MAPPING = ["CodexDictation"];
  const CODEX_RIGHT_PANEL_MAPPING = ["ControlLeft", "AltLeft", "KeyB"];
  const CONTROLLER_WORKFLOW_MAPPINGS = {
    circle: ["ShiftLeft", "Tab"],
    triangle: ["Escape"],
    l1: ["CodexModelNext"],
    r1: ["ControlLeft", "AltLeft", "KeyB"],
    l2: [...CODEX_DICTATION_MAPPING],
    ps: ["CodexFocus"],
    r2: ["Enter"],
    square: ["CodexSmartDelete"],
    r3: [...CODEX_RIGHT_PANEL_MAPPING],
    right_stick_up: ["MouseWheelUp"],
    right_stick_down: ["MouseWheelDown"],
    touchpad: ["ControlLeft", "KeyF"],
    mute: ["ControlLeft", "ShiftLeft", "KeyV"],
  };
  const CLEARED_STICK_INPUTS = [
    "left_stick_up",
    "left_stick_right",
    "left_stick_down",
    "left_stick_left",
    "right_stick_up",
    "right_stick_right",
    "right_stick_down",
    "right_stick_left",
  ];
  const LEFT_STICK_NAVIGATION = {
    left_stick_up: ["ArrowUp"],
    left_stick_right: ["ArrowRight"],
    left_stick_down: ["ArrowDown"],
    left_stick_left: ["ArrowLeft"],
  };
  const DPAD_CONVERSATION_NAVIGATION = {
    dpad_up: ["ControlLeft", "ShiftLeft", "BracketLeft"],
    dpad_right: ["ControlLeft", "Tab"],
    dpad_down: ["ControlLeft", "ShiftLeft", "BracketRight"],
    dpad_left: ["ControlLeft", "ShiftLeft", "Tab"],
  };
  const DEFAULT_TRIGGERS = {
    left: { mode: "off", start: 3, end: 6, strength: 5 },
    right: { mode: "weapon", start: 3, end: 6, strength: 5 },
  };
  const DEFAULT_TOUCHPAD_GESTURES = {
    enabled: true,
    threshold: 320,
    muteOnSwitch: false,
  };
  const HAS_SAVED_TOUCHPAD_GESTURES = Boolean(
    localStorage.getItem("vibeHubTouchpadGestures"),
  );
  const savedTouchpadGestures = () => {
    try {
      const saved = JSON.parse(
        localStorage.getItem("vibeHubTouchpadGestures") || "null",
      );
      return saved && typeof saved.enabled === "boolean"
        ? {
            enabled: saved.enabled,
            threshold: Number(saved.threshold) || 320,
            muteOnSwitch: Boolean(saved.muteOnSwitch),
          }
        : { ...DEFAULT_TOUCHPAD_GESTURES };
    } catch {
      return { ...DEFAULT_TOUCHPAD_GESTURES };
    }
  };
  const HAS_SAVED_TRIGGERS = Boolean(localStorage.getItem("vibeHubTriggers"));
  const savedTriggers = () => {
    try {
      const saved = JSON.parse(
        localStorage.getItem("vibeHubTriggers") || "null",
      );
      return saved?.left && saved?.right
        ? saved
        : structuredClone(DEFAULT_TRIGGERS);
    } catch {
      return structuredClone(DEFAULT_TRIGGERS);
    }
  };
  const CODEX_STATUS_META = {
    approval: { label: "待核准", light: "黃燈閃爍" },
    working: { label: "工作中", light: "藍色呼吸" },
    complete: { label: "已完成", light: "綠燈常亮" },
    idle: { label: "待命", light: "白燈常亮" },
    error: { label: "發生錯誤", light: "紅燈閃爍" },
  };
  const PROFILE_META = {
    micro_focus: { label: "舊版專注配置", short: "舊版配置" },
    micro_tasks: { label: "舊版任務配置", short: "舊版配置" },
    micro_review: { label: "舊版審閱配置", short: "舊版配置" },
    vibe: { label: "Codex（推薦）", short: "Codex 推薦" },
    navigation: { label: "桌面導覽", short: "桌面導覽" },
    blank: { label: "空白設定", short: "空白設定" },
  };
  const UI_PROFILES = new Set(["vibe", "navigation", "blank"]);
  const CORE_BUTTON_IDS = [
    "mute",
    "l2",
    "touchpad",
    "r2",
    "cross",
    "circle",
    "ps",
    "square",
  ];
  const OFFICIAL_PLAYER_MASKS = [0x04, 0x0a, 0x15, 0x1b, 0x1f];
  const PLAYER_LED_GROUPS = [[0, 4], [1, 3], [2]];
  const MODIFIER_ORDER = [
    "ControlLeft",
    "ControlRight",
    "ShiftLeft",
    "ShiftRight",
    "AltLeft",
    "AltRight",
    "MetaLeft",
    "MetaRight",
  ];
  const MODIFIER_CODES = new Set(MODIFIER_ORDER);
  const NAMED_KEY_CODES = new Set([
    "Backspace",
    "Tab",
    "Enter",
    "Pause",
    "CapsLock",
    "Escape",
    "Space",
    "PageUp",
    "PageDown",
    "End",
    "Home",
    "ArrowLeft",
    "ArrowUp",
    "ArrowRight",
    "ArrowDown",
    "PrintScreen",
    "Insert",
    "Delete",
    "ContextMenu",
    "NumLock",
    "ScrollLock",
    "Semicolon",
    "Equal",
    "Comma",
    "Minus",
    "Period",
    "Slash",
    "Backquote",
    "BracketLeft",
    "Backslash",
    "BracketRight",
    "Quote",
    "NumpadMultiply",
    "NumpadAdd",
    "NumpadSubtract",
    "NumpadDecimal",
    "NumpadDivide",
    "NumpadEnter",
    ...MODIFIER_ORDER,
  ]);
  const isSupportedKeyCode = (code) =>
    NAMED_KEY_CODES.has(code) ||
    /^Key[A-Z]$/.test(code) ||
    /^Digit[0-9]$/.test(code) ||
    /^F(?:[1-9]|1[0-2])$/.test(code) ||
    /^Numpad[0-9]$/.test(code);

  const BUTTONS = [
    {
      id: "cross",
      label: "叉鍵",
      symbol: "×",
      group: "face",
      groupLabel: "主按鍵",
    },
    {
      id: "circle",
      label: "圓鍵",
      symbol: "○",
      group: "face",
      groupLabel: "主按鍵",
    },
    {
      id: "square",
      label: "方塊鍵",
      symbol: "□",
      group: "face",
      groupLabel: "主按鍵",
    },
    {
      id: "triangle",
      label: "三角鍵",
      symbol: "△",
      group: "face",
      groupLabel: "主按鍵",
    },
    {
      id: "dpad_up",
      label: "方向上",
      symbol: "↑",
      group: "control",
      groupLabel: "方向與肩鍵",
    },
    {
      id: "dpad_right",
      label: "方向右",
      symbol: "→",
      group: "control",
      groupLabel: "方向與肩鍵",
    },
    {
      id: "dpad_down",
      label: "方向下",
      symbol: "↓",
      group: "control",
      groupLabel: "方向與肩鍵",
    },
    {
      id: "dpad_left",
      label: "方向左",
      symbol: "←",
      group: "control",
      groupLabel: "方向與肩鍵",
    },
    {
      id: "l1",
      label: "L1",
      symbol: "L1",
      group: "control",
      groupLabel: "方向與肩鍵",
    },
    {
      id: "r1",
      label: "R1",
      symbol: "R1",
      group: "control",
      groupLabel: "方向與肩鍵",
    },
    {
      id: "l2",
      label: "L2",
      symbol: "L2",
      group: "control",
      groupLabel: "方向與肩鍵",
    },
    {
      id: "r2",
      label: "R2",
      symbol: "R2",
      group: "control",
      groupLabel: "方向與肩鍵",
    },
    {
      id: "l3",
      label: "左搖桿按下",
      symbol: "L3",
      group: "control",
      groupLabel: "方向與肩鍵",
    },
    {
      id: "r3",
      label: "右搖桿按下",
      symbol: "R3",
      group: "control",
      groupLabel: "方向與肩鍵",
    },
    {
      id: "left_stick_up",
      label: "左搖桿上",
      symbol: "L↑",
      group: "stick",
      groupLabel: "搖桿方向",
    },
    {
      id: "left_stick_right",
      label: "左搖桿右",
      symbol: "L→",
      group: "stick",
      groupLabel: "搖桿方向",
    },
    {
      id: "left_stick_down",
      label: "左搖桿下",
      symbol: "L↓",
      group: "stick",
      groupLabel: "搖桿方向",
    },
    {
      id: "left_stick_left",
      label: "左搖桿左",
      symbol: "L←",
      group: "stick",
      groupLabel: "搖桿方向",
    },
    {
      id: "right_stick_up",
      label: "右搖桿上",
      symbol: "R↑",
      group: "stick",
      groupLabel: "搖桿方向",
    },
    {
      id: "right_stick_right",
      label: "右搖桿右",
      symbol: "R→",
      group: "stick",
      groupLabel: "搖桿方向",
    },
    {
      id: "right_stick_down",
      label: "右搖桿下",
      symbol: "R↓",
      group: "stick",
      groupLabel: "搖桿方向",
    },
    {
      id: "right_stick_left",
      label: "右搖桿左",
      symbol: "R←",
      group: "stick",
      groupLabel: "搖桿方向",
    },
    {
      id: "create",
      label: "Create",
      symbol: "CR",
      group: "system",
      groupLabel: "系統按鍵",
    },
    {
      id: "options",
      label: "Options",
      symbol: "OP",
      group: "system",
      groupLabel: "系統按鍵",
    },
    {
      id: "touchpad",
      label: "觸控板按下",
      symbol: "TP",
      group: "system",
      groupLabel: "系統按鍵",
    },
    {
      id: "ps",
      label: "PS 鍵",
      symbol: "PS",
      group: "system",
      groupLabel: "系統按鍵",
    },
    {
      id: "mute",
      label: "麥克風鍵",
      symbol: "MIC",
      group: "system",
      groupLabel: "系統按鍵",
    },
  ];

  const PRESETS = {
    micro_focus: {
      cross: ["Enter"],
      circle: ["Escape"],
      square: ["CodexSmartDelete"],
      triangle: ["ControlLeft", "KeyK"],
      dpad_up: ["ControlLeft", "ShiftLeft", "BracketLeft"],
      dpad_right: ["ControlLeft", "BracketRight"],
      dpad_down: ["ControlLeft", "ShiftLeft", "BracketRight"],
      dpad_left: ["ControlLeft", "BracketLeft"],
      l1: ["ControlLeft", "ShiftLeft", "Tab"],
      r1: ["ControlLeft", "AltLeft", "KeyB"],
      l2: [...CODEX_DICTATION_MAPPING],
      r2: ["Enter"],
      l3: ["ControlLeft", "KeyB"],
      r3: [...CODEX_RIGHT_PANEL_MAPPING],
      ...LEFT_STICK_NAVIGATION,
      right_stick_up: ["MouseWheelUp"],
      right_stick_down: ["MouseWheelDown"],
      create: ["ControlLeft", "AltLeft", "KeyO"],
      options: ["ControlLeft", "KeyP"],
      touchpad: ["ControlLeft", "KeyF"],
      ps: ["CodexFocus"],
      mute: ["ControlLeft", "ShiftLeft", "KeyV"],
    },
    micro_tasks: {
      cross: ["Enter"],
      circle: ["Escape"],
      square: ["CodexSmartDelete"],
      triangle: ["ControlLeft", "KeyK"],
      ...DPAD_CONVERSATION_NAVIGATION,
      l1: ["ControlLeft", "ShiftLeft", "Tab"],
      r1: ["ControlLeft", "AltLeft", "KeyB"],
      l2: [...CODEX_DICTATION_MAPPING],
      r2: ["Enter"],
      l3: ["ControlLeft", "KeyB"],
      r3: [...CODEX_RIGHT_PANEL_MAPPING],
      ...LEFT_STICK_NAVIGATION,
      right_stick_up: ["MouseWheelUp"],
      right_stick_down: ["MouseWheelDown"],
      create: ["ControlLeft", "AltLeft", "KeyO"],
      options: ["ControlLeft", "AltLeft", "KeyR"],
      touchpad: ["ControlLeft", "AltLeft", "KeyA"],
      ps: ["CodexFocus"],
      mute: ["ControlLeft", "ShiftLeft", "KeyV"],
    },
    micro_review: {
      cross: ["Enter"],
      circle: ["Escape"],
      square: ["CodexSmartDelete"],
      triangle: ["ControlLeft", "KeyK"],
      dpad_up: ["ArrowUp"],
      dpad_right: ["ArrowRight"],
      dpad_down: ["ArrowDown"],
      dpad_left: ["ArrowLeft"],
      l1: ["ControlLeft", "ShiftLeft", "Tab"],
      r1: ["ControlLeft", "AltLeft", "KeyB"],
      l2: [...CODEX_DICTATION_MAPPING],
      r2: ["Enter"],
      l3: ["ControlLeft", "KeyB"],
      r3: [...CODEX_RIGHT_PANEL_MAPPING],
      ...LEFT_STICK_NAVIGATION,
      right_stick_up: ["MouseWheelUp"],
      right_stick_down: ["MouseWheelDown"],
      create: ["ControlLeft", "AltLeft", "KeyO"],
      options: ["ControlLeft", "KeyP"],
      touchpad: ["ControlLeft", "KeyF"],
      ps: ["CodexFocus"],
      mute: ["ControlLeft", "ShiftLeft", "KeyV"],
    },
    vibe: {
      cross: ["Enter"],
      circle: [...CONTROLLER_WORKFLOW_MAPPINGS.circle],
      square: [...CONTROLLER_WORKFLOW_MAPPINGS.square],
      triangle: [...CONTROLLER_WORKFLOW_MAPPINGS.triangle],
      ...DPAD_CONVERSATION_NAVIGATION,
      l1: [...CONTROLLER_WORKFLOW_MAPPINGS.l1],
      r1: [...CONTROLLER_WORKFLOW_MAPPINGS.r1],
      l2: [...CONTROLLER_WORKFLOW_MAPPINGS.l2],
      r2: [...CONTROLLER_WORKFLOW_MAPPINGS.r2],
      l3: ["ControlLeft", "KeyB"],
      r3: [...CODEX_RIGHT_PANEL_MAPPING],
      create: ["ControlLeft", "KeyK"],
      options: ["ControlLeft", "ShiftLeft", "KeyP"],
      touchpad: [...CONTROLLER_WORKFLOW_MAPPINGS.touchpad],
      ps: [...CONTROLLER_WORKFLOW_MAPPINGS.ps],
      mute: [...CONTROLLER_WORKFLOW_MAPPINGS.mute],
      ...LEFT_STICK_NAVIGATION,
      right_stick_up: [...CONTROLLER_WORKFLOW_MAPPINGS.right_stick_up],
      right_stick_down: [...CONTROLLER_WORKFLOW_MAPPINGS.right_stick_down],
    },
    navigation: {
      cross: ["Enter"],
      circle: ["Escape"],
      square: ["Tab"],
      triangle: ["Space"],
      dpad_up: ["ArrowUp"],
      dpad_right: ["ArrowRight"],
      dpad_down: ["ArrowDown"],
      dpad_left: ["ArrowLeft"],
      l1: ["PageUp"],
      r1: ["PageDown"],
      l2: ["ControlLeft", "KeyW"],
      r2: ["ControlLeft", "KeyL"],
      l3: ["Home"],
      r3: ["End"],
      create: ["AltLeft", "ArrowLeft"],
      options: ["AltLeft", "ArrowRight"],
      touchpad: ["ControlLeft", "KeyT"],
      ps: ["MetaLeft"],
      mute: ["ControlLeft", "KeyL"],
    },
    blank: {},
  };

  const KEY_LABELS = {
    ControlLeft: "Ctrl",
    ControlRight: "Ctrl(R)",
    ShiftLeft: "Shift",
    ShiftRight: "Shift(R)",
    AltLeft: "Alt",
    AltRight: "AltGr",
    CodexFocus: "開啟 / 切回 Codex",
    CodexDictation: "按住以使用 Codex 聽寫",
    CodexModelNext: "下一個模型",
    CodexModelPrevious: "上一個模型",
    CodexSmartDelete: "刪字 / 長按清空",
    CodexClearInput: "清空輸入",
    MouseWheelUp: "滾輪向上",
    MouseWheelDown: "滾輪向下",
    MetaLeft: "Win",
    MetaRight: "Win(R)",
    Enter: "Enter",
    Escape: "Esc",
    Space: "Space",
    Tab: "Tab",
    Backspace: "Backspace",
    ArrowUp: "↑",
    ArrowRight: "→",
    ArrowDown: "↓",
    ArrowLeft: "←",
    PageUp: "PageUp",
    PageDown: "PageDown",
    Backquote: "`",
    Slash: "/",
    Semicolon: ";",
    Quote: "'",
    Comma: ",",
    Period: ".",
    Minus: "-",
    Equal: "=",
    BracketLeft: "[",
    BracketRight: "]",
    Backslash: "\\",
    Delete: "Delete",
    Insert: "Insert",
    Home: "Home",
    End: "End",
  };
  const ACTION_NAMES = {
    CodexFocus: "開啟 / 切回 Codex",
    CodexDictation: "按住以使用 Codex 聽寫",
    CodexModelNext: "循環切換模型",
    CodexModelPrevious: "反向切換模型",
    CodexSmartDelete: "刪字 / 長按清空",
    CodexClearInput: "清空輸入",
    Backspace: "刪除一字",
    MouseWheelUp: "向上捲動",
    MouseWheelDown: "向下捲動",
    Enter: "確認 / 送出",
    Escape: "取消 / 關閉",
    "ControlLeft+ShiftLeft+KeyV": "切換語音對話",
    "ControlLeft+ShiftLeft+KeyD": "Codex 切換聽寫",
    "MetaLeft+KeyH": "Windows 語音輸入",
    "ControlLeft+KeyK": "開啟指令選單",
    "ControlLeft+ShiftLeft+Tab": "上一個最近任務",
    "ControlLeft+Tab": "下一個最近任務",
    "ControlLeft+AltLeft+KeyA": "下一個待處理任務",
    "ControlLeft+ShiftLeft+BracketLeft": "上一則對話",
    "ControlLeft+ShiftLeft+BracketRight": "下一則對話",
    "ControlLeft+BracketLeft": "上一步",
    "ControlLeft+BracketRight": "向前",
    "ControlLeft+AltLeft+KeyO": "新增獨立對話",
    "ControlLeft+AltLeft+KeyP": "切換釘選",
    "ControlLeft+AltLeft+KeyR": "重新命名對話",
    "ControlLeft+KeyF": "尋找",
    "ControlLeft+KeyP": "搜尋檔案",
    "ControlLeft+KeyB": "切換側邊欄",
    "ControlLeft+AltLeft+KeyB": "切換側邊面板",
    "ControlLeft+KeyJ": "切換底部面板",
    "ControlLeft+Backquote": "開啟終端",
    ArrowUp: "向上選取",
    ArrowRight: "向右選取",
    ArrowDown: "向下選取",
    ArrowLeft: "向左選取",
    PageUp: "向上捲動",
    PageDown: "向下捲動",
  };
  const DISPATCH_LABELS = {
    touchpad_swipe_left: "觸控板左滑",
    touchpad_swipe_right: "觸控板右滑",
  };

  const state = {
    serviceOnline: false,
    controllerConnected: false,
    mappingEnabled: false,
    profile: UI_PROFILES.has(localStorage.getItem("vibeHubProfile"))
      ? localStorage.getItem("vibeHubProfile")
      : "vibe",
    mappings: {},
    touchpadGestures: savedTouchpadGestures(),
    touchpadGesturesLoaded: false,
    filter: "all",
    captureButton: null,
    captureCodes: [],
    captureRequestVersion: 0,
    capturePollTimer: 0,
    hoveredTwin: null,
    selectedButton: "mute",
    remoteLoaded: false,
    statusRequestPending: false,
    lastReconnectAttempt: 0,
    lastDispatchAt: 0,
    lastInjectionError: null,
    pressed: new Set(),
    microActionTimer: 0,
    color: "#38DDB2",
    brightness: 100,
    players: [false, false, true, false, false],
    effect: "static",
    speed: 3,
    codex: { enabled: true, available: false, state: "idle", profile: null },
    triggers: savedTriggers(),
    triggersLoaded: false,
    restoreSavedTriggers: HAS_SAVED_TRIGGERS,
    triggerPositions: { left: 0, right: 0 },
  };

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const elements = {
    connectionDot: $("#connectionDot"),
    connectionLabel: $("#connectionLabel"),
    mappingToggle: $("#mappingToggle"),
    mappingToggleLabel: $("#mappingToggleLabel"),
    serviceHealth: $("#serviceHealth"),
    serviceHealthLabel: $("#serviceHealthLabel"),
    controllerHealth: $("#controllerHealth"),
    codexHealth: $("#codexHealth"),
    codexHealthLabel: $("#codexHealthLabel"),
    deviceName: $("#deviceName"),
    deviceId: $("#deviceId"),
    transport: $("#transportValue"),
    reportCount: $("#reportCount"),
    reportAge: $("#reportAge"),
    dispatchCount: $("#dispatchCount"),
    reconnect: $("#reconnectButton"),
    sidebarFocusCodex: $("#sidebarFocusCodexButton"),
    deviceReconnect: $("#deviceReconnectButton"),
    deviceTestFeedback: $("#deviceTestFeedbackButton"),
    deviceResetProfile: $("#deviceResetProfileButton"),
    serviceDot: $("#serviceDot"),
    serviceState: $("#serviceState"),
    inputBadge: $("#inputBadge"),
    profile: $("#profileSelect"),
    resetProfile: $("#resetProfileButton"),
    mappingList: $("#mappingList"),
    mappingCount: $("#mappingCount"),
    mappingPanel: $(".mapping-panel"),
    toggleAllMappings: $("#toggleAllMappingsButton"),
    selectedButtonSymbol: $("#selectedButtonSymbol"),
    selectedButtonName: $("#selectedButtonName"),
    selectedButtonAction: $("#selectedButtonAction"),
    selectedButtonShortcut: $("#selectedButtonShortcut"),
    selectedButtonReliability: $("#selectedButtonReliability"),
    selectedCapture: $("#selectedCaptureButton"),
    selectedClear: $("#selectedClearButton"),
    pressedButtons: $("#pressedButtons"),
    leftAxis: $("#leftAxisValue"),
    rightAxis: $("#rightAxisValue"),
    trigger: $("#triggerValue"),
    touchpadPosition: $("#touchpadPosition"),
    touchpadGestureToggle: $("#touchpadGestureToggle"),
    touchpadGestureState: $("#touchpadGestureState"),
    touchpadGestureThreshold: $("#touchpadGestureThreshold"),
    touchpadGestureThresholdOutput: $("#touchpadGestureThresholdOutput"),
    touchpadMuteToggle: $("#touchpadMuteToggle"),
    touchpadDriverLeft: $("#touchpadDriverLeft"),
    touchpadDriverRight: $("#touchpadDriverRight"),
    touchpadLiveBadge: $("#touchpadLiveBadge"),
    touchpadLiveCoordinates: $("#touchpadLiveCoordinates"),
    touchpadSurface: $("#touchpadSurface"),
    touchpadCursor: $("#touchpadCursor"),
    touchpadGestureDelta: $("#touchpadGestureDelta"),
    touchpadLastGesture: $("#touchpadLastGesture"),
    leftStick: $("#leftStick"),
    rightStick: $("#rightStick"),
    activity: $("#activityMessage"),
    activityTime: $("#activityTime"),
    twinReadout: $("#twinReadout"),
    twinButtonName: $("#twinButtonName"),
    twinMappingValue: $("#twinMappingValue"),
    lightOutputBadge: $("#lightOutputBadge"),
    effectTitle: $("#effectTitle"),
    colorChip: $("#colorChip"),
    lightPreview: $("#lightPreview"),
    previewPlayers: $("#previewPlayers"),
    telemetryHex: $("#telemetryHex"),
    telemetryRgb: $("#telemetryRgb"),
    telemetryMask: $("#telemetryMask"),
    colorWheel: $("#colorWheel"),
    hex: $("#hexInput"),
    red: $("#redInput"),
    green: $("#greenInput"),
    blue: $("#blueInput"),
    brightness: $("#brightness"),
    brightnessOutput: $("#brightnessOutput"),
    speed: $("#speed"),
    speedOutput: $("#speedOutput"),
    playerOutput: $("#playerOutput"),
    playerLeds: $("#playerLeds"),
    apply: $("#applyButton"),
    turnOff: $("#turnOffButton"),
    codexStatusToggle: $("#codexStatusToggle"),
    codexStateDot: $("#codexStateDot"),
    codexStateLabel: $("#codexStateLabel"),
    codexStateMeta: $("#codexStateMeta"),
    triggerOutputBadge: $("#triggerOutputBadge"),
    applyTriggers: $("#applyTriggersButton"),
    disableTriggers: $("#disableTriggersButton"),
    triggerGunPreset: $("#triggerGunPreset"),
    microHero: $("#microHero"),
    microModeBadge: $("#microModeBadge"),
    microStateLabel: $("#microStateLabel"),
    microStateMeta: $("#microStateMeta"),
    microServiceVital: $("#microServiceVital"),
    microControllerVital: $("#microControllerVital"),
    microCodexVital: $("#microCodexVital"),
    microInputBadge: $("#microInputBadge"),
    microCoreActions: $("#microCoreActions"),
    microLastAction: $("#microLastAction"),
    microLastActionIcon: $("#microLastActionIcon"),
    microLastActionMeta: $("#microLastActionMeta"),
    focusCodex: $("#focusCodexButton"),
    testFeedback: $("#testFeedbackButton"),
    openMapping: $("#openMappingButton"),
    dialog: $("#messageDialog"),
    dialogEyebrow: $("#dialogEyebrow"),
    dialogTitle: $("#dialogTitle"),
    dialogMessage: $("#dialogMessage"),
    dialogClose: $("#dialogCloseButton"),
  };

  const cloneMappings = (mappings) =>
    Object.fromEntries(
      Object.entries(mappings).map(([button, codes]) => [button, [...codes]]),
    );
  const mappingsEqual = (left, right) => {
    const leftKeys = Object.keys(left || {})
      .filter((key) => left[key]?.length)
      .sort();
    const rightKeys = Object.keys(right || {})
      .filter((key) => right[key]?.length)
      .sort();
    return (
      leftKeys.length === rightKeys.length &&
      leftKeys.every((key, index) => {
        const leftCodes = left[key] || [];
        const rightCodes = right[rightKeys[index]] || [];
        return (
          key === rightKeys[index] &&
          leftCodes.length === rightCodes.length &&
          leftCodes.every((code, codeIndex) => code === rightCodes[codeIndex])
        );
      })
    );
  };
  const clampByte = (value) =>
    Math.max(0, Math.min(255, Number.parseInt(value, 10) || 0));
  const timestamp = () =>
    new Intl.DateTimeFormat("zh-Hant-TW", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    }).format(new Date());
  const playerMask = () =>
    state.players.reduce((mask, on, index) => mask | (on ? 1 << index : 0), 0);
  const rgbFromHex = (hex) => {
    const match = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(
      String(hex).trim(),
    );
    return match
      ? [parseInt(match[1], 16), parseInt(match[2], 16), parseInt(match[3], 16)]
      : null;
  };
  const hexFromRgb = (rgb) =>
    `#${rgb
      .map((value) => clampByte(value).toString(16).padStart(2, "0"))
      .join("")
      .toUpperCase()}`;
  const hsvToRgb = (hue, saturation, value = 1) => {
    const chroma = value * saturation;
    const section = hue / 60;
    const second = chroma * (1 - Math.abs((section % 2) - 1));
    const channels = [
      [chroma, second, 0],
      [second, chroma, 0],
      [0, chroma, second],
      [0, second, chroma],
      [second, 0, chroma],
      [chroma, 0, second],
    ][Math.floor(section) % 6];
    const match = value - chroma;
    return channels.map((channel) => Math.round((channel + match) * 255));
  };
  const rgbToHsv = ([red, green, blue]) => {
    const [r, g, b] = [red, green, blue].map((channel) => channel / 255);
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    const delta = max - min;
    let hue = 0;
    if (delta)
      hue =
        ((max === r
          ? (g - b) / delta
          : max === g
            ? 2 + (b - r) / delta
            : 4 + (r - g) / delta) *
          60 +
          360) %
        360;
    return [hue, max === 0 ? 0 : delta / max, max];
  };

  function setActivity(message) {
    elements.activity.textContent = message;
    elements.activityTime.textContent = timestamp();
  }

  function showDialog(title, message, eyebrow = "CODEX CONTROLLER") {
    elements.dialogEyebrow.textContent = eyebrow;
    elements.dialogTitle.textContent = title;
    elements.dialogMessage.textContent = message;
    if (!elements.dialog.open) elements.dialog.showModal();
  }

  function formatShortcut(codes) {
    return codes?.length
      ? codes
          .map(
            (code) =>
              KEY_LABELS[code] ||
              code.replace(/^Key/, "").replace(/^Digit/, ""),
          )
          .join(" + ")
      : "未映射";
  }

  function formatTwinShortcut(codes) {
    return codes?.length
      ? codes
          .map(
            (code) =>
              KEY_LABELS[code] ||
              code.replace(/^Key/, "").replace(/^Digit/, ""),
          )
          .join("+")
      : "—";
  }

  const shortcutSignature = (codes = []) => codes.join("+");

  function shortcutActionName(codes) {
    if (!codes?.length) return "尚未指定";
    return ACTION_NAMES[shortcutSignature(codes)] || formatShortcut(codes);
  }

  function shortcutReliability(codes) {
    const signature = shortcutSignature(codes || []);
    if (!signature) return { id: "empty", label: "未映射" };
    if (signature === "CodexModelNext" || signature === "CodexModelPrevious")
      return { id: "experimental", label: "實驗性 · 選單操作" };
    if (
      [
        "CodexFocus",
        "CodexDictation",
        "CodexSmartDelete",
        "MouseWheelUp",
        "MouseWheelDown",
      ].includes(signature)
    )
      return { id: "system", label: "系統穩定" };
    if (
      ACTION_NAMES[signature] &&
      !signature.startsWith("Arrow") &&
      !signature.startsWith("Page")
    )
      return { id: "native", label: "Codex 原生" };
    return { id: "system", label: "系統穩定" };
  }

  function renderSelectedMapping() {
    const button =
      BUTTONS.find((item) => item.id === state.selectedButton) || BUTTONS[0];
    const codes = state.mappings[button.id] || [];
    const reliability = shortcutReliability(codes);
    elements.selectedButtonSymbol.textContent = button.symbol;
    elements.selectedButtonName.textContent = button.label;
    elements.selectedButtonAction.textContent = shortcutActionName(codes);
    elements.selectedButtonShortcut.textContent = formatShortcut(codes);
    elements.selectedButtonReliability.className = `reliability-chip is-${reliability.id}`;
    elements.selectedButtonReliability.innerHTML = `<i></i>${reliability.label}`;
    elements.selectedCapture.textContent =
      state.captureButton === button.id ? "請按鍵盤快捷鍵…" : "變更快捷鍵";
    elements.selectedCapture.classList.toggle(
      "is-capturing",
      state.captureButton === button.id,
    );
    $$(".twin-node[data-button]").forEach((node) =>
      node.classList.toggle(
        "is-selected",
        node.dataset.button === state.selectedButton,
      ),
    );
    $$(".mapping-row[data-mapping-row]").forEach((row) =>
      row.classList.toggle(
        "is-selected",
        row.dataset.mappingRow === state.selectedButton,
      ),
    );
  }

  function selectMappingButton(buttonId) {
    if (!BUTTONS.some((button) => button.id === buttonId)) return;
    state.selectedButton = buttonId;
    showTwinReadout(buttonId, false);
    renderSelectedMapping();
    const label = BUTTONS.find((button) => button.id === buttonId)?.label;
    setActivity(`已選取 ${label}`);
  }

  function setHealthClass(element, status) {
    element.classList.toggle("is-online", status === "online");
    element.classList.toggle("is-warning", status === "warning");
    element.classList.toggle("is-error", status === "error");
  }

  function setVital(element, status, label) {
    element.classList.toggle("is-online", status === "online");
    element.classList.toggle("is-warning", status === "warning");
    element.classList.toggle("is-error", status === "error");
    element.querySelector("strong").textContent = label;
  }

  function renderSystemHealth() {
    setHealthClass(
      elements.serviceHealth,
      state.serviceOnline ? "online" : "error",
    );
    elements.serviceHealthLabel.textContent = state.serviceOnline
      ? "在線"
      : "離線";
    setHealthClass(
      elements.controllerHealth,
      state.controllerConnected
        ? "online"
        : state.serviceOnline
          ? "warning"
          : "error",
    );
    elements.connectionLabel.textContent = state.controllerConnected
      ? "已連接"
      : state.serviceOnline
        ? "等待中"
        : "不可用";
    const codexDisplayState = state.codex.lastError
      ? "error"
      : state.codex.state;
    const codexStatus = !state.serviceOnline
      ? "error"
      : state.codex.lastError
        ? "error"
        : state.codex.available
          ? "online"
          : "warning";
    setHealthClass(elements.codexHealth, codexStatus);
    elements.codexHealthLabel.textContent = state.codex.lastError
      ? "錯誤"
      : state.codex.available
        ? CODEX_STATUS_META[codexDisplayState]?.label || "已連接"
        : "等待狀態";
    setVital(
      elements.microServiceVital,
      state.serviceOnline ? "online" : "error",
      state.serviceOnline ? "在線" : "離線",
    );
    setVital(
      elements.microControllerVital,
      state.controllerConnected
        ? "online"
        : state.serviceOnline
          ? "warning"
          : "error",
      state.controllerConnected ? "已連接" : "等待 USB",
    );
    setVital(
      elements.microCodexVital,
      codexStatus,
      state.codex.lastError
        ? "輸出錯誤"
        : state.codex.available
          ? CODEX_STATUS_META[codexDisplayState]?.label || "已連接"
          : "等待活動",
    );

    let heroState = "offline";
    let title = "本機服務尚未連接";
    let meta = "啟動背景服務後，控制中心會自動恢復目前配置。";
    if (state.serviceOnline && !state.controllerConnected) {
      heroState = "idle";
      title = "控制中心在線，等待 DualSense";
      meta = "插入 USB 線後會自動連接；設定與模式已保存在本機服務。";
    } else if (
      state.serviceOnline &&
      state.controllerConnected &&
      !state.codex.available
    ) {
      heroState = "idle";
      title = "DualSense 已就緒";
      meta = "按下 PS 鍵切回 Codex，開始任務後即可取得即時狀態。";
    } else if (state.serviceOnline && state.controllerConnected) {
      heroState =
        codexDisplayState in CODEX_STATUS_META ? codexDisplayState : "idle";
      const statusMeta = CODEX_STATUS_META[heroState] || CODEX_STATUS_META.idle;
      title = state.codex.lastError
        ? "狀態輸出需要重新連接"
        : `Codex ${statusMeta.label}`;
      if (heroState === "approval")
        meta = `有 ${state.codex.pendingRequests || 1} 個動作需要你確認；按 × 接受或 ○ 取消目前選項。`;
      else if (heroState === "working")
        meta = `正在處理 ${state.codex.inflightTurns || 1} 個任務；藍色呼吸燈表示可以先讓它繼續工作。`;
      else if (heroState === "complete")
        meta = "任務已完成並有新結果；綠燈會短暫保留，方便你立即注意。";
      else if (heroState === "error")
        meta = "Codex 或控制器輸出發生錯誤；控制中心會自動重試連線。";
      else
        meta = "系統已待命；你可以按 MIC 說話，或按 PS 鍵將 Codex 帶到前景。";
    }
    elements.microHero.dataset.state = heroState;
    elements.microStateLabel.textContent = title;
    elements.microStateMeta.textContent = meta;
  }

  function renderMicroCoreActions() {
    const fragment = document.createDocumentFragment();
    CORE_BUTTON_IDS.forEach((buttonId) => {
      const button = BUTTONS.find((item) => item.id === buttonId);
      const codes = state.mappings[buttonId] || [];
      const tile = document.createElement("button");
      tile.type = "button";
      tile.className = "micro-action-tile";
      tile.dataset.selectButton = buttonId;
      tile.classList.toggle("is-active", state.pressed.has(buttonId));
      tile.innerHTML = `<span class="micro-action-key">${button?.symbol || buttonId}</span><div><strong>${shortcutActionName(codes)}</strong><small>${formatShortcut(codes)}</small></div>`;
      fragment.append(tile);
    });
    elements.microCoreActions.replaceChildren(fragment);
  }

  function updateProfilePresentation() {
    const meta = PROFILE_META[state.profile] || PROFILE_META.vibe;
    elements.microModeBadge.textContent = `目前配置 · ${meta.short}`;
    $$("[data-micro-profile]").forEach((card) =>
      card.classList.toggle(
        "is-active",
        card.dataset.microProfile === state.profile,
      ),
    );
  }

  function showMicroLastAction(buttonId, codes) {
    const button = BUTTONS.find((item) => item.id === buttonId);
    const label =
      button?.label || DISPATCH_LABELS[buttonId] || buttonId || "控制器動作";
    const reliability = shortcutReliability(codes);
    elements.microLastActionIcon.textContent = button?.symbol || "↔";
    elements.microLastAction.textContent = `${label} · ${shortcutActionName(codes)}`;
    elements.microLastActionMeta.textContent = `${formatShortcut(codes)} · ${reliability.label}`;
    const panel = elements.microLastAction.closest(".micro-last-action");
    panel.classList.add("is-live");
    clearTimeout(state.microActionTimer);
    state.microActionTimer = setTimeout(
      () => panel.classList.remove("is-live"),
      750,
    );
  }

  function updateTwinMappings() {
    $$("[data-map-for]").forEach((label) => {
      const buttonId = label.dataset.mapFor;
      const button = BUTTONS.find((item) => item.id === buttonId);
      const codes = state.mappings[buttonId] || [];
      label.textContent = formatTwinShortcut(codes);
      label.title = formatShortcut(codes);
      const node = label.closest(".twin-node");
      node.classList.toggle("is-capturing", state.captureButton === buttonId);
      node.setAttribute(
        "aria-label",
        `${button?.label || buttonId}，${state.captureButton === buttonId ? "等待輸入" : formatShortcut(codes)}`,
      );
    });
    if (state.hoveredTwin) showTwinReadout(state.hoveredTwin, false);
  }

  function showTwinReadout(buttonId, live = false) {
    const button = BUTTONS.find((item) => item.id === buttonId);
    if (!button) return;
    elements.twinButtonName.textContent = button.label;
    elements.twinMappingValue.textContent = formatShortcut(
      state.mappings[buttonId] || [],
    );
    elements.twinReadout.classList.toggle("is-live", live);
  }

  function clearTwinReadout() {
    elements.twinButtonName.textContent = "等待輸入";
    elements.twinMappingValue.textContent = "—";
    elements.twinReadout.classList.remove("is-live");
  }

  function savedProfiles() {
    try {
      const saved = JSON.parse(localStorage.getItem("vibeHubMappings") || "{}");
      const savedSchema = Number(
        localStorage.getItem("vibeHubMappingSchema") || 0,
      );
      if (savedSchema < MAPPING_SCHEMA_VERSION) {
        if (saved.vibe) {
          CLEARED_STICK_INPUTS.forEach((input) => {
            delete saved.vibe[input];
          });
          Object.entries(LEFT_STICK_NAVIGATION).forEach(([input, codes]) => {
            saved.vibe[input] = [...codes];
          });
          Object.entries(DPAD_CONVERSATION_NAVIGATION).forEach(
            ([input, codes]) => {
              saved.vibe[input] = [...codes];
            },
          );
          delete saved.vibe.r1;
          const legacyWorkflowMappings = {
            circle: ["CodexNavigateBack"],
            triangle: ["ControlLeft", "ShiftLeft", "KeyP"],
            l1: ["ControlLeft", "KeyZ"],
            ps: ["MetaLeft"],
            r2: ["ControlLeft", "Enter"],
            touchpad: ["Tab"],
            mute: ["ControlLeft", "Slash"],
          };
          Object.entries(CONTROLLER_WORKFLOW_MAPPINGS).forEach(
            ([input, codes]) => {
              const current = saved.vibe[input];
              const legacy = legacyWorkflowMappings[input];
              const isLegacyDefault =
                Array.isArray(current) &&
                current.length === legacy.length &&
                current.every((code, index) => code === legacy[index]);
              if (!(input in saved.vibe) || isLegacyDefault)
                saved.vibe[input] = [...codes];
            },
          );
          localStorage.setItem("vibeHubMappings", JSON.stringify(saved));
        }
        const legacyMicroTouchpadMappings = {
          micro_focus: ["ControlLeft", "KeyJ"],
          micro_tasks: ["ControlLeft", "KeyB"],
          micro_review: ["ControlLeft", "KeyJ"],
        };
        Object.entries(legacyMicroTouchpadMappings).forEach(
          ([profile, legacy]) => {
            const current = saved[profile]?.touchpad;
            const isLegacyDefault =
              Array.isArray(current) &&
              current.length === legacy.length &&
              current.every((code, index) => code === legacy[index]);
            if (isLegacyDefault)
              saved[profile].touchpad = [...CODEX_DICTATION_MAPPING];
          },
        );
        const microProfiles = ["micro_focus", "micro_tasks", "micro_review"];
        microProfiles.forEach((profile) => {
          if (!saved[profile]) return;
          saved[profile].l2 = [...CODEX_DICTATION_MAPPING];
          saved[profile].touchpad =
            profile === "micro_tasks"
              ? ["ControlLeft", "AltLeft", "KeyA"]
              : ["ControlLeft", "KeyF"];
          saved[profile].square = ["CodexSmartDelete"];
          saved[profile].r1 = ["ControlLeft", "AltLeft", "KeyB"];
          saved[profile].r3 = [...CODEX_RIGHT_PANEL_MAPPING];
          saved[profile].right_stick_up = ["MouseWheelUp"];
          saved[profile].right_stick_down = ["MouseWheelDown"];
        });
        if (saved.vibe) {
          saved.vibe.l3 = ["ControlLeft", "KeyB"];
          saved.vibe.r3 = [...CODEX_RIGHT_PANEL_MAPPING];
          saved.vibe.l2 = [...CODEX_DICTATION_MAPPING];
          saved.vibe.touchpad = ["ControlLeft", "KeyF"];
        }
        localStorage.setItem("vibeHubMappings", JSON.stringify(saved));
        localStorage.setItem(
          "vibeHubMappingSchema",
          String(MAPPING_SCHEMA_VERSION),
        );
      }
      return saved;
    } catch {
      return {};
    }
  }

  function loadProfile(profile) {
    const saved = savedProfiles();
    state.profile = UI_PROFILES.has(profile) ? profile : "vibe";
    state.mappings = cloneMappings(
      saved[state.profile] || PRESETS[state.profile],
    );
    elements.profile.value = state.profile;
    localStorage.setItem("vibeHubProfile", state.profile);
    renderMappings();
    updateProfilePresentation();
  }

  function saveProfile() {
    const saved = savedProfiles();
    saved[state.profile] = cloneMappings(state.mappings);
    localStorage.setItem("vibeHubMappings", JSON.stringify(saved));
  }

  function renderMappings() {
    const groups = ["face", "control", "stick", "system"];
    const fragment = document.createDocumentFragment();
    let mapped = 0;
    BUTTONS.forEach((button) => {
      if (state.mappings[button.id]?.length) mapped += 1;
    });
    elements.mappingCount.textContent = `${mapped} / ${BUTTONS.length}`;
    groups.forEach((group) => {
      if (state.filter !== "all" && state.filter !== group) return;
      const groupButtons = BUTTONS.filter((button) => button.group === group);
      const heading = document.createElement("div");
      heading.className = "mapping-group-title";
      heading.textContent = groupButtons[0].groupLabel.toUpperCase();
      fragment.append(heading);
      groupButtons.forEach((button) => {
        const row = document.createElement("div");
        row.className = "mapping-row";
        row.dataset.mappingRow = button.id;
        row.classList.toggle(
          "is-overridden",
          button.id === "touchpad" && state.touchpadGestures.enabled,
        );
        const codes = state.mappings[button.id] || [];
        const reliability = shortcutReliability(codes);
        const capturing = state.captureButton === button.id;
        row.innerHTML = `<div class="controller-key-label"><span class="controller-key-symbol">${button.symbol}</span><span class="controller-key-copy"><span>${button.label}</span><small class="mapping-stability is-${reliability.id}">${reliability.label}</small></span></div><button class="shortcut-button${codes.length ? "" : " is-empty"}${capturing ? " is-capturing" : ""}" type="button" data-capture="${button.id}">${capturing ? (state.captureCodes.length ? formatShortcut(state.captureCodes) : "請按鍵…") : formatShortcut(codes)}</button><button class="clear-mapping" type="button" data-clear="${button.id}" title="清除映射" aria-label="清除 ${button.label} 映射">×</button>`;
        fragment.append(row);
      });
    });
    elements.mappingList.replaceChildren(fragment);
    updateTwinMappings();
    renderMicroCoreActions();
    renderSelectedMapping();
    updateProfilePresentation();
  }

  function renderTouchpadGestures(
    live = {},
    axes = {},
    touchpadPressed = false,
  ) {
    elements.touchpadGestureToggle.checked = state.touchpadGestures.enabled;
    elements.touchpadMuteToggle.checked = state.touchpadGestures.muteOnSwitch;
    elements.touchpadGestureThreshold.value = state.touchpadGestures.threshold;
    elements.touchpadGestureThresholdOutput.textContent = `${state.touchpadGestures.threshold} px`;
    updateRange(elements.touchpadGestureThreshold);
    const driverReady = Boolean(live.driverAvailable);
    const driverLabel = driverReady ? "虛擬 HID 在線" : "等待 HID 驅動";
    elements.touchpadDriverLeft.textContent = driverLabel;
    elements.touchpadDriverRight.textContent = driverLabel;
    const lastGesture = !driverReady
      ? "需要虛擬 HID 驅動"
      : live.lastGesture === "left"
        ? "左滑已觸發"
        : live.lastGesture === "right"
          ? "右滑已觸發"
          : "待機";
    elements.touchpadGestureState.textContent = live.active
      ? "追蹤中"
      : lastGesture;
    elements.touchpadGestureState.classList.toggle(
      "is-live",
      Boolean(live.active),
    );
    const touchActive = Boolean(axes.touchActive);
    const touchX = Number(axes.touchX || 0);
    const touchY = Number(axes.touchY || 0);
    elements.touchpadLiveBadge.textContent = live.active
      ? "手勢追蹤中"
      : touchActive
        ? "觸點在線"
        : "等待觸點";
    elements.touchpadLiveBadge.classList.toggle("is-live", touchActive);
    elements.touchpadLiveBadge.classList.toggle(
      "is-active",
      Boolean(live.active),
    );
    elements.touchpadLiveCoordinates.textContent = touchActive
      ? `${touchX} / ${touchY}`
      : "— / —";
    elements.touchpadCursor.classList.toggle("is-visible", touchActive);
    elements.touchpadCursor.style.setProperty(
      "--touch-x",
      `${Math.max(0, Math.min(100, (touchX / 1919) * 100))}%`,
    );
    elements.touchpadCursor.style.setProperty(
      "--touch-y",
      `${Math.max(0, Math.min(100, (touchY / 1079) * 100))}%`,
    );
    elements.touchpadSurface.classList.toggle("is-pressed", touchpadPressed);
    elements.touchpadSurface.classList.toggle(
      "is-tracking",
      Boolean(live.active),
    );
    const delta =
      live.startX == null || live.currentX == null
        ? 0
        : Number(live.currentX) - Number(live.startX);
    elements.touchpadGestureDelta.textContent = `${delta > 0 ? "+" : ""}${delta} px`;
    elements.touchpadLastGesture.textContent =
      live.lastGesture === "left"
        ? "左滑"
        : live.lastGesture === "right"
          ? "右滑"
          : "—";
  }

  function setServiceState(online) {
    state.serviceOnline = online;
    elements.serviceDot.classList.toggle("is-online", online);
    elements.serviceState.textContent = online
      ? "本機服務在線"
      : "本機服務離線";
    if (!online) {
      state.controllerConnected = false;
      elements.connectionDot.classList.remove("is-online");
      elements.connectionLabel.textContent = "本機服務未連接";
      elements.transport.textContent = "USB / 等待";
      elements.inputBadge.textContent = "等待輸入";
      elements.inputBadge.classList.remove("is-live");
    }
    renderSystemHealth();
  }

  function updateInputStatus(input) {
    state.controllerConnected = Boolean(input.connected);
    state.mappingEnabled = Boolean(input.enabled);
    elements.mappingToggle.checked = state.mappingEnabled;
    elements.mappingToggleLabel.textContent = state.mappingEnabled
      ? "執行中"
      : "已停用";
    elements.connectionDot.classList.toggle(
      "is-online",
      state.controllerConnected,
    );
    elements.connectionLabel.textContent = state.controllerConnected
      ? "DualSense 已連接"
      : "等待 DualSense";
    elements.deviceName.textContent = state.controllerConnected
      ? "DualSense Wireless Controller"
      : "DualSense";
    elements.deviceId.textContent = `054C / ${input.productId || "----"}`;
    elements.transport.textContent = state.controllerConnected
      ? "USB / HID"
      : "USB / 等待";
    elements.reportCount.textContent = Number(
      input.reports || 0,
    ).toLocaleString("zh-Hant-TW");
    elements.dispatchCount.textContent = Number(
      input.dispatchCount || 0,
    ).toLocaleString("zh-Hant-TW");
    elements.reportAge.textContent =
      input.reportAgeMs == null
        ? "-- ms"
        : `${Math.min(input.reportAgeMs, 9999)} ms`;
    const dispatchAt = Number(input.lastDispatchAt || 0);
    if (dispatchAt > state.lastDispatchAt) {
      state.lastDispatchAt = dispatchAt;
      const button = BUTTONS.find(
        (item) => item.id === input.lastDispatchedButton,
      );
      const label =
        button?.label ||
        DISPATCH_LABELS[input.lastDispatchedButton] ||
        input.lastDispatchedButton;
      const nativeTouchGesture =
        input.lastDispatchedButton?.startsWith("touchpad_swipe_") &&
        input.touchpadGestures?.switchMode === "touch-injection";
      setActivity(
        nativeTouchGesture
          ? `${label} → Windows 原生四指手勢已注入`
          : `${label} → ${formatShortcut(input.lastShortcut)} 已派發`,
      );
      showMicroLastAction(input.lastDispatchedButton, input.lastShortcut || []);
    }
    if (
      input.lastInjectionError &&
      input.lastInjectionError !== state.lastInjectionError
    ) {
      state.lastInjectionError = input.lastInjectionError;
      setActivity(`按鍵映射注入失敗：${input.lastInjectionError}`);
    } else if (!input.lastInjectionError) {
      state.lastInjectionError = null;
    }
    if (
      input.touchpadGestures?.switchError &&
      input.touchpadGestures.switchError !== state.lastInjectionError
    ) {
      state.lastInjectionError = input.touchpadGestures.switchError;
      setActivity(
        input.touchpadGestures.switchMode === "driver-required"
          ? "原生四指手勢需要虛擬 HID 精密觸控板驅動"
          : `觸控板手勢注入失敗：${input.touchpadGestures.switchError}`,
      );
    }
    const pressed = new Set(input.pressed || []);
    state.pressed = pressed;
    $$("#controllerVisual [data-button]").forEach((element) =>
      element.classList.toggle(
        "is-pressed",
        pressed.has(element.dataset.button),
      ),
    );
    $$(".micro-action-tile[data-button]").forEach((element) =>
      element.classList.toggle(
        "is-active",
        pressed.has(element.dataset.button),
      ),
    );
    const names = BUTTONS.filter((button) => pressed.has(button.id)).map(
      (button) => button.label,
    );
    elements.pressedButtons.textContent = names.length
      ? names.join(" / ")
      : "—";
    elements.inputBadge.textContent = pressed.size
      ? `${pressed.size} 個按鍵`
      : state.controllerConnected
        ? "輸入在線"
        : "等待輸入";
    elements.inputBadge.classList.toggle("is-live", state.controllerConnected);
    elements.microInputBadge.textContent = pressed.size
      ? `${pressed.size} 個按鍵`
      : state.controllerConnected
        ? "輸入在線"
        : "等待輸入";
    elements.microInputBadge.classList.toggle(
      "is-live",
      state.controllerConnected,
    );
    const activeTwinButton = BUTTONS.find((button) => pressed.has(button.id));
    if (activeTwinButton) showTwinReadout(activeTwinButton.id, true);
    else if (state.hoveredTwin) showTwinReadout(state.hoveredTwin, false);
    else clearTwinReadout();
    const axes = input.axes || {};
    const lx = Number(axes.leftX || 0);
    const ly = Number(axes.leftY || 0);
    const rx = Number(axes.rightX || 0);
    const ry = Number(axes.rightY || 0);
    elements.leftAxis.textContent = `${lx.toFixed(2)} / ${ly.toFixed(2)}`;
    elements.rightAxis.textContent = `${rx.toFixed(2)} / ${ry.toFixed(2)}`;
    elements.trigger.textContent = `${Math.round(Number(axes.leftTrigger || 0) * 100)}% / ${Math.round(Number(axes.rightTrigger || 0) * 100)}%`;
    elements.touchpadPosition.textContent = axes.touchActive
      ? `${axes.touchX} / ${axes.touchY}`
      : "—";
    state.triggerPositions.left = Number(axes.leftTrigger || 0);
    state.triggerPositions.right = Number(axes.rightTrigger || 0);
    updateTriggerPositions();
    elements.leftStick.style.transform = `translate(${lx * 7}px, ${ly * 7}px)`;
    elements.rightStick.style.transform = `translate(${rx * 7}px, ${ry * 7}px)`;
    if (
      !state.remoteLoaded &&
      input.enabled &&
      input.mappings &&
      Object.keys(input.mappings).length
    ) {
      state.remoteLoaded = true;
      state.mappings = cloneMappings(input.mappings);
      const saved = savedProfiles();
      const profileMatch = [...UI_PROFILES].find((profile) =>
        mappingsEqual(saved[profile] || PRESETS[profile], state.mappings),
      );
      state.profile = profileMatch || "vibe";
      elements.profile.value = state.profile;
      localStorage.setItem("vibeHubProfile", state.profile);
      if (!profileMatch) {
        saved.vibe = cloneMappings(state.mappings);
        localStorage.setItem("vibeHubMappings", JSON.stringify(saved));
      }
      renderMappings();
    }
    if (!state.touchpadGesturesLoaded && input.touchpadGestures) {
      state.touchpadGesturesLoaded = true;
      if (!HAS_SAVED_TOUCHPAD_GESTURES) {
        state.touchpadGestures = {
          enabled: Boolean(input.touchpadGestures.enabled),
          threshold:
            Number(input.touchpadGestures.threshold) ||
            DEFAULT_TOUCHPAD_GESTURES.threshold,
          muteOnSwitch: Boolean(input.touchpadGestures.muteOnSwitch),
        };
      }
      renderMappings();
    }
    renderTouchpadGestures(
      input.touchpadGestures || {},
      axes,
      pressed.has("touchpad"),
    );
    renderSystemHealth();
  }

  async function checkBridge(showFailure = false) {
    state.lastReconnectAttempt = Date.now();
    try {
      const response = await fetch(`${API_BASE}/health`, { cache: "no-store" });
      const payload = await response.json();
      setServiceState(true);
      if (payload.input) updateInputStatus(payload.input);
      if (payload.codex) updateCodexStatus(payload.codex);
      if (payload.triggers) updateTriggerStatus(payload.triggers);
      if (
        !payload.input?.enabled ||
        !Object.keys(payload.input?.mappings || {}).length
      ) {
        await syncMapping(true);
      }
      setActivity(
        payload.ready
          ? "DualSense 橋接通道已就緒"
          : "本機服務在線，等待 USB 控制器",
      );
      return true;
    } catch (error) {
      if (showFailure) console.warn(error);
      setServiceState(false);
      setActivity("本機橋接服務未回應");
      if (showFailure)
        showDialog(
          "本機服務未連接",
          "背景服務尚未連線。請到裝置頁點擊重新偵測。",
          "LOCAL BRIDGE",
        );
      return false;
    }
  }

  async function pollStatus() {
    if (state.statusRequestPending) return;
    if (!state.serviceOnline) {
      if (Date.now() - state.lastReconnectAttempt > 1800)
        await checkBridge(false);
      return;
    }
    state.statusRequestPending = true;
    try {
      const response = await fetch(`${API_BASE}/api/status`, {
        cache: "no-store",
      });
      if (!response.ok) throw new Error(`status ${response.status}`);
      const payload = await response.json();
      updateInputStatus(payload.input);
      if (payload.codex) updateCodexStatus(payload.codex);
      if (payload.triggers) updateTriggerStatus(payload.triggers);
    } catch (error) {
      setServiceState(false);
    } finally {
      state.statusRequestPending = false;
    }
  }

  async function syncMapping(enabled = state.mappingEnabled) {
    if (!state.serviceOnline && !(await checkBridge(false))) {
      throw new Error("bridge offline");
    }
    const response = await fetch(`${API_BASE}/api/mapping`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        enabled,
        mappings: state.mappings,
        touchpadGestures: state.touchpadGestures,
      }),
    });
    const payload = await response.json();
    if (!response.ok)
      throw new Error(payload.error || `mapping ${response.status}`);
    updateInputStatus(payload.input);
    return payload.input;
  }

  let mappingSyncTimer = 0;
  function queueMappingSync() {
    if (!state.mappingEnabled) return;
    clearTimeout(mappingSyncTimer);
    mappingSyncTimer = setTimeout(
      () =>
        syncMapping(true).catch((error) => {
          console.error(error);
          setActivity("映射設定同步失敗");
        }),
      160,
    );
  }

  async function requestKeyCapture(action) {
    if (!state.serviceOnline && !(await checkBridge(false)))
      throw new Error("bridge offline");
    const response = await fetch(`${API_BASE}/api/key-capture`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    });
    const payload = await response.json();
    if (!response.ok)
      throw new Error(payload.error || `key capture ${response.status}`);
    return payload.keyCapture;
  }

  function stopCapturePolling() {
    clearTimeout(state.capturePollTimer);
    state.capturePollTimer = 0;
  }

  function cancelCapture({ notifyBridge = true } = {}) {
    const wasCapturing = Boolean(state.captureButton);
    state.captureRequestVersion += 1;
    stopCapturePolling();
    state.captureButton = null;
    state.captureCodes = [];
    renderMappings();
    if (wasCapturing && notifyBridge)
      requestKeyCapture("cancel").catch(() => {});
  }

  async function pollKeyCapture(version) {
    if (!state.captureButton || version !== state.captureRequestVersion) return;
    try {
      const capture = await requestKeyCapture("poll");
      if (!state.captureButton || version !== state.captureRequestVersion)
        return;
      if (Array.isArray(capture.result) && capture.result.length) {
        completeCaptureCodes(capture.result);
        return;
      }
      if (capture.lastError) {
        const label =
          BUTTONS.find((button) => button.id === state.captureButton)?.label ||
          state.captureButton;
        cancelCapture({ notifyBridge: false });
        setActivity(`${label} 快速鍵輸入超時，映射未改變`);
        return;
      }
      if (!capture.active && !capture.blocking) {
        cancelCapture({ notifyBridge: false });
        setActivity("安全快速鍵輸入已結束，映射未改變");
        return;
      }
      state.capturePollTimer = setTimeout(() => pollKeyCapture(version), 45);
    } catch (error) {
      console.error(error);
      if (state.captureButton && version === state.captureRequestVersion) {
        cancelCapture({ notifyBridge: false });
        setActivity("安全快速鍵輸入已中斷，映射未改變");
      }
    }
  }

  async function startCapture(button) {
    if (state.captureButton) {
      cancelCapture({ notifyBridge: false });
      try {
        await requestKeyCapture("cancel");
      } catch (error) {
        console.warn(error);
      }
    }
    state.captureButton = button;
    state.captureCodes = [];
    renderMappings();
    const version = ++state.captureRequestVersion;
    try {
      await requestKeyCapture("start");
      if (!state.captureButton || version !== state.captureRequestVersion)
        return;
      setActivity("安全快速鍵輸入已啟用，按下組合鍵");
      pollKeyCapture(version);
    } catch (error) {
      console.error(error);
      if (!state.captureButton || version !== state.captureRequestVersion)
        return;
      cancelCapture({ notifyBridge: false });
      showDialog(
        "無法開始安全輸入",
        "鍵盤攔截服務沒有啟動，未寫入映射。請重啟本機 Bridge 後重試。",
        "KEY CAPTURE",
      );
    }
  }

  function completeCaptureCodes(codes) {
    if (!state.captureButton) return;
    const buttonId = state.captureButton;
    state.mappings[buttonId] = [...new Set(codes)];
    const label =
      BUTTONS.find((button) => button.id === buttonId)?.label || buttonId;
    state.captureRequestVersion += 1;
    stopCapturePolling();
    state.captureButton = null;
    state.captureCodes = [];
    saveProfile();
    renderMappings();
    queueMappingSync();
    setActivity(
      `${label} 已映射為 ${formatShortcut(state.mappings[buttonId])}`,
    );
  }

  function setColor(hex) {
    const rgb = rgbFromHex(hex);
    if (!rgb) return false;
    state.color = hexFromRgb(rgb);
    updateLightingPreview();
    return true;
  }

  function updateRange(input) {
    const percent =
      ((Number(input.value) - Number(input.min)) /
        (Number(input.max) - Number(input.min))) *
      100;
    input.style.background = `linear-gradient(90deg, var(--mint) 0%, var(--mint) ${percent}%, #465154 ${percent}%, #465154 100%)`;
  }

  function triggerElements(side) {
    const prefix = side === "left" ? "left" : "right";
    return {
      control: $(`[data-trigger-control="${side}"]`),
      preview: $(`[data-trigger-preview="${side}"]`),
      modeLabel: $(`#${prefix}TriggerModeLabel`),
      summary: $(`#${prefix}TriggerSummary`),
      start: $(`#${prefix}TriggerStart`),
      startOutput: $(`#${prefix}TriggerStartOutput`),
      end: $(`#${prefix}TriggerEnd`),
      endOutput: $(`#${prefix}TriggerEndOutput`),
      strength: $(`#${prefix}TriggerStrength`),
      strengthOutput: $(`#${prefix}TriggerStrengthOutput`),
      current: $(`#${prefix}TriggerCurrent`),
    };
  }

  function normalizeTriggerUi(side) {
    const config = state.triggers[side];
    if (config.mode === "weapon") {
      config.start = Math.max(2, Math.min(7, config.start));
      config.end = Math.max(config.start + 1, Math.min(8, config.end));
    } else {
      config.start = Math.max(0, Math.min(9, config.start));
      config.end = Math.max(config.start + 1, Math.min(9, config.end));
    }
    config.strength = Math.max(1, Math.min(8, config.strength));
  }

  function renderTriggerSide(side) {
    normalizeTriggerUi(side);
    const config = state.triggers[side];
    const ui = triggerElements(side);
    ui.control.dataset.mode = config.mode;
    ui.preview.dataset.mode = config.mode;
    ui.preview.style.setProperty("--trigger-start", `${config.start * 10}%`);
    ui.preview.style.setProperty("--trigger-end", `${config.end * 10}%`);
    ui.modeLabel.textContent = TRIGGER_MODE_NAMES[config.mode];
    ui.summary.textContent =
      config.mode === "off"
        ? "關閉"
        : `${config.start * 10}% · ${config.strength}/8`;
    ui.start.min = config.mode === "weapon" ? 2 : 0;
    ui.start.max = config.mode === "weapon" ? 7 : 9;
    ui.end.max = config.mode === "weapon" ? 8 : 9;
    ui.start.value = config.start;
    ui.end.value = config.end;
    ui.strength.value = config.strength;
    ui.startOutput.value = `${config.start * 10}%`;
    ui.endOutput.value = `${config.end * 10}%`;
    ui.strengthOutput.value = `${config.strength} / 8`;
    [ui.start, ui.end, ui.strength].forEach(updateRange);
    $$(`[data-trigger-side="${side}"]`).forEach((button) =>
      button.classList.toggle(
        "is-active",
        button.dataset.triggerMode === config.mode,
      ),
    );
  }

  function renderTriggers() {
    renderTriggerSide("left");
    renderTriggerSide("right");
    updateTriggerPositions();
    localStorage.setItem("vibeHubTriggers", JSON.stringify(state.triggers));
  }

  function updateTriggerPositions() {
    ["left", "right"].forEach((side) => {
      const position = Math.max(
        0,
        Math.min(1, state.triggerPositions[side] || 0),
      );
      triggerElements(side).preview.style.setProperty(
        "--trigger-current",
        `${position * 100}%`,
      );
    });
  }

  function updateTriggerStatus(triggers) {
    if (!state.triggersLoaded && triggers.left && triggers.right) {
      state.triggersLoaded = true;
      if (state.restoreSavedTriggers) {
        state.restoreSavedTriggers = false;
        setTimeout(
          () =>
            sendTriggers().catch((error) => {
              console.error(error);
              elements.triggerOutputBadge.textContent = "同步失敗";
            }),
          0,
        );
      } else {
        state.triggers = {
          left: { ...state.triggers.left, ...triggers.left },
          right: { ...state.triggers.right, ...triggers.right },
        };
      }
      renderTriggers();
    }
    elements.triggerOutputBadge.textContent = triggers.lastError
      ? "輸出失敗"
      : triggers.available
        ? "效果在線"
        : "等待輸出";
    elements.triggerOutputBadge.classList.toggle(
      "is-live",
      Boolean(triggers.available && !triggers.lastError),
    );
  }

  async function sendTriggers({ silent = false } = {}) {
    if (!state.serviceOnline && !(await checkBridge(false)))
      throw new Error("bridge offline");
    const response = await fetch(`${API_BASE}/api/triggers`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state.triggers),
    });
    const payload = await response.json();
    if (!response.ok)
      throw new Error(payload.error || `triggers ${response.status}`);
    updateTriggerStatus(payload.triggers);
    if (!silent)
      setActivity(
        `自適應扳機已套用：L2 ${TRIGGER_MODE_NAMES[state.triggers.left.mode]} / R2 ${TRIGGER_MODE_NAMES[state.triggers.right.mode]}`,
      );
  }

  let triggerSyncTimer = 0;
  let triggerSyncVersion = 0;
  function queueTriggerSync() {
    const version = ++triggerSyncVersion;
    clearTimeout(triggerSyncTimer);
    localStorage.setItem("vibeHubTriggers", JSON.stringify(state.triggers));
    elements.triggerOutputBadge.textContent = "正在同步";
    triggerSyncTimer = setTimeout(
      () =>
        sendTriggers({ silent: true })
          .then(() => {
            if (version === triggerSyncVersion)
              elements.triggerOutputBadge.textContent = "即時生效";
          })
          .catch((error) => {
            console.error(error);
            if (version === triggerSyncVersion)
              elements.triggerOutputBadge.textContent = "同步失敗";
          }),
      100,
    );
  }

  function renderColorWheel() {
    const canvas = elements.colorWheel;
    const context = canvas.getContext("2d");
    const size = canvas.width;
    const center = size / 2;
    const radius = center - 4;
    const pixels = context.createImageData(size, size);
    for (let y = 0; y < size; y += 1)
      for (let x = 0; x < size; x += 1) {
        const dx = x - center;
        const dy = y - center;
        const distance = Math.hypot(dx, dy);
        const offset = (y * size + x) * 4;
        if (distance > radius) continue;
        const hue = ((Math.atan2(dy, dx) * 180) / Math.PI + 450) % 360;
        const rgb = hsvToRgb(hue, distance / radius);
        pixels.data[offset] = rgb[0];
        pixels.data[offset + 1] = rgb[1];
        pixels.data[offset + 2] = rgb[2];
        pixels.data[offset + 3] = 255;
      }
    context.clearRect(0, 0, size, size);
    context.putImageData(pixels, 0, 0);
    const [hue, saturation] = rgbToHsv(rgbFromHex(state.color));
    const radians = ((hue - 90) * Math.PI) / 180;
    const markerX = center + Math.cos(radians) * saturation * radius;
    const markerY = center + Math.sin(radians) * saturation * radius;
    context.beginPath();
    context.arc(markerX, markerY, 6, 0, Math.PI * 2);
    context.strokeStyle = "#fff";
    context.lineWidth = 2.5;
    context.stroke();
    context.beginPath();
    context.arc(markerX, markerY, 8.5, 0, Math.PI * 2);
    context.strokeStyle = "rgba(10,14,16,.82)";
    context.lineWidth = 1.5;
    context.stroke();
  }

  function renderLightingOutput({ rgb, effect, speed, mask, title }) {
    document.documentElement.style.setProperty("--light-rgb", rgb.join(", "));
    const color = hexFromRgb(rgb);
    elements.telemetryHex.textContent = color;
    elements.telemetryRgb.textContent = rgb.join(" / ");
    elements.telemetryMask.textContent = `0x${mask.toString(16).padStart(2, "0").toUpperCase()}`;
    elements.colorChip.style.background = color;
    elements.colorChip.style.boxShadow = `0 0 13px rgba(${rgb.join(",")},.65)`;
    elements.effectTitle.textContent = title || EFFECT_NAMES[effect];
    elements.lightPreview.classList.toggle("is-breathe", effect === "breathe");
    elements.lightPreview.classList.toggle("is-blink", effect === "blink");
    elements.lightPreview.style.setProperty(
      "--effect-duration",
      `${5.5 - speed * 0.55}s`,
    );
    [...elements.previewPlayers.children].forEach((light, index) =>
      light.classList.toggle("is-on", Boolean(mask & (1 << index))),
    );
    $$(".player-lights-preview i").forEach((light, index) =>
      light.classList.toggle("is-on", Boolean(mask & (1 << index))),
    );
  }

  function updateLightingPreview() {
    const rgb = rgbFromHex(state.color);
    renderLightingOutput({
      rgb,
      effect: state.effect,
      speed: state.speed,
      mask: playerMask(),
    });
    elements.hex.value = state.color;
    [elements.red.value, elements.green.value, elements.blue.value] = rgb;
    elements.brightness.value = state.brightness;
    elements.brightnessOutput.value = `${state.brightness}%`;
    updateRange(elements.brightness);
    elements.speed.value = state.speed;
    elements.speedOutput.value = SPEED_NAMES[state.speed - 1];
    updateRange(elements.speed);
    $$("#effectControls button").forEach((button) =>
      button.classList.toggle(
        "is-active",
        button.dataset.effect === state.effect,
      ),
    );
    $$(".swatch").forEach((button) =>
      button.classList.toggle(
        "is-selected",
        button.dataset.color === state.color,
      ),
    );
    $$("#playerLeds button").forEach((button, index) =>
      button.classList.toggle("is-on", state.players[index]),
    );
    const player = OFFICIAL_PLAYER_MASKS.indexOf(playerMask());
    elements.playerOutput.value = player >= 0 ? `P${player + 1}` : "自訂";
    $$("#playerPresets button").forEach((button) =>
      button.classList.toggle(
        "is-active",
        Number(button.dataset.player) === player + 1,
      ),
    );
    renderColorWheel();
  }

  function updateCodexStatus(codex) {
    const previousEnabled = state.codex.enabled;
    const previousState = state.codex.state;
    state.codex = { ...state.codex, ...codex };
    const enabled = Boolean(state.codex.enabled);
    const statusMeta =
      CODEX_STATUS_META[state.codex.state] || CODEX_STATUS_META.idle;
    elements.codexStatusToggle.checked = enabled;
    $(".light-controls-panel").classList.toggle("is-codex-linked", enabled);
    $$(".manual-light-control input, .manual-light-control button").forEach(
      (control) => {
        control.disabled = enabled;
      },
    );
    elements.colorWheel.tabIndex = enabled ? -1 : 0;
    elements.colorWheel.setAttribute("aria-disabled", String(enabled));
    $$("[data-codex-state]").forEach((row) =>
      row.classList.toggle(
        "is-active",
        row.dataset.codexState === state.codex.state,
      ),
    );
    elements.codexStateDot.className = `state-light state-light-${state.codex.state}`;
    elements.codexStateLabel.textContent = enabled
      ? `${statusMeta.label} · ${statusMeta.light}`
      : "手動燈光控制";
    if (!enabled) elements.codexStateMeta.textContent = "Codex 連動已停用";
    else if (state.codex.lastError)
      elements.codexStateMeta.textContent = "控制器輸出重試中";
    else if (!state.codex.available)
      elements.codexStateMeta.textContent = "等待 Codex 本機狀態";
    else {
      const latency = Number.isFinite(Number(state.codex.hookLatencyMs))
        ? ` · Hook ${state.codex.hookLatencyMs} ms`
        : "";
      elements.codexStateMeta.textContent = `待核准 ${state.codex.pendingRequests || 0} · 任務 ${state.codex.inflightTurns || 0}${latency}`;
    }
    elements.lightOutputBadge.textContent = enabled
      ? `Codex · ${statusMeta.label}`
      : "手動控制";
    elements.lightOutputBadge.classList.toggle("is-live", enabled);
    elements.lightOutputBadge.classList.toggle(
      "is-active",
      enabled && state.codex.state === "approval",
    );
    if (enabled && state.codex.profile?.lightbar) {
      const profile = state.codex.profile;
      const rgb = [
        profile.lightbar.red,
        profile.lightbar.green,
        profile.lightbar.blue,
      ];
      renderLightingOutput({
        rgb,
        effect: profile.effect,
        speed: profile.speed,
        mask: profile.playerLeds,
        title: `${statusMeta.label} · ${statusMeta.light}`,
      });
    } else if (previousEnabled && !enabled) {
      updateLightingPreview();
    }
    if (enabled && previousState !== state.codex.state)
      setActivity(`Codex ${statusMeta.label}，狀態燈切換為${statusMeta.light}`);
    renderSystemHealth();
  }

  async function configureCodexLighting(enabled) {
    if (!state.serviceOnline && !(await checkBridge(false)))
      throw new Error("bridge offline");
    const response = await fetch(`${API_BASE}/api/codex-lighting`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    });
    const payload = await response.json();
    if (!response.ok)
      throw new Error(payload.error || `codex lighting ${response.status}`);
    updateCodexStatus(payload.codex);
  }

  function lightingPayload(off = false) {
    const [red, green, blue] = rgbFromHex(state.color);
    return {
      lightbar: { red, green, blue, brightness: off ? 0 : state.brightness },
      playerLeds: playerMask(),
      effect: off ? "static" : state.effect,
      speed: state.speed,
    };
  }

  async function sendLighting({ off = false, silent = false } = {}) {
    if (!state.serviceOnline && !(await checkBridge(false))) {
      if (!silent)
        showDialog(
          "狀態燈不可用",
          "背景服務尚未啟動，請到裝置頁重新偵測。",
          "STATUS LIGHT",
        );
      return false;
    }
    try {
      const response = await fetch(`${API_BASE}/api/lighting`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(lightingPayload(off)),
      });
      const payload = await response.json();
      if (!response.ok)
        throw new Error(payload.error || `lighting ${response.status}`);
      elements.lightOutputBadge.textContent = off ? "已關閉" : "已套用";
      elements.lightOutputBadge.classList.toggle("is-live", !off);
      if (!silent)
        setActivity(
          off
            ? "狀態燈已關閉"
            : `${state.color} / ${EFFECT_NAMES[state.effect]} 已套用`,
        );
      return true;
    } catch (error) {
      console.error(error);
      elements.lightOutputBadge.textContent = "輸出失敗";
      elements.lightOutputBadge.classList.remove("is-live");
      if (!silent)
        showDialog(
          "狀態燈輸出失敗",
          "確認 DualSense 已通過 USB 連接，且沒有被其他控制器工具獨佔。",
          "STATUS LIGHT",
        );
      return false;
    }
  }

  function pickColor(event) {
    const bounds = elements.colorWheel.getBoundingClientRect();
    const center = elements.colorWheel.width / 2;
    const radius = center - 4;
    const dx =
      ((event.clientX - bounds.left) * elements.colorWheel.width) /
        bounds.width -
      center;
    const dy =
      ((event.clientY - bounds.top) * elements.colorWheel.height) /
        bounds.height -
      center;
    const distance = Math.min(Math.hypot(dx, dy), radius);
    const hue = ((Math.atan2(dy, dx) * 180) / Math.PI + 450) % 360;
    setColor(hexFromRgb(hsvToRgb(hue, distance / radius)));
  }

  function activateView(viewName) {
    const isExperience = ["lighting", "triggers", "touchpad"].includes(
      viewName,
    );
    $$(".nav-item").forEach((item) =>
      item.classList.toggle(
        "is-active",
        item.dataset.view === viewName ||
          (isExperience && item.dataset.view === "lighting"),
      ),
    );
    $$(".view").forEach((view) =>
      view.classList.toggle("is-active", view.id === `${viewName}View`),
    );
    $(".main-stage").scrollTop = 0;
    window.scrollTo(0, 0);
  }

  async function applyExperienceProfile(profile) {
    if (!(profile in PRESETS)) return;
    const meta = PROFILE_META[profile] || PROFILE_META.vibe;
    loadProfile(profile);
    if (profile.startsWith("micro_") || profile === "vibe") {
      state.touchpadGestures.enabled = false;
      localStorage.setItem(
        "vibeHubTouchpadGestures",
        JSON.stringify(state.touchpadGestures),
      );
    }
    saveProfile();
    updateProfilePresentation();
    try {
      await syncMapping(true);
      setActivity(`${meta.label}已套用並保存到本機服務`);
      showMicroLastAction("ps", state.mappings.ps || []);
    } catch (error) {
      console.error(error);
      showDialog(
        "模式已保存，等待本機服務",
        `${meta.label}已保存在控制頁面；本機橋接恢復後會自動同步。`,
        "CODEX CONTROLLER",
      );
    }
  }

  async function sendBridgeAction(action) {
    if (!state.serviceOnline && !(await checkBridge(false)))
      throw new Error("bridge offline");
    const response = await fetch(`${API_BASE}/api/action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    });
    const payload = await response.json();
    if (!response.ok)
      throw new Error(payload.error || `action ${response.status}`);
    return payload;
  }

  async function testStatusFeedback() {
    if (!state.serviceOnline && !(await checkBridge(false)))
      throw new Error("bridge offline");
    const response = await fetch(`${API_BASE}/api/haptics`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pattern: "double-soft" }),
    });
    const payload = await response.json();
    if (!response.ok)
      throw new Error(payload.error || `haptics ${response.status}`);
    return payload;
  }

  $$(".nav-item").forEach((button) =>
    button.addEventListener("click", () => {
      activateView(button.dataset.view);
    }),
  );
  $$("[data-experience-view]").forEach((button) =>
    button.addEventListener("click", () =>
      activateView(button.dataset.experienceView),
    ),
  );
  elements.reconnect.addEventListener("click", () => checkBridge(true));
  elements.deviceReconnect?.addEventListener("click", () => checkBridge(true));
  elements.mappingToggle.addEventListener("change", async () => {
    const enabled = elements.mappingToggle.checked;
    elements.mappingToggle.disabled = true;
    try {
      await syncMapping(enabled);
      setActivity(enabled ? "按鍵映射已啟用" : "按鍵映射已停用");
    } catch (error) {
      console.error(error);
      elements.mappingToggle.checked = state.mappingEnabled;
      showDialog(
        "無法切換映射",
        "背景服務沒有回應。請從裝置頁重新偵測後再試。",
        "KEY MAPPING",
      );
    } finally {
      elements.mappingToggle.disabled = false;
    }
  });
  elements.profile.addEventListener("change", () => {
    loadProfile(elements.profile.value);
    saveProfile();
    queueMappingSync();
    setActivity(`已切換到 ${elements.profile.selectedOptions[0].textContent}`);
  });
  $$("[data-apply-profile]").forEach((button) =>
    button.addEventListener("click", () =>
      applyExperienceProfile(button.dataset.applyProfile),
    ),
  );
  elements.openMapping?.addEventListener("click", () =>
    activateView("mapping"),
  );
  elements.focusCodex.addEventListener("click", async () => {
    elements.focusCodex.disabled = true;
    try {
      await sendBridgeAction("focus-codex");
      setActivity("Codex 已開啟或切回前景");
      showMicroLastAction("ps", ["CodexFocus"]);
    } catch (error) {
      console.error(error);
      showDialog(
        "無法切回 Codex",
        "本機服務目前沒有回應；恢復連線後也可以直接按 PS 鍵。",
        "CODEX CONTROLLER",
      );
    } finally {
      elements.focusCodex.disabled = false;
    }
  });
  elements.sidebarFocusCodex?.addEventListener("click", () =>
    elements.focusCodex.click(),
  );
  elements.deviceTestFeedback?.addEventListener("click", () =>
    elements.testFeedback.click(),
  );
  elements.testFeedback.addEventListener("click", async () => {
    elements.testFeedback.disabled = true;
    try {
      const result = await testStatusFeedback();
      setActivity(
        result.played
          ? "DualSense 狀態震動測試完成"
          : "扳機效果正在執行，狀態震動稍後再試",
      );
    } catch (error) {
      console.error(error);
      showDialog(
        "無法測試狀態震動",
        "請確認 DualSense 已透過 USB 連接，且本機服務正在執行。",
        "CODEX CONTROLLER",
      );
    } finally {
      elements.testFeedback.disabled = false;
    }
  });
  elements.resetProfile.addEventListener("click", () => {
    const saved = savedProfiles();
    delete saved[state.profile];
    localStorage.setItem("vibeHubMappings", JSON.stringify(saved));
    loadProfile(state.profile);
    queueMappingSync();
    setActivity("目前設定已還原為預設值");
  });
  elements.deviceResetProfile?.addEventListener("click", () => {
    if (state.profile !== "vibe") loadProfile("vibe");
    elements.resetProfile.click();
  });
  elements.touchpadGestureToggle.addEventListener("change", () => {
    state.touchpadGestures.enabled = elements.touchpadGestureToggle.checked;
    localStorage.setItem(
      "vibeHubTouchpadGestures",
      JSON.stringify(state.touchpadGestures),
    );
    renderTouchpadGestures();
    renderMappings();
    queueMappingSync();
    setActivity(
      state.touchpadGestures.enabled
        ? "觸控板桌面手勢已啟用"
        : "觸控板按鍵映射已恢復",
    );
  });
  elements.touchpadGestureThreshold.addEventListener("input", () => {
    state.touchpadGestures.threshold = Number(
      elements.touchpadGestureThreshold.value,
    );
    localStorage.setItem(
      "vibeHubTouchpadGestures",
      JSON.stringify(state.touchpadGestures),
    );
    renderTouchpadGestures();
    queueMappingSync();
  });
  elements.touchpadMuteToggle.addEventListener("change", () => {
    state.touchpadGestures.muteOnSwitch = elements.touchpadMuteToggle.checked;
    localStorage.setItem(
      "vibeHubTouchpadGestures",
      JSON.stringify(state.touchpadGestures),
    );
    renderTouchpadGestures();
    queueMappingSync();
    setActivity(
      state.touchpadGestures.muteOnSwitch
        ? "桌面切換靜音已啟用"
        : "桌面切換靜音已停用",
    );
  });
  $$(".mapping-filter button").forEach((button) =>
    button.addEventListener("click", () => {
      state.filter = button.dataset.filter;
      $$(".mapping-filter button").forEach((item) =>
        item.classList.toggle("is-active", item === button),
      );
      renderMappings();
    }),
  );
  elements.mappingList.addEventListener("click", (event) => {
    const capture = event.target.closest("[data-capture]");
    const clear = event.target.closest("[data-clear]");
    if (capture) {
      selectMappingButton(capture.dataset.capture);
      startCapture(capture.dataset.capture);
    }
    if (clear) {
      delete state.mappings[clear.dataset.clear];
      cancelCapture();
      saveProfile();
      renderMappings();
      queueMappingSync();
      setActivity("映射已清除");
    }
  });
  elements.toggleAllMappings.addEventListener("click", () => {
    const expanded = elements.mappingPanel.classList.toggle("is-expanded");
    elements.toggleAllMappings.textContent = expanded ? "收合" : "展開";
    elements.toggleAllMappings.setAttribute("aria-expanded", String(expanded));
    setActivity(expanded ? "已展開所有按鍵" : "已收合所有按鍵");
  });
  $("#controllerVisual").addEventListener("click", (event) => {
    const node = event.target.closest(".twin-node[data-button]");
    if (!node) return;
    state.filter = "all";
    $$(".mapping-filter button").forEach((button) =>
      button.classList.toggle("is-active", button.dataset.filter === "all"),
    );
    selectMappingButton(node.dataset.button);
  });
  elements.microCoreActions.addEventListener("click", (event) => {
    const button = event.target.closest("[data-select-button]");
    if (!button) return;
    activateView("mapping");
    selectMappingButton(button.dataset.selectButton);
  });
  elements.selectedCapture.addEventListener("click", () =>
    startCapture(state.selectedButton),
  );
  elements.selectedClear.addEventListener("click", () => {
    const button = BUTTONS.find((item) => item.id === state.selectedButton);
    delete state.mappings[state.selectedButton];
    cancelCapture();
    saveProfile();
    renderMappings();
    queueMappingSync();
    setActivity(`${button?.label || "按鍵"}映射已清除`);
  });
  $("#controllerVisual").addEventListener("pointerover", (event) => {
    const node = event.target.closest(".twin-node[data-button]");
    if (!node) return;
    state.hoveredTwin = node.dataset.button;
    showTwinReadout(node.dataset.button, node.classList.contains("is-pressed"));
  });
  $("#controllerVisual").addEventListener("pointerout", (event) => {
    const node = event.target.closest(".twin-node[data-button]");
    const nextNode = event.relatedTarget?.closest?.(".twin-node[data-button]");
    if (!node || nextNode === node) return;
    state.hoveredTwin = nextNode?.dataset.button || null;
    if (nextNode)
      showTwinReadout(
        nextNode.dataset.button,
        nextNode.classList.contains("is-pressed"),
      );
    else if (!$("#controllerVisual .twin-node.is-pressed")) clearTwinReadout();
  });
  window.addEventListener(
    "keydown",
    (event) => {
      if (!state.captureButton) return;
      event.preventDefault();
      event.stopPropagation();
    },
    true,
  );
  window.addEventListener(
    "keyup",
    (event) => {
      if (!state.captureButton) return;
      event.preventDefault();
      event.stopPropagation();
    },
    true,
  );
  window.addEventListener("beforeunload", () => {
    if (state.captureButton) requestKeyCapture("cancel").catch(() => {});
  });

  elements.hex.addEventListener("change", () => {
    if (!setColor(elements.hex.value)) {
      elements.hex.value = state.color;
      setActivity("顏色格式應為 #RRGGBB");
    }
  });
  [elements.red, elements.green, elements.blue].forEach((input) =>
    input.addEventListener("input", () =>
      setColor(
        hexFromRgb([
          elements.red.value,
          elements.green.value,
          elements.blue.value,
        ]),
      ),
    ),
  );
  elements.colorWheel.addEventListener("pointerdown", (event) => {
    elements.colorWheel.setPointerCapture(event.pointerId);
    pickColor(event);
  });
  elements.colorWheel.addEventListener("pointermove", (event) => {
    if (event.buttons) pickColor(event);
  });
  elements.colorWheel.addEventListener("keydown", (event) => {
    const [hue, saturation] = rgbToHsv(rgbFromHex(state.color));
    const step = event.shiftKey ? 15 : 4;
    const saturationStep = event.shiftKey ? 0.12 : 0.04;
    const nextHue =
      event.key === "ArrowLeft"
        ? hue - step
        : event.key === "ArrowRight"
          ? hue + step
          : hue;
    const nextSaturation =
      event.key === "ArrowDown"
        ? saturation - saturationStep
        : event.key === "ArrowUp"
          ? saturation + saturationStep
          : saturation;
    if (nextHue === hue && nextSaturation === saturation) return;
    event.preventDefault();
    setColor(
      hexFromRgb(
        hsvToRgb(
          (nextHue + 360) % 360,
          Math.max(0, Math.min(1, nextSaturation)),
        ),
      ),
    );
  });
  $$(".swatch").forEach((button) =>
    button.addEventListener("click", () => setColor(button.dataset.color)),
  );
  elements.brightness.addEventListener("input", () => {
    state.brightness = Number(elements.brightness.value);
    updateLightingPreview();
  });
  elements.speed.addEventListener("input", () => {
    state.speed = Number(elements.speed.value);
    updateLightingPreview();
  });
  $$("#effectControls button").forEach((button) =>
    button.addEventListener("click", () => {
      state.effect = button.dataset.effect;
      updateLightingPreview();
    }),
  );
  $("#playerPresets").addEventListener("click", (event) => {
    const button = event.target.closest("[data-player]");
    if (!button) return;
    const mask = OFFICIAL_PLAYER_MASKS[Number(button.dataset.player) - 1];
    state.players = state.players.map((_on, index) =>
      Boolean(mask & (1 << index)),
    );
    updateLightingPreview();
  });
  elements.playerLeds.addEventListener("click", (event) => {
    const button = event.target.closest("[data-index]");
    if (!button) return;
    const index = Number(button.dataset.index);
    const group = PLAYER_LED_GROUPS.find((indices) => indices.includes(index));
    const next = !state.players[group[0]];
    group.forEach((led) => {
      state.players[led] = next;
    });
    updateLightingPreview();
  });
  elements.apply.addEventListener("click", () => sendLighting());
  elements.turnOff.addEventListener("click", () => sendLighting({ off: true }));
  elements.codexStatusToggle.addEventListener("change", async () => {
    const enabled = elements.codexStatusToggle.checked;
    elements.codexStatusToggle.disabled = true;
    try {
      await configureCodexLighting(enabled);
      setActivity(
        enabled
          ? "Codex 狀態燈連動已啟用"
          : "Codex 狀態燈連動已停用，可使用手動燈控",
      );
    } catch (error) {
      console.error(error);
      elements.codexStatusToggle.checked = state.codex.enabled;
      showDialog(
        "無法切換 Codex 連動",
        "背景服務沒有回應，請到裝置頁重新偵測。",
        "CODEX STATUS",
      );
    } finally {
      elements.codexStatusToggle.disabled = false;
    }
  });
  $$("[data-trigger-side][data-trigger-mode]").forEach((button) =>
    button.addEventListener("click", () => {
      state.triggers[button.dataset.triggerSide].mode =
        button.dataset.triggerMode;
      renderTriggers();
      queueTriggerSync();
    }),
  );
  ["left", "right"].forEach((side) => {
    const ui = triggerElements(side);
    ui.start.addEventListener("input", () => {
      state.triggers[side].start = Number(ui.start.value);
      renderTriggerSide(side);
      queueTriggerSync();
    });
    ui.end.addEventListener("input", () => {
      state.triggers[side].end = Number(ui.end.value);
      renderTriggerSide(side);
      queueTriggerSync();
    });
    ui.strength.addEventListener("input", () => {
      state.triggers[side].strength = Number(ui.strength.value);
      renderTriggerSide(side);
      queueTriggerSync();
    });
  });
  elements.triggerGunPreset.addEventListener("click", () => {
    state.triggers.left = { mode: "weapon", start: 3, end: 6, strength: 5 };
    state.triggers.right = { mode: "weapon", start: 3, end: 6, strength: 5 };
    renderTriggers();
    queueTriggerSync();
  });
  elements.disableTriggers.addEventListener("click", async () => {
    state.triggers.left.mode = "off";
    state.triggers.right.mode = "off";
    renderTriggers();
    try {
      await sendTriggers();
    } catch (error) {
      console.error(error);
      showDialog(
        "無法關閉扳機效果",
        "請確認 DualSense 已通過 USB 連接，且橋接服務正在執行。",
        "ADAPTIVE TRIGGERS",
      );
    }
  });
  elements.applyTriggers.addEventListener("click", async () => {
    clearTimeout(triggerSyncTimer);
    triggerSyncVersion += 1;
    elements.applyTriggers.disabled = true;
    try {
      await sendTriggers();
    } catch (error) {
      console.error(error);
      showDialog(
        "扳機效果套用失敗",
        "請確認 DualSense 已通過 USB 連接，且沒有被其他控制器軟體占用。",
        "ADAPTIVE TRIGGERS",
      );
    } finally {
      elements.applyTriggers.disabled = false;
    }
  });
  elements.dialogClose.addEventListener("click", () => elements.dialog.close());

  loadProfile(state.profile);
  renderTouchpadGestures();
  updateLightingPreview();
  renderTriggers();
  renderSystemHealth();
  setActivity("Codex Controller 已就緒");
  checkBridge(false);
  setInterval(pollStatus, 120);
})();
