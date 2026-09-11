from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from pydantic import ValidationError
from backend.app.adapters.base import AdapterMode, ProtocolMetadata, TelemetryPacket
from backend.app.adapters.can import CANAdapter, RawCANFrame
from backend.app.adapters.factory import create_adapter
from backend.app.adapters.simulator import SimulatorAdapter, SimulatedCANStream

NOW=datetime.now(timezone.utc)
def packet(sequence,timestamp=None,signals=None):
    return TelemetryPacket(timestamp=timestamp or NOW,sequence_number=sequence,source="TEST",engine_id="ENGINE",
        mission_id="MISSION",signals=signals or {"rpm":2200},quality={},protocol_metadata=ProtocolMetadata(protocol="TEST"))

class QueueAdapter(SimulatorAdapter):
    def __init__(self,**kwargs):
        # Avoid populating the demonstration simulator in sequence unit tests.
        from backend.app.adapters.base import TelemetryAdapter
        TelemetryAdapter.__init__(self,AdapterMode.SIMULATOR,"TEST",**kwargs); self._queue=[]

def test_sequence_buffering_duplicate_detection_and_loss_recovery():
    adapter=QueueAdapter(recovery_timeout_seconds=2)
    assert [x.sequence_number for x in adapter.ingest_packet(packet(0),NOW)]==[0]
    assert adapter.ingest_packet(packet(2),NOW)==[]
    assert adapter.ingest_packet(packet(3),NOW)==[]
    health=adapter.adapter_health()
    assert health.sequence_errors==2 and health.missing_packets==1 and health.buffered_messages==2
    assert [x.sequence_number for x in adapter.ingest_packet(packet(1),NOW)]==[1,2,3]
    assert adapter.adapter_health().recovered_messages==2
    assert adapter.ingest_packet(packet(1),NOW)==[]
    assert adapter.adapter_health().duplicate_messages==1

def test_timeout_declares_gap_lost_and_releases_buffer():
    adapter=QueueAdapter(recovery_timeout_seconds=2); adapter.ingest_packet(packet(10),NOW)
    adapter.ingest_packet(packet(12),NOW)
    released=adapter.recover_loss(NOW+timedelta(seconds=3))
    assert [x.sequence_number for x in released]==[12]
    health=adapter.adapter_health(); assert health.messages_dropped==1 and health.missing_packets==0

def test_stale_and_future_timestamp_detection():
    adapter=QueueAdapter(max_age_seconds=10,max_future_skew_seconds=2)
    assert adapter.ingest_packet(packet(0,NOW-timedelta(seconds=11)),NOW)==[]
    assert adapter.ingest_packet(packet(1,NOW+timedelta(seconds=3)),NOW)==[]
    assert adapter.adapter_health().stale_messages==2

def test_packet_rejects_naive_timestamp():
    with pytest.raises(ValidationError): packet(0,datetime(2026,1,1))

def test_synthetic_can_mapping_decodes_without_manufacturer_claim():
    mapping=Path("backend/app/adapters/sample_synthetic_can.json")
    adapter=CANAdapter(mapping); frame=next(SimulatedCANStream(NOW).frames(1))
    decoded=adapter.decode_frame(frame,"ENGINE","MISSION",0)
    assert decoded is not None and decoded.signals["rpm"]==1800 and decoded.signals["throttle_percent"]==55
    assert decoded.protocol_metadata.extra["signal_database"]=="synthetic-demonstration-can-v1"

def test_unmapped_and_invalid_can_frames_are_counted_not_crashed():
    adapter=CANAdapter(Path("backend/app/adapters/sample_synthetic_can.json"))
    result=adapter.decode_frame(RawCANFrame(0x999,b"\x00"*8,NOW),"ENGINE","MISSION",0)
    assert result is None and adapter.adapter_health().invalid_frames==1 and adapter.adapter_health().messages_dropped==1

def test_factory_supports_all_configured_modes_without_hardware():
    mapping=Path("backend/app/adapters/sample_synthetic_can.json")
    for mode in AdapterMode:
        adapter=create_adapter(mode,mapping)
        assert adapter.adapter_health().mode==mode
    fadec=create_adapter(AdapterMode.FADEC,mapping); fadec.start()
    assert not fadec.adapter_health().connected
    assert "No FADEC compatibility claimed" in fadec.adapter_health().detail

def test_simulator_adapter_produces_complete_packet_metadata():
    adapter=SimulatorAdapter(); adapter.start(); packets=adapter.poll()
    assert packets and packets[0].source=="SIMULATOR"
    assert packets[0].protocol_metadata.clock.synchronized
    assert packets[0].protocol_metadata.extra["synthetic"] is True
    health=adapter.adapter_health(); assert health.connected and health.messages_received==len(packets)
