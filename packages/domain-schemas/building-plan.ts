import type {Building,Feature,StateValue,Subject} from './index';
export const interiorKinds={ROOM:'실',CORRIDOR:'복도',STAIR:'계단',ELEVATOR:'승강기',COMPARTMENT:'방화구획',EVAC_ROUTE:'피난통로',FIRE_EQUIPMENT:'소방시설',HAZMAT:'위험물 저장구역',PASSAGE:'연결통로'} as const;
export const buildingPresets:Record<string,Partial<Building>>={
 '공장':{floors:3,width:36,depth:24,floor_height:4.5,roof_style:'SHED',wall_finish:'METAL'},
 '창고':{floors:2,width:42,depth:28,floor_height:5,roof_style:'GABLE',wall_finish:'METAL'},
 '지하상가':{floors:1,basement_floors:2,width:40,depth:24,floor_height:3.5,roof_style:'FLAT',wall_finish:'CONCRETE'},
 '고층아파트':{floors:12,width:28,depth:18,floor_height:3,roof_style:'FLAT',wall_finish:'CONCRETE'},
 '다중이용시설':{floors:4,width:36,depth:28,floor_height:4,roof_style:'FLAT',wall_finish:'GLASS'},
 '의료시설':{floors:6,width:34,depth:24,floor_height:3.6,roof_style:'FLAT',wall_finish:'CONCRETE'},
 '학교':{floors:4,width:42,depth:18,floor_height:3.5,roof_style:'FLAT',wall_finish:'BRICK'},
 '위험물 시설':{floors:1,width:24,depth:20,floor_height:5,roof_style:'GABLE',wall_finish:'METAL'},
 '지하차도':{floors:1,basement_floors:1,width:60,depth:14,floor_height:4.5,roof_style:'FLAT',window_style:'NONE',wall_finish:'CONCRETE'},
 '복합건물':{floors:8,basement_floors:2,width:32,depth:26,floor_height:3.6,roof_style:'FLAT',wall_finish:'GLASS'},
};
export const buildingFloors=(b:Building)=>[...Array.from({length:b.basement_floors||0},(_,i)=>i-(b.basement_floors||0)),...Array.from({length:b.floors},(_,i)=>i+1)];
export const floorLabel=(floor:number)=>floor<0?`지하 ${-floor}층`:floor===0?'대지·건물 전체':`${floor}층`;
export const floorElevation=(floor:number,height:number)=>(floor>0?floor-1:floor)*height;
export function floorPlan(b:Building,floor:number){return b.floor_outlines?.find(item=>item.floor===floor)?.footprint|| (b.footprint.length>=3?b.footprint:[[-b.width/2,-b.depth/2],[b.width/2,-b.depth/2],[b.width/2,b.depth/2],[-b.width/2,b.depth/2]]);}
export function sceneObjectBudget(buildings:Building[],features:Feature[],state:Record<string,Record<string,StateValue>>={}){
 let total=0;
 for(const b of buildings){total+=(b.entrances||[]).length+8;if(total>15000)return total;
  for(const floor of buildingFloors(b)){const points=floorPlan(b,floor);total+=6+points.length;
   if(floor>0&&b.window_style!=='NONE')for(let i=0;i<points.length;i++){const next=points[(i+1)%points.length];total+=Math.ceil(Math.hypot(next[0]-points[i][0],next[1]-points[i][1])/4.3);}
   if(total>15000)return total;
  }
 }
 for(const feature of features){const value=state[feature.id]||feature.state,smoke=Math.min(4,Math.max(0,Number(value.smoke)||0));total+=4+(feature.kind in interiorKinds?16:0)+(feature.kind==='PARKING'?Math.ceil((feature.width??4)/3):0)+Math.ceil(smoke*4)+(Number(value.fire)>0?2:0)+(Number(value.water)>0?2:0);if(total>15000)return total;}
 return total;
}
/** Conservative planar radius for rotated footprints, local interiors and resources. */
export function siteRadius(subject:Pick<Subject,'buildings'|'features'>,state:Record<string,Record<string,StateValue>>={}){
 let radius=0;const buildings=new Map(subject.buildings.map(b=>[b.id,b]));
 for(const b of subject.buildings){const outlines=[b.footprint,...(b.floor_outlines||[]).map(item=>item.footprint)],size=Math.max(Math.hypot(b.width,b.depth)/2,...outlines.flatMap(points=>points.map(([x,z])=>Math.hypot(x,z))));radius=Math.max(radius,Math.hypot(b.x,b.z)+size);}
 for(const f of subject.features){const b=f.building_id?buildings.get(f.building_id):null,local=Math.hypot(f.x,f.z)+(f.kind==='PERIMETER'?Math.min(2000,Math.max(0,Number((state[f.id]||f.state).radius)||0)):Math.hypot(f.width??4,f.depth??4)/2);radius=Math.max(radius,(b?Math.hypot(b.x,b.z):0)+local);}
 return radius;
}
