import cv2
import numpy as np
import os

def compare_templates(template, image, method=cv2.TM_CCOEFF_NORMED, threshold=0.8):
    # Perform template matching using the specified method
    result = cv2.matchTemplate(image, template, method)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    locations = np.where(result >= threshold)
    return locations

def find_occurrences(image_path, template_directory, threshold=.8):
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
            
            loc = compare_templates(template, image, threshold=threshold)
    
    # Highlight matches on the image (for visualization)
    for loc_x, loc_y in zip(loc[1][::-1], loc[0][::-1]):
        x, y = loc_x, loc_y
        template_width, template_height = template.shape[1], template.shape[0]
        cv2.rectangle(image, (x, y), (x + template_width, y + template_height), (255, 171, 10), 2)
    # Save or display the result
    print(f"Found {len(loc[0])} matches. Results saved to matches_output.png")
    return (len(loc[0]), image)

# Example usage
image_path = "image2.png"
template_directory = "./media/zenbook/lit_friends"  # Replace with the path to your template directory


if __name__ == "__main__":
    for i in range(10, 20):
        occurances, image = find_occurrences(image_path, template_directory, threshold=.8+i/100)
        if occurances < 3 and occurances > 0:
            cv2.imwrite("matches_output.png", image)