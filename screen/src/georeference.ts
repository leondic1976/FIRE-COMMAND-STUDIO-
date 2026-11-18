import type {SceneState} from './types';
import {entityPosition} from './types';
import type {View} from './Scene';

export type Vector3=[number,number,number];
export type MapCamera={view:number[];projection:number[];root:number[]};
export type CameraBridge={current:MapCamera|null};

/** Local right/up/front coordinates -> east/north/up, in metres. */
export function toENU([x,y,z]:Vector3,bearing:number):Vector3{
 const angle=(180-bearing)*Math.PI/180,c=Math.cos(angle),s=Math.sin(angle);
 return [x*c+z*s,x*s-z*c,y];
}
/** Column-major matrix with the same basis as toENU, without Earth-size translations. */
export function enuBasis(bearing:number):number[]{
 const a=(180-bearing)*Math.PI/180,c=Math.cos(a),s=Math.sin(a);
 return [c,s,0,0,0,0,1,0,s,-c,0,0,0,0,0,1];
}
export function cameraPose(state:SceneState,view:View):{position:Vector3;target:Vector3}{
 const b=state.buildings[0],height=Math.max(10,b.floors*b.floor_height);
 const offsets:Record<View,Vector3>={A:[42,Math.max(17,height*.85),112],B:[-88,Math.max(12,height*.7),-23],C:[-28,Math.max(12,height*.7),-88],D:[88,Math.max(12,height*.7),25],overview:[108,100,120],commander:[5,2.2,74]};
 let position:Vector3=[b.x+offsets[view][0],offsets[view][1],b.z+offsets[view][2]];
 const command=state.entities.find(e=>e.kind==='command'&&e.visible);
 if(view==='commander'&&command){const p=entityPosition(command,state.buildings);position=[p[0],p[1]+2.2,p[2]];}
 return {position,target:[b.x,height*.45,b.z]};
}
export function validCamera(value:unknown):value is MapCamera{
 if(!value||typeof value!=='object')return false;
 return ['view','projection','root'].every(k=>{const a=(value as Record<string,unknown>)[k];return Array.isArray(a)&&a.length===16&&a.every(n=>typeof n==='number'&&Number.isFinite(n)&&Math.abs(n)<1e9);});
}

/** The SDK frame receives viewport coordinates only, never scene entities or messages. */
export function mapViewport(state:SceneState,view:View){
 const pose=cameraPose(state,view);
 return {latitude:state.site.latitude,longitude:state.site.longitude,
  position:toENU(pose.position,state.site.front_bearing),target:toENU(pose.target,state.site.front_bearing)};
}
