from uuid import uuid4
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.tests.api_auth import authenticate
from backend.tests.test_api import SAMPLE

def test_synchronize_returns_matching_assessment_and_quality_state():
    with TestClient(app) as client:
        assert client.post('/api/v1/telemetry/synchronize',json=SAMPLE).status_code==401
        authenticate(client)
        sample={**SAMPLE,'engine_id':f'UI_TEST_{uuid4().hex[:12]}'}
        result=client.post('/api/v1/telemetry/synchronize',json=sample)
        assert result.status_code==201
        data=result.json()
        assert data['assessment']['timestamp']==data['state']['synchronized_at']
        assert data['assessment']['health_index']==data['state']['health']['overall_index']
        assert data['state']['synchronized'] is True
        assert client.get(f"/api/v1/engines/{sample['engine_id']}/latest").json()['state']==data['state']
        # Repeating a timestamp must return its rejected state, not the prior valid state.
        repeated=client.post('/api/v1/telemetry/synchronize',json=sample).json()
        assert repeated['state']['synchronized'] is False
        assert repeated['state']['telemetry']['parameters']['rpm']['quality']=='STALE'

def test_synchronize_does_not_accept_out_of_schema_signals():
    with TestClient(app) as client:
        authenticate(client)
        assert client.post('/api/v1/telemetry/synchronize',json={**SAMPLE,'rpm':9000}).status_code==422

def test_simulation_includes_diagnostic_state_for_each_sample():
    with TestClient(app) as client:
        authenticate(client)
        response=client.post('/api/v1/simulations',json={'profile':'NORMAL_CRUISE','duration_minutes':1,'interval_seconds':5,'degradation_scenario':'LUBRICATION_DEGRADATION','degradation_severity':1})
        assert response.status_code==200
        data=response.json()
        assert len(data['states'])==len(data['telemetry'])==len(data['assessments'])
        for telemetry,state in zip(data['telemetry'],data['states']):
            assert telemetry['timestamp']==state['synchronized_at']
            for fault in state['faults']['diagnostics']:
                assert fault['probability'] is None
                assert {'fault_code','engineering_score','uncertainty','affected_subsystems','evidence'} <= fault.keys()
