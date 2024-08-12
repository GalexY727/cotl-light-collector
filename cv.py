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
    
def detect_stars(image):
    global star_size, particle_size, star_threshold, particle_threshold

    # Convert image to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Calculate histogram
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256])

    # Find peak values in histogram
    peaks, _ = find_peaks(hist.flatten(), distance=10, prominence=100)

    # Sort peaks in descending order
    sorted_peaks = sorted(peaks, key=lambda x: hist[x], reverse=True)

    # Find star threshold
    star_threshold = sorted_peaks[0]

    # Find particle threshold
    particle_threshold = sorted_peaks[1]

    # Threshold image to find stars
    _, binary = cv2.threshold(gray, star_threshold, 255, cv2.THRESH_BINARY)

    # Find connected components
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)

    # Filter out small components
    filtered_labels = []
    for label in range(1, num_labels):
        area = stats[label, cv2.CC_STAT_AREA]
        if area >= star_size:
            filtered_labels.append(label)

    # Find stars with particles and stars without particles
    stars_with_particles = []
    stars_without_particles = []
    for label in filtered_labels:
        x, y, w, h = stats[label, cv2.CC_STAT_LEFT], stats[label, cv2.CC_STAT_TOP], stats[label, cv2.CC_STAT_WIDTH], stats[label, cv2.CC_STAT_HEIGHT]

        # Check if the component size is close to the expected star size
        if abs(w - star_size) <= 5 and abs(h - star_size) <= 5:
            # Check for particles in the surrounding area
            surrounding_area = gray[max(0, y-20):min(gray.shape[0], y+h+20),
                                    max(0, x-20):min(gray.shape[1], x+w+20)]

            _, particle_binary = cv2.threshold(surrounding_area, particle_threshold, 255, cv2.THRESH_BINARY)

            # Find connected components in the surrounding area
            num_particle_labels, particle_labels, particle_stats, _ = cv2.connectedComponentsWithStats(particle_binary, connectivity=8)

            # Filter out small particle components
            filtered_particle_labels = []
            for particle_label in range(1, num_particle_labels):
                particle_area = particle_stats[particle_label, cv2.CC_STAT_AREA]
                if particle_area <= particle_size:
                    filtered_particle_labels.append(particle_label)

            # Check if there are particles near the edge
            has_particles = False
            for particle_label in filtered_particle_labels:
                px, py, pw, ph = particle_stats[particle_label, cv2.CC_STAT_LEFT], particle_stats[particle_label, cv2.CC_STAT_TOP], particle_stats[particle_label, cv2.CC_STAT_WIDTH], particle_stats[particle_label, cv2.CC_STAT_HEIGHT]
                if px < 10 or px > w-10 or py < 10 or py > h-10:
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