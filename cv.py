import cv2
import numpy as np
import mss.tools
from PIL import Image

def capture_screenshot():
    with mss.mss() as sct:
        monitor = {"top": 250, "left": 200, "width": 2300, "height": 1360}
        output = "sct-{top}x{left}_{width}x{height}.png".format(**monitor)
        screenshot = sct.grab(monitor)
        mss.tools.to_png(screenshot.rgb, screenshot.size, output=output)
        return np.array(Image.open(output))

def create_star_template(size):
    template = np.zeros((size, size), dtype=np.uint8)
    center = size // 2
    
    # Create the main star shape
    for i in range(4):
        angle = i * np.pi / 2
        x = int(center + (size // 3) * np.cos(angle))
        y = int(center + (size // 3) * np.sin(angle))
        cv2.line(template, (center, center), (x, y), 255, 2)
    
    # Add a circle in the center for the core of the star
    cv2.circle(template, (center, center), size // 8, 255, -1)
    
    # Add some "particle" effects
    for _ in range(20):
        x = np.random.randint(0, size)
        y = np.random.randint(0, size)
        cv2.circle(template, (x, y), 1, 255, -1)
    
    return template

def detect_stars_with_particles(image, threshold=0.7):
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

    # Create a template for the star with particles
    template_size = 50  # Adjust based on the size of your stars
    template = create_star_template(template_size)

    # Perform template matching
    result = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)

    # Find positions where the matching exceeds the threshold
    locations = np.where(result >= threshold)
    locations = list(zip(*locations[::-1]))

    # Draw rectangles around the detected stars
    for loc in locations:
        top_left = loc
        bottom_right = (top_left[0] + template_size, top_left[1] + template_size)
        cv2.rectangle(image, top_left, bottom_right, (0, 255, 0), 2)

    return image, locations

def main():
    # Capture screenshot
    screenshot = capture_screenshot()
    
    # Detect stars with particles
    result_image, detected_locations = detect_stars_with_particles(screenshot)

    # Display the result
    cv2.imshow('Detected Stars with Particles', cv2.cvtColor(result_image, cv2.COLOR_RGB2BGR))
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    print(f"Detected {len(detected_locations)} stars with particles")

if __name__ == "__main__":
    main()