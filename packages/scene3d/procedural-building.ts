import * as THREE from 'three';
import type {Building,Feature,StateValue} from '../domain-schemas';
import {buildingFloors,floorElevation,floorLabel,floorPlan,interiorKinds} from '../domain-schemas/building-plan';

function mesh(group:THREE.Object3D,geometry:THREE.BufferGeometry,color:string,position:number[],options:THREE.MeshStandardMaterialParameters={}){
 const result=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color,roughness:.8,...options}));result.position.set(position[0],position[1],position[2]);result.castShadow=true;result.receiveShadow=true;group.add(result);return result;
}
const box=(g:THREE.Object3D,w:number,h:number,d:number,c:string,p:number[],o:THREE.MeshStandardMaterialParameters={})=>mesh(g,new THREE.BoxGeometry(w,h,d),c,p,o);
function polygon(points:number[][],height:number){const shape=new THREE.Shape();points.forEach(([x,z],i)=>i?shape.lineTo(x,-z):shape.moveTo(x,-z));shape.closePath();const geometry=new THREE.ExtrudeGeometry(shape,{depth:height,bevelEnabled:false});geometry.rotateX(-Math.PI/2);return geometry;}

export function proceduralBuilding(b:Building,{hiddenFloor=0,cutaway=false,selected=false,closed=false}:{hiddenFloor?:number;cutaway?:boolean;selected?:boolean;closed?:boolean}={}){
 const root=new THREE.Group();root.name=b.id;root.userData={buildingId:b.id,trainingOnly:true,accuracy:b.accuracy};
 const finish=b.wall_finish||'CONCRETE',roughness=finish==='GLASS'?.2:finish==='METAL'?.4:.9,metalness=finish==='METAL'?.5:0;
 for(const floor of buildingFloors(b)){
  if(hiddenFloor!==0&&floor>hiddenFloor)continue;
  const group=new THREE.Group();group.name=b.id+':floor:'+floor;group.position.y=floorElevation(floor,b.floor_height);root.add(group);
  const points=floorPlan(b,floor);
  const open=cutaway&&floor===hiddenFloor,wall=selected?'#c5ced1':b.color;
  mesh(group,polygon(points,b.floor_height-.18),wall,[0,.14,0],{roughness,metalness,transparent:open||finish==='GLASS',opacity:open?.13:finish==='GLASS'?.65:1,depthWrite:!open});
  mesh(group,polygon(points,.12),'#747f82',[0,open?0:b.floor_height-.12,0]);
  if(b.window_style!=='NONE'&&!open&&floor>0){
   const winding=points.reduce((total,p,i)=>total+p[0]*points[(i+1)%points.length][1]-points[(i+1)%points.length][0]*p[1],0)>0?1:-1;
   for(let i=0;i<points.length;i++){const [x,z]=points[i],next=points[(i+1)%points.length],dx=next[0]-x,dz=next[1]-z,length=Math.hypot(dx,dz);for(let along=2.7;along<length-1.5;along+=4.3){const win=box(group,2.8,1.7,.08,'#3c5d70',[x+dx*along/length+winding*dz/length*.06,b.floor_height*.57,z+dz*along/length-winding*dx/length*.06],{roughness:.25,metalness:.45});win.rotation.y=-Math.atan2(dz,dx);}}
  }
 }
 if(!hiddenFloor||hiddenFloor===b.floors&&!cutaway){
  const y=b.floors*b.floor_height;
  if(b.roof_style==='GABLE'){
   const shape=new THREE.Shape();shape.moveTo(-b.width/2,0);shape.lineTo(0,Math.min(4,b.width*.12));shape.lineTo(b.width/2,0);shape.closePath();
   const geometry=new THREE.ExtrudeGeometry(shape,{depth:b.depth+.8,bevelEnabled:false});mesh(root,geometry,'#65757b',[0,y,-b.depth/2-.4]);
  }else if(b.roof_style==='SHED'){
   const shape=new THREE.Shape();shape.moveTo(-b.width/2,0);shape.lineTo(-b.width/2,Math.min(3,b.width*.08));shape.lineTo(b.width/2,0);shape.closePath();
   mesh(root,new THREE.ExtrudeGeometry(shape,{depth:b.depth+.8,bevelEnabled:false}),'#65757b',[0,y,-b.depth/2-.4]);
  }else mesh(root,polygon(floorPlan(b,b.floors),.35),'#65757b',[0,y,0]);
 }
 if(hiddenFloor>=0)for(const [index,entrance] of b.entrances.entries()){
  const direction=entrance.toUpperCase(),side=direction==='SOUTH'?1:-1;
  if(direction==='EAST'||direction==='WEST')box(root,.2,2.7,3.2,closed?'#b54f3c':'#314a5d',[(direction==='EAST'?1:-1)*(b.width/2+.15),1.4,0]);
  else box(root,3.2,2.7,.2,closed?'#b54f3c':'#314a5d',[index>1?(index-1)*4:0,1.4,side*(b.depth/2+.15)]);
 }
 root.traverse(item=>{if(item instanceof THREE.Mesh)item.userData={...root.userData};});
 return root;
}

