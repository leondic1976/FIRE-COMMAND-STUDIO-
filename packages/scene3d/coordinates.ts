/** Local X=east, Z=south, metres. Positive rotation matches Three.js Y rotation. */
export function rotateLocal(x:number,z:number,degrees:number):[number,number]{const a=degrees*Math.PI/180;return [x*Math.cos(a)+z*Math.sin(a),-x*Math.sin(a)+z*Math.cos(a)];}
/** Small-area approximate projection, not a surveying or engineering guarantee. */
export function localToWGS84(latitude:number,longitude:number,x:number,z:number):[number,number]{if(![latitude,longitude,x,z].every(Number.isFinite)||Math.abs(latitude)>85||Math.abs(longitude)>180)throw new Error('지도 좌표 범위를 확인하세요.');const lat=latitude-z/111320;const lng=longitude+x/(111320*Math.cos(latitude*Math.PI/180));return [lat,((lng+180)%360+360)%360-180];}
