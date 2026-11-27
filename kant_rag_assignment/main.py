"""KANT NEXT DevDesk RAG. 이 파일의 빈칸만 작성하세요."""
import uuid

from qdrant_client import models

import support


def todo(message):
    raise NotImplementedError(message)


# chunk_id용 UUID 이름공간. 같은 원문과 번호는 실행을 다시 해도 같은 ID가 나옵니다.
CHUNK_NAMESPACE = uuid.UUID("6f1d4a2c-9b3e-4c57-8a10-2d7e5b4c9f08")


# 필수 1. 문서를 저장하고 현행 자료만 검색하기
def prepare_chunks(documents):
    chunks = []
    for document in documents:
        seen = set()
        number = 0
        for paragraph in document["paragraphs"]:
            text = " ".join(paragraph.split())
            if not text or text == "KANT NEXT | 내부 문서" or text in seen:
                continue
            seen.add(text)
            chunk = {
                "chunk_id": str(uuid.uuid5(CHUNK_NAMESPACE, f"{document['document_id']}:{number}")),
                "document_id": document["document_id"],
                "title": document["title"],
                "category": document["category"],
                "status": document["status"],
                "source": document["source"],
                "text": text,
            }
            chunks.append(chunk)
            number += 1
    # 이유: 제공 문단은 승인 절차처럼 한 문장이 한 조건이라 더 쪼개면 근거가 끊기므로 문단을 청크 단위로 둡니다.
    # chunk_id가 UUID라 원문을 역산할 수 없으므로 document_id와 source를 함께 저장해야 출처를 추적할 수 있고,
    # status와 category는 현행/분류 필터에 쓰이므로 청크마다 복사해 둡니다.
    return chunks


def build_index(chunks, embedder):
    texts = ["passage: " + row["title"] + "\n" + row["text"] for row in chunks]
    vectors = embedder.encode(texts, normalize_embeddings=True)
    client = support.empty_store(len(vectors[0]))
    points = []
    for i, (row, vector) in enumerate(zip(chunks, vectors, strict=True)):
        point = models.PointStruct(id=i, vector=list(vector), payload=row)
        points.append(point)
    client.upsert(collection_name="devdesk", points=points, wait=True)
    return client


def search(client, embedder, question, category, top_k=2):
    if type(top_k) is not int or not 1 <= top_k <= 5:
        raise ValueError("top_k는 1~5의 정수여야 합니다.")
    vector = embedder.encode(["query: " + question], normalize_embeddings=True)[0]
    scope = models.Filter(must=[
        models.FieldCondition(key="status", match=models.MatchValue(value="current")),
        models.FieldCondition(key="category", match=models.MatchValue(value=category)),
    ])
    hits = client.query_points(collection_name="devdesk", query=list(vector),
                               query_filter=scope, limit=top_k, with_payload=True).points
    return [{**hit.payload, "score": hit.score} for hit in hits]


# 필수 2. 별칭 검색을 개선하고 답변을 비교하기
def rewrite_query(question, aliases):
    rewritten = question
    for alias, formal_name in aliases.items():
        rewritten = rewritten.replace(alias, formal_name)
    return rewritten


def answer_question(question, rows, generate):
    if not rows:
        return {"answer": "확인할 문서가 없습니다.", "citations": [], "needs_human": True}
    context = "\n\n".join(f"[{row['chunk_id']}] {row['text']}" for row in rows)
    reply = support.validate_shape(generate(question, context))
    allowed = {row["chunk_id"] for row in rows}
    if not set(reply["citations"]) <= allowed:
        raise ValueError("검색하지 않은 출처가 있습니다.")
    if reply["needs_human"] == bool(reply["citations"]):
        raise ValueError("답변에는 출처가 필요하며 담당자 확인에는 출처를 비웁니다.")
    return reply


def make_golden():
    return [
        {"question_id": "mine-vpn-approval",
        "question": "초록문 사용 승인은 어디에 요청하나요?",
        "category": "access",
        "reference_answer": "보안팀에 승인을 요청합니다.",
        "relevant_document_ids": ["vpn"],
        "required_terms": ["보안팀"]},
        {"question_id": "mine-overseas-expense",
        "question": "해외 지사 출장비는 어떻게 정산하나요?",
        "category": "overseas",
        "reference_answer": "해외 출장비 정산 절차를 다루는 현행 문서가 없어 담당자 확인이 필요합니다.",
        "relevant_document_ids": [],
        "required_terms": []},
    ]


def measure(case, rows, reply):
    expected = set(case["relevant_document_ids"])
    found = {row["document_id"] for row in rows}
    recall = len(expected & found) / len(expected) if expected else None
    answer_ok = (all(term in reply["answer"] for term in case["required_terms"])
                 and not reply["needs_human"]) if expected else reply["needs_human"]
    failure = "없음"
    if expected and recall < 1:
        failure = "검색 누락"
    elif not answer_ok:
        failure = "답변 확인 필요" if expected else "보류 실패"
    # 관측: 문서 Recall 0.667 -> 1.000, answer_check 0.750 -> 1.000이며 악화된 질문은 없습니다.
    # mine-vpn-approval만 개선되었습니다. 변환 전에는 "초록문"이 door 문서(초록색, 출입문)에 0.8225로 걸려
    # vpn 문서를 놓친 검색 누락이고, 답변 문제는 아닙니다. 모델은 틀린 문서로 답하지 않고 보류했습니다.
    # 변환 후 vpn 문서를 0.9197로 찾아 "보안팀"을 답했습니다. given-token은 전후 모두 token 문서이지만
    # 점수가 0.7925에서 0.9367로 올라 top_k=1에서의 여유가 늘어 변환을 적용할 이유가 됩니다.
    # 한계: 단순 치환이라 "API 토큰를"처럼 조사가 어긋나고, 사전에 없는 은어는 그대로 누락됩니다.
    return {"document_recall": recall, "answer_check": bool(answer_ok), "failure": failure}


# 선택 심화 1. 두 검색 순위를 합쳐 근거를 모으기
def fuse_rankings(rankings, top_k=2):
    # 선택 심화: 문제의 RRF 규칙에 맞춰 직접 작성하세요.
    return todo("검색 순위 목록을 RRF 점수로 합치세요.")


if __name__ == "__main__":
    support.cli(globals())
