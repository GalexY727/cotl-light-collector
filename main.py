from pyautogui import *
import pyautogui
import keyboard
from ahk import AHK
import time
import cv2
import numpy as np
import os

ahk = AHK()

page_transition_time = 1.3
confidence = 0.9

total_pages = -1
current_page = 0

friend_count = 0
light_collected = 0

screen_width, screen_height = pyautogui.size()

using_zenbook = screen_width > 1920
path = './media/zenbook/' if using_zenbook else './media/desktop/'

def pick_region(region1, region2):
    return region1 if not using_zenbook else region2

def cv_pick_region(region1, region2):
    desired_region = region1 if not using_zenbook else region2
    return (desired_region[0], desired_region[1], desired_region[0]+desired_region[2], desired_region[1]+desired_region[3])

def press_key(key):
    try:
        region = pick_region((1765, 1026, 120, 50), (2610, 1700, 200, 100))
        pyautogui.locateOnScreen(path+'esc.png', grayscale=1, region=region, confidence=.7)
        ahk.key_down(key)
        time.sleep(.1)
        ahk.key_up(key)
        return 1
    except:
        print("Esc not found")
        return 0
    
def doubleClick(x, y):
    ahk.click(x, y)
    ahk.click(x, y)

def attempt_reentry():
    try:
        pyautogui.locateOnScreen(path+'const.png', grayscale=1, confidence=0.6)
        key = 'f'
        ahk.key_down(key)
        time.sleep(.1)
        ahk.key_up(key)
        return 1
    except:
        return 0

def enter_ui():
    if attempt_reentry():
        return
    
    for _ in range(7):
        pyautogui.scroll(25)
        pyautogui.moveTo(pyautogui.size()[0]/2, pyautogui.size()[1])
    
    attempts = 50
    
    while attempts > 0:
        if (attempt_reentry()):
            break
        attempts -= 1
        pyautogui.moveTo(1591, 932)
        pass
    time.sleep(3)


def index_to_start():
    try:
        pyautogui.locateOnScreen(path+'add_friends.png', grayscale=1, confidence=confidence)
        return
    except:
        key = 'z'
        ahk.key_down(key)
        time.sleep(.1)
        ahk.key_up(key)
        index_to_start()

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

# run AFTER we index or else everything explodes
def get_total_pages():
    left, top, width, height = pyautogui.locateOnScreen(path+'add_friends.png', grayscale=1, confidence=confidence)
    screen_width, screen_height = pyautogui.size()
    region=(left, top+height, int(screen_width*0.12), screen_height-(top+height))
    try:
        positions = pyautogui.locateAllOnScreen(path+'page_bubble_online.png', grayscale=0, region=region, confidence=confidence)
        pages_online = positions
    except:
        pages_online = 0
        print("No online")
    try:
        positions = pyautogui.locateAllOnScreen(path+'page_bubble.png', grayscale=0, region=region, confidence=confidence)
        pages_offline = positions
    except:
        pages_offline = 0
        print("No offline")
    return len(make_unique_list(list(pages_online) + list(pages_offline)))

def find_all(image, haystackPath=None):
    region = pick_region((190, 120, 1510, 948), (250, 200, 2300, 1360))
    try:
        if haystackPath is None:
            pyautogui.moveTo(500, 0)
            width = cv2.imread(path+image+'.png').shape[1]
            return make_unique_list(list(pyautogui.locateAllOnScreen(path+image+'.png', grayscale=1, region=region, confidence=confidence)), pixel_distance=width)
        else:
            return make_unique_list(list(pyautogui.locateAll(needleImage=path+image+'.png', haystackImage=haystackPath, grayscale=1, region=region, confidence=confidence)), pixel_distance=width)
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

    
def wait_for_candle(duration):
    start_time = time.time()
    while time.time() - start_time < duration:
        # Considering the search takes .24 seconds, 
        # if we have less than .24 seconds left, 
        # we should just wait it out
        if duration-(time.time() - start_time) < 0.24:
            time.sleep(duration-(time.time() - start_time))
        try:
            region = pick_region((500,0,784,1080), (840, 0, 1087, 1800))
            pyautogui.locateOnScreen(path+'candle.png', grayscale=1, region=region, confidence=.6)
            time.sleep(.05)
            return 1
        except:
            pass
    return 0

def light_friend(x, y):
    doubleClick(x, y)

    time.sleep(.3)

    skip = 0
    
    # Let's make sure we didn't misclick
    try:
        region = pick_region((500,0,784,1080), (840, 0, 1087, 1800))
        skip = pyautogui.locateOnScreen(path+'candle.png', region=region, grayscale=1, confidence=0.6)
    except:
        try:
            pyautogui.locateOnScreen(path+'esc.png', grayscale=1, confidence=0.6)
        except:
            enter_ui()
            return
    if not skip:
        wait_for_candle(.9)
    
    press_key('f')
    time.sleep(.2)
    press_key('esc')
    time.sleep(.3)
    global friend_count
    friend_count += 1

def loop():
    global current_page, light_collected
    while current_page <= total_pages:
        testImagePath = './cache/' + str(current_page) + '.png'
        pyautogui.screenshot(testImagePath)
        testImage = cv2.imread(testImagePath)
        # this loop helps double check missed friends
        for i in range(2):
            for star in find_flare_stars():
                pyautogui.click(star)
                light_collected += 1
                cv2.circle(testImage, (int(star[0]), int(star[1])), 40, (255, 0, 255), 5)
        while True:
            # move mouse out of way becuase we were clicking
            pyautogui.moveTo(500, 0)
            friends = find_all('unlit_friend')
            for friend in friends:
                x, y = pyautogui.center(friend)
                cv2.circle(testImage, (x, y), 12, (0, 255, 0), 2)
                light_friend(x, y)
            if len(friends) == 0:
                break
        press_key('c')
        cv2.imwrite(testImagePath, testImage)
        time.sleep(page_transition_time)
        pyautogui.moveTo(501, 0)
        current_page += 1

if __name__ == "__main__":
    print("Starting!!")
    start_time = time.time()
    time.sleep(1)
    try:
        pyautogui.locateOnScreen(path+'esc.png', grayscale=1, confidence=0.6)
    except:
        enter_ui()
    index_to_start()
    total_pages = get_total_pages()
    print(f"Total pages: {total_pages}")
    press_key('c')
    time.sleep(page_transition_time)
    loop()
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Lit {friend_count} friends, and collected {light_collected} light in {int(elapsed_time)} seconds")