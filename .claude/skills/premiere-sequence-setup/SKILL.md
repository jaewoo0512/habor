---
name: premiere-sequence-setup
description: Premiere Pro 시퀀스 셋업 - XML/SRT 임포트, 인트로/아웃트로 클론 배치
---

# Premiere Pro 시퀀스 셋업 스킬

## 개요
afm(AI 공장장) 에피소드의 Premiere Pro 시퀀스를 셋업하는 전체 워크플로우.
전처리된 XML/SRT를 임포트하고, reference 시퀀스에서 인트로/아웃트로 MOGRT 클립을
property까지 보존하여 클론 배치한다.

## 사전 조건
- Premiere Pro에서 `_inputs/premier/harbor-school-courses.prproj` 프로젝트가 열려있어야 함
- adb-mcp 프록시 서버가 실행 중이어야 함 (`_mcp/scripts/start-proxy.sh`)
- UXP 플러그인이 Premiere에서 로드+Connect 상태여야 함
- reference 시퀀스 (예: `afm-weekend-5-1`)가 프로젝트에 존재해야 함

## 핵심 상수

```
TICKS_PER_SECOND = 254016000000
VIDEO_SPEC = 1920x1080, 23.976fps (24fps NTSC)
INTRO_DURATION_SEC = 6.298
INTRO_LOGO_START_SEC = 3.754
```

## 파일 경로

```
PROJECT_ROOT = /Volumes/PortableSSD/openclaw-workspaces/workspace-harbor-ai-factory-manager/afm-3th/_operating/vod
Vrew 원본    = {PROJECT_ROOT}/_outputs/afm-weekday-{episode}-fix.xml / .srt  (보존)
전처리 출력  = {PROJECT_ROOT}/_outputs/afm-weekday-{episode}-premiere.xml / .srt
인트로 에셋  = {PROJECT_ROOT}/_inputs/premier/intro-logo.png
오디오 에셋  = {PROJECT_ROOT}/_inputs/premier/ding.mov.mp3
전처리 스크립트 = {PROJECT_ROOT}/_mcp/scripts/prepare_premiere.py
MCP 디렉토리 = {PROJECT_ROOT}/_mcp/adb-mcp/mcp/
UXP 플러그인 = {PROJECT_ROOT}/_mcp/adb-mcp/uxp/pr/commands/core.js
```

## 작업 절차

### 1. XML/SRT 전처리

`prepare_premiere.py`가 인트로 오프셋(6.298초)을 모든 start/end에 적용한다.
**인트로 클립은 XML에 삽입하지 않는다** (MCP API로 배치).

```bash
cd /Volumes/PortableSSD/openclaw-workspaces/workspace-harbor-ai-factory-manager/afm-3th/_operating/vod
python3 _mcp/scripts/prepare_premiere.py {episode}
# 예: python3 _mcp/scripts/prepare_premiere.py 6-1
# 입력: _outputs/afm-weekday-6-1-fix.xml (Vrew 원본, 보존됨)
# 출력: _outputs/afm-weekday-6-1-premiere.xml, _outputs/afm-weekday-6-1-premiere.srt
```

> **미디어 경로 (pathurl) 규칙**
> XML의 `<pathurl>`은 Vrew가 내보낸 원본 편집 머신 경로(예: `file:///Users/yongmin/Downloads/...`)를
> 그대로 담고 있다. 그 경로에 파일이 없으면 임포트 직후 **미디어가 전부 오프라인**으로 뜬다.
> 전처리 단계에서 mp3/mp4 `pathurl`을 **이 워크스페이스의 `_inputs/` 로컬 절대경로로 치환**할 것.
> 그러면 임포트 후 relink가 아예 필요 없다.
> - 치환은 XMEML 주의사항대로 **regex 텍스트 치환**으로 (ElementTree 재직렬화 금지)
> - 시퀀스가 이미 완성·저장된 뒤라면 XML을 고쳐도 재임포트가 필요하므로 이득이 없다 → 그때는 Premiere UI에서 relink가 더 싸다
> - 로컬에 실제로 없는 파일(예: 원본 mp4 미확보)은 경로를 고쳐도 오프라인이다. relink로 해결되는 건 **파일이 존재하는 경우뿐**

