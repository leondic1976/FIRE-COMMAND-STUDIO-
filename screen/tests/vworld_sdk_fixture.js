/* Test-only synthetic API surface. No provider code, key, terrain or photograph. */
window.__received=[];window.__cameraViews=[];
addEventListener('message',e=>{if(e.source===parent)window.__received.push(e.data);});
const identity=()=>[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1];
const dot=(a,b)=>a.x*b.x+a.y*b.y+a.z*b.z;
const cross=(a,b)=>new C3(a.y*b.z-a.z*b.y,a.z*b.x-a.x*b.z,a.x*b.y-a.y*b.x);
class C3{constructor(x=0,y=0,z=0){Object.assign(this,{x,y,z});}static fromDegrees(x,y,z=0){return new C3(x,y,z);}static subtract(a,b){return new C3(a.x-b.x,a.y-b.y,a.z-b.z);}static normalize(a){const d=Math.hypot(a.x,a.y,a.z);return new C3(a.x/d,a.y/d,a.z/d);}}
C3.UNIT_Z=new C3(0,0,1);
const listeners=[];
const camera={viewMatrix:identity(),frustum:{projectionMatrix:identity()},setView({destination:p,orientation:{direction:f,up}}){const r=C3.normalize(cross(f,up)),u=cross(r,f);this.viewMatrix=[r.x,u.x,-f.x,0,r.y,u.y,-f.y,0,r.z,u.z,-f.z,0,-dot(r,p),-dot(u,p),dot(f,p),1];window.__cameraViews.push([p.x,p.y,p.z]);}};
const viewer={camera,scene:{globe:{getHeight:()=>0},postRender:{addEventListener:f=>listeners.push(f)},requestRender(){}},resize(){const f=1/Math.tan(21*Math.PI/180),aspect=innerWidth/innerHeight,n=.3,z=10000;camera.frustum.projectionMatrix=[f/aspect,0,0,0,0,f,0,0,0,0,(z+n)/(n-z),-1,0,0,2*z*n/(n-z),0];}};
window.Cesium={Cartesian3:C3,Cartographic:{fromDegrees:(x,y)=>({x,y})},Transforms:{eastNorthUpToFixedFrame:identity},Matrix4:{multiplyByPoint:(m,p)=>p,multiplyByPointAsVector:(m,p)=>p}};
window.ws3d={viewer};
window.vw={CoordZ:C3,Direction:class{},CameraPosition:class{},Map:class{setOption(value){this.options=value;}getLayerElement(){return{show(){}};}start(){document.getElementById('vmap').style.background='linear-gradient(#d9e8f0,#c8d8c9)';const label=document.createElement('div');label.textContent='합성 SDK FIXTURE · 실제 지도 아님';Object.assign(label.style,{position:'absolute',bottom:'15px',left:'15px',font:'12px sans-serif',background:'white',padding:'7px'});document.body.append(label);setTimeout(()=>window.vw.ws3dInitCallBack(),0);}}};
setInterval(()=>listeners.forEach(f=>f()),50);
