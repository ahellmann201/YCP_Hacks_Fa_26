"""One-controller, acknowledged stop-and-capture scans; three atomic sample records."""
import asyncio
import hashlib
import io
import json
import os
import shutil
import time
from pathlib import Path
from uuid import uuid4, uuid5, UUID

import httpx
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field


class MotorTransport:
    async def request(self, method, path, data=None):
        url=os.getenv('SCANNER_MOTOR_URL','http://127.0.0.1:8765').rstrip('/')
        try:
            async with httpx.AsyncClient(timeout=2,trust_env=False) as client:
                response=await client.request(method,url+path,json=data,headers={'X-Scanner-Motor':'1'})
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError,ValueError) as exc:
            raise HTTPException(503,'UNO Q is not ready. Check its USB connection and automatic-scan setup.') from exc


class AutomaticCapture:
    def __init__(self, store, uploads, motor=None):
        self.store=store; self.uploads=Path(uploads)
        self.motor=motor or MotorTransport()
        self.lock=asyncio.Lock()
        self.runs={}; self.active=None

    def require(self, scan_id):
        run=self.runs.get(scan_id)
        if not run: raise HTTPException(404,'Scan no longer available. Start a new scan.')
        self.store.require_active(run['session_id'])
        if run['phase']=='stopped': raise HTTPException(409,'Scan stopped. Start a new scan.')
        if run['phase']!='done' and time.monotonic()-run['touched']>90:
            run['phase']='stopped'
            raise HTTPException(409,'Scan expired. Start a new scan.')
        run['touched']=time.monotonic()
        return run

    async def stop_motor(self):
        try: await self.motor.request('POST','/stop',{})
        except Exception: pass # MCU also stops after 1.5 s without status heartbeats.

    def available_lock(self):
        if self.lock.locked(): raise HTTPException(409,'A scan operation is already running.')

    async def start(self, session_id, date_received, speed=1):
        self.available_lock()
        async with self.lock:
            self.store.require_active(session_id)
            if self.active:
                old=self.runs[self.active]
                if old['phase'] not in ('done','stopped'):
                    if time.monotonic()-old['touched']<90: raise HTTPException(409,'Another scan is active.')
                    old['phase']='stopped'; await self.stop_motor()
            status=await self.motor.request('GET','/status')
            if status.get('protocol')!=1 or status.get('state') not in (0,3,4) or not status.get('boot'):
                raise HTTPException(409,'Motor is busy or automatic-scan firmware is missing.')
            scan_id=uuid4().hex
            run={'id':scan_id,'session_id':session_id,'date_received':date_received,
                 'speed':speed,'boot':status['boot'],'phase':'ready','view':0,'frames':{},
                 'touched':time.monotonic(),'record_ids':[]}
            self.runs[scan_id]=run; self.active=scan_id
            (self.uploads/('.capture-'+scan_id)).mkdir(parents=True)
            # Completed history is only needed for near-term retry acknowledgments.
            for key in list(self.runs):
                if len(self.runs)<=64: break
                if key!=scan_id and self.runs[key]['phase'] in ('done','stopped'): del self.runs[key]
            return {'scan_id':scan_id,'view':0,'views':8}

    async def advance(self, scan_id, view):
        self.available_lock()
        async with self.lock:
            run=self.require(scan_id)
            if run['view']==view and run['phase']=='ready': return {'view':view,'ready':True}
            if run['phase']!='ready' or view!=run['view']+1 or run['view'] not in run['frames'] or not 1<=view<=7:
                raise HTTPException(409,'Save the current view before advancing one position.')
            run['phase']='moving'
            try:
                result=await self.motor.request('POST','/move',{'request_id':f'{scan_id}:{view}','speed':run['speed']})
                if result.get('boot')!=run['boot']: raise HTTPException(409,'UNO Q agent restarted. Start a new scan.')
                deadline=time.monotonic()+15
                while time.monotonic()<deadline:
                    if run['phase']=='stopped': raise HTTPException(409,'Scan stopped.')
                    state=await self.motor.request('GET','/status')
                    if state.get('boot')!=run['boot'] or state.get('id')!=result['command_id']:
                        raise HTTPException(409,'Motor restarted or its command changed. Scan stopped.')
                    if state['state']==3:
                        # Stop may have arrived while status RPC was in flight.
                        if run['phase']=='stopped': raise HTTPException(409,'Scan stopped.')
                        run['view']=view; run['phase']='ready'; run['touched']=time.monotonic()
                        return {'view':view,'ready':True}
                    if state['state'] not in (1,2): raise HTTPException(409,'Motor stopped before completing the view.')
                    await asyncio.sleep(.1)
                raise HTTPException(504,'Motor timed out. Scan stopped.')
            except BaseException:
                run['phase']='stopped'; await self.stop_motor(); raise

    @staticmethod
    def crop_frame(raw):
        try:
            with Image.open(io.BytesIO(raw)) as source:
                if source.width*source.height>32_000_000: raise ValueError('Photo is too large.')
                image=ImageOps.exif_transpose(source).convert('RGB')
                width,height=image.size
                if width<height or width<900: raise ValueError('Use a landscape camera frame at least 900 pixels wide.')
                crops=[]
                for station in range(3):
                    box=(width*station//3,0,width*(station+1)//3,height)
                    buffer=io.BytesIO(); image.crop(box).save(buffer,format='JPEG',quality=95)
                    if buffer.tell()>10*1024*1024: raise ValueError('Cropped photo exceeds 10 MB.')
                    crops.append(buffer.getvalue())
                return crops
        except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError) as exc:
            raise HTTPException(400,str(exc) or 'Unreadable camera frame.') from exc

    async def save_view(self, scan_id, view, raw):
        self.available_lock()
        async with self.lock:
            run=self.require(scan_id)
            digest=hashlib.sha256(raw).hexdigest()
            if view in run['frames']:
                if run['frames'][view]!=digest: raise HTTPException(409,'This view already has a different photo.')
                return {'view':view,'saved':True}
            if run['phase']!='ready' or view!=run['view']: raise HTTPException(409,'Wait until the motor finishes this view.')
            crops=await asyncio.to_thread(self.crop_frame,raw)
            if run['phase']=='stopped': raise HTTPException(409,'Scan stopped.')
            folder=self.uploads/('.capture-'+scan_id)
            for station,crop in enumerate(crops):
                (folder/f'{station}_{view}.jpg').write_bytes(crop)
            run['frames'][view]=digest; run['touched']=time.monotonic()
            return {'view':view,'saved':True}

    async def finish(self, scan_id):
        self.available_lock()
        async with self.lock:
            run=self.require(scan_id)
            if run['phase']=='done': return {'record_ids':run['record_ids'],'queued_samples':3}
            if run['phase']!='ready' or len(run['frames'])!=8: raise HTTPException(409,'All eight views are required.')
            source=self.uploads/('.capture-'+scan_id)
            records=[]; destinations=[]
            try:
                for station in range(3):
                    record_id=uuid5(UUID(scan_id),str(station)).hex
                    folder=self.uploads/record_id
                    folder.mkdir(); destinations.append(folder)
                    images=[]
                    for view in range(8):
                        name=f'image_{view+1}.jpg'; raw=(source/f'{station}_{view}.jpg').read_bytes()
                        (folder/name).write_bytes(raw)
                        images.append({'filename':name,'size_bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
                                       'view_index':view,'nominal_angle_degrees':view*45})
                    sample={'record_id':record_id,'session_id':run['session_id'],'created_at':self.store.now(),
                            'date_received':run['date_received'],'images':images,'image_count':8,
                            'capture_scan_id':scan_id,'capture_station':['left','middle','right'][station]}
                    (folder/'sample.json').write_text(json.dumps(sample,indent=2),encoding='utf-8')
                    records.append(sample)
                self.store.register_batch(run['session_id'],[s['record_id'] for s in records],
                                          samples={s['record_id']:s for s in records})
            except Exception:
                for folder in destinations: shutil.rmtree(folder)
                raise
            run['record_ids']=[s['record_id'] for s in records]; run['phase']='done'
            # Mark done before cleanup: cleanup failure must never enqueue twice.
            shutil.rmtree(source,ignore_errors=True)
            return {'record_ids':run['record_ids'],'queued_samples':3}

    async def stop(self, scan_id):
        run=self.runs.get(scan_id)
        if not run: raise HTTPException(404,'Scan not found.')
        if run['phase']!='done': run['phase']='stopped'
        if self.active==scan_id: await self.stop_motor()
        return {'stopped':True,'saved_views':len(run['frames'])}


class StartScan(BaseModel):
    session_id:str
    date_received:str
    speed:int=Field(default=1,ge=1,le=3)


class AdvanceScan(BaseModel):
    view:int=Field(ge=1,le=7)


def make_router(service, valid_date):
    router=APIRouter(prefix='/capture-scans')
    @router.post('')
    async def start(value:StartScan):
        if not valid_date(value.date_received): raise HTTPException(400,'Invalid Date Received.')
        return await service.start(value.session_id,value.date_received,value.speed)
    @router.post('/{scan_id}/advance')
    async def advance(scan_id:str,value:AdvanceScan): return await service.advance(scan_id,value.view)
    @router.post('/{scan_id}/views')
    async def save(scan_id:str,view:int=Form(...),file:UploadFile=File(...)):
        try:
            raw=await file.read(10*1024*1024+1)
            if not raw or len(raw)>10*1024*1024: raise HTTPException(413,'Camera frame must be 1 byte to 10 MB.')
            return await service.save_view(scan_id,view,raw)
        finally: await file.close()
    @router.post('/{scan_id}/finish')
    async def finish(scan_id:str): return await service.finish(scan_id)
    @router.post('/{scan_id}/stop')
    async def stop(scan_id:str): return await service.stop(scan_id)
    return router