> **XMEML 주의사항 (치명적!)**
> - `ElementTree`(ET.tostring)로 재직렬화하면 **Premiere import 100% 실패**
> - 반드시 **regex 텍스트 치환**으로 원본 XML 구조를 보존해야 함
> - Vrew XML은 float 프레임값(예: `137.862`) 사용 → Premiere는 이를 허용하므로 정수 변환 불필요
> - 입력(`-fix.xml`)과 출력(`-premiere.xml`) 파일명을 분리하여 원본 보존

### 2. Premiere Pro에 임포트

MCP 도구를 사용하여 XML 시퀀스와 SRT를 임포트한다.

```
# XML 시퀀스 임포트 (시퀀스가 자동 생성됨)
import_xml_sequence("{PROJECT_ROOT}/_outputs/afm-weekday-{episode}-premiere.xml")

# SRT 자막 임포트
import_srt("{PROJECT_ROOT}/_outputs/afm-weekday-{episode}-premiere.srt")
```

임포트 후 `list_sequences()`로 새 시퀀스 ID를 확인한다.

### 3. 인트로 클론 (reference → target)

MOGRT 클립([Toko] Big_Title_21)은 텍스트/폰트/색상 등 property를 API로 개별 설정할 수 없으므로,
**reference 시퀀스에서 클론**하여 property를 보존한다.

#### 클론 방식 (clone-and-move)

`createCloneTrackItemAction`은 `source_position + insertionTime`에 배치하므로:
1. `insertionTime = 0`으로 클론 → 클립이 source의 원래 위치에 배치
2. `createMoveAction(delta)`로 원하는 위치로 이동 (delta는 상대값, 음수 가능)

```
delta = target_position_ticks - source_position_ticks
```

#### 인트로 배치 순서

1. **[Toko] Big_Title_21 클론** (MOGRT → reference에서 클론 필수)
   - reference V1[0] → target V1 at 0 ticks (delta=0, clone-no-move-needed)

2. **intro-logo.png 배치** (V1 @ 953512560000 ticks / 3.754s)
   - `add_media_to_sequence`로 배치
   - **주의**: 기본 duration이 길게 배치됨 → 반드시 트림 필요
   - `set_clip_start_end_times`로 end를 1599782184000 (6.298s)로 트림

3. **ding.mov.mp3 배치** (A1 @ 953512560000 ticks / 3.754s)
   - `add_media_to_sequence`로 배치
   - **주의**: overwrite=true로 기존 오디오를 덮어씀 → 트림 후 복원 필요
   - `set_clip_start_end_times`로 end를 1599782184000 (6.298s)로 트림
   - 덮어쓰여진 첫 오디오 클립의 start를 원래 위치로 복원

4. **intro-logo.png Scale 50% 적용**
   - `set_clip_param(component_name="AE.ADBE Motion", param_name="Scale", value=50)`

```python
# Step 1: Big_Title_21 클론
cmd = createCommand('copyClipBetweenSequences', {
    'sourceSequenceId': '{reference_seq_id}',
    'sourceTrackIndex': 0,          # V1
    'sourceTrackItemIndex': 0,      # 첫 번째 클립
    'sourceTrackType': 'VIDEO',
    'destSequenceId': '{target_seq_id}',
    'destTimeTicks': '0',
    'destTrackIndex': 0
})

# Step 2: intro-logo.png 클론 (⚠️ addMediaToSequence 절대 금지 — overwrite로 콘텐츠 파괴)
# ref V1[1] → target V1 at same ticks. clone으로 trim + Scale 50% 모두 보존됨
copyClipBetweenSequences(sourceSequenceId=REF, sourceTrackIndex=0, sourceTrackItemIndex=1,
    sourceTrackType='VIDEO', destSequenceId=TARGET, destTimeTicks='{ref_intro_logo_start}', destTrackIndex=0)

# Step 3: ding.mov.mp3 클론 (ref A1[0] → target A1 at same ticks. trim 보존됨)
copyClipBetweenSequences(sourceSequenceId=REF, sourceTrackIndex=0, sourceTrackItemIndex=0,
    sourceTrackType='AUDIO', destSequenceId=TARGET, destTimeTicks='{ref_ding_start}', destTrackIndex=0)
```

### 3-1. 인트로 MOGRT Text E 수정 (영상 부제목)

