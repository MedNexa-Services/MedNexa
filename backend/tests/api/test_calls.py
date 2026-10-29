from datetime import UTC, datetime, timedelta

from tests.api.helpers import create_hospital


async def test_call_lifecycle_endpoints(client) -> None:
    hospital = await create_hospital(client)
    started = await client.post(
        "/api/v1/calls", json={"hospital_id": hospital["id"], "caller_phone": "98765 43210"}
    )
    assert started.status_code == 201
    call_id = started.json()["id"]

    for role, content in [("ASSISTANT", "Namaste!"), ("USER", "OPD timing?")]:
        logged = await client.post(
            f"/api/v1/calls/{call_id}/logs", json={"role": role, "content": content}
        )
        assert logged.status_code == 201
    tool = await client.post(
        f"/api/v1/calls/{call_id}/logs",
        json={"role": "TOOL", "content": "", "tool_called": "get_hospital_info",
              "tool_result": "[...]"},
    )  # fmt: skip
    assert tool.json()["tool_called"] == "get_hospital_info"

    ended = await client.post(
        f"/api/v1/calls/{call_id}/end",
        json={"call_outcome": "INFO_PROVIDED", "summary": "OPD timings", "language_detected": "hi"},
    )
    assert ended.json()["total_turns"] == 2
    assert ended.json()["language_detected"] == "hi"

    detail = (await client.get(f"/api/v1/calls/{call_id}")).json()
    assert [log["role"] for log in detail["logs"]] == ["ASSISTANT", "USER", "TOOL"]

    late = await client.post(f"/api/v1/calls/{call_id}/logs", json={"role": "USER", "content": "?"})
    assert late.status_code == 422


async def test_call_listing_filters(client) -> None:
    hospital = await create_hospital(client)
    ids = []
    for phone, outcome, escalated in [
        ("9876543210", "BOOKED", False),
        ("9812345678", "ESCALATED", True),
    ]:
        call = (
            await client.post(
                "/api/v1/calls", json={"hospital_id": hospital["id"], "caller_phone": phone}
            )
        ).json()
        await client.post(
            f"/api/v1/calls/{call['id']}/end",
            json={"call_outcome": outcome, "escalated_to_human": escalated},
        )
        ids.append(call["id"])

    def query(**params):
        return client.get("/api/v1/calls", params=params)

    newest_first = (await query()).json()["items"]
    assert [c["id"] for c in newest_first] == ids[::-1]
    assert (await query(caller_phone="+91 98765 43210")).json()["total"] == 1
    assert (await query(outcome="ESCALATED")).json()["total"] == 1
    assert (await query(escalated=False)).json()["total"] == 1

    future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    assert (await query(started_after=future)).json()["total"] == 0
    assert (await query(started_before=future)).json()["total"] == 2


async def test_call_for_unknown_hospital_is_404(client) -> None:
    response = await client.post(
        "/api/v1/calls",
        json={"hospital_id": "00000000-0000-0000-0000-000000000000", "caller_phone": "9876543210"},
    )
    assert response.status_code == 404


async def test_withheld_caller_number_is_logged_as_anonymous(client) -> None:
    hospital = await create_hospital(client)
    for withheld in ["anonymous", "", "Restricted"]:
        response = await client.post(
            "/api/v1/calls", json={"hospital_id": hospital["id"], "caller_phone": withheld}
        )
        assert response.status_code == 201
        assert response.json()["caller_phone"] == "anonymous"
