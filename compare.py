import cv2
import numpy as np
import os
import pyautogui
import time
from ahk import  AHK

ahk = AHK()

def compare_templates(template, image, method=cv2.TM_CCOEFF_NORMED, threshold=0.8):
    # Perform template matching using the specified method
    result = cv2.matchTemplate(image, template, method)
    locations = np.where(result >= threshold)
    return locations

def make_unique_list(list, pixel_distance=3):
    unique_list = []
    for item in list:
        unique = True
        for unique_item in unique_list:
            if abs(unique_item[0] - item[0]) < pixel_distance:
                unique = False
        if unique:
            unique_list.append(item)
    return unique_list

def find_occurrences(image_path, template_path=None, template_directory=None, threshold=.8, method=cv2.TM_CCOEFF_NORMED):
    # Load the image where occurrences are to be found
    image = cv2.imread(image_path)
    if image is None:
        print(f"Failed to load image {image_path}")
        return
    
    matches = []

    # If template_path is provided, use it as the template
    if template_path:
        template = cv2.imread(template_path)
        if template is None:
            print(f"Failed to load template {template_path}")
            return
        
        locations = compare_templates(template, image, threshold=threshold, method=method)
        matches.append(locations)
    else:
        # Iterate over all files in the template directory
        for filename in os.listdir(template_directory):
            if filename.endswith(".png") or filename.endswith(".jpg"):
                template_path = os.path.join(template_directory, filename)
                template = cv2.imread(template_path)
                if template is None:
                    print(f"Failed to load template {template_path}")
                    continue
                
                locations = compare_templates(template, image, threshold=threshold)
                matches.append(locations)
    
    # Highlight matches on the image (for visualization)
    for locations in matches:
        for loc_x, loc_y in zip(locations[1][::-1], locations[0][::-1]):
            x, y = loc_x, loc_y
            template_width, template_height = template.shape[1], template.shape[0]
            color = (0, 0, 255) if method == cv2.TM_CCOEFF else (0, 255, 0) if method == cv2.TM_CCORR_NORMED else (255, 0, 255) if method == cv2.TM_CCOEFF_NORMED else (255, 0, 0)
            cv2.rectangle(image, (x, y), (x + template_width, y + template_height), color, 2)
    
    # Save or display the result
    print(f"Found {sum(len(loc[0]) for loc in matches)} matches. Results saved to matches_output.png")
    return (sum(len(loc[0]) for loc in matches), image)

# Example usage
image_path = "image5.png"
template_directory = "./media/zenbook/lit_friends"  # Replace with the path to your template directory

def flare_finder(ogimage):
    image = cv2.imread(image_path)
    try:
        for pos in pyautogui.locateAll(needleImage='./media/zenbook/flare.png', haystackImage=image_path, grayscale=0, confidence=.9):
            # draw rectangle
            x, y, width, height = pos
            cv2.rectangle(ogimage, (x, y), (x + width, y + height), color, 1)
    except:
        pass
    return ogimage

final_image = flare_finder(cv2.imread(image_path))

def cv_find_all(haystack, needle, confidence=.8, color=(0, 255, 0)):
    result = cv2.matchTemplate(haystack, needle, method=cv2.TM_CCOEFF_NORMED)
    locations = np.where(result >= confidence)[::-1]
    friendlyArray = list(zip(*locations))
    friendlyArray = make_unique_list(friendlyArray, pixel_distance=needle.shape[0])
    return (friendlyArray, haystack)

if __name__ == "__main__":
    # occurances, image = find_occurrences(image_path, template_path='./media/desktop/flare.png', threshold=.8, method=cv2.TM_CCOEFF_NORMED)
    # cv2.imwrite("matches_output.png", image)
    occurances, image = cv_find_all(cv2.imread(image_path), cv2.imread('./media/desktop/flare_old.png'), color=(255, 0, 255))
    cv2.imwrite("matches_output.png", final_image)