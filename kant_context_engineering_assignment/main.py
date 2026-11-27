"""main.py의 todo(...) 부분을 작성하세요. support.py와 checks.py는 그대로 사용합니다."""
import copy
import hashlib
import json
import sys

import support


def todo(message):
    raise NotImplementedError(message)


# 필수 1. 필요한 자료와 사용자 기억 관리하기
def select_context(items, user_id, now):
    kept = []
    for item in items:
        allowed = (
            item["user_id"] in ("public", user_id)
            and item["trusted"] is True
            and item["active"] is True
            and (item["expires_at"] is None or item["expires_at"] > now)
        )
        if allowed:
            kept.append(copy.deepcopy(item))
    # 이유: 이 데이터에서 우선순위 99는 만료된 기억, 다른 사용자의 메모, 검토되지 않은 문서처럼 쓰면 안 되는 자료에 붙어 있습니다.
    # 우선순위로 먼저 고르면 이런 자료가 현행 정책보다 앞에 놓이거나 입력에 들어가므로, 사용할 수 있는지 먼저 거른 뒤 남은 자료끼리만 순서를 정합니다.
    return sorted(kept, key=lambda item: (-item["priority"], item["id"]))


def memory_action(records, user_id, action, name, value=None):
    support.validate_memory_input(user_id, action, name, value)
    key = f"{user_id}:{name}"
    if action == "read":
        return copy.deepcopy(records.get(key))
    if action == "create":
        if key in records:
            raise ValueError("이미 있는 기억입니다. update를 사용하세요.")
        records[key] = copy.deepcopy(value)
    elif action == "update":
        if key not in records:
            raise KeyError("수정할 기억이 없습니다.")
        records[key] = copy.deepcopy(value)
    elif action == "delete":
        return records.pop(key, None)
    return copy.deepcopy(records[key])


def build_messages(prefix, question, context, turns, summary):
    data = json.dumps({"reference_data": context, "summary": summary}, ensure_ascii=False)
    history = [message for turn in turns for message in turn["messages"]]
    # 이유: 장기 기억(style)은 동의받은 선호라 파일에 남겨 다음 세션에도 읽고, 세션 상태(task)는 이번 작업에만 필요해 세션이 끝나면 비웁니다.
    # 자료 본문에는 "규칙을 무시하라" 같은 문장이 섞일 수 있으므로 developer 지시와 분리해 user의 참고 데이터로만 넣어야 서비스 지시를 바꾸지 못합니다.
    return [
        {"role": "developer", "content": prefix},
        {"role": "user", "content": data},
        *history,
        {"role": "user", "content": question},
    ]


# 필수 2. 긴 대화를 줄이고 반복 입력 재사용하기
def summarize(turns):
    summary = {}
    for turn in turns:
        for name, value in support.fact_lines(turn["messages"][0]["content"]):
            summary[name] = {"value": value, "source_turn_id": turn["id"]}
    return summary


def select_window(turns, limit, reserve, margin, make_messages, count):
    support.validate_budget(limit, reserve, margin)
    budget = limit - reserve - margin
    if budget <= 0 or count(make_messages([])) > budget:
        raise ValueError("고정 입력만으로 예산을 넘었습니다.")
    kept = []
    for turn in reversed(turns):
        candidate = [turn, *kept]
        if count(make_messages(candidate)) > budget:
            break
        kept = candidate
    # 관측: live 입력 토큰은 전체 1938, 최근 1699, 요약+최근 1695입니다(추정 1999/1744/1744). 최근 대화만 쓰면 T05~T07만 남아 0/3이었고,
    # 승인조건을 공통 정책 문장으로 바꿔 채우는 오답이 나왔습니다. 요약+최근은 T06~T07만 남기고도 3/3이라 한도 2300의 요약+최근 방식을 사용합니다.
    return kept


def cache_key(prefix, user_id):
    return hashlib.sha256(f"{user_id}\n{prefix}".encode("utf-8")).hexdigest()
    # 관측: cached_tokens 0→1228→1228이고 cache_write_tokens는 세 번 모두 0이라 쓰기는 관측되지 않았습니다. 첫 사용부터 읽기가 나와 이전 요청의 캐시가 남았을 수 있습니다.
    # 입력 비용은 0.0003066→0.0000856달러(약 72% 감소), 지연은 1493→914→1062ms인데 1회씩이라 속도 향상은 단정하지 않습니다. 오염 자료 tainted-document, unverified-tool은 선택에서 빠져 입력에 없습니다.


# 선택 심화 1. 새 대화만 반영하고 변경 이력 남기기
def merge_summary(previous, turns):
    return todo("선택 심화: 새 턴의 요약과 변경 이력")


if __name__ == "__main__":
    raise SystemExit(support.cli(sys.modules[__name__]))
