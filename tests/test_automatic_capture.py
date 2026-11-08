import asyncio
import io
import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from PIL import Image
from automatic_capture import AutomaticCapture
from scanner.queue.background_scanner import QueueStore


class Motor:
    def __init__(self): self.id=0; self.moves=[]; self.boot='test'; self.stopped=False; self.fail=False
    async def request(self,method,path,data=None):
        if path=='/stop': self.stopped=True;return {'stopped':True}
        if self.fail: raise HTTPException(503,'Disconnected')
        if path=='/move':
            self.id+=1;self.moves.append(data);return {'boot':self.boot,'command_id':self.id}
        return {'boot':self.boot,'protocol':1,'id':self.id,'state':3 if self.id else 0}


def frame():
    im=Image.new('RGB',(903,600));im.paste('red',(0,0,301,600));im.paste('green',(301,0,602,600));im.paste('blue',(602,0,903,600))
    out=io.BytesIO();im.save(out,format='PNG');return out.getvalue()


def build(tmp):
    store=QueueStore(tmp/'db.sqlite3');session=store.create('auto test')['id'];motor=Motor()
    return AutomaticCapture(store,tmp/'uploads',motor),session,motor,store


def test_complete_separate_records_and_idempotence(tmp_path):
    async def scenario():
        service,session,motor,store=build(tmp_path)
        run=await service.start(session,'2026-11-08');sid=run['scan_id']
        for view in range(8):
            if view:
                await service.advance(sid,view);await service.advance(sid,view)
            await service.save_view(sid,view,frame());await service.save_view(sid,view,frame())
        result=await service.finish(sid);assert await service.finish(sid)==result
        assert len(motor.moves)==7
        assert len(set(result['record_ids']))==3
        for station,rid in enumerate(result['record_ids']):
            folder=tmp_path/'uploads'/rid;sample=json.loads((folder/'sample.json').read_text())
            assert sample['image_count']==8 and sample['capture_station']==['left','middle','right'][station]
            assert len(list(folder.glob('*.jpg')))==8
            pixel=Image.open(folder/'image_1.jpg').getpixel((150,200))
            assert pixel[station]>pixel[(station+1)%3]+80
        assert store.status(session)['counts']['queued']==3
    asyncio.run(scenario())


def test_order_and_connection_failure_stop(tmp_path):
    async def scenario():
        service,session,motor,_=build(tmp_path);sid=(await service.start(session,'2026-11-08'))['scan_id']
        with pytest.raises(HTTPException): await service.advance(sid,1)
        with pytest.raises(HTTPException): await service.finish(sid)
        with pytest.raises(HTTPException): await service.start(session,'2026-11-08')
        await service.save_view(sid,0,frame());motor.fail=True
        with pytest.raises(HTTPException): await service.advance(sid,1)
        assert motor.stopped and service.runs[sid]['phase']=='stopped'
        with pytest.raises(HTTPException): await service.save_view(sid,1,frame())
        assert not motor.moves
    asyncio.run(scenario())


def test_motor_restart_and_stop_in_flight(tmp_path):
    async def scenario():
        service,session,motor,_=build(tmp_path);sid=(await service.start(session,'2026-11-08'))['scan_id']
        await service.save_view(sid,0,frame());motor.boot='restart'
        with pytest.raises(HTTPException): await service.advance(sid,1)
        assert motor.stopped
    asyncio.run(scenario())


def test_bad_frame_and_failed_registration_leave_no_partial_samples(tmp_path,monkeypatch):
    async def scenario():
        service,session,motor,store=build(tmp_path);sid=(await service.start(session,'2026-11-08'))['scan_id']
        with pytest.raises(HTTPException): await service.save_view(sid,0,b'not an image')
        for view in range(8):
            if view: await service.advance(sid,view)
            await service.save_view(sid,view,frame())
        def fail(*args,**kwargs): raise RuntimeError('database failure')
        monkeypatch.setattr(store,'register_batch',fail)
        with pytest.raises(RuntimeError): await service.finish(sid)
        assert len(list((tmp_path/'uploads').iterdir()))==1 # staging only; no partial OCR samples
        assert len(service.runs[sid]['frames'])==8
    asyncio.run(scenario())