export function proceduralInterior(feature:Feature,b:Building,state:Record<string,StateValue>={}){
 if(!(feature.kind in interiorKinds))return null;
 const root=new THREE.Group();root.position.set(feature.x,floorElevation(feature.floor,b.floor_height),feature.z);root.rotation.y=THREE.MathUtils.degToRad(feature.rotation||0);
 const width=feature.width??4,depth=feature.depth??4,height=Math.min(feature.height??2.5,b.floor_height-.3),alert=state.closed||state.warning;
 const color=alert?'#dc694f':feature.kind==='EVAC_ROUTE'?'#62b694':feature.kind==='COMPARTMENT'?'#dfad63':feature.kind==='HAZMAT'?'#dca34d':'#7b9eae';
 if(['ROOM','COMPARTMENT','ELEVATOR'].includes(feature.kind)){
  box(root,width,.08,depth,color,[0,.06,0]);
  for(const x of [-width/2,width/2])box(root,.12,height,depth,color,[x,height/2,0],{transparent:true,opacity:.55});
  for(const z of [-depth/2,depth/2])box(root,width,height,.12,color,[0,height/2,z],{transparent:true,opacity:.55});
 }else if(feature.kind==='STAIR'){
  for(let i=0;i<12;i++){const h=(i+1)*height/12;box(root,width,h,depth/12,color,[0,h/2,-depth/2+(i+.5)*depth/12]);}
 }else if(feature.kind==='FIRE_EQUIPMENT'||feature.kind==='HAZMAT')mesh(root,new THREE.CylinderGeometry(Math.min(width,depth)*.35,Math.min(width,depth)*.35,height,12),feature.kind==='FIRE_EQUIPMENT'?'#bf544b':color,[0,height/2,0]);
 else box(root,width,feature.kind==='PASSAGE'?.25:.1,depth,color,[0,feature.kind==='PASSAGE'?.15:.08,0]);
 root.name=feature.id;root.userData={featureId:feature.id,trainingOnly:true};root.traverse(item=>{if(item instanceof THREE.Mesh)item.userData={featureId:feature.id,assetNode:`${feature.name} · ${feature.id} · ${floorLabel(feature.floor)} · 가상 도식${alert?' · 통제/위험 연출':''}`};});return root;
}

export function proceduralSiteResource(f:Feature,state:Record<string,StateValue>={}){
 if(!['ROAD','PARKING','HYDRANT','VEHICLE','PERIMETER','ASSEMBLY','HOSPITAL','ENTRANCE'].includes(f.kind))return null;
 const root=new THREE.Group();root.name=f.id;root.position.set(f.x,0,f.z);root.rotation.y=THREE.MathUtils.degToRad(f.rotation||0);const width=f.width??4,depth=f.depth??4;
 if(f.kind==='ROAD'||f.kind==='PARKING'){
  box(root,width,.12,depth,f.kind==='ROAD'?'#29333d':'#6c7b7d',[0,.08,0]);
  if(f.kind==='PARKING')for(let x=-width/2+3;x<width/2;x+=3)box(root,.08,.03,depth*.7,'#d4dacf',[x,.16,0]);
  if(state.closed)box(root,Math.min(width,6),.9,.35,'#e09a5e',[0,.5,0]);
 }else if(f.kind==='HYDRANT')mesh(root,new THREE.CylinderGeometry(.45,.6,1.6,8),state.water==='UNAVAILABLE'?'#615d60':'#d57d4d',[0,.8,0]);
 else if(f.kind==='VEHICLE'){
  box(root,width,1.8,depth,'#bc4a39',[0,1.4,0]);box(root,Math.min(1.6,width*.3),2,depth,'#e4e8e5',[width*.35,1.4,0]);
  for(const x of [-width*.3,width*.3])for(const z of [-depth/2,depth/2]){const wheel=mesh(root,new THREE.CylinderGeometry(.5,.5,.3,12),'#202a30',[x,.5,z]);wheel.rotation.x=Math.PI/2;}
 }else if(f.kind==='PERIMETER'){const radius=Math.min(2000,Math.max(0,Number(state.radius)||15));const ring=mesh(root,new THREE.RingGeometry(radius,radius+.24,64),'#d59561',[0,.15,0],{side:THREE.DoubleSide,transparent:true,opacity:.7});ring.rotation.x=-Math.PI/2;}
 else if(f.kind==='ENTRANCE')box(root,width,Math.min(f.height||2.7,4),.2,state.closed?'#b54f3c':'#4f9e88',[0,(f.height||2.7)/2,0]);
 else box(root,width,.15,depth,state.closed?'#b54f3c':f.kind==='ASSEMBLY'?'#4e8d77':'#7b94ad',[0,.1,0]);
 root.traverse(item=>{if(item instanceof THREE.Mesh)item.userData={featureId:f.id,assetNode:`${f.name} · ${f.id} · ${f.data_origin==='REFERENCE'?'출처 기반 참고시설':'가상 배치'}${state.closed?' · 통제':''}`};});return root;
}
