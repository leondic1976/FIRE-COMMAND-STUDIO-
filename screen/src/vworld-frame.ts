// Deliberately isolated SDK adapter. This module never imports training state/API code.
export {};
declare const vw:any;
declare const ws3d:any;
declare const Cesium:any;
type Viewport={latitude:number;longitude:number;position:number[];target:number[]};
const channel=new URLSearchParams(location.hash.slice(1)).get('channel');
const parentOrigin=new URL(location.href).origin;
let viewport:Viewport|null=null,viewer:any=null,root:any=null,lastHeight:number|null=null,lastSent=0,started=false,lastPose='';
const status=document.querySelector('#status') as HTMLElement;
const send=(kind:string,extra:Record<string,unknown>={})=>{if(channel)parent.postMessage({channel,kind,...extra},parentOrigin);};
const fail=()=>{status.textContent='브이월드 연결 실패 · 부모 화면에서 다시 시도하세요';send('map-error');};
const vector=(v:unknown):v is number[]=>Array.isArray(v)&&v.length===3&&v.every(n=>typeof n==='number'&&Number.isFinite(n)&&Math.abs(n)<10000);
const matrix=(v:any)=>Array.from({length:16},(_,i)=>v[i]);
function valid(v:unknown):v is Viewport{
 if(!v||typeof v!=='object')return false;const p=v as Viewport;
 return Number.isFinite(p.latitude)&&Math.abs(p.latitude)<=90&&Number.isFinite(p.longitude)&&Math.abs(p.longitude)<=180&&vector(p.position)&&vector(p.target);
}
function update(){
 if(!viewer||!viewport)return;
 try{
  const p=viewport,point=Cesium.Cartographic.fromDegrees(p.longitude,p.latitude),height=viewer.scene.globe.getHeight(point);
  if(!Number.isFinite(height)){status.textContent='지형 높이를 불러오는 중';return;}
  root=Cesium.Transforms.eastNorthUpToFixedFrame(Cesium.Cartesian3.fromDegrees(p.longitude,p.latitude,height));
  const signature=JSON.stringify(p);
  if(signature!==lastPose||lastHeight===null||Math.abs(height-lastHeight)>.3){
   const destination=Cesium.Matrix4.multiplyByPoint(root,new Cesium.Cartesian3(...p.position),new Cesium.Cartesian3());
   const target=Cesium.Matrix4.multiplyByPoint(root,new Cesium.Cartesian3(...p.target),new Cesium.Cartesian3());
   const direction=Cesium.Cartesian3.normalize(Cesium.Cartesian3.subtract(target,destination,new Cesium.Cartesian3()),new Cesium.Cartesian3());
   const up=Cesium.Matrix4.multiplyByPointAsVector(root,Cesium.Cartesian3.UNIT_Z,new Cesium.Cartesian3());
   viewer.camera.setView({destination,orientation:{direction,up}});lastPose=signature;lastHeight=height;
  }
  const now=performance.now();if(now-lastSent<33)return;lastSent=now;
  status.textContent='브이월드3D · 건물별 제공 범위/최신성 확인 필요';status.style.display='none';
  send('map-camera',{camera:{view:matrix(viewer.camera.viewMatrix),projection:matrix(viewer.camera.frustum.projectionMatrix),root:matrix(root)}});
 }catch{fail();}
}
function initialize(){
 if(started||!viewport)return;started=true;
 try{
  const onReady=()=>{if(viewer)return;viewer=ws3d.viewer;if(!viewer?.scene||!viewer?.camera)return;
   viewer.scene.globe.enableLighting=false;
   try{map.getLayerElement('facility_build')?.show();}catch{/* Layer availability varies by SDK/service. */}
   viewer.scene.postRender.addEventListener(update);viewer.resize();update();};
  vw.ws3dInitCallBack=onReady;
  const map=new vw.Map();
  map.setOption({mapId:'vmap',initPosition:new vw.CameraPosition(new vw.CoordZ(viewport.longitude,viewport.latitude,12000),new vw.Direction(0,-65,0)),logo:true,navigation:false});
  map.start();
  const timer=setInterval(()=>{try{if(typeof ws3d!=='undefined'&&ws3d.viewer)onReady();}catch{/* Wait for SDK. */}if(viewer)clearInterval(timer);},250);
  setTimeout(()=>{clearInterval(timer);if(!viewer)fail();},30000);
  addEventListener('resize',()=>viewer?.resize());
 }catch{fail();}
}
addEventListener('message',event=>{
 if(event.source!==parent||event.origin!==parentOrigin||event.data?.channel!==channel)return;
 if(event.data.kind==='viewport'&&valid(event.data.viewport)){
  viewport=event.data.viewport;initialize();viewer?.scene.requestRender?.();
 }
});
addEventListener('error',event=>{event.preventDefault();fail();});
const hello=setInterval(()=>{if(viewport){clearInterval(hello);return;}send('map-frame-ready');},250);
send('map-frame-ready');