인트로 `[Toko] Big_Title_21`의 Text E는 영상 부제목(예: "실전 프로젝트 02")이다.
reference에서 클론하면 이전 에피소드의 부제목이 그대로 복사되므로 **반드시 수정**해야 한다.

**부제목 정보가 없으면 사용자에게 물어볼 것.**

CEP ExtendScript Bridge(port 47200)를 통해 수정:

```python
import json, urllib.request

# Big_Title_21 = V1 clips[0], components[2] (Graphic Parameters)
# Text E = properties[4], 폰트: Pretendard-Thin 50pt
subtitle = "실전 프로젝트 02"  # ← 사용자에게 확인

script = f'''(function(){{
  var seq = app.project.activeSequence;
  var c = seq.videoTracks[0].clips[0];
  var capsule = c.components[2];
  var tE = capsule.properties[4];
  var val = JSON.stringify({{
    capPropFontEdit:true, capPropFontFauxStyleEdit:true, capPropFontSizeEdit:true,
    capPropTextRunCount:1, fontEditValue:["Pretendard-Thin"],
    fontFSAllCapsValue:[false], fontFSBoldValue:[false], fontFSItalicValue:[false],
    fontFSSmallCapsValue:[false], fontSizeEditValue:[50],
    fontTextRunLength:[{len(subtitle)}], textEditValue:"{subtitle}"
  }});
  tE.setValue(val, true);
  return "OK";
}})()'''

data = json.dumps({{'script': script}}).encode()
req = urllib.request.Request('http://127.0.0.1:47200/', data=data,
      headers={{'Content-Type': 'application/json'}})
resp = urllib.request.urlopen(req, timeout=10)
```

> **Big_Title_21 vs Typography_Slide_62 구조 차이:**
> - Big_Title_21: `components[2]` (Graphic Parameters), Text A~E = properties[0~4]
> - Typography_Slide_62: `components[3]`, Edit Text A/B/C = properties[1/2/3]

### 4. 아웃트로 클론 (reference → target)

reference 시퀀스 끝에 있는 아웃트로 3개 클립을 클론한다.

#### 아웃트로 구성 (reference 기준)

| 트랙 | 클립 | 설명 |
|------|------|------|
| V1 | "unknown" (Graphic) | Essential Graphics 흰색 배경 사각형 |
| V2 | [Toko] Logo_01 | 로고 애니메이션 MOGRT |
| A1 | ding.mov.mp3 | 띵 효과음 |

세 클립 모두 같은 시작 시간에 배치됨.

#### 아웃트로 위치 계산

target 시퀀스의 마지막 콘텐츠 end ticks를 `get_sequence_track_info(from_end=true)`로 확인하여
아웃트로 시작 위치로 사용한다.

#### 클론 순서

```python
# 1. V1 Graphic 클론 (clone-and-move 자동)
cmd = createCommand('copyClipBetweenSequences', {
    'sourceSequenceId': '{ref_id}',
    'sourceTrackIndex': 0,
    'sourceTrackItemIndex': {ref_v1_outro_index},   # get_sequence_track_info로 확인
    'sourceTrackType': 'VIDEO',
    'destSequenceId': '{target_id}',
    'destTimeTicks': '{outro_start_ticks}',
    'destTrackIndex': 0
})

# 2. V2 Logo_01 클론
# 주의: createCloneTrackItemAction이 dstTrackIndex=1 지정해도 V3에 배치되는 현상 있음
# 클론 후 moveTrackItem으로 수동 이동 필요
cmd = createCommand('copyClipBetweenSequences', {
    'sourceSequenceId': '{ref_id}',
    'sourceTrackIndex': 1,
    'sourceTrackItemIndex': {ref_v2_outro_index},
    'sourceTrackType': 'VIDEO',
    'destSequenceId': '{target_id}',
    'destTimeTicks': '{outro_start_ticks}',
    'destTrackIndex': 1
})
# → "clone-only-move-failed" 발생 시:
# get_sequence_track_info로 Logo_01이 어느 트랙에 갔는지 확인
# moveTrackItem으로 올바른 위치로 이동:
cmd = createCommand('moveTrackItem', {
    'sequenceId': '{target_id}',
    'trackIndex': {actual_track_index},   # 보통 2 (V3)
    'trackItemIndex': 0,
    'trackType': 'VIDEO',
    'deltaTicks': '{delta}'               # target_ticks - source_ticks (음수)
})

# 3. A1 ding 클론
cmd = createCommand('copyClipBetweenSequences', {
    'sourceSequenceId': '{ref_id}',
    'sourceTrackIndex': 0,
    'sourceTrackItemIndex': {ref_a1_outro_index},
    'sourceTrackType': 'AUDIO',
    'destSequenceId': '{target_id}',
    'destTimeTicks': '{outro_start_ticks}',
    'destTrackIndex': 0
})
```

