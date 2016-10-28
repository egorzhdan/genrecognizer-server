from flask import Flask, request, render_template, url_for, send_from_directory
from werkzeug.exceptions import BadRequest
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


def process(filename):
    os.system('ffmpeg -loglevel fatal -ss 60 -t 60 -i "' + filename + '" "' + filename + '-1.wav"')
    os.system('rm "' + filename + '"')

    spectr = spectrogram(filename + '-1.wav')
    os.system('rm "' + filename + '-1.wav"')

    x = np.asarray([spectr])
    x = x.astype('float32')
    x /= 256.0

    result = model.predict_proba(x)[0]
    print(result)
    return result


@app.route('/', methods=['GET', 'POST'])
def index():
    global model
    if request.method == 'GET' or request.method == 'HEAD':
        return render_template('index.html')
    elif request.method == 'POST':
        if model is None:
            model = read_model()

        print(request.files)

        if 'file' in request.files:
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
            url = request.form['url']
            print(source, url)
            filename = random_string(20)
            print('filename =', filename)
            if source == 'youtube':
                os.system('youtube-dl --extract-audio --audio-format "wav" --audio-quality 192 -o "' + filename +
                          '.%(ext)s" "' + url + '"')

                result = process(filename + '.wav')

                answer = sorted(zip(genres, result, ['{0:.0f} %'.format(i * 100) for i in result]), key=lambda i: -i[1])
                return render_template('results.html', results=answer)
            elif source == 'lastfm':
                pass
        raise BadRequest()


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


def send_disagree_report(track_title, genre_predicted):
    bot_id = '296039634:AAGrRrRikkvIrInsdhK0g_-CWE1I3Zy5tqc'
    chat_id = '29312956'
    url = "https://api.telegram.org/bot" + bot_id + "/sendMessage?chat_id=" + chat_id + "&text=" + \
          urllib.parse.quote('Track *' + track_title + '* was recognized as *' + genre_predicted + '*')
    print(url)
    result = urllib.request.urlopen(url).read()
    print(result)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
