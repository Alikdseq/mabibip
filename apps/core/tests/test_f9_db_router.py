import pytest

from config.db_routers import PrimaryReplicaRouter


@pytest.mark.django_db
def test_f9_t1_router_routes_reads_to_replica_when_enabled(settings):
    from apps.stations.models import ServiceStation

    settings.READ_REPLICA_ENABLED = True
    settings.DATABASES["replica"] = settings.DATABASES["default"]

    r = PrimaryReplicaRouter()
    assert r.db_for_read(ServiceStation) == "replica"
    assert r.db_for_write(ServiceStation) == "default"

