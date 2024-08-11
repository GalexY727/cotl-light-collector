import cv2
import numpy as np
import mss.tools
import time
from PIL import Image

def capture_screenshot():
    with mss.mss() as sct:
        monitor = {"top": 250, "left": 200, "width": 2300, "height": 1360}
        output = "sct-{top}x{left}_{width}x{height}.png".format(**monitor)
        screenshot = sct.grab(monitor)
        mss.tools.to_png(screenshot.rgb, screenshot.size, output=output)
        return cv2.imread(output)

star_size = 63
particle_size = 9
star_threshold = 200
particle_threshold = 150

def detect_stars(image):
    global star_size, particle_size, star_threshold, particle_threshold
    
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Detect potential stars
    _, binary = cv2.threshold(gray, star_threshold, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    stars_with_particles = []
    stars_without_particles = []
    
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        
        # Check if the contour size is close to the expected star size
        if abs(w - star_size) <= 5 and abs(h - star_size) <= 5:
            # Check for particles in the surrounding area
            surrounding_area = gray[max(0, y-20):min(gray.shape[0], y+h+20),
                                    max(0, x-20):min(gray.shape[1], x+w+20)]
            
            _, particle_binary = cv2.threshold(surrounding_area, particle_threshold, 255, cv2.THRESH_BINARY)
            particle_contours, _ = cv2.findContours(particle_binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            has_particles = False
            for particle_contour in particle_contours:
                px, py, pw, ph = cv2.boundingRect(particle_contour)
                if (pw <= particle_size and ph <= particle_size and 
                    (px < 10 or px > w-10 or py < 10 or py > h-10)):  # Ensure particle is near the edge
                    has_particles = True
                    break
            
            if has_particles:
                stars_with_particles.append((x, y, w, h))
            else:
                stars_without_particles.append((x, y, w, h))
    
    # Draw rectangles
    for x, y, w, h in stars_with_particles:
        cv2.rectangle(image, (x, y), (x+w, y+h), (0, 255, 0), 2)  # Green for stars with particles
    
    for x, y, w, h in stars_without_particles:
        cv2.rectangle(image, (x, y), (x+w, y+h), (0, 0, 255), 2)  # Red for stars without particles
    
    return image, len(stars_with_particles), len(stars_without_particles)

def test_on_image(image_path):
    image = cv2.imread(image_path)
    result_image, with_particles, without_particles = detect_stars(image)
    cv2.imwrite(f"result_{image_path}", result_image)
    print(f"Image: {image_path}")
    print(f"Stars with particles: {with_particles}")
    print(f"Stars without particles: {without_particles}")
    return with_particles, without_particles

def main():
    # Test on provided images
    test1_with, test1_without = test_on_image("image1.png")
    test2_with, test2_without = test_on_image("image2.png")
    
    if test1_with == 13 and test1_without == 0 and test2_with == 2 and test2_without == 8:
        print("Tests passed successfully!")
    else:
        print("Tests failed. Adjusting parameters...")
        # adjust parameters and re-run tests
        # Adjust parameters and re-run tests
        max_attempts = 100
        attempts = 0
        global star_size, particle_size, star_threshold, particle_threshold
        while attempts < max_attempts:
            star_threshold = int(star_threshold * 1.25)
            particle_threshold = int(particle_threshold * 1.25)
            
            test1_with, test1_without = test_on_image("image1.png")
            test2_with, test2_without = test_on_image("image2.png")
            
            if test1_with == 13 and test1_without == 0 and test2_with == 2 and test2_without == 8:
                print("Tests passed successfully!")
                break
            
            attempts += 1
        
        if attempts == max_attempts:
            print("Tests failed after maximum attempts. Unable to find suitable parameters.")
    return
    
    # If tests pass, run on live screenshot
    screenshot = capture_screenshot()
    result_image, stars_with_particles, stars_without_particles = detect_stars(screenshot)

    cv2.imshow('Detected Stars', result_image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    print(f"Live detection:")
    print(f"Detected {stars_with_particles} stars with particles")
    print(f"Detected {stars_without_particles} stars without particles")

if __name__ == "__main__":
    time.sleep(.5)
    main()