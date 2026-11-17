import hashlib
import json
import os
from pathlib import Path
import pytest
from apps.api.domain import AssetBinding,AssetManifest,MediaCue,validate_exercise
from apps.api.seeds import demo_exercise
from apps.api.asset_validation import AssetValidationError
from apps.api.media_validation import MediaProcessor,MediaSettings,MediaUnavailable
from apps.api.offline_process import run_bounded


def test_media_processing_defaults_closed_and_cue_ranges_validate():
    processor=MediaProcessor();assert not processor.status()['configured']
    with pytest.raises(MediaUnavailable):processor.normalize(b'\x1a\x45\xdf\xa3SYNTHETIC_NOT_A_VIDEO')
    with pytest.raises(AssetValidationError):processor.normalize(b'<!DOCTYPE UNSAFE>')
    with pytest.raises(ValueError):MediaCue(binding_id='binding-'+'a'*32,feature_id='B01-F03-Z01',clip_start_seconds=4,clip_end_seconds=3)


@pytest.mark.parametrize('mutator',[
    lambda info:info['format'].update(duration='nan'),
    lambda info:info['format'].update(duration=181),
    lambda info:info['streams'][0].update(avg_frame_rate='0/0'),
    lambda info:info['streams'][0].update(width=5000),
    lambda info:info['streams'].append({'codec_type':'attachment'}),
])
def test_invalid_video_metadata_is_rejected(mutator):
    info={'format':{'duration':3},'streams':[{'codec_type':'video','codec_name':'vp8','width':320,'height':180,'avg_frame_rate':'20/1'}]}
    mutator(info)
    with pytest.raises(AssetValidationError):MediaProcessor._info(json.dumps(info))


def test_media_tool_manifest_is_checked_before_process(tmp_path):
    path=tmp_path/'bundle.json';path.write_text('{}')
    processor=MediaProcessor(MediaSettings(approved=True,approval_reference='SYNTHETIC QA ONLY',host_isolation_confirmed=True,manifest_path=str(path),manifest_sha256='1'*64))
    with pytest.raises(MediaUnavailable,match='무결성'):processor.normalize(b'\x1a\x45\xdf\xa3SYNTHETIC')


def test_event_media_references_rights_anchors_and_clip_bounds_gate_publication():
    exercise=demo_exercise();cue=MediaCue(binding_id='binding-'+'a'*32,feature_id='B01-F02-Z01',clip_end_seconds=3)
    exercise.events[0].media_cues=[cue]
    assert any(issue['gate']=='G5' and '영상 연결' in issue['message'] for issue in validate_exercise(exercise,readiness=False))
    binding=AssetBinding(id=cue.binding_id,asset_id='asset-'+'b'*32,sha256='c'*64,kind='VIDEO',mime='video/webm',label='합성 영상',source=exercise.subject.source.model_copy(update={'reviewer':'synthetic-reviewer'}),
        manifest=AssetManifest(duration_seconds=3,width=320,height=180,frame_rate=20,video_codec='vp8'),reviewed_at='2026-11-17T02:00:00Z',building_id='B01',purpose='VIDEO',visibility='PUBLIC')
    exercise.subject.asset_bindings=[binding]
    assert not any(issue['gate']=='G5' for issue in validate_exercise(exercise,readiness=False))
    binding.visibility='STAFF'
    assert any('전용 영상' in issue['message'] for issue in validate_exercise(exercise,readiness=False))
    binding.visibility='PUBLIC';cue.clip_end_seconds=4
    assert any('클립 범위' in issue['message'] for issue in validate_exercise(exercise,readiness=False))
    cue.clip_end_seconds=3;cue.feature_id='B02'
    assert any('객체의 건물' in issue['message'] for issue in validate_exercise(exercise,readiness=False))


@pytest.mark.skipif(os.name!='nt' or os.getenv('RUN_MEDIA_TOOL_TESTS')!='1',reason='Explicit fixed native FFmpeg QA; synthetic video only')
def test_actual_fixed_tool_normalizes_synthetic_video_and_removes_private_metadata(tmp_path):
    manifest=Path('runtime/tools/ffmpeg-9.0.2/bundle.json').resolve();assert manifest.is_file()
    processor=MediaProcessor(MediaSettings(approved=True,approval_reference='SYNTHETIC TOOL QA ONLY, NOT INSTITUTION APPROVAL',host_isolation_confirmed=True,manifest_path=str(manifest),manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest()))
    ffmpeg,ffprobe=processor._tools();source=tmp_path/'synthetic.mp4'
    run_bounded([str(ffmpeg),'-hide_banner','-loglevel','error','-f','lavfi','-i','testsrc2=size=320x180:rate=10','-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','3','-c:v','libx264','-threads','1','-pix_fmt','yuv420p','-c:a','aac','-metadata','artist=PRIVATE_SYNTHETIC_VIDEO_METADATA','-metadata:s:v:0','handler_name=PRIVATE_SYNTHETIC_VIDEO_METADATA','-metadata','copyright=Generated QA video; no real institution.','-n',str(source)],tmp_path,seconds=20,output=source)
    content,info=processor.normalize(source.read_bytes())
    assert content.startswith(b'\x1a\x45\xdf\xa3') and info.video_codec=='vp8'
    assert 2.9<info.duration_seconds<3.1 and info.frame_rate==20 and info.has_audio
    assert info.width==320 and info.height==180 and 'Generated QA video' in info.copyright_notice
    assert b'PRIVATE_SYNTHETIC_VIDEO_METADATA' not in content
    artifact=Path('artifacts/media');artifact.mkdir(exist_ok=True)
    (artifact/'synthetic-normalized.webm').write_bytes(content)
    (artifact/'synthetic-manifest.json').write_text(json.dumps(info.model_dump(mode='json'),indent=2),encoding='utf-8')
