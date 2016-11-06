import werkzeug
from flask import Flask, request, render_template, url_for, send_from_directory, abort, jsonify
from werkzeug.exceptions import BadRequest, Gone, InternalServerError
from werkzeug.utils import secure_filename, redirect
import os
import string
import random
import scipy.io.wavfile as wav
import numpy as np
import keras
from unittest import mock
import sys
import json
from keras.models import model_from_json
import urllib.request, urllib.parse

sys.modules.update((mod_name, mock.Mock()) for mod_name in ['matplotlib', 'matplotlib.pyplot', 'matplotlib.image'])

import librosa

app = Flask(__name__, static_folder='static')

SITE_ROOT = os.path.realpath(os.path.dirname(__file__))
ALLOWED_EXTENSIONS = ['mp3', 'wav', 'm4a', 'flac']
genres = sorted(['classical', 'rock', 'hip-hop', 'pop', 'jazz'])


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
    return log[:, :1200]


def website_by_url(url):
    return 'youtube'


def process(filename):
    os.system('ffmpeg -loglevel fatal -ss 60 -t 60 -i "' + filename + '" "' + filename + '-1.wav"')
    try:
        os.system('rm "' + filename + '"')
    except OSError:
        print("OSError")
        raise BadRequest('bad file')

    spectr = spectrogram(filename + '-1.wav')
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
    return result


def process_youtube(filename, url, need_title=False):
    title = None
    if need_title:
        title = os.popen('youtube-dl -q --get-filename -o "%(title)s" "' + url + '"').read().rstrip()
        title = title.replace('<', '(').replace('>', ')')
    os.system('youtube-dl --extract-audio --audio-format "wav" --audio-quality 192 -o "' + filename +
              '.%(ext)s" "' + url + '"')

    try:
        result = process(filename + '.wav')
    except FileNotFoundError:
        raise Gone("Failed to Download the Video")

    return title, sorted(zip(genres, result, ['{0:.0f} %'.format(i * 100) for i in result]), key=lambda i: -i[1])


@app.route('/', methods=['GET', 'POST'])
def index():
    global model
    if request.method == 'GET' or request.method == 'HEAD':
        return render_template('index.html')
    elif request.method == 'POST':
        if model is None:
            model = read_model()

        if 'file' in request.files:
            print(request.files)
            file = request.files['file']
            if file.filename == '':
                raise BadRequest()
            if file and allowed_file(file.filename):
                print(file.filename)
                filename = secure_filename(file.filename)
                file.save(filename)

                result = process(filename)

                answer = sorted(zip(genres, result, ['{0:.0f} %'.format(i * 100) for i in result]), key=lambda i: -i[1])
                return render_template('results.html', results=answer)
        elif 'select' in request.form:
            source = request.form['select']
            if len(source) == 0:
                raise BadRequest()
            url = request.form['url']
            print(source, url)
            filename = random_string(20)
            print('filename =', filename)
            if source == 'youtube':
                title, answer = process_youtube(filename, url)
                return render_template('results.html', show_title=False, results=answer, allow_disagree=True, url=url)
            elif source == 'lastfm':
                pass
        raise BadRequest()


@app.route('/recognize', methods=['POST'])
def recognize():
    global model
    if model is None:
        model = read_model()

    if 'file' in request.files:
        print(request.files)
        file = request.files['file']
        if file.filename == '':
            raise BadRequest()
        if file and allowed_file(file.filename):
            print(file.filename)
            filename = secure_filename(file.filename)
            file.save(filename)

            result = process(filename)

            answer = sorted(zip(genres, result, ['{0:.0f} %'.format(i * 100) for i in result]), key=lambda i: -i[1])
            # return jsonify({'results': answer})
            return render_template('results.html', results=answer)
    elif 'select' in request.form:
        source = request.form['select']
        if len(source) == 0:
            raise BadRequest()
        url = request.form['url']
        print(source, url)
        filename = random_string(20)
        print('filename =', filename)
        if source == 'youtube':
            title, answer = process_youtube(filename, url)
            # for i in range(len(answer)):
            #     answer[i] = (answer[i][0], str(answer[i][1]), answer[i][2])
            # return jsonify({'show_title': False, 'results': answer, 'allow_disagree': True, 'url': url})
            return render_template('results.html', show_title=False, results=answer, allow_disagree=True, url=url)
        elif source == 'lastfm':
            pass
    raise BadRequest()


@app.route('/disagree', methods=['GET'])
def disagree():
    print('Disagree', request.args)
    if 'url' not in request.args:
        raise BadRequest()
    url = request.args['url']
    website = website_by_url(url)

    filename = random_string(20)
    if website == 'youtube':
        title, answer = process_youtube(filename, url, True)
        predicted = answer[0][0]
    else:
        raise InternalServerError('unknown website')
    send_disagree_report(title, predicted, url)
    return 'ok'


@app.errorhandler(404)
def page_not_found(e):
    print('not found', e)
    return render_template('error.html', error='Not Found'), 404


@app.errorhandler(400)
def bad_request(e):
    print('bad request', e)
    return render_template('error.html', error='Bad Request'), 400


@app.errorhandler(500)
def internal_server_error(e):
    print('internal server error', e)
    return render_template('error.html', error='Internal Server Error'), 500


@app.errorhandler(503)
def service_unavailable(e):
    print('service unavailable', e)
    return render_template('error.html', error='Service Unavailable'), 503


@app.errorhandler(410)
def service_unavailable(e):
    print('gone', e)
    return render_template('error.html', error=e.description), 410


def send_disagree_report(track_title, genre_predicted, url):
    bot_id = '296039634:AAGrRrRikkvIrInsdhK0g_-CWE1I3Zy5tqc'
    chat_id = '29312956'
    url = "https://api.telegram.org/bot" + bot_id + "/sendMessage?chat_id=" + chat_id + "&text=" + \
          urllib.parse.quote('' + track_title + ' was recognized as ' + genre_predicted + '' + '\nURL: ' + url)
    urllib.request.urlopen(url).read()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
