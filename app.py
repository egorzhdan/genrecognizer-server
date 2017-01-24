from flask import Flask, request, render_template, url_for, send_from_directory, abort, jsonify
from flask_cors import CORS
from werkzeug.exceptions import BadRequest, Gone, InternalServerError, NotFound, ServiceUnavailable
from werkzeug.utils import secure_filename, redirect
import os
import string
import random
import numpy as np
import keras

import json
from keras.models import model_from_json
import urllib.request, urllib.parse
import base64
import matplotlib as mpl

mpl.use('Agg')
import matplotlib.pyplot as plt

import librosa
import spectrograms

app = Flask(__name__, static_folder='static')
CORS(app)

cache = {'gr_recents': []}

SITE_ROOT = os.path.realpath(os.path.dirname(__file__))
ALLOWED_EXTENSIONS = ['mp3', 'wav', 'm4a', 'flac']
genres = sorted(['classical', 'country', 'rock', 'hip-hop', 'pop', 'jazz'])


def get_recents():
    val = cache['gr_recents']
    if val is None:
        return []
    return val


def add_recent(data):
    rec = [data] + get_recents()
    if len(rec) > 5:
        rec = rec[:5]
    cache['gr_recents'] = rec


def mark_cache_verdict(url, vtype):
    for item in cache['gr_recents']:
        if item['url'] == url:
            item['verdict'] = vtype


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def random_string(n):
    return ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(n))


def read_model():
    with open(os.path.join(SITE_ROOT, 'static', 'model'), 'r') as file:
        md = model_from_json(json.load(file))
        md.load_weights(os.path.join(SITE_ROOT, 'static', 'weights'))
        return md


model = None


def spectrogram(file_path):
    y, sr = librosa.load(file_path)
    s = librosa.feature.melspectrogram(y, sr=sr, n_mels=128)
    log = librosa.logamplitude(s, ref_power=np.max)
    return log[:, :2400], sr


def website_by_url(url):
    return 'youtube'


def process(filename, need_image=False):
    image = None
    os.system('ffmpeg -loglevel fatal -ss 60 -t 60 -i "' + filename + '" "' + filename + '-1.wav"')
    try:
        os.system('rm "' + filename + '"')
    except OSError:
        print("OSError")
        raise BadRequest('bad file')

    spectr, sr = spectrogram(filename + '-1.wav')

    if need_image:
        spectrograms.make_for_sample(spectr, sr, filename)
        with open(filename + '.png', 'rb') as f:
            image = base64.b64encode(f.read()).decode('utf-8').replace('\n', '')
        os.system('rm "' + filename + '.png"')

    os.system('rm "' + filename + '-1.wav"')

    x = np.asarray([spectr])
    x = x.astype('float32')
    x /= 256.0

    new_x = []

    for i in range(len(x)):
        new_x.append([x[i]])

    new_x = np.array(new_x)

    result = model.predict_proba(new_x)[0]
    print(result)
    return result, image


def process_youtube(filename, url, need_title=False, need_image=False):
    title = None
    if 'list=' in url:
        url = url[:url.index('&list=')]
    if need_title:
        title = os.popen('youtube-dl -q --get-filename -o "%(title)s" "' + url + '"').read().rstrip()
        title = title.replace('<', '(').replace('>', ')')\
            .replace('(Official Music Video)', '').replace('(Lyric Video)', '').replace('(Music Video)', '').replace('[Official Video]', '')
    os.system('youtube-dl --no-playlist --extract-audio --audio-format "wav" --audio-quality 192 -o "' + filename +
              '.%(ext)s" "' + url + '"')

    try:
        result, image = process(filename + '.wav', need_image)
    except FileNotFoundError:
        raise ServiceUnavailable('Failed to download the video. '
                                 'Please ensure you entered a correct URL and the video is available on the US YouTube')

    return title, sorted(zip(genres, result, ['{0:.0f} %'.format(i * 100) for i in result]), key=lambda i: -i[1]), image


