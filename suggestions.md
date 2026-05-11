# 파이프라인 개선 제안

> **갱신 일자**: 2026-05-11

## 컨텍스트 파이프라인

- [ ] Ghost 소스를 컨텍스트에서 제외

## 생성 프롬프트 (`prompt.md`)

- [ ] `generation_error`가 비어 있지 않은 조건 강화
- [ ] `include_reasoning` 플래그를 프롬프트 수준에서 구현
- [ ] 컨텍스트 내 필드 간 모순에 대한 안전장치 추가 — 모순을 조용히 해소하지 말고 `generation_error`에 명시적으로 기록. 소스 간 표현 방식·강조 수준의 차이는 모순으로 간주하지 않음

## 생성 파이프라인 (`main.py`)

- [ ] 토큰 소비 편차 억제를 위해 extended thinking 상한 설정 (`budget_tokens`)
