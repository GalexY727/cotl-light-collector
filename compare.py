import cv2
import numpy as np
import os

def compare_templates(template, image, method=cv2.TM_CCOEFF_NORMED, threshold=0.8):
    # Perform template matching using the specified method
    result = cv2.matchTemplate(image, template, method)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    locations = np.where(result >= threshold)
    print(locations)
    return locations

def find_occurrences(image_path, template_directory, threshold=0.8):
    # Load the image where occurrences are to be found
    image = cv2.imread(image_path)
    if image is None:
        print(f"Failed to load image {image_path}")
        return
    
    matches = []

    # Iterate over all files in the template directory
    for filename in os.listdir(template_directory):
        if filename.endswith(".png") or filename.endswith(".jpg"):
            template_path = os.path.join(template_directory, filename)
            template = cv2.imread(template_path)
            if template is None:
                print(f"Failed to load template {template_path}")
                continue
            
            for loc in compare_templates(template, image, threshold=threshold):
                matches.append((loc.x, loc.y, threshold))
    
    # Highlight matches on the image (for visualization)
    for (x, y, score) in matches:
        template_width, template_height = template.shape[1], template.shape[0]
        cv2.rectangle(image, (x, y), (x + template_width, y + template_height), (10, 171, 255), 2)
    
    # Save or display the result
    cv2.imwrite("matches_output.png", image)
    print(f"Found {len(matches)} matches. Results saved to matches_output.png")

# Example usage
image_path = "image1.png"
template_directory = "./media/zenbook/lit_friends"  # Replace with the path to your template directory

find_occurrences(image_path, template_directory)