@app.route('/', methods=['GET'])
def index():
    global model
    if request.method == 'GET' or request.method == 'HEAD':
        print(get_recents())
        return render_template('index.html', recents=get_recents())
    raise BadRequest()


@app.route('/recognize_youtube/<path:url>', methods=['GET'])
def recognize_youtube(url=None):
    global model
    if model is None:
        model = read_model()
    filename = random_string(20)
    title, answer, image = process_youtube(filename, url, need_title=False, need_image=False)
    return json.dumps([answer[0][0], answer[0][2]])


@app.route('/recognize', methods=['POST'])
def recognize():
    global model
    if model is None:
        model = read_model()

    if 'file' in request.files:
        print(request.files)
        file = request.files['file']
        if file.filename == '':
            raise BadRequest('No file uploaded')
        if file and allowed_file(file.filename):
            print(file.filename)
            filename = secure_filename(file.filename)
            file.save(filename)

            result, image = process(filename)

            answer = sorted(zip(genres, result, ['{0:.0f} %'.format(i * 100) for i in result]), key=lambda i: -i[1])
            return render_template('results.html', results=answer)
    elif 'select' in request.form:
        source = request.form['select']
        if len(source) == 0:
            raise BadRequest()
        url = request.form['url']
        print(source, url)
        if len(url.strip()) == 0:
            raise BadRequest('URL cannot be empty')
        filename = random_string(20)
        print('filename =', filename)
        if source == 'youtube':
            title, answer, image = process_youtube(filename, url, need_title=True, need_image=True)
            if len(title) > 60:
                title = title[:57] + '...'
            add_recent({'title': title, 'answer': answer[0][0], 'url': url})
            return render_template('results.html', show_title=True, title=title,
                                   title_safe=title.replace('\'', '').replace('\"', ''), results=answer,
                                   allow_disagree=True, url=url, base64img=image)
        elif source == 'lastfm':
            raise BadRequest('lastfm is not supported yet')
    raise BadRequest('Neither file nor URL was submitted')


@app.route('/agree', methods=['GET'])
def agree():
    if 'url' not in request.args or 'title' not in request.args or 'predicted' not in request.args:
        raise BadRequest()
    url = request.args['url']
    title = request.args['title']
    predicted = request.args['predicted']
    send_telegram_report('OK: ', title, predicted, url)
    print('Agreed: ' + title + ' was recognized as ' + predicted + ' (' + url + ')')
    return 'ok'


@app.route('/disagree', methods=['GET'])
def disagree():
    if 'url' not in request.args or 'title' not in request.args or 'predicted' not in request.args:
        raise BadRequest()
    url = request.args['url']
    title = request.args['title']
    predicted = request.args['predicted']
    send_telegram_report('Wrong: ', title, predicted, url)
    print('Disagreed: ' + title + ' was recognized as ' + predicted + ' (' + url + ')')
    return 'ok'


@app.errorhandler(404)
def page_not_found(e):
    print('not found', e)
    return render_template('error.html', error='Not Found'), 404


@app.errorhandler(400)
def bad_request(e):
    print('bad request', e)
    return render_template('error.html', error='Bad Request', description=e.description), 400


@app.errorhandler(500)
def internal_server_error(e):
    print('internal server error', e)
    return render_template('error.html', error='Internal Server Error', description=e.description), 500


@app.errorhandler(503)
def service_unavailable(e):
    print('service unavailable', e)
    return render_template('error.html', error='Service Unavailable', description=e.description), 503


def send_telegram_report(vtype, track_title, genre_predicted, url):
    bot_id = '296039634:AAGrRrRikkvIrInsdhK0g_-CWE1I3Zy5tqc'
    chat_id = '29312956'
    mark_cache_verdict(url, vtype)
    url = "https://api.telegram.org/bot" + bot_id + "/sendMessage?chat_id=" + chat_id + "&text=" + vtype + \
          urllib.parse.quote('' + track_title + ' was recognized as ' + genre_predicted + '' + '\nURL: ' + url)
    urllib.request.urlopen(url).read()


@app.route('/chrome', methods=['GET'])
def chrome_ext():
    return render_template('chrome.html')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
