import argparse
import json
import re
from pathlib import Path

from flask import Flask, render_template, make_response, request, abort

app = Flask('visualize')

audio_dir = Path('debug-croatian/wav')
json_dir = Path('debug-croatian/output')


@app.route('/')
def index():
    files = [x.stem for x in json_dir.glob('*.json')]

    return render_template('index.html', files=files)


@app.route('/visualize/<utt>')
def visualize(utt):
    audio_file = audio_dir / (utt + '.wav')
    json_file = json_dir / (utt + '.json')

    if not audio_file.exists() or not json_file.exists():
        abort(404)

    with open(json_file) as f:
        annotations = json.load(f)

    stats = {'ref_only_seg': 0, 'ref_only_words': 0,
             'reco_only_seg': 0, 'reco_only_words': 0,
             'ok_match_seg': 0, 'ok_match_words': 0}
    corr = 0
    num = 0
    for seg in annotations:
        if seg['match_error'] == 'only in reference':
            stats['ref_only_seg'] += 1
            stats['ref_only_words'] += len(seg['text'].split())
        elif seg['match_error'] == 'only in reco':
            stats['reco_only_seg'] += 1
            stats['reco_only_words'] += len(seg['reco'].split())
        else:
            stats['ok_match_seg'] += 1
            stats['ok_match_words'] += len(seg['norm'].split())

        if 'errors' in seg:
            corr += seg['errors']['corr']
            num += seg['errors']['num']

    stats['overall_wer'] = round(100 * (num - corr) / num, 2)

    annot_filt = annotations
    if 'noref' in request.args:
        annot_filt = list(filter(lambda x: x['match_error'] != 'only in reference', annotations))

    return render_template('visualize.html', utt=utt, annotations=annot_filt, stats=stats)


@app.route('/audio/<utt>')
def get_audio(utt):
    audio_file = audio_dir / (utt + '.wav')

    if not audio_file.exists():
        abort(404)

    headers = []
    if 'Range' in request.headers:
        audio_size = audio_file.stat().st_size
        end = audio_size - 1
        status = 206
        headers.append(('Accept-Ranges', 'bytes'))
        ranges = re.findall(r'\d+', request.headers['Range'])
        begin = int(ranges[0])
        if len(ranges) > 1:
            end = int(ranges[1])
        headers.append(('Content-Range', f'bytes {begin}-{end}/{audio_size}'))
        with open(audio_file, 'rb') as f:
            f.seek(begin)
            buf = f.read(end - begin + 1)
    else:
        status = 200
        with open(audio_file, 'rb') as f:
            buf = f.read()

    response = make_response(buf)
    response.status = status
    response.headers['Content-Type'] = 'audio/x-wav'
    response.headers['Content-Disposition'] = 'inline; filename=audio.wav'
    for k, v in headers:
        response.headers[k] = v
    return response


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('wav_dir', type=Path)
    parser.add_argument('json_dir', type=Path)

    args = parser.parse_args()

    audio_dir = args.wav_dir
    json_dir = args.json_dir

    app.run()
