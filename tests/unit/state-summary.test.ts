import {describe,it,expect} from 'vitest';
import type {Subject} from '../../packages/domain-schemas';
import source from '../../data/synthetic/factory.json';
import {sceneStateSummary} from '../../packages/scene3d/state-summary';
describe('사건 상태의 화면 정보 보존',()=>{
 const subject=structuredClone(source.subject) as unknown as Subject;
 subject.features.push({id:'ENV-PRIVATE',name:'합성 환경 주석',kind:'ZONE',building_id:null,floor:0,x:0,z:0,state:{rain:0,wind:0,power:true}});
 it('연출 강우/바람·정전·자원 상태를2D/3D 공통 문장에 보존한다',()=>{const rows=sceneStateSummary(subject,{'ENV-PRIVATE':{rain:2,wind:7,power:false,status:'WORKING'}});expect(rows).toHaveLength(1);for(const text of ['강우 연출 2단계','바람 강도 7 (연출)','정전 (연출)','작업 중'])expect(rows[0].details).toContain(text);});
 it('제공받은 권한 투영값이 초기 객체의 다른 상태보다 우선한다',()=>{const hidden=structuredClone(subject);hidden.features.at(-1)!.state={rain:2,wind:7,power:false};expect(sceneStateSummary(hidden,{'ENV-PRIVATE':{rain:0,wind:0,power:true}})).toEqual([]);});
});
