import pyautogui
import keyboard
import time
import os
import cv2
import numpy as np
from ahk import AHK

ahk = AHK()

page_transition_time = 1.3
confidence = 0.8

total_pages = 10
current_page = 0

friend_count = 0

screen_width, screen_height = pyautogui.size()

using_zenbook = screen_width > 1920
path = './media/zenbook/' if using_zenbook else './media/desktop/'

def pick_region(region1, region2):
    return region1 if not using_zenbook else region2

def cv_pick_region(region1, region2):
    desired_region = region1 if not using_zenbook else region2
    return (desired_region[0], desired_region[1], desired_region[0]+desired_region[2], desired_region[1]+desired_region[3])


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

def find_all(image, haystackPath=None):
    region = pick_region((190, 120, 1510, 948), (250, 200, 2300, 1360))
    try:
        if haystackPath is None:
            pyautogui.moveTo(500, 0)
            return list(pyautogui.locateAllOnScreen(path+image+'.png', grayscale=1, region=region, confidence=.9))
        else:
            return list(pyautogui.locateAll(needleImage=path+image+'.png', haystackImage=haystackPath, grayscale=1, region=region, confidence=.9))
    except:
        return []

def cv_find_all(needlePath, haystackPath='./cache/cv_find_all_cache.png', confidence=.8):
    region = cv_pick_region((190, 120, 1510, 948), (250, 200, 2300, 1360))
    # move mouse out of the way
    pyautogui.moveTo(500, 0)
    # check if the needle is a real file
    try:
        os.read(needlePath)
        cv2.imread(needlePath)
    except:
        needleImage = cv2.imread(path+needlePath+'.png')

    # check if the haystack is a real file
    if haystackPath is None:
        haystackPath = './cache/cv_find_all_cache.png'
    if haystackPath == './cache/cv_find_all_cache.png':
        # take temporary screenshot and assign it to haystack
        pyautogui.screenshot(haystackPath)
        haystackImage = cv2.imread(haystackPath)
    else:
        try:
            haystackImage = cv2.imread(haystackPath)
        except:
            haystackImage = cv2.imread(path+haystackPath+'.png')

    result = cv2.matchTemplate(haystackImage[region[1]:region[3], region[0]:region[2]], needleImage, method=cv2.TM_CCOEFF_NORMED)
    # Invert the array since its [y,y,y,y][x,x,x,x] and we want [x,y][x,y] (literally why is it like that)
    # but first we have to make it [x,x,x,x][y,y,y,y] so we invert it
    locations = np.where(result >= confidence)[::-1]
    # zip is like a zipper, it takes two lists and combines them into a list of tuples
    # so if we have [1,2,3] and [4,5,6] we get [(1,4), (2,5), (3,6)]
    friendlyArray = list(zip(*locations))
    # there are a lot of occuances that appear on top of eachother, this eliminates that
    friendlyArray = make_unique_list(friendlyArray, pixel_distance=needleImage.shape[0])
    friendlyArray = list((item[0] + needleImage.shape[0]//2 + region[0], item[1] + needleImage.shape[0]//2 + region[1]) for item in friendlyArray)
    return friendlyArray
    
def find_flare_stars(testImagePath=None):
    # Look for stars, then look for a group of 2 or more flares within 100 px of the star's center
    lit_star_locations = cv_find_all('lit_friend', testImagePath)
    unlit_star_locations = cv_find_all('unlit_friend', testImagePath)
    flare_positions = cv_find_all('flare', testImagePath)

    flared_star_positions = []
    for star in lit_star_locations + unlit_star_locations:
        star_x, star_y = star[0], star[1]
        flare_group = []
        for flare in flare_positions:
            flare_x, flare_y = flare[0], flare[1]
            hypot = ((star_x - flare_x)**2 + (star_y - flare_y)**2)**.5
            if hypot < 70:
                flare_group.append(flare)
        if len(flare_group) > 1:
            flared_star_positions.append((star_x, star_y))
    return flared_star_positions

def loop():
    global current_page, total_pages
    while current_page <= total_pages:
        testImagePath = './cache/' + str(current_page) + '.png'
        pyautogui.screenshot(testImagePath)
        testImage = cv2.imread(testImagePath)
        # this loop helps double check missed friends
        while True:
            for i in range(2):
                for star in find_flare_stars(testImagePath=testImagePath):
                    cv2.circle(testImage, (int(star[0]), int(star[1])), 40, (255, 0, 255), 5)
            # move mouse out of way becuase we were clicking
            pyautogui.moveTo(500, 0)
            friends = find_all('unlit_friend', haystackPath=testImagePath)
            for friend in friends:
                x, y = pyautogui.center(friend)
                cv2.circle(testImage, (x, y), 12, (0, 255, 0), 2)
            break
        key = 'c'
        ahk.key_down(key)
        time.sleep(.1)
        ahk.key_up(key)
        cv2.imwrite(testImagePath, testImage)
        time.sleep(page_transition_time)
        pyautogui.moveTo(501, 0)
        current_page += 1

if __name__ == '__main__':
    time.sleep(.5)
    loop()