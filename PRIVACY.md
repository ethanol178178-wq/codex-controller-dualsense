# Privacy Policy / 隱私權政策

Last updated: 2026-08-27

## Summary

Codex Controller for DualSense is a local controller integration for Windows.
It does not operate an analytics service, advertising service, user account
system, or cloud backend.

This program will not transfer any information to other networked systems
unless specifically requested by the user or the person installing or
operating it.

Codex Desktop, GitHub, Windows, and any website or service that the user opens
separately are governed by their own privacy policies.

## Data processed locally

The application may process the following data on the user's computer:

- DualSense input, connection state, lighting, haptics, and trigger settings.
- Custom controller mappings and application preferences.
- Local Codex lifecycle events needed to display idle, working, completed,
  approval, and error states.
- Local diagnostic logs when the user explicitly starts or exports diagnostics.

Prompt text, Codex response content, workspace paths, audio recordings, API
keys, and account credentials are not collected by this project. Session and
request identifiers used for local status tracking are anonymized before they
enter bridge state.

## Storage and deletion

Preferences are stored locally under `%LOCALAPPDATA%\DS5VibeHub`. They remain
on the computer after an ordinary application update or uninstall so that the
user can keep their mappings. The user may delete that directory to remove the
saved preferences. Release packages do not contain the maintainer's local
preferences, logs, tokens, or personal paths.

## Network behavior

The controller service listens only on the local loopback interface. The
control page communicates with that local service using a locally generated
random token. The application does not upload controller input, Codex content,
preferences, or diagnostics.

Opening an external link, downloading a release, or using Codex Desktop is an
explicit user action outside this project's local data flow.

## Contact

For a privacy or security concern, use GitHub private vulnerability reporting
when available. Otherwise, open a minimal public issue asking the maintainer
for a private contact channel and do not include sensitive information.

---

## 中文摘要

Codex Controller for DualSense 的控制服務與設定都在使用者電腦本機運作，
不提供分析、廣告、帳號或雲端後端服務。除非由安裝或操作程式的人明確要求，
本程式不會把任何資訊傳送到其他網路系統。

程式只會在本機處理手把輸入、連線狀態、個人按鍵配置、裝置體驗設定與
Codex 工作狀態。它不蒐集提示詞、回覆內容、工作目錄、錄音、API 金鑰或
帳號憑證。設定儲存在 `%LOCALAPPDATA%\DS5VibeHub`，使用者可刪除該資料夾
以清除設定。Codex Desktop、GitHub、Windows 與使用者另外開啟的服務，
各自適用其服務提供者的隱私權政策。
