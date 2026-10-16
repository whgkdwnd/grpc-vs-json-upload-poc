# gRPC vs JSON vs REST 스트리밍 파일 업로드 비교

악성코드 다운로드 탐지 플랫폼([2026-Teecher-Team-C](https://github.com/2026-Teecher-Team-C))에서 로컬 에이전트가
검사 서버로 파일(최대 500MB)을 올리는 방식을 gRPC client-streaming으로 정했다. 이 레포는 그 선택을 측정으로
검증한 실험이다. 결정은 먼저 내렸고, 이 실험은 2026-10-16에 따로 했다.

## 비교한 것

| 방식 | 클라이언트 | 서버 |
|---|---|---|
| JSON | 파일을 base64로 인코딩해 `{"sha256","filename","data"}` 하나로 POST | 본문 전체를 읽고 파싱·디코딩한 뒤 디스크에 씀 |
| REST 스트리밍 | 바이너리 본문을 그대로 POST(`application/octet-stream`), sha256·파일명은 헤더 | 본문을 64KB씩 읽어 바로 디스크에 씀 |
| gRPC | 64KB 청크로 client-streaming, sha256·파일명은 첫 메시지 | 청크를 받는 대로 디스크에 씀 |

세 방식 모두 Python(표준 `http.server`·`http.client` / `grpcio`)이라 언어 차이는 섞이지 않는다. 세 방식 모두
sha256을 계산해 함께 보낸다(REST 스트리밍·gRPC는 파일을 한 번 더 읽어 스트리밍으로 계산). 조건마다 서버
프로세스를 새로 띄우고, 최대 메모리는 각 프로세스의 `ru_maxrss`로 잰다.

## 결과 (macOS, Apple Silicon, 같은 장비 안 loopback, 조건별 3회, 범위)

| 파일 | 방식 | 전송량 | 시간 | 서버 최대 메모리 | 클라이언트 최대 메모리 |
|---|---|---|---|---|---|
| 50MB | JSON | 66.7MB | 0.62–0.71s | 261MB | 261MB |
| 50MB | REST 스트리밍 | 50.0MB | 0.11–0.12s | 23MB | 22MB |
| 50MB | gRPC | 50.0MB | 0.15–0.19s | 39–46MB | 36MB |
| 200MB | JSON | 266.7MB | 2.48–2.98s | 964–977MB | 976MB |
| 200MB | REST 스트리밍 | 200.0MB | 0.31–0.50s | 23MB | 22MB |
| 200MB | gRPC | 200.0MB | 0.44–0.62s | 40–50MB | 36–37MB |
| 500MB | JSON | 666.7MB | 6.66–7.50s | 1,772–2,301MB | 2,116–2,407MB |
| 500MB | REST 스트리밍 | 500.0MB | 0.79–1.20s | 23MB | 22MB |
| 500MB | gRPC | 500.0MB | 1.05–1.38s | 41–47MB | 37MB |

원본 측정값은 [`results-2026-10-16-macos-v2.jsonl`](results-2026-10-16-macos-v2.jsonl). 처음 실험(JSON·gRPC만,
2회, gRPC가 sha256을 보내지 않음)은 [`results-2026-10-16-macos.jsonl`](results-2026-10-16-macos.jsonl).

- **JSON**은 base64 때문에 전송량이 33% 늘고, 메모리가 파일 크기의 4~5배로 커진다. 500MB면 서버·클라이언트
  모두 2GB를 넘었다.
- **REST 스트리밍과 gRPC는 둘 다 파일 크기와 상관없이 메모리가 일정**했다. 업로드 성능만 보면 둘 다 충분하다.
- 이 실험에서는 REST 스트리밍이 메모리(약 23MB 대 40MB)와 시간 모두 조금 더 가벼웠다. gRPC 쪽 차이는 대부분
  `grpcio` 런타임이 기본으로 쓰는 메모리로 보인다(파일 크기가 늘어도 차이가 커지지 않음).
- 결론: **업로드 성능은 gRPC를 고를 이유가 아니다.** 단순 JSON을 피해야 할 이유일 뿐이다. gRPC를 고른 이유는
  스키마 강제·버전 호환·마감 시간(deadline) 같은 다른 데서 찾아야 한다.

## 한계

- 같은 장비 안에서 주고받아 네트워크 지연은 거의 빠져 있다. 실제 네트워크에서는 JSON의 33% 추가 전송량이
  시간에 그대로 더해진다.
- REST 스트리밍은 Python 표준 라이브러리의 가장 단순한 구현이다. 실제 서버(Spring MVC + nginx)에서는 multipart
  처리 방식이나 nginx 요청 버퍼링(`proxy_request_buffering`) 설정에 따라 결과가 달라질 수 있다.
- 조건별 3회라 시간은 편차가 있다. 전송량과 메모리는 실행마다 거의 같았다.

## 다시 돌리기

[uv](https://docs.astral.sh/uv/)가 필요하다.

```bash
./run.sh                       # 50MB, 200MB 각 2회 (기본값)
SIZES="500" TRIALS=3 ./run.sh  # 크기·횟수 바꾸기
```

결과는 `results.jsonl`에 한 줄씩 쌓인다.
