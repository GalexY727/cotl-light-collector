import pyautogui
import keyboard
import time
import os
import cv2
import numpy as np
from ahk import AHK

ahk = AHK()

page_transition_time = 0.86
confidence = 0.9

total_pages = -1
current_page = 0

friend_count = 0

screen_width, screen_height = pyautogui.size()

using_zenbook = screen_width > 1920
path = './media/zenbook/' if using_zenbook else './media/desktop/'

def pick_region(region1, region2):
    return region1 if not using_zenbook else region2

def timer():
    start_time = time.time()
    try:
        region = (840, 0, 1087, 1800)
        pyautogui.locateOnScreen('./media/zenbook/candle.png', grayscale=1, region=region, confidence=.6)
        print("Found")
    except Exception as e:
        print("Error occurred:", str(e))
    print("--- %s seconds ---" % (time.time() - start_time))

def ss():
    region = (2192, 1701, 60, 60)
    pyautogui.screenshot(region=region).save('region.png')
    try: 
        pyautogui.locateOnScreen('./media/zenbook/q_info.png', grayscale=1, region=region, confidence=.9)
        print("Found")
    except:
        pass

def flare_finder():
    try:
        for pos in pyautogui.locateAllOnScreen('./media/zenbook/flare.png', grayscale=1, confidence=.9):
            pyautogui.moveTo(pos)
            time.sleep(.025)
    except:
        pass

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

def find_all(image):
    pyautogui.moveTo(500, 0)
    try:
        region = pick_region((190, 160, 1691, 948), (250, 200, 2300, 1360))
        return list(pyautogui.locateAllOnScreen(path+image+'.png', grayscale=1, region=region, confidence=confidence))
    except:
        return []
    
def find_all_cv(needle, haystack, threshold=0.9):
    result = cv2.matchTemplate(haystack, path+needle+'.png', cv2.TM_CCOEFF_NORMED)
    loc = np.where(result >= threshold)
    return list(zip(*loc[::-1]))


def get_flare_stars(image):
    positions = make_unique_list(find_all_cv('flare', image), pixel_distance=10)
    star_positions = []
    # find groupings of flares that are within 100 px of each other
    # a group of 3 or more is a star
    # get the center of the star and add that position to a list
    for position in positions:
        x, y = position
        flare_group = []
        for otro_star in positions:
            x2, y2 = otro_star
            hypot = ((x - x2)**2 + (y - y2)**2)**.5
            if hypot < 120:
                flare_group.append(otro_star)
        if len(flare_group) > 1:
            centerpoint = (0, 0)
            for flare_pos in flare_group:
                centerpoint = (centerpoint[0] + flare_pos[0], centerpoint[1] + flare_pos[1])
            centerpoint = (centerpoint[0] / len(flare_group), centerpoint[1] / len(flare_group))
            star_positions.append(centerpoint)
    flare_centers = make_unique_list(star_positions, pixel_distance=20)
    lit_star_locations = make_unique_list(find_all('lit_friend'), pixel_distance=10)
    final_star_positions = []
    for star in flare_centers:
        # find closest lit star to this star
        closest = 200
        closest_star = None
        for lit_star in lit_star_locations:
            distance = ((star[0] - lit_star[0])**2 + (star[1] - lit_star[1])**2)**.5
            if distance < closest:
                closest = distance
                closest_star = lit_star
        final_star_positions.append(closest_star)
    return final_star_positions

def find_flare_stars(image):
    # go inside path./lit_friends/* and go through all pictures in that folder
    # and match with one screenshot of the screen
    # return a list of unique positions (50px) of all results
    results = []
    for picture in os.listdir(path+'lit_friends'):
        # temp screenshot 
        screenshot = cv2.imread(image)
        try:
            region = pick_region((190, 160, 1691, 948), (250, 200, 2300, 1360))
            haystack = screenshot[region[1]:region[3], region[0]:region[2]]
            needle = cv2.imread(path+'lit_friends/'+picture, cv2.IMREAD_GRAYSCALE)
            result = cv2.matchTemplate(haystack, needle, cv2.TM_CCOEFF_NORMED)
            threshold = 0.1
            loc = np.where(result >= threshold)
            for pt in zip(*loc[::-1]):
                x, y = pt[0] + needle.shape[1] // 2, pt[1] + needle.shape[0] // 2
                results.append((x, y))
        except:
            pass
        # delete temp screenshot
    
    return make_unique_list(results, pixel_distance=50)


def confidences(image):
    for i in range(4, 10):
        conf = i/100 + .9
        for picture in os.listdir(path+'lit_friends'):
            # temp screenshot 
            pyautogui.screenshot(image)
            length = []
            region = pick_region((190, 160, 1691, 948), (250, 200, 2300, 1360))
            positions = list(pyautogui.locateAll(needleImage=(path+'lit_friends/'+picture), haystackImage=image, grayscale=1, region=region, confidence=conf))
            for position in positions:
                x, y = pyautogui.center(position)
                length.append((x, y))
            print(str(len(length)) + ' found with confidence ' + str(conf))

def draw_flare_stars(image_file):
        flare_positions = find_flare_stars(image_file)
        image = cv2.imread(image_file)
        for position in flare_positions:
            x, y = position
            cv2.rectangle(image, (x-10, y-10), (x+10, y+10), (255, 171, 10), 2)
        print("Found", len(flare_positions), "flare stars")
        # cv2.imshow("Flare Stars", image)
        # cv2.waitKey(0)
        # cv2.destroyAllWindows()

if __name__ == '__main__':
    time.sleep(.5)
    draw_flare_stars('image2.png')