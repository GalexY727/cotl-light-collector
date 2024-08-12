import cv2
import numpy as np
import mss.tools
import time
from PIL import Image
import sys 


def capture_screenshot():
    with mss.mss() as sct:
        monitor = {"top": 190, "left": 160, "width": 1691, "height": 948}
        output = "sct-{top}x{left}_{width}x{height}.png".format(**monitor)
        screenshot = sct.grab(monitor)
        mss.tools.to_png(screenshot.rgb, screenshot.size, output=output)
        return cv2.imread(output)
    
star_size = 63
particle_size = 9
star_threshold = 0
particle_threshold = 0

def detect_stars(image):
    global star_size, particle_size, star_threshold, particle_threshold

    

    # Draw rectangles
    for x, y, w, h in stars_with_particles:
        cv2.rectangle(image, (x, y), (x+w, y+h), (0, 255, 0), 2)  # Green for stars with particles

    for x, y, w, h in stars_without_particles:
        cv2.rectangle(image, (x, y), (x+w, y+h), (0, 0, 255), 2)  # Red for stars without particles

    return image, len(stars_with_particles), len(stars_without_particles)
    
def main():
    # Test on provided images
    
    result_image, stars_with_particles, stars_without_particles = detect_stars(cv2.imread("image1.png"))

    cv2.imshow('Detected Stars', result_image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    print(f"Live detection:")
    print(f"Detected {stars_with_particles} stars with particles")
    print(f"Detected {stars_without_particles} stars without particles")

if __name__ == "__main__":
    # print(sys.executable)

    time.sleep(.5)
    main()