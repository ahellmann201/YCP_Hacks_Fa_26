// Exercise the actual browser capture code with fake images and upload transport.
const fs=require('node:fs'), vm=require('node:vm'), assert=require('node:assert/strict');
const html=fs.readFileSync('static/index.html','utf8');
const code='const photoQueue=[];\n'+html.slice(html.indexOf('let cameraStream=null,'),html.indexOf('window.addEventListener("beforeunload"'));
const elements=new Map(), draws=[], uploads=[];
function element() { return {value:'',checked:false,disabled:false,hidden:false,classList:{add(){},remove(){},toggle(){}},append(){},replaceChildren(){}}; }
const $=id=>{ if(!elements.has(id)) elements.set(id,element()); return elements.get(id); };
$('#capture-mode').value='3';
let attempts=0, failAt=0;
const context=vm.createContext({$,File,Blob,FormData,console,Uint8Array,Date,Set,Math,setTimeout,clearTimeout,navigator:{},
 URL:{createObjectURL:()=> 'blob:test',revokeObjectURL(){}},
 Image:class { naturalWidth=901; naturalHeight=600; set src(value) {this.onload();} },
 document:{hidden:false,addEventListener(){},createElement(tag){ if(tag==='canvas') return {getContext:()=>({drawImage:(...args)=>draws.push(args.slice(1))}),toBlob:cb=>cb(new Blob(['jpeg'],{type:'image/jpeg'}))};return element(); }},
 window:{addEventListener(){}},setInterval(){},uploading:false,finishing:false,
 renderBar(){},say(){},post:value=>({method:'POST',body:JSON.stringify(value)}),ensureSession:async()=>{},sessionId:'session',today:()=> '2026-11-08',refresh:async()=>{},
 api:async(url,options)=>{attempts++;if(attempts===failAt) throw new Error('Test failure');uploads.push([...options.body.getAll('files')]);return {};}
});
vm.runInContext(code,context);
const run=source=>vm.runInContext(source,context);
(async()=>{
 await run('addPhotos([new File(["photo"],"a.jpg",{type:"image/jpeg"}),new File(["photo"],"b.jpg",{type:"image/jpeg"})])');
 assert.equal(run('photoQueue.length'),6);
 assert.deepEqual(draws.slice(0,3).map(a=>[a[0],a[2]]),[[0,300],[300,300],[600,301]]);
 failAt=2;
 await $('#upload-captured').onclick();
 assert.equal(uploads.length,1);assert.equal(uploads[0].length,2);
 assert.equal(run('photoQueue.length'),4);assert.equal(run('captureUploadPending'),true);
 await run('addPhotos([new File(["photo"],"c.jpg",{type:"image/jpeg"})])');assert.equal(run('photoQueue.length'),4);
 failAt=0;await $('#upload-captured').onclick();
 assert.equal(uploads.length,3);assert.ok(uploads.every(group=>group.length===2));
 assert.ok(uploads.every(group=>new Set(group.map(file=>file.name.split('_')[1])).size===1));
 assert.equal(run('photoQueue.length'),0);assert.equal(run('captureUploadPending'),false);
 $('#capture-mode').value='1';
 await run('addPhotos([new File(["photo"],"one.jpg",{type:"image/jpeg"})])');
 assert.equal(run('photoQueue.length'),1);await $('#upload-captured').onclick();assert.equal(uploads[3].length,1);
 $('#capture-mode').value='3';$('#scan-speed').value='1';
 const video=$('#camera-preview');Object.assign(video,{videoWidth:901,videoHeight:600,paused:false,ended:false,
   requestVideoFrameCallback:callback=>{queueMicrotask(callback);return 1;},cancelVideoFrameCallback(){}});
 run('cameraStream={getVideoTracks:()=>[{readyState:"live",muted:false}]}');
 let autoCalls=[], failView=-1, cancelDuringMove=false;
 context.api=async(url,options)=>{
   autoCalls.push(url);
   if(url==='/capture-scans')return {scan_id:'scan'};
   if(url.endsWith('/advance') && cancelDuringMove)run('automaticCancelled=true');
   if(url.endsWith('/views') && Number(options.body.get('view'))===failView)throw new Error('Camera upload failed');
   return url.endsWith('/finish')?{queued_samples:3}:{};
 };
 await $('#scan-three').onclick();
 assert.equal(autoCalls.filter(x=>x.endsWith('/advance')).length,7);
 assert.equal(autoCalls.filter(x=>x.endsWith('/views')).length,8);
 assert.equal(autoCalls.filter(x=>x.endsWith('/finish')).length,1);
 assert.equal(run('automaticScanning'),false);assert.equal(run('uploading'),false);
 autoCalls=[];failView=2;await $('#scan-three').onclick();
 assert.equal(autoCalls.filter(x=>x.endsWith('/advance')).length,2);
 assert.ok(autoCalls.includes('/capture-scans/scan/stop'));assert.ok(!autoCalls.some(x=>x.endsWith('/finish')));
 autoCalls=[];failView=-1;cancelDuringMove=true;await $('#scan-three').onclick();
 assert.equal(autoCalls.filter(x=>x.endsWith('/views')).length,1);
 assert.ok(autoCalls.includes('/capture-scans/scan/stop'));
 console.log('PASS: exact three-way crop bounds, independent samples, partial-failure retry, capture lock, original single-tube path.');
 console.log('PASS: automatic 8-view / 7-movement sequence, upload failure stops scan, Stop during movement prevents next capture.');
})().catch(error=>{console.error(error);process.exitCode=1;});
