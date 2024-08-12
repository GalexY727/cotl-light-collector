import cv2
import numpy as np
import os

def save_histogram(image_path, save_path):
    # Load the image
    image = cv2.imread(image_path)
    
    if image is None:
        print(f"Failed to load image {image_path}")
        return
    
    # Convert to grayscale
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Calculate grayscale histogram
    hist_gray = cv2.calcHist([gray_image], [0], None, [256], [0, 256])
    
    # Calculate color histograms for B, G, R channels
    hist_b = cv2.calcHist([image], [0], None, [256], [0, 256])
    hist_g = cv2.calcHist([image], [1], None, [256], [0, 256])
    hist_r = cv2.calcHist([image], [2], None, [256], [0, 256])

    # Combine histograms into a dictionary
    histograms = {
        "grayscale": hist_gray,
        "blue": hist_b,
        "green": hist_g,
        "red": hist_r
    }
    
    # Save histograms as a .npy file
    base_filename = os.path.splitext(os.path.basename(image_path))[0]
    save_filename = os.path.join(save_path, f"{base_filename}_histograms.npy")
    np.save(save_filename, histograms)
    
    print(f"Histograms saved to {save_filename}")

# Example usage
image_path = "./media/zenbook/unlit_friend.png"
save_path = "./histograms/"

save_histogram(image_path, save_path)
