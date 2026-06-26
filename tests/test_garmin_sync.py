"""Testes da orquestração do sync Garmin — sem login real, sem rede.

Injetamos um cliente FAKE (lista de atividades) e sobrescrevemos o passo de
download+ingestão. Testa a lógica incremental: só processa atividades novas.
O conftest semeia garmin_activity_id 1 e 2; logo só o id novo deve ser processado.
"""

from ingestion.garmin_sync import GarminSync


class FakeClient:
    def __init__(self, activities):
        self._activities = activities

    def get_activities_by_date(self, start, end, *args, **kwargs):
        return self._activities


def _make_sync(activities, processed):
    sync = GarminSync(client=FakeClient(activities), user_id="u", device_id=1)
    # sobrescreve o download+ingestao real por um registrador
    sync._process_activity = lambda gid, name: processed.append((gid, name)) or {"status": "imported"}
    return sync


def test_sync_processes_only_new_activities():
    activities = [
        {"activityId": 1, "activityName": "Ja existe A"},
        {"activityId": 2, "activityName": "Ja existe B"},
        {"activityId": 99, "activityName": "Nova corrida"},
    ]
    processed = []
    sync = _make_sync(activities, processed)
    r = sync.sync("2026-06-01", "2026-06-30")
    assert r["total"] == 3
    assert r["new"] == 1
    assert processed == [(99, "Nova corrida")]


def test_sync_no_new_activities():
    activities = [{"activityId": 1, "activityName": "A"}, {"activityId": 2, "activityName": "B"}]
    processed = []
    sync = _make_sync(activities, processed)
    r = sync.sync("2026-06-01", "2026-06-30")
    assert r["new"] == 0 and processed == []


def test_existing_ids_reads_db():
    sync = GarminSync(client=FakeClient([]), user_id="u", device_id=1)
    assert {1, 2} <= sync.existing_garmin_ids()
