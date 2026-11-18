import * as T from 'three';
import type {Entity,Weather} from './types';

const smokeVertex=`attribute float lifeSeed; uniform float clock; uniform float intensity; uniform vec2 wind; uniform float pointScale; varying float alpha; varying float shade;
void main(){float life=fract(clock*.045+lifeSeed);vec3 p=position; p.y+=life*(12.+intensity*5.);p.xz+=wind*life*life*4.;p.x+=sin(lifeSeed*90.+clock*.2)*life*2.;p.z+=cos(lifeSeed*70.+clock*.16)*life*2.;vec4 mv=modelViewMatrix*vec4(p,1.);gl_Position=projectionMatrix*mv;gl_PointSize=clamp((3.+life*9.)*pointScale/max(1.,-mv.z),1.,210.);alpha=sin(life*3.14159)*(.24+intensity*.065);shade=.16+life*.18;}`;
const smokeFragment=`precision highp float;varying float alpha;varying float shade;uniform sampler2D puff;void main(){float a=texture2D(puff,gl_PointCoord).a*alpha;if(a<.015)discard;gl_FragColor=vec4(vec3(shade*.94,shade*.97,shade),a);}`;
const flameVertex=`varying vec2 uv2;void main(){uv2=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`;
const flameFragment=`precision highp float;varying vec2 uv2;uniform float clock;uniform float strength;
float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}float noise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(hash(i),hash(i+vec2(1.,0.)),f.x),mix(hash(i+vec2(0.,1.)),hash(i+vec2(1.,1.)),f.x),f.y);}
void main(){vec2 q=uv2;float n=noise(vec2(q.x*7.,q.y*5.-clock*2.4));n+=noise(vec2(q.x*15.,q.y*12.-clock*4.))*.4;float x=abs(q.x-.5+sin(q.y*8.-clock*4.)*.055);float shape=(.44-x)-q.y*(.26+n*.14);float a=smoothstep(-.06,.12,shape)*(1.-smoothstep(.65,1.,q.y))*strength;vec3 col=mix(vec3(1.,.85,.33),vec3(.92,.20,.025),q.y+n*.22);gl_FragColor=vec4(col,a);}`;

function smokeTexture(){const c=document.createElement('canvas');c.width=c.height=128;const g=c.getContext('2d')!;let seed=341;const r=()=>{seed=(seed*16807)%2147483647;return seed/2147483647;};for(let i=0;i<36;i++){const x=36+r()*56,y=36+r()*56,rad=16+r()*27;const gradient=g.createRadialGradient(x,y,0,x,y,rad);gradient.addColorStop(0,'rgba(255,255,255,.20)');gradient.addColorStop(.6,'rgba(255,255,255,.13)');gradient.addColorStop(1,'rgba(255,255,255,0)');g.fillStyle=gradient;g.fillRect(0,0,128,128);}return new T.CanvasTexture(c);}

