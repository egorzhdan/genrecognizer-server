from flask import Flask, request, render_template, url_for, send_from_directory
from werkzeug.exceptions import BadRequest
from werkzeug.utils import secure_filename, redirect
import os
import scipy.io.wavfile as wav
from base import mfcc
import numpy as np
import keras
import json
from keras.models import model_from_json

app = Flask(__name__, static_folder='static')

SITE_ROOT = os.path.realpath(os.path.dirname(__file__))
ALLOWED_EXTENSIONS = ['mp3', 'wav', 'm4a']
genres = sorted(['classical', 'rock', 'hiphop', 'pop', 'jazz'])


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def read_model():
    with open(os.path.join(SITE_ROOT, 'static', 'model'), 'r') as file:
        md = model_from_json(json.load(file))
        md.load_weights(os.path.join(SITE_ROOT, 'static', 'weights'))
        return md


model = None


@app.route('/', methods=['GET', 'POST'])
def index():
    global model
    if request.method == 'GET':
        return render_template('index.html')
    else:
        if model is None:
            model = read_model()

        print(request.files)
        if 'file' not in request.files:
            return BadRequest()
        file = request.files['file']
        if file.filename == '':
            return BadRequest()
        if file and allowed_file(file.filename):
            print(file.filename)
            filename = secure_filename(file.filename)
            file.save(filename)
            sample_rate, x = wav.read(filename)
            x[x == 0] = 1

            res = mfcc(x, samplerate=sample_rate)
            num_mfcc = len(res)
            mfcc_data = np.mean(res[int(num_mfcc / 10):int(num_mfcc * 9 / 10)], axis=0)

            result = model.predict_proba(np.array([mfcc_data]))[0]
            print(result)

            answer = sorted(zip(genres, result, ['{0:.0f} %'.format(i * 100) for i in result]), key=lambda i: -i[1])
            return render_template('results.html', results=answer)
        return BadRequest()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