### 5. 검증

```
get_sequence_track_info(sequence_id, max_items=3, from_end=true)
```

아웃트로 클립들이 올바른 위치와 길이인지 확인:
- V1 Graphic과 V2/V3 Logo_01: 동일한 start/end ticks, ~3.42초
- A1 ding: 동일한 start ticks, ~2.002초

## UXP 커스텀 커맨드 (core.js)

### copyClipBetweenSequences
클립을 시퀀스 간 복사. clone(insertionTime=0) → findClonedItem → moveAction(delta).

| 파라미터 | 설명 |
|----------|------|
| sourceSequenceId | reference 시퀀스 ID |
| sourceTrackIndex | 소스 트랙 인덱스 |
| sourceTrackItemIndex | 소스 클립 인덱스 |
| sourceTrackType | "VIDEO" 또는 "AUDIO" |
| destSequenceId | 대상 시퀀스 ID |
| destTimeTicks | 대상 위치 (ticks 문자열) |
| destTrackIndex | 대상 트랙 인덱스 |

### moveTrackItem
클립을 상대적으로 이동. `createMoveAction(delta)`를 사용.

| 파라미터 | 설명 |
|----------|------|
| sequenceId | 시퀀스 ID |
| trackIndex | 트랙 인덱스 |
| trackItemIndex | 클립 인덱스 |
| trackType | "VIDEO" 또는 "AUDIO" |
| deltaTicks | 이동량 (음수=왼쪽, 양수=오른쪽) |

### getClipComponents
MOGRT/이펙트의 컴포넌트와 파라미터 구조를 조회.

### setClipParam
컴포넌트 파라미터 값 설정 (scalar 숫자만 가능, 텍스트/배열은 불가).

## 알려진 제약 사항

1. **XMEML ElementTree 금지**: `ET.tostring()` 재직렬화 시 Premiere import 실패. 반드시 regex 텍스트 치환으로 원본 구조 보존
2. **XMEML에 클립 삽입 금지**: 인트로 클립을 XML에 직접 삽입하면 import 실패. MCP API(add_media, clone)로만 배치
3. **MOGRT 텍스트 설정 불가**: UXP API로 MOGRT 텍스트 파라미터(keyframesSupported=false) 읽기/쓰기 불가 → 반드시 reference에서 클론
4. **MOGRT 배열 파라미터 설정 불가**: Position, Box Control 등 배열 타입 → "Illegal Parameter type" 오류
5. **createCloneTrackItemAction 위치**: `source_position + insertionTime`으로 배치됨 (절대 위치 아님)
6. **createMoveAction**: 상대 delta (음수 가능). `TickTime.createWithTicks(negativeDelta)` 정상 동작
7. **MOGRT 클론 트랙 오프셋**: dstTrackIndex 지정과 다른 트랙에 배치될 수 있음 → 클론 후 위치 확인 필수
8. **set_clip_start_end_times**: 큰 위치 변경에는 "Invalid parameter" 오류. 트리밍에만 사용

## Direct Proxy Script 사용법

MCP 서버를 재시작하지 않고 커스텀 UXP 커맨드를 호출할 때:

```bash
cd /Volumes/PortableSSD/openclaw-workspaces/workspace-harbor-ai-factory-manager/afm-3th/_operating/vod/_mcp/adb-mcp/mcp/
.venv/bin/python3 -c "
import socket_client
from core import init, sendCommand, createCommand
socket_client.configure(app='premiere', url='http://localhost:47001', timeout=30)
init('premiere', socket_client)
cmd = createCommand('{action}', {options_dict})
result = sendCommand(cmd)
print(result.get('response', result))
"
```

UXP core.js 수정 후에는 반드시 Premiere에서 **UXP 플러그인 리로드 + Connect** 필요.