export class FireEffect{
 group=new T.Group();smoke:T.Points;flames:T.Mesh[]=[];light:T.PointLight;
 private inverse=new T.Quaternion();
 constructor(low:boolean){
  const count=low?28:62,positions=new Float32Array(count*3),seeds=new Float32Array(count);
  for(let i=0;i<count;i++){positions[i*3]=Math.sin(i*3.2)*1.3;positions[i*3+1]=Math.cos(i)*.2;positions[i*3+2]=Math.cos(i*4.3)*1.2;seeds[i]=i/count;}
  const geo=new T.BufferGeometry();geo.setAttribute('position',new T.BufferAttribute(positions,3));geo.setAttribute('lifeSeed',new T.BufferAttribute(seeds,1));
  const mat=new T.ShaderMaterial({uniforms:{clock:{value:0},intensity:{value:1},wind:{value:new T.Vector2()},pointScale:{value:600},puff:{value:smokeTexture()}},vertexShader:smokeVertex,fragmentShader:smokeFragment,transparent:true,depthWrite:false});
  this.smoke=new T.Points(geo,mat);this.smoke.frustumCulled=false;this.group.add(this.smoke);
  for(let i=0;i<4;i++){const flame=new T.Mesh(new T.PlaneGeometry(3.5,6),new T.ShaderMaterial({uniforms:{clock:{value:0},strength:{value:.8}},vertexShader:flameVertex,fragmentShader:flameFragment,transparent:true,depthWrite:false,side:T.DoubleSide,blending:T.AdditiveBlending}));flame.position.set(Math.sin(i*2)*.8,2,Math.cos(i*2)*.6);this.flames.push(flame);this.group.add(flame);}
  this.light=new T.PointLight('#ff722e',30,22,1.8);this.light.position.y=1;this.group.add(this.light);
 }
 update(entity:Entity,t:number,camera:T.Camera,weather:Weather,height:number){
  this.smoke.visible=entity.smoke>0;
  const mat=this.smoke.material as T.ShaderMaterial;mat.uniforms.clock.value=t;mat.uniforms.intensity.value=entity.smoke;mat.uniforms.pointScale.value=height*.82;
  const angle=weather.wind_degrees*Math.PI/180;mat.uniforms.wind.value.set(Math.sin(angle)*weather.wind_speed,Math.cos(angle)*weather.wind_speed);
  this.group.getWorldQuaternion(this.inverse).invert();
  this.flames.forEach((flame,i)=>{flame.visible=entity.fire>0;flame.quaternion.copy(this.inverse).multiply(camera.quaternion);flame.scale.setScalar(.55+entity.fire*.3);const material=flame.material as T.ShaderMaterial;material.uniforms.clock.value=t+i*1.2;material.uniforms.strength.value=.7+entity.fire*.09;});
  this.light.intensity=entity.fire*(8+Math.sin(t*17)*1.5);
 }
}

export class RainEffect{
 group:T.LineSegments;private positions:Float32Array;private count:number;
 constructor(low:boolean){this.count=low?120:280;this.positions=new Float32Array(this.count*6);const geometry=new T.BufferGeometry();geometry.setAttribute('position',new T.BufferAttribute(this.positions,3));this.group=new T.LineSegments(geometry,new T.LineBasicMaterial({color:'#c3d7e2',transparent:true,opacity:.5,depthWrite:false}));this.group.frustumCulled=false;}
 update(t:number,strength:number){this.group.visible=strength>0;if(!strength)return;for(let i=0;i<this.count;i++){const n=i*6,x=Math.sin(i*19.31)*100,z=Math.cos(i*12.77)*90,y=45-((t*18+i*.73)%45);this.positions[n]=x;this.positions[n+1]=y;this.positions[n+2]=z;this.positions[n+3]=x-.2;this.positions[n+4]=y-1.8;this.positions[n+5]=z+.2;}(this.group.geometry.attributes.position as T.BufferAttribute).needsUpdate=true;(this.group.material as T.LineBasicMaterial).opacity=.15+strength*.55;}
}

export class WaterEffect{
 group=new T.Group();points:T.Points;positions:Float32Array;from=new T.Vector3();to=new T.Vector3();
 constructor(){this.positions=new Float32Array(100*3);const geo=new T.BufferGeometry();geo.setAttribute('position',new T.BufferAttribute(this.positions,3));this.points=new T.Points(geo,new T.PointsMaterial({color:'#e8f6ff',size:.24,transparent:true,opacity:.72,depthWrite:false}));this.points.frustumCulled=false;this.group.add(this.points);}
 update(t:number,from:T.Vector3,to:T.Vector3){this.from.copy(from);this.to.copy(to);for(let i=0;i<100;i++){const f=(t*.8+i/100)%1;this.positions[i*3]=T.MathUtils.lerp(from.x,to.x,f)+Math.sin(i*10+t)*f*.45;this.positions[i*3+1]=T.MathUtils.lerp(from.y+2,to.y,f)+Math.sin(f*Math.PI)*6;this.positions[i*3+2]=T.MathUtils.lerp(from.z,to.z,f)+Math.cos(i*10+t)*f*.45;}(this.points.geometry.attributes.position as T.BufferAttribute).needsUpdate=true;}
}
