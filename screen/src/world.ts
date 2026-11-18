import * as T from 'three';
import {mergeGeometries} from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import type {Building,Entity,SceneState} from './types';

export const material=(color:string,roughness=.8,metalness=0)=>new T.MeshStandardMaterial({color,roughness,metalness});
export function mesh(parent:T.Object3D,geometry:T.BufferGeometry,mat:T.Material,x=0,y=0,z=0){const m=new T.Mesh(geometry,mat);m.position.set(x,y,z);m.castShadow=true;m.receiveShadow=true;parent.add(m);return m;}
export const box=(parent:T.Object3D,w:number,h:number,d:number,mat:T.Material,x=0,y=0,z=0)=>mesh(parent,new T.BoxGeometry(w,h,d),mat,x,y,z);
export function label(text:string,color='#364351',width=14){
 const canvas=document.createElement('canvas');canvas.width=512;canvas.height=96;const c=canvas.getContext('2d')!;
 c.fillStyle='#ffffffeb';c.beginPath();c.roundRect(3,3,506,90,16);c.fill();c.strokeStyle='#d3dae0';c.lineWidth=3;c.stroke();c.font='600 30px "Malgun Gothic", sans-serif';c.fillStyle=color;c.textAlign='center';c.textBaseline='middle';c.fillText(text.slice(0,32),256,48,480);
 const tex=new T.CanvasTexture(canvas);tex.colorSpace=T.SRGBColorSpace;const sprite=new T.Sprite(new T.SpriteMaterial({map:tex,depthTest:false,transparent:true}));sprite.scale.set(width,width*96/512,1);return sprite;
}
export function grain(base:string,kind:'asphalt'|'concrete'|'roof'){
 const canvas=document.createElement('canvas');canvas.width=256;canvas.height=256;const c=canvas.getContext('2d')!;c.fillStyle=base;c.fillRect(0,0,256,256);
 let seed=321;const rand=()=>{seed=(seed*16807)%2147483647;return seed/2147483647;};
 for(let i=0;i<18000;i++){const light=rand()>.5?255:0;c.fillStyle=`rgba(${light},${light},${light},${kind==='asphalt'?.10:.055})`;c.fillRect(rand()*256,rand()*256,rand()*2+1,rand()*2+1);}
 if(kind==='roof'){for(let x=0;x<256;x+=16){c.fillStyle='#ffffff22';c.fillRect(x,0,2,256);c.fillStyle='#00000022';c.fillRect(x+3,0,2,256);}}
 if(kind==='concrete'){for(let y=32;y<256;y+=64){c.strokeStyle='#777e7c22';c.beginPath();c.moveTo(0,y);c.lineTo(256,y);c.stroke();}}
 const texture=new T.CanvasTexture(canvas);texture.colorSpace=T.SRGBColorSpace;texture.wrapS=texture.wrapT=T.RepeatWrapping;texture.repeat.set(kind==='asphalt'?24:4,kind==='asphalt'?24:4);texture.anisotropy=4;return texture;
}
export function makeWorld(scene:SceneState){
 const group=new T.Group();group.name='site-world';
 const concrete=material('#b8b9b2');concrete.map=grain('#b8b9b2','concrete');
 const grass=material('#909c76'),asphalt=material('#7a8180');asphalt.map=grain('#747a79','asphalt');
 const ground=box(group,600,.3,600,grass,0,-.5,0);ground.castShadow=false;
 box(group,226,.25,205,concrete,0,-.23,0);
 box(group,450,.13,24,asphalt,0,-.04,66);box(group,450,.13,19,asphalt,0,-.04,-77);box(group,19,.13,330,asphalt,-94,-.04,0);box(group,19,.13,330,asphalt,95,-.04,0);
 const white=material('#f1eee1'),curb=material('#cbd0c8');
 for(const z of [52,80,-66,-88])box(group,220,.25,.3,curb,0,0,z);
 for(let x=-210;x<210;x+=12){box(group,5,.02,.24,white,x,.05,66);box(group,5,.02,.24,white,x,.05,-77);}
 for(let z=-145;z<150;z+=12){box(group,.24,.02,5,white,-94,.05,z);box(group,.24,.02,5,white,95,.05,z);}
 for(let x=43;x<84;x+=6){box(group,.12,.02,12,white,x,.03,34);}
 for(let x=-77;x<-36;x+=6)box(group,.12,.02,12,white,x,.03,-39);
 // Perimeter, street furniture and a restrained distant city context.
 const fence=material('#9ea9a7',.5,.4);
 for(let x=-78;x<85;x+=8){box(group,.15,2.7,.15,fence,x,1.3,-54);box(group,8,.06,.08,fence,x+4,2,-54);}
 const bark=material('#8c7e67'),leaves=material('#687e52');
 for(const [x,z] of [[-78,40],[-77,-55],[80,42],[79,-53],[-120,90],[123,40],[122,-20]]){mesh(group,new T.CylinderGeometry(.24,.4,4,7),bark,x,2,z);mesh(group,new T.IcosahedronGeometry(3,1),leaves,x,5,z);}
 for(let i=0;i<15;i++){const x=(i%5-2)*52,z=i<5?-140:i<10?145:((i%2)*210-105);if(i>=10&&Math.abs(x)<100)continue;const h=12+(i*7)%24;box(group,27,h,24,material(i%2?'#c1c8c8':'#cbd0cd'),x,h/2,z);}
 const height=Math.max(...scene.buildings.map(b=>b.floors*b.floor_height));
 const sidePositions:Record<string,[number,number,number]>={A:[0,.12,94],B:[-116,.12,0],C:[0,.12,-100],D:[116,.12,0]};
 for(const [side,pos]of Object.entries(sidePositions)){const marker=label(`${side} 방면`,side==='A'?'#d85d37':'#3e5364',15);marker.position.set(...pos);group.add(marker);}
 return {group,height};
}
export function makeBuilding(building:Building){
 const g=new T.Group();g.position.set(building.x,0,building.z);g.name=building.id;
 if(building.model_asset_id)g.userData.noBatch=true;
 const {width:w,depth:d,floors,floor_height:fh}=building,h=floors*fh;
 const wall=material(building.color);wall.map=grain(building.color,'concrete');
 box(g,w,h,d,wall,0,h/2,0);const trim=material('#e5e6df'),dark=material('#485a63',.32,.45);
 for(let floor=0;floor<=floors;floor++)box(g,w+.13,.18,d+.13,trim,0,floor*fh+.2,0);
 const rows=Math.max(1,Math.floor(w/6)),cols=Math.max(1,Math.floor(d/6));
 const windowGeometry=new T.BoxGeometry(2.7,1.65,.08),matrices:T.Matrix4[]=[];
 for(let floor=0;floor<floors;floor++){
  for(let i=0;i<rows;i++)for(const side of [1,-1]){if(floor===0&&building.style==='warehouse')continue;matrices.push(new T.Matrix4().makeTranslation((i+.5)*w/rows-w/2,floor*fh+fh*.6,side*(d/2+.055)));}
  for(let i=0;i<cols;i++)for(const side of [1,-1]){const matrix=new T.Matrix4().makeRotationY(Math.PI/2);matrix.setPosition(side*(w/2+.055),floor*fh+fh*.6,(i+.5)*d/cols-d/2);matrices.push(matrix);}
 }
 const windows=new T.InstancedMesh(windowGeometry,dark,matrices.length);windows.name='windows';matrices.forEach((m,i)=>windows.setMatrixAt(i,m));g.add(windows);
 const sills=material('#a5b0b0');for(let i=0;i<rows;i++){if(i%2===0)box(g,.22,h,.26,trim,(i+.5)*w/rows-w/2,h/2,d/2+.1);}
 if(building.style==='warehouse'){
  const door=material('#708485',.5,.25);for(let i=0;i<Math.max(2,Math.floor(w/13));i++){const x=(i+.5)*w/Math.max(2,Math.floor(w/13))-w/2;box(g,6,3.5,.18,door,x,1.75,d/2+.13);for(let y=.5;y<3.4;y+=.42)box(g,5.9,.045,.06,sills,x,y,d/2+.25);box(g,7,.35,2.3,material('#9da49e'),x,.18,d/2+1.1);}}
 const roof=material('#abb5b3',.55,.35);roof.map=grain('#acb6b4','roof');const roofMesh=box(g,w+1,.35,d+1,roof,0,h+.12,0);roofMesh.name='roof';
 for(let i=0;i<Math.min(4,rows);i++){box(g,3.8,1.35,2.5,material('#a4aeac',.5,.4),i*7-w/3,h+.95,-d*.18);mesh(g,new T.CylinderGeometry(.55,.7,1.8,10),material('#808e8e',.5,.4),i*7-w/3,h+1.7,-d*.18);}
 const sign=label(building.name,'#3e565a',Math.min(w*.4,12));sign.position.set(0,h+2.8,d/2+.4);g.add(sign);
 return g;
}
/** Batch only static geometry. Articulated limbs, ladders and reviewed models
 * keep their own transforms/visibility. This runs before their first render. */
