import asyncio

from teamlead.adapters.thinker.claude_cli import ClaudeCliThinker


def test_missing_binary_raises():
    t = ClaudeCliThinker(claude_bin="definitely_not_claude_xyz")
    try:
        asyncio.run(t.think("hi"))
        assert False, "should raise"
    except RuntimeError as e:
        assert "찾을 수 없음" in str(e)


def test_result_from_envelope_extracts_result():
    env = b'{"type":"result","is_error":false,"result":"hello"}'
    assert ClaudeCliThinker._result_from_envelope(env) == "hello"


def test_result_from_envelope_non_json_passthrough():
    assert ClaudeCliThinker._result_from_envelope(b"plain text") == "plain text"


def test_result_from_envelope_flags_is_error():
    env = b'{"result":"boom","is_error":true}'
    try:
        ClaudeCliThinker._result_from_envelope(env)
        assert False
    except RuntimeError as e:
        assert "is_error" in str(e)


def test_extract_json_strips_fence():
    out = ClaudeCliThinker._extract_json('```json\n{"topics":["a","b"]}\n```')
    assert out == {"topics": ["a", "b"]}


def test_extract_json_plain():
    assert ClaudeCliThinker._extract_json('{"x":1}') == {"x": 1}


def test_extract_json_with_surrounding_text():
    # 앞뒤 설명이 섞여도 첫{~마지막} 구간 파싱
    out = ClaudeCliThinker._extract_json('여기 결과입니다: {"topics":[]} 끝')
    assert out == {"topics": []}


def test_extract_json_failure_raises():
    try:
        ClaudeCliThinker._extract_json("그냥 텍스트, JSON 없음")
        assert False
    except RuntimeError as e:
        assert "파싱 실패" in str(e)


def test_compose_appends_schema_when_present():
    t = ClaudeCliThinker()
    schema = {"type": "object", "properties": {"topics": {"type": "array"}}}
    composed = t._compose("주제 제안", schema)
    assert "주제 제안" in composed and "topics" in composed
    # schema 없으면 원문 그대로
    assert t._compose("그대로", None) == "그대로"


def test_implements_thinker_port():
    from teamlead.ports.thinker import Thinker
    assert isinstance(ClaudeCliThinker(), Thinker)
