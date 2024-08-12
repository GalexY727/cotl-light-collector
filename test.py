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

def cv_find_all(needlePath, haystackPath='./cache/cv_find_all_cache.png', confidence=.8):
    # check if the needle is a real file
    try:
        os.read(needlePath)
        cv2.imread(needlePath)
    except:
        needleImage = cv2.imread(path+needlePath+'.png')

    # check if the haystack is a real file
    if haystackPath == './cache/cv_find_all_cache.png':
        # take temporary screenshot and assign it to haystack
        haystackImage = pyautogui.screenshot(haystackPath)
    else:
        try:
            haystackImage = cv2.imread(haystackPath)
        except:
            haystackImage = cv2.imread(path+haystackPath+'.png')

    result = cv2.matchTemplate(haystackImage, needleImage, method=cv2.TM_CCOEFF_NORMED)
    # Invert the array since its [y,y,y,y][x,x,x,x] and we want [x,y][x,y] (literally why is it like that)
    # but first we have to make it [x,x,x,x][y,y,y,y] so we invert it
    locations = np.where(result >= confidence)[::-1]
    # zip is like a zipper, it takes two lists and combines them into a list of tuples
    # so if we have [1,2,3] and [4,5,6] we get [(1,4), (2,5), (3,6)]
    friendlyArray = list(zip(*locations))
    # there are a lot of occuances that appear on top of eachother, this eliminates that
    friendlyArray = make_unique_list(friendlyArray, pixel_distance=needleImage.shape[0])
    friendlyArray = list((item[0] + needleImage.shape[0]//2, item[1] + needleImage.shape[0]//2) for item in friendlyArray)
    return friendlyArray
    
def find_flare_stars(testImagePath):
    # Look for stars, then look for a group of 2 or more flares within 100 px of the star's center
    lit_star_locations = cv_find_all('lit_friend', testImagePath)
    print("Found lit stars:", len(lit_star_locations))
    flare_positions = cv_find_all('flare', testImagePath)
    print("Found flares:", len(flare_positions))

    flared_star_positions = []
    for star in lit_star_locations:
        star_x, star_y = star[0], star[1]
        flare_group = []
        for flare in flare_positions:
            flare_x, flare_y = flare[0], flare[1]
            hypot = ((star_x - flare_x)**2 + (star_y - flare_y)**2)**.5
            if hypot < 120:
                flare_group.append(flare)
        if len(flare_group) > 1:
            flared_star_positions.append((star_x, star_y))
    return flared_star_positions

if __name__ == '__main__':
    time.sleep(.5)
    testImagePath = 'image1.png'
    testImage = cv2.imread(testImagePath)
    flared_positions = find_flare_stars(testImagePath)
    for star in flared_positions:
        cv2.circle(testImage, (int(star[0]), int(star[1])), 40, (255, 0, 255), 4)

    for pos in cv_find_all('lit_friend', testImagePath):
        cv2.circle(testImage, (int(pos[0]), int(pos[1])), 15, (0, 255, 0), 4)

    for pos in cv_find_all('flare', testImagePath):
        cv2.circle(testImage, (int(pos[0]), int(pos[1])), 7, (255, 255, 0), 2)

    cv2.imwrite('matches_output.png', testImage)