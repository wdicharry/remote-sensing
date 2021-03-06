import cv2
import numpy as np
from matplotlib import pyplot as plt

import constants
import operations

def histogram_all():
    for band in range(1, 5):
        band_image = cv2.imread(constants.base_name % band)
        band_image = band_image[4418:4859, 1231:1924]
        band_hist = cv2.calcHist([band_image], [0], None, [256], [1, 256])
        plt.plot(band_hist, label='Band %d' % band)
    plt.legend()
    plt.show()
    
if __name__ == '__main__':
    histogram_all()