export function batchStatic(root:T.Object3D){
 root.updateWorldMatrix(true,true);const inverse=root.matrixWorld.clone().invert();
 const groups=new Map<string,T.Mesh[]>();
 root.traverse(object=>{
  const m=object as T.Mesh;if(!m.isMesh||(m as T.InstancedMesh).isInstancedMesh||Array.isArray(m.material)||!(m.material instanceof T.MeshStandardMaterial))return;
  let parent:T.Object3D|null=m;
  while(parent&&parent!==root){if(parent.userData.noBatch||['roof','windows','wave','ladder','beacon'].includes(parent.name))return;parent=parent.parent;}
  const mat=m.material,key=[mat.color.getHexString(),mat.roughness,mat.metalness,mat.transparent,mat.opacity,mat.side,mat.emissive.getHexString(),mat.emissiveIntensity,mat.map?.uuid||'',Object.keys(m.geometry.attributes).sort().join(',')].join('|');
  const list=groups.get(key)||[];list.push(m);groups.set(key,list);
 });
 for(const meshes of groups.values()){
  if(meshes.length<2)continue;
  const parts=meshes.map(m=>{const part=m.geometry.index?m.geometry.toNonIndexed():m.geometry.clone();part.applyMatrix4(new T.Matrix4().multiplyMatrices(inverse,m.matrixWorld));return part;});
  const merged=mergeGeometries(parts,false);parts.forEach(g=>g.dispose());if(!merged)continue;
  const combined=new T.Mesh(merged,meshes[0].material);combined.castShadow=meshes.some(m=>m.castShadow);combined.receiveShadow=true;
  for(const m of meshes){m.removeFromParent();m.geometry.dispose();}root.add(combined);
 }
}
function human(group:T.Group,crew=false){
 const clothes=material(crew?'#4e585b':'#c77a55'),stripe=material('#e7da83'),skin=material('#c99f82');
 box(group,.5,.65,.27,clothes,0,1.05,0);for(const x of[-.15,.15])box(group,.17,.6,.2,clothes,x,.43,0);
 mesh(group,new T.SphereGeometry(.19,10,8),skin,0,1.6,0);
 if(crew){mesh(group,new T.SphereGeometry(.23,10,6),stripe,0,1.7,0);box(group,.51,.07,.29,stripe,0,1.03,0);}
 const arm=new T.Group();arm.position.set(-.3,1.2,0);box(arm,.13,.63,.15,clothes,0,-.18,0);arm.rotation.z=crew?-.2:2.3;group.add(arm);arm.name='wave';
 box(group,.13,.6,.15,clothes,.32,1.03,0);return group;
}
export function makeEntity(entity:Entity){
 const group=new T.Group();group.name=entity.id;
 if(entity.kind==='fire')return group;
 if(entity.kind==='victim'||entity.kind==='crew'){human(group,entity.kind==='crew');if(entity.kind==='crew'){const mate=new T.Group();human(mate,true);mate.position.set(1.2,0,.3);group.add(mate);}return group;}
 if(entity.kind==='hydrant'){
  const red=material('#ce4338',.4,.4);mesh(group,new T.CylinderGeometry(.28,.35,1,12),red,0,.6,0);mesh(group,new T.SphereGeometry(.3,10,6),red,0,1.1,0);const valve=mesh(group,new T.CylinderGeometry(.16,.16,.9,10),red,0,.75,0);valve.rotation.z=Math.PI/2;
 }else if(entity.kind==='cordon'){
  for(const x of[-8,8]){mesh(group,new T.ConeGeometry(.3,.7,8),material('#e76a30'),x,.35,0);box(group,.07,1.2,.07,material('#eceddf'),x,.6,0);}box(group,16,.2,.035,material('#e0b834'),0,1,0);
 }else{
  const command=entity.kind==='command',ambulance=entity.kind==='ambulance',length=command?5:ambulance?5.5:8.5;
  const red=material(ambulance||command?'#e4e9e4':'#cb3f35',.34,.25),rubber=material('#33383b'),glass=material('#8daeb7',.18,.3),metal=material('#b6c1bf',.3,.7),stripe=material('#f2eedc');
  box(group,length,1.6,2.5,red,0,1.5,0);box(group,2.2,1.35,2.45,red,length/2-1,2.1,0);box(group,.08,.8,2.15,glass,length/2+.12,2.4,0);
  for(const z of[-1.27,1.27]){box(group,1.7,.8,.035,glass,length/2-1,2.4,z);box(group,length-.2,.24,.04,stripe,0,1.3,z);for(let i=0;i<3;i++)box(group,1.35,.92,.045,metal,-length/2+.9+i*1.65,1.85,z);}
  for(const x of[-length*.31,length*.31])for(const z of[-1.3,1.3]){const wheel=mesh(group,new T.CylinderGeometry(.55,.55,.3,14),rubber,x,.6,z);wheel.rotation.x=Math.PI/2;const hub=mesh(group,new T.CylinderGeometry(.3,.3,.32,10),metal,x,.6,z);hub.rotation.x=Math.PI/2;}
  box(group,.07,.35,2.1,metal,length/2+.22,.95,0);
  for(const z of[-.8,.8])box(group,.1,.26,.4,material('#fff3cf'),length/2+.21,1.52,z);
  const beacon=box(group,.9,.18,1.8,new T.MeshStandardMaterial({color:'#b23d33',emissive:'#ef4b38',emissiveIntensity:1}),length/2-1,2.87,0);beacon.name='beacon';
  if(entity.kind==='ladder'){
   const ladder=new T.Group();ladder.position.set(-1,2.7,0);ladder.rotation.z=.45;for(const z of[-.4,.4])box(ladder,12,.15,.12,metal,4,0,z);for(let x=-1;x<10;x+=.6)box(ladder,.08,.1,.9,metal,x,0,0);ladder.name='ladder';group.add(ladder);
  }
  if(command){
   const tent=mesh(group,new T.ConeGeometry(3,1.4,4),material('#f1eee1'),0,3.8,5.5);tent.rotation.y=Math.PI/4;
   for(const x of[-2,2])for(const z of[3.5,7.5])box(group,.07,3.1,.07,metal,x,1.55,z);
   box(group,2,.9,.8,material('#98a5a3'),0,.5,5);const sign=label('현장 지휘대','#d85d37',9);sign.position.set(0,4.8,5);group.add(sign);
  }
 }
 if(entity.kind==='hydrant'){const name=label(entity.label,'#367a78',7);name.position.y=2.5;group.add(name);}
 return group;
}
export function disposeTree(root:T.Object3D){
 const geometries=new Set<T.BufferGeometry>(),materials=new Set<T.Material>(),textures=new Set<T.Texture>();
 root.traverse(object=>{const m=object as T.Mesh;if(m.geometry)geometries.add(m.geometry);if(m.material)for(const mat of Array.isArray(m.material)?m.material:[m.material]){materials.add(mat);for(const value of Object.values(mat))if(value instanceof T.Texture)textures.add(value);if(mat instanceof T.ShaderMaterial)for(const uniform of Object.values(mat.uniforms))if(uniform.value instanceof T.Texture)textures.add(uniform.value);}});
 geometries.forEach(v=>v.dispose());materials.forEach(v=>v.dispose());textures.forEach(v=>{if(typeof ImageBitmap!=='undefined'&&v.image instanceof ImageBitmap)v.image.close();v.dispose();});
}
