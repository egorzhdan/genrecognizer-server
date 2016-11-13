import os
import matplotlib.pyplot as plt
import librosa


def make_for_sample(spectr, sr, file_path):
    fig_file = file_path + '.png'

    print('Creating spectrogram for', file_path)

    plt.figure(figsize=(20, 4))
    librosa.display.specshow(spectr, sr=sr, cmap='hot')

    plt.tight_layout()

    plt.savefig(fig_file, bbox_inches='tight', pad_inches=0)

    plt.close()
