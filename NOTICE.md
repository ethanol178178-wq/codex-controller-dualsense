# Attribution and Modifications

## Upstream project

This repository is a modified distribution of the DualSense project from
LYiHub's **AI Mic Series**.

The upstream copyright notice and MIT License are retained verbatim in
[`LICENSE`](LICENSE):

> Copyright (c) 2026 深圳市有亦网络科技有限公司下属的 LYiHub

The MIT License permits use, modification, and redistribution, provided that
the copyright and permission notices remain with copies or substantial
portions of the software.

## Modifications in this edition

This edition substantially extends and reorganizes the project, including:

- a device-centred Codex Controller interface;
- direct controller-button selection and mapping;
- Codex voice, dictation, navigation, and review workflows;
- persistent mappings and background service startup;
- Codex status lighting and haptic feedback;
- adaptive trigger and touchpad controls;
- portable and Windows installer packaging;
- privacy, authorization, and release tests.

Git history and repository contributions identify the authors of these
modifications. This notice supplements, and does not replace, the upstream
license or third-party notices.

## Third-party components

- Microsoft Windows Driver Samples `vhidmini2`, under the Microsoft Public
  License, are used by the optional virtual Precision Touchpad driver.
- `PeronGH/BLE-PTP-PoC`, under the MIT License, is the source of adapted
  Precision Touchpad report structures and capability data.
- The Traditional Chinese Inno Setup message file retains its original author
  and translator credits in `packaging/ChineseTraditional.isl`.

Complete license texts and source links are provided in
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## Trademarks

DualSense and PlayStation are trademarks of Sony Interactive Entertainment
Inc. or its affiliates. Codex is a product of OpenAI. This is an independent
community project and is not endorsed, sponsored, or published by Sony or
OpenAI.